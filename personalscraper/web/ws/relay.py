"""WebSocket event relay — Redis Streams → WebSocket fan-out (tm-shell feature).

This is the ONLY async module in ``personalscraper.web/`` per DESIGN §4.5.
Redis Streams provide both live transport and the reconnect cursor for replay.

See docs/features/tm-shell/DESIGN.md §4.5 for the full relay protocol.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

import redis.asyncio as aioredis

from personalscraper.conf.models.web import WebConfig
from personalscraper.logger import get_logger

logger = get_logger(__name__)

#: Interval in seconds between keep-alive pings to each connected client.
PING_INTERVAL = 30.0

#: Per-client send timeout (seconds) applied during broadcast fan-out.  A socket
#: that cannot accept a frame within this window is treated as dead and dropped,
#: so one stalled client never blocks fan-out for every other connection.
BROADCAST_SEND_TIMEOUT = 1.0


class ConnectionRegistry:
    """Thread-safe-enough set of active WebSocket connections for asyncio (single loop).

    Methods are synchronous (``add`` / ``discard`` operate on a plain ``set``).
    Broadcasting iterates a snapshot of the current connections so that dead
    sockets are removed without mutating the set during iteration.
    """

    def __init__(self) -> None:
        """Initialize an empty connection registry."""
        self._connections: set[Any] = set()

    def add(self, ws: Any) -> None:
        """Register a WebSocket connection.

        Args:
            ws: An accepted Starlette WebSocket instance.
        """
        self._connections.add(ws)

    def discard(self, ws: Any) -> None:
        """Unregister a WebSocket connection (idempotent).

        Args:
            ws: The WebSocket instance to remove.
        """
        self._connections.discard(ws)

    async def broadcast(self, msg: dict[str, Any]) -> None:
        """Send a JSON message to every registered connection.

        Each send is bounded by :data:`BROADCAST_SEND_TIMEOUT` via
        ``asyncio.wait_for`` so a single stalled client cannot block fan-out for
        the rest.  Connections that time out or raise during ``send_json``
        (disconnected / closed / wedged) are collected and removed after the
        iteration completes.

        Args:
            msg: A JSON-serialisable dict to send to all clients.
        """
        dead: list[Any] = []
        for ws in list(self._connections):
            try:
                await asyncio.wait_for(ws.send_json(msg), timeout=BROADCAST_SEND_TIMEOUT)
            except Exception:
                # Timeout (stalled client) or any transport error → drop it.
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)
        if dead:
            logger.warning("relay_clients_dropped", count=len(dead))

    @property
    def count(self) -> int:
        """Return the number of currently registered connections."""
        return len(self._connections)


async def init_redis_pool(web_config: WebConfig) -> aioredis.Redis:
    """Create a ``redis.asyncio`` connection pool from the web config.

    The pool connects lazily — no network I/O occurs until the first command.

    Args:
        web_config: Web configuration carrying ``redis_url``.

    Returns:
        An async Redis client ready for use (pool connects on first command).
    """
    return aioredis.from_url(web_config.redis_url, decode_responses=True)


def _entry_to_message(entry_id: str, fields: dict[str, str]) -> dict[str, Any]:
    """Convert a raw Redis stream entry into the standard WS message shape.

    Args:
        entry_id: The stream entry id (``<ms>-<seq>``).
        fields: The stream entry field mapping (expects ``envelope`` + ``type``).

    Returns:
        A message dict ``{"id", "type", "data"}``.

    Raises:
        ValueError: If ``envelope`` is not valid JSON (``json.JSONDecodeError``
            subclasses ``ValueError``).
        KeyError: If the decoded envelope has no ``data`` key.
        TypeError: If the decoded envelope is not subscriptable (e.g. ``null``).
    """
    envelope = json.loads(fields.get("envelope", "{}"))
    return {
        "id": entry_id,
        "type": fields.get("type", "unknown"),
        "data": envelope["data"],
    }


async def read_stream_loop(
    redis_pool: aioredis.Redis,
    registry: ConnectionRegistry,
    stream_key: str,
) -> None:
    """Tail the Redis Stream and broadcast every new entry to all connected WebSockets.

    Starts from ``$`` (live-only — no history).  Blocks on ``XREAD`` with a 5 s
    timeout so the asyncio event loop stays responsive.  Runs forever as a
    background task.  Redis exceptions are logged once and retried after a short
    sleep — this loop **never crashes the app**.

    Args:
        redis_pool: An async Redis client from :func:`init_redis_pool`.
        registry: The connection registry for broadcasting.
        stream_key: The Redis Stream key to read from.
    """
    last_id = "$"
    warned_down = False

    while True:
        try:
            result = cast(
                "list[tuple[str, list[tuple[str, dict[str, str]]]]] | None",
                await redis_pool.xread({stream_key: last_id}, block=5000, count=100),
            )
            warned_down = False  # Redis is reachable — reset warning flag.

            if result:
                for _stream_name, entries in result:
                    for entry_id, fields in entries:
                        # Parse/broadcast each entry in its OWN guard so a single
                        # malformed entry (bad JSON, missing data key) is skipped
                        # and logged once — never re-read forever.  last_id ALWAYS
                        # advances so the loop can never wedge on a poison entry.
                        try:
                            msg = _entry_to_message(entry_id, fields)
                        except (KeyError, ValueError, TypeError) as exc:
                            logger.warning("relay_entry_skipped", entry_id=entry_id, error=str(exc))
                            last_id = entry_id
                            continue
                        await registry.broadcast(msg)
                        last_id = entry_id
        except asyncio.CancelledError:
            raise
        except Exception:
            # Reserved for transport errors (Redis unreachable) — NOT per-entry
            # decode failures, which are handled above without wedging the loop.
            if not warned_down:
                logger.warning("redis_stream_read_failed", stream_key=stream_key)
                warned_down = True
            await asyncio.sleep(2)


async def replay_events(
    redis_pool: aioredis.Redis,
    stream_key: str,
    last_id: str,
) -> list[dict[str, Any]]:
    """Replay events from the stream after a given ID (**exclusive**).

    Uses ``XRANGE (last_id +`` per Redis Stream exclusive-range semantics.
    Called during the WebSocket handshake when the client passes
    ``?last_id=<stream-id>``.

    Args:
        redis_pool: An async Redis client.
        stream_key: The Redis Stream key.
        last_id: The last stream entry ID the client already saw.  Entries
            **strictly greater** than this ID are returned.

    Returns:
        A list of message dicts in the standard WS shape ``{id, type, data}``,
        ordered by stream position.  Returns an empty list on Redis errors.
    """
    try:
        entries = cast(
            "list[tuple[str, dict[str, str]]]",
            await redis_pool.xrange(stream_key, min=f"({last_id}", max="+"),
        )
    except Exception:
        logger.warning("redis_replay_failed", stream_key=stream_key, last_id=last_id)
        return []

    messages: list[dict[str, Any]] = []
    for entry_id, fields in entries:
        # Same poison-pill guard as the live loop: a malformed entry in the
        # replay range is skipped (logged once) instead of aborting the replay.
        try:
            messages.append(_entry_to_message(entry_id, fields))
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("relay_entry_skipped", entry_id=entry_id, error=str(exc))
    return messages


def _stream_id_le(a: str, b: str) -> bool:
    """Return ``True`` if Redis stream id *a* is less than or equal to *b*.

    Stream ids are ``<ms>-<seq>``; both components are compared as integers so
    that lexicographic surprises (e.g. ``"10-0"`` vs ``"9-0"``) never cause a
    mis-dedup during the replay→live handoff.

    Args:
        a: A stream id string.
        b: A stream id string.

    Returns:
        ``True`` when *a* orders at or before *b* in the stream.
    """

    def _parse(sid: str) -> tuple[int, int]:
        ms, _, seq = sid.partition("-")
        return (int(ms), int(seq) if seq else 0)

    return _parse(a) <= _parse(b)


class _ReplayGuard:
    """Per-connection forwarder that bridges the replay→live gap (DESIGN §4.5).

    Registered in the :class:`ConnectionRegistry` **before** the replay runs so
    live events emitted during the replay window are captured instead of lost.
    Until :meth:`open_live` is called, ``send_json`` buffers messages in memory;
    afterwards messages pass straight through to the wrapped socket.

    :meth:`open_live` flushes the buffer, dropping any entry whose stream id is
    ``<=`` the highest id already delivered by the replay (exactly-once dedup),
    then flips to pass-through with no ``await`` between the final empty-buffer
    check and the flip — so no live event can slip past un-forwarded.
    """

    def __init__(self, ws: Any) -> None:
        """Wrap *ws* in a buffering (not-yet-live) forwarder.

        Args:
            ws: The accepted Starlette WebSocket to forward live events to.
        """
        self._ws = ws
        self._live = False
        self._pending: list[dict[str, Any]] = []

    async def send_json(self, msg: dict[str, Any]) -> None:
        """Forward *msg* to the socket if live, otherwise buffer it.

        Called by :meth:`ConnectionRegistry.broadcast` during fan-out.  Buffering
        is a synchronous append (no ``await``), so while replay is streaming no
        concurrent socket write can occur.

        Args:
            msg: The live message to forward or buffer.
        """
        if self._live:
            await self._ws.send_json(msg)
        else:
            self._pending.append(msg)

    async def open_live(self, floor_id: str | None) -> None:
        """Flush buffered live events (deduped) and switch to pass-through.

        Drains ``_pending`` in batches — each ``await`` may let the relay append
        more, so the drain loops until the buffer is empty.  Entries whose id is
        ``<= floor_id`` were already delivered by the replay and are dropped.

        Args:
            floor_id: The highest stream id delivered during replay, or ``None``
                when no replay ran (nothing to dedup against).
        """
        while self._pending:
            batch = self._pending
            self._pending = []
            for msg in batch:
                if floor_id is not None and _stream_id_le(str(msg["id"]), floor_id):
                    continue
                await self._ws.send_json(msg)
        # No await between the empty-buffer check above and this flip: atomic.
        self._live = True

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

        Connections that raise during ``send_json`` (disconnected / closed) are
        collected and removed after the iteration completes.

        Args:
            msg: A JSON-serialisable dict to send to all clients.
        """
        dead: list[Any] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.discard(ws)

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
                        envelope_str = fields.get("envelope", "{}")
                        msg: dict[str, Any] = {
                            "id": entry_id,
                            "type": fields.get("type", "unknown"),
                            "data": json.loads(envelope_str)["data"],
                        }
                        await registry.broadcast(msg)
                        last_id = entry_id
        except asyncio.CancelledError:
            raise
        except Exception:
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
        envelope_str = fields.get("envelope", "{}")
        messages.append(
            {
                "id": entry_id,
                "type": fields.get("type", "unknown"),
                "data": json.loads(envelope_str)["data"],
            }
        )
    return messages

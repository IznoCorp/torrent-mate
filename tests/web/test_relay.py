"""Integration tests for the WebSocket event relay (tm-shell feature).

Two layers are exercised:

1. **Pure asyncio** — the relay primitives (``read_stream_loop`` fan-out,
   ``replay_events`` exclusive range, ``ConnectionRegistry`` dead-drop) driven
   directly via ``asyncio.run`` against ``fakeredis.FakeAsyncRedis``.  No HTTP
   layer, fully deterministic.
2. **TestClient** — the ``/ws/events`` endpoint: 4401 on missing/invalid
   session, ``ws.hello`` on connect, live fan-out of an XADD'd event, replay on
   reconnect with ``?last_id=``, and degraded operation when Redis is down.

WS cookie gotcha: httpx's TestClient does **not** attach its cookie jar to the
WebSocket handshake, so the ``tm_session`` cookie is passed explicitly via a
``cookie`` header after logging in over REST.  The Redis pool is injected by
patching ``personalscraper.web.app.init_redis_pool`` with an async factory that
builds a ``FakeAsyncRedis`` inside the app's own event loop; the test thread
XADDs through a synchronous ``FakeRedis`` sharing the same ``FakeServer``.

See docs/features/tm-shell/plan/phase-03-event-relay.md §3.4.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import fakeredis
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from personalscraper.config import Settings
from personalscraper.core.event_bus import event_to_envelope
from personalscraper.indexer.events import BackfillCompleted
from personalscraper.web.auth.passwords import hash_password
from personalscraper.web.ws.relay import (
    ConnectionRegistry,
    read_stream_loop,
    replay_events,
)
from tests.web._web_harness import make_web_app

# ── Test constants ────────────────────────────────────────────────────────────
TEST_USER = "testuser"
TEST_PASS = "test-password"
TEST_HASH = hash_password(TEST_PASS)
TEST_SECRET = "relay-integration-test-secret"
STREAM_KEY = "personalscraper:events"


# ── Helpers ───────────────────────────────────────────────────────────────────


class _MockWebSocket:
    """Minimal async WebSocket stub collecting messages sent via ``send_json``.

    Used by the pure-asyncio relay tests so broadcasts can be observed without
    a real HTTP server.
    """

    def __init__(self) -> None:
        """Initialise an empty message buffer."""
        self.messages: list[dict[str, Any]] = []

    async def send_json(self, msg: dict[str, Any]) -> None:
        """Record *msg* as if it had been sent to a client.

        Args:
            msg: The JSON-serialisable message the relay broadcast.
        """
        self.messages.append(msg)


def _make_event(scope: str = "full", scanned: int = 1) -> BackfillCompleted:
    """Build a minimal :class:`BackfillCompleted` event for test purposes.

    Args:
        scope: Backfill scope label.
        scanned: Number of items scanned.

    Returns:
        A frozen ``BackfillCompleted`` with default-zero metrics.
    """
    return BackfillCompleted(
        scope=scope,
        scanned=scanned,
        updated=0,
        skipped=0,
        failed=0,
        ids_added_count=0,
        ratings_added_count=0,
    )


def _stream_fields(event: BackfillCompleted) -> dict[str, str]:
    """Serialise *event* into the ``{envelope, type}`` fields the relay reads.

    Args:
        event: The event to serialise.

    Returns:
        The stream-entry field mapping (JSON envelope + event class name).
    """
    return {"envelope": json.dumps(event_to_envelope(event)), "type": type(event).__name__}


async def _await_until(predicate: Callable[[], bool], timeout: float = 5.0, interval: float = 0.02) -> bool:
    """Await until *predicate* is truthy or *timeout* elapses.

    Args:
        predicate: A zero-argument callable returning a bool.
        timeout: Maximum seconds to wait.
        interval: Sleep between polls.

    Returns:
        The final value of *predicate*.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        await asyncio.sleep(interval)
    return predicate()


def _build_app(test_config) -> tuple[Any, Any]:
    """Build a FastAPI app with the known relay-test credentials.

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.

    Returns:
        A ``(app, config)`` tuple — the config carries the overridden username.
    """
    web_cfg = test_config.web.model_copy(update={"username": TEST_USER})
    cfg = test_config.model_copy(update={"web": web_cfg})
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        web_password_hash=TEST_HASH,
        web_jwt_secret=TEST_SECRET,
    )
    return make_web_app(cfg, settings), cfg


def _patch_redis_pool(pool_factory: Callable[[], Any]) -> Any:
    """Patch ``app.init_redis_pool`` with an async factory built in the app loop.

    The lifespan awaits ``init_redis_pool`` on the app's event loop, so building
    the async client there (rather than in the test thread) guarantees correct
    loop affinity for ``fakeredis.FakeAsyncRedis``.

    Args:
        pool_factory: A zero-argument callable returning the Redis client the
            relay should use (a ``FakeAsyncRedis`` or a broken mock).

    Returns:
        A ``patch`` context manager targeting ``personalscraper.web.app``.
    """

    async def _fake_init(_web_config: Any) -> Any:
        return pool_factory()

    return patch("personalscraper.web.app.init_redis_pool", _fake_init)


def _login(client: TestClient) -> str:
    """Log in over REST and return the ``tm_session`` cookie value.

    Args:
        client: A ``TestClient`` with ``base_url="https://testserver"``.

    Returns:
        The signed session token to replay in the WebSocket handshake.
    """
    resp = client.post("/api/auth/login", json={"username": TEST_USER, "password": TEST_PASS})
    assert resp.status_code == 204
    return client.cookies["tm_session"]


def _recv_matching(ws: Any, predicate: Callable[[dict[str, Any]], bool], max_messages: int = 10) -> dict[str, Any]:
    """Receive JSON messages until one satisfies *predicate*.

    Skips keep-alive frames (``ws.ping``) that may interleave with data frames.

    Args:
        ws: The connected TestClient WebSocket.
        predicate: Returns True for the awaited message.
        max_messages: Safety bound on frames consumed before failing.

    Returns:
        The first message satisfying *predicate*.

    Raises:
        AssertionError: If no matching message arrives within *max_messages*.
    """
    for _ in range(max_messages):
        msg = ws.receive_json()
        if predicate(msg):
            return msg
    raise AssertionError("expected message never arrived")


# ═══════════════════════════════════════════════════════════════════════════════
# Pure-asyncio relay primitives
# ═══════════════════════════════════════════════════════════════════════════════


def test_read_stream_loop_broadcasts_new_entry() -> None:
    """``read_stream_loop`` picks up a freshly XADD'd entry and broadcasts it."""

    async def _run() -> None:
        redis = fakeredis.FakeAsyncRedis(decode_responses=True)
        registry = ConnectionRegistry()
        ws = _MockWebSocket()
        registry.add(ws)

        task = asyncio.create_task(read_stream_loop(redis, registry, STREAM_KEY))
        await asyncio.sleep(0.3)  # let the loop enter its blocking XREAD at the tail
        await redis.xadd(STREAM_KEY, _stream_fields(_make_event(scope="live")))

        assert await _await_until(lambda: len(ws.messages) == 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        msg = ws.messages[0]
        assert msg["type"] == "BackfillCompleted"
        assert "id" in msg
        assert msg["data"]["scope"] == "live"

    asyncio.run(_run())


def test_entry_to_message_resolves_type_from_envelope_only() -> None:
    """An entry carrying only ``envelope`` still resolves the real event type.

    Regression: the relay previously read the class name from a duplicated
    top-level ``type`` field, so a minimal manual ``XADD`` (the DESIGN §11
    manual-test path) that carries just the JSON envelope degraded every event
    to ``"unknown"`` on the client — breaking the feed's severity classification
    (no warning amber, no error red). The envelope is the single source of truth.
    """
    from personalscraper.web.ws.relay import _entry_to_message

    envelope_only = {"envelope": json.dumps(event_to_envelope(_make_event(scope="live")))}
    msg = _entry_to_message("1700000000000-0", envelope_only)
    assert msg["type"] == "BackfillCompleted"
    assert msg["data"]["scope"] == "live"

    # The redundant top-level field, when present, still works as a fallback.
    both_fields = _stream_fields(_make_event(scope="both"))
    assert _entry_to_message("1700000000001-0", both_fields)["type"] == "BackfillCompleted"


def test_replay_events_returns_entries_after_last_id() -> None:
    """``replay_events`` returns only entries strictly after ``last_id`` (exclusive)."""

    async def _run() -> None:
        redis = fakeredis.FakeAsyncRedis(decode_responses=True)
        id1 = await redis.xadd(STREAM_KEY, _stream_fields(_make_event(scope="first")))
        await redis.xadd(STREAM_KEY, _stream_fields(_make_event(scope="second")))

        after_first = await replay_events(redis, STREAM_KEY, id1)
        assert len(after_first) == 1
        assert after_first[0]["type"] == "BackfillCompleted"
        assert after_first[0]["data"]["scope"] == "second"

        from_zero = await replay_events(redis, STREAM_KEY, "0-0")
        assert [m["data"]["scope"] for m in from_zero] == ["first", "second"]

    asyncio.run(_run())


def test_read_stream_loop_skips_malformed_entry() -> None:
    """A malformed XADD entry is skipped (last_id advances) and the next good entry delivered.

    Regression for the poison-pill wedge: previously a per-entry JSON/envelope
    failure fell through to the outer ``except``, so ``last_id`` never advanced
    and the SAME bad entry was re-read forever (relay stuck, log spam every 2 s).
    """

    async def _run() -> None:
        redis = fakeredis.FakeAsyncRedis(decode_responses=True)
        registry = ConnectionRegistry()
        ws = _MockWebSocket()
        registry.add(ws)

        task = asyncio.create_task(read_stream_loop(redis, registry, STREAM_KEY))
        await asyncio.sleep(0.3)  # let the loop reach its blocking XREAD at the tail

        # Poison entry: envelope JSON has no "data" key → KeyError on parse.
        await redis.xadd(STREAM_KEY, {"envelope": json.dumps({"nope": 1}), "type": "Bad"})
        # Good entry immediately after — must still be delivered.
        await redis.xadd(STREAM_KEY, _stream_fields(_make_event(scope="after_poison")))

        assert await _await_until(lambda: any(m["data"].get("scope") == "after_poison" for m in ws.messages))
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # The poison entry was skipped (never broadcast); only the good one arrived.
        assert len(ws.messages) == 1
        assert ws.messages[0]["data"]["scope"] == "after_poison"

    asyncio.run(_run())


def test_replay_events_skips_malformed_entry() -> None:
    """``replay_events`` skips a malformed entry in the range and returns the good ones."""

    async def _run() -> None:
        redis = fakeredis.FakeAsyncRedis(decode_responses=True)
        # Poison: envelope is not valid JSON → ValueError on parse.
        await redis.xadd(STREAM_KEY, {"envelope": "this-is-not-json", "type": "Bad"})
        await redis.xadd(STREAM_KEY, _stream_fields(_make_event(scope="good")))

        messages = await replay_events(redis, STREAM_KEY, "0-0")
        assert [m["data"]["scope"] for m in messages] == ["good"]

    asyncio.run(_run())


def test_broadcast_drops_stalled_client(monkeypatch) -> None:
    """A client whose ``send_json`` hangs is dropped; other clients still receive.

    Regression for the head-of-line stall: one wedged socket must not block
    fan-out for everyone.  ``BROADCAST_SEND_TIMEOUT`` bounds each send.
    """
    monkeypatch.setattr("personalscraper.web.ws.relay.BROADCAST_SEND_TIMEOUT", 0.2)

    async def _run() -> None:
        registry = ConnectionRegistry()
        good = _MockWebSocket()
        stalled = _MockWebSocket()

        async def _hang(_msg: dict[str, Any]) -> None:
            await asyncio.sleep(10)  # far exceeds the (patched) 0.2 s send timeout

        stalled.send_json = _hang  # type: ignore[method-assign]
        registry.add(good)
        registry.add(stalled)

        await registry.broadcast({"type": "live"})

        assert registry.count == 1
        assert good.messages == [{"type": "live"}]

    asyncio.run(_run())


def test_replay_events_empty_when_none_after() -> None:
    """``replay_events`` returns an empty list when nothing follows ``last_id``."""

    async def _run() -> None:
        redis = fakeredis.FakeAsyncRedis(decode_responses=True)
        last_id = await redis.xadd(STREAM_KEY, _stream_fields(_make_event()))

        assert await replay_events(redis, STREAM_KEY, last_id) == []

    asyncio.run(_run())


def test_registry_broadcast_drops_dead_connection() -> None:
    """A connection raising on ``send_json`` is discarded after a broadcast."""

    async def _run() -> None:
        registry = ConnectionRegistry()
        good = _MockWebSocket()
        bad = _MockWebSocket()

        async def _boom(_msg: dict[str, Any]) -> None:
            raise RuntimeError("socket closed")

        bad.send_json = _boom  # type: ignore[method-assign]
        registry.add(good)
        registry.add(bad)

        await registry.broadcast({"type": "ping"})

        assert registry.count == 1
        assert good.messages == [{"type": "ping"}]

    asyncio.run(_run())


# ═══════════════════════════════════════════════════════════════════════════════
# TestClient — /ws/events endpoint
# ═══════════════════════════════════════════════════════════════════════════════


class TestWsAuth:
    """Handshake authentication for ``/ws/events``."""

    def test_no_cookie_closes_4401(self, test_config) -> None:
        """A WS connect with no ``tm_session`` cookie closes with code 4401.

        The endpoint now ``accept()``s BEFORE the auth check and closes with
        4401 afterwards.  Accept-then-close is load-bearing on real servers:
        uvicorn turns a *pre-accept* close into an HTTP 403 handshake rejection
        (browser sees 1006, never 4401), so the client's terminal-close /
        stop-reconnecting logic would be dead.  Post-accept close delivers a
        real 4401 close frame — which is what this test asserts.
        """
        app, _cfg = _build_app(test_config)
        server = fakeredis.FakeServer()
        with _patch_redis_pool(lambda: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)):
            with TestClient(app, base_url="https://testserver") as client:
                with pytest.raises(WebSocketDisconnect) as exc:
                    with client.websocket_connect("/ws/events") as ws:
                        ws.receive_json()
                assert exc.value.code == 4401

    def test_invalid_token_closes_4401(self, test_config) -> None:
        """A WS connect with a garbage token closes with code 4401.

        As with the no-cookie case, the socket is accepted first so the 4401 is
        delivered as a real WebSocket close frame rather than a pre-accept HTTP
        403 (which uvicorn would surface to the browser as an opaque 1006).
        """
        app, _cfg = _build_app(test_config)
        server = fakeredis.FakeServer()
        with _patch_redis_pool(lambda: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)):
            with TestClient(app, base_url="https://testserver") as client:
                with pytest.raises(WebSocketDisconnect) as exc:
                    with client.websocket_connect(
                        "/ws/events",
                        headers={"cookie": "tm_session=not-a-valid-jwt"},
                    ) as ws:
                        ws.receive_json()
                assert exc.value.code == 4401

    def test_authed_connect_receives_hello(self, test_config) -> None:
        """An authenticated WS connect receives ``ws.hello`` with ``build_commit``."""
        app, _cfg = _build_app(test_config)
        server = fakeredis.FakeServer()
        with _patch_redis_pool(lambda: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)):
            with TestClient(app, base_url="https://testserver") as client:
                token = _login(client)
                with client.websocket_connect(
                    "/ws/events",
                    headers={"cookie": f"tm_session={token}"},
                ) as ws:
                    hello = ws.receive_json()
                    assert hello["type"] == "ws.hello"
                    assert "build_commit" in hello["data"]


class TestWsLiveFanOut:
    """Live event fan-out from the Redis stream to a connected client."""

    def test_live_event_is_broadcast(self, test_config) -> None:
        """An XADD after connect is delivered to the client as ``{id,type,data}``."""
        app, cfg = _build_app(test_config)
        server = fakeredis.FakeServer()
        sync_redis = fakeredis.FakeRedis(server=server, decode_responses=True)
        with _patch_redis_pool(lambda: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)):
            with TestClient(app, base_url="https://testserver") as client:
                token = _login(client)
                with client.websocket_connect(
                    "/ws/events",
                    headers={"cookie": f"tm_session={token}"},
                ) as ws:
                    assert ws.receive_json()["type"] == "ws.hello"
                    time.sleep(0.3)  # let read_stream_loop reach the stream tail
                    sync_redis.xadd(cfg.web.stream_key, _stream_fields(_make_event(scope="fanned")))

                    msg = _recv_matching(ws, lambda m: m.get("type") == "BackfillCompleted")
                    assert msg["data"]["scope"] == "fanned"
                    assert "id" in msg


class TestWsReplay:
    """Replay-on-reconnect via the ``?last_id=`` query parameter."""

    def test_replay_missed_events_in_order(self, test_config) -> None:
        """Events seeded before connect are replayed in order via ``?last_id=0-0``."""
        app, cfg = _build_app(test_config)
        server = fakeredis.FakeServer()
        sync_redis = fakeredis.FakeRedis(server=server, decode_responses=True)
        # Seed two entries before the app starts, so the live loop (starting at
        # "$") never sees them — they are only reachable through replay.
        sync_redis.xadd(cfg.web.stream_key, _stream_fields(_make_event(scope="replay_1")))
        sync_redis.xadd(cfg.web.stream_key, _stream_fields(_make_event(scope="replay_2")))

        with _patch_redis_pool(lambda: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)):
            with TestClient(app, base_url="https://testserver") as client:
                token = _login(client)
                with client.websocket_connect(
                    "/ws/events?last_id=0-0",
                    headers={"cookie": f"tm_session={token}"},
                ) as ws:
                    assert ws.receive_json()["type"] == "ws.hello"
                    first = ws.receive_json()
                    second = ws.receive_json()
                    assert first["type"] == "BackfillCompleted"
                    assert [first["data"]["scope"], second["data"]["scope"]] == ["replay_1", "replay_2"]

    def test_event_during_replay_window_delivered_exactly_once(self, test_config, monkeypatch) -> None:
        """An event XADD'd during the replay window reaches the client exactly once.

        Regression for the replay→live gap: the forwarder is registered BEFORE
        replay, so a live event emitted while replay runs is buffered and
        flushed afterwards (deduped against the replay high-water id) instead of
        being lost between the XRANGE read and live registration.
        """
        # Shrink the ping interval so that if the fix regresses (event lost) the
        # loop drains quick pings and fails fast instead of blocking on the 30 s
        # default; on the happy path the event is flushed before any ping.
        monkeypatch.setattr("personalscraper.web.ws.routes.PING_INTERVAL", 0.2)
        app, cfg = _build_app(test_config)
        server = fakeredis.FakeServer()
        sync_redis = fakeredis.FakeRedis(server=server, decode_responses=True)
        # One historical event, reachable only via replay (?last_id=0-0).
        sync_redis.xadd(cfg.web.stream_key, _stream_fields(_make_event(scope="historical")))

        from personalscraper.web.ws import routes as ws_routes

        real_replay = ws_routes.replay_events

        async def _replay_then_inject(redis_pool: Any, stream_key: str, last_id: str) -> Any:
            """Run the real replay, then inject a live event mid-window."""
            result = await real_replay(redis_pool, stream_key, last_id)
            # Simulate an event landing AFTER the XRANGE read but before the
            # (previously buggy) live registration.
            sync_redis.xadd(stream_key, _stream_fields(_make_event(scope="during_replay")))
            await asyncio.sleep(0.4)  # let read_stream_loop broadcast it to the forwarder
            return result

        with _patch_redis_pool(lambda: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)):
            with patch.object(ws_routes, "replay_events", _replay_then_inject):
                with TestClient(app, base_url="https://testserver") as client:
                    token = _login(client)
                    with client.websocket_connect(
                        "/ws/events?last_id=0-0",
                        headers={"cookie": f"tm_session={token}"},
                    ) as ws:
                        assert ws.receive_json()["type"] == "ws.hello"
                        scopes: list[str] = []
                        for _ in range(12):
                            msg = ws.receive_json()
                            if msg.get("type") == "BackfillCompleted":
                                scopes.append(msg["data"]["scope"])
                            if scopes.count("historical") and scopes.count("during_replay"):
                                break
                        assert scopes.count("historical") == 1
                        assert scopes.count("during_replay") == 1


class TestWsKeepAlive:
    """Server-driven keep-alive ping loop on an idle connection."""

    def test_ping_arrives_and_connection_survives_pong(self, test_config, monkeypatch) -> None:
        """After idle > PING_INTERVAL a ``ws.ping`` arrives; a pong keeps it alive."""
        # Shrink the idle interval so the test does not wait the 30 s default.
        monkeypatch.setattr("personalscraper.web.ws.routes.PING_INTERVAL", 0.2)
        app, _cfg = _build_app(test_config)
        server = fakeredis.FakeServer()
        with _patch_redis_pool(lambda: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)):
            with TestClient(app, base_url="https://testserver") as client:
                token = _login(client)
                with client.websocket_connect(
                    "/ws/events",
                    headers={"cookie": f"tm_session={token}"},
                ) as ws:
                    assert ws.receive_json()["type"] == "ws.hello"
                    # Send nothing → a keep-alive ping must arrive after ~0.2 s idle.
                    ping = _recv_matching(ws, lambda m: m.get("type") == "ws.ping")
                    assert ping["type"] == "ws.ping"
                    # Reply pong; the receive/ping loop resets and pings again.
                    ws.send_text("pong")
                    ping2 = _recv_matching(ws, lambda m: m.get("type") == "ws.ping")
                    assert ping2["type"] == "ws.ping"


class TestWsDegraded:
    """Degraded operation: the app survives a broken Redis relay."""

    def test_rest_and_ws_hello_survive_redis_down(self, test_config) -> None:
        """REST routes and the WS handshake still work when the relay's Redis fails."""
        app, _cfg = _build_app(test_config)
        broken = AsyncMock()
        broken.xread.side_effect = ConnectionError("redis unreachable")

        with _patch_redis_pool(lambda: broken):
            with TestClient(app, base_url="https://testserver") as client:
                assert client.get("/api/health").status_code == 200
                token = _login(client)
                with client.websocket_connect(
                    "/ws/events",
                    headers={"cookie": f"tm_session={token}"},
                ) as ws:
                    assert ws.receive_json()["type"] == "ws.hello"


# ═══════════════════════════════════════════════════════════════════════════════
# Relay → projection wiring (S6 reg-health §2.1)
# ═══════════════════════════════════════════════════════════════════════════════


def test_read_stream_loop_updates_projection() -> None:
    """A ``CircuitBreakerOpened`` broadcast updates the projection to ``open``.

    Verifies the relay→projection wiring: when ``read_stream_loop`` parses an
    event and the optional *projection* parameter is provided, the projection
    reducer is called with the event type and data.
    """

    async def _run() -> None:
        from personalscraper.web.registry_projection import RegistryHealthProjection

        redis = fakeredis.FakeAsyncRedis(decode_responses=True)
        registry = ConnectionRegistry()
        ws = _MockWebSocket()
        registry.add(ws)
        projection = RegistryHealthProjection()

        task = asyncio.create_task(
            read_stream_loop(redis, registry, STREAM_KEY, projection=projection),
        )
        await asyncio.sleep(0.3)  # let the loop reach its blocking XREAD at the tail

        # XADD a CircuitBreakerOpened event (mimics what the pipeline process emits).
        envelope = json.dumps(
            {
                "_type": "CircuitBreakerOpened",
                "data": {
                    "breaker": "tmdb",
                    "failure_count": 5,
                    "last_error_class": "ApiError",
                    "last_error_message": "500 Internal Server Error",
                },
            }
        )
        await redis.xadd(STREAM_KEY, {"envelope": envelope, "type": "CircuitBreakerOpened"})

        # Wait for the message to flow through the loop.
        assert await _await_until(lambda: len(ws.messages) >= 1)
        # Give the projection.apply a tiny window to complete (it is synchronous
        # and runs before broadcast, so this is defensive).
        await asyncio.sleep(0.05)

        snap = projection.snapshot()
        assert "tmdb" in snap
        assert snap["tmdb"]["circuit_state"] == "open"
        assert snap["tmdb"]["failure_count_recent"] == 5
        assert snap["tmdb"]["last_failure_at"] is not None

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(_run())

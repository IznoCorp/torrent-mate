"""E2E smoke test for the web UI (tm-shell feature, DESIGN §8).

Boots uvicorn on an ephemeral port in a background thread, logs in over HTTP,
opens an authenticated WebSocket, publishes a test event via Redis, and
asserts the event is received on the WS connection — proving the entire pipe:
HTTP → auth → WS handshake → Redis relay → client fan-out.

Uses the real local Redis on a unique test stream key (cleaned up after the
test).  Skips cleanly when Redis is unavailable (CI-safe).
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
import uuid
from typing import Any

import httpx
import pytest
import redis
import uvicorn
from websockets.asyncio.client import connect as ws_connect

from personalscraper.config import Settings
from personalscraper.core.event_bus import event_to_envelope
from personalscraper.indexer.events import BackfillCompleted
from personalscraper.web.app import create_app
from personalscraper.web.auth.passwords import hash_password

# ── Test constants ────────────────────────────────────────────────────────────
TEST_USER = "e2e_smoke_user"
TEST_PASS = "e2e-smoke-password"
TEST_HASH = hash_password(TEST_PASS)
TEST_SECRET = "e2e-smoke-test-secret-at-least-32-bytes"


def _make_event(scope: str = "e2e_smoke") -> BackfillCompleted:
    """Build a minimal :class:`BackfillCompleted` event for the smoke test.

    Args:
        scope: Label to embed in the test event so the assertion can match it.

    Returns:
        A frozen ``BackfillCompleted`` with default-zero metrics.
    """
    return BackfillCompleted(
        scope=scope,
        scanned=1,
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


def _get_free_port() -> int:
    """Return an available TCP port on localhost.

    Binds a socket to port 0 (ephemeral), reads the assigned port, then
    closes the socket.  There is a small race window between close and
    reuse, but on a local dev machine with port=0 this is negligible.

    Returns:
        An available TCP port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _redis_reachable() -> bool:
    """Return ``True`` if the local Redis server is reachable.

    Returns:
        ``True`` if ``redis.Redis(...).ping()`` succeeds, ``False`` otherwise.
    """
    try:
        r = redis.Redis(host="127.0.0.1", port=6379, socket_connect_timeout=2)
        return r.ping()
    except Exception:
        return False


@pytest.mark.e2e
def test_web_e2e_smoke_boot_login_ws_event(test_config: Any) -> None:
    """Boot web app → login 204 → WS hello → XADD → event received.

    End-to-end smoke test per DESIGN §8:

    1. Build the FastAPI app configured with a unique Redis stream key.
    2. Start ``uvicorn.Server`` in a daemon thread on an ephemeral port.
    3. Login via ``httpx`` → assert 204 + extract ``tm_session`` cookie.
    4. Open an authenticated ``websockets`` connection to ``/ws/events``.
    5. Assert ``ws.hello`` arrives with ``build_commit``.
    6. ``XADD`` a test event through the real Redis client.
    7. Assert the event is received on the WebSocket with the correct shape.

    The unique stream key is deleted at the end so no test residue remains
    in Redis.

    Args:
        test_config: Synthetic ``Config`` fixture from ``tests/fixtures/config.py``.
    """
    if not _redis_reachable():
        pytest.skip("Redis not reachable on localhost:6379")

    # Unique stream key so parallel runs / leftover residue never collide.
    test_stream_key = f"pytest:e2e-smoke:{uuid.uuid4().hex[:12]}"

    # ── Build the app with real Redis, unique stream key ────────────────────
    web_cfg = test_config.web.model_copy(
        update={
            "username": TEST_USER,
            "redis_url": "redis://127.0.0.1:6379/0",
            "stream_key": test_stream_key,
        }
    )
    cfg = test_config.model_copy(update={"web": web_cfg})
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        web_password_hash=TEST_HASH,
        web_jwt_secret=TEST_SECRET,
    )

    app = create_app(cfg, settings)

    # ── Start uvicorn in a background thread ──────────────────────────────────
    port = _get_free_port()
    uvicorn_config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    uvicorn_server = uvicorn.Server(uvicorn_config)
    thread = threading.Thread(target=uvicorn_server.run, daemon=True)
    thread.start()

    # Poll until the server is accepting connections.
    base_url = f"http://127.0.0.1:{port}"
    started = False
    for _ in range(50):  # 5 s max (50 × 0.1 s)
        try:
            with httpx.Client(base_url=base_url, timeout=httpx.Timeout(2.0)) as probe:
                probe.get("/api/health")
            started = True
            break
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError):
            time.sleep(0.1)
    if not started:
        uvicorn_server.should_exit = True
        thread.join(timeout=5)
        pytest.fail("uvicorn server did not start within 5 s")

    # Redis client for XADD and cleanup (same Redis the app uses).
    test_redis = redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)

    try:
        # ── 1. Login via httpx → 204 ─────────────────────────────────────
        with httpx.Client(base_url=base_url) as client:
            resp = client.post(
                "/api/auth/login",
                json={"username": TEST_USER, "password": TEST_PASS},
            )
            assert resp.status_code == 204, f"Login returned {resp.status_code}, expected 204"
            session_cookie = client.cookies["tm_session"]
            assert session_cookie, "No tm_session cookie set after login"

        # ── 2. Open WebSocket + hello, 3. XADD + receive ─────────────────
        async def _ws_test() -> None:
            """Coroutine: connect, consume hello, wait for the published event."""
            ws_url = f"ws://127.0.0.1:{port}/ws/events"
            async with ws_connect(
                ws_url,
                additional_headers={"Cookie": f"tm_session={session_cookie}"},
            ) as ws:
                # Assert ws.hello
                hello_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                hello = json.loads(hello_raw)
                assert hello["type"] == "ws.hello", (
                    f"Expected ws.hello, got {hello.get('type')}: {hello}"
                )
                assert "build_commit" in hello["data"], (
                    f"ws.hello missing build_commit: {hello}"
                )

                # XADD a test event through the real Redis client.
                event = _make_event(scope="e2e_smoke")
                test_redis.xadd(test_stream_key, _stream_fields(event))

                # Wait for the event on the WS (skip pings / hello).
                for _ in range(30):
                    raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    msg = json.loads(raw)
                    if msg.get("type") == "BackfillCompleted":
                        assert msg["data"]["scope"] == "e2e_smoke", (
                            f"Event scope mismatch: {msg['data']}"
                        )
                        assert "id" in msg, f"Event missing stream id: {msg}"
                        return  # ✅

                raise AssertionError(
                    "Did not receive BackfillCompleted event on WS after 30 messages"
                )

        asyncio.run(_ws_test())

    finally:
        uvicorn_server.should_exit = True
        thread.join(timeout=5)
        # Clean up the test stream key so no residue remains in Redis.
        try:
            test_redis.delete(test_stream_key)
        except Exception:
            pass

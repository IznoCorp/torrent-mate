"""WebSocket event endpoint (tm-shell feature).

``GET /ws/events`` — authenticated WebSocket with replay-on-reconnect.
See docs/features/tm-shell/DESIGN.md §4.5 for the full protocol.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from personalscraper.logger import get_logger
from personalscraper.web.deps import _validate_session_token
from personalscraper.web.routes.version import _read_build_commit
from personalscraper.web.ws.relay import (
    PING_INTERVAL,
    ConnectionRegistry,
    replay_events,
)

logger = get_logger(__name__)

router = APIRouter()


@router.websocket("/ws/events")
async def ws_events(
    websocket: WebSocket,
    last_id: str | None = Query(None),
) -> None:
    """WebSocket endpoint for live event streaming with optional replay.

    **Handshake** — reads the ``tm_session`` cookie, validates the JWT, and
    closes with custom code ``4401`` if the session is missing or invalid
    (mirrors the REST guard's 401 but adapted for the WebSocket lifecycle).

    **Hello** — sends ``{"type": "ws.hello", "data": {"build_commit": ...}}``
    immediately after accept, before any replay or live messages.

    **Replay** — if ``?last_id=<stream-id>`` is present, replays all events
    strictly later than *last_id* (XRANGE exclusive) in order before entering
    live fan-out.

    **Live** — registers the connection and enters a receive/ping loop:
    client messages are ignored (they serve as pongs); every
    :data:`PING_INTERVAL` seconds of silence a ``{"type": "ws.ping"}`` is
    sent.  On disconnect the connection is removed from the registry.

    Args:
        websocket: The incoming WebSocket connection.
        last_id: Optional stream entry ID for replay (exclusive lower bound).
    """
    # ── Auth handshake ────────────────────────────────────────────────
    config = websocket.app.state.config
    settings = websocket.app.state.settings
    registry: ConnectionRegistry = websocket.app.state.ws_registry

    token = websocket.cookies.get("tm_session")
    if token is None:
        await websocket.close(code=4401)
        return

    session = _validate_session_token(token, settings.web_jwt_secret, config.web.username)
    if session is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    # ── Hello ─────────────────────────────────────────────────────────
    await websocket.send_json(
        {
            "type": "ws.hello",
            "data": {"build_commit": _read_build_commit()},
        }
    )

    # ── Replay (if client passed ?last_id=) ───────────────────────────
    redis_pool = websocket.app.state.redis
    if last_id and redis_pool is not None:
        messages = await replay_events(redis_pool, config.web.stream_key, last_id)
        for msg in messages:
            await websocket.send_json(msg)

    # ── Live fan-out ──────────────────────────────────────────────────
    registry.add(websocket)
    try:
        while True:
            try:
                # Wait for client messages (pong or anything) — ignored.
                await asyncio.wait_for(websocket.receive_text(), timeout=PING_INTERVAL)
            except asyncio.TimeoutError:
                # Idle timeout → send keep-alive ping.
                await websocket.send_json({"type": "ws.ping"})
    except WebSocketDisconnect:
        pass
    finally:
        registry.discard(websocket)

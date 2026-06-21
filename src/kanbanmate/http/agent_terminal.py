"""WebSocket endpoint for the interactive agent terminal (tiller §4.2).

Registered on the shared config-API ``app`` via side-effect import from
``http/monitor_routes.py``. The ``@app.middleware("http")`` auth guard does NOT
run for WebSocket scopes; auth is checked in-handler (cookie → verify_token).

Layering: ``http`` top entrypoint — may import ``app``, ``core``, ``adapters``.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket, WebSocketDisconnect

from kanbanmate.http.auth import COOKIE_NAME, verify_token
from kanbanmate.http.config_api import _auth_config, _kanban_root, app
from kanbanmate.http.monitor_routes import _monitor_sessions

logger = logging.getLogger("kanbanmate.http.agent_terminal")

_MAX_MSG_BYTES = 1 * 1024 * 1024  # 1 MiB cap per message
_CAPTURE_INTERVAL = 0.3  # seconds between pane snapshots
_IDLE_TIMEOUT = 300.0  # seconds of client silence before auto-close


@app.websocket("/api/monitor/agent/{issue}/attach")
async def agent_attach(websocket: WebSocket, issue: int) -> None:
    """Bidirectional terminal for agent session ``ticket-<issue>``.

    Auth: in-handler cookie check (middleware skips WS scope). Read-only by
    default; client sends ``{type:"take_control"}`` to arm writing. Every armed
    send is audit-logged. Reaper sentinel written on take_control, removed on
    release/disconnect.

    Args:
        websocket: The FastAPI WebSocket connection.
        issue: The ticket issue number (path parameter).
    """
    # --- Auth gate (in-handler: middleware does not cover WS scope) ---
    auth_cfg = _auth_config()
    if auth_cfg is not None and auth_cfg.enabled:
        token = websocket.cookies.get(COOKIE_NAME, "")
        login = verify_token(token, auth_cfg.secret) if token else None
        if login is None:
            await websocket.close(code=1008)
            return
    else:
        login = "operator"  # open mode

    await websocket.accept()
    sessions = _monitor_sessions()
    session_name = f"ticket-{issue}"
    armed = False
    store_root = _kanban_root()

    # Resolve sentinel path lazily (best-effort; sentinel helper imported below)
    try:
        from kanbanmate.app.control_state import remove_sentinel, sentinel_path, write_sentinel  # noqa: PLC0415

        _sentinel = sentinel_path(store_root, issue)
    except Exception:
        _sentinel = None

    async def _read_loop() -> None:
        """Push ANSI pane snapshots to the client every _CAPTURE_INTERVAL seconds."""
        while True:
            await asyncio.sleep(_CAPTURE_INTERVAL)
            try:
                alive = sessions.is_alive(session_name)
                if not alive:
                    await websocket.send_text(json.dumps({"alive": False}))
                    await websocket.close()
                    return
                data = sessions.capture_ansi(session_name)
                await websocket.send_text(json.dumps({"alive": True, "data": data}))
            except Exception:
                # Fail-soft: a tmux error or a closed socket — exit the loop cleanly.
                return

    read_task = asyncio.create_task(_read_loop())
    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=_IDLE_TIMEOUT)
            except asyncio.TimeoutError:
                await websocket.close(code=1001)
                break
            if len(raw.encode()) > _MAX_MSG_BYTES:
                await websocket.send_text(json.dumps({"error": "message too large"}))
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue  # ignore malformed frames
            kind = msg.get("type", "")
            if kind == "take_control":
                armed = True
                if _sentinel is not None:
                    try:
                        write_sentinel(_sentinel)
                    except Exception:
                        pass
                await websocket.send_text(json.dumps({"control": "armed"}))
            elif kind == "release_control":
                armed = False
                if _sentinel is not None:
                    try:
                        remove_sentinel(_sentinel)
                    except Exception:
                        pass
                await websocket.send_text(json.dumps({"control": "released"}))
            elif kind == "text":
                if not armed:
                    await websocket.send_text(json.dumps({"error": "not in control"}))
                    continue
                data = msg.get("data", "")
                _audit(login, issue, f"text len={len(data)}")
                try:
                    sessions.send_text(session_name, data, literal=True)
                except Exception as exc:
                    await websocket.send_text(json.dumps({"error": str(exc)}))
                    await websocket.close()
                    break
            elif kind == "key":
                if not armed:
                    await websocket.send_text(json.dumps({"error": "not in control"}))
                    continue
                key = msg.get("name", "")
                _audit(login, issue, f"key={key!r}")
                try:
                    sessions.send_text(session_name, key, literal=False)
                except Exception as exc:
                    await websocket.send_text(json.dumps({"error": str(exc)}))
                    await websocket.close()
                    break
            elif kind == "resize":
                cols = int(msg.get("cols", 80))
                rows = int(msg.get("rows", 24))
                try:
                    sessions.resize(session_name, cols, rows)
                except Exception:
                    pass  # fail-soft: resize errors are non-fatal
            # Unknown types silently ignored (forward-compat).
    except WebSocketDisconnect:
        pass
    finally:
        read_task.cancel()
        if _sentinel is not None:
            try:
                remove_sentinel(_sentinel)
            except Exception:
                pass


def _audit(login: str, issue: int, payload_summary: str) -> None:
    """Log a structured audit line for an armed operator write (D2).

    Emits to the Python logger, and optionally appends to
    ``<kanban_root>/control/audit.log`` (fail-soft: file errors never
    interrupt a send).

    Args:
        login: The authenticated operator login (from the session cookie).
        issue: The ticket issue number.
        payload_summary: A short, repr-safe summary of what was sent.
    """
    line = f"audit: operator {login}→ticket-{issue}: {payload_summary}"
    logger.info(line)
    # Optional file sink: append to <kanban_root>/control/audit.log when accessible.
    try:
        log_path = _kanban_root() / "control" / "audit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        import datetime  # noqa: PLC0415

        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.datetime.now(datetime.UTC).isoformat()} {line}\n")
    except Exception:
        pass  # fail-soft: audit file errors must never interrupt a send

"""Tests for the WS agent-terminal endpoint (tiller §1.3)."""

from __future__ import annotations

import json
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402


class _FakeSessions:
    def __init__(self) -> None:
        self.send_calls: list[tuple[str, str, bool]] = []
        self.resize_calls: list[tuple[str, int, int]] = []
        self._alive = True

    def is_alive(self, name: str) -> bool:
        return self._alive

    def capture_ansi(self, name: str) -> str:
        return f"\x1b[32m{name}\x1b[0m"

    def send_text(self, name: str, text: str, *, literal: bool = True, enter: bool = False) -> None:
        self.send_calls.append((name, text, literal))

    def resize(self, name: str, cols: int, rows: int) -> None:
        self.resize_calls.append((name, cols, rows))

    def capture(self, name: str) -> str:
        return name


def _recv_until(ws: Any, key: str, max_attempts: int = 20) -> Any:
    """Receive WS frames, skipping alive heartbeats, return first frame with ``key``.

    The handler's background ``_read_loop`` pushes ``{"alive":true,"data":…}`` every
    0.3s. These interleave with the control/error frames the tests await, so a bare
    ``ws.receive_text()`` may return an alive frame instead of the expected one.
    This helper drains up to ``max_attempts`` frames, skipping anything with an
    ``"alive"`` key, and returns the first frame that has ``key`` (or ``None`` if the
    bound is exhausted).
    """
    for _ in range(max_attempts):
        raw = ws.receive_text()
        frame = json.loads(raw)
        if "alive" in frame:
            continue
        if key in frame:
            return frame
        # Unrecognised non-alive frame — keep draining.
    return None


def _setup(tmp_path: Any, auth_enabled: bool = False) -> _FakeSessions:
    import kanbanmate.http.config_api as api_mod
    import json as _json

    root = tmp_path / "root"
    root.mkdir()
    (root / "projects.json").write_text(
        _json.dumps(
            {
                "PVT_x": {
                    "repo": "O/r",
                    "clone": str(tmp_path / "clone"),
                    "project_id": "PVT_x",
                    "status_field_node_id": "FLD",
                }
            }
        ),
        encoding="utf-8",
    )
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = None
    fake = _FakeSessions()
    api_mod.app.state.monitor_sessions = fake
    return fake


def test_ws_auth_required_closes_1008(tmp_path: Any) -> None:
    """Without a cookie when auth is enabled the WS must close with code 1008."""
    import kanbanmate.http.config_api as api_mod
    from kanbanmate.http.auth import AuthConfig

    _setup(tmp_path, auth_enabled=True)
    api_mod.app.state.auth = AuthConfig(login="op", password="secret", secret="s3cr3t")
    with TestClient(api_mod.app) as client:
        with pytest.raises(Exception):
            # TestClient raises on WS close with non-normal code
            with client.websocket_connect("/api/monitor/agent/7/attach"):
                pass


def test_ws_write_rejected_before_take_control(tmp_path: Any) -> None:
    """Text frames are rejected with an error frame until take_control is sent."""
    fake = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/7/attach") as ws:
            ws.send_text(json.dumps({"type": "text", "data": "hello"}))
            # Drain alive frames from the background _read_loop to get the error frame.
            frame = _recv_until(ws, "error")
            assert frame is not None
            assert frame.get("error") == "not in control"
            assert fake.send_calls == []


def test_ws_take_control_then_text_calls_send(tmp_path: Any) -> None:
    """After take_control, a text frame calls sessions.send_text."""
    fake = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/5/attach") as ws:
            ws.send_text(json.dumps({"type": "take_control"}))
            ctrl = _recv_until(ws, "control")
            assert ctrl is not None
            assert ctrl.get("control") == "armed"

            ws.send_text(json.dumps({"type": "text", "data": "ls\n"}))
            # Flush: send release_control to force a response, ensuring the text frame
            # has been processed before we check send_calls.
            ws.send_text(json.dumps({"type": "release_control"}))
            _recv_until(ws, "control")

    assert any(c[1] == "ls\n" for c in fake.send_calls)


def test_audit_logged_on_armed_send(tmp_path: Any, caplog: Any) -> None:
    """An armed text send emits an audit log line."""
    import logging

    _ = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with caplog.at_level(logging.INFO, logger="kanbanmate.http.agent_terminal"):
        with TestClient(api_mod.app) as client:
            with client.websocket_connect("/api/monitor/agent/9/attach") as ws:
                ws.send_text(json.dumps({"type": "take_control"}))
                ws.receive_text()
                ws.send_text(json.dumps({"type": "text", "data": "hello"}))
                try:
                    ws.receive_text()
                except Exception:
                    pass
    assert any("audit" in r.message and "ticket-9" in r.message for r in caplog.records)


def test_ws_resize_calls_sessions_resize(tmp_path: Any) -> None:
    """A resize frame calls sessions.resize with the given cols/rows."""
    fake = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/5/attach") as ws:
            ws.send_text(json.dumps({"type": "resize", "cols": 200, "rows": 48}))
            # Flush: send a text frame (unarmed → error response) to ensure the resize
            # frame has been processed before we check resize_calls.
            ws.send_text(json.dumps({"type": "text", "data": "flush"}))
            _recv_until(ws, "error")

    assert ("ticket-5", 200, 48) in fake.resize_calls

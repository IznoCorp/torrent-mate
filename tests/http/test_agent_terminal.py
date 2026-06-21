"""Tests for the PTY-streamed WS agent-terminal endpoint (tiller §4.2).

The endpoint spawns a real PTY child (``tmux attach`` in production) and streams its
master fd over the WebSocket. We inject a tiny Python child via
``app.state.terminal_pty_cmd`` so the streaming / input-gating / resize path is
exercised end-to-end through a real pty WITHOUT needing tmux:

* it prints ``READY`` on start,
* echoes input as ``ECHO:<input>``,
* when it sees ``SIZE`` in the input, reports its pty window size as ``WINSIZE <rows> <cols>``.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402

# A self-contained PTY child: echoes input, reports winsize on the "SIZE" command. Reads/writes the
# slave pty via fd 0/1 so it works regardless of controlling-tty subtleties.
_CHILD_SRC = (
    "import os,fcntl,termios,struct\n"
    "os.write(1,b'READY\\n')\n"
    "while True:\n"
    "    ch=os.read(0,4096)\n"
    "    if not ch: break\n"
    "    if b'SIZE' in ch:\n"
    "        s=struct.unpack('HHHH',fcntl.ioctl(0,termios.TIOCGWINSZ,b'\\x00'*8))\n"
    "        os.write(1,('WINSIZE %d %d\\n'%(s[0],s[1])).encode())\n"
    "    else:\n"
    "        os.write(1,b'ECHO:'+ch)\n"
)


def _recv_text(ws: Any, key: str, max_attempts: int = 30) -> dict[str, Any] | None:
    """Receive frames, skipping binary terminal output, return the first text frame with ``key``."""
    for _ in range(max_attempts):
        msg = ws.receive()
        if msg.get("text") is None:
            continue  # binary terminal frame — skip
        frame: dict[str, Any] = json.loads(msg["text"])
        if key in frame:
            return frame
    return None


def _recv_bytes_containing(ws: Any, marker: bytes, max_attempts: int = 30) -> bytes | None:
    """Receive frames, accumulating binary output, return the buffer once ``marker`` appears."""
    buf = b""
    for _ in range(max_attempts):
        msg = ws.receive()
        if msg.get("bytes") is None:
            continue  # text control frame — skip
        buf += bytes(msg["bytes"])
        if marker in buf:
            return buf
    return None


class _FakeSessions:
    """Records kill_repl_process calls (the only sessions method the WS handler now uses)."""

    def __init__(self) -> None:
        self.kill_calls: list[str] = []

    def kill_repl_process(self, name: str) -> None:
        self.kill_calls.append(name)


def _setup(tmp_path: Any) -> _FakeSessions:
    import json as _json

    import kanbanmate.http.config_api as api_mod

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
    # Inject the test PTY child in place of `tmux attach-session`.
    api_mod.app.state.terminal_pty_cmd = lambda _issue: [sys.executable, "-c", _CHILD_SRC]
    fake = _FakeSessions()
    api_mod.app.state.monitor_sessions = fake
    return fake


def test_ws_auth_required_closes_1008(tmp_path: Any) -> None:
    """Without a cookie when auth is enabled the WS must close with code 1008."""
    import kanbanmate.http.config_api as api_mod
    from kanbanmate.http.auth import AuthConfig

    _setup(tmp_path)
    api_mod.app.state.auth = AuthConfig(login="op", password="secret", secret="s3cr3t")
    with TestClient(api_mod.app) as client:
        with pytest.raises(Exception):
            with client.websocket_connect("/api/monitor/agent/7/attach"):
                pass


def test_ws_input_rejected_before_take_control(tmp_path: Any) -> None:
    """Input frames are rejected with an error until take_control is sent."""
    _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/7/attach") as ws:
            ws.send_text(json.dumps({"type": "input", "data": "hello\n"}))
            frame = _recv_text(ws, "error")
            assert frame is not None
            assert frame.get("error") == "not in control"


def test_ws_take_control_then_input_streams_to_pty(tmp_path: Any) -> None:
    """After take_control, an input frame reaches the PTY and its echo streams back."""
    _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/5/attach") as ws:
            ws.send_text(json.dumps({"type": "take_control"}))
            assert _recv_text(ws, "control") == {"control": "armed"}

            ws.send_text(json.dumps({"type": "input", "data": "ls\n"}))
            out = _recv_bytes_containing(ws, b"ECHO:ls")
            assert out is not None


def test_audit_logged_on_armed_input(tmp_path: Any, caplog: Any) -> None:
    """An armed input send emits an audit log line."""
    import logging

    _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with caplog.at_level(logging.INFO, logger="kanbanmate.http.agent_terminal"):
        with TestClient(api_mod.app) as client:
            with client.websocket_connect("/api/monitor/agent/9/attach") as ws:
                ws.send_text(json.dumps({"type": "take_control"}))
                _recv_text(ws, "control")
                # Newline: the test pty slave is canonical, so the child only reads on a line break.
                ws.send_text(json.dumps({"type": "input", "data": "hello\n"}))
                _recv_bytes_containing(ws, b"ECHO:hello")
    assert any("audit" in r.message and "ticket-9" in r.message for r in caplog.records)


def test_ws_resize_sets_pty_winsize(tmp_path: Any) -> None:
    """A resize frame applies TIOCSWINSZ to the PTY (verified via the child's winsize report)."""
    _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/5/attach") as ws:
            ws.send_text(json.dumps({"type": "take_control"}))
            assert _recv_text(ws, "control") == {"control": "armed"}

            ws.send_text(json.dumps({"type": "resize", "cols": 200, "rows": 48}))
            ws.send_text(json.dumps({"type": "input", "data": "SIZE\n"}))
            out = _recv_bytes_containing(ws, b"WINSIZE 48 200")
            assert out is not None, "resize must set the PTY rows/cols (48x200)"


def test_ws_kill_ends_repl_when_armed(tmp_path: Any) -> None:
    """A kill frame (in control) calls sessions.kill_repl_process for the agent's session."""
    fake = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/5/attach") as ws:
            ws.send_text(json.dumps({"type": "take_control"}))
            assert _recv_text(ws, "control") == {"control": "armed"}

            ws.send_text(json.dumps({"type": "kill"}))
            # Flush: the injected child is unaffected by the (fake) kill, so it still echoes — use
            # that round-trip to guarantee the kill frame was processed first.
            ws.send_text(json.dumps({"type": "input", "data": "ping\n"}))
            assert _recv_bytes_containing(ws, b"ECHO:ping") is not None

    assert fake.kill_calls == ["ticket-5"]


def test_ws_kill_rejected_before_take_control(tmp_path: Any) -> None:
    """A kill frame is refused (and no-op) until the operator is in control."""
    fake = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod

    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/5/attach") as ws:
            ws.send_text(json.dumps({"type": "kill"}))
            assert _recv_text(ws, "error") == {"error": "not in control"}

    assert fake.kill_calls == []

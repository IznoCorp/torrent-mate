# Phase 1 — Backend terminal

## Gate

**No prior phase required.** This is the first phase. Branch `feat/tiller` must exist and
`make check` must be green on the base commit before starting.

## Overview

Add `resize` + `capture_ansi` to the `Sessions` port and `TmuxSessions` adapter, implement the
WebSocket endpoint `/api/monitor/agent/{issue}/attach` in a new `http/agent_terminal.py` module,
wire reaper sentinel coordination via a new `app/control_state.py` helper, and add per-send audit
logging. Five commits — one per sub-phase.

---

## Sub-phase 1.1 — Sessions.resize port + TmuxSessions impl

**Commit:** `feat(tiller): add Sessions.resize port + TmuxSessions impl`

**Files touched:**

- Modify: `src/kanbanmate/ports/workspace.py` — add `resize(name, cols, rows) -> None` to `Sessions`
  Protocol (after `send_text`).
- Modify: `src/kanbanmate/adapters/workspace/sessions.py` — add `TmuxSessions.resize()`.
- Create: `tests/adapters/workspace/test_sessions_resize.py`

**What to implement:**

In `ports/workspace.py`, after the `send_text` method in the `Sessions` Protocol:

```python
def resize(self, name: str, cols: int, rows: int) -> None:
    """Resize session ``name``'s window to ``cols`` × ``rows``.

    Runs ``tmux resize-window -t <name> -x <cols> -y <rows>`` (argv-list,
    no shell) so the agent's terminal wrapping matches the browser xterm size.

    Args:
        name: The session name (e.g. ``ticket-7``).
        cols: Number of terminal columns.
        rows: Number of terminal rows.
    """
    ...
```

In `adapters/workspace/sessions.py`, add after `send_text`:

```python
def resize(self, name: str, cols: int, rows: int) -> None:
    """Resize session *name*'s window to *cols* × *rows* (DESIGN §4.1).

    Args:
        name: The session name to resize.
        cols: Terminal width in columns.
        rows: Terminal height in rows.
    """
    self._runner(
        ["tmux", "resize-window", "-t", name, "-x", str(cols), "-y", str(rows)],
        check=True,
    )
```

**Tests** (`tests/adapters/workspace/test_sessions_resize.py`):

```python
"""Tests for TmuxSessions.resize (tiller §1.1)."""
from __future__ import annotations
import subprocess
from kanbanmate.adapters.workspace.sessions import TmuxSessions

def _fake_run(calls):
    def runner(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")
    return runner

def test_resize_builds_correct_argv() -> None:
    calls: list[list[str]] = []
    s = TmuxSessions(runner=_fake_run(calls))
    s.resize("ticket-7", cols=220, rows=50)
    assert calls[-1] == [
        "tmux", "resize-window", "-t", "ticket-7", "-x", "220", "-y", "50"
    ]

def test_resize_uses_check_true() -> None:
    """resize must raise on non-zero exit (check=True path)."""
    def failing_runner(argv, **kwargs):
        if "resize-window" in argv:
            raise subprocess.CalledProcessError(1, argv)
        return subprocess.CompletedProcess(argv, 0)
    s = TmuxSessions(runner=failing_runner)
    import pytest
    with pytest.raises(subprocess.CalledProcessError):
        s.resize("ticket-7", 80, 24)
```

Run: `pytest tests/adapters/workspace/test_sessions_resize.py -v` → 2 PASS.

---

## Sub-phase 1.2 — ANSI capture variant

**Commit:** `feat(tiller): add capture_ansi variant to Sessions port + TmuxSessions`

**Files touched:**

- Modify: `src/kanbanmate/ports/workspace.py` — add `capture_ansi(name) -> str` to `Sessions`.
- Modify: `src/kanbanmate/adapters/workspace/sessions.py` — add `TmuxSessions.capture_ansi()`.
- Create: `tests/adapters/workspace/test_sessions_capture_ansi.py`

**What to implement:**

In `ports/workspace.py`, after `capture`:

```python
def capture_ansi(self, name: str) -> str:
    """Return the ANSI-escape-preserved contents of session ``name``'s active pane.

    Like :meth:`capture` but passes ``-e`` to ``tmux capture-pane`` so ANSI
    colour/style sequences are included. Used by the WS terminal stream so
    xterm.js renders colour faithfully. The existing :meth:`capture` (no ``-e``)
    is unchanged for the read-only tail and all other callers.

    Args:
        name: The session name whose active pane to snapshot.

    Returns:
        The joined (``-J``), ANSI-preserved (``-e``) pane text.
    """
    ...
```

In `adapters/workspace/sessions.py`, after `capture`:

```python
def capture_ansi(self, name: str) -> str:
    """ANSI-preserving capture (``-e``) for the interactive terminal stream (tiller §4.2).

    Args:
        name: The session name whose active pane to snapshot.

    Returns:
        The joined, ANSI-preserved pane text (empty string when runner returns no stdout).
    """
    res = self._runner(
        ["tmux", "capture-pane", "-p", "-J", "-e", "-t", name],
        capture_output=True,
        text=True,
        check=True,
    )
    return res.stdout or ""
```

**Tests** (`tests/adapters/workspace/test_sessions_capture_ansi.py`):

```python
"""Tests for TmuxSessions.capture_ansi (tiller §1.2)."""
from __future__ import annotations
import subprocess
from kanbanmate.adapters.workspace.sessions import TmuxSessions

def _recording_runner(output: str = ""):
    calls: list[list[str]] = []
    def runner(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr="")
    return runner, calls

def test_capture_ansi_includes_e_flag() -> None:
    runner, calls = _recording_runner("\x1b[32mgreen\x1b[0m")
    s = TmuxSessions(runner=runner)
    result = s.capture_ansi("ticket-3")
    assert "-e" in calls[-1]
    assert "ticket-3" in calls[-1]
    assert result == "\x1b[32mgreen\x1b[0m"

def test_capture_plain_does_not_include_e_flag() -> None:
    """Existing capture() must remain unchanged (no -e)."""
    runner, calls = _recording_runner("plain")
    s = TmuxSessions(runner=runner)
    s.capture("ticket-3")
    assert "-e" not in calls[-1]
```

Run: `pytest tests/adapters/workspace/test_sessions_capture_ansi.py -v` → 2 PASS.

---

## Sub-phase 1.3 — http/agent_terminal.py WebSocket endpoint

**Commit:** `feat(tiller): add WS /api/monitor/agent/{issue}/attach endpoint`

**Files touched:**

- Create: `src/kanbanmate/http/agent_terminal.py`
- Modify: `src/kanbanmate/http/monitor_routes.py` — add side-effect import at the bottom.
- Create: `tests/http/test_agent_terminal.py`

**What to implement in `src/kanbanmate/http/agent_terminal.py`:**

```python
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
from kanbanmate.http.config_api import _auth_config, _kanban_root, _resolve_entry, app
from kanbanmate.http.monitor_routes import _monitor_sessions

logger = logging.getLogger("kanbanmate.http.agent_terminal")

_MAX_MSG_BYTES = 1 * 1024 * 1024   # 1 MiB cap per message
_CAPTURE_INTERVAL = 0.3             # seconds between pane snapshots
_IDLE_TIMEOUT = 300.0               # seconds of client silence before auto-close


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

    Args:
        login: The authenticated operator login (from the session cookie).
        issue: The ticket issue number.
        payload_summary: A short, repr-safe summary of what was sent.
    """
    logger.info("audit: operator %s→ticket-%s: %s", login, issue, payload_summary)
```

Add at the **bottom** of `src/kanbanmate/http/monitor_routes.py`:

```python
# Side-effect import: registers the agent-terminal WS endpoint on `app` (tiller §1.3).
import kanbanmate.http.agent_terminal as _agent_terminal  # noqa: F401, E402
```

**Tests** (`tests/http/test_agent_terminal.py`):

```python
"""Tests for the WS agent-terminal endpoint (tiller §1.3)."""
from __future__ import annotations
import json
import pytest

pytest.importorskip("fastapi", reason="[ui] extra not installed")

from fastapi.testclient import TestClient  # noqa: E402

class _FakeSessions:
    def __init__(self) -> None:
        self.send_calls: list[tuple] = []
        self.resize_calls: list[tuple] = []
        self._alive = True

    def is_alive(self, name: str) -> bool:
        return self._alive

    def capture_ansi(self, name: str) -> str:
        return f"\x1b[32m{name}\x1b[0m"

    def send_text(self, name, text, *, literal=True, enter=False) -> None:
        self.send_calls.append((name, text, literal))

    def resize(self, name: str, cols: int, rows: int) -> None:
        self.resize_calls.append((name, cols, rows))

    def capture(self, name: str) -> str:
        return name


def _setup(tmp_path, auth_enabled=False):
    import kanbanmate.http.config_api as api_mod
    import json as _json
    root = tmp_path / "root"
    root.mkdir()
    (root / "projects.json").write_text(
        _json.dumps({"PVT_x": {"repo": "O/r", "clone": str(tmp_path / "clone"),
                               "project_id": "PVT_x", "status_field_node_id": "FLD"}}),
        encoding="utf-8",
    )
    api_mod.app.state.kanban_root = root
    api_mod.app.state.auth = None
    fake = _FakeSessions()
    api_mod.app.state.monitor_sessions = fake
    return fake


def test_ws_auth_required_closes_1008(tmp_path) -> None:
    """Without a cookie when auth is enabled the WS must close with code 1008."""
    import kanbanmate.http.config_api as api_mod
    from kanbanmate.http.auth import AuthConfig, make_token
    fake = _setup(tmp_path, auth_enabled=True)
    api_mod.app.state.auth = AuthConfig(login="op", password="secret", secret="s3cr3t")
    with TestClient(api_mod.app) as client:
        with pytest.raises(Exception):
            # TestClient raises on WS close with non-normal code
            with client.websocket_connect("/api/monitor/agent/7/attach"):
                pass


def test_ws_write_rejected_before_take_control(tmp_path) -> None:
    """Text frames are rejected with an error frame until take_control is sent."""
    fake = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod
    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/7/attach") as ws:
            ws.send_text(json.dumps({"type": "text", "data": "hello"}))
            frame = json.loads(ws.receive_text())
            assert frame.get("error") == "not in control"
            assert fake.send_calls == []


def test_ws_take_control_then_text_calls_send(tmp_path) -> None:
    """After take_control, a text frame calls sessions.send_text."""
    fake = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod
    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/5/attach") as ws:
            ws.send_text(json.dumps({"type": "take_control"}))
            _resp = json.loads(ws.receive_text())  # {"control": "armed"}
            ws.send_text(json.dumps({"type": "text", "data": "ls\n"}))
            # Drain any queued frame
            try:
                ws.receive_text()
            except Exception:
                pass
    assert any(c[1] == "ls\n" for c in fake.send_calls)


def test_ws_resize_calls_sessions_resize(tmp_path) -> None:
    """A resize frame calls sessions.resize with the given cols/rows."""
    fake = _setup(tmp_path)
    import kanbanmate.http.config_api as api_mod
    with TestClient(api_mod.app) as client:
        with client.websocket_connect("/api/monitor/agent/5/attach") as ws:
            ws.send_text(json.dumps({"type": "resize", "cols": 200, "rows": 48}))
            try:
                ws.receive_text()
            except Exception:
                pass
    assert ("ticket-5", 200, 48) in fake.resize_calls
```

Run: `pytest tests/http/test_agent_terminal.py -v` → 4 PASS.

---

## Sub-phase 1.4 — Reaper sentinel coordination

**Commit:** `feat(tiller): add control_state sentinel + reaper suspend-under-control`

**Files touched:**

- Create: `src/kanbanmate/app/control_state.py`
- Modify: `src/kanbanmate/app/reaper.py` — add sentinel check at top of `_end_done_session`.
- Create: `tests/app/test_control_state.py`

**What to implement in `src/kanbanmate/app/control_state.py`:**

```python
"""Per-ticket "human attached" sentinel for reaper coordination (tiller §4.4).

The WS handler writes ``control/ticket-<n>.attached`` under the project's resolved
store root when a human takes control; the reaper skips ``end_session`` while the
sentinel is present (or deletes it as stale after ``stale_minutes``). Pure path
helpers + thin filesystem ops — no I/O inside ``core/``.
"""
from __future__ import annotations

import time
from pathlib import Path

_DEFAULT_STALE_MINUTES = 5


def sentinel_path(store_root: Path, ticket: int) -> Path:
    """Return the per-ticket sentinel path ``control/ticket-<n>.attached``.

    Args:
        store_root: The project's runtime store root (e.g. ``~/.kanban-km/projects/<id>``).
        ticket: The issue number.

    Returns:
        The sentinel file path (not necessarily existing).
    """
    return store_root / "control" / f"ticket-{ticket}.attached"


def write_sentinel(path: Path) -> None:
    """Create (or touch) the sentinel file, creating parent dirs as needed.

    Args:
        path: The sentinel path returned by :func:`sentinel_path`.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def remove_sentinel(path: Path) -> None:
    """Remove the sentinel file if it exists (best-effort, no raise).

    Args:
        path: The sentinel path to remove.
    """
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def is_attached(path: Path, *, stale_minutes: int = _DEFAULT_STALE_MINUTES) -> bool:
    """Return whether the sentinel is present and not stale.

    A sentinel older than ``stale_minutes`` is treated as stale (client crashed
    without releasing control) and removed so the reaper is not pinned forever.

    Args:
        path: The sentinel path.
        stale_minutes: Age in minutes after which the sentinel is treated as stale.

    Returns:
        ``True`` if the sentinel exists and is fresh; ``False`` otherwise.
    """
    if not path.exists():
        return False
    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > stale_minutes * 60:
        remove_sentinel(path)
        return False
    return True
```

**Modify `src/kanbanmate/app/reaper.py`** — in `_end_done_session`, add at the very top (before
any `repl_alive` call):

```python
    # Sentinel check (tiller §4.4): skip end_session while the operator has taken control.
    try:
        from kanbanmate.app.control_state import is_attached, sentinel_path  # noqa: PLC0415
        _store_root = getattr(deps.store, "_root", None)
        if _store_root is not None and is_attached(sentinel_path(_store_root, state.issue_number)):
            logger.info(
                "reaper: end_session deferred for #%s — human attached (tiller sentinel)",
                state.issue_number,
            )
            return False
    except Exception:
        pass  # fail-soft: a broken sentinel check must never block the reaper
```

**Tests** (`tests/app/test_control_state.py`):

```python
"""Tests for app/control_state sentinel helpers (tiller §1.4)."""
from __future__ import annotations
import time
from pathlib import Path
from kanbanmate.app.control_state import (
    is_attached, remove_sentinel, sentinel_path, write_sentinel,
)

def test_sentinel_path_shape(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 7)
    assert p == tmp_path / "control" / "ticket-7.attached"

def test_write_creates_file(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 3)
    write_sentinel(p)
    assert p.exists()

def test_is_attached_returns_true_when_fresh(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 3)
    write_sentinel(p)
    assert is_attached(p, stale_minutes=5) is True

def test_is_attached_returns_false_when_absent(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 99)
    assert is_attached(p, stale_minutes=5) is False

def test_stale_sentinel_removed_and_returns_false(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 4)
    write_sentinel(p)
    # Back-date the mtime by 10 minutes
    past = time.time() - 600
    import os
    os.utime(p, (past, past))
    result = is_attached(p, stale_minutes=5)
    assert result is False
    assert not p.exists()  # removed by is_attached

def test_remove_sentinel_is_idempotent(tmp_path: Path) -> None:
    p = sentinel_path(tmp_path, 5)
    remove_sentinel(p)  # absent — must not raise
    write_sentinel(p)
    remove_sentinel(p)
    assert not p.exists()
```

Run: `pytest tests/app/test_control_state.py -v` → 5 PASS.

---

## Sub-phase 1.5 — Audit logging

**Commit:** `feat(tiller): audit logging for armed WS writes`

The audit line is already emitted by `_audit()` in `agent_terminal.py` (sub-phase 1.3). This
sub-phase adds an **optional file sink** and a test that the audit logger fires.

**Files touched:**

- Modify: `src/kanbanmate/http/agent_terminal.py` — extend `_audit` to optionally append to
  `<store_root>/control/audit.log`.
- Modify: `tests/http/test_agent_terminal.py` — add `test_audit_logged_on_armed_send`.

**Extend `_audit` in `agent_terminal.py`:**

```python
def _audit(login: str, issue: int, payload_summary: str) -> None:
    """Log a structured audit line; optionally append to control/audit.log.

    Args:
        login: The authenticated operator login.
        issue: The ticket issue number.
        payload_summary: A short summary of what was sent.
    """
    line = f"audit: operator {login}→ticket-{issue}: {payload_summary}"
    logger.info(line)
    # Optional file sink: append to <kanban_root>/control/audit.log when accessible.
    try:
        from kanbanmate.http.config_api import _kanban_root  # noqa: PLC0415
        log_path = _kanban_root() / "control" / "audit.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            import datetime  # noqa: PLC0415
            f.write(f"{datetime.datetime.utcnow().isoformat()} {line}\n")
    except Exception:
        pass  # fail-soft: audit file errors must never interrupt a send
```

**Add to `tests/http/test_agent_terminal.py`:**

```python
def test_audit_logged_on_armed_send(tmp_path, caplog) -> None:
    """An armed text send emits an audit log line."""
    import logging
    fake = _setup(tmp_path)
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
```

Run: `pytest tests/http/test_agent_terminal.py -v` → 5 PASS.

---

## Definition of Done

- [ ] `pytest tests/adapters/workspace/test_sessions_resize.py tests/adapters/workspace/test_sessions_capture_ansi.py tests/http/test_agent_terminal.py tests/app/test_control_state.py -v` — all PASS.
- [ ] `make check` → zero lint/mypy errors, all tests green, module-size guards pass.
- [ ] `python -c "from kanbanmate.http import agent_terminal"` → no import error.
- [ ] The WS endpoint is registered: `grep -r "agent_terminal" src/kanbanmate/http/monitor_routes.py` → import line present.

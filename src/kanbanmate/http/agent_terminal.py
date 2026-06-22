"""WebSocket endpoint for the interactive agent terminal (tiller §4.2).

A REAL terminal, not a screen-scraper. The endpoint allocates a pseudo-terminal
(``os.openpty``), spawns ``tmux attach-session`` attached to that PTY, and streams
the master fd **bidirectionally** over the WebSocket — exactly how ttyd / wetty /
pyxtermjs expose a shell in the browser:

* PTY output bytes  → WebSocket **binary** frames → ``xterm.write`` (raw ANSI, real
  time — no polling, so animations/spinners and key echo are fluid).
* WebSocket **text** frames (JSON) → control / input / resize.
* Browser resize → ``ioctl(TIOCSWINSZ)`` on the master → the tmux client follows,
  so the agent's pane reflows to fit the browser (fullscreen genuinely enlarges it).

Read-only by default: input bytes reach the PTY only after ``take_control``; every
armed send is audit-logged and guarded by the reaper sentinel. The child command is
overridable via ``app.state.terminal_pty_cmd`` (a ``Callable[[int], list[str]]``) so
the streaming path is testable without tmux.

Registered on the shared config-API ``app`` via side-effect import from
``http/monitor_routes.py``. The ``@app.middleware("http")`` auth guard does NOT run
for WebSocket scopes; auth is checked in-handler (cookie → verify_token).

Layering: ``http`` top entrypoint — may import ``app``, ``core``, ``adapters``.
"""

from __future__ import annotations

import asyncio
import contextlib
import fcntl
import json
import logging
import os
import select
import signal
import struct
import subprocess
import termios
from typing import Any, Callable

from fastapi import WebSocket, WebSocketDisconnect

from kanbanmate.http.auth import COOKIE_NAME, verify_token
from kanbanmate.http.config_api import _auth_config, _kanban_root, app
from kanbanmate.http.monitor_routes import _monitor_sessions

logger = logging.getLogger("kanbanmate.http.agent_terminal")

_MAX_MSG_BYTES = 1 * 1024 * 1024  # 1 MiB cap per client message
_READ_CHUNK = 64 * 1024  # bytes read from the PTY master per readable event
# Bound the outbound buffer: a chatty agent + a stalled client must NOT grow the queue without
# limit (OOM). At ~64 KiB/chunk this caps the viewer buffer at ~32 MiB; beyond it, terminal output
# chunks are dropped (the live stream catches up) — control frames are never dropped.
_OUT_QUEUE_MAX = 512
_WRITE_MAX_RETRIES = 20  # bounded retries when the PTY input buffer is momentarily full
# Resize bounds — a 0 / absurd size from a mid-layout client would break the tmux client.
_MIN_COLS, _MAX_COLS = 20, 500
_MIN_ROWS, _MAX_ROWS = 5, 200


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    """Set the PTY window size (``TIOCSWINSZ``) so the attached client gets SIGWINCH."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def _write_input(fd: int, data: bytes) -> None:
    """Write ALL of *data* to the non-blocking PTY master, tolerating partial / would-block writes.

    A single ``os.write`` on a non-blocking fd may write fewer bytes than asked (dropping the tail —
    losing operator keystrokes) or raise ``BlockingIOError`` when the PTY input buffer is full. Loop
    until drained, waiting briefly for writability on a full buffer. Bounded so a stuck (non-reading)
    agent can't block the event loop forever; genuine ``OSError`` (slave gone) propagates to the
    caller as end-of-session.

    Raises:
        OSError: When the retry budget is exhausted with bytes still undelivered (a persistently
            full PTY buffer). Surfaces the dropped keystrokes to the caller as an end-of-session
            error frame rather than silently truncating the operator's input.
    """
    view = memoryview(data)
    for _ in range(_WRITE_MAX_RETRIES):
        if not view:
            return
        try:
            view = view[os.write(fd, view) :]
        except BlockingIOError:
            select.select([], [fd], [], 0.25)  # rare: wait for the PTY to drain (tiny keystrokes)
        except InterruptedError:
            continue  # signal — retry
    # Budget exhausted with bytes still pending: do NOT silently drop the remaining keystrokes. Raise
    # so the receive loop's OSError handler emits an {"error": ...} frame and ends the session — the
    # operator sees their input was not delivered instead of it vanishing.
    if view:
        raise OSError(
            f"PTY input buffer stayed full after {_WRITE_MAX_RETRIES} retries; "
            f"{len(view)} byte(s) of operator input undelivered"
        )


def _pty_command(issue: int) -> list[str]:
    """The child command to run in the PTY (overridable via ``app.state.terminal_pty_cmd``)."""
    factory: Callable[[int], list[str]] | None = getattr(app.state, "terminal_pty_cmd", None)
    if factory is not None:
        return list(factory(issue))
    # A real, interactive tmux client attached to the agent's session. The client's PTY winsize
    # drives the session size (window-size defaults to "latest" — the most recent client wins).
    #
    # `set status off` (chained after the attach): drop tmux's status bar so the pane height equals
    # the client (xterm) height. Otherwise the status row steals the bottom line and Claude Code's
    # Ink TUI — which assumes the full window — paints its footer/menus *under* the bar (invisible
    # bottom rows; Claude issue #51497). A single-pane agent session has no use for a status bar, and
    # removing it also makes xterm's geometry match Claude's exactly, reducing the Ink redraw drift
    # (#29937) that garbles interactive menus (/model, /plugin, …).
    name = f"ticket-{issue}"
    return [
        "tmux",
        "attach-session",
        "-t",
        name,
        ";",
        "set-option",
        "-t",
        name,
        "status",
        "off",
    ]


@app.websocket("/api/monitor/agent/{issue}/attach")
async def agent_attach(websocket: WebSocket, issue: int) -> None:
    """Bidirectional PTY-streamed terminal for agent session ``ticket-<issue>``.

    Auth: in-handler cookie check (middleware does not cover WS scope). Read-only by
    default; the client sends ``{type:"take_control"}`` to arm input. Every armed send
    is audit-logged. The reaper sentinel is written on take_control, removed on
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
    store_root = _kanban_root()
    session_name = f"ticket-{issue}"  # the agent's tmux session (for kill_repl_process)
    armed = False

    # Resolve the reaper sentinel path lazily (best-effort).
    try:
        from kanbanmate.app.control_state import (  # noqa: PLC0415
            remove_sentinel,
            sentinel_path,
            write_sentinel,
        )

        _sentinel = sentinel_path(store_root, issue)
    except Exception:
        _sentinel = None

    # --- Spawn the PTY child (tmux attach by default; injectable for tests) ---
    try:
        master_fd, slave_fd = os.openpty()
        _set_winsize(master_fd, 24, 80)  # sane default until the client's first resize
        env = dict(os.environ)
        env["TERM"] = "xterm-256color"
        # ``login_tty`` (setsid + TIOCSCTTY + dup to 0/1/2) gives the child a CONTROLLING terminal —
        # without it the tmux client never receives SIGWINCH and resize silently no-ops (merely
        # inheriting the slave fd is NOT enough). It also makes the child a session leader, so
        # ``killpg`` on detach cleanly tears down just this client. ``pass_fds`` keeps the slave open
        # until ``login_tty`` consumes it.
        proc = subprocess.Popen(  # noqa: S603 — argv list, no shell
            _pty_command(issue),
            preexec_fn=lambda: os.login_tty(slave_fd),  # noqa: PLW1509 — PTY controlling-tty setup
            close_fds=True,
            pass_fds=(slave_fd,),
            env=env,
        )
        os.close(slave_fd)
        os.set_blocking(master_fd, False)
    except Exception as exc:
        logger.error("agent terminal: failed to start PTY for ticket-%s", issue, exc_info=True)
        with contextlib.suppress(Exception):
            await websocket.send_text(json.dumps({"error": f"could not start terminal: {exc}"}))
        await websocket.close()
        return

    loop = asyncio.get_running_loop()
    out_queue: asyncio.Queue[Any] = asyncio.Queue()

    def _on_pty_readable() -> None:
        """Drain the PTY master and queue the bytes (EOF → sentinel ``None``)."""
        try:
            data = os.read(master_fd, _READ_CHUNK)
        except (BlockingIOError, InterruptedError):
            return
        except OSError:
            data = b""  # fd error == EOF
        if not data:
            loop.remove_reader(master_fd)
            out_queue.put_nowait(None)
            return
        # Backpressure: under extreme output flood with a stalled client, drop terminal bytes rather
        # than grow the queue without bound (the live stream re-syncs). Control frames are unaffected.
        if out_queue.qsize() < _OUT_QUEUE_MAX:
            out_queue.put_nowait(data)

    loop.add_reader(master_fd, _on_pty_readable)

    async def _sender() -> None:
        """Single send path: bytes → binary frame (terminal), dict → text frame (control)."""
        while True:
            item = await out_queue.get()
            if item is None:  # PTY EOF — the session ended.
                with contextlib.suppress(Exception):
                    await websocket.close()
                return
            try:
                if isinstance(item, bytes):
                    await websocket.send_bytes(item)
                else:
                    await websocket.send_text(json.dumps(item))
            except Exception:
                return

    send_task = asyncio.create_task(_sender())

    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode()) > _MAX_MSG_BYTES:
                out_queue.put_nowait({"error": "message too large"})
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue  # ignore malformed frames
            kind = msg.get("type", "")
            if kind == "take_control":
                armed = True
                if _sentinel is not None:
                    with contextlib.suppress(Exception):
                        write_sentinel(_sentinel)
                out_queue.put_nowait({"control": "armed"})
            elif kind == "release_control":
                armed = False
                if _sentinel is not None:
                    with contextlib.suppress(Exception):
                        remove_sentinel(_sentinel)
                out_queue.put_nowait({"control": "released"})
            elif kind == "input":
                if not armed:
                    out_queue.put_nowait({"error": "not in control"})
                    continue
                data = msg.get("data", "")
                _audit(login, issue, f"input len={len(data)}")
                try:
                    _write_input(master_fd, data.encode("utf-8", "ignore"))
                except OSError as exc:
                    # Genuine PTY error (slave gone) — the session has ended.
                    out_queue.put_nowait({"error": str(exc)})
                    break
            elif kind == "resize":
                # A malformed (non-numeric) cols/rows must not crash the loop and kill the terminal.
                try:
                    cols = max(_MIN_COLS, min(_MAX_COLS, int(msg.get("cols", 80))))
                    rows = max(_MIN_ROWS, min(_MAX_ROWS, int(msg.get("rows", 24))))
                except (TypeError, ValueError):
                    continue
                with contextlib.suppress(Exception):
                    _set_winsize(master_fd, rows, cols)
            elif kind == "kill":
                # End the agent: SIGKILL the claude REPL but let the surviving shell run the
                # ``; kanban-session-end <issue>`` wrapper → clean teardown / state purge (NOT
                # tmux kill-session, which would skip that cleanup). Requires control + audited.
                if not armed:
                    out_queue.put_nowait({"error": "not in control"})
                    continue
                _audit(login, issue, "kill (end claude session)")
                with contextlib.suppress(Exception):
                    _monitor_sessions().kill_repl_process(session_name)
                # The shell then exits → the tmux session ends → the PTY hits EOF → the WS closes.
            # Unknown types silently ignored (forward-compat).
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        # Teardown path (e.g. a close-state error from the concurrent EOF close) — never propagate.
        logger.debug("agent terminal: receive loop ended unexpectedly", exc_info=True)
    finally:
        with contextlib.suppress(Exception):
            loop.remove_reader(master_fd)
        send_task.cancel()
        # Detach the tmux client (SIGTERM to the child's group) — the AGENT session keeps running.
        with contextlib.suppress(Exception):
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        with contextlib.suppress(Exception):
            await loop.run_in_executor(None, proc.wait)
        with contextlib.suppress(Exception):
            os.close(master_fd)
        if _sentinel is not None:
            with contextlib.suppress(Exception):
                remove_sentinel(_sentinel)


def _audit(login: str, issue: int, payload_summary: str) -> None:
    """Log a structured audit line for an armed operator write (D2).

    Emits to the Python logger, and optionally appends to
    ``<kanban_root>/control/audit.log`` (fail-soft: file errors never interrupt a send).

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

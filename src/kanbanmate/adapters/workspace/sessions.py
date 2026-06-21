"""Tmux-session adapter implementing the :class:`~kanbanmate.ports.workspace.Sessions` Protocol.

Ported from the PoC ``engine/tmux.py``. All tmux invocations use argv lists
(no ``shell=True``) — session names and commands are separate argv elements,
preventing shell injection.

Layering: adapters MAY import ``kanbanmate.ports.*`` and ``kanbanmate.core.*``;
MUST NOT import ``app``, ``daemon``, or ``cli``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Callable
from typing import Any

Runner = Callable[..., "subprocess.CompletedProcess[Any]"]
Sleeper = Callable[[float], None]

# Bounded poll for the freshly-created session's shell to RENDER its prompt before the launch command
# is typed (first-keystroke race). ``tmux new-session -d`` returns before the interactive shell
# (zsh/oh-my-zsh) has printed its prompt and is ready to read; send-keys fired into that window drops
# the leading character(s) — the live ``export PATH=…`` → ``xport`` → ``command not found`` case. A
# non-empty pane means the shell printed SOMETHING (its prompt), i.e. it is ready for input. Bounded
# so a silent shell still proceeds (best-effort, same as the pre-fix immediate send).
_SHELL_READY_ATTEMPTS = 30
_SHELL_READY_INTERVAL = 0.1  # seconds between capture probes (overridable for offline tests)

# Large LITERAL sends (the filled ``/implement:*`` prompt embeds the ticket body — up to ~12KB) are
# CHUNKED so a single huge ``send-keys`` write cannot overflow the pane PTY. The helm #5 launch
# failure: an ~11KB one-shot ``send-keys -l`` raised ``CalledProcessError`` (exit 1) under daemon load
# (a transient write failure — the monitor already watches for "No buffer space"), which ABORTED the
# launch and orphaned claude with no prompt + no persisted state. Chunking keeps each write small, and
# each chunk is RETRIED on a transient failure so a momentary glitch never aborts a launch. Small sends
# (the command line, key names) fit in ONE chunk — byte-identical to the pre-fix single send-keys.
_SEND_CHUNK_SIZE = 1024  # max chars per literal send-keys write (well under any PTY burst limit)
_SEND_CHUNK_RETRIES = 3  # per-chunk attempts on a transient send-keys CalledProcessError
_SEND_CHUNK_RETRY_DELAY = 0.2  # backoff between chunk retries (routed through the injected sleeper)

# Delays between the end_session keystrokes so claude v2.1.x processes each step (menu close → box
# clear → EOF → confirm-EOF → menu-render). Kept SMALL — end_session runs rarely (once per finished
# session) and is dispatched from the reaper sweep, so the total must stay well under ~2s. Worst case
# here is 0.3 + 0.3 + 0.5 + 0.5 = 1.6s (under budget). Routed through the existing ``sleeper`` seam so
# offline tests inject a fake and pay zero real wall time.
_END_MENU_DELAY = 0.3  # after Escape (let the slash-command autocomplete/menu close)
_END_CLEAR_DELAY = 0.3  # after C-u (let the input line clear before EOF)
_END_CONFIRM_DELAY = 0.5  # between the two C-d (let the background-shell exit MENU surface)
_END_MENU_CONFIRM_DELAY = (
    0.5  # after the second C-d (let the "Exit anyway?" menu render before Enter confirms it)
)


class TmuxSessions:
    """Detached tmux session lifecycle for launched agents.

    One session per ticket hosts the resumable ``claude`` process. The session
    name is the dispatcher's correlation key (e.g. ``ticket-<n>``).

    ``launch`` creates a detached session, types the command literally into it,
    and presses Enter — the agent begins executing immediately. ``capture``
    snapshots the active pane (so the launch flow can poll for the trust dialog
    / a ready REPL), ``send_text`` types into the live REPL (the filled prompt +
    Enter), ``is_alive`` probes existence, and ``kill`` tears the session down.
    """

    def __init__(self, *, runner: Runner = subprocess.run, sleeper: Sleeper = time.sleep) -> None:
        """Initialise the tmux sessions adapter.

        Args:
            runner: Subprocess runner (injected for tests). Defaults to
                :func:`subprocess.run`.
            sleeper: Sleep primitive between the launch shell-readiness probes (injected so
                offline tests drive the poll without real waiting). Defaults to :func:`time.sleep`.
        """
        self._runner = runner
        self._sleeper = sleeper

    # ------------------------------------------------------------------
    # Sessions Protocol methods
    # ------------------------------------------------------------------

    def launch(self, name: str, cwd: str, command: str) -> str:
        """Create a detached tmux session *name* rooted at *cwd* running *command*.

        The session is created detached (``-d``) so the caller does not block.
        *command* is sent with ``send-keys -l`` (literal) so slash-commands and
        special characters are typed verbatim, followed by ``Enter`` to execute.

        Args:
            name: The session name (the dispatcher's correlation key).
            cwd: The working directory to root the session in (the worktree).
            command: The shell command line to run inside the session
                (typically the ``claude`` invocation).

        Returns:
            The session identifier (the *name* that was created), used by
            later :meth:`is_alive` / :meth:`kill` calls.
        """
        # IDEMPOTENT LAUNCH (phase-27 §A): a leftover/stale session of the SAME name (e.g. an old
        # churning agent the reaper relaunched) would make ``tmux new-session -s <name>`` exit 1 and
        # abort the launch (the live #91 e2e bug). Kill any pre-existing session FIRST, tolerating
        # "no such session" so the first-launch case (no prior session) is a clean no-op — restoring
        # the PoC tmux wrapper's re-launch tolerance.
        self._kill_if_present(name)
        self._runner(
            ["tmux", "new-session", "-d", "-s", name, "-c", cwd],
            check=True,
        )
        # Wait for the new session's shell to RENDER its prompt before typing (first-keystroke race):
        # ``new-session -d`` returns before zsh/oh-my-zsh is ready to read, so an immediate send-keys
        # drops the leading char(s) — the live ``export PATH=…`` → ``xport`` failure. Poll until the
        # pane is non-empty (the shell printed its prompt), then send.
        self._wait_for_shell_ready(name)
        # Type the command literally, then press Enter — routed through the same
        # ``send_text`` primitive the app's prompt-delivery uses, so there is one
        # send-keys seam (argv-list, no shell).
        self.send_text(name, command, literal=True, enter=True)
        return name

    def _wait_for_shell_ready(self, name: str) -> None:
        """Poll ``capture-pane`` until session *name*'s shell has rendered its prompt (best-effort).

        Bounded by :data:`_SHELL_READY_ATTEMPTS` × :data:`_SHELL_READY_INTERVAL`. A non-empty pane
        means the interactive shell printed SOMETHING (its prompt) and is ready to read, so the
        launch command's leading character is no longer dropped (the ``export`` → ``xport`` race).
        Fail-soft: a capture error is treated as "not ready yet" and, on timeout, the caller sends
        anyway (same best-effort behaviour as before the fix — never block a launch on a quiet shell).

        Args:
            name: The freshly-created session name to probe.
        """
        for i in range(_SHELL_READY_ATTEMPTS):
            try:
                pane = self.capture(name)
            except Exception:
                pane = ""
            if pane.strip():
                return
            # Don't sleep after the final probe (no point waiting just to time out).
            if i < _SHELL_READY_ATTEMPTS - 1:
                self._sleeper(_SHELL_READY_INTERVAL)
        # TIMEOUT: the shell never printed a prompt within the budget — proceed with the send anyway
        # (best-effort; the worst case is the pre-fix immediate-send behaviour).

    def capture(self, name: str) -> str:
        """Return the printable contents of session *name*'s active pane.

        Ported from the PoC ``engine/tmux.py`` ``capture``. The launch flow polls
        this snapshot to detect the trust dialog (``you trust``) or a ready REPL
        before typing the prompt — without it the prompt would be typed before
        ``claude`` is ready to accept input and never submit.

        Args:
            name: The session name whose active pane to snapshot.

        Returns:
            The joined (``-J``), printable (``-p``) pane text. Empty string when
            the runner returns no stdout.
        """
        res = self._runner(
            ["tmux", "capture-pane", "-p", "-J", "-t", name],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout or ""

    def capture_ansi(self, name: str, *, scrollback: int = 0) -> str:
        """ANSI-preserving capture (``-e``) for the interactive terminal stream (tiller §4.2).

        Args:
            name: The session name whose active pane to snapshot.
            scrollback: When > 0, also capture this many lines of pane HISTORY above the
                visible screen (``-S -<n>``) so the operator can scroll back through output
                that has already scrolled off. ``0`` (default) captures only the visible pane.

        Returns:
            The joined, ANSI-preserved pane text (empty string when runner returns no stdout).
        """
        argv = ["tmux", "capture-pane", "-p", "-J", "-e"]
        if scrollback > 0:
            # ``-S -<n>`` starts the capture n lines into the scrollback history.
            argv += ["-S", f"-{scrollback}"]
        argv += ["-t", name]
        res = self._runner(argv, capture_output=True, text=True, check=True)
        return res.stdout or ""

    def pane_size(self, name: str) -> tuple[int, int]:
        """Return session *name*'s active pane size as ``(cols, rows)``.

        The interactive terminal sizes the browser xterm to the pane's REAL geometry so the
        full width is shown (scaled / scrolled to fit the viewport) instead of reflowing the
        running agent's pane down to the viewer's size — which would disrupt the live agent.

        Args:
            name: The session name to measure.

        Returns:
            ``(cols, rows)``; falls back to ``(80, 24)`` on any runner/parse error.
        """
        try:
            res = self._runner(
                ["tmux", "display-message", "-p", "-t", name, "#{pane_width} #{pane_height}"],
                capture_output=True,
                text=True,
                check=True,
            )
            parts = (res.stdout or "").split()
            return (int(parts[0]), int(parts[1]))
        except Exception:  # noqa: BLE001 — best-effort geometry; the viewer defaults to 80x24
            return (80, 24)

    def send_text(self, name: str, text: str, *, literal: bool = True, enter: bool = False) -> None:
        """Send *text* to session *name*, optionally followed by Enter.

        The single send-keys seam (the ``launch`` command line, the trust-dialog
        dismiss Enter, and the filled prompt all route through here). Ported from
        the PoC ``engine/tmux.py`` ``send_keys`` — argv-list only, never
        ``shell=True``.

        Args:
            name: The session name to type into.
            text: The text (``literal=True``) or tmux key name (``literal=False``,
                e.g. ``"Enter"``) to send. Ignored as a separate event only when a
                caller passes the empty string with ``enter=True`` (Enter only) —
                but the normal contract is a non-empty payload.
            literal: When ``True`` (default), send raw text (``-l --``) so
                slash-commands and spaces are typed verbatim; when ``False``,
                *text* is a tmux key name.
            enter: When ``True``, send a trailing ``Enter`` key as a SEPARATE
                event after *text* (so a literal prompt is submitted).
        """
        if literal:
            # CHUNKED + retried (a huge one-shot send-keys can fail under load → aborted launch +
            # orphaned claude; see ``_send_literal`` / the chunk-constant note).
            self._send_literal(name, text)
        else:
            self._runner(["tmux", "send-keys", "-t", name, text], check=True)
        if enter:
            # Enter is a SEPARATE send-keys event (a key NAME, not literal text), so a
            # literal prompt is typed first then submitted — mirroring the PoC's two-call
            # ``send_keys(..., literal=True)`` then ``send_keys("Enter", literal=False)``.
            self._runner(
                ["tmux", "send-keys", "-t", name, "Enter"],
                check=True,
            )

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

    def is_alive(self, name: str) -> bool:
        """Return whether the tmux session *name* currently exists.

        Args:
            name: The session name to probe.

        Returns:
            ``True`` iff the session exists.
        """
        res = self._runner(
            ["tmux", "has-session", "-t", name],
            capture_output=True,
            text=True,
        )
        return res.returncode == 0

    def kill(self, name: str) -> None:
        """Kill the tmux session *name*.

        Args:
            name: The session name to kill. Killing an absent session raises
                :class:`subprocess.CalledProcessError` — the caller (teardown
                path) must tolerate that.
        """
        self._runner(
            ["tmux", "kill-session", "-t", name],
            check=True,
        )

    def _send_literal(self, name: str, text: str) -> None:
        """Send literal *text* to session *name* in bounded, individually-retried chunks (#helm5).

        A single ``tmux send-keys -l`` write of a very large prompt (the filled ``/implement:*``
        prompt embeds the ticket body — up to ~12KB) can fail with ``CalledProcessError`` (exit 1)
        under daemon load — a transient write failure that, left unhandled, ABORTED the launch and
        orphaned claude with no prompt + no persisted state (helm #5). This splits the payload into
        ``_SEND_CHUNK_SIZE``-char chunks (so each write stays well under any PTY burst limit) and
        RETRIES each chunk up to ``_SEND_CHUNK_RETRIES`` times on a transient failure, backing off via
        the injected ``sleeper``. A payload that fits in one chunk (the command line, key names) sends
        with a SINGLE ``send-keys`` — byte-identical to the pre-fix behaviour. An empty payload sends
        nothing (the trailing Enter, if any, is the caller's separate event).

        Args:
            name: The session name to type into.
            text: The literal text to send (may be large; may be empty).

        Raises:
            subprocess.CalledProcessError: If a chunk still fails after ``_SEND_CHUNK_RETRIES``
                attempts (a genuine, non-transient send failure — the caller decides how to handle).
        """
        for start in range(0, len(text), _SEND_CHUNK_SIZE):
            chunk = text[start : start + _SEND_CHUNK_SIZE]
            argv = ["tmux", "send-keys", "-t", name, "-l", "--", chunk]
            for attempt in range(_SEND_CHUNK_RETRIES):
                try:
                    self._runner(argv, check=True)
                    break
                except Exception:
                    # Last attempt failed → propagate (a genuine failure, not a transient glitch).
                    if attempt == _SEND_CHUNK_RETRIES - 1:
                        raise
                    # Transient (e.g. a momentary "No buffer space") → back off and re-send the chunk.
                    self._sleeper(_SEND_CHUNK_RETRY_DELAY)

    def _send_key(self, name: str, key: str) -> None:
        """Send one tmux KEY NAME (no ``-l``) to session *name*, ``check=True``.

        The single argv seam for the :meth:`end_session` keystroke sequence. Key NAMES (``Escape``,
        ``C-u``, ``C-d``, ``BSpace``) are sent WITHOUT ``-l`` — exactly like the ``Enter`` event in
        :meth:`send_text` — so tmux interprets them as keys rather than literal text.

        Args:
            name: The session name to send the key to.
            key: The tmux key name (e.g. ``"Escape"``, ``"C-d"``).
        """
        self._runner(["tmux", "send-keys", "-t", name, key], check=True)

    def _clear_input_line(self, name: str) -> None:
        """Clear session *name*'s claude input line so the EOF lands on an EMPTY idle prompt.

        Ships ``C-u`` (kill-line) — it clears the whole input line in one key, harmless on an
        already-empty box.

        Args:
            name: The session name whose input line to clear.
        """
        self._send_key(name, "C-u")

    def end_session(self, name: str) -> None:
        """Cleanly EXIT the ``claude`` REPL in session *name* without killing the session (#1).

        Robust exit sequence (firm-exit) for claude v2.1.x — sends, in order, with small delays so
        claude processes each step:

        1. ``Escape`` — close any open slash-command autocomplete / menu (the helm #5 condition: a
           leftover ``/implement:plan`` in the input box kept C-c/C-d from landing on an idle prompt).
        2. ``C-u`` (via :meth:`_clear_input_line`) — clear the input line so the EOF lands on an
           EMPTY idle prompt.
        3. ``C-d`` — EOF → ``claude`` exits at the idle prompt. With background shells running, this
           FIRST ``C-d`` instead surfaces claude v2.1.x's "Background work is running — Exit anyway?"
           MENU (``❯ 1. Exit anyway`` / ``2. Stay``, "Enter to confirm").
        4. ``C-d`` — a SECOND EOF (harmless if claude already exited; a no-op against the menu).
        5. ``Enter`` — CONFIRM the highlighted "Exit anyway" option of the background-shell exit MENU.
           This step is load-bearing: the menu is confirmed with ENTER, NOT a second ``C-d`` — without
           it a FINISHED agent that left background shells stays stuck at the dialog forever, never
           drops past the graceful budget, and the reaper SIGKILLs it (clearing the done breadcrumb →
           ⚠️ + NO auto-advance, stranding the card). Reproduced live on #5's plan stage. Harmless when
           there is no menu: Enter on an empty idle prompt / the surviving shell is a no-op newline.

        Every event is a tmux KEY NAME (sent WITHOUT ``-l``, like the ``Enter`` event in
        :meth:`send_text`), NOT literal text, and each ``send-keys`` stays ``check=True``. Delays go
        through the injected ``sleeper`` seam (offline tests pay zero wall time); worst case is
        :data:`_END_MENU_DELAY` + :data:`_END_CLEAR_DELAY` + :data:`_END_CONFIRM_DELAY` +
        :data:`_END_MENU_CONFIRM_DELAY` = 1.6s.

        INVARIANT — this NEVER runs ``tmux kill-session``: when ``claude`` exits the surviving shell
        runs the trailing ``; kanban-session-end <issue>`` of the launched command, so the teardown
        fires. ``kill-session`` would tear the shell down and that wrapper would never run.

        Args:
            name: The session name whose REPL to exit (``ticket-<n>``).
        """
        # 1. Close any open slash-command autocomplete / menu so the box is editable.
        self._send_key(name, "Escape")
        self._sleeper(_END_MENU_DELAY)
        # 2. Clear the input line so the EOF lands on an EMPTY idle prompt (not a leftover command).
        self._clear_input_line(name)
        self._sleeper(_END_CLEAR_DELAY)
        # 3. First C-d (EOF): exits at an empty prompt, OR (background shells) surfaces claude
        #    v2.1.x's "Background work is running — Exit anyway?" MENU.
        self._send_key(name, "C-d")
        self._sleeper(_END_CONFIRM_DELAY)
        # 4. Second C-d: a harmless second EOF (a no-op against the menu; covers any non-menu confirm).
        self._send_key(name, "C-d")
        self._sleeper(_END_MENU_CONFIRM_DELAY)
        # 5. Enter: CONFIRM the highlighted "Exit anyway" of the background-shell exit MENU (the menu is
        #    confirmed with Enter, NOT a second C-d). claude exits and the surviving shell then runs the
        #    trailing ``; kanban-session-end <issue>`` wrapper (never kill-session here). Harmless no-op
        #    when there is no menu (empty idle prompt / surviving shell).
        self._send_key(name, "Enter")

    def kill_repl_process(self, name: str) -> None:
        """SIGKILL the ``claude`` REPL child of session *name*'s pane — NOT the session/shell (#).

        Escalation primitive for a graceful exit (:meth:`end_session`) that failed repeatedly (a
        genuinely-hung REPL or stubborn leftover state that swallows the keystrokes). It resolves the
        pane's shell PID (``tmux list-panes -t <name> -F '#{pane_pid}'``), finds the shell's child
        (the ``claude`` REPL) and sends it ``SIGKILL`` so the REPL dies but the SURVIVING shell still
        runs the trailing ``; kanban-session-end <issue>`` of the launched command → teardown fires.

        WHY SIGKILL (guaranteed termination) AND NOT SIGTERM: this escalation runs ONLY after the
        graceful end_session keystrokes (Escape → C-u → C-d → C-d → Enter) have failed ``MAX_END_ATTEMPTS``
        times — graceful exit was already given every chance. A live test proved SIGTERM is
        INSUFFICIENT: a finished claude REPL with a background shell still running (the
        "N shells still running" confirm) traps/survives SIGTERM, so the finished agent never
        terminates and re-parks WAITING. SIGKILL cannot be trapped, so termination is guaranteed.
        Because ONLY the claude child is killed (never the session, never the pane shell PID), the
        pane shell still runs the trailing ``; kanban-session-end <issue>`` wrapper → teardown still
        fires on the correct root.

        INVARIANT — it MUST NOT ``kill-session`` (that kills the shell and the wrapper never runs)
        and MUST NOT kill the shell PID itself. FAIL-SOFT: any resolution/kill error is swallowed
        (the reaper logs and still clears the breadcrumb so the budget is not re-spent).

        Args:
            name: The session name whose REPL process to terminate (``ticket-<n>``).
        """
        pane_pid = self._pane_pid(name)
        if pane_pid is None:
            return  # fail-soft: pane gone / unresolved
        child = self._child_pid(pane_pid)
        if child is None:
            return  # fail-soft: no live child under the shell
        try:
            os.kill(child, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            # fail-soft: the child raced away or we cannot signal it — the reaper still clears.
            return

    def repl_alive(self, name: str) -> bool:
        """Return whether session *name*'s pane still hosts a live ``claude`` REPL child (Candidate 2).

        Reuses the SAME comm-verified resolution :meth:`kill_repl_process` relies on: resolve the
        pane shell PID, then find a child whose ``comm`` is ``claude``. This lets the reaper SKIP a
        re-dispatch of the graceful end_session keystrokes when the REPL has already exited (a daemon
        restart racing the wrapper) — there is nothing to exit, so the session-end / purge completes
        on its own. FAIL-SOFT: a gone pane or no live child returns ``False`` (conservative — an
        unprobeable pane is treated as "no live REPL").

        Args:
            name: The session name whose REPL liveness to probe (``ticket-<n>``).

        Returns:
            ``True`` iff the pane has a live, comm-verified ``claude`` child; ``False`` otherwise.
        """
        pane_pid = self._pane_pid(name)
        if pane_pid is None:
            return False  # fail-soft: pane gone / unresolved → no live REPL
        return self._child_pid(pane_pid) is not None

    def _pane_pid(self, name: str) -> int | None:
        """Resolve session *name*'s active-pane shell PID via ``tmux list-panes`` (fail-soft).

        Runs ``tmux list-panes -t <name> -F '#{pane_pid}'`` and parses the first line as the pane's
        shell PID. Returns ``None`` on any error / empty output / non-int line — never raises (a gone
        or unresolvable pane is the fail-soft escalation no-op).

        Args:
            name: The session name whose pane PID to resolve.

        Returns:
            The pane's shell PID, or ``None`` when it cannot be resolved.
        """
        try:
            res = self._runner(
                ["tmux", "list-panes", "-t", name, "-F", "#{pane_pid}"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return None
        out = (res.stdout or "").strip().splitlines()
        if not out:
            return None
        try:
            return int(out[0].strip())
        except (TypeError, ValueError):
            return None

    def _child_pid(self, pane_pid: int) -> int | None:
        """Resolve the ``claude`` REPL child of shell *pane_pid* — comm-VERIFIED (fail-soft).

        The launched command is ``… claude … ; kanban-session-end``, so under the pane shell there is
        exactly one live ``claude`` UNTIL it exits — after which the surviving shell may be running the
        trailing ``; kanban-session-end`` (teardown) as its sole child. Resolution order:

        1. ``pgrep -P <pane_pid>`` — the direct children of the shell (verified on this host: the
           pane shell is ``-zsh`` and ``claude`` is its direct child).
        2. Fallback: scan ``ps -o ppid=,pid= -A`` for rows whose ppid == ``pane_pid``.

        Then ALWAYS comm-verify (via ``ps -o comm= -p <pid>``) — even for a SINGLE child: return only
        a child whose command name looks like ``claude``. If the SOLE child is NOT claude (claude has
        already exited and ``; kanban-session-end`` or another command is now the shell's child), or
        no child matches, return ``None`` so :meth:`kill_repl_process` SKIPS the kill — SIGKILLing a
        non-claude process would kill the teardown mid-flight. Claude already gone → the session will
        reap normally; we never SIGKILL the wrong process.

        Args:
            pane_pid: The pane's shell PID whose child to resolve.

        Returns:
            The ``claude`` REPL child PID, or ``None`` when no live ``claude`` child can be resolved.
        """
        children = self._children_via_pgrep(pane_pid)
        if not children:
            children = self._children_via_ps(pane_pid)
        if not children:
            return None
        # ALWAYS comm-verify (single- AND multi-child): only ever return a child that looks like the
        # claude REPL, so a surviving ``; kanban-session-end`` (teardown) child is never SIGKILLed.
        for pid in children:
            if "claude" in self._comm_of(pid):
                return pid
        # No child is claude → claude already exited; skip the kill (let the session reap normally).
        return None

    def _children_via_pgrep(self, pane_pid: int) -> list[int]:
        """Return the direct child PIDs of *pane_pid* via ``pgrep -P`` (empty list, never raises)."""
        try:
            res = self._runner(
                ["pgrep", "-P", str(pane_pid)],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return []
        return self._parse_pids(res.stdout or "")

    def _children_via_ps(self, pane_pid: int) -> list[int]:
        """Return *pane_pid*'s children by scanning ``ps -o ppid=,pid= -A`` (empty list, no raise).

        The fallback when ``pgrep`` is unavailable / yields nothing. Reuses the same ``ps`` family of
        probes the workspace adapter already shells out to. Each row is ``<ppid> <pid>``; rows whose
        ppid equals *pane_pid* contribute their pid.
        """
        try:
            res = self._runner(
                ["ps", "-o", "ppid=,pid=", "-A"],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return []
        children: list[int] = []
        for line in (res.stdout or "").splitlines():
            parts = line.split()
            if len(parts) != 2:
                continue
            try:
                ppid, pid = int(parts[0]), int(parts[1])
            except (TypeError, ValueError):
                continue
            if ppid == pane_pid:
                children.append(pid)
        return children

    def _comm_of(self, pid: int) -> str:
        """Return *pid*'s command name via ``ps -o comm=`` (empty string on any error, no raise)."""
        try:
            res = self._runner(
                ["ps", "-o", "comm=", "-p", str(pid)],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception:
            return ""
        return (res.stdout or "").strip()

    @staticmethod
    def _parse_pids(text: str) -> list[int]:
        """Parse whitespace/newline-separated PID lines into ``int``s (skips non-int lines)."""
        pids: list[int] = []
        for line in text.split():
            try:
                pids.append(int(line.strip()))
            except (TypeError, ValueError):
                continue
        return pids

    def _kill_if_present(self, name: str) -> None:
        """Kill session *name* if it exists, TOLERATING "no such session" (idempotent pre-launch).

        The pre-launch kill seam for the idempotent :meth:`launch` (phase-27 §A). Unlike the public
        :meth:`kill` (``check=True`` — the teardown path WANTS to know a kill failed), this runs
        ``kill-session`` with ``check=False`` so the common first-launch case (NO prior session, tmux
        exits non-zero with "can't find session") is a clean no-op rather than an error. Stays on the
        argv-list runner — no ``shell=True``.

        Args:
            name: The session name to kill if present.
        """
        # check=False: tmux exits non-zero when the session is absent ("can't find session"); that is
        # the expected first-launch case and must NOT raise. A real kill (session existed) succeeds.
        self._runner(
            ["tmux", "kill-session", "-t", name],
            check=False,
        )

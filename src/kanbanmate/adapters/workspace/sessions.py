"""Tmux-session adapter implementing the :class:`~kanbanmate.ports.workspace.Sessions` Protocol.

Ported from the PoC ``engine/tmux.py``. All tmux invocations use argv lists
(no ``shell=True``) — session names and commands are separate argv elements,
preventing shell injection.

Layering: adapters MAY import ``kanbanmate.ports.*`` and ``kanbanmate.core.*``;
MUST NOT import ``app``, ``daemon``, or ``cli``.
"""

from __future__ import annotations

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
            argv = ["tmux", "send-keys", "-t", name, "-l", "--", text]
        else:
            argv = ["tmux", "send-keys", "-t", name, text]
        self._runner(argv, check=True)
        if enter:
            # Enter is a SEPARATE send-keys event (a key NAME, not literal text), so a
            # literal prompt is typed first then submitted — mirroring the PoC's two-call
            # ``send_keys(..., literal=True)`` then ``send_keys("Enter", literal=False)``.
            self._runner(
                ["tmux", "send-keys", "-t", name, "Enter"],
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

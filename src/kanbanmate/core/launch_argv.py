"""Build the launched ``claude`` argv + the session-end-wrapped command line (DESIGN §8.3/§10).

Pure functional core — imports only :mod:`shlex`, no I/O (DESIGN §3.2). The argv shape and the
``; kanban-session-end <issue>`` wrapper are pure decisions: the bypass-ban guard rejects a
forbidden profile/mode, and the command composition shell-quotes every element so a worktree path
carrying spaces never splits at ``--add-dir <path>``. The argv is BARE: the filled prompt is
delivered into the live REPL via send-keys after launch (phase-25 §25.1), not part of this line.

Ported faithfully from the PoC at
``PersonalScraper/.claude/skills/kanban/kanbanmate/engine/launch.py``:
``build_claude_argv`` (L80-115) and ``_default_claude_runner``'s command composition (L137-140).
The PoC TYPED the command into the pane via ``send_keys``; NEW instead passes the composed command
STRING to ``Sessions.launch(name, cwd, command)`` — so only the command COMPOSITION is ported here,
not the send-keys mechanics.
"""

from __future__ import annotations

import shlex


def build_claude_argv(
    session_uuid: str,
    worktree: str,
    permission_profile: str,
    permission_mode: str = "auto",
) -> list[str]:
    """Build the ``claude`` argv for an orchestrated agent session (DESIGN §4.6/§8.3/§10).

    The CLI ``--permission-mode`` flag is authoritative for the session and OVERRIDES the
    worktree ``.claude/settings.json`` ``defaultMode``; it is emitted directly from
    ``permission_mode`` (sourced per-transition). The default ``"auto"`` is headless-safe and
    still enforces ``permissions.deny`` (merge / force-push / history-rewrite stay denied), so a
    launched agent never hangs on a permission prompt yet can never bypass the deny layer.

    ``--session-id <uuid>`` makes the generated uuid the single source of truth for resumability:
    ``claude --resume <uuid>`` reattaches the same session (DESIGN §8.3). ``permission_profile`` is
    used ONLY for the bypass-ban guard — it is NOT emitted into the argv (the profile's concrete
    allow/deny is materialised into the worktree settings, not passed on the command line).

    Args:
        session_uuid: The generated uuid (single source of truth for ``claude --resume``).
        worktree: Absolute worktree path, added to claude's scope via ``--add-dir``.
        permission_profile: The permission profile name (one of ``docs`` / ``prepare`` / ``dev`` /
            ``check``). Any value containing ``bypass`` (case-insensitive) is rejected (banned,
            DESIGN §10). Not emitted.
        permission_mode: The ``claude --permission-mode`` value (default ``"auto"``). A value
            containing ``bypass`` is rejected — it would skip the deny layer.

    Returns:
        The argv list: ``["claude", "--session-id", uuid, "--permission-mode", mode, "--add-dir",
        worktree]``.

    Raises:
        ValueError: If ``permission_profile`` OR ``permission_mode`` requests a bypass.
    """
    # Bypass is banned everywhere (DESIGN §10: merge is human-only; the deny layer must never be
    # skipped). Guard the profile AND the mode independently so neither channel can re-enable it.
    if "bypass" in permission_profile.lower():
        raise ValueError("bypassPermissions profile is banned (DESIGN §10)")
    if "bypass" in permission_mode.lower():
        raise ValueError("bypassPermissions mode is banned (DESIGN §10)")
    return [
        "claude",
        "--session-id",
        session_uuid,
        "--permission-mode",
        permission_mode,
        "--add-dir",
        worktree,
    ]


def wrap_with_session_end(
    argv: list[str], issue: int, *, session_end_bin: str, terminate_session: bool = False
) -> str:
    """Compose the shell command line: the claude argv followed by the session-end wrapper.

    Each argv element is ``shlex.quote``-escaped before joining, so a worktree path containing
    spaces stays ONE shell argument and never splits at ``--add-dir <path>`` (P5 T10). The
    ``session_end_bin`` is likewise quoted. The argv is BARE (no positional prompt): the filled
    ``/implement:*`` prompt is delivered INTO the live REPL via send-keys after launch (phase-25
    §25.1), never composed into this command line.

    The wrapper is appended with ``;`` (NOT ``&&``): the ``;`` ensures ``kanban-session-end`` ALWAYS
    fires, whether ``claude`` exits cleanly or with a non-zero status, so the cap slot is always
    released and the ticket always marked idle on exit (PoC comment ``launch.py:132-135``). With
    ``&&`` a crashing claude would never reach the wrapper, leaking the slot until the reaper's TTL.

    The function stays pure: the session-end bin PATH is INJECTED by the app layer (resolved against
    the installed console-script or an absolute path), never discovered here.

    ``terminate_session`` (ad-hoc launches only): append ``; tmux kill-session -t ticket-<issue>`` so
    the tmux session DISAPPEARS when claude exits. ``kanban-session-end`` has already purged the
    runtime state (slot + state + breadcrumbs) by then, so there is no running state left for the
    reaper to relaunch — only the otherwise-idle login shell would linger, which the kill removes. The
    autonomous flow leaves this False so a finished agent's pane stays attachable for inspection.

    Args:
        argv: The bare ``claude`` argv (from :func:`build_claude_argv`; no positional prompt —
            the prompt is send-keys'd into the REPL after launch, phase-25 §25.1).
        issue: The ticket issue number passed to ``kanban-session-end``.
        session_end_bin: Path to (or name of) the ``kanban-session-end`` shim.
        terminate_session: When True, append a ``tmux kill-session`` for ``ticket-<issue>`` so the
            session is removed on claude exit (ad-hoc operator launch). Default False.

    Returns:
        The composed command line ``<quoted argv> ; <quoted session_end_bin> <issue>`` (plus the
        ``; tmux kill-session -t ticket-<issue>`` suffix when ``terminate_session``).
    """
    command = " ".join(shlex.quote(part) for part in argv)
    line = f"{command} ; {shlex.quote(session_end_bin)} {issue}"
    if terminate_session:
        # ``ticket-<issue>`` is the stable session-name convention (adapters/workspace/sessions +
        # app/actions). Runs LAST (after session-end) so the state is already torn down.
        line += f" ; tmux kill-session -t {shlex.quote(f'ticket-{issue}')}"
    return line

"""Tests for the pure launch-argv builder (:mod:`kanbanmate.core.launch_argv`).

Pure unit tests — no I/O, no git, no tmux. They assert the exact argv SHAPE, both bypass-ban
guards, and the ``; kanban-session-end <issue>`` command composition (``;`` not ``&&``) with
shlex-quoting that survives a space-/newline-bearing worktree path or filled prompt.
"""

from __future__ import annotations

import shlex

import pytest

from kanbanmate.core.launch_argv import build_claude_argv, wrap_with_session_end

# ---------------------------------------------------------------------------
# build_claude_argv
# ---------------------------------------------------------------------------


def test_build_claude_argv_emits_exact_shape() -> None:
    """The argv is exactly claude --session-id <uuid> --permission-mode <mode> --add-dir <wt>."""
    argv = build_claude_argv("uuid-123", "/work/tree", "docs", "auto")
    assert argv == [
        "claude",
        "--session-id",
        "uuid-123",
        "--permission-mode",
        "auto",
        "--add-dir",
        "/work/tree",
    ]


def test_build_claude_argv_does_not_emit_the_profile() -> None:
    """The permission_profile is a guard-only arg — it never appears in the argv."""
    argv = build_claude_argv("uuid-123", "/work/tree", "dev", "auto")
    assert "dev" not in argv


def test_build_claude_argv_threads_permission_mode() -> None:
    """A non-default permission_mode is emitted after --permission-mode."""
    argv = build_claude_argv("uuid-123", "/work/tree", "docs", "plan")
    assert argv[argv.index("--permission-mode") + 1] == "plan"


def test_build_claude_argv_rejects_bypass_profile() -> None:
    """A profile containing 'bypass' is banned (DESIGN §10)."""
    with pytest.raises(ValueError, match="profile"):
        build_claude_argv("uuid-123", "/work/tree", "bypassPermissions", "auto")


def test_build_claude_argv_rejects_bypass_mode() -> None:
    """A permission_mode containing 'bypass' is banned (DESIGN §10) — separate guard."""
    with pytest.raises(ValueError, match="mode"):
        build_claude_argv("uuid-123", "/work/tree", "docs", "bypassPermissions")


# ---------------------------------------------------------------------------
# wrap_with_session_end
# ---------------------------------------------------------------------------


def test_wrap_with_session_end_appends_semicolon_wrapper() -> None:
    """The wrapper appends '; <bin> <issue>' with ';' (NOT '&&') so it always fires."""
    argv = build_claude_argv("uuid-123", "/work/tree", "docs", "auto")
    command = wrap_with_session_end(argv, 7, session_end_bin="kanban-session-end")
    assert command.endswith("; kanban-session-end 7")
    assert "&&" not in command


def test_wrap_with_session_end_terminate_session_appends_kill() -> None:
    """terminate_session=True appends a kill-session for ticket-<issue> AFTER the session-end shim."""
    argv = build_claude_argv("uuid-123", "/work/tree", "docs", "auto")
    command = wrap_with_session_end(
        argv, 7, session_end_bin="kanban-session-end", terminate_session=True
    )
    assert command.endswith("; tmux kill-session -t ticket-7")
    # The kill runs AFTER session-end (state is purged first, then the session is removed).
    assert command.index("kanban-session-end 7") < command.index("tmux kill-session")


def test_wrap_with_session_end_default_no_kill() -> None:
    """The autonomous default leaves the session attachable (no kill-session)."""
    argv = build_claude_argv("uuid-123", "/work/tree", "docs", "auto")
    command = wrap_with_session_end(argv, 7, session_end_bin="kanban-session-end")
    assert "kill-session" not in command


def test_wrap_with_session_end_quotes_each_element() -> None:
    """Each argv element is shlex-quoted (the composed line round-trips via shlex.split)."""
    argv = ["claude", "--add-dir", "/work/tree"]
    command = wrap_with_session_end(argv, 9, session_end_bin="kanban-session-end")
    # shlex.split recovers the original argv + the ';' separator + the bin + the issue, un-split.
    assert shlex.split(command) == [
        "claude",
        "--add-dir",
        "/work/tree",
        ";",
        "kanban-session-end",
        "9",
    ]


def test_wrap_with_session_end_preserves_space_bearing_worktree_path() -> None:
    """A worktree path WITH a space stays one un-split arg (does not break --add-dir <path>)."""
    spaced = "/Volumes/My Disk/work tree"
    argv = build_claude_argv("uuid-123", spaced, "docs", "auto")
    command = wrap_with_session_end(argv, 42, session_end_bin="kanban-session-end")
    # The spaced path round-trips as a single token after --add-dir, never two args.
    parts = shlex.split(command)
    assert parts[parts.index("--add-dir") + 1] == spaced
    # And it is single-quoted in the raw command line.
    assert shlex.quote(spaced) in command


def test_wrap_with_session_end_preserves_multiline_prompt_positional() -> None:
    """A filled prompt positional with spaces/newlines is preserved as ONE quoted arg."""
    argv = build_claude_argv("uuid-123", "/work/tree", "docs", "auto")
    prompt = "/implement:phase do the thing\nthen the other thing"
    command = wrap_with_session_end([*argv, prompt], 7, session_end_bin="kanban-session-end")
    parts = shlex.split(command)
    # The prompt is the last claude arg (right before the ';' separator), recovered un-split.
    assert parts[parts.index(";") - 1] == prompt


def test_wrap_with_session_end_quotes_the_session_end_bin() -> None:
    """An absolute session-end bin path with a space is quoted in the wrapper."""
    abs_bin = "/opt/my tools/kanban-session-end"
    command = wrap_with_session_end(["claude"], 7, session_end_bin=abs_bin)
    assert shlex.quote(abs_bin) in command
    assert shlex.split(command) == ["claude", ";", abs_bin, "7"]

"""Tests for TmuxSessions.capture_ansi (tiller §1.2)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

from kanbanmate.adapters.workspace.sessions import TmuxSessions


def _recording_runner(
    output: str = "",
) -> tuple[Callable[..., subprocess.CompletedProcess[Any]], list[list[str]]]:
    calls: list[list[str]] = []

    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
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


def test_capture_ansi_scrollback_adds_start_line() -> None:
    """``scrollback=N`` captures N lines of history via ``-S -<N>`` (operator scroll-back)."""
    runner, calls = _recording_runner("history")
    s = TmuxSessions(runner=runner)
    s.capture_ansi("ticket-3", scrollback=500)
    argv = calls[-1]
    assert "-S" in argv
    assert argv[argv.index("-S") + 1] == "-500"
    assert "-e" in argv


def test_capture_ansi_no_scrollback_omits_start_line() -> None:
    """Default (scrollback=0) captures only the visible pane (no ``-S``)."""
    runner, calls = _recording_runner("visible")
    s = TmuxSessions(runner=runner)
    s.capture_ansi("ticket-3")
    assert "-S" not in calls[-1]


def test_pane_size_parses_display_message() -> None:
    """pane_size returns the (cols, rows) reported by tmux display-message."""
    runner, calls = _recording_runner("213 51")
    s = TmuxSessions(runner=runner)
    assert s.pane_size("ticket-3") == (213, 51)
    assert "display-message" in calls[-1]


def test_pane_size_falls_back_on_error() -> None:
    """A malformed/empty display-message degrades to the 80x24 default."""
    runner, _ = _recording_runner("")  # empty stdout → parse error → fallback
    s = TmuxSessions(runner=runner)
    assert s.pane_size("ticket-3") == (80, 24)

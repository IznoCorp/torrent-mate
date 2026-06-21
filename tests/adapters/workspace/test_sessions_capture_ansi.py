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

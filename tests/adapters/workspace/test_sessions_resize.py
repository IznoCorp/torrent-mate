"""Tests for TmuxSessions.resize (tiller §1.1)."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import Any

import pytest

from kanbanmate.adapters.workspace.sessions import TmuxSessions


def _fake_run(calls: list[list[str]]) -> Callable[..., subprocess.CompletedProcess[Any]]:
    def runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="", stderr="")

    return runner


def test_resize_builds_correct_argv() -> None:
    calls: list[list[str]] = []
    s = TmuxSessions(runner=_fake_run(calls))
    s.resize("ticket-7", cols=220, rows=50)
    assert calls[-1] == ["tmux", "resize-window", "-t", "ticket-7", "-x", "220", "-y", "50"]


def test_resize_uses_check_true() -> None:
    """resize must raise on non-zero exit (check=True path)."""

    def failing_runner(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        if "resize-window" in argv:
            raise subprocess.CalledProcessError(1, argv)
        return subprocess.CompletedProcess(argv, 0)

    s = TmuxSessions(runner=failing_runner)
    with pytest.raises(subprocess.CalledProcessError):
        s.resize("ticket-7", 80, 24)

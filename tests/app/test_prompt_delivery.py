"""Tests for the prompt-delivery observability helpers (#11).

These cover the extracted :func:`pane_tail`, :func:`poll_pane` (with its loud timeout log), and
:func:`verify_prompt_delivered` (WARN-only post-send check) directly, so the behaviour is pinned
independently of the full ``LaunchAction.execute`` flow.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from kanbanmate.app.prompt_delivery import pane_tail, poll_pane, verify_prompt_delivered


def _deps_with_capture(*captures: str) -> MagicMock:
    """Build a ``Deps``-like mock whose ``sessions.capture`` yields the scripted snapshots."""
    deps = MagicMock()
    deps.sessions.capture.side_effect = list(captures)
    deps.sleeper = lambda _s: None
    return deps


def test_pane_tail_empty_capture() -> None:
    """An empty capture renders a clear placeholder rather than nothing."""
    assert pane_tail("") == "(empty pane capture)"
    assert pane_tail("   \n  ") == "(empty pane capture)"


def test_pane_tail_returns_trailing_lines() -> None:
    """``pane_tail`` returns only the trailing lines (bounded diagnostic)."""
    capture = "\n".join(f"line {n}" for n in range(50))
    tail = pane_tail(capture)
    assert "line 49" in tail
    assert "line 0" not in tail  # the head is dropped


def test_poll_pane_returns_true_on_trust() -> None:
    """A trust-dialog snapshot returns True (the caller sends the dismiss Enter)."""
    deps = _deps_with_capture("Do you trust the files in this folder?")
    assert poll_pane(deps, "ticket-7") is True


def test_poll_pane_returns_false_on_ready() -> None:
    """A ready-REPL snapshot returns False (already trusted → no dismiss Enter)."""
    deps = _deps_with_capture("│ > Welcome to Claude")
    assert poll_pane(deps, "ticket-7") is False


def test_poll_pane_timeout_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """#11: an exhausted poll (no trust/ready) returns False AND logs the pane tail."""
    from kanbanmate.core.launch_keys import TRUST_POLL_ATTEMPTS

    deps = _deps_with_capture(*(["unrecognised pane"] * TRUST_POLL_ATTEMPTS))
    with caplog.at_level(logging.WARNING):
        result = poll_pane(deps, "ticket-7")
    assert result is False
    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "timed out" in messages and "Pane tail" in messages


def test_verify_prompt_delivered_warns_when_prompt_visible(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """#11: a prompt still sitting verbatim in the pane WARNs + stickies (never raises)."""
    filled = "/implement:phase #7 run all the remaining phases now please"
    deps = MagicMock()
    deps.sessions.capture.return_value = f"│ > {filled}"

    with caplog.at_level(logging.WARNING):
        verify_prompt_delivered(deps, 7, "ticket-7", filled, column_key="InProgress")

    messages = " ".join(r.getMessage() for r in caplog.records)
    assert "UNDELIVERED" in messages
    deps.board_writer.list_issue_comments.assert_called()  # the advisory sticky was attempted


def test_verify_prompt_delivered_silent_when_consumed() -> None:
    """#11: a clean post-send pane (prompt consumed) is silent — no warning, no sticky."""
    filled = "/implement:phase #7 run all the remaining phases now please"
    deps = MagicMock()
    deps.sessions.capture.return_value = "│ > Welcome to Claude"  # prompt gone → consumed

    verify_prompt_delivered(deps, 7, "ticket-7", filled, column_key="InProgress")

    deps.board_writer.list_issue_comments.assert_not_called()


def test_verify_prompt_delivered_capture_error_is_swallowed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """#11: a capture error during verification is swallowed (never breaks the launch)."""
    deps = MagicMock()
    deps.sessions.capture.side_effect = RuntimeError("tmux gone")

    with caplog.at_level(logging.WARNING):
        # Must NOT raise.
        verify_prompt_delivered(deps, 7, "ticket-7", "some prompt", column_key="InProgress")

    assert any("capture failed" in r.getMessage() for r in caplog.records)


def test_verify_prompt_delivered_short_prompt_never_false_positives() -> None:
    """#11: a SHORT prompt line (could legitimately echo) does not trigger the warning."""
    filled = "go"  # below the _MIN_PROBE_LEN floor
    deps = MagicMock()
    deps.sessions.capture.return_value = "│ > go"

    verify_prompt_delivered(deps, 7, "ticket-7", filled, column_key="InProgress")

    deps.board_writer.list_issue_comments.assert_not_called()

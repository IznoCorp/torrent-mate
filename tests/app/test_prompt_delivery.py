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


# ---------------------------------------------------------------------------
# submit_prompt_with_retries — the submit-reliability fix. Re-sends Enter until the prompt leaves the
# input box (claude v2.1.x can absorb the first submit Enter); bounded, fail-soft, WARN on exhaustion.
# ---------------------------------------------------------------------------


def _submit_deps() -> MagicMock:
    """A Deps-like mock with a no-op sleeper for the submit-retry loop."""
    deps = MagicMock()
    deps.sleeper = lambda _s: None
    return deps


def test_submit_lands_on_first_check_sends_no_extra_enter() -> None:
    """When the initial submit already landed, the loop sends NO extra Enter and returns True."""
    from kanbanmate.app.prompt_delivery import submit_prompt_with_retries

    deps = _submit_deps()
    # A running-turn marker ⇒ submitted on the first probe.
    deps.sessions.capture.return_value = "● working…\n  esc to interrupt"
    ok = submit_prompt_with_retries(
        deps, 7, "ticket-7", "/implement:brainstorm do the thing now", "B"
    )
    assert ok is True
    deps.sessions.send_text.assert_not_called()  # no resubmit needed


def test_submit_resends_enter_until_submitted() -> None:
    """An absorbed first Enter ⇒ the loop re-sends Enter until the prompt leaves the input box."""
    from kanbanmate.app.prompt_delivery import submit_prompt_with_retries

    deps = _submit_deps()
    # pending, pending, then submitted (empty input box).
    deps.sessions.capture.side_effect = [
        "❯ [Pasted text #1 +20 lines]\n  auto mode on",
        "❯ [Pasted text #1 +20 lines]\n  auto mode on",
        "assistant: working\n❯ \n  auto mode on",
    ]
    ok = submit_prompt_with_retries(deps, 7, "ticket-7", "/implement:brainstorm do the thing", "B")
    assert ok is True
    # Enter re-sent exactly twice (the two pending probes), then the third probe saw it submitted.
    enter_calls = [c for c in deps.sessions.send_text.call_args_list if c.args[1:2] == ("Enter",)]
    assert len(enter_calls) == 2
    assert all(c.kwargs.get("literal") is False for c in enter_calls)


def test_submit_exhaustion_returns_false_and_warns() -> None:
    """A prompt that never submits exhausts the budget, returns False, and WARNs (advisory sticky)."""
    from kanbanmate.app.prompt_delivery import SUBMIT_RETRY_ATTEMPTS, submit_prompt_with_retries

    deps = _submit_deps()
    deps.board_writer.list_issue_comments.return_value = []
    filled = (
        "/implement:plan prepare the plan for #7 right now please"  # > 40 chars, verbatim probe
    )
    # Always pending: the verbatim prompt keeps sitting in the input box.
    deps.sessions.capture.return_value = f"❯ {filled}\n  auto mode on"
    ok = submit_prompt_with_retries(deps, 7, "ticket-7", filled, "Plan")
    assert ok is False
    # Enter re-sent once per attempt (budget spent).
    enter_calls = [c for c in deps.sessions.send_text.call_args_list if c.args[1:2] == ("Enter",)]
    assert len(enter_calls) == SUBMIT_RETRY_ATTEMPTS
    # The WARN fallback ran (verify_prompt_delivered upserts an advisory sticky → reads comments).
    assert deps.board_writer.list_issue_comments.called


def test_submit_fail_soft_on_capture_error() -> None:
    """A capture error ends the loop quietly (returns False) — never breaks the launch."""
    from kanbanmate.app.prompt_delivery import submit_prompt_with_retries

    deps = _submit_deps()
    deps.sessions.capture.side_effect = RuntimeError("tmux capture failed")
    ok = submit_prompt_with_retries(deps, 7, "ticket-7", "/implement:brainstorm do it", "B")
    assert ok is False
    deps.sessions.send_text.assert_not_called()

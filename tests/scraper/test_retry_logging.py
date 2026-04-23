"""Tests for build_retry_logger in personalscraper.scraper.http_retry.

Verifies the before_sleep callback factory produces correct structured log
output in the three key scenarios: exception present, no exception, and
no next_action (wait=0 fallback).
"""

from unittest.mock import Mock

import pytest
from tenacity import RetryCallState

from personalscraper.scraper.http_retry import build_retry_logger


class TestBuildRetryLogger:
    """Tests for the build_retry_logger factory function."""

    def test_exception_outcome_logs_warning_with_exc_info(self, caplog: pytest.LogCaptureFixture) -> None:
        """Outcome has an exception — warning emits event, attempt, wait, and exc_info.

        The callback must forward the exception to exc_info so that log
        aggregators capture the traceback alongside the structured fields.
        """
        log = Mock()
        cb = build_retry_logger(log, "http_retry")

        exc = ValueError("connection refused")
        outcome = Mock()
        outcome.exception.return_value = exc

        next_action = Mock()
        next_action.sleep = 2.5

        retry_state = Mock(spec=RetryCallState)
        retry_state.outcome = outcome
        retry_state.attempt_number = 3
        retry_state.next_action = next_action

        cb(retry_state)

        log.warning.assert_called_once_with(
            "http_retry",
            attempt=3,
            wait=2.5,
            exc_info=exc,
        )

    def test_successful_outcome_logs_warning_with_none_exc_info(self, caplog: pytest.LogCaptureFixture) -> None:
        """Outcome has no exception (success path) — exc_info=None is passed safely.

        Tenacity can call before_sleep even when the previous attempt succeeded
        but a stop condition has not yet triggered; the callback must not crash.
        """
        log = Mock()
        cb = build_retry_logger(log, "http_retry")

        outcome = Mock()
        outcome.exception.return_value = None  # no exception — successful result

        next_action = Mock()
        next_action.sleep = 1.0

        retry_state = Mock(spec=RetryCallState)
        retry_state.outcome = outcome
        retry_state.attempt_number = 1
        retry_state.next_action = next_action

        cb(retry_state)

        log.warning.assert_called_once_with(
            "http_retry",
            attempt=1,
            wait=1.0,
            exc_info=None,
        )

    def test_none_next_action_reports_wait_zero(self, caplog: pytest.LogCaptureFixture) -> None:
        """Next_action is None — wait=0 is reported and no AttributeError is raised.

        Tenacity sets next_action=None in edge cases (e.g. the last attempt
        before giving up). The callback must not crash and must report wait=0.
        """
        log = Mock()
        cb = build_retry_logger(log, "tvdb_retry")

        exc = RuntimeError("timeout")
        outcome = Mock()
        outcome.exception.return_value = exc

        retry_state = Mock(spec=RetryCallState)
        retry_state.outcome = outcome
        retry_state.attempt_number = 2
        retry_state.next_action = None  # no next action scheduled

        cb(retry_state)

        log.warning.assert_called_once_with(
            "tvdb_retry",
            attempt=2,
            wait=0,
            exc_info=exc,
        )

    def test_none_outcome_reports_exc_info_none(self, caplog: pytest.LogCaptureFixture) -> None:
        """Outcome is None — exc_info=None is passed and no AttributeError is raised.

        Guards against tenacity passing outcome=None before the first attempt
        result is recorded.
        """
        log = Mock()
        cb = build_retry_logger(log, "tmdb_retry")

        next_action = Mock()
        next_action.sleep = 5.0

        retry_state = Mock(spec=RetryCallState)
        retry_state.outcome = None
        retry_state.attempt_number = 1
        retry_state.next_action = next_action

        cb(retry_state)

        log.warning.assert_called_once_with(
            "tmdb_retry",
            attempt=1,
            wait=5.0,
            exc_info=None,
        )

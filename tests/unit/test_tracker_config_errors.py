"""Unit tests for tracker boot-validation error types — tracker-wiring RP5a.

Covers: TrackerError base, TrackerConfigIssue frozen dataclass,
TrackerConfigError aggregation and message formatting.
"""

from __future__ import annotations

import pytest

from personalscraper.api.tracker._errors import (
    TorrentFetchError,
    TrackerAuthError,
    TrackerConfigError,
    TrackerConfigIssue,
    TrackerError,
)


class TestTrackerErrorBase:
    """TrackerError is the base exception for the tracker provider family."""

    def test_is_exception_subclass(self) -> None:
        """TrackerError must inherit from Exception."""
        assert issubclass(TrackerError, Exception)

    def test_tracker_config_error_is_tracker_error(self) -> None:
        """TrackerConfigError must be catchable as TrackerError."""
        issue = TrackerConfigIssue(
            severity="error",
            code="missing_credentials",
            provider="lacale",
            message="no key",
        )
        err = TrackerConfigError([issue])
        assert isinstance(err, TrackerError)

    def test_existing_errors_unaffected(self) -> None:
        """TrackerAuthError and TorrentFetchError still exist and are ApiError subclasses."""
        from personalscraper.api._contracts import ApiError

        assert issubclass(TrackerAuthError, ApiError)
        assert issubclass(TorrentFetchError, ApiError)


class TestTrackerConfigIssue:
    """TrackerConfigIssue is a frozen dataclass carrying one boot-validation finding."""

    def test_frozen_dataclass(self) -> None:
        """TrackerConfigIssue fields cannot be mutated after construction."""
        issue = TrackerConfigIssue(
            severity="error",
            code="missing_credentials",
            provider="lacale",
            message="LACALE_API_KEY absent",
        )
        with pytest.raises(Exception):
            issue.severity = "warning"  # type: ignore[misc]

    def test_warning_severity(self) -> None:
        """Issues with severity 'warning' are non-fatal."""
        issue = TrackerConfigIssue(
            severity="warning",
            code="disabled_in_priority",
            provider="lacale",
            message="disabled but in priority",
        )
        assert issue.severity == "warning"

    def test_provider_none(self) -> None:
        """Provider can be None for issues not tied to a single tracker."""
        issue = TrackerConfigIssue(
            severity="error",
            code="unknown_provider",
            provider=None,
            message="ghost in priority list",
        )
        assert issue.provider is None

    def test_all_error_codes_accepted(self) -> None:
        """All four defined error codes are valid for the code field."""
        for code in (
            "missing_credentials",
            "protocol_mismatch",
            "unknown_provider",
            "disabled_in_priority",
        ):
            TrackerConfigIssue(
                severity="error",
                code=code,  # type: ignore[arg-type]
                provider="x",
                message="m",
            )


class TestTrackerConfigError:
    """TrackerConfigError aggregates multiple error-severity TrackerConfigIssue instances."""

    def test_carries_issues(self) -> None:
        """TrackerConfigError stores the exact list passed to its constructor."""
        issues = [
            TrackerConfigIssue(
                severity="error",
                code="missing_credentials",
                provider="lacale",
                message="no key",
            ),
            TrackerConfigIssue(
                severity="error",
                code="unknown_provider",
                provider=None,
                message="ghost",
            ),
        ]
        err = TrackerConfigError(issues)
        assert err.issues is issues
        assert len(err.issues) == 2

    def test_message_includes_count(self) -> None:
        """The error message includes the issue count and provider names."""
        issue = TrackerConfigIssue(
            severity="error",
            code="protocol_mismatch",
            provider="c411",
            message="not searchable",
        )
        err = TrackerConfigError([issue])
        assert "1 error" in str(err)
        assert "c411" in str(err)

    def test_catchable_as_tracker_error(self) -> None:
        """TrackerConfigError can be caught via the TrackerError base class."""
        issue = TrackerConfigIssue(
            severity="error",
            code="missing_credentials",
            provider="lacale",
            message="no key",
        )
        with pytest.raises(TrackerError):
            raise TrackerConfigError([issue])

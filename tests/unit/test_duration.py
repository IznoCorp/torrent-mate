"""Tests for parse_duration() — tracker-economy §Components.2."""

from __future__ import annotations

import pytest

from personalscraper.conf.models._duration import parse_duration


class TestParseDuration:
    """Duration parser: humanized strings and malformed input."""

    def test_seconds_unit(self) -> None:
        """Parse '90s' → 90 seconds."""
        assert parse_duration("90s") == 90

    def test_minutes_unit(self) -> None:
        """Parse '90m' → 5400 seconds."""
        assert parse_duration("90m") == 5_400

    def test_hours_unit(self) -> None:
        """Parse '72h' → 259200 seconds."""
        assert parse_duration("72h") == 259_200

    def test_days_unit(self) -> None:
        """Parse '3d' → 259200 seconds."""
        assert parse_duration("3d") == 259_200

    def test_weeks_unit(self) -> None:
        """Parse '2w' → 1209600 seconds."""
        assert parse_duration("2w") == 1_209_600

    def test_bare_int(self) -> None:
        """Bare int 3600 passes through unchanged."""
        assert parse_duration(3600) == 3_600

    def test_zero_value(self) -> None:
        """Parse '0h' → 0 seconds."""
        assert parse_duration("0h") == 0

    def test_unit_case_insensitive(self) -> None:
        """Parse '24H' (uppercase) → 86400 seconds."""
        assert parse_duration("24H") == 86_400

    def test_malformed_no_unit(self) -> None:
        """Reject '3600' with no unit suffix → ValueError."""
        with pytest.raises(ValueError, match="unknown duration unit"):
            parse_duration("3600")

    def test_malformed_non_integer_magnitude(self) -> None:
        """Reject '1.5h' with float magnitude → ValueError."""
        with pytest.raises(ValueError, match="non-integer magnitude"):
            parse_duration("1.5h")

    def test_malformed_unknown_unit(self) -> None:
        """Reject '3x' with unknown unit → ValueError."""
        with pytest.raises(ValueError, match="unknown duration unit"):
            parse_duration("3x")

    def test_empty_string(self) -> None:
        """Empty string → ValueError."""
        with pytest.raises(ValueError, match="must not be empty"):
            parse_duration("")

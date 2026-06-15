"""Tests for acquire/airing.py — aired predicate helpers (Phase 1)."""

from __future__ import annotations

from datetime import date

# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------


def test_parse_date_valid_past() -> None:
    """_parse_date returns a date for a valid ISO-8601 string."""
    from personalscraper.acquire.airing import _parse_date

    result = _parse_date("2023-01-15")
    assert result == date(2023, 1, 15)


def test_parse_date_empty_string_returns_none() -> None:
    """_parse_date returns None for an empty string (TBA / unknown)."""
    from personalscraper.acquire.airing import _parse_date

    assert _parse_date("") is None


def test_parse_date_malformed_returns_none() -> None:
    """_parse_date returns None for a non-ISO string — never raises."""
    from personalscraper.acquire.airing import _parse_date

    assert _parse_date("January 15, 2023") is None
    assert _parse_date("2023/01/15") is None
    assert _parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# _is_aired
# ---------------------------------------------------------------------------


def test_is_aired_past_date_true() -> None:
    """LOAD-BEARING: an episode with a past air-date is aired."""
    from personalscraper.acquire.airing import _is_aired

    today = date(2024, 6, 1)
    assert _is_aired("2023-01-15", today) is True


def test_is_aired_future_date_false() -> None:
    """LOAD-BEARING: an episode with a future air-date is NOT aired."""
    from personalscraper.acquire.airing import _is_aired

    today = date(2024, 6, 1)
    assert _is_aired("2025-12-31", today) is False


def test_is_aired_today_boundary_true() -> None:
    """LOAD-BEARING: air_date == today counts as aired (<= today inclusive)."""
    from personalscraper.acquire.airing import _is_aired

    today = date(2024, 6, 15)
    assert _is_aired("2024-06-15", today) is True


def test_is_aired_empty_string_false() -> None:
    """LOAD-BEARING: empty air_date (TBA) is never aired, never raises."""
    from personalscraper.acquire.airing import _is_aired

    assert _is_aired("", date(2024, 6, 1)) is False


def test_is_aired_malformed_false() -> None:
    """LOAD-BEARING: malformed air_date is never aired, never raises."""
    from personalscraper.acquire.airing import _is_aired

    assert _is_aired("not-a-date", date(2024, 6, 1)) is False

"""Unit tests for core.identity.MediaRef."""

from __future__ import annotations

import pytest

from personalscraper.core.identity import MediaRef


def test_media_ref_tvdb_primary() -> None:
    """tvdb_id is the primary identifier — must accept int."""
    ref = MediaRef(tvdb_id=255968)
    assert ref.tvdb_id == 255968
    assert ref.tmdb_id is None
    assert ref.imdb_id is None


def test_media_ref_all_slots() -> None:
    """All three provider IDs can be set simultaneously."""
    ref = MediaRef(tvdb_id=1, tmdb_id=2, imdb_id="tt0000001")
    assert ref.tvdb_id == 1
    assert ref.tmdb_id == 2
    assert ref.imdb_id == "tt0000001"


def test_media_ref_frozen() -> None:
    """Frozen dataclass — attribute mutation after construction is forbidden."""
    ref = MediaRef(tvdb_id=1)
    with pytest.raises((AttributeError, TypeError)):
        ref.tvdb_id = 99  # type: ignore[misc]


def test_media_ref_equality() -> None:
    """Equality is structural — same tvdb_id means same MediaRef."""
    assert MediaRef(tvdb_id=1) == MediaRef(tvdb_id=1)
    assert MediaRef(tvdb_id=1) != MediaRef(tvdb_id=2)


def test_media_ref_requires_at_least_one_id() -> None:
    """Construction with no provider IDs must raise ValueError."""
    with pytest.raises((ValueError, TypeError)):
        MediaRef()

"""Tests for core.ownership: OwnershipChecker Protocol + NullOwnershipChecker."""

from __future__ import annotations

from personalscraper.core.identity import MediaRef
from personalscraper.core.ownership import NullOwnershipChecker, OwnershipChecker


def test_null_checker_always_returns_false() -> None:
    """NullOwnershipChecker.owns always returns False (fail-open default)."""
    checker = NullOwnershipChecker()
    ref = MediaRef(tvdb_id=12345)
    assert checker.owns(ref, kind="movie") is False


def test_null_checker_episode_always_returns_false() -> None:
    """NullOwnershipChecker returns False for episode kind with season/episode args."""
    checker = NullOwnershipChecker()
    ref = MediaRef(tvdb_id=99)
    assert checker.owns(ref, kind="episode", season=1, episode=3) is False


def test_null_checker_tmdb_only_ref_returns_false() -> None:
    """NullOwnershipChecker returns False even for a tmdb-only MediaRef."""
    checker = NullOwnershipChecker()
    ref = MediaRef(tmdb_id=555)
    assert checker.owns(ref, kind="movie") is False


def test_null_checker_imdb_only_ref_returns_false() -> None:
    """NullOwnershipChecker returns False for an imdb-only MediaRef."""
    checker = NullOwnershipChecker()
    ref = MediaRef(imdb_id="tt0000001")
    assert checker.owns(ref, kind="movie") is False


def test_null_checker_implements_protocol() -> None:
    """NullOwnershipChecker satisfies the OwnershipChecker runtime-checkable Protocol."""
    checker = NullOwnershipChecker()
    assert isinstance(checker, OwnershipChecker)

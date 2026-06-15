"""Tests for _WantedSubStore.find — soft dedup guard (criterion 4)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a fresh AcquireStore on a temp acquire.db and close it afterwards.

    The store is inert until a sub-store is accessed; the first ``store.wanted``
    access lazily opens the connection and applies the schema migration.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        A :class:`ConcreteAcquireStore` (opens on first sub-store access).
    """
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _add_series(store: ConcreteAcquireStore, tvdb_id: int) -> int:
    """Insert a ``followed_series`` parent row and return its rowid.

    ``wanted.followed_id`` carries a ``REFERENCES followed_series(id)`` FK and
    the connection runs with ``PRAGMA foreign_keys=ON``, so a wanted row can
    only point at an existing followed_series row.

    Args:
        store: The open store.
        tvdb_id: TVDB id for the parent series' media ref.

    Returns:
        The rowid of the inserted ``followed_series`` row.
    """
    return store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=tvdb_id),
            title=f"Series {tvdb_id}",
            added_at=1_000_000,
            active=True,
        )
    )


def _episode(followed_id: int, season: int, ep: int) -> WantedItem:
    """Build a pending episode :class:`WantedItem` for the given coordinates.

    Args:
        followed_id: FK to an existing followed_series row.
        season: Season number.
        ep: Episode number within the season.

    Returns:
        A 'pending' episode :class:`WantedItem`.
    """
    return WantedItem(
        media_ref=MediaRef(tvdb_id=12345),
        kind="episode",
        status="pending",
        enqueued_at=1_000_000,
        followed_id=followed_id,
        season=season,
        episode=ep,
    )


def test_find_returns_none_when_empty(store: ConcreteAcquireStore) -> None:
    """Find returns None when the wanted table is empty."""
    fid = _add_series(store, tvdb_id=100)
    result = store.wanted.find(followed_id=fid, kind="episode", season=1, episode=1)
    assert result is None


def test_find_returns_row_after_add(store: ConcreteAcquireStore) -> None:
    """Find returns the WantedItem that was just added via add()."""
    fid = _add_series(store, tvdb_id=200)
    store.wanted.add(_episode(followed_id=fid, season=2, ep=3))
    result = store.wanted.find(followed_id=fid, kind="episode", season=2, episode=3)
    assert result is not None
    assert result.followed_id == fid
    assert result.season == 2
    assert result.episode == 3
    assert result.kind == "episode"
    assert result.status == "pending"


def test_find_returns_none_for_different_episode(store: ConcreteAcquireStore) -> None:
    """Find returns None when season/episode does not match."""
    fid = _add_series(store, tvdb_id=300)
    store.wanted.add(_episode(followed_id=fid, season=1, ep=1))
    result = store.wanted.find(followed_id=fid, kind="episode", season=1, episode=2)
    assert result is None


def test_find_null_safe_season_no_false_match(store: ConcreteAcquireStore) -> None:
    """find(season=None) does NOT match an episode row with season=1."""
    fid = _add_series(store, tvdb_id=400)
    store.wanted.add(_episode(followed_id=fid, season=1, ep=1))
    result = store.wanted.find(followed_id=fid, kind="episode", season=None, episode=None)
    assert result is None


def test_find_different_followed_id_no_match(store: ConcreteAcquireStore) -> None:
    """Find with a different followed_id returns None."""
    fid_a = _add_series(store, tvdb_id=500)
    fid_b = _add_series(store, tvdb_id=501)
    store.wanted.add(_episode(followed_id=fid_a, season=1, ep=1))
    result = store.wanted.find(followed_id=fid_b, kind="episode", season=1, episode=1)
    assert result is None

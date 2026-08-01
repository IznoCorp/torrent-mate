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


# ── find(statuses=...) — status-filtered lookup (review S1) ────────────────


def test_find_statuses_filter_excludes_non_matching(store: ConcreteAcquireStore) -> None:
    """find(statuses=...) returns None when the only row is in another status."""
    fid = _add_series(store, tvdb_id=700)
    wid = store.wanted.add(_episode(followed_id=fid, season=1, ep=1))
    store.wanted.set_status(wid, "abandoned")

    live = store.wanted.find(
        followed_id=fid,
        kind="episode",
        season=1,
        episode=1,
        statuses=("pending", "searching", "available"),
    )
    assert live is None, "a terminal row must not match a live-statuses lookup"

    # Status-agnostic lookup still sees it (existing dedup behavior unchanged).
    any_row = store.wanted.find(followed_id=fid, kind="episode", season=1, episode=1)
    assert any_row is not None and any_row.status == "abandoned"


def test_find_statuses_filter_skips_older_terminal_row(store: ConcreteAcquireStore) -> None:
    """S1 REGRESSION: the LIVE row wins over an OLDER terminal one.

    After an R6 fallback re-enqueues episodes, an older ``absorbed`` row shares
    the coordinates of the fresh ``pending`` one. The status-agnostic find
    returns the OLDEST row (the absorbed one) — the statuses filter must find
    the live row instead.
    """
    fid = _add_series(store, tvdb_id=701)
    old_wid = store.wanted.add(_episode(followed_id=fid, season=2, ep=4))
    store.wanted.set_status(old_wid, "absorbed")
    new_wid = store.wanted.add(_episode(followed_id=fid, season=2, ep=4))

    # Status-agnostic: OLDEST row (the absorbed shadow) — documented behavior.
    oldest = store.wanted.find(followed_id=fid, kind="episode", season=2, episode=4)
    assert oldest is not None and oldest.id == old_wid

    # Statuses filter: the LIVE row.
    live = store.wanted.find(
        followed_id=fid,
        kind="episode",
        season=2,
        episode=4,
        statuses=("pending", "searching", "available"),
    )
    assert live is not None and live.id == new_wid
    assert live.status == "pending"


# ── list_for_followed — bulk read feeding the shared facts selector ────────


def test_list_for_followed_returns_every_row_ordered_by_id(store: ConcreteAcquireStore) -> None:
    """All rows of the follow come back, oldest first — the selector needs them all."""
    fid = _add_series(store, tvdb_id=600)
    first = store.wanted.add(_episode(followed_id=fid, season=1, ep=1))
    second = store.wanted.add(_episode(followed_id=fid, season=1, ep=2))

    rows = store.wanted.list_for_followed(fid, kind="episode")

    assert [r.id for r in rows] == [first, second]
    assert [(r.season, r.episode) for r in rows] == [(1, 1), (1, 2)]


def test_list_for_followed_includes_closed_rows(store: ConcreteAcquireStore) -> None:
    """Closed rows are NOT filtered here — that judgement belongs to the selector.

    Filtering in SQL is exactly what let two surfaces diverge: each owned its
    own WHERE clause. The store returns the facts; ``select_wanted_facts``
    decides which row governs.
    """
    fid = _add_series(store, tvdb_id=601)
    wid = store.wanted.add(_episode(followed_id=fid, season=1, ep=1))
    store.wanted.set_status(wid, "done")

    rows = store.wanted.list_for_followed(fid, kind="episode")

    assert [r.status for r in rows] == ["done"]


def test_list_for_followed_isolates_kind_and_follow(store: ConcreteAcquireStore) -> None:
    """Another follow's rows — and the movie family — never leak into the result."""
    fid_a = _add_series(store, tvdb_id=602)
    fid_b = _add_series(store, tvdb_id=603)
    store.wanted.add(_episode(followed_id=fid_a, season=1, ep=1))
    store.wanted.add(_episode(followed_id=fid_b, season=9, ep=9))
    store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=12345),
            kind="movie",
            status="pending",
            enqueued_at=1_000_000,
            followed_id=fid_a,
        )
    )

    rows = store.wanted.list_for_followed(fid_a, kind="episode")

    assert [(r.season, r.episode) for r in rows] == [(1, 1)]


def test_list_for_followed_empty_when_no_rows(store: ConcreteAcquireStore) -> None:
    """A follow with no queue rows yields an empty list, not an error."""
    fid = _add_series(store, tvdb_id=604)
    assert store.wanted.list_for_followed(fid, kind="episode") == []

"""``find_all_by_refs``: many media looked up in ONE query, each answered as ``find_all_by_ref`` would.

The provider search flags a page of results ``followed``; asking the store once per result is a
query per row, so the batch asks once. The batch must never answer differently from the single
lookup it replaces: the parity test runs both over the same rows.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import FollowedSeries, FollowKind
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a migrated store on a temp acquire.db and close it afterwards.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        The store.
    """
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    s.follow.list_all()  # opens the store and applies the migrations
    try:
        yield s
    finally:
        s.close()


def _follow(store: ConcreteAcquireStore, ref: MediaRef, title: str, kind: FollowKind) -> int:
    """Store a follow and return its rowid.

    Args:
        store: The store.
        ref: The medium's ids.
        title: Its title.
        kind: ``"show"`` or ``"movie"``.

    Returns:
        The rowid.
    """
    return store.follow.add(FollowedSeries(media_ref=ref, title=title, added_at=1, kind=kind))


def test_an_empty_batch_asks_nothing(store: ConcreteAcquireStore) -> None:
    """No lookup, no answer, and no query."""
    assert store.follow.find_all_by_refs([]) == []


def test_each_lookup_gets_the_rows_the_single_lookup_gives(store: ConcreteAcquireStore) -> None:
    """The batch is the single lookup, asked many times: same rows, same order, one list per ask."""
    _follow(store, MediaRef(tvdb_id=81189, tmdb_id=1396), "Breaking Bad", "show")
    _follow(store, MediaRef(tmdb_id=603, imdb_id="tt0133093"), "The Matrix", "movie")
    _follow(store, MediaRef(tmdb_id=603), "A show numbered 603", "show")
    asked: list[tuple[MediaRef, FollowKind | None]] = [
        (MediaRef(tvdb_id=81189), "show"),
        (MediaRef(tmdb_id=603), "movie"),
        (MediaRef(tmdb_id=603), "show"),
        (MediaRef(imdb_id="tt0133093"), None),
        (MediaRef(tmdb_id=1396), None),
        (MediaRef(tmdb_id=999), "movie"),
        (MediaRef(tvdb_id=81189, tmdb_id=1396), "movie"),
    ]

    batch = store.follow.find_all_by_refs(asked)

    assert len(batch) == len(asked)
    for (ref, kind), rows in zip(asked, batch, strict=True):
        assert [row.id for row in rows] == [row.id for row in store.follow.find_all_by_ref(ref, kind=kind)]


def test_an_unknown_medium_gets_an_empty_list_among_known_ones(store: ConcreteAcquireStore) -> None:
    """A lookup that matches nothing answers ``[]`` in its own slot, never shifting the others."""
    followed = _follow(store, MediaRef(tmdb_id=1), "One", "movie")

    batch = store.follow.find_all_by_refs([(MediaRef(tmdb_id=2), "movie"), (MediaRef(tmdb_id=1), "movie")])

    assert [[row.id for row in rows] for rows in batch] == [[], [followed]]


def test_removed_and_request_rows_are_returned_for_the_caller_to_judge(store: ConcreteAcquireStore) -> None:
    """Like the single lookup, the batch returns every row; whether one stands is the caller's rule."""
    removed = _follow(store, MediaRef(tmdb_id=7), "Gone", "movie")
    store.follow.mark_removed(removed, now=2)

    (rows,) = store.follow.find_all_by_refs([(MediaRef(tmdb_id=7), "movie")])

    assert [(row.id, row.removed_at) for row in rows] == [(removed, 2)]


def test_a_batch_larger_than_one_statement_is_answered_whole(store: ConcreteAcquireStore) -> None:
    """A page well past SQLite's parameter limit still gets one answer per lookup."""
    kept = _follow(store, MediaRef(tmdb_id=4000), "Kept", "movie")
    asked: list[tuple[MediaRef, FollowKind | None]] = [(MediaRef(tmdb_id=n), "movie") for n in range(3000, 5000)]

    batch = store.follow.find_all_by_refs(asked)

    assert len(batch) == len(asked)
    assert [[row.id for row in rows] for rows in batch].count([kept]) == 1

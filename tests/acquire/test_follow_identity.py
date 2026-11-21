"""A follow is found by any of its provider ids, and the ids it learns are merged.

Covers the lookup that falls through tvdb → tmdb → imdb (``find_all_by_ref`` /
``find_by_ref``), the merge of learned ids on ``add`` (one row per medium, its
``media_ref_json`` widened and never narrowed nor overwritten), and the duplicates
that were already written before the merge existed: logged by the lookup and named
by :func:`find_follow_duplicates`.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.acquire.domain import FollowedSeries
from personalscraper.acquire.follow_duplicates import FollowDuplicate, find_follow_duplicates
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

_TVDB = 81189
_TMDB = 1396
_IMDB = "tt0903747"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return the path of the temporary acquire.db.

    Args:
        tmp_path: Pytest temp directory.

    Returns:
        The path the store opens.
    """
    return tmp_path / "acquire.db"


@pytest.fixture
def store(db_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a migrated store on a temp acquire.db and close it afterwards.

    Args:
        db_path: The temporary acquire.db path.

    Yields:
        A :class:`ConcreteAcquireStore` whose schema is applied.
    """
    s = build_acquire_store(AcquireConfig(db_path=db_path))
    s.follow.list_all()  # opens the store and applies the migrations before any raw write
    try:
        yield s
    finally:
        s.close()


def _follow(ref: MediaRef, title: str = "Breaking Bad", **fields: object) -> FollowedSeries:
    """Build an unpersisted follow.

    Args:
        ref: Its provider ids.
        title: Its title.
        **fields: Other :class:`FollowedSeries` fields.

    Returns:
        The follow, ``added_at`` fixed.
    """
    return FollowedSeries(media_ref=ref, title=title, added_at=1_700_000_000, **fields)  # type: ignore[arg-type]


def _insert_raw(db_path: Path, ref: dict[str, object], title: str = "Breaking Bad", active: int = 1) -> int:
    """Write a follow row directly, as the store wrote duplicates before the merge existed.

    Args:
        db_path: The migrated acquire.db.
        ref: The ``media_ref_json`` object.
        title: The row's title.
        active: The row's ``active`` flag.

    Returns:
        The rowid written.
    """
    blob = json.dumps({"tvdb_id": ref.get("tvdb_id"), "tmdb_id": ref.get("tmdb_id"), "imdb_id": ref.get("imdb_id")})
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO followed_series (media_ref_json, title, active, added_at) VALUES (?, ?, ?, 1)",
            (blob, title, active),
        )
        conn.commit()
        assert cur.lastrowid is not None
        return int(cur.lastrowid)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The merge of learned ids
# ---------------------------------------------------------------------------


def test_add_widens_the_row_found_by_its_tvdb_id(store: ConcreteAcquireStore) -> None:
    """``{tvdb:X}`` stored, then ``{tvdb:X, tmdb:Y}`` added → ONE row, its ref widened.

    Before the merge, the second add (a TMDB card whose TVDB id the route resolved)
    wrote a second row the whole-JSON unique index did not catch.
    """
    first = store.follow.add(_follow(MediaRef(tvdb_id=_TVDB)))

    second = store.follow.add(_follow(MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB)))

    assert second == first
    rows = store.follow.list_all()
    assert [r.id for r in rows] == [first]
    assert rows[0].media_ref == MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB)


def test_add_by_a_learned_id_lands_on_the_same_row(store: ConcreteAcquireStore) -> None:
    """After the widening, ``{tmdb:Y}`` alone finds the same row and narrows nothing."""
    first = store.follow.add(_follow(MediaRef(tvdb_id=_TVDB)))
    store.follow.add(_follow(MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB)))

    third = store.follow.add(_follow(MediaRef(tmdb_id=_TMDB)))

    assert third == first
    rows = store.follow.list_all()
    assert [r.id for r in rows] == [first]
    assert rows[0].media_ref == MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB)


def test_add_never_overwrites_a_held_id(store: ConcreteAcquireStore) -> None:
    """A learned id fills an empty slot only: a TMDB id already held is kept (the separation of ids)."""
    first = store.follow.add(_follow(MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB)))

    second = store.follow.add(_follow(MediaRef(tvdb_id=_TVDB, tmdb_id=999, imdb_id=_IMDB)))

    assert second == first
    (row,) = store.follow.list_all()
    assert row.media_ref == MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB, imdb_id=_IMDB)


def test_add_on_a_found_row_reactivates_it_as_the_conflict_path_does(store: ConcreteAcquireStore) -> None:
    """The merge reactivates and refreshes like ``ON CONFLICT``: title and kind refreshed, the rest kept."""
    first = store.follow.add(
        _follow(MediaRef(tvdb_id=_TVDB), title="Old", replace_owned=True, original_title="Original")
    )
    store.follow.set_active(first, False)

    second = store.follow.add(
        _follow(MediaRef(tvdb_id=_TVDB, imdb_id=_IMDB), title="New", kind="movie", replace_owned=False)
    )

    assert second == first
    row = store.follow.get(first)
    assert row is not None
    assert row.active is True
    assert (row.title, row.kind) == ("New", "movie")
    assert row.replace_owned is True, "a re-add must not withdraw a replacement authorisation"
    assert row.original_title == "Original", "a re-add that does not know the original title keeps it"
    assert row.media_ref == MediaRef(tvdb_id=_TVDB, imdb_id=_IMDB)


def test_add_with_nothing_found_inserts_a_new_row(store: ConcreteAcquireStore) -> None:
    """No row holds any of the ids → a new row, as before."""
    first = store.follow.add(_follow(MediaRef(tvdb_id=_TVDB)))

    second = store.follow.add(_follow(MediaRef(tvdb_id=1, tmdb_id=2), title="Other"))

    assert second != first
    assert len(store.follow.list_all()) == 2


# ---------------------------------------------------------------------------
# The lookup falls through
# ---------------------------------------------------------------------------


def test_lookup_falls_through_to_a_stored_tmdb_id(store: ConcreteAcquireStore) -> None:
    """A lookup ``{tvdb:A, tmdb:Y}`` finds a stored ``{tmdb:Y}`` (the TVDB id misses, the TMDB id hits)."""
    stored = store.follow.add(_follow(MediaRef(tmdb_id=_TMDB)))

    found = store.follow.find_by_ref(MediaRef(tvdb_id=4242, tmdb_id=_TMDB))

    assert found is not None
    assert found.id == stored


def test_lookup_falls_through_to_a_stored_imdb_id(store: ConcreteAcquireStore) -> None:
    """The fall-through reaches the IMDb id when neither TVDB nor TMDB id is held."""
    stored = store.follow.add(_follow(MediaRef(imdb_id=_IMDB)))

    found = store.follow.find_by_ref(MediaRef(tvdb_id=4242, tmdb_id=4343, imdb_id=_IMDB))

    assert found is not None
    assert found.id == stored


def test_find_all_by_ref_returns_every_row_holding_any_id_oldest_first(
    store: ConcreteAcquireStore, db_path: Path
) -> None:
    """Every row holding one of the ref's ids is returned, by rowid; a row holding none is not."""
    by_tvdb = _insert_raw(db_path, {"tvdb_id": _TVDB})
    unrelated = _insert_raw(db_path, {"tvdb_id": 5})
    by_tmdb = _insert_raw(db_path, {"tmdb_id": _TMDB})
    by_imdb = _insert_raw(db_path, {"imdb_id": _IMDB}, active=0)

    rows = store.follow.find_all_by_ref(MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB, imdb_id=_IMDB))

    assert [r.id for r in rows] == [by_tvdb, by_tmdb, by_imdb]
    assert unrelated not in [r.id for r in rows]


def test_find_by_ref_with_one_row_logs_no_duplicate(
    store: ConcreteAcquireStore, caplog: pytest.LogCaptureFixture
) -> None:
    """A single row found is not a duplicate: nothing logged."""
    store.follow.add(_follow(MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB)))

    with caplog.at_level(logging.WARNING):
        found = store.follow.find_by_ref(MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB))

    assert found is not None
    assert "acquire.follow.duplicate_id" not in caplog.text


# ---------------------------------------------------------------------------
# Duplicates written before the merge
# ---------------------------------------------------------------------------


def test_two_rows_sharing_a_tvdb_id_are_logged_and_named(
    store: ConcreteAcquireStore, db_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Two rows holding tvdb X → ``find_by_ref`` logs the duplicate and returns the oldest; the read names both."""
    oldest = _insert_raw(db_path, {"tvdb_id": _TVDB})
    newer = _insert_raw(db_path, {"tvdb_id": _TVDB, "tmdb_id": _TMDB})

    with caplog.at_level(logging.WARNING):
        found = store.follow.find_by_ref(MediaRef(tvdb_id=_TVDB))

    assert found is not None
    assert found.id == oldest
    assert "acquire.follow.duplicate_id" in caplog.text
    assert str(newer) in caplog.text
    duplicates = find_follow_duplicates(store.follow)
    assert [(d.provider, d.provider_id, d.followed_ids) for d in duplicates] == [("tvdb", _TVDB, (oldest, newer))]


def test_add_over_a_duplicate_widens_the_oldest_with_ids_no_other_row_holds(
    store: ConcreteAcquireStore, db_path: Path
) -> None:
    """Over two rows sharing tvdb X, ``add`` lands on the oldest and writes no third row.

    The oldest learns only an id no other row holds: giving it the TMDB id the newer row
    already carries would make the two rows' whole JSON equal, which the unique index
    refuses (an ``IntegrityError`` the engine would raise on every such re-add).
    """
    oldest = _insert_raw(db_path, {"tvdb_id": _TVDB}, active=0)
    _insert_raw(db_path, {"tvdb_id": _TVDB, "tmdb_id": _TMDB})

    landed = store.follow.add(_follow(MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB)))
    widened = store.follow.add(_follow(MediaRef(tvdb_id=_TVDB, imdb_id=_IMDB)))

    assert landed == widened == oldest
    assert len(store.follow.list_all()) == 2
    row = store.follow.get(oldest)
    assert row is not None
    assert row.active is True
    assert row.media_ref == MediaRef(tvdb_id=_TVDB, imdb_id=_IMDB)


def test_find_follow_duplicates_names_every_shared_id(store: ConcreteAcquireStore, db_path: Path) -> None:
    """An id held by two or more rows is one group, inactive rows included; ids held once are not."""
    first = _insert_raw(db_path, {"tvdb_id": _TVDB, "tmdb_id": _TMDB})
    second = _insert_raw(db_path, {"tvdb_id": _TVDB, "tmdb_id": _TMDB, "imdb_id": _IMDB}, active=0)
    film_a = _insert_raw(db_path, {"tmdb_id": 603}, title="The Matrix")
    film_b = _insert_raw(db_path, {"tmdb_id": 603, "imdb_id": "tt0133093"}, title="Matrix")
    _insert_raw(db_path, {"tvdb_id": 1}, title="Alone")

    duplicates = find_follow_duplicates(store.follow)

    assert duplicates == [
        FollowDuplicate(provider="tvdb", provider_id=_TVDB, followed_ids=(first, second)),
        FollowDuplicate(provider="tmdb", provider_id=603, followed_ids=(film_a, film_b)),
        FollowDuplicate(provider="tmdb", provider_id=_TMDB, followed_ids=(first, second)),
    ]


def test_find_follow_duplicates_is_empty_without_shared_ids(store: ConcreteAcquireStore) -> None:
    """Follows merged by ``add`` leave nothing to report."""
    store.follow.add(_follow(MediaRef(tvdb_id=_TVDB)))
    store.follow.add(_follow(MediaRef(tvdb_id=_TVDB, tmdb_id=_TMDB)))
    store.follow.add(_follow(MediaRef(tmdb_id=603), title="The Matrix", kind="movie"))

    assert find_follow_duplicates(store.follow) == []

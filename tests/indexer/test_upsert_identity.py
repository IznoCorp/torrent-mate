"""Identity of ``item_repo.upsert``: the canonical provider id first, the title second.

The index used to find an existing ``media_item`` by its canonicalised title only.
A row whose stored title still carried « (YYYY) » (« House of the Dragon (2022) »)
was then missed by a later write of the canonical title, and a 0-file phantom row
holding the same TVDB id was inserted beside it (prod, 2026-09-02: 18 such rows).
The write now looks up the incoming row's canonical provider id first; the title
path only runs when the incoming row carries no id, when no row holds it, or when
two or more rows already hold it (then the ambiguity is logged, never merged).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.schema import MediaItemKind, MediaItemRow

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB with every indexer migration applied.

    Returns:
        An open :class:`sqlite3.Connection`.
    """
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, _MIGRATIONS_DIR)
    return c


def _ids_json(**ids: str) -> str:
    """Build an ``external_ids_json`` value from provider-family keyword ids.

    Args:
        **ids: Provider family → series id (``tvdb="361753"``).

    Returns:
        The JSON string in the scanner's shape, ``"{}"`` when no id is given.
    """
    if not ids:
        return "{}"
    return json.dumps({family: {"series_id": sid, "episode_id": None} for family, sid in ids.items()})


def _make_item(
    title: str,
    *,
    kind: MediaItemKind = "show",
    year: int | None = None,
    external_ids_json: str = "{}",
    canonical_provider: str | None = None,
    category_id: str = "tv_shows",
) -> MediaItemRow:
    """Return a minimal :class:`MediaItemRow`.

    Args:
        title: Title as the caller passes it (may carry « (YYYY) »).
        kind: ``'movie'`` or ``'show'``.
        year: Release year, or ``None``.
        external_ids_json: Provider ids JSON.
        canonical_provider: ``'tvdb'`` / ``'tmdb'`` / ``None``.
        category_id: Logical category.

    Returns:
        A row ready for :func:`item_repo.insert` or :func:`item_repo.upsert`.
    """
    now = int(time.time())
    return MediaItemRow(
        id=0,
        kind=kind,
        title=title,
        title_sort=title,
        original_title=None,
        year=year,
        category_id=category_id,
        external_ids_json=external_ids_json,
        ratings_json=None,
        canonical_provider=canonical_provider,
        nfo_status=None,
        artwork_json=None,
        date_created=now,
        date_modified=now,
        date_metadata_refreshed=None,
        is_locked=0,
        preferred_lang="fr",
    )


def _count(conn: sqlite3.Connection, kind: str = "show") -> int:
    """Count the ``media_item`` rows of one kind.

    Args:
        conn: Open connection.
        kind: ``'movie'`` or ``'show'``.

    Returns:
        The row count.
    """
    count: int = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = ?", (kind,)).fetchone()[0]
    return count


def _events(caplog: pytest.LogCaptureFixture, name: str) -> list[dict[str, object]]:
    """Return the structlog event dicts named *name* captured by *caplog*.

    Args:
        caplog: The pytest log capture.
        name: Event name to keep.

    Returns:
        The matching event dicts, in emission order.
    """
    return [r.msg for r in caplog.records if isinstance(r.msg, dict) and r.msg.get("event") == name]


def test_upsert_same_tvdb_id_updates_the_row_whose_title_carries_its_year(conn: sqlite3.Connection) -> None:
    """« Silo (2023) » tvdb 361753 stored; an upsert of « Silo » tvdb 361753 updates it, no phantom."""
    stored_id = item_repo.insert(
        conn,
        _make_item("Silo (2023)", year=2023, external_ids_json=_ids_json(tvdb="361753"), canonical_provider="tvdb"),
    )

    result_id = item_repo.upsert(
        conn,
        _make_item("Silo", year=2023, external_ids_json=_ids_json(tvdb="361753"), canonical_provider="tvdb"),
    )

    assert result_id == stored_id, "the row holding the id must be updated, not a phantom inserted"
    assert _count(conn) == 1


def test_upsert_movie_matches_by_tmdb_id(conn: sqlite3.Connection) -> None:
    """A movie is found by its TMDB id even when the stored title differs."""
    stored_id = item_repo.insert(
        conn,
        _make_item(
            "Dune (2021)",
            kind="movie",
            year=2021,
            external_ids_json=_ids_json(tmdb="438631"),
            canonical_provider="tmdb",
            category_id="movies",
        ),
    )

    result_id = item_repo.upsert(
        conn,
        _make_item(
            "Dune",
            kind="movie",
            year=2021,
            external_ids_json=_ids_json(tmdb="438631"),
            canonical_provider="tmdb",
            category_id="movies",
        ),
    )

    assert result_id == stored_id
    assert _count(conn, "movie") == 1


def test_upsert_tmdb_canonical_show_matches_by_tmdb_id(conn: sqlite3.Connection) -> None:
    """A show whose canonical provider is TMDB is found by its TMDB id."""
    stored_id = item_repo.insert(
        conn,
        _make_item("Bref (2011)", year=2011, external_ids_json=_ids_json(tmdb="39275"), canonical_provider="tmdb"),
    )

    result_id = item_repo.upsert(
        conn,
        _make_item("Bref", year=2011, external_ids_json=_ids_json(tmdb="39275"), canonical_provider="tmdb"),
    )

    assert result_id == stored_id
    assert _count(conn) == 1


def test_upsert_id_shared_by_two_rows_takes_title_path_and_logs(
    conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """Two rows hold tvdb 79168: the write runs the title path, logs the ids, merges nothing."""
    friends_id = item_repo.insert(
        conn, _make_item("Friends", external_ids_json=_ids_json(tvdb="79168"), canonical_provider="tvdb")
    )
    uncut_id = item_repo.insert(
        conn, _make_item("Friends [UNCUT]", external_ids_json=_ids_json(tvdb="79168"), canonical_provider="tvdb")
    )

    with caplog.at_level(logging.WARNING):
        result_id = item_repo.upsert(
            conn, _make_item("Friends", external_ids_json=_ids_json(tvdb="79168"), canonical_provider="tvdb")
        )

    assert result_id == friends_id, "the title path must pick the row titled « Friends »"
    assert _count(conn) == 2, "an ambiguous id must never merge the duplicate rows"
    events = _events(caplog, "indexer.upsert.external_id_ambiguous")
    assert events, f"expected the ambiguity to be logged; got {[r.msg for r in caplog.records]}"
    assert events[0]["provider"] == "tvdb"
    assert events[0]["series_id"] == "79168"
    assert events[0]["item_ids"] == [friends_id, uncut_id]


def test_upsert_without_ids_keeps_the_title_path(conn: sqlite3.Connection) -> None:
    """A row without provider ids is matched by its title exactly as before."""
    stored_id = item_repo.upsert(conn, _make_item("Foo (2020)", kind="movie", year=2020, category_id="movies"))

    result_id = item_repo.upsert(conn, _make_item("Foo", kind="movie", year=2020, category_id="movies"))
    other_id = item_repo.upsert(conn, _make_item("Bar", kind="movie", year=2020, category_id="movies"))

    assert result_id == stored_id
    assert other_id != stored_id
    assert _count(conn, "movie") == 2


def test_upsert_remakes_with_distinct_ids_stay_two_rows(conn: sqlite3.Connection) -> None:
    """« Scrubs (2026) » tvdb 465690 and « Scrubs (2001) » tvdb 76156 stay two rows."""
    original_id = item_repo.upsert(
        conn,
        _make_item("Scrubs (2001)", year=2001, external_ids_json=_ids_json(tvdb="76156"), canonical_provider="tvdb"),
    )
    revival_id = item_repo.upsert(
        conn,
        _make_item("Scrubs (2026)", year=2026, external_ids_json=_ids_json(tvdb="465690"), canonical_provider="tvdb"),
    )

    assert revival_id != original_id
    assert _count(conn) == 2


def test_upsert_same_id_other_explicit_year_stays_two_rows(
    conn: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    """« Rick et Morty (2006) » and « Rick and Morty (2013) » share tvdb 275274: two folders, two rows."""
    misdated_id = item_repo.upsert(
        conn,
        _make_item(
            "Rick et Morty (2006)", year=2006, external_ids_json=_ids_json(tvdb="275274"), canonical_provider="tvdb"
        ),
    )

    with caplog.at_level(logging.WARNING):
        right_id = item_repo.upsert(
            conn,
            _make_item(
                "Rick and Morty (2013)",
                year=2013,
                external_ids_json=_ids_json(tvdb="275274"),
                canonical_provider="tvdb",
            ),
        )

    assert right_id != misdated_id
    assert _count(conn) == 2
    stored = item_repo.get_by_id(conn, misdated_id)
    assert stored is not None
    assert stored.year == 2006
    events = _events(caplog, "indexer.upsert.external_id_year_mismatch")
    assert events, f"expected the year mismatch to be logged; got {[r.msg for r in caplog.records]}"
    assert events[0]["item_id"] == misdated_id
    assert events[0]["stored_year"] == 2006
    assert events[0]["incoming_year"] == 2013


def test_upsert_by_id_keeps_the_stored_title(conn: sqlite3.Connection) -> None:
    """The UPDATE reached by id never rewrites ``title``."""
    stored_id = item_repo.insert(
        conn,
        _make_item("Silo (2023)", year=2023, external_ids_json=_ids_json(tvdb="361753"), canonical_provider="tvdb"),
    )

    result_id = item_repo.upsert(
        conn, _make_item("Silo", year=2023, external_ids_json=_ids_json(tvdb="361753"), canonical_provider="tvdb")
    )

    assert result_id == stored_id
    stored = item_repo.get_by_id(conn, stored_id)
    assert stored is not None
    assert stored.title == "Silo (2023)"


def test_upsert_by_id_skips_a_year_backfill_that_would_collide(conn: sqlite3.Connection) -> None:
    """A year-less row found by id is not given a year another row of its title already holds."""
    yearless_id = item_repo.insert(
        conn, _make_item("Foo", external_ids_json=_ids_json(tvdb="111"), canonical_provider="tvdb")
    )
    item_repo.insert(
        conn, _make_item("Foo", year=2020, external_ids_json=_ids_json(tvdb="222"), canonical_provider="tvdb")
    )

    result_id = item_repo.upsert(
        conn, _make_item("Foo", year=2020, external_ids_json=_ids_json(tvdb="111"), canonical_provider="tvdb")
    )

    assert result_id == yearless_id
    stored = item_repo.get_by_id(conn, yearless_id)
    assert stored is not None
    assert stored.year is None
    assert _count(conn) == 2


def test_get_by_canonical_id_ignores_a_placeholder_id(conn: sqlite3.Connection) -> None:
    """A leaked placeholder id (``0``) never matches a row."""
    item_repo.insert(conn, _make_item("Foo", external_ids_json=_ids_json(tvdb="0"), canonical_provider="tvdb"))

    found = item_repo.get_by_canonical_id(
        conn, _make_item("Bar", external_ids_json=_ids_json(tvdb="0"), canonical_provider="tvdb")
    )

    assert found is None


def test_get_by_canonical_id_filters_on_kind(conn: sqlite3.Connection) -> None:
    """A movie and a show sharing a TMDB number are distinct identities."""
    item_repo.insert(
        conn,
        _make_item(
            "Foo", kind="movie", external_ids_json=_ids_json(tmdb="42"), canonical_provider="tmdb", category_id="movies"
        ),
    )

    found = item_repo.get_by_canonical_id(
        conn, _make_item("Foo", external_ids_json=_ids_json(tmdb="42"), canonical_provider="tmdb")
    )

    assert found is None

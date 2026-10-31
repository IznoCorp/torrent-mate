"""The index facts (overview, poster URL, provider-read date) survive a write and a read.

``upsert`` writes them since migration 017; every read of ``item_repo`` must carry them
back, and the standalone ``insert`` must write them too, or a reader of the index sees
``None`` for a fact the index holds.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from personalscraper.indexer import migrations as _migrations_pkg
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.repos.item_repo import ItemAttributeRow, MediaItemRow

_FACTS = {
    "overview": "A detective and his doctor.",
    "poster_url": "https://image.tmdb.org/t/p/original/poster.jpg",
    "date_provider_read": 1_700_000_000.5,
}


def _row(**overrides: object) -> MediaItemRow:
    """Build a movie row carrying the three index facts.

    Args:
        **overrides: Fields replacing the defaults.

    Returns:
        The row.
    """
    base: dict[str, object] = {
        "id": 0,
        "kind": "movie",
        "title": "Sherlock Holmes",
        "title_sort": "Sherlock Holmes",
        "original_title": None,
        "year": 2009,
        "category_id": "movies",
        "external_ids_json": json.dumps({"tmdb": {"series_id": 10528}}),
        "ratings_json": None,
        "canonical_provider": "tmdb",
        "nfo_status": "valid",
        "artwork_json": None,
        "date_created": 1_750_000_000,
        "date_modified": 1_750_000_000,
        "date_metadata_refreshed": None,
        "is_locked": 0,
        "preferred_lang": "fr",
        **_FACTS,
    }
    base.update(overrides)
    return MediaItemRow(**base)  # type: ignore[arg-type]


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    """A migrated, empty index.

    Args:
        tmp_path: Pytest's temporary directory.

    Returns:
        The open connection.
    """
    connection = sqlite3.connect(str(tmp_path / "library.db"))
    apply_migrations(connection, Path(_migrations_pkg.__file__).parent)
    return connection


def _facts(row: MediaItemRow | None) -> dict[str, object]:
    """Read the three facts off a row.

    Args:
        row: The row read back.

    Returns:
        The facts by name.
    """
    assert row is not None
    return {"overview": row.overview, "poster_url": row.poster_url, "date_provider_read": row.date_provider_read}


def test_insert_writes_the_facts(conn: sqlite3.Connection) -> None:
    """``insert`` writes the three facts, ``get_by_id`` reads them back."""
    item_id = item_repo.insert(conn, _row())

    assert _facts(item_repo.get_by_id(conn, item_id)) == _FACTS


def test_every_item_read_carries_the_facts(conn: sqlite3.Connection) -> None:
    """Each read returning a ``MediaItemRow`` carries the facts ``upsert`` wrote."""
    item_id = item_repo.upsert(conn, _row(nfo_status="invalid", date_metadata_refreshed=None))

    assert _facts(item_repo.get_by_id(conn, item_id)) == _FACTS
    assert _facts(item_repo.find_by_tmdb_id(conn, 10528)) == _FACTS
    by_external_id = item_repo.find_by_external_id(conn, "tmdb", "10528", "movie")
    assert by_external_id is not None
    assert _facts(by_external_id[0]) == _FACTS
    assert _facts(item_repo.get_by_title_kind_year(conn, "Sherlock Holmes", "movie", 2009)) == _FACTS
    canonical = item_repo.get_by_canonical_id(conn, _row())
    assert isinstance(canonical, MediaItemRow)
    assert _facts(canonical) == _FACTS
    _on_a_disk_with_dispatch_attributes(conn, item_id)

    named = item_repo.find_by_normalized_name(conn, "sherlock holmes", "movie")
    assert named is not None
    assert _facts(named[0]) == _FACTS
    on_disk = item_repo.find_on_disk(conn, 1)
    assert [_facts(item) for item, _, _ in on_disk] == [_FACTS]
    rescrape = item_repo.find_items_needing_rescrape(conn)
    assert [_facts(item) for item, _, _ in rescrape] == [_FACTS]
    dispatched = item_repo.list_all_dispatch_items(conn)
    assert [_facts(item) for item, _, _ in dispatched] == [_FACTS]
    at_path = item_repo._get_holder_at_dispatch_path(conn, _row(), "/Volumes/D1/films/Sherlock Holmes")
    assert _facts(at_path) == _FACTS


def _on_a_disk_with_dispatch_attributes(conn: sqlite3.Connection, item_id: int) -> None:
    """Give an item a file on a disk and the dispatch attributes the dispatch reads need.

    Args:
        conn: The open index.
        item_id: The item.
    """
    conn.execute("INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u1', 'D1', '/Volumes/D1', 1)")
    conn.execute("INSERT INTO path(disk_id, rel_path) VALUES (1, 'films/Sherlock Holmes')")
    release = conn.execute("INSERT INTO media_release(item_id) VALUES (?)", (item_id,)).lastrowid
    conn.execute(
        "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
        " last_verified_at) VALUES (?, 1, 'x.mkv', 1, 1, '0', 1, 1)",
        (release,),
    )
    for key, value in (
        ("dispatch_normalized_title", "sherlock holmes"),
        ("dispatch_disk", "drive_a"),
        ("dispatch_path", "/Volumes/D1/films/Sherlock Holmes"),
    ):
        item_repo.upsert_attr(conn, ItemAttributeRow(item_id=item_id, key=key, value=value))

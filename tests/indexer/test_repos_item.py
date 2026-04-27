"""Repo-specific tests for item_repo: find_by_tmdb_id, upsert_attr, cascade delete.

Focuses on behaviors not covered by the round-trip tests in test_schema.py:
- find_by_tmdb_id lookup
- upsert_attr (insert + conflict-update)
- cascade delete: deleting a media_item removes its item_attribute rows
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.schema import ItemAttributeRow, MediaItemRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB seeded with the full migration chain.

    Returns:
        An open :class:`sqlite3.Connection` with the full schema applied.
    """
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


def _make_item(tmdb_id: int | None = None, kind: str = "movie") -> MediaItemRow:
    """Return a minimal MediaItemRow.

    Args:
        tmdb_id: Optional TMDB numeric ID.
        kind: Media kind: ``'movie'`` or ``'show'``.

    Returns:
        Populated :class:`MediaItemRow` ready for insertion.
    """
    now = int(time.time())
    return MediaItemRow(
        id=0,
        kind=kind,
        title="Test Item",
        title_sort="Test Item",
        original_title=None,
        year=2024,
        category_id="movies",
        tmdb_id=tmdb_id,
        imdb_id=None,
        tvdb_id=None,
        nfo_status=None,
        artwork_json=None,
        date_created=now,
        date_modified=now,
        date_metadata_refreshed=None,
        is_locked=0,
        preferred_lang="en",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_insert_item_returns_rowid(conn: sqlite3.Connection) -> None:
    """Insert returns a positive rowid on success."""
    rowid = item_repo.insert(conn, _make_item())
    assert isinstance(rowid, int)
    assert rowid > 0


def test_find_by_tmdb_id_returns_matching_row(conn: sqlite3.Connection) -> None:
    """find_by_tmdb_id returns the inserted row when the TMDB ID matches."""
    item_repo.insert(conn, _make_item(tmdb_id=99001))
    row = item_repo.find_by_tmdb_id(conn, 99001)
    assert row is not None
    assert row.tmdb_id == 99001
    assert row.title == "Test Item"


def test_find_by_tmdb_id_returns_none_when_not_found(conn: sqlite3.Connection) -> None:
    """find_by_tmdb_id returns None when no row matches the given TMDB ID."""
    result = item_repo.find_by_tmdb_id(conn, 99999)
    assert result is None


def test_upsert_attr_inserts_new_attribute(conn: sqlite3.Connection) -> None:
    """upsert_attr inserts a new item_attribute row."""
    item_id = item_repo.insert(conn, _make_item())
    attr = ItemAttributeRow(item_id=item_id, key="rating", value="8.5")
    rowid = item_repo.upsert_attr(conn, attr)
    assert rowid > 0

    fetched = item_repo.get_attr(conn, item_id, "rating")
    assert fetched is not None
    assert fetched.value == "8.5"


def test_upsert_attr_updates_existing_value_on_conflict(conn: sqlite3.Connection) -> None:
    """upsert_attr replaces the value when (item_id, key) already exists."""
    item_id = item_repo.insert(conn, _make_item())
    attr_v1 = ItemAttributeRow(item_id=item_id, key="rating", value="7.0")
    item_repo.upsert_attr(conn, attr_v1)

    attr_v2 = ItemAttributeRow(item_id=item_id, key="rating", value="9.1")
    item_repo.upsert_attr(conn, attr_v2)

    fetched = item_repo.get_attr(conn, item_id, "rating")
    assert fetched is not None
    assert fetched.value == "9.1"


def test_cascade_delete_item_removes_attributes(conn: sqlite3.Connection) -> None:
    """Deleting a media_item cascades to remove its item_attribute rows (ON DELETE CASCADE)."""
    item_id = item_repo.insert(conn, _make_item())
    item_repo.upsert_attr(conn, ItemAttributeRow(item_id=item_id, key="k1", value="v1"))
    item_repo.upsert_attr(conn, ItemAttributeRow(item_id=item_id, key="k2", value="v2"))

    # Verify attributes exist before deletion
    assert item_repo.get_attr(conn, item_id, "k1") is not None
    assert item_repo.get_attr(conn, item_id, "k2") is not None

    # Delete the parent item
    deleted = item_repo.delete(conn, item_id)
    assert deleted is True

    # Attributes should have been removed by CASCADE
    assert item_repo.get_attr(conn, item_id, "k1") is None
    assert item_repo.get_attr(conn, item_id, "k2") is None


def test_delete_nonexistent_item_returns_false(conn: sqlite3.Connection) -> None:
    """Delete returns False when the given id does not exist."""
    result = item_repo.delete(conn, 9999)
    assert result is False

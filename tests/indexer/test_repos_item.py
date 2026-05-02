"""Repo-specific tests for item_repo: find_by_tmdb_id, upsert_attr, cascade delete.

Focuses on behaviors not covered by the round-trip tests in test_schema.py:
- find_by_tmdb_id lookup
- upsert_attr (insert + conflict-update)
- cascade delete: deleting a media_item removes its item_attribute rows
- find_on_disk query helper (7.4)
- find_items_needing_rescrape query helper (7.4)
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Literal

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


def _make_item(tmdb_id: int | None = None, kind: Literal["movie", "show"] = "movie") -> MediaItemRow:
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


# ---------------------------------------------------------------------------
# Helpers for find_on_disk / find_items_needing_rescrape tests
# ---------------------------------------------------------------------------


def _insert_disk(conn: sqlite3.Connection, mount: str, uuid: str = "disk-uuid-1") -> int:
    """Insert a mounted disk row and return its PK.

    Args:
        conn: Open SQLite connection.
        mount: Mount-path string for the disk.
        uuid: Unique volume UUID string.

    Returns:
        PK of the inserted disk row.
    """
    cursor = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, last_seen_at, is_mounted, unreachable_strikes) "
        "VALUES (?, ?, ?, ?, 1, 0)",
        (uuid, "TestDisk", mount, int(time.time())),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_path(conn: sqlite3.Connection, disk_id: int, rel_path: str) -> int:
    """Insert a path row and return its PK.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the owning disk.
        rel_path: Relative directory path string.

    Returns:
        PK of the inserted path row.
    """
    cursor = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)",
        (disk_id, rel_path),
    )
    return cursor.lastrowid  # type: ignore[return-value]


def _insert_release_and_file(conn: sqlite3.Connection, item_id: int, path_id: int) -> None:
    """Insert a minimal media_release + media_file chain for an item.

    Args:
        conn: Open SQLite connection.
        item_id: PK of the owning media_item.
        path_id: PK of the path row for the file.
    """
    cursor = conn.execute(
        "INSERT INTO media_release (item_id, quality) VALUES (?, '1080p')",
        (item_id,),
    )
    release_id: int = cursor.lastrowid  # type: ignore[assignment]
    conn.execute(
        "INSERT INTO media_file "
        "(release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation, last_verified_at) "
        "VALUES (?, ?, 'video.mkv', 1000000, 1000000000, 'aabbccddeeff0011', 1, ?)",
        (release_id, path_id, int(time.time())),
    )


def _make_item_with_nfo(
    nfo_status: Literal["valid", "invalid", "missing"] | None = None,
    date_metadata_refreshed: int | None = None,
    is_locked: int = 0,
) -> MediaItemRow:
    """Return a MediaItemRow with configurable NFO status and refresh date.

    Args:
        nfo_status: One of ``'valid'``, ``'invalid'``, ``'missing'``, or ``None``.
        date_metadata_refreshed: Unix epoch seconds, or ``None``.
        is_locked: 0 (default) or 1.

    Returns:
        Populated :class:`MediaItemRow` ready for insertion.
    """
    now = int(time.time())
    return MediaItemRow(
        id=0,
        kind="movie",
        title="Test Movie",
        title_sort="Test Movie",
        original_title=None,
        year=2024,
        category_id="movies",
        tmdb_id=None,
        imdb_id=None,
        tvdb_id=None,
        nfo_status=nfo_status,
        artwork_json=None,
        date_created=now,
        date_modified=now,
        date_metadata_refreshed=date_metadata_refreshed,
        is_locked=is_locked,
        preferred_lang="fr",
    )


# ---------------------------------------------------------------------------
# find_on_disk tests
# ---------------------------------------------------------------------------


class TestFindOnDisk:
    """Tests for item_repo.find_on_disk."""

    def test_returns_items_linked_to_disk(self, conn: sqlite3.Connection) -> None:
        """Items with files on the target disk are returned."""
        disk_id = _insert_disk(conn, "/Volumes/Disk1")
        path_id = _insert_path(conn, disk_id, "MOVIES/Movie A (2024)")
        item_id = item_repo.insert(conn, _make_item_with_nfo(nfo_status="valid"))
        _insert_release_and_file(conn, item_id, path_id)

        results = item_repo.find_on_disk(conn, disk_id)

        assert len(results) == 1
        item_row, mount, rel = results[0]
        assert item_row.id == item_id
        assert mount == "/Volumes/Disk1"
        assert rel == "MOVIES/Movie A (2024)"

    def test_does_not_return_items_on_other_disk(self, conn: sqlite3.Connection) -> None:
        """Items whose files reside on a different disk are excluded."""
        disk1_id = _insert_disk(conn, "/Volumes/Disk1", uuid="uuid-1")
        disk2_id = _insert_disk(conn, "/Volumes/Disk2", uuid="uuid-2")
        path1_id = _insert_path(conn, disk1_id, "MOVIES/Movie A (2024)")
        path2_id = _insert_path(conn, disk2_id, "MOVIES/Movie B (2023)")
        item_a = item_repo.insert(conn, _make_item_with_nfo(nfo_status="valid"))
        item_b = item_repo.insert(conn, _make_item_with_nfo(nfo_status="valid"))
        _insert_release_and_file(conn, item_a, path1_id)
        _insert_release_and_file(conn, item_b, path2_id)

        results = item_repo.find_on_disk(conn, disk1_id)

        ids = [r[0].id for r in results]
        assert item_a in ids
        assert item_b not in ids

    def test_empty_result_when_disk_has_no_files(self, conn: sqlite3.Connection) -> None:
        """Returns an empty list when no media_file rows link to the disk."""
        disk_id = _insert_disk(conn, "/Volumes/Disk1")
        # Insert item and path but NO media_file row.
        item_repo.insert(conn, _make_item_with_nfo(nfo_status="valid"))

        results = item_repo.find_on_disk(conn, disk_id)

        assert results == []


# ---------------------------------------------------------------------------
# find_items_needing_rescrape tests
# ---------------------------------------------------------------------------


class TestFindItemsNeedingRescrape:
    """Tests for item_repo.find_items_needing_rescrape."""

    def _setup_item_on_disk(
        self,
        conn: sqlite3.Connection,
        disk_id: int,
        nfo_status: Literal["valid", "invalid", "missing"] | None,
        date_refreshed: int | None = None,
        is_locked: int = 0,
    ) -> int:
        """Insert a media_item with a file on disk_id; return item PK.

        Args:
            conn: Open SQLite connection.
            disk_id: PK of the disk row.
            nfo_status: NFO status string.
            date_refreshed: Optional metadata refresh timestamp.
            is_locked: Whether the item is locked.

        Returns:
            PK of the inserted media_item.
        """
        rel = f"MOVIES/Item-{nfo_status}-{date_refreshed}"
        path_id = _insert_path(conn, disk_id, rel)
        item_id = item_repo.insert(
            conn,
            _make_item_with_nfo(
                nfo_status=nfo_status,
                date_metadata_refreshed=date_refreshed,
                is_locked=is_locked,
            ),
        )
        _insert_release_and_file(conn, item_id, path_id)
        return item_id

    def test_returns_item_with_invalid_nfo(self, conn: sqlite3.Connection) -> None:
        """Items with nfo_status='invalid' are returned."""
        disk_id = _insert_disk(conn, "/Volumes/Disk1")
        item_id = self._setup_item_on_disk(conn, disk_id, nfo_status="invalid")

        results = item_repo.find_items_needing_rescrape(conn)

        ids = [r[0].id for r in results]
        assert item_id in ids

    def test_returns_item_with_missing_nfo(self, conn: sqlite3.Connection) -> None:
        """Items with nfo_status='missing' are returned."""
        disk_id = _insert_disk(conn, "/Volumes/Disk1")
        item_id = self._setup_item_on_disk(conn, disk_id, nfo_status="missing")

        results = item_repo.find_items_needing_rescrape(conn)

        ids = [r[0].id for r in results]
        assert item_id in ids

    def test_returns_item_with_null_refresh_date(self, conn: sqlite3.Connection) -> None:
        """Items with date_metadata_refreshed=NULL are returned even if nfo='valid'."""
        disk_id = _insert_disk(conn, "/Volumes/Disk1")
        # nfo_status='valid' but never refreshed — must still appear
        item_id = self._setup_item_on_disk(conn, disk_id, nfo_status="valid", date_refreshed=None)

        results = item_repo.find_items_needing_rescrape(conn)

        ids = [r[0].id for r in results]
        assert item_id in ids

    def test_excludes_valid_and_refreshed_item(self, conn: sqlite3.Connection) -> None:
        """Items with nfo_status='valid' AND a refresh date are excluded."""
        disk_id = _insert_disk(conn, "/Volumes/Disk1")
        item_id = self._setup_item_on_disk(conn, disk_id, nfo_status="valid", date_refreshed=int(time.time()))

        results = item_repo.find_items_needing_rescrape(conn)

        ids = [r[0].id for r in results]
        assert item_id not in ids

    def test_excludes_locked_items(self, conn: sqlite3.Connection) -> None:
        """Locked items (is_locked=1) are excluded regardless of NFO status."""
        disk_id = _insert_disk(conn, "/Volumes/Disk1")
        item_id = self._setup_item_on_disk(conn, disk_id, nfo_status="invalid", is_locked=1)

        results = item_repo.find_items_needing_rescrape(conn)

        ids = [r[0].id for r in results]
        assert item_id not in ids

    def test_result_includes_mount_path_and_rel_path(self, conn: sqlite3.Connection) -> None:
        """Each result triple includes the correct mount and rel path."""
        disk_id = _insert_disk(conn, "/Volumes/Disk1")
        self._setup_item_on_disk(conn, disk_id, nfo_status="missing")

        results = item_repo.find_items_needing_rescrape(conn)

        assert len(results) == 1
        _, mount, rel = results[0]
        assert mount == "/Volumes/Disk1"
        assert "MOVIES" in rel

"""Repo-specific tests for file_repo: lookup, soft-delete, miss-strike increment.

Focuses on behaviors not covered by the round-trip tests in test_schema.py:
- find_by_path_and_filename lookup
- soft_delete sets deleted_at timestamp
- increment_miss_strike advances the counter (0 → 1 → 2)
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo, file_repo, item_repo, release_repo
from personalscraper.indexer.schema import (
    DiskRow,
    MediaFileRow,
    MediaItemRow,
    MediaReleaseRow,
    PathRow,
)

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


def _seed_path(c: sqlite3.Connection) -> int:
    """Insert minimal disk + path rows and return the path id.

    Args:
        c: Open SQLite connection.

    Returns:
        The rowid of the inserted path row.
    """
    now = int(time.time())
    disk_id = disk_repo.insert(
        c,
        DiskRow(
            id=0,
            uuid="file-test-disk-uuid",
            label="FileDisk",
            mount_path="/mnt/FileDisk",
            last_seen_at=now,
            merkle_root=None,
            is_mounted=1,
            unreachable_strikes=0,
        ),
    )
    path_id = disk_repo.insert_path(
        c,
        PathRow(id=0, disk_id=disk_id, rel_path="001-MOVIES/TestMovie", dir_mtime_ns=None, last_walked_at=None),
    )
    return path_id


def _seed_release(c: sqlite3.Connection) -> int:
    """Insert minimal media_item + media_release rows and return the release id.

    Args:
        c: Open SQLite connection.

    Returns:
        The rowid of the inserted media_release row.
    """
    now = int(time.time())
    item_id = item_repo.insert(
        c,
        MediaItemRow(
            id=0,
            kind="movie",
            title="Test Movie",
            title_sort="Test Movie",
            original_title=None,
            year=2024,
            category_id="movies",
            external_ids_json="{}",
            ratings_json=None,
            canonical_provider=None,
            nfo_status=None,
            artwork_json=None,
            date_created=now,
            date_modified=now,
            date_metadata_refreshed=None,
            is_locked=0,
            preferred_lang="en",
        ),
    )
    release_id = release_repo.insert(
        c,
        MediaReleaseRow(
            id=0,
            item_id=item_id,
            episode_id=None,
            quality=None,
            edition=None,
            primary_lang=None,
        ),
    )
    return release_id


def _make_file(path_id: int, release_id: int, filename: str = "movie.mkv") -> MediaFileRow:
    """Return a minimal MediaFileRow linked to the given path and release.

    Args:
        path_id: FK referencing the path row.
        release_id: FK referencing the media_release row.
        filename: Bare filename for the file row.

    Returns:
        Populated :class:`MediaFileRow` ready for insertion.
    """
    now = int(time.time())
    return MediaFileRow(
        id=0,
        release_id=release_id,
        path_id=path_id,
        filename=filename,
        size_bytes=1_500_000_000,
        mtime_ns=now * 1_000_000_000,
        ctime_ns=now * 1_000_000_000,
        # oshash and last_verified_at are NOT NULL in the schema.
        oshash="aabbccddeeff0011",
        xxh3_partial=None,
        xxh3_full=None,
        scan_generation=1,
        last_verified_at=now,
        enriched_at=None,
        miss_strikes=0,
        deleted_at=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_insert_file_returns_rowid(conn: sqlite3.Connection) -> None:
    """Insert returns a positive rowid on success."""
    path_id = _seed_path(conn)
    release_id = _seed_release(conn)
    rowid = file_repo.insert(conn, _make_file(path_id, release_id))
    assert isinstance(rowid, int)
    assert rowid > 0


def test_find_by_path_and_filename_returns_row(conn: sqlite3.Connection) -> None:
    """find_by_path_and_filename returns the matching file row."""
    path_id = _seed_path(conn)
    release_id = _seed_release(conn)
    file_repo.insert(conn, _make_file(path_id, release_id, filename="feature.mkv"))

    row = file_repo.find_by_path_and_filename(conn, path_id, "feature.mkv")
    assert row is not None
    assert row.filename == "feature.mkv"
    assert row.path_id == path_id


def test_find_by_path_and_filename_returns_none_for_wrong_filename(conn: sqlite3.Connection) -> None:
    """find_by_path_and_filename returns None when the filename does not match."""
    path_id = _seed_path(conn)
    release_id = _seed_release(conn)
    file_repo.insert(conn, _make_file(path_id, release_id, filename="real.mkv"))

    result = file_repo.find_by_path_and_filename(conn, path_id, "other.mkv")
    assert result is None


def test_soft_delete_sets_deleted_at(conn: sqlite3.Connection) -> None:
    """soft_delete writes the deleted_at timestamp; the row remains in the table."""
    path_id = _seed_path(conn)
    release_id = _seed_release(conn)
    file_id = file_repo.insert(conn, _make_file(path_id, release_id))

    ts = int(time.time())
    updated = file_repo.soft_delete(conn, file_id, ts)
    assert updated is True

    row = file_repo.get_by_id(conn, file_id)
    assert row is not None
    assert row.deleted_at == ts


def test_soft_delete_returns_false_for_nonexistent_id(conn: sqlite3.Connection) -> None:
    """soft_delete returns False when the id does not exist."""
    result = file_repo.soft_delete(conn, 9999, int(time.time()))
    assert result is False


def test_increment_miss_strike_advances_counter(conn: sqlite3.Connection) -> None:
    """increment_miss_strike increments miss_strikes: 0 → 1 → 2."""
    path_id = _seed_path(conn)
    release_id = _seed_release(conn)
    file_id = file_repo.insert(conn, _make_file(path_id, release_id))

    # Initial value
    row = file_repo.get_by_id(conn, file_id)
    assert row is not None
    assert row.miss_strikes == 0

    # First increment
    file_repo.increment_miss_strike(conn, file_id)
    row = file_repo.get_by_id(conn, file_id)
    assert row is not None
    assert row.miss_strikes == 1

    # Second increment
    file_repo.increment_miss_strike(conn, file_id)
    row = file_repo.get_by_id(conn, file_id)
    assert row is not None
    assert row.miss_strikes == 2


def test_increment_miss_strike_returns_false_for_nonexistent_id(conn: sqlite3.Connection) -> None:
    """increment_miss_strike returns False when the id does not exist."""
    result = file_repo.increment_miss_strike(conn, 9999)
    assert result is False

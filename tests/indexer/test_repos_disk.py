"""Repo-specific tests for disk_repo: update operations and get_by_uuid.

Focuses on behaviors not covered by the round-trip tests in test_schema.py:
- get_by_uuid lookup
- update_mount_path (sets is_mounted implicitly)
- update_is_mounted
- update_merkle_root
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.schema import DiskRow

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


def _make_disk(uuid: str = "abc-def-123") -> DiskRow:
    """Return a minimal DiskRow with the given UUID.

    Args:
        uuid: Volume UUID string.

    Returns:
        Populated :class:`DiskRow` ready for insertion.
    """
    return DiskRow(
        id=0,
        uuid=uuid,
        label="TestDisk",
        mount_path="/mnt/TestDisk",
        last_seen_at=int(time.time()),
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_insert_disk_returns_rowid(conn: sqlite3.Connection) -> None:
    """Insert returns a positive rowid on success."""
    rowid = disk_repo.insert(conn, _make_disk())
    assert isinstance(rowid, int)
    assert rowid > 0


def test_get_by_uuid_finds_inserted_row(conn: sqlite3.Connection) -> None:
    """get_by_uuid returns the DiskRow matching the UUID."""
    disk_repo.insert(conn, _make_disk(uuid="unique-uuid-1"))
    row = disk_repo.get_by_uuid(conn, "unique-uuid-1")
    assert row is not None
    assert row.uuid == "unique-uuid-1"
    assert row.label == "TestDisk"


def test_get_by_uuid_returns_none_for_missing(conn: sqlite3.Connection) -> None:
    """get_by_uuid returns None when the UUID is not present."""
    result = disk_repo.get_by_uuid(conn, "does-not-exist")
    assert result is None


def test_update_mount_path_changes_path_and_is_mounted(conn: sqlite3.Connection) -> None:
    """update_mount_path updates mount_path and flips is_mounted accordingly."""
    disk_id = disk_repo.insert(conn, _make_disk())

    # Update to a new path → should mark as mounted
    updated = disk_repo.update_mount_path(conn, disk_id, "/mnt/NewPath")
    assert updated is True
    row = disk_repo.get_by_id(conn, disk_id)
    assert row is not None
    assert row.mount_path == "/mnt/NewPath"
    assert row.is_mounted == 1

    # Update to None → should mark as unmounted
    updated = disk_repo.update_mount_path(conn, disk_id, None)
    assert updated is True
    row = disk_repo.get_by_id(conn, disk_id)
    assert row is not None
    assert row.mount_path is None
    assert row.is_mounted == 0


def test_update_mount_path_returns_false_for_nonexistent_id(conn: sqlite3.Connection) -> None:
    """update_mount_path returns False when the id does not exist."""
    result = disk_repo.update_mount_path(conn, 9999, "/mnt/Nowhere")
    assert result is False


def test_update_is_mounted_toggles_flag(conn: sqlite3.Connection) -> None:
    """update_is_mounted(0) clears is_mounted and auto-nulls mount_path.

    The schema enforces (is_mounted=0 AND mount_path IS NULL) OR
    (is_mounted=1 AND mount_path IS NOT NULL).  Setting is_mounted=0 must
    therefore clear mount_path atomically.  Re-mounting is done via
    update_mount_path, which sets both fields together.
    """
    disk_id = disk_repo.insert(conn, _make_disk())

    # Mark as unmounted — mount_path must be cleared automatically.
    disk_repo.update_is_mounted(conn, disk_id, 0)
    row = disk_repo.get_by_id(conn, disk_id)
    assert row is not None
    assert row.is_mounted == 0
    assert row.mount_path is None  # auto-cleared by update_is_mounted(0)

    # Restore via update_mount_path (the canonical way to mark a disk as mounted).
    disk_repo.update_mount_path(conn, disk_id, "/mnt/TestDisk")
    row = disk_repo.get_by_id(conn, disk_id)
    assert row is not None
    assert row.is_mounted == 1
    assert row.mount_path == "/mnt/TestDisk"


def test_update_is_mounted_returns_false_for_nonexistent_id(conn: sqlite3.Connection) -> None:
    """update_is_mounted returns False when the id does not exist."""
    result = disk_repo.update_is_mounted(conn, 9999, 0)
    assert result is False


def test_update_merkle_root_sets_value(conn: sqlite3.Connection) -> None:
    """update_merkle_root writes the given hex string and clears it with None."""
    disk_id = disk_repo.insert(conn, _make_disk())

    updated = disk_repo.update_merkle_root(conn, disk_id, "deadbeef01234567")
    assert updated is True
    row = disk_repo.get_by_id(conn, disk_id)
    assert row is not None
    assert row.merkle_root == "deadbeef01234567"

    # Clearing the merkle_root
    disk_repo.update_merkle_root(conn, disk_id, None)
    row = disk_repo.get_by_id(conn, disk_id)
    assert row is not None
    assert row.merkle_root is None


def test_update_merkle_root_returns_false_for_nonexistent_id(conn: sqlite3.Connection) -> None:
    """update_merkle_root returns False when the id does not exist."""
    result = disk_repo.update_merkle_root(conn, 9999, "abc123")
    assert result is False

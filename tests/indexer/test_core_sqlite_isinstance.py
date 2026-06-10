"""Regression test: IndexerXxxError subclasses core Sqlite markers (RP3 Phase 1)."""

from __future__ import annotations

from personalscraper.core.sqlite.errors import (
    SqliteCorruptError,
    SqliteDiskFullError,
    SqliteFKOrphansError,
    SqliteInvalidPathError,
    SqliteLockError,
    SqliteMigrationError,
)
from personalscraper.indexer.db import (
    IndexerCorruptError,
    IndexerDiskFullError,
    IndexerFKOrphansError,
    IndexerInvalidPathError,
    IndexerLockError,
    IndexerMigrationError,
)


def test_indexer_lock_error_is_sqlite_lock_error() -> None:
    """IndexerLockError(pid=42) is a SqliteLockError."""
    err = IndexerLockError(pid=42)
    assert isinstance(err, SqliteLockError)
    assert err.pid == 42


def test_indexer_corrupt_error_is_sqlite_corrupt_error(tmp_path) -> None:
    """IndexerCorruptError is a SqliteCorruptError."""
    err = IndexerCorruptError(db_path=tmp_path / "a.db", quarantine_path=tmp_path / "a.db.bak")
    assert isinstance(err, SqliteCorruptError)


def test_indexer_diskfull_error_is_sqlite_diskfull_error(tmp_path) -> None:
    """IndexerDiskFullError is a SqliteDiskFullError."""
    err = IndexerDiskFullError(path=tmp_path / "a.db", free_bytes=100, required_bytes=500)
    assert isinstance(err, SqliteDiskFullError)


def test_indexer_invalid_path_error_is_sqlite_invalid_path_error(tmp_path) -> None:
    """IndexerInvalidPathError is a SqliteInvalidPathError."""
    err = IndexerInvalidPathError(db_path=tmp_path / "a.db", mount_point="/Volumes/ext")
    assert isinstance(err, SqliteInvalidPathError)


def test_indexer_fkorphans_error_is_sqlite_fkorphans_error(tmp_path) -> None:
    """IndexerFKOrphansError is a SqliteFKOrphansError."""
    # REAL constructor: (db_path: Path, orphan_count: int, sample=None)
    err = IndexerFKOrphansError(db_path=tmp_path / "a.db", orphan_count=3)
    assert isinstance(err, SqliteFKOrphansError)
    assert err.orphan_count == 3


def test_indexer_migration_error_is_sqlite_migration_error(tmp_path) -> None:
    """IndexerMigrationError is a SqliteMigrationError."""
    err = IndexerMigrationError(version=2)
    assert isinstance(err, SqliteMigrationError)

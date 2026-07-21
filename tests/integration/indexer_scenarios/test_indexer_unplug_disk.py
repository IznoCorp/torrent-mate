"""E2E test: unplugged disk does not increment miss_strikes or soft-delete rows.

DESIGN §3.5 — Per-disk circuit breaker and I/O error handling.

When a disk appears unmounted (guard_disk_mounted raises DiskUnmountedError),
the scanner must:

- Log ``indexer.disk.skipped_unmounted`` at WARNING level.
- NOT increment ``miss_strikes`` on any existing ``media_file`` rows for that
  disk (drift is frozen for unmounted disks).
- NOT set ``deleted_at`` on any existing rows (no soft-delete).

This test verifies the entire lifecycle:
1. Seed the DB with a disk and several media_file rows (simulating a previous
   scan where the disk was mounted).
2. Mock ``guard_disk_mounted`` to raise ``DiskUnmountedError`` (disk unplugged).
3. Run ``scan()`` against the same disk.
4. Assert: no new ``media_file`` rows inserted, no ``miss_strikes`` increment,
   no ``deleted_at`` set, ``indexer.disk.skipped_unmounted`` event in caplog.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.merkle import DiskUnmountedError
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied.

    Returns:
        Open :class:`sqlite3.Connection` with FK enforcement and migrations.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, label: str, mount_path: str) -> DiskRow:
    """Insert a minimal disk row and return the populated :class:`DiskRow`.

    Args:
        conn: Open SQLite connection.
        label: Human-readable disk label.
        mount_path: Absolute path of the disk mount point.

    Returns:
        :class:`DiskRow` with the PK assigned by SQLite.
    """
    now = int(time.time())
    row = DiskRow(
        id=0,
        uuid=f"test-uuid-{label}",
        label=label,
        mount_path=mount_path,
        last_seen_at=now,
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    disk_id = disk_repo.insert(conn, row)
    return DiskRow(
        id=disk_id,
        uuid=row.uuid,
        label=row.label,
        mount_path=row.mount_path,
        last_seen_at=row.last_seen_at,
        merkle_root=row.merkle_root,
        is_mounted=row.is_mounted,
        unreachable_strikes=row.unreachable_strikes,
    )


def _seed_media_file(
    conn: sqlite3.Connection,
    disk_id: int,
    rel_path: str,
    filename: str,
) -> int:
    """Seed a ``path`` and ``media_file`` row; return the media_file PK.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the owning disk.
        rel_path: Relative directory path (no leading slash).
        filename: Bare filename.

    Returns:
        PK of the inserted ``media_file`` row.
    """
    path_cur = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)",
        (disk_id, rel_path),
    )
    path_id: int = path_cur.lastrowid  # type: ignore[assignment]
    now_s = int(time.time())
    file_cur = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (NULL, ?, ?, 100, 1000000000, NULL,
                  NULL, NULL, NULL, 1,
                  ?, NULL, 0, NULL)
        """,
        (path_id, filename, now_s),
    )
    file_id: int = file_cur.lastrowid  # type: ignore[assignment]
    conn.commit()
    return file_id


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestUnpluggedDiskNoStrike:
    """Unplugged disk: scan skips it without touching existing media_file rows."""

    def test_unplugged_disk_no_strike(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Scan with disk unplugged: no strike, no soft-delete, skipped_unmounted logged.

        Scenario:
        1. Seed DB: one disk, two media_file rows at scan_generation=1.
        2. Mock guard_disk_mounted to raise DiskUnmountedError (disk is gone).
        3. Run scan() in full mode at generation=2.
        4. Assert:
           - No new media_file rows inserted (count still == 2).
           - miss_strikes unchanged (still 0) for all rows.
           - deleted_at still NULL for all rows.
           - ``indexer.disk.skipped_unmounted`` WARNING is in caplog.
        """
        conn = _open_db()

        mount = str(tmp_path / "DiskC")

        disk = _insert_disk(conn, "DiskC", mount)

        file_id_1 = _seed_media_file(conn, disk.id, "movies/Alien (1979)", "Alien.mkv")
        file_id_2 = _seed_media_file(conn, disk.id, "movies/Aliens (1986)", "Aliens.mkv")

        # Disk is now "unplugged" — guard raises DiskUnmountedError.
        with (
            caplog.at_level(logging.WARNING, logger="indexer.disk"),
            patch(_GUARD_PATCH, side_effect=DiskUnmountedError(disk.uuid)),
        ):
            result = scan(
                [disk],
                mode=ScanMode.full,
                generation=2,
                conn=conn,
                event_bus=EventBus(),
            )

        # Scan must complete cleanly (not 'failed').
        assert result.status == "ok", f"Expected status='ok', got {result.status!r}"

        # No files indexed this run (disk was skipped).
        assert result.files_visited == 0, f"Expected 0 files_visited, got {result.files_visited}"

        # Row count must not have changed.
        count = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
        assert count == 2, f"Expected 2 media_file rows (unchanged), got {count}"

        # miss_strikes must be 0 for both seeded files — drift is frozen for
        # unmounted disks; the scanner must NOT call mark_missed_files.
        for fid in (file_id_1, file_id_2):
            row = conn.execute(
                "SELECT miss_strikes, deleted_at FROM media_file WHERE id = ?",
                (fid,),
            ).fetchone()
            assert row is not None
            miss_strikes, deleted_at = row
            assert miss_strikes == 0, f"File {fid}: miss_strikes must stay 0 on unmounted scan, got {miss_strikes}"
            assert deleted_at is None, f"File {fid}: deleted_at must remain NULL on unmounted scan, got {deleted_at}"

        # The skipped_unmounted event must have been logged.
        warning_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("skipped_unmounted" in t for t in warning_texts), (
            f"Expected 'skipped_unmounted' in warning records, got: {warning_texts}"
        )

        conn.close()

"""Integration test: quick-mode paranoia branch detects silent file mutations.

Covers DESIGN §17.1: when a file is mutated without updating the parent
directory mtime (e.g. by the outbox pipeline), the quick-mode paranoia branch
must detect the discrepancy by querying recent ``scan_event`` rows with
``event LIKE 'outbox.%'`` and re-stating the referenced paths.

Test plan:
1. Build a temporary filesystem with a media file.
2. Insert ``disk`` and ``media_file`` rows in the DB.
3. Insert a ``scan_event`` row with ``event='outbox.move'`` for that path.
4. Backdate the stored ``media_file.size_bytes`` to simulate a stale index.
5. Run ``scan()`` in quick mode with paranoia enabled.
6. Assert that ``indexer.scan.paranoia_recheck`` is logged for that path.
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
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite connection to *db_path* with the full schema applied.

    Args:
        db_path: Filesystem path for the database file.

    Returns:
        Open :class:`sqlite3.Connection` with migrations applied and
        foreign-key enforcement enabled.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, mount_path: str) -> DiskRow:
    """Insert a minimal mounted disk row and return the resulting :class:`DiskRow`.

    Args:
        conn: Open SQLite connection.
        mount_path: Absolute path of the fake mount point.

    Returns:
        :class:`DiskRow` with the PK assigned by SQLite.
    """
    row = DiskRow(
        id=0,
        uuid=f"uuid-paranoia-{mount_path[-8:]}",
        label="ParanoiaTestDisk",
        mount_path=mount_path,
        last_seen_at=int(time.time()),
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


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestOutboxParanoiaBranch:
    """Integration-level tests for the quick-mode paranoia branch (DESIGN §17.1)."""

    def test_paranoia_branch_detects_silent_mutation(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Paranoia branch detects a size mismatch caused by a silent file mutation.

        This test exercises the full path from filesystem setup → DB seeding →
        outbox event insertion → quick-mode scan → log assertion, without mocking
        the paranoia branch itself.

        Steps:
        1. Create a file on disk under a temp mount.
        2. Full scan to populate ``media_file`` with the real stat values.
        3. Backdate ``media_file.size_bytes`` to simulate a stale index entry
           (mimics the scanner's last known state before a silent mutation).
        4. Insert a ``scan_event`` row representing an outbox.move event for the file.
        5. Force Merkle miss (set wrong merkle_root) so the Merkle short-circuit
           does not abort the scan before the paranoia branch runs.
        6. Quick scan with ``paranoia_window_seconds=86400``.
        7. Assert ``indexer.scan.paranoia_recheck`` is logged.

        Args:
            tmp_path: Pytest temporary directory (unique per test).
            caplog: pytest log capture fixture.
        """
        # Set up the DB at a real filesystem path so scan() can open connections.
        db_path = tmp_path / "library.db"
        conn = _make_conn(db_path)

        # Set up the fake mount point and media file.
        mount = str(tmp_path / "disk")
        Path(mount).mkdir(parents=True, exist_ok=True)
        media_file = Path(mount) / "movie.mkv"
        media_file.write_bytes(b"A" * 1024)

        # Insert disk row and run a full scan to seed media_file.
        disk = _insert_disk(conn, mount)

        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Verify media_file row was inserted.
        conn.row_factory = sqlite3.Row
        mf_row = conn.execute("SELECT id, size_bytes, mtime_ns FROM media_file WHERE filename = 'movie.mkv'").fetchone()
        assert mf_row is not None, "media_file row must exist after full scan"
        conn.row_factory = None

        # Backdate size_bytes so the paranoia re-stat sees a mismatch — this
        # simulates the scenario where the file was mutated after the last scan
        # but the parent dir mtime was not updated (so dir-mtime walk would skip it).
        conn.execute("UPDATE media_file SET size_bytes = 1 WHERE id = ?", (mf_row["id"],))

        # Insert a scan_run row to satisfy the FK constraint on scan_event.
        scan_run_id = conn.execute(
            "INSERT INTO scan_run (generation, mode, started_at, status) VALUES (1, 'quick', ?, 'running')",
            (int(time.time()),),
        ).lastrowid

        # Insert a fake outbox event for the mutated file (rel_path relative to mount).
        conn.execute(
            "INSERT INTO scan_event (scan_id, ts, event, payload_json) VALUES (?, ?, 'outbox.move', ?)",
            (scan_run_id, int(time.time()), '{"rel_path": "movie.mkv"}'),
        )

        # Force Merkle miss so the paranoia branch actually runs (it only runs on miss).
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot-paranoia")
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None

        # Quick scan with paranoia enabled.
        # confirm_bulk_change=True bypasses the Merkle delta freeze guard so the
        # scan returns 'ok' rather than raising DiskBulkChangeDetected (the wrongroot
        # we stored causes a 100% delta).  The paranoia branch runs BEFORE the
        # bulk-change check so the recheck event is logged regardless.
        with caplog.at_level(logging.INFO):
            with patch(_GUARD_PATCH, return_value=None):
                result = scan(
                    [updated_disk],
                    ScanMode.quick,
                    generation=2,
                    conn=conn,
                    paranoia_window_seconds=86400,
                    confirm_bulk_change=True,
                    event_bus=EventBus(),
                )

        assert result.status == "ok"

        # The paranoia branch must have logged a recheck event for the mutated file.
        # Use full event names to avoid false positives on tmp_path substrings.
        log_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
        assert any("indexer.scan.paranoia_recheck" in t for t in log_texts), (
            "Expected 'indexer.scan.paranoia_recheck' in log records.\nAll INFO+ records:\n"
            + "\n".join(f"  {t}" for t in log_texts)
        )

        # The paranoia_branch summary event must also appear.
        assert any("indexer.scan.paranoia_branch" in t for t in log_texts), (
            "Expected 'indexer.scan.paranoia_branch' summary in log records.\nAll INFO+ records:\n"
            + "\n".join(f"  {t}" for t in log_texts)
        )

    def test_paranoia_branch_skipped_when_window_zero(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When paranoia_window_seconds=0, the paranoia branch is entirely skipped.

        No ``indexer.scan.paranoia_branch`` log event must appear, confirming the
        branch is disabled without a DB query.

        Args:
            tmp_path: Pytest temporary directory.
            caplog: pytest log capture fixture.
        """
        db_path = tmp_path / "library.db"
        conn = _make_conn(db_path)

        mount = str(tmp_path / "disk2")
        Path(mount).mkdir(parents=True, exist_ok=True)
        (Path(mount) / "movie.mkv").write_bytes(b"B" * 512)

        disk = _insert_disk(conn, mount)
        # Force Merkle miss so scan would normally reach the paranoia branch.
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot-disabled")
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None

        with caplog.at_level(logging.INFO):
            with patch(_GUARD_PATCH, return_value=None):
                result = scan(
                    [updated_disk],
                    ScanMode.quick,
                    generation=1,
                    conn=conn,
                    paranoia_window_seconds=0,
                    # Bypass the bulk-change freeze: wrongroot with no stored rows
                    # yields a 100% delta that would otherwise raise DiskBulkChangeDetected.
                    confirm_bulk_change=True,
                    event_bus=EventBus(),
                )

        assert result.status == "ok"

        # paranoia_branch must NOT appear when window=0.
        # Use the full event name to avoid false matches on the tmp_path which
        # contains the test function name as a substring (e.g. "test_paranoia_branch_...").
        log_texts = [r.getMessage() for r in caplog.records]
        assert not any("indexer.scan.paranoia_branch" in t for t in log_texts), (
            "indexer.scan.paranoia_branch must not be logged when window=0, got: "
            + "\n".join(f"  {t}" for t in log_texts if "indexer.scan.paranoia" in t)
        )

    def test_paranoia_branch_no_false_positive_when_file_unchanged(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Paranoia branch does NOT log paranoia_recheck when size and mtime match.

        Inserts an outbox event but keeps the stored ``media_file.size_bytes`` and
        ``mtime_ns`` consistent with the actual on-disk stat so no mismatch is
        detected.

        Args:
            tmp_path: Pytest temporary directory.
            caplog: pytest log capture fixture.
        """
        db_path = tmp_path / "library.db"
        conn = _make_conn(db_path)

        mount = str(tmp_path / "disk3")
        Path(mount).mkdir(parents=True, exist_ok=True)
        (Path(mount) / "movie.mkv").write_bytes(b"C" * 256)

        disk = _insert_disk(conn, mount)

        # Full scan seeds media_file with the CORRECT stat values.
        with patch(_GUARD_PATCH, return_value=None):
            scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

        # Insert outbox event for the file.
        scan_run_id = conn.execute(
            "INSERT INTO scan_run (generation, mode, started_at, status) VALUES (1, 'quick', ?, 'running')",
            (int(time.time()),),
        ).lastrowid
        conn.execute(
            "INSERT INTO scan_event (scan_id, ts, event, payload_json) VALUES (?, ?, 'outbox.move', ?)",
            (scan_run_id, int(time.time()), '{"rel_path": "movie.mkv"}'),
        )

        # Force Merkle miss.
        disk_repo.update_merkle_root(conn, disk.id, "wrongroot-unchanged")
        updated_disk = disk_repo.get_by_id(conn, disk.id)
        assert updated_disk is not None

        with caplog.at_level(logging.INFO):
            with patch(_GUARD_PATCH, return_value=None):
                result = scan(
                    [updated_disk],
                    ScanMode.quick,
                    generation=2,
                    conn=conn,
                    paranoia_window_seconds=86400,
                    # Bypass the bulk-change freeze guard (wrongroot → 100% delta).
                    confirm_bulk_change=True,
                    event_bus=EventBus(),
                )

        assert result.status == "ok"

        # No recheck must be logged when size+mtime_ns match perfectly.
        # Use full event names to avoid false positives on tmp_path substrings.
        log_texts = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO]
        assert not any("indexer.scan.paranoia_recheck" in t for t in log_texts), (
            "indexer.scan.paranoia_recheck must not be logged when file is unchanged, got:\n"
            + "\n".join(f"  {t}" for t in log_texts if "indexer.scan.paranoia_recheck" in t)
        )
        # Branch summary still appears (it ran, just found nothing to recheck).
        assert any("indexer.scan.paranoia_branch" in t for t in log_texts), (
            "indexer.scan.paranoia_branch summary must still be logged even when no paths mismatch"
        )

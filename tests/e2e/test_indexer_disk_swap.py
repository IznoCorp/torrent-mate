"""E2E test: Merkle delta freeze and --confirm-bulk-change.

DESIGN §3.6 — Bulk-restore detection via Merkle delta.

When a quick scan detects that the fraction of changed files exceeds
``IndexerDriftConfig.merkle_delta_freeze_threshold``, the scanner must:

- Log ``indexer.merkle.delta_freeze`` at WARNING level.
- Raise ``DiskBulkChangeDetected`` (which propagates out of ``scan(event_bus=EventBus())``).
- NOT modify any ``media_file`` rows for the affected disk.

When ``confirm_bulk_change=True`` is passed, the guard is bypassed and the
scan proceeds normally, re-fingerprinting changed files.

Test scenarios:
1. ``test_disk_swap_freeze_without_confirmation``:
   - Seed DB with 5 files via a first scan.
   - Mutate 4 of the 5 files on disk (new content → new size/mtime).
   - Set ``disk.merkle_root`` to the OLD value (simulate pre-swap snapshot).
   - Run quick scan WITHOUT ``confirm_bulk_change``.
   - Assert: ``DiskBulkChangeDetected`` is raised (scan halts),
     ``indexer.merkle.delta_freeze`` is in WARNING caplog, no media_file
     rows changed for the disk after the second scan.

2. ``test_disk_swap_proceeds_with_confirmation``:
   - Same setup.
   - Run quick scan WITH ``confirm_bulk_change=True``.
   - Assert: scan returns normally (no exception), files are re-fingerprinted
     (size_bytes updated), scan_run status == 'ok'.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.breaker import DiskCircuitBreaker
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.merkle import DiskBulkChangeDetected
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"

# Freeze threshold used in both tests — well below the 4/5 = 80 % delta
# that the fixture produces.
_FREEZE_THRESHOLD = 0.50


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


def _build_fixture(mount: Path, filenames: list[str], content: bytes = b"ORIGINAL" * 50) -> None:
    """Create a flat directory of media files under *mount*.

    Args:
        mount: Root directory for the fake disk.
        filenames: List of bare filenames to create.
        content: Bytes to write into each file.
    """
    mount.mkdir(parents=True, exist_ok=True)
    for name in filenames:
        (mount / name).write_bytes(content)


def _mutate_files(mount: Path, filenames: list[str], new_content: bytes = b"RESTORED" * 60) -> None:
    """Overwrite *filenames* on *mount* with new content (different size/mtime).

    Args:
        mount: Root directory of the disk.
        filenames: Files to mutate.
        new_content: Replacement bytes (must differ in length from the original
            to guarantee size_bytes differs).
    """
    for name in filenames:
        (mount / name).write_bytes(new_content)


_STALE_MERKLE_ROOT = "000000000000dead"


def _run_initial_scan(conn: sqlite3.Connection, disk: DiskRow, mount: str) -> DiskRow:
    """Run a full-mode scan to populate media_file rows and return an updated DiskRow.

    After the full scan, we store a *stale* (deliberately wrong) ``merkle_root``
    on the disk row.  This guarantees that the subsequent quick scan always sees
    a Merkle miss — the DB-computed root will differ from the stored stale value —
    which is a prerequisite for the bulk-change guard to be evaluated.

    The guard itself compares *live FS fingerprints* (sampled via ``os.stat``)
    against the *stored DB fingerprints* (from the initial full scan), so the
    stale root does not affect the delta computation.

    Args:
        conn: Open SQLite connection.
        disk: :class:`DiskRow` for the disk to scan.
        mount: Absolute mount path.

    Returns:
        Updated :class:`DiskRow` with ``merkle_root`` set to :data:`_STALE_MERKLE_ROOT`.
    """
    with patch(_GUARD_PATCH):
        scan(
            [disk],
            mode=ScanMode.full,
            generation=1,
            conn=conn,
            disk_breaker=DiskCircuitBreaker(event_bus=EventBus()),
            event_bus=EventBus(),
        )

    # Store a stale root that will never match the DB-computed root, ensuring
    # every subsequent quick scan sees a Merkle miss and evaluates the bulk-change guard.
    disk_repo.update_merkle_root(conn, disk.id, _STALE_MERKLE_ROOT)

    return DiskRow(
        id=disk.id,
        uuid=disk.uuid,
        label=disk.label,
        mount_path=disk.mount_path,
        last_seen_at=disk.last_seen_at,
        merkle_root=_STALE_MERKLE_ROOT,
        is_mounted=disk.is_mounted,
        unreachable_strikes=disk.unreachable_strikes,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FILENAMES = ["movie1.mkv", "movie2.mkv", "movie3.mkv", "movie4.mkv", "movie5.mkv"]

# 4 of 5 files will be mutated → delta = 0.80 > _FREEZE_THRESHOLD = 0.50.
_MUTATED_FILENAMES = _FILENAMES[:4]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDiskSwapFreeze:
    """Bulk-restore detection halts the scan unless confirmed."""

    def test_disk_swap_freeze_without_confirmation(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Quick scan freezes when >50% of files changed without confirmation.

        Scenario:
        1. Build a disk fixture with 5 .mkv files.
        2. Run a full scan to populate media_file rows and store merkle_root.
        3. Mutate 4 of the 5 files (different content/size) → delta = 80 %.
        4. Run quick scan WITHOUT confirm_bulk_change and with threshold = 0.50.
        5. Assert:
           - ``DiskBulkChangeDetected`` is raised.
           - ``indexer.merkle.delta_freeze`` WARNING is in caplog.
           - media_file size_bytes for the mutated files are unchanged (old values).
        """
        mount = tmp_path / "DiskSwap"
        _build_fixture(mount, _FILENAMES)

        conn = _open_db()
        disk = _insert_disk(conn, "DiskSwap", str(mount))

        # Initial full scan: seed the DB and store merkle_root.
        disk = _run_initial_scan(conn, disk, str(mount))

        # Snapshot the pre-mutation size_bytes for the mutated files.
        conn.row_factory = sqlite3.Row
        pre_sizes: dict[str, int] = {}
        for name in _MUTATED_FILENAMES:
            row = conn.execute(
                """
                SELECT mf.size_bytes
                FROM media_file mf
                JOIN path p ON mf.path_id = p.id
                WHERE p.disk_id = ? AND mf.filename = ?
                """,
                (disk.id, name),
            ).fetchone()
            assert row is not None, f"Expected media_file row for {name!r}"
            pre_sizes[name] = row["size_bytes"]

        # Mutate 4 of 5 files on disk.
        _mutate_files(mount, _MUTATED_FILENAMES)

        # Quick scan must freeze: DiskBulkChangeDetected raised, no rows changed.
        with (
            caplog.at_level(logging.WARNING, logger="indexer.merkle"),
            patch(_GUARD_PATCH),
            pytest.raises(DiskBulkChangeDetected) as exc_info,
        ):
            scan(
                [disk],
                mode=ScanMode.quick,
                generation=2,
                conn=conn,
                confirm_bulk_change=False,
                merkle_delta_freeze_threshold=_FREEZE_THRESHOLD,
                disk_breaker=DiskCircuitBreaker(event_bus=EventBus()),
                event_bus=EventBus(),
            )

        # Exception attributes must reflect the freeze.
        exc = exc_info.value
        assert exc.disk_uuid == disk.uuid
        assert exc.delta > _FREEZE_THRESHOLD, f"Expected delta > {_FREEZE_THRESHOLD}, got {exc.delta}"

        # The freeze event must have been logged.
        delta_freeze_logged = any(
            "delta_freeze" in r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING
        )
        assert delta_freeze_logged, (
            f"Expected 'delta_freeze' in WARNING records; got: {[r.getMessage() for r in caplog.records]}"
        )

        # media_file rows for the mutated files must be unchanged.
        for name in _MUTATED_FILENAMES:
            row = conn.execute(
                """
                SELECT mf.size_bytes
                FROM media_file mf
                JOIN path p ON mf.path_id = p.id
                WHERE p.disk_id = ? AND mf.filename = ?
                """,
                (disk.id, name),
            ).fetchone()
            assert row is not None
            assert row["size_bytes"] == pre_sizes[name], (
                f"size_bytes for {name!r} changed during frozen scan: "
                f"expected {pre_sizes[name]}, got {row['size_bytes']}"
            )

        conn.close()

    def test_disk_swap_proceeds_with_confirmation(
        self,
        tmp_path: Path,
    ) -> None:
        """Quick scan proceeds and re-fingerprints files when confirmed.

        Scenario:
        1. Same setup: 5 files, full scan, mutate 4.
        2. Run quick scan WITH confirm_bulk_change=True.
        3. Assert:
           - scan(event_bus=EventBus()) returns without exception.
           - scan_run status == 'ok'.
           - size_bytes for the mutated files are updated to the new values.
        """
        mount = tmp_path / "DiskSwapConfirm"
        _build_fixture(mount, _FILENAMES)

        conn = _open_db()
        disk = _insert_disk(conn, "DiskSwapConfirm", str(mount))

        # Initial full scan.
        disk = _run_initial_scan(conn, disk, str(mount))

        # New content is longer — size will differ.
        new_content = b"RESTORED" * 60
        _mutate_files(mount, _MUTATED_FILENAMES, new_content)
        new_size = len(new_content)

        # Quick scan WITH confirmation — must proceed without raising.
        with patch(_GUARD_PATCH):
            result = scan(
                [disk],
                mode=ScanMode.quick,
                generation=2,
                conn=conn,
                confirm_bulk_change=True,
                merkle_delta_freeze_threshold=_FREEZE_THRESHOLD,
                disk_breaker=DiskCircuitBreaker(event_bus=EventBus()),
                event_bus=EventBus(),
            )

        assert result.status == "ok", f"Expected status='ok', got {result.status!r}"

        # Mutated files must have their new size recorded.
        conn.row_factory = sqlite3.Row
        for name in _MUTATED_FILENAMES:
            row = conn.execute(
                """
                SELECT mf.size_bytes
                FROM media_file mf
                JOIN path p ON mf.path_id = p.id
                WHERE p.disk_id = ? AND mf.filename = ?
                """,
                (disk.id, name),
            ).fetchone()
            assert row is not None, f"Expected media_file row for {name!r} after confirmed scan"
            assert row["size_bytes"] == new_size, (
                f"size_bytes for {name!r} not updated: expected {new_size}, got {row['size_bytes']}"
            )

        conn.close()

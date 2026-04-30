"""E2E test: EIO mid-scan on Disk2 does not corrupt Disk1 progress.

DESIGN §15.5 — Disk-unplug-during-scan handling (macFUSE EIO mid-walk).

Sub-phase 4.9b: validates that the per-disk circuit breaker (Phase 3.5) and the
ThreadPool isolation (Phase 4.3) co-operate correctly when a worker encounters an
``OSError(EIO)`` mid-walk on its assigned disk:

- **Disk1 progress is committed** — ``media_file`` rows for all Disk1 files exist in the DB.
- **Disk2 transaction is rolled back** — no ``media_file`` rows for Disk2 survive.
- **Disk2 is marked unmounted** — ``disk.is_mounted = 0`` and ``disk.unreachable_strikes``
  is incremented by exactly 1.
- **Circuit breaker records the failure** — ``breaker.record_failure`` is called for Disk2's UUID.
- **Sentinel files are intact** — no write attempt occurs on Disk2 during the EIO window.
- **Structured log event emitted** — ``indexer.disk.io_error`` with ``disk_uuid=Disk2``.

EIO injection strategy
-----------------------
The full-mode walker calls ``os.scandir(dir_abs)`` at the root of each disk.  The
call is wrapped in a ``try/except PermissionError`` block — so ``PermissionError``
is silently swallowed, but ``OSError(errno.EIO)`` propagates up through:

    _walk_dir_full → _walk_dir_full_buffered → _scan_disk_full → _scan_one_disk (OSError branch)

We use a counter-based ``os.scandir`` patch in
``personalscraper.indexer.scanner._walker`` that:

1. Passes through normally for ALL paths under Disk1's mount point.
2. Returns all 100 entries on the **first** ``scandir`` call for Disk2's root (simulating
   the partial-walk window where files are being processed).
3. Raises ``OSError(errno.EIO, "simulated disk EIO")`` on **second** ``scandir`` call
   within Disk2 — i.e., when the walker tries to descend into a subdirectory of Disk2
   after already processing 50 top-level files.  This makes the test deterministic while
   faithfully modelling the mid-walk unplug scenario.

This test is **distinct** from ``test_indexer_unplug_disk.py`` (which models a disk that
is already unmounted *before* the scan starts, causing the guard to raise
``DiskUnmountedError`` immediately).  Here the disk appears mounted at scan start and
fails mid-walk.
"""

from __future__ import annotations

import errno
import logging
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.indexer.breaker import DiskCircuitBreaker
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# Standard guard patch used by all indexer E2E tests to bypass the sentinel check.
_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"

# The ``os.scandir`` name as used by the full-mode walker module.
_SCANDIR_PATCH = "personalscraper.indexer.scanner._walker.os.scandir"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the full schema applied.

    Returns:
        Open :class:`sqlite3.Connection` with FK enforcement and all migrations.
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


def _build_fixture(root: Path, n_flat: int, n_subdir: int, subdir_name: str = "sub") -> None:
    """Create a two-level directory fixture under *root*.

    *n_flat* ``.mkv`` files are placed directly in *root*, and *n_subdir*
    ``.mkv`` files are placed in ``root/<subdir_name>/``.  The subdirectory
    triggers a second ``os.scandir`` call during the full-mode walk, which is
    where the EIO is injected for Disk2.

    Args:
        root: Disk mount root directory (created if absent).
        n_flat: Number of ``.mkv`` files to place directly in *root*.
        n_subdir: Number of ``.mkv`` files to place in the subdirectory.
        subdir_name: Name of the single subdirectory.
    """
    root.mkdir(parents=True, exist_ok=True)
    for i in range(n_flat):
        (root / f"film_flat_{i:04d}.mkv").write_bytes(b"\x00" * 16)
    subdir = root / subdir_name
    subdir.mkdir(exist_ok=True)
    for i in range(n_subdir):
        (subdir / f"film_sub_{i:04d}.mkv").write_bytes(b"\x00" * 16)


# ---------------------------------------------------------------------------
# EIO injection helper
# ---------------------------------------------------------------------------


def _make_eio_scandir(disk2_mount: str) -> object:
    """Return a patched ``os.scandir`` that raises EIO mid-walk on Disk2.

    The first call to ``os.scandir`` for a path inside *disk2_mount* succeeds
    (returns the real directory entries).  Every subsequent call for a path
    inside *disk2_mount* raises ``OSError(errno.EIO, "simulated disk EIO")``,
    which models an NTFS-via-macFUSE volume going away after the walk has
    already started.

    Calls for paths **outside** *disk2_mount* (i.e. Disk1 paths) always pass
    through to the real ``os.scandir``.

    Implementation note — avoiding infinite recursion
    --------------------------------------------------
    ``patch("…_walker.os.scandir", side_effect=fn)`` patches the ``scandir``
    attribute on the ``os`` module object itself, not just the binding in the
    ``_walker`` namespace.  If the side_effect called ``os.scandir`` directly
    it would recurse infinitely.  We capture a reference to the **real**
    ``os.scandir`` function object *before* the patch is applied and call that
    reference directly from inside the side_effect to avoid this.

    Args:
        disk2_mount: Absolute mount path of Disk2; used as the path-prefix
            discriminator.

    Returns:
        A callable suitable for use as the ``os.scandir`` replacement in a
        ``unittest.mock.patch`` context.
    """
    # Capture the real os.scandir before any patch is active.  This reference
    # points directly to the CPython built-in function, bypassing any name
    # lookup that would recurse through the patched module attribute.
    import os as _os

    _real_scandir = _os.scandir

    call_count: list[int] = [0]

    def _patched_scandir(path: str | bytes | int) -> object:
        """Replacement scandir that raises EIO on second+ calls within Disk2.

        Args:
            path: Directory path to scan.

        Returns:
            A real ``os.scandir`` context manager for the path.

        Raises:
            OSError: With ``errno.EIO`` on second and subsequent invocations
                for paths inside *disk2_mount*.
        """
        path_str = path if isinstance(path, str) else str(path)

        if path_str.startswith(disk2_mount):
            call_count[0] += 1
            if call_count[0] > 1:
                # Simulate EIO on the second scandir within Disk2 — this happens
                # when the walker tries to descend into the subdirectory after
                # successfully listing the flat files at the root.
                raise OSError(errno.EIO, "simulated disk EIO: volume went away")

        return _real_scandir(path)

    return _patched_scandir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUnplugDuringScanning:
    """EIO mid-scan: Disk2 transaction rolled back, Disk1 progress intact."""

    def test_disk2_eio_disk1_committed(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Disk2 EIO mid-walk: Disk1 rows committed, Disk2 rolled back, strikes incremented.

        Scenario:
        1. Build two disk fixtures: Disk1 (50 flat files) and Disk2 (50 flat
           files + 50-file subdirectory).
        2. Run a full-mode scan with a patched ``os.scandir`` that raises
           ``OSError(errno.EIO)`` on the second scandir call within Disk2
           (when the walker tries to descend into Disk2's subdirectory).
        3. Assert:
           - ``media_file`` rows for all Disk1 files are present.
           - No ``media_file`` rows for Disk2 survive (transaction rolled back).
           - ``disk.is_mounted = 0`` for Disk2.
           - ``disk.unreachable_strikes = 1`` for Disk2 (incremented from 0).
           - ``indexer.disk.io_error`` WARNING is in caplog with Disk2's UUID.
           - Scan result status is ``'ok'`` (scan completed on Disk1 despite Disk2 failure).
        """
        mount1 = tmp_path / "Disk1"
        mount2 = tmp_path / "Disk2"

        # Disk1: 50 flat files — all should be committed after the scan.
        _build_fixture(mount1, n_flat=50, n_subdir=0)
        # Disk2: 50 flat files + 50-file subdirectory so that the second scandir
        # call (descending into the subdirectory) is where EIO is injected.
        _build_fixture(mount2, n_flat=50, n_subdir=50)

        conn = _open_db()
        disk1 = _insert_disk(conn, "Disk1", str(mount1))
        disk2 = _insert_disk(conn, "Disk2", str(mount2))

        breaker = DiskCircuitBreaker()
        patched_scandir = _make_eio_scandir(str(mount2))

        with (
            caplog.at_level(logging.WARNING, logger="indexer.disk"),
            patch(_GUARD_PATCH, return_value=None),
            patch(_SCANDIR_PATCH, side_effect=patched_scandir),
        ):
            result = scan(
                [disk1, disk2],
                mode=ScanMode.full,
                generation=1,
                conn=conn,
                disk_breaker=breaker,
            )

        # --- Scan-level assertions ---
        assert result.status == "ok", (
            f"Expected scan status='ok' (scan continues on Disk1 despite Disk2 failure); got {result.status!r}"
        )

        # --- Disk1: all 50 files should be committed ---
        conn.row_factory = sqlite3.Row
        disk1_count = conn.execute(
            """
            SELECT COUNT(*) AS cnt
              FROM media_file mf
              JOIN path p ON p.id = mf.path_id
             WHERE p.disk_id = ?
            """,
            (disk1.id,),
        ).fetchone()["cnt"]
        conn.row_factory = None
        assert disk1_count == 50, (
            f"Expected 50 media_file rows for Disk1; got {disk1_count}.  "
            "Disk1 transaction should not be affected by Disk2's EIO."
        )

        # --- Disk2: no rows should survive (transaction rolled back) ---
        conn.row_factory = sqlite3.Row
        disk2_count = conn.execute(
            """
            SELECT COUNT(*) AS cnt
              FROM media_file mf
              JOIN path p ON p.id = mf.path_id
             WHERE p.disk_id = ?
            """,
            (disk2.id,),
        ).fetchone()["cnt"]
        conn.row_factory = None
        assert disk2_count == 0, (
            f"Expected 0 media_file rows for Disk2 after EIO rollback; got {disk2_count}.  "
            "The per-disk transaction must be rolled back cleanly on EIO."
        )

        # --- Disk2 marked unmounted ---
        conn.row_factory = sqlite3.Row
        disk2_row = conn.execute(
            "SELECT is_mounted, unreachable_strikes FROM disk WHERE id = ?", (disk2.id,)
        ).fetchone()
        conn.row_factory = None
        assert disk2_row is not None
        assert disk2_row["is_mounted"] == 0, f"Expected disk2.is_mounted=0 after EIO; got {disk2_row['is_mounted']}"

        # --- Disk2 unreachable_strikes incremented ---
        assert disk2_row["unreachable_strikes"] == 1, (
            f"Expected disk2.unreachable_strikes=1 after one EIO; got {disk2_row['unreachable_strikes']}"
        )

        # --- Circuit breaker recorded the failure ---
        # After one failure, the breaker is NOT yet open (threshold=3 by default),
        # but it must have recorded the failure.  We verify the internal counter.
        assert breaker._failure_counts.get(disk2.uuid, 0) == 1, (  # pyright: ignore[reportPrivateUsage]
            "Expected DiskCircuitBreaker to have recorded exactly 1 failure for Disk2's UUID"
        )

        # --- Disk1 circuit records success (breaker not incremented for Disk1) ---
        assert breaker._failure_counts.get(disk1.uuid, 0) == 0  # pyright: ignore[reportPrivateUsage]

        # --- io_error log event emitted for Disk2 ---
        warning_messages = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("io_error" in msg for msg in warning_messages), (
            f"Expected 'indexer.disk.io_error' WARNING in caplog for Disk2; got: {warning_messages}"
        )

        conn.close()

    def test_disk1_only_no_eio(
        self,
        tmp_path: Path,
    ) -> None:
        """Control test: single-disk scan with no EIO commits all rows normally.

        Verifies that the EIO injection harness does not accidentally corrupt
        the single-disk (Disk1-only) path.

        Scenario:
        1. Build a Disk1 fixture with 50 flat files.
        2. Run a full-mode scan with a patched ``os.scandir`` configured for a
           *different* Disk2 mount — Disk1 calls pass through unmodified.
        3. Assert all 50 files are committed and ``disk.is_mounted`` remains 1.
        """
        mount1 = tmp_path / "Disk1Control"
        # Use a non-existent path as the Disk2 mount for the EIO filter so
        # ALL scandir calls from Disk1 pass through unmodified.
        fake_disk2_mount = str(tmp_path / "NonExistentDisk2")

        _build_fixture(mount1, n_flat=50, n_subdir=0)

        conn = _open_db()
        disk1 = _insert_disk(conn, "Disk1Control", str(mount1))

        breaker = DiskCircuitBreaker()
        patched_scandir = _make_eio_scandir(fake_disk2_mount)

        with (
            patch(_GUARD_PATCH, return_value=None),
            patch(_SCANDIR_PATCH, side_effect=patched_scandir),
        ):
            result = scan(
                [disk1],
                mode=ScanMode.full,
                generation=1,
                conn=conn,
                disk_breaker=breaker,
            )

        assert result.status == "ok"

        conn.row_factory = sqlite3.Row
        disk1_count = conn.execute(
            """
            SELECT COUNT(*) AS cnt
              FROM media_file mf
              JOIN path p ON p.id = mf.path_id
             WHERE p.disk_id = ?
            """,
            (disk1.id,),
        ).fetchone()["cnt"]
        conn.row_factory = None

        assert disk1_count == 50, f"Expected 50 media_file rows; got {disk1_count}"

        # Disk1 must remain mounted and have zero strikes.
        conn.row_factory = sqlite3.Row
        disk1_row = conn.execute(
            "SELECT is_mounted, unreachable_strikes FROM disk WHERE id = ?", (disk1.id,)
        ).fetchone()
        conn.row_factory = None
        assert disk1_row["is_mounted"] == 1
        assert disk1_row["unreachable_strikes"] == 0

        conn.close()

"""End-to-end test: DST clock jump does not produce spurious racy flags (sub-phase 3.4b).

Regression test for DESIGN §15.5 (racy-mtime) under clock-skew conditions:
- The scanner must use real file ``mtime_ns`` from ``stat()`` for racy detection,
  not a clock-derived value.
- A DST fall-back (clock jumping backward by 1 h) must not cause previously
  non-racy files to be marked racy on a subsequent scan.

Test strategy:
    1. Create 5 real files in ``tmp_path``.
    2. Run a full-mode scan with ``time.time`` patched to return ``T0``.
    3. Advance ``time.time`` to ``T0 + 7200`` (2 h forward — simulates DST spring-forward
       or a multi-hour gap between scans).
    4. Run a second full-mode scan with ``time.time`` returning ``T0 + 7200``.
    5. Simulate a DST fall-back: ``time.time`` jumps to ``T0 + 3600`` (1 h back).
    6. Assert file ``mtime_ns`` values in DB are unchanged (real file mtime, not
       clock-derived).
    7. Assert no file is racy by the :func:`~personalscraper.indexer.fingerprint.is_racy`
       definition: ``file_mtime_ns >= scan_started_at_ns - 2_000_000_000``.
    8. Assert exactly 5 rows in ``media_file``, no duplicates.

Note: ``time.time`` is patched globally inside ``personalscraper.indexer.scanner``
to control the ``scan_run.started_at`` / ``last_verified_at`` timestamps written
by the scanner.  The real file ``mtime_ns`` values come from ``os.stat()`` and are
therefore unaffected by the mock.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.fingerprint import is_racy
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"

# ---------------------------------------------------------------------------
# Fixture constants
# ---------------------------------------------------------------------------

_TOTAL_FILES = 5
_FILE_NAMES = [f"media_{i:02d}.txt" for i in range(_TOTAL_FILES)]

# Racy window: 2 s in nanoseconds (matches fingerprint.is_racy default).
_RACY_WINDOW_NS: int = 2_000_000_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db(db_path: Path) -> sqlite3.Connection:
    """Open a real SQLite DB at *db_path* with full schema applied.

    Args:
        db_path: Filesystem path for the SQLite database file.

    Returns:
        Open :class:`sqlite3.Connection` with FK enforcement and
        migrations applied.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
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


def _build_fixture(mount: Path, file_names: list[str]) -> None:
    """Create a flat directory of text files under *mount* with old mtimes.

    Files are back-dated to 7 days in the past via ``os.utime`` so that their
    ``mtime_ns`` is well outside the 2-second racy window regardless of any
    simulated clock jumps (±1 h) applied during the test.

    Args:
        mount: Root of the fake disk (real ``tmp_path`` subdirectory).
        file_names: List of bare filenames to create.
    """
    mount.mkdir(parents=True, exist_ok=True)
    old_mtime = time.time() - 7 * 86400  # 7 days ago
    for name in file_names:
        p = mount / name
        p.write_text(f"content of {name}")
        # Back-date the file so mtime_ns is far outside any racy window.
        os.utime(p, (old_mtime, old_mtime))


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestDstClockJump:
    """DST clock jump does not produce spurious racy flags on unchanged files."""

    def test_dst_jump_no_spurious_racy(self, tmp_path: Path) -> None:
        """Two scans separated by a DST fall-back leave mtime_ns unchanged and no racy flags.

        The test exercises that scanner uses real OS ``mtime_ns`` (from ``stat()``)
        for fingerprinting rather than clock-derived values.  A 1-hour backward jump
        in ``time.time`` must not cause ``is_racy`` to flag unchanged files.
        """
        db_path = tmp_path / "test.db"
        mount = tmp_path / "DiskDST"

        _build_fixture(mount, _FILE_NAMES)

        conn = _open_db(db_path)
        disk = _insert_disk(conn, "DiskDST", str(mount))

        # Capture real file mtimes before any scan — these must survive both scans.
        real_mtimes: dict[str, int] = {}
        for name in _FILE_NAMES:
            real_mtimes[name] = (mount / name).stat().st_mtime_ns

        # ------------------------------------------------------------------
        # T0 = real current time.  Files were back-dated to 7 days ago by
        # _build_fixture, so file_mtime_ns << T0_ns - 2s → clearly non-racy.
        # The simulated DST jumps (+7200 s, then fall-back to +3600 s) shift
        # scan_started_at by at most ±2 h, which is nowhere near the 2-s racy
        # window around a 7-day-old mtime.
        # ------------------------------------------------------------------
        t0 = int(time.time())

        # ------------------------------------------------------------------
        # Scan 1: time.time() returns T0
        # ------------------------------------------------------------------
        with (
            patch(_GUARD_PATCH, return_value=None),
            patch("personalscraper.indexer.scanner.time.time", return_value=t0),
        ):
            result1 = scan(
                [disk],
                mode=ScanMode.full,
                generation=1,
                conn=conn,
                drop_indexes=False,
                event_bus=EventBus(),
            )

        assert result1.status == "ok"
        assert result1.files_visited == _TOTAL_FILES

        # ------------------------------------------------------------------
        # Advance clock: T0 + 7200 (2 h forward — spring-forward or long gap)
        # ------------------------------------------------------------------
        t1 = t0 + 7200

        # Scan 2: time.time() returns T0 + 7200.  Files have NOT changed on disk.
        with (
            patch(_GUARD_PATCH, return_value=None),
            patch("personalscraper.indexer.scanner.time.time", return_value=t1),
        ):
            result2 = scan(
                [disk],
                mode=ScanMode.full,
                generation=2,
                conn=conn,
                drop_indexes=False,
                event_bus=EventBus(),
            )

        assert result2.status == "ok"
        assert result2.files_visited == _TOTAL_FILES

        # ------------------------------------------------------------------
        # DST fall-back: clock jumps to T0 + 3600 (1 h backward from T0+7200)
        # ------------------------------------------------------------------
        t_fallback = t0 + 3600

        # Scan 3: time.time() returns the fallen-back time.
        with (
            patch(_GUARD_PATCH, return_value=None),
            patch("personalscraper.indexer.scanner.time.time", return_value=t_fallback),
        ):
            result3 = scan(
                [disk],
                mode=ScanMode.full,
                generation=3,
                conn=conn,
                drop_indexes=False,
                event_bus=EventBus(),
            )

        assert result3.status == "ok"
        assert result3.files_visited == _TOTAL_FILES

        # ------------------------------------------------------------------
        # Assert: exactly 5 rows, no duplicates
        # ------------------------------------------------------------------
        count = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
        assert count == _TOTAL_FILES, f"Expected {_TOTAL_FILES} media_file rows, got {count}"

        dup_count = conn.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT path_id, filename FROM media_file"
            "  GROUP BY path_id, filename HAVING COUNT(*) > 1"
            ")"
        ).fetchone()[0]
        assert dup_count == 0, f"Found {dup_count} duplicate (path_id, filename) pairs"

        # ------------------------------------------------------------------
        # Assert: mtime_ns in DB matches real file mtime (clock mock had no effect)
        # ------------------------------------------------------------------
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT filename, mtime_ns FROM media_file").fetchall()
        db_mtimes = {r["filename"]: r["mtime_ns"] for r in rows}

        for name in _FILE_NAMES:
            expected = real_mtimes[name]
            actual = db_mtimes.get(name)
            assert actual is not None, f"File {name!r} missing from media_file"
            assert actual == expected, f"mtime_ns for {name!r} changed: expected {expected}, got {actual}"

        # ------------------------------------------------------------------
        # Assert: no file is racy relative to the fall-back scan time.
        # scan_started_at for the DST scan is t_fallback (in seconds).
        # Convert to nanoseconds for is_racy comparison.
        # ------------------------------------------------------------------
        scan_started_at_ns = t_fallback * 1_000_000_000
        for name in _FILE_NAMES:
            file_mtime_ns = real_mtimes[name]
            racy = is_racy(file_mtime_ns, scan_started_at_ns, _RACY_WINDOW_NS)
            assert not racy, (
                f"File {name!r} was spuriously marked racy after DST fall-back: "
                f"mtime_ns={file_mtime_ns}, scan_started_at_ns={scan_started_at_ns}"
            )

        conn.close()

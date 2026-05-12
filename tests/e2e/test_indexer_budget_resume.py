"""End-to-end test: budget exhaustion + crash-resume lifecycle (sub-phase 3.4b).

Covers the checkpoint/resume pipeline introduced in sub-phase 3.4a:
- Run a full-mode scan with a short ``budget_seconds`` limit and
  ``checkpoint_every_n_files=1`` so the budget exhausts after a handful of files.
- Manually inject a stale ``scan_run`` row and a lock-file pointing at a
  dead PID so the second scan detects a "crashed" predecessor and resumes.
- Assert that the resumed scan completes and the total file count is correct
  with no duplicates.

Real SQLite (``tmp_path / "test.db"``) is used (not ``:memory:``) so that
``db_path`` is meaningful for :func:`~personalscraper.indexer.scanner._check_crash_resume`.

pyfakefs is NOT used here — the test uses real files in ``tmp_path``.  This
avoids the ``fs.pause()``/``fs.resume()`` ceremony while still exercising the
lock-file logic.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.schema import DiskRow

_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"

# ---------------------------------------------------------------------------
# Number of files in the fixture.  Choose 10 so we can assert an exact total.
# ---------------------------------------------------------------------------

_TOTAL_FILES = 10

# Plain .txt files — no oshash computed, avoids 128 KiB I/O in CI.
# The scanner accepts every file regardless of extension.
_FILE_NAMES = [f"file_{i:02d}.txt" for i in range(_TOTAL_FILES)]


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
    """Create a flat directory of text files under *mount*.

    Args:
        mount: Root of the fake disk (real ``tmp_path`` subdirectory).
        file_names: List of bare filenames to create.
    """
    mount.mkdir(parents=True, exist_ok=True)
    for name in file_names:
        (mount / name).write_text(f"content of {name}")


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestBudgetResume:
    """Budget exhaustion followed by crash-resume completes the full index."""

    def test_budget_exhaustion_then_resume_completes(self, tmp_path: Path) -> None:
        """Scan stops mid-walk on budget exhaustion; resume indexes remaining files.

        Steps:
        1. Build 10 real text files in a temp directory.
        2. Run scan with ``budget_seconds=3.0`` and ``checkpoint_every_n_files=1``.
           Mock ``time.monotonic`` so elapsed advances by 1.0 s per call, causing
           the budget to exhaust after 3 files.
        3. Assert ``result.budget_exhausted is True`` and ``files_visited <= 4``.
        4. Patch the stale scan_run row: set its status back to ``'running'``
           and write a lock file pointing at a presumed-dead PID (99999).
        5. Run scan again (no budget) — _check_crash_resume detects the stale
           run and resumes past the last checkpoint.
        6. Assert 10 total ``media_file`` rows with no duplicates.
        """
        db_path = tmp_path / "test.db"
        mount = tmp_path / "DiskX"

        _build_fixture(mount, _FILE_NAMES)

        conn = _open_db(db_path)
        disk = _insert_disk(conn, "DiskX", str(mount))

        # ------------------------------------------------------------------
        # Phase 1: budget-limited scan
        # ------------------------------------------------------------------

        # time.monotonic() call order inside scan(event_bus=EventBus()):
        #   call 0  → _started_at_monotonic capture   → 0.0
        #   call 1  → first  _maybe_checkpoint check  → 1.0  (elapsed 1.0 < 3.0)
        #   call 2  → second _maybe_checkpoint check  → 2.0  (elapsed 2.0 < 3.0)
        #   call 3  → third  _maybe_checkpoint check  → 3.0  (elapsed 3.0 >= 3.0 → stop)
        _mono_counter: list[float] = [0.0]

        def _fake_monotonic() -> float:
            """Advance monotonic clock by 1.0 s on each call."""
            _mono_counter[0] += 1.0
            return _mono_counter[0]

        with (
            patch(_GUARD_PATCH, return_value=None),
            patch("personalscraper.indexer.scanner.time.monotonic", side_effect=_fake_monotonic),
        ):
            result1 = scan(
                [disk],
                mode=ScanMode.full,
                generation=1,
                conn=conn,
                drop_indexes=False,
                budget_seconds=3.0,
                db_path=db_path,
                checkpoint_every_n_files=1,
                event_bus=EventBus(),
            )

        assert result1.budget_exhausted is True, f"Expected budget_exhausted=True, got {result1.budget_exhausted}"
        # With checkpoint_every=1 and budget=3.0s advancing 1.0s/call, the walk
        # stops after 3 checkpoints.  Allow up to 4 to tolerate off-by-one in
        # the counter reset logic.
        assert result1.files_visited <= 4, (
            f"Expected at most 4 files visited on budget run, got {result1.files_visited}"
        )

        # Verify last_path was checkpointed (non-NULL in the DB).
        run1 = conn.execute(
            "SELECT last_path, status FROM scan_run WHERE id = ?",
            (result1.scan_run_id,),
        ).fetchone()
        assert run1 is not None
        # The budget-exhausted path marks status='ok' and last_path should be set.
        assert run1[1] == "ok"
        assert run1[0] is not None, "last_path must be populated after budget exhaustion"

        # ------------------------------------------------------------------
        # Inject stale "running" state so _check_crash_resume detects a crash.
        # ------------------------------------------------------------------
        conn.execute(
            "UPDATE scan_run SET status = 'running' WHERE id = ?",
            (result1.scan_run_id,),
        )
        conn.commit()

        # Write a lock file pointing at a PID that is almost certainly dead.
        # PID 99999 is above the default macOS/Linux max PID (32768 / 4194304)
        # or is extremely unlikely to be in use; os.kill(99999, 0) will raise
        # ProcessLookupError, which _check_crash_resume treats as "process dead".
        lock_path = db_path.parent / (db_path.name + ".lock.json")
        lock_data = {
            "pid": 99999,
            "started_at": int(time.time()) - 3600,
            "hostname": "test-host",
        }
        lock_path.write_text(json.dumps(lock_data))

        # ------------------------------------------------------------------
        # Phase 2: resumed scan (no budget, no extra mocking)
        # ------------------------------------------------------------------
        with patch(_GUARD_PATCH, return_value=None):
            result2 = scan(
                [disk],
                mode=ScanMode.full,
                generation=2,
                conn=conn,
                drop_indexes=False,
                db_path=db_path,
                checkpoint_every_n_files=10,
                event_bus=EventBus(),
            )

        assert result2.status == "ok", f"Expected status='ok', got {result2.status!r}"
        assert result2.budget_exhausted is False

        # ------------------------------------------------------------------
        # Assert: all 10 files indexed, no duplicates.
        # ------------------------------------------------------------------
        count = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
        assert count == _TOTAL_FILES, f"Expected {_TOTAL_FILES} media_file rows after resume, got {count}"

        # No duplicate (path_id, filename) pairs.
        dup_count = conn.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT path_id, filename FROM media_file"
            "  GROUP BY path_id, filename HAVING COUNT(*) > 1"
            ")"
        ).fetchone()[0]
        assert dup_count == 0, f"Found {dup_count} duplicate (path_id, filename) pairs"

        conn.close()

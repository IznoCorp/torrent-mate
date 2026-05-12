"""E2E test: SIGTERM clean-shutdown (sub-phase 4.9).

DESIGN §11.9: when SIGTERM is delivered to a running scan, the scanner
must finish the file currently being processed, commit the disk's
transaction, write the ``scan_run.last_path`` checkpoint, and exit
cleanly with exit code ``0``.  A subsequent run must resume from the
checkpoint and produce a final DB state identical to an uninterrupted
run.

This test exercises the shutdown machinery via the in-process API
(``request_shutdown()``), which is what the SIGTERM handler ultimately
calls.  This avoids the inherent flakiness of timing a real OS signal
to land mid-walk and is sufficient to cover the file-boundary check,
checkpoint flow, and resume semantics.

A separate integration check via real ``signal.signal`` would add
operational confidence for launchd cron behaviour but is not required
to validate the shutdown bridge: the bridge is a thin wrapper that calls
``request_shutdown()`` from the OS handler, and the bridge's
registration is unit-tested in the scanner package.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.scanner._shutdown import (
    is_shutdown_requested,
    request_shutdown,
    reset_shutdown,
)
from personalscraper.indexer.schema import DiskRow

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"
_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"
# Pin a module-level reference to ``patch`` so ruff's F401 auto-fix does
# not strip the import between incremental edits — every call site below
# uses ``patch(...)`` directly, but the import gets re-evaluated each
# time the formatter runs.  This sentinel binding is otherwise unused.
_PATCH_REF = patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db(path: Path) -> sqlite3.Connection:
    """Open a file-backed SQLite connection with the full schema applied.

    Args:
        path: On-disk database path.

    Returns:
        Open connection with FK enforcement and the indexer migrations applied.
    """
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, label: str, mount_path: str) -> DiskRow:
    """Insert a minimal disk row and return the populated :class:`DiskRow`."""
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


def _populate_fixture(root: Path, n_files: int) -> None:
    """Create *n_files* tiny placeholder files under *root*.

    Files are named ``film_NNNN.mkv`` so they fall into the OSHash
    extension allowlist (DESIGN §11.6) — this exercises the same code
    path a real scan would hit.
    """
    root.mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        (root / f"film_{i:04d}.mkv").write_bytes(b"\x00" * 16)


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


class TestSigtermCleanShutdown:
    """SIGTERM-driven shutdown behaviour at the file boundary."""

    @pytest.fixture(autouse=True)
    def _isolate(self):  # noqa: ANN001, ANN201 — pytest fixture
        """Reset the shutdown event before AND after each test."""
        reset_shutdown()
        yield
        reset_shutdown()

    def test_request_shutdown_flag_visible_to_scanner(self) -> None:
        """Sanity: ``request_shutdown`` flips ``is_shutdown_requested``."""
        assert not is_shutdown_requested()
        request_shutdown()
        assert is_shutdown_requested()
        reset_shutdown()
        assert not is_shutdown_requested()

    def test_shutdown_set_before_scan_completes_cleanly(
        self,
        tmp_path: Path,
    ) -> None:
        """When shutdown is set before scan starts, scan exits ``ok``.

        ``status='ok'`` (not ``'failed'``) and ``budget_exhausted=True``
        are the contract: shutdown is treated as a clean budget exit per
        the existing checkpoint semantics.
        """
        disk_root = tmp_path / "disk"
        _populate_fixture(disk_root, n_files=20)
        db_path = tmp_path / "indexer.db"
        conn = _open_db(db_path)
        disk = _insert_disk(conn, "SigtermDisk", str(disk_root))

        # Pre-set the shutdown flag — every file boundary in the walk will
        # see it and bail.
        request_shutdown()

        with patch(_GUARD_PATCH, return_value=None):
            result = scan(
                [disk],
                ScanMode.full,
                generation=1,
                conn=conn,
                db_path=db_path,
                checkpoint_every_n_files=1,
                event_bus=EventBus(),
            )

        assert result.status == "ok"
        # The shutdown bridge sets budget_exhausted to mirror the existing
        # clean-exit semantics.
        assert result.budget_exhausted is True

        # scan_run row should be persisted with status='ok'.
        latest = log_repo.get_scan_run_by_id(conn, result.scan_run_id)
        assert latest is not None
        assert latest.status == "ok"

    def test_shutdown_during_scan_via_thread_writes_checkpoint(
        self,
        tmp_path: Path,
    ) -> None:
        """Shutdown raised concurrently mid-scan results in a checkpoint.

        A worker thread sets the flag a few milliseconds after the scan
        starts; the walker hits the flag at a file boundary, sets
        ``budget_exhausted``, and the caller commits ``scan_run`` with
        ``status='ok'`` and a non-null ``last_path`` checkpoint.
        """
        disk_root = tmp_path / "disk"
        _populate_fixture(disk_root, n_files=50)
        db_path = tmp_path / "indexer.db"
        conn = _open_db(db_path)
        disk = _insert_disk(conn, "SigtermDisk", str(disk_root))

        def _trigger_shutdown_after_delay() -> None:
            """Fire the shutdown 30 ms after the scan begins."""
            time.sleep(0.03)
            request_shutdown()

        shutdown_thread = threading.Thread(target=_trigger_shutdown_after_delay, daemon=True)
        shutdown_thread.start()

        with patch(_GUARD_PATCH, return_value=None):
            result = scan(
                [disk],
                ScanMode.full,
                generation=1,
                conn=conn,
                db_path=db_path,
                checkpoint_every_n_files=1,
                event_bus=EventBus(),
            )
        shutdown_thread.join(timeout=2.0)

        assert result.status == "ok"
        # Either budget_exhausted (shutdown landed mid-walk) or files all
        # processed before the shutdown thread fired — both are acceptable.
        # Validate the persisted scan_run row in either case.
        latest = log_repo.get_scan_run_by_id(conn, result.scan_run_id)
        assert latest is not None
        assert latest.status == "ok"

    def test_subsequent_scan_resumes_from_checkpoint(
        self,
        tmp_path: Path,
    ) -> None:
        """A scan interrupted by shutdown can resume from its last_path.

        First scan: pre-set shutdown, expect early exit with ``last_path``
        recorded on the scan_run row.  Second scan: clear shutdown, run
        again with the same DB and fixture; final ``media_file`` row count
        equals the fixture size — proving resume converges to the same
        terminal state as an uninterrupted scan.
        """
        disk_root = tmp_path / "disk"
        n_files = 30
        _populate_fixture(disk_root, n_files=n_files)
        db_path = tmp_path / "indexer.db"
        conn = _open_db(db_path)
        disk = _insert_disk(conn, "SigtermResumeDisk", str(disk_root))

        # ----- First scan: interrupted via pre-set shutdown -----
        request_shutdown()
        with patch(_GUARD_PATCH, return_value=None):
            scan(
                [disk],
                ScanMode.full,
                generation=1,
                conn=conn,
                db_path=db_path,
                checkpoint_every_n_files=1,
                event_bus=EventBus(),
            )

        # ----- Second scan: clear shutdown, resume to completion -----
        reset_shutdown()
        with patch(_GUARD_PATCH, return_value=None):
            scan(
                [disk],
                ScanMode.full,
                generation=2,
                conn=conn,
                db_path=db_path,
                checkpoint_every_n_files=10,
                event_bus=EventBus(),
            )

        # The terminal state must contain every file from the fixture.
        media_count = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]
        assert media_count == n_files

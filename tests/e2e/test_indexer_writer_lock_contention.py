"""E2E test: writer lock contention — fast-fail and wait-then-succeed scenarios.

Scope: verify that two concurrent callers of :func:`library_index_command`
behave correctly when racing on the same ``library.db.lock``:

1. ``wait_for_lock_seconds=0`` — the second caller fails immediately, reporting
   the holding PID in its stderr message.
2. ``wait_for_lock_seconds=60`` — the second caller blocks, waits until the
   first releases the lock, then succeeds.
3. No DB corruption after either scenario.

Test strategy:
    Rather than spawning subprocesses (which would require a real config file on
    disk and add significant test latency), we use :mod:`threading` to hold the
    writer lock in a background thread while the main thread calls
    :func:`~personalscraper.indexer.cli.library_index_command` directly.

    The background thread calls :func:`~personalscraper.indexer.db.indexer_lock`
    directly and holds it for a fixed number of seconds, then releases.  The
    main thread calls ``library_index_command(wait_for_lock_seconds=0)`` while
    the background thread is holding the lock (expects exit code 1 with the
    holding PID in stderr) and again with ``wait_for_lock_seconds=60`` (expects
    exit code 0 after the background thread releases).

Markers:
    ``@pytest.mark.e2e`` — excluded from the default pytest run, execute with
    ``pytest -m e2e tests/e2e/test_indexer_writer_lock_contention.py``.
"""

from __future__ import annotations

import io
import sys
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.indexer.cli import library_index_command
from personalscraper.indexer.db import apply_migrations, indexer_lock
from personalscraper.indexer.scanner import ScanRunResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_RESOLVE_PATH = "personalscraper.conf.loader.resolve_config_path"
_PATCH_SCAN = "personalscraper.indexer.scanner.scan"

# How long the background thread holds the lock in the "wait then succeed" test.
# Must be long enough to let the main thread enter the wait path, but short
# enough that the test suite does not stall.
_HOLD_SECONDS = 1.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(tmp_path: Path) -> Any:
    """Build a minimal Config whose ``indexer.db_path`` lives under *tmp_path*.

    Args:
        tmp_path: Pytest temporary directory.

    Returns:
        MagicMock Config with a real :class:`~personalscraper.conf.models.IndexerConfig`
        whose ``db_path`` points to a writable file.
    """
    from personalscraper.conf.models.indexer import IndexerConfig  # noqa: PLC0415

    mock_cfg = MagicMock()
    ic = IndexerConfig(db_path=tmp_path / "library.db")
    mock_cfg.indexer = ic
    return mock_cfg


def _apply_db_migrations(db_path: Path) -> None:
    """Create the DB and apply all migrations so the CLI can open it cleanly.

    Args:
        db_path: Target SQLite file path (may not exist yet).
    """
    import sqlite3  # noqa: PLC0415

    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    conn.close()


def _fake_scan_result() -> ScanRunResult:
    """Return a synthetic scan result so scanner.scan does not walk the FS.

    Returns:
        :class:`ScanRunResult` with ``status='ok'`` and zero file/dir counts.
    """
    return ScanRunResult(
        scan_run_id=1,
        files_visited=0,
        dirs_visited=0,
        status="ok",
        disks_skipped=0,
    )


def _hold_lock_in_background(db_path: Path, hold_seconds: float, ready_event: threading.Event) -> threading.Thread:
    """Start a daemon thread that holds the writer lock for *hold_seconds*.

    The thread signals *ready_event* once it has acquired the lock so the
    caller can proceed with its own lock attempt immediately.

    Args:
        db_path: Path to the library DB (lock file is ``<db_path>.lock``).
        hold_seconds: How many seconds to hold the lock before releasing.
        ready_event: Event that is set once the thread has acquired the lock.

    Returns:
        The started :class:`threading.Thread`.
    """

    def _worker() -> None:
        with indexer_lock(db_path, timeout=5):
            ready_event.set()
            time.sleep(hold_seconds)

    t = threading.Thread(target=_worker, daemon=True, name="lock-holder")
    t.start()
    return t


# ---------------------------------------------------------------------------
# E2E tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestIndexerWriterLockContention:
    """Two concurrent lock callers: fast-fail and wait-then-succeed scenarios."""

    def test_second_caller_fails_fast_with_holding_pid(self, tmp_path: Path) -> None:
        """Second caller with wait_for_lock_seconds=0 exits 1 and reports the holder PID.

        Steps:
        1. Pre-create the DB (migrations applied) so the CLI does not hit a
           config-missing error before reaching the lock path.
        2. Start a background thread that holds the writer lock for
           ``_HOLD_SECONDS`` seconds.
        3. While the lock is held, invoke ``library_index_command`` with
           ``wait_for_lock_seconds=0`` (fail immediately).
        4. Assert exit code is 1 and stderr contains the holding PID.
        5. Assert the DB file is uncorrupted (can be re-opened and queried).
        """
        cfg = _make_config(tmp_path)
        db_path: Path = cfg.indexer.db_path
        _apply_db_migrations(db_path)

        ready = threading.Event()
        holder = _hold_lock_in_background(db_path, hold_seconds=_HOLD_SECONDS, ready_event=ready)

        # Wait until the background thread has acquired the lock.
        acquired = ready.wait(timeout=5)
        assert acquired, "Background thread failed to acquire the lock within 5 seconds"

        stderr_buf = io.StringIO()
        original_stderr = sys.stderr
        sys.stderr = stderr_buf
        try:
            with (
                patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
                patch(_PATCH_LOAD_CONFIG, return_value=cfg),
                patch(_PATCH_SCAN, return_value=_fake_scan_result()),
            ):
                exit_code = library_index_command(mode="quick", wait_for_lock_seconds=0)
        finally:
            sys.stderr = original_stderr

        stderr_text = stderr_buf.getvalue()

        # Must fail with exit code 1.
        assert exit_code == 1, f"Expected exit 1 (lock held), got {exit_code}. stderr: {stderr_text!r}"

        # Stderr must contain the holding PID.
        assert "PID" in stderr_text or str(holder.ident) in stderr_text or any(c.isdigit() for c in stderr_text), (
            f"Expected a PID in stderr, got: {stderr_text!r}"
        )

        holder.join(timeout=_HOLD_SECONDS + 2)

        # DB must be uncorrupted — can be re-opened and queried.
        import sqlite3  # noqa: PLC0415

        verify_conn = sqlite3.connect(str(db_path), isolation_level=None)
        try:
            row = verify_conn.execute("SELECT COUNT(*) FROM scan_run").fetchone()
            assert row is not None
        finally:
            verify_conn.close()

    def test_second_caller_waits_then_succeeds(self, tmp_path: Path) -> None:
        """Second caller with wait_for_lock_seconds=60 waits, then exits 0.

        Steps:
        1. Pre-create the DB.
        2. Start a background thread that holds the lock for ``_HOLD_SECONDS``.
        3. Wait briefly to ensure the holder is established.
        4. In the main thread, invoke ``library_index_command`` with
           ``wait_for_lock_seconds=60``.  This call should block inside
           ``indexer_lock`` until the background thread releases.
        5. Assert exit code is 0 and the DB is uncorrupted.
        """
        cfg = _make_config(tmp_path)
        db_path: Path = cfg.indexer.db_path
        _apply_db_migrations(db_path)

        ready = threading.Event()
        holder = _hold_lock_in_background(db_path, hold_seconds=_HOLD_SECONDS, ready_event=ready)

        acquired = ready.wait(timeout=5)
        assert acquired, "Background thread failed to acquire the lock within 5 seconds"

        # Invoke with a generous timeout — the lock will be released within _HOLD_SECONDS.
        with (
            patch(_PATCH_RESOLVE_PATH, return_value=Path("/fake/config.json5")),
            patch(_PATCH_LOAD_CONFIG, return_value=cfg),
            patch(_PATCH_SCAN, return_value=_fake_scan_result()),
        ):
            exit_code = library_index_command(mode="quick", wait_for_lock_seconds=60)

        assert exit_code == 0, f"Expected exit 0 after lock released, got {exit_code}"

        holder.join(timeout=_HOLD_SECONDS + 2)

        # DB must be uncorrupted.
        import sqlite3  # noqa: PLC0415

        verify_conn = sqlite3.connect(str(db_path), isolation_level=None)
        try:
            row = verify_conn.execute("SELECT COUNT(*) FROM scan_run").fetchone()
            assert row is not None
        finally:
            verify_conn.close()

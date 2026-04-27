"""Checkpoint and crash-resume helpers for the scanner (sub-phase 3.4).

Provides:
- :func:`_checkpoint_scan_run` — persist current walk position.
- :func:`_check_crash_resume` — detect a previous crashed scan.
- :func:`_maybe_checkpoint` — conditionally write a checkpoint and test budget.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

from personalscraper.indexer.scanner._types import IndexerScanActiveError
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")


def _checkpoint_scan_run(conn: sqlite3.Connection, scan_run_id: int, last_path_str: str) -> None:
    """Persist the current walk position so a crashed scan can resume.

    Writes ``last_path`` on the ``scan_run`` row and immediately commits so
    the update survives a hard kill.  Called every ``checkpoint_every_n_files``
    files during the walk.

    Args:
        conn: Open SQLite connection.
        scan_run_id: PK of the active ``scan_run`` row.
        last_path_str: Opaque path string of the form ``"<disk_label>/<rel>/<filename>"``
            that identifies the last successfully processed file.
    """
    conn.execute(
        "UPDATE scan_run SET last_path = ? WHERE id = ?",
        (last_path_str, scan_run_id),
    )
    conn.commit()


def _check_crash_resume(conn: sqlite3.Connection, db_path: Path) -> str | None:
    """Detect a previous crashed scan and return its resume position.

    Queries ``scan_run`` for any row with ``status='running'``.  If found,
    checks whether the locking process is still alive by reading the PID from
    the companion lock file (``<db_path>.lock.json``).

    Args:
        conn: Open SQLite connection.
        db_path: Filesystem path of the SQLite database file.  Used to derive
            the lock-file path as ``<db_path.parent>/<db_path.name>.lock.json``.

    Returns:
        The ``last_path`` value from the stale scan_run row (may be ``None``
        if the previous scan crashed before any checkpoint was written), or
        ``None`` if no stale run is found.

    Raises:
        IndexerScanActiveError: When the process that holds the lock is still
            alive, indicating a genuinely concurrent scan.
    """
    row = conn.execute(
        "SELECT id, started_at, last_path FROM scan_run WHERE status='running' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None

    last_path: str | None = row[2]

    # Derive lock-file path alongside the database.
    lock_path = db_path.parent / (db_path.name + ".lock.json")
    if not lock_path.exists():
        # Lock file missing — process probably died without cleanup; resume best-effort.
        log.info("indexer.scan.resumed", reason="lock_file_missing", last_path=last_path)
        return last_path

    try:
        with lock_path.open() as fh:
            lock_data = json.load(fh)
        pid: int = int(lock_data["pid"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        # Invalid or unreadable lock file — treat as dead process, resume best-effort.
        log.info("indexer.scan.resumed", reason="lock_file_invalid", last_path=last_path)
        return last_path

    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OSError):
        # Signal 0 raised — process is dead; safe to resume.
        log.info("indexer.scan.resumed", reason="process_dead", pid=pid, last_path=last_path)
        return last_path

    # Process is alive — genuine concurrent scan; refuse to proceed.
    raise IndexerScanActiveError(f"scan already running, PID {pid}")


def _maybe_checkpoint(
    conn: sqlite3.Connection,
    scan_run_id: int,
    current_path: str,
    files_since_checkpoint: int,
    checkpoint_every: int,
    started_at_monotonic: float,
    budget_seconds: float | None,
) -> tuple[int, bool]:
    """Conditionally write a checkpoint and test whether the budget is exhausted.

    Called after every file processed during the walk.  When
    ``files_since_checkpoint`` reaches ``checkpoint_every`` the walk position is
    persisted via :func:`_checkpoint_scan_run`.  If ``budget_seconds`` is set and
    elapsed time exceeds it, the budget-exhausted flag is returned so the caller
    can stop the walk early.

    Args:
        conn: Open SQLite connection.
        scan_run_id: PK of the active ``scan_run`` row.
        current_path: Opaque path string identifying the file just processed.
        files_since_checkpoint: Number of files processed since the last checkpoint.
        checkpoint_every: How many files to process between checkpoints.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start.
        budget_seconds: Maximum wall-clock seconds allowed for the scan; ``None``
            means unlimited.

    Returns:
        A ``(new_counter, budget_exhausted)`` tuple.  ``new_counter`` resets to
        ``0`` when a checkpoint was written, otherwise increments by one.
        ``budget_exhausted`` is ``True`` only when the budget is set and exceeded.
    """
    if files_since_checkpoint >= checkpoint_every:
        _checkpoint_scan_run(conn, scan_run_id, current_path)
        if budget_seconds is not None and time.monotonic() - started_at_monotonic >= budget_seconds:
            return 0, True
        return 0, False
    return files_since_checkpoint, False

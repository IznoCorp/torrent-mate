"""ThreadPoolExecutor helpers for parallel per-disk scan workers.

Provides:
- :func:`_run_disks_in_parallel` — submit one Future per disk, collect results,
  log per-disk failures without propagating them to the caller.

SQLite WAL mode supports multiple readers and one writer at a time.  Each worker
thread opens its **own** :class:`sqlite3.Connection` from *db_path* so writers do
not contend on a single shared connection.  The shared ``scan_run`` lifecycle
(INSERT / UPDATE) is performed by the *caller* on the original ``conn`` before and
after this function returns.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import NamedTuple

from personalscraper.logger import get_logger

log = get_logger("indexer.scan")


class _DiskWorkerResult(NamedTuple):
    """Aggregated counters returned by a single per-disk worker.

    Attributes:
        files_visited: Number of media files visited on this disk.
        dirs_visited: Number of directories visited on this disk.
        disks_skipped: 1 when the disk was Merkle-skipped, 0 otherwise.
        budget_exhausted: ``True`` when the disk's budget was exhausted.
        error: Human-readable error string, or ``None`` on success.
    """

    files_visited: int
    dirs_visited: int
    disks_skipped: int
    budget_exhausted: bool
    error: str | None


def _open_worker_conn(db_path: Path) -> sqlite3.Connection:
    """Open a WAL-mode SQLite connection suitable for a scan worker thread.

    Args:
        db_path: Filesystem path to the SQLite database.

    Returns:
        Open :class:`sqlite3.Connection` with WAL journal mode, normal synchronous
        level, and foreign keys enabled.
    """
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


# Type alias: a disk worker factory receives per-worker counter lists and
# returns a callable that accepts an open SQLite connection.
DiskWorkerFactory = Callable[
    [
        list[int],  # local_files_visited
        list[int],  # local_dirs_visited
        list[int],  # local_disks_skipped
        list[bool],  # local_budget_exhausted
    ],
    Callable[[sqlite3.Connection], None],
]


def _run_disks_in_parallel(
    worker_factories: list[DiskWorkerFactory],
    db_path: Path,
    *,
    max_workers: int,
    shared_files_visited: list[int],
    shared_dirs_visited: list[int],
    shared_disks_skipped: list[int],
    shared_budget_exhausted: list[bool],
) -> list[str]:
    """Run one disk-scan worker per disk in a ThreadPoolExecutor.

    Each entry in *worker_factories* is a callable that builds a disk-scan
    function when given per-worker counter lists.  The returned function accepts
    an open :class:`sqlite3.Connection` and performs the complete scan for one
    disk, writing its counters into the provided local lists.

    Each worker opens its own :class:`sqlite3.Connection` from *db_path*
    (SQLite WAL mode allows concurrent readers; writers serialise per-transaction
    but do not hold the write-lock for the entire disk walk).

    On per-disk worker failure (uncaught exception): log
    ``indexer.scan.disk_worker_failed`` and continue with remaining workers.
    The exception is *not* re-raised — the scan proceeds on all other disks.
    After all futures complete, per-worker counters are merged into the shared
    counter lists under a lock.

    Args:
        worker_factories: One factory per disk.  Each factory is called with
            four single-element mutable lists (local counters) and returns a
            callable ``(conn) -> None``.
        db_path: Filesystem path to the SQLite database.  Used to open per-worker
            connections.
        max_workers: Maximum number of concurrent worker threads.
        shared_files_visited: Shared single-element counter; incremented by each
            worker's result after the worker finishes.
        shared_dirs_visited: Shared single-element counter for directories.
        shared_disks_skipped: Shared single-element counter for Merkle-hit skips.
        shared_budget_exhausted: Shared single-element flag; set to ``True`` when
            any worker exhausts the budget.

    Returns:
        List of error strings for any workers that raised an exception.  Empty
        list means all workers completed successfully.
    """
    merge_lock = threading.Lock()
    errors: list[str] = []

    def _build_and_run(factory: DiskWorkerFactory) -> _DiskWorkerResult:
        """Instantiate per-worker counters, open a connection, run the worker."""
        local_files: list[int] = [0]
        local_dirs: list[int] = [0]
        local_skipped: list[int] = [0]
        local_exhausted: list[bool] = [False]

        fn = factory(local_files, local_dirs, local_skipped, local_exhausted)

        worker_conn = _open_worker_conn(db_path)
        try:
            fn(worker_conn)
        finally:
            worker_conn.close()

        return _DiskWorkerResult(
            files_visited=local_files[0],
            dirs_visited=local_dirs[0],
            disks_skipped=local_skipped[0],
            budget_exhausted=local_exhausted[0],
            error=None,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx: dict[Future[_DiskWorkerResult], int] = {
            executor.submit(_build_and_run, factory): idx for idx, factory in enumerate(worker_factories)
        }

        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            exc = future.exception()

            if exc is not None:
                err_msg = f"disk worker {idx} failed: {exc}"
                errors.append(err_msg)
                log.warning(
                    "indexer.scan.disk_worker_failed",
                    worker_index=idx,
                    error=str(exc),
                )
                continue

            result: _DiskWorkerResult = future.result()

            # Merge per-worker counters into shared state under lock.
            with merge_lock:
                shared_files_visited[0] += result.files_visited
                shared_dirs_visited[0] += result.dirs_visited
                shared_disks_skipped[0] += result.disks_skipped
                if result.budget_exhausted:
                    shared_budget_exhausted[0] = True

    return errors


__all__ = ["_DiskWorkerResult", "_open_worker_conn", "_run_disks_in_parallel"]

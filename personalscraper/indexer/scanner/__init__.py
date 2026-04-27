"""Scanner package for the media indexer.

Public API — mirrors the original monolithic scanner.py so all existing imports
of the form ``from personalscraper.indexer.scanner import scan, ScanMode, ...``
continue to work without modification.

The ``scan()`` and ``filter_disks()`` functions live directly in this module
(not in a submodule) so that unittest.mock patches targeting
``personalscraper.indexer.scanner.guard_disk_mounted`` and
``personalscraper.indexer.scanner.os.*`` correctly intercept the names used
inside those functions.

All other helpers (walker, checkpoint, db_writes, etc.) live in private
submodules imported here for re-export.
"""

from __future__ import annotations

import errno
import json
import os
import sqlite3
import tempfile  # noqa: F401 — imported so tests can patch scanner.tempfile.*
import time
from pathlib import Path

from personalscraper.indexer.breaker import DiskCircuitBreaker, get_global_disk_breaker
from personalscraper.indexer.merkle import (
    DiskBulkChangeDetected,
    DiskMismatchError,
    DiskUnmountedError,
    guard_disk_mounted,
)
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner._checkpoint import _check_crash_resume
from personalscraper.indexer.scanner._db_writes import _upsert_path_row
from personalscraper.indexer.scanner._exclusions import EXCLUDED_NAMES, _should_exclude
from personalscraper.indexer.scanner._modes import (
    _scan_disk_enrich,
    _scan_disk_full,
    _scan_disk_incremental,
    _scan_disk_quick,
)
from personalscraper.indexer.scanner._types import (
    IndexerConfigError,
    IndexerScanActiveError,
    ScanMode,
    ScanRunResult,
)
from personalscraper.indexer.scanner._walker import (
    _build_disk_fingerprints,
    _verify_dir_mtime_reliable,
    _walk_dir,
)
from personalscraper.indexer.schema import DiskRow, ScanRunRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")


def filter_disks(disks: list[DiskRow], disk_label: str | None) -> list[DiskRow]:
    """Filter a disk list to a single disk by label, or return all disks.

    When ``disk_label`` is ``None``, the full list is returned unchanged.
    When ``disk_label`` is provided, the list is filtered to disks whose
    ``label`` matches exactly.  If no match is found an
    :class:`IndexerConfigError` is raised.

    Args:
        disks: Full list of :class:`~personalscraper.indexer.schema.DiskRow`
            objects to filter.
        disk_label: Disk label to match against.  ``None`` returns all disks.

    Returns:
        Filtered list of :class:`~personalscraper.indexer.schema.DiskRow`
        objects.  Contains at most one element when ``disk_label`` is given.

    Raises:
        IndexerConfigError: When ``disk_label`` is not ``None`` and no disk
            with that label exists in ``disks``.
    """
    if disk_label is None:
        return list(disks)

    matched = [d for d in disks if d.label == disk_label]
    if not matched:
        raise IndexerConfigError(f"no disk with label '{disk_label}'")
    return matched


def scan(
    disks: list[DiskRow],
    mode: ScanMode,
    generation: int,
    conn: sqlite3.Connection,
    disk_filter: str | None = None,
    drop_indexes: bool = False,
    *,
    budget_seconds: float | None = None,
    db_path: Path | None = None,
    checkpoint_every_n_files: int = 100,
    disk_breaker: DiskCircuitBreaker | None = None,
    confirm_bulk_change: bool = False,
    merkle_delta_freeze_threshold: float = 0.50,
    quick_enrich: bool = False,
) -> ScanRunResult:
    """Walk all provided disks and record discovered files in the database.

    Sub-phase 2.5 extends the skeleton walk with full-mode fingerprinting:

    * ``mode == ScanMode.full``: For each file, ``fingerprint_tier1`` extracts
      (size, mtime_ns, ctime_ns) from the already-computed ``stat`` result
      (zero extra I/O).  For files whose lowercase extension is in
      :data:`~personalscraper.indexer.fingerprint.OSHASH_EXTENSIONS`, ``oshash``
      is also computed (128 KiB read).  Symlinks and non-video files receive
      ``oshash=None`` (stored as SQL NULL per migration 002).
    * ``drop_indexes=True``: Secondary indexes on ``media_file`` / ``media_stream``
      are dropped before bulk inserts and recreated in a ``try/finally`` block.
      New rows are buffered in memory (up to :data:`_INSERT_BATCH_SIZE`) and
      flushed via ``executemany`` for faster throughput.
    * ``disk_filter``: When not ``None``, the ``scan_run.disk_filter`` column is
      set to this value to record which single disk was scoped.

    Sub-phase 2.6 extends the function with quick-mode:

    * ``mode == ScanMode.quick``: Before walking any disk, :func:`_verify_dir_mtime_reliable`
      runs a one-time check to confirm the OS updates directory mtime on child writes.
      For each disk, :func:`_scan_disk_quick` attempts a Merkle short-circuit first
      (zero FS reads on match), then falls back to a dir-mtime subtree walk.

    Walk strategy (per disk):
        1. Call :func:`~personalscraper.indexer.merkle.guard_disk_mounted`.  On
           :class:`~personalscraper.indexer.merkle.DiskUnmountedError` or
           :class:`~personalscraper.indexer.merkle.DiskMismatchError` the disk is
           skipped with a warning; the scan continues on remaining disks.
        2. If ``mode == ScanMode.full`` and ``drop_indexes`` is ``True``, drop
           secondary indexes and use ``executemany`` batches for inserts.  Always
           recreate the indexes in a ``try/finally`` block.
        3. Walk the disk root via recursive :func:`os.scandir` calls.
           - Never follow symlinks (``entry.stat(follow_symlinks=False)``).
           - Skip any entry whose name is in :data:`EXCLUDED_NAMES` or starts with ``"._"``.
           - After visiting all children of a directory, upsert the ``path`` row
             with its current ``dir_mtime_ns``.
           - For each file (or symlink) entry, insert/update a ``media_file`` row.
             In full mode, ``oshash`` is populated for eligible video files.
        4. Track ``files_visited`` and ``dirs_visited`` counters.

    Lifecycle:
        A ``scan_run`` row is inserted at start (``status='running'``).  On
        success the row is updated to ``status='ok'`` with ``finished_at``.  On
        any unexpected exception the row is updated to ``status='failed'`` and the
        exception is re-raised.

    Args:
        disks: List of :class:`~personalscraper.indexer.schema.DiskRow` objects
            representing the disks to scan.  Unmounted / mismatched disks are
            skipped without aborting the scan.
        mode: The :class:`ScanMode` to use.  ``full`` enables fingerprinting;
            ``quick`` uses Merkle + dir-mtime short-circuits; other modes fall
            back to the skeleton walk.
        generation: Monotonically increasing generation counter stamped on every
            ``media_file`` row visited during this scan.
        conn: Open :class:`sqlite3.Connection` with ``isolation_level=None``
            (autocommit) or an active transaction managed by the caller.
        disk_filter: Disk label when scoped to a single disk (``--disk D``);
            ``None`` = all disks.  Stored in ``scan_run.disk_filter``.
        drop_indexes: When ``True`` and ``mode == ScanMode.full``, drop and
            recreate secondary indexes around bulk inserts (DESIGN §11.7).
            Only activated when ``IndexerConfig.scan.drop_indexes_during_full_scan``
            is true; callers should pass this value from the config.
        budget_seconds: Maximum wall-clock seconds allowed for the scan.
            When the elapsed time exceeds this limit after a checkpoint, the
            scan stops early and :attr:`ScanRunResult.budget_exhausted` is
            set to ``True``.  ``None`` means unlimited.
        db_path: Filesystem path to the SQLite database file.  When provided,
            :func:`_check_crash_resume` is called at scan start to detect and
            resume a previously crashed scan from its last checkpoint.
            Also used to derive the companion lock-file path.
        checkpoint_every_n_files: How many files to process between successive
            :func:`_checkpoint_scan_run` writes.  Defaults to ``100``.
        disk_breaker: :class:`DiskCircuitBreaker` instance to guard per-disk I/O.
            When ``None``, the module-level singleton returned by
            :func:`get_global_disk_breaker` is used.  Tests that need isolation
            should pass a freshly created :class:`DiskCircuitBreaker` instance.
        confirm_bulk_change: When ``True``, bypass the Merkle delta freeze guard
            in quick mode and proceed with the walk even when the delta exceeds
            *merkle_delta_freeze_threshold*.  Corresponds to ``--confirm-bulk-change``.
        merkle_delta_freeze_threshold: Halt quick-mode scan for a disk if the
            fraction of changed files exceeds this value (0.0–1.0).  Sourced
            from ``IndexerDriftConfig.merkle_delta_freeze_threshold``; callers
            should pass the config value explicitly.
        quick_enrich: When ``True`` and ``mode == ScanMode.enrich``, passes
            ``parse_speed=0.5`` to :class:`~personalscraper.indexer.mediainfo.MediaInfoWrapper`
            for a faster but less complete mediainfo parse.  Default ``False``
            (full parse, ``parse_speed=1.0``).

    Returns:
        :class:`ScanRunResult` with the assigned ``scan_run_id``, visit counts,
        and final status.  When the budget is exhausted,
        :attr:`ScanRunResult.budget_exhausted` is ``True``.

    Raises:
        Exception: Any unexpected exception from the walk loop is re-raised after
            the ``scan_run`` row is updated to ``status='failed'``.
    """
    started_at = int(time.time())

    # Insert scan_run row with status=running.
    scan_run_id = log_repo.insert_scan_run(
        conn,
        ScanRunRow(
            id=0,
            generation=generation,
            mode=mode.value,
            disk_filter=disk_filter,
            started_at=started_at,
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        ),
    )

    # Resolve the circuit breaker: use caller-supplied instance for test isolation,
    # fall back to the module-level singleton for production use.
    breaker: DiskCircuitBreaker = disk_breaker if disk_breaker is not None else get_global_disk_breaker()

    files_visited = [0]  # mutable counter (list avoids nonlocal in nested helper)
    dirs_visited = [0]
    disks_skipped = [0]  # quick-mode Merkle-hit counter

    # Checkpoint / crash-resume state (sub-phase 3.4).
    # Single-element lists used so nested walk helpers can mutate them without
    # nonlocal declarations or extra return values — consistent with files_visited[].
    _resume_from: list[str | None] = [None]
    if db_path is not None:
        _resume_from[0] = _check_crash_resume(conn, db_path)
    _files_since_checkpoint: list[int] = [0]
    _budget_exhausted: list[bool] = [False]
    _started_at_monotonic: float = time.monotonic()

    # One-time dir-mtime reliability check for quick and incremental modes.
    dir_mtime_reliable: bool = True
    if mode in (ScanMode.quick, ScanMode.incremental):
        dir_mtime_reliable = _verify_dir_mtime_reliable()

    try:
        for disk in disks:
            if disk.mount_path is None:
                log.warning(
                    "indexer.scan.disk_skipped",
                    disk_id=disk.id,
                    label=disk.label,
                    reason="no mount_path",
                )
                continue

            # Circuit-breaker guard: skip disks whose circuit is currently OPEN
            # (too many consecutive I/O failures in previous scans).
            if breaker.is_open(disk.uuid):
                log.warning(
                    "indexer.disk.breaker_open",
                    disk_uuid=disk.uuid,
                    label=disk.label,
                    reason="circuit_open_skip",
                )
                continue

            # Guard: verify disk is mounted and identity sentinel matches.
            try:
                guard_disk_mounted(disk)
            except DiskUnmountedError as exc:
                log.warning(
                    "indexer.disk.skipped_unmounted",
                    disk_id=disk.id,
                    label=disk.label,
                    reason=str(exc),
                )
                continue
            except DiskMismatchError as exc:
                log.warning(
                    "indexer.scan.disk_skipped",
                    disk_id=disk.id,
                    label=disk.label,
                    reason=str(exc),
                )
                continue

            mount = disk.mount_path
            log.info("indexer.scan.disk_start", disk_id=disk.id, label=disk.label, mount_path=mount)

            try:
                if mode == ScanMode.full:
                    # Full-mode walk with optional index drop + batched inserts.
                    _scan_disk_full(
                        conn,
                        disk,
                        mount,
                        files_visited,
                        dirs_visited,
                        generation,
                        drop_indexes,
                        _resume_from,
                        _files_since_checkpoint,
                        _budget_exhausted,
                        _started_at_monotonic,
                        budget_seconds,
                        scan_run_id,
                        checkpoint_every_n_files,
                    )
                    if not _budget_exhausted[0]:
                        # Write-through the path row for the disk root.
                        try:
                            root_st = os.stat(mount, follow_symlinks=False)
                            _upsert_path_row(conn, disk.id, ".", root_st.st_mtime_ns)
                            dirs_visited[0] += 1
                        except OSError:
                            log.warning("indexer.scan.root_stat_failed", mount_path=mount)
                elif mode == ScanMode.quick:
                    # Quick-mode: Merkle short-circuit then dir-mtime walk.
                    _scan_disk_quick(
                        conn,
                        disk,
                        mount,
                        files_visited,
                        dirs_visited,
                        generation,
                        disks_skipped,
                        dir_mtime_reliable,
                        _resume_from,
                        _files_since_checkpoint,
                        _budget_exhausted,
                        _started_at_monotonic,
                        budget_seconds,
                        scan_run_id,
                        checkpoint_every_n_files,
                        confirm_bulk_change=confirm_bulk_change,
                        merkle_delta_freeze_threshold=merkle_delta_freeze_threshold,
                    )
                elif mode == ScanMode.incremental:
                    # Incremental-mode: quick semantics + OSHash recompute on tier-1
                    # mismatch for rename detection and content-drift classification.
                    _scan_disk_incremental(
                        conn,
                        disk,
                        mount,
                        files_visited,
                        dirs_visited,
                        generation,
                        disks_skipped,
                        dir_mtime_reliable,
                        _resume_from,
                        _files_since_checkpoint,
                        _budget_exhausted,
                        _started_at_monotonic,
                        budget_seconds,
                        scan_run_id,
                        checkpoint_every_n_files,
                        confirm_bulk_change=confirm_bulk_change,
                        merkle_delta_freeze_threshold=merkle_delta_freeze_threshold,
                    )
                elif mode == ScanMode.enrich:
                    # Enrich mode: pymediainfo + NFO + artwork on un-enriched rows,
                    # budget-bounded, per-file commits.
                    _scan_disk_enrich(
                        conn,
                        disk,
                        budget_seconds,
                        _started_at_monotonic,
                        _budget_exhausted,
                        scan_run_id,
                        quick_enrich=quick_enrich,
                    )
                else:
                    # Skeleton walk for any future modes not yet implemented.
                    _walk_dir(
                        conn,
                        disk,
                        mount,
                        files_visited,
                        dirs_visited,
                        generation,
                        _resume_from,
                        _files_since_checkpoint,
                        _budget_exhausted,
                        _started_at_monotonic,
                        budget_seconds,
                        scan_run_id,
                        checkpoint_every_n_files,
                    )
                    if not _budget_exhausted[0]:
                        # Write-through the path row for the disk root.
                        try:
                            root_st = os.stat(mount, follow_symlinks=False)
                            _upsert_path_row(conn, disk.id, ".", root_st.st_mtime_ns)
                            dirs_visited[0] += 1
                        except OSError:
                            log.warning("indexer.scan.root_stat_failed", mount_path=mount)

            except DiskBulkChangeDetected:
                # Merkle delta exceeded the freeze threshold — skip this disk
                # without modifying any DB rows.  The exception was already
                # logged by _scan_disk_quick; re-raise so the CLI layer can
                # surface an actionable message and return exit code 3.
                raise
            except OSError as io_exc:
                # I/O error on a disk walk (EIO, ENOENT, etc.).  Roll back any
                # partial writes for this disk, mark it unmounted, increment the
                # unreachable strike counter, and open the circuit if the threshold
                # is reached.  The scan continues on remaining disks.
                if io_exc.errno in (errno.EIO, errno.ENOENT, errno.ENOTCONN, errno.ETIMEDOUT):
                    conn.rollback()
                    disk_repo.update_is_mounted(conn, disk.id, is_mounted=0)
                    new_strikes = disk.unreachable_strikes + 1
                    disk_repo.update_unreachable_strikes(conn, disk.id, new_strikes)
                    breaker.record_failure(disk.uuid)
                    log.warning(
                        "indexer.disk.io_error",
                        disk_uuid=disk.uuid,
                        label=disk.label,
                        errno=io_exc.errno,
                        error=str(io_exc),
                        unreachable_strikes=new_strikes,
                    )
                    continue
                # Re-raise unexpected OS errors that are not disk-I/O related.
                raise
            except PermissionError as perm_exc:
                # Per-file EACCES: log a warning and continue (no strike against the disk).
                log.warning(
                    "indexer.file.permission_denied",
                    disk_uuid=disk.uuid,
                    label=disk.label,
                    error=str(perm_exc),
                )
                continue
            else:
                # Walk completed without I/O error — record success to allow
                # HALF_OPEN → CLOSED transition if the circuit was recovering.
                breaker.record_success(disk.uuid)

            log.info(
                "indexer.scan.disk_done",
                disk_id=disk.id,
                label=disk.label,
                files_visited=files_visited[0],
                dirs_visited=dirs_visited[0],
            )

            # Stop iterating disks if the budget was exhausted mid-walk.
            if _budget_exhausted[0]:
                break

        # Budget exhausted — commit current state and return early.
        if _budget_exhausted[0]:
            finished_at = int(time.time())
            stats: dict[str, int] = {
                "files_visited": files_visited[0],
                "dirs_visited": dirs_visited[0],
            }
            conn.execute(
                "UPDATE scan_run SET stats_json = ?, status = 'ok', finished_at = ? WHERE id = ?",
                (json.dumps(stats), finished_at, scan_run_id),
            )
            conn.commit()
            log.info(
                "indexer.scan.budget_exhausted",
                scan_run_id=scan_run_id,
                files_visited=files_visited[0],
                budget_seconds=budget_seconds,
            )
            return ScanRunResult(
                scan_run_id=scan_run_id,
                files_visited=files_visited[0],
                dirs_visited=dirs_visited[0],
                status="ok",
                disks_skipped=disks_skipped[0],
                budget_exhausted=True,
            )

        # All disks processed — mark scan_run ok.
        finished_at = int(time.time())
        log_repo.update_scan_run_status(conn, scan_run_id, "ok", finished_at=finished_at)
        return ScanRunResult(
            scan_run_id=scan_run_id,
            files_visited=files_visited[0],
            dirs_visited=dirs_visited[0],
            status="ok",
            disks_skipped=disks_skipped[0],
        )

    except DiskBulkChangeDetected:
        # Bulk-change freeze: the scan_run row has already been set to 'running';
        # mark it failed to avoid leaving a dangling running row, then re-raise
        # so the CLI can surface an actionable message and return exit code 3.
        finished_at = int(time.time())
        log_repo.update_scan_run_status(conn, scan_run_id, "failed", finished_at=finished_at)
        raise
    except Exception as exc:
        # Unexpected failure — record it and re-raise.
        finished_at = int(time.time())
        log_repo.update_scan_run_status(
            conn,
            scan_run_id,
            "failed",
            finished_at=finished_at,
        )
        return ScanRunResult(
            scan_run_id=scan_run_id,
            files_visited=files_visited[0],
            dirs_visited=dirs_visited[0],
            status="failed",
            disks_skipped=disks_skipped[0],
            error=str(exc),
        )


__all__ = [
    "EXCLUDED_NAMES",
    "IndexerConfigError",
    "IndexerScanActiveError",
    "ScanMode",
    "ScanRunResult",
    "_build_disk_fingerprints",
    "_scan_disk_enrich",
    "_scan_disk_incremental",
    "_should_exclude",
    "_verify_dir_mtime_reliable",
    "filter_disks",
    "guard_disk_mounted",
    "os",
    "scan",
    "tempfile",
]

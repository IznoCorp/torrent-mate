"""Per-disk scan mode drivers.

Provides:
- :func:`_scan_disk_full` — full-mode walk with optional index drop + batched inserts.
- :func:`_scan_disk_quick` — quick-mode walk with Merkle short-circuit + dir-mtime walk.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any

from personalscraper.indexer.merkle import (
    DiskBulkChangeDetected,
    compute_merkle_delta,
    compute_merkle_root,
)
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner._db_writes import _flush_insert_buffer, _upsert_path_row
from personalscraper.indexer.scanner._index_ddl import _drop_secondary_indexes, _recreate_indexes
from personalscraper.indexer.scanner._walker import (
    _build_disk_fingerprints,
    _sample_fresh_fingerprints,
    _walk_dir_full_buffered,
    _walk_dir_quick,
)
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")


def _scan_disk_full(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    drop_indexes: bool,
    resume_from: list[str | None] | None = None,
    files_since_checkpoint: list[int] | None = None,
    budget_exhausted: list[bool] | None = None,
    started_at_monotonic: float = 0.0,
    budget_seconds: float | None = None,
    scan_run_id: int = 0,
    checkpoint_every: int = 100,
) -> None:
    """Run the full-mode walk for a single disk with optional index management.

    Wraps the :func:`_walk_dir_full` recursive walk.  When ``drop_indexes`` is
    ``True``, secondary indexes on ``media_file`` / ``media_stream`` are dropped
    before the walk and always recreated in a ``try/finally`` block, regardless
    of whether an exception occurs during the walk.

    New rows are accumulated in an ``insert_buffer``.  The buffer is flushed
    every :data:`_INSERT_BATCH_SIZE` rows (checked inside
    :func:`_walk_dir_full`) and once more at the end to drain any remainder.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being scanned.
        mount: Absolute mount point path.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation counter.
        drop_indexes: Whether to drop and recreate secondary indexes.
        resume_from: Single-element list holding the opaque path string of the last
            checkpoint (or ``None``).  Forwarded to :func:`_walk_dir_full_buffered`.
        files_since_checkpoint: Single-element mutable counter forwarded to the walk.
        budget_exhausted: Single-element flag; set to ``True`` when the time budget
            is exceeded inside the walk.
        started_at_monotonic: :func:`time.monotonic` timestamp forwarded to the walk.
        budget_seconds: Maximum wall-clock seconds; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row.
        checkpoint_every: How many files to process between checkpoint writes.
    """
    ddl_pairs: list[tuple[str, str]] = []
    if drop_indexes:
        ddl_pairs = _drop_secondary_indexes(conn)

    insert_buffer: list[Any] = []
    try:
        _walk_dir_full_buffered(
            conn,
            disk,
            mount,
            files_visited,
            dirs_visited,
            generation,
            insert_buffer,
            resume_from,
            files_since_checkpoint,
            budget_exhausted,
            started_at_monotonic,
            budget_seconds,
            scan_run_id,
            checkpoint_every,
        )
        # Flush any remaining rows that did not fill a full batch.
        _flush_insert_buffer(conn, insert_buffer)
    finally:
        if drop_indexes and ddl_pairs:
            _recreate_indexes(conn, ddl_pairs)


def _scan_disk_quick(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    disks_skipped: list[int],
    dir_mtime_reliable: bool,
    resume_from: list[str | None] | None = None,
    files_since_checkpoint: list[int] | None = None,
    budget_exhausted: list[bool] | None = None,
    started_at_monotonic: float = 0.0,
    budget_seconds: float | None = None,
    scan_run_id: int = 0,
    checkpoint_every: int = 100,
    confirm_bulk_change: bool = False,
    merkle_delta_freeze_threshold: float = 0.50,
) -> None:
    """Run the quick-mode walk for a single disk.

    Implements two levels of short-circuiting:

    1. **Merkle short-circuit** (cheapest): recompute the Merkle root from the
       existing ``media_file`` rows in the database.  If it equals
       ``disk.merkle_root``, the disk has not changed since the last scan —
       skip all filesystem access for this disk.

    2. **Dir-mtime walk** (on Merkle miss): walk the disk using
       :func:`_walk_dir_quick`, which skips unchanged subtrees by comparing
       the stored ``path.dir_mtime_ns`` to the current filesystem value.

    On Merkle miss (stored root differs from DB-computed root), a bulk-change
    check is performed by sampling fresh tier-1 fingerprints from ``os.scandir``
    and computing the Merkle delta against stored.  If the delta exceeds
    *merkle_delta_freeze_threshold* and *confirm_bulk_change* is ``False``,
    the disk is skipped (no walk performed) and
    :class:`~personalscraper.indexer.merkle.DiskBulkChangeDetected` is raised
    to signal the caller.

    After a successful dir-mtime walk, the disk's Merkle root is recomputed
    from the updated ``media_file`` state and stored on ``disk.merkle_root``
    so the *next* quick scan can use the short-circuit.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being scanned.
        mount: Absolute mount point path.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation counter.
        disks_skipped: Single-element mutable counter for Merkle-hit skips.
        dir_mtime_reliable: Whether the dir-mtime skip optimisation is enabled
            for this scan session (from :func:`_verify_dir_mtime_reliable`).
        resume_from: Single-element list holding the opaque path string of the last
            checkpoint (or ``None``).  Forwarded to :func:`_walk_dir_quick`.
        files_since_checkpoint: Single-element mutable counter forwarded to
            :func:`_walk_dir_quick`.
        budget_exhausted: Single-element flag; set to ``True`` when the time budget
            is exceeded inside :func:`_walk_dir_quick`.
        started_at_monotonic: :func:`time.monotonic` timestamp forwarded to the
            walk helper.
        budget_seconds: Maximum wall-clock seconds; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row.
        checkpoint_every: How many files to process between checkpoint writes.
        confirm_bulk_change: When ``True``, bypass the Merkle delta freeze check
            and proceed with the walk even if the delta is high.  Corresponds to
            the ``--confirm-bulk-change`` CLI flag.
        merkle_delta_freeze_threshold: Halt if the Merkle delta exceeds this
            fraction (0.0–1.0).  Sourced from
            ``IndexerDriftConfig.merkle_delta_freeze_threshold``.

    Raises:
        DiskBulkChangeDetected: When the Merkle delta exceeds
            *merkle_delta_freeze_threshold* and *confirm_bulk_change* is
            ``False``.  The caller should skip this disk and surface an
            actionable message to the user.
    """
    # --- Merkle short-circuit ---
    fingerprints = _build_disk_fingerprints(conn, disk.id)
    current_root = compute_merkle_root(fingerprints)

    if disk.merkle_root is not None and current_root == disk.merkle_root:
        # DB-computed root matches stored root → disk unchanged, skip walk.
        log.info("indexer.scan.merkle_match", disk_uuid=disk.uuid, label=disk.label, merkle_root=current_root)
        disks_skipped[0] += 1
        return

    log.info(
        "indexer.scan.merkle_miss",
        disk_uuid=disk.uuid,
        label=disk.label,
        stored_root=disk.merkle_root,
        computed_root=current_root,
    )

    # --- Bulk-change guard (quick-mode only, on Merkle miss) ---
    # Sample fresh tier-1 fingerprints by doing a shallow scandir for all
    # media_file paths already known to the DB and comparing size/mtime_ns.
    # A high delta (many files changed at once) suggests a bulk restore or
    # disk swap rather than organic drift — freeze unless confirmed by caller.
    if not confirm_bulk_change and disk.merkle_root is not None:
        fresh_fps = _sample_fresh_fingerprints(conn, disk.id, mount)
        delta = compute_merkle_delta(fingerprints, fresh_fps)
        if delta > merkle_delta_freeze_threshold:
            log.warning(
                "indexer.merkle.delta_freeze",
                disk_uuid=disk.uuid,
                label=disk.label,
                delta=delta,
                threshold=merkle_delta_freeze_threshold,
            )
            raise DiskBulkChangeDetected(delta=delta, disk_uuid=disk.uuid)

    # --- Dir-mtime walk ---
    _walk_dir_quick(
        conn,
        disk,
        mount,
        files_visited,
        dirs_visited,
        generation,
        dir_mtime_reliable,
        resume_from,
        files_since_checkpoint,
        budget_exhausted,
        started_at_monotonic,
        budget_seconds,
        scan_run_id,
        checkpoint_every,
    )

    # Skip post-walk bookkeeping if the budget was exhausted during the walk —
    # the partial state is preserved for crash-resume; Merkle root must not be
    # updated to an incomplete snapshot.
    if budget_exhausted is not None and budget_exhausted[0]:
        return

    # Write-through the path row for the disk root itself.
    try:
        root_st = os.stat(mount, follow_symlinks=False)
        _upsert_path_row(conn, disk.id, ".", root_st.st_mtime_ns)
    except OSError:
        log.warning("indexer.scan.root_stat_failed", mount_path=mount)

    # Recompute and persist the updated Merkle root so the next quick scan
    # can short-circuit if the FS state is unchanged.
    updated_fingerprints = _build_disk_fingerprints(conn, disk.id)
    new_root = compute_merkle_root(updated_fingerprints)
    disk_repo.update_merkle_root(conn, disk.id, new_root)
    log.debug("indexer.scan.merkle_root_updated", disk_id=disk.id, merkle_root=new_root)

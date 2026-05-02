"""Per-disk scan mode drivers.

Provides:
- :func:`_scan_disk_full` — full-mode walk with optional index drop + batched inserts.
- :func:`_scan_disk_quick` — quick-mode walk with Merkle short-circuit + dir-mtime walk.
- :func:`_scan_disk_incremental` — incremental walk: quick semantics + OSHash recompute on
  tier-1 mismatch with rename-detection and content-drift repair enqueue.
- :func:`_scan_disk_enrich` — enrich mode: pymediainfo + NFO presence check + artwork
  inventory on rows where ``enriched_at IS NULL``, budget-bounded, per-file commits.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Literal

from personalscraper.indexer import drift as _drift
from personalscraper.indexer.mediainfo import MediaInfoUnavailableError, MediaInfoWrapper
from personalscraper.indexer.merkle import (
    DiskBulkChangeDetected,
    compute_merkle_delta,
    compute_merkle_root,
)
from personalscraper.indexer.release_linker import link_file_to_release
from personalscraper.indexer.repos import disk_repo, file_repo
from personalscraper.indexer.scanner._db_writes import (
    _compute_oshash,
    _flush_insert_buffer,
    _safe_mtime_ns,
    _upsert_file_row,
    _upsert_path_row,
)
from personalscraper.indexer.scanner._exclusions import _relpath, _should_exclude
from personalscraper.indexer.scanner._index_ddl import _drop_secondary_indexes, _recreate_indexes
from personalscraper.indexer.scanner._walker import (
    _build_disk_fingerprints,
    _sample_fresh_fingerprints,
    _walk_dir_full_buffered,
    _walk_dir_quick,
)
from personalscraper.indexer.schema import ArtworkInventory, DiskRow, MediaStreamRow
from personalscraper.logger import get_logger
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS as _VIDEO_EXTENSIONS

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


def _run_paranoia_branch(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    paranoia_window_seconds: int,
) -> None:
    """Check recent outbox events and log paths that may need re-fingerprinting.

    Queries ``scan_event`` for rows with ``event LIKE 'outbox.%'`` within the
    last *paranoia_window_seconds* seconds.  For each matching row, extracts
    the ``rel_path`` field from ``payload_json``, builds the absolute path,
    and compares the on-disk stat to the stored ``media_file`` row.

    When a mismatch is detected (size or mtime_ns differs from the stored row),
    logs ``indexer.scan.paranoia_recheck`` for that path.  The actual
    re-fingerprinting is deferred to the subsequent dir-mtime walk or a later
    sub-phase; this branch only surfaces the discrepancy (DESIGN §17.1).

    Paths that do not exist on disk, fall outside *mount*, or whose
    ``payload_json`` lacks a ``rel_path`` field are silently skipped.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being scanned.
        mount: Absolute mount point path for the disk.
        paranoia_window_seconds: How far back (in seconds) to look for outbox
            events.  Must be positive (caller already guards against 0).
    """
    cutoff_ts = int(time.time()) - paranoia_window_seconds
    mount_path = Path(mount)

    # Fetch distinct payload blobs from recent outbox events.
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT DISTINCT payload_json FROM scan_event WHERE event LIKE 'outbox.%' AND ts > ?",
        (cutoff_ts,),
    ).fetchall()
    conn.row_factory = None

    paths_inspected = 0
    for row in rows:
        payload_json: str | None = row["payload_json"]
        if not payload_json:
            continue

        # Parse the JSON payload and extract rel_path.  Rows without rel_path
        # cannot be resolved to a filesystem path — skip them silently.
        try:
            payload: dict[str, object] = json.loads(payload_json)
        except (json.JSONDecodeError, TypeError):
            continue

        rel_path = payload.get("rel_path")
        if not rel_path or not isinstance(rel_path, str):
            continue

        # Build the absolute path and verify it is anchored under mount.
        abs_path = mount_path / rel_path
        try:
            abs_path.resolve().relative_to(mount_path.resolve())
        except ValueError:
            # Path escapes the mount root (e.g. via ``..`` components) — skip.
            continue

        if not abs_path.exists():
            continue

        paths_inspected += 1

        # Re-stat the file and compare to the stored media_file row (if any).
        try:
            st = abs_path.stat()
        except OSError:
            continue

        # Look up the stored row by joining path.rel_path + media_file.filename.
        # Root-level files use rel_path="" (matching _relpath strip logic), NOT ".".
        filename = abs_path.name
        if abs_path.parent == mount_path:
            parent_rel = ""
        else:
            parent_rel = str(abs_path.parent.relative_to(mount_path))

        conn.row_factory = sqlite3.Row
        stored = conn.execute(
            """
            SELECT mf.id, mf.size_bytes, mf.mtime_ns
              FROM media_file mf
              JOIN path p ON p.id = mf.path_id
             WHERE p.disk_id = ?
               AND p.rel_path = ?
               AND mf.filename = ?
               AND mf.deleted_at IS NULL
             LIMIT 1
            """,
            (disk.id, parent_rel, filename),
        ).fetchone()
        conn.row_factory = None

        if stored is None:
            # No stored row — the file is new; the normal walker will handle it.
            continue

        stored_size: int = stored["size_bytes"] or 0
        stored_mtime_ns: int = stored["mtime_ns"] or 0

        if st.st_size != stored_size or st.st_mtime_ns != stored_mtime_ns:
            # Tier-1 mismatch detected via paranoia branch: dir-mtime was stale
            # or unupdated, but the file has actually changed.  Log the event so
            # operators and metrics pipelines can track detection coverage.
            log.info(
                "indexer.scan.paranoia_recheck",
                disk_uuid=disk.uuid,
                label=disk.label,
                rel_path=rel_path,
                stored_size=stored_size,
                current_size=st.st_size,
                stored_mtime_ns=stored_mtime_ns,
                current_mtime_ns=st.st_mtime_ns,
            )

    log.info(
        "indexer.scan.paranoia_branch",
        disk_uuid=disk.uuid,
        label=disk.label,
        paths_inspected=paths_inspected,
        cutoff_ts=cutoff_ts,
        window_seconds=paranoia_window_seconds,
    )


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
    paranoia_window_seconds: int = 86400,
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
        paranoia_window_seconds: Look-back window for the paranoia branch
            (DESIGN §17.1).  ``scan_event`` rows with ``event LIKE 'outbox.%'``
            created within this many seconds of now are re-checked against
            on-disk state regardless of dir-mtime status.  ``0`` disables the
            branch.  Sourced from ``IndexerScanConfig.paranoia_window_seconds``.

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

    # --- Paranoia branch (DESIGN §17.1) ---
    # On Merkle miss, query recent outbox events and force a re-stat for any
    # paths they reference that fall under this disk's mount point.  This
    # shortens the detection gap for files changed by the outbox pipeline
    # without touching the parent directory mtime (e.g. in-place content
    # rewrites or cross-directory moves whose parent dir mtime is unreliable).
    #
    # The branch is ADDITIVE: the normal dir-mtime walk still runs below.
    # Its sole job here is to surface paths that dir-mtime would falsely
    # treat as unchanged, so they can be flagged for re-fingerprinting.
    # Full re-fingerprinting integration deferred to a later sub-phase;
    # for now we log ``indexer.scan.paranoia_recheck`` for each detected path.
    if paranoia_window_seconds > 0:
        _run_paranoia_branch(conn, disk, mount, paranoia_window_seconds)

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


def _scan_disk_incremental(
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
    """Run the incremental-mode walk for a single disk.

    Incremental mode builds on quick-mode semantics (Merkle short-circuit +
    dir-mtime subtree skip) but adds an OSHash recompute step for every file
    whose tier-1 fingerprint (size, mtime_ns, ctime_ns) differs from the stored
    value.  This allows the scanner to distinguish:

    - **Mtime/size drift only** (content unchanged): update tier-1 fields, no
      repair enqueue.
    - **Rename** (same content, different path): delegate to
      :func:`~personalscraper.indexer.drift.detect_rename`; the drift module
      updates the ``path_id`` / ``filename`` in-place.
    - **OSHash collision** (multiple candidates with the same hash): the drift
      module enqueues repair for the ambiguous rows.
    - **Real content drift** (oshash changed): call
      :func:`~personalscraper.indexer.drift.enqueue_repair` with
      ``reason='content_drift'``.

    The incremental walk uses the same Merkle short-circuit guard as quick mode:
    if the DB-computed Merkle root matches ``disk.merkle_root`` the entire disk
    is skipped.  On Merkle miss, a bulk-change check samples fresh fingerprints
    to protect against accidental mass-restores.

    After a successful walk, the disk's Merkle root is recomputed from the
    updated ``media_file`` state and stored so the next scan can short-circuit.

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
            checkpoint (or ``None``).
        files_since_checkpoint: Single-element mutable counter forwarded to
            the inner walk.
        budget_exhausted: Single-element flag; set to ``True`` when the time budget
            is exceeded inside the walk.
        started_at_monotonic: :func:`time.monotonic` timestamp forwarded to the walk.
        budget_seconds: Maximum wall-clock seconds; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row.
        checkpoint_every: How many files to process between checkpoint writes.
        confirm_bulk_change: When ``True``, bypass the Merkle delta freeze guard
            and proceed with the walk even when the delta exceeds
            *merkle_delta_freeze_threshold*.
        merkle_delta_freeze_threshold: Halt if the Merkle delta exceeds this
            fraction (0.0–1.0).

    Raises:
        DiskBulkChangeDetected: When the Merkle delta exceeds
            *merkle_delta_freeze_threshold* and *confirm_bulk_change* is ``False``.
    """
    # --- Merkle short-circuit (same as quick mode) ---
    fingerprints = _build_disk_fingerprints(conn, disk.id)
    current_root = compute_merkle_root(fingerprints)

    if disk.merkle_root is not None and current_root == disk.merkle_root:
        log.info(
            "indexer.scan.merkle_match",
            disk_uuid=disk.uuid,
            label=disk.label,
            merkle_root=current_root,
        )
        disks_skipped[0] += 1
        return

    log.info(
        "indexer.scan.merkle_miss",
        disk_uuid=disk.uuid,
        label=disk.label,
        stored_root=disk.merkle_root,
        computed_root=current_root,
    )

    # --- Bulk-change guard (same as quick mode, on Merkle miss) ---
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

    # --- Incremental walk ---
    _walk_dir_incremental(
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

    # Skip post-walk bookkeeping if the budget was exhausted — partial state is
    # preserved for crash-resume; Merkle root must not be updated to an incomplete
    # snapshot.
    if budget_exhausted is not None and budget_exhausted[0]:
        return

    # Write-through the path row for the disk root itself.
    try:
        root_st = os.stat(mount, follow_symlinks=False)
        _upsert_path_row(conn, disk.id, ".", root_st.st_mtime_ns)
    except OSError:
        log.warning("indexer.scan.root_stat_failed", mount_path=mount)

    # Recompute and persist the updated Merkle root.
    updated_fingerprints = _build_disk_fingerprints(conn, disk.id)
    new_root = compute_merkle_root(updated_fingerprints)
    disk_repo.update_merkle_root(conn, disk.id, new_root)
    log.debug("indexer.scan.merkle_root_updated", disk_id=disk.id, merkle_root=new_root)


def _walk_dir_incremental(
    conn: sqlite3.Connection,
    disk: DiskRow,
    dir_abs: str,
    files_visited: list[int],
    dirs_visited: list[int],
    generation: int,
    dir_mtime_reliable: bool,
    resume_from: list[str | None] | None = None,
    files_since_checkpoint: list[int] | None = None,
    budget_exhausted: list[bool] | None = None,
    started_at_monotonic: float = 0.0,
    budget_seconds: float | None = None,
    scan_run_id: int = 0,
    checkpoint_every: int = 100,
) -> None:
    """Recursively walk *dir_abs* in incremental mode.

    Incremental mode extends quick-mode dir-mtime subtree skipping with an
    OSHash recompute step for files whose tier-1 fingerprint has changed.  The
    OSHash comparison enables accurate rename detection and distinguishes
    cosmetic mtime drift from real content changes.

    Per-file logic for files with a tier-1 mismatch against the stored row:

    1. Recompute OSHash for video files (non-video/symlinks skip this step).
    2. Compare the recomputed hash to the stored ``oshash`` column:

       a. **Match** — content is unchanged (mtime/size drift only): update tier-1
          fields in place, no repair enqueue.
       b. **Mismatch and oshash is not empty** — call
          :func:`~personalscraper.indexer.drift.detect_rename`:

          - ``rename_applied`` → drift module already updated the row.
          - ``oshash_collision`` → drift module already enqueued repair.
          - ``no_match`` → real content drift; call
            :func:`~personalscraper.indexer.drift.enqueue_repair` with
            ``reason='content_drift'``.

       c. **Mismatch and no oshash** (non-video file) — treat as content drift
          and enqueue repair directly.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` owning this subtree.
        dir_abs: Absolute path of the current directory.
        files_visited: Single-element mutable counter for files.
        dirs_visited: Single-element mutable counter for directories.
        generation: Scan generation stamped on every ``media_file`` row.
        dir_mtime_reliable: When ``False``, dir-mtime skip is disabled.
        resume_from: Single-element list holding the opaque path string of the
            last checkpoint (or ``None``).
        files_since_checkpoint: Single-element mutable counter.
        budget_exhausted: Single-element flag; set to ``True`` when budget exceeded.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start.
        budget_seconds: Maximum wall-clock seconds; ``None`` = unlimited.
        scan_run_id: PK of the active ``scan_run`` row.
        checkpoint_every: How many files to process between checkpoint writes.
    """
    from personalscraper.indexer.scanner._checkpoint import _maybe_checkpoint  # noqa: PLC0415

    assert disk.mount_path is not None  # guard: mount_path checked before entering walk

    if budget_exhausted is not None and budget_exhausted[0]:
        return

    try:
        with os.scandir(dir_abs) as it:
            entries = list(it)
    except PermissionError:
        log.warning("indexer.scan.dir_permission_denied", path=dir_abs)
        return

    for entry in entries:
        if _should_exclude(entry.name):
            continue

        try:
            st = entry.stat(follow_symlinks=False)
        except OSError:
            log.warning("indexer.scan.stat_failed", path=entry.path)
            continue

        if entry.is_dir(follow_symlinks=False):
            dirs_visited[0] += 1
            rel = _relpath(disk.mount_path, entry.path)
            current_mtime_ns: int = st.st_mtime_ns

            if dir_mtime_reliable:
                # Check stored dir_mtime_ns — skip unchanged subtrees.
                existing_path = disk_repo.get_path_by_disk_and_relpath(conn, disk.id, rel)
                if existing_path is not None and existing_path.dir_mtime_ns == current_mtime_ns:
                    log.debug(
                        "indexer.scan.dir_unchanged",
                        path=entry.path,
                        dir_mtime_ns=current_mtime_ns,
                    )
                    continue

            # Recurse into changed (or all, when dir-mtime is unreliable) subtrees.
            _walk_dir_incremental(
                conn,
                disk,
                entry.path,
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

            if budget_exhausted is not None and budget_exhausted[0]:
                return

            # Update dir_mtime_ns so next scan can short-circuit.
            _upsert_path_row(conn, disk.id, rel, current_mtime_ns)

        else:
            # File (or symlink) — incremental fingerprint logic.

            # --- crash-resume skip ---
            if resume_from is not None and resume_from[0] is not None:
                parent_rel_r = _relpath(disk.mount_path, dir_abs)
                current_path_str_r = f"{disk.label}/{parent_rel_r}/{entry.name}"
                if current_path_str_r <= resume_from[0]:
                    continue
                resume_from[0] = None

            files_visited[0] += 1
            parent_rel = _relpath(disk.mount_path, dir_abs)
            path_id = _upsert_path_row(conn, disk.id, parent_rel, 0)
            ctime_ns_val: int | None = st.st_ctime_ns if hasattr(st, "st_ctime_ns") else None
            mtime_ns_val = _safe_mtime_ns(st.st_mtime_ns)
            is_symlink = entry.is_symlink()

            existing = file_repo.find_by_path_and_filename(conn, path_id, entry.name)

            if existing is None:
                # New file — compute oshash.  For video files attempt rename
                # detection before inserting a fresh row.  A rename appears as
                # a new path whose oshash matches an existing DB row at a
                # different location (the old location is now gone from disk).
                oshash_value = _compute_oshash(entry.path, entry.name, is_symlink)

                if oshash_value is not None:
                    # Check whether a candidate with this oshash already exists
                    # on the disk at a different path.  If so, try rename
                    # detection first so we don't hit the UNIQUE constraint
                    # (path_id, filename) when the old row is updated in place.
                    conn.row_factory = sqlite3.Row
                    candidate = conn.execute(
                        """
                        SELECT mf.id
                          FROM media_file mf
                          JOIN path p ON p.id = mf.path_id
                         WHERE mf.oshash = ?
                           AND p.disk_id = ?
                           AND NOT (mf.path_id = ? AND mf.filename = ?)
                           AND mf.deleted_at IS NULL
                         LIMIT 1
                        """,
                        (oshash_value, disk.id, path_id, entry.name),
                    ).fetchone()
                    conn.row_factory = None

                    if candidate is not None:
                        # There is at least one existing row with this oshash —
                        # insert a temporary stub row so detect_rename can use
                        # the current (path_id, filename, size) for its size guard
                        # and old-path-existence check.
                        _upsert_file_row(
                            conn,
                            path_id=path_id,
                            filename=entry.name,
                            size_bytes=st.st_size,
                            mtime_ns=mtime_ns_val,
                            ctime_ns=ctime_ns_val,
                            generation=generation,
                            oshash_value=oshash_value,
                        )
                        # Now detect_rename can query (path_id, filename) to get
                        # current size. If it applies a rename, it UPDATES the old
                        # row to (path_id, filename) — but that would collide with
                        # the stub row we just inserted.  To avoid the UNIQUE
                        # constraint, delete the stub first then let detect_rename
                        # update the old row.
                        conn.execute(
                            "DELETE FROM media_file WHERE path_id = ? AND filename = ? AND oshash = ?",
                            (path_id, entry.name, oshash_value),
                        )
                        outcome = _drift.detect_rename(
                            conn,
                            disk.id,
                            path_id,
                            entry.name,
                            oshash_value,
                        )
                        if outcome == "rename_applied":
                            # The old row was updated in-place to (path_id, entry.name).
                            # Update its tier-1 fields to reflect the current stat.
                            conn.execute(
                                """
                                UPDATE media_file
                                   SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                                       scan_generation = ?
                                 WHERE path_id = ? AND filename = ?
                                """,
                                (st.st_size, mtime_ns_val, ctime_ns_val, generation, path_id, entry.name),
                            )
                            log.info(
                                "indexer.scan.incremental.rename_applied",
                                new_path_id=path_id,
                                new_filename=entry.name,
                            )
                        else:
                            # no_match or oshash_collision — insert as a new file.
                            _upsert_file_row(
                                conn,
                                path_id=path_id,
                                filename=entry.name,
                                size_bytes=st.st_size,
                                mtime_ns=mtime_ns_val,
                                ctime_ns=ctime_ns_val,
                                generation=generation,
                                oshash_value=oshash_value,
                            )
                    else:
                        # No candidate with this oshash on this disk — genuinely
                        # new file, plain insert.
                        _upsert_file_row(
                            conn,
                            path_id=path_id,
                            filename=entry.name,
                            size_bytes=st.st_size,
                            mtime_ns=mtime_ns_val,
                            ctime_ns=ctime_ns_val,
                            generation=generation,
                            oshash_value=oshash_value,
                        )
                else:
                    # Non-video file (no oshash) — plain insert, no rename detection.
                    _upsert_file_row(
                        conn,
                        path_id=path_id,
                        filename=entry.name,
                        size_bytes=st.st_size,
                        mtime_ns=mtime_ns_val,
                        ctime_ns=ctime_ns_val,
                        generation=generation,
                        oshash_value=None,
                    )
            else:
                # Existing file — compare tier-1 fingerprint.
                t1_stored = (existing.size_bytes, existing.mtime_ns, existing.ctime_ns or 0)
                t1_current = (st.st_size, mtime_ns_val, ctime_ns_val or 0)

                if t1_current == t1_stored:
                    # Tier-1 unchanged — bump generation only (cheap skip).
                    conn.execute(
                        "UPDATE media_file SET scan_generation = ? WHERE id = ?",
                        (generation, existing.id),
                    )
                else:
                    # Tier-1 mismatch — recompute OSHash for video files to determine
                    # whether the content actually changed or just the metadata.
                    new_oshash = _compute_oshash(entry.path, entry.name, is_symlink)

                    if new_oshash is not None and new_oshash == existing.oshash:
                        # OSHash matches stored value: content unchanged (mtime drift
                        # only).  Update tier-1 fields; no repair enqueue needed.
                        conn.execute(
                            """
                            UPDATE media_file
                               SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                                   scan_generation = ?
                             WHERE id = ?
                            """,
                            (st.st_size, mtime_ns_val, ctime_ns_val, generation, existing.id),
                        )
                        log.debug(
                            "indexer.scan.incremental.tier1_drift_only",
                            file_id=existing.id,
                            filename=entry.name,
                        )
                    elif new_oshash is not None:
                        # OSHash changed — attempt rename detection via drift module.
                        # First persist updated tier-1 and the new oshash so
                        # detect_rename can find the current row by path.
                        conn.execute(
                            """
                            UPDATE media_file
                               SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                                   oshash = ?, scan_generation = ?
                             WHERE id = ?
                            """,
                            (st.st_size, mtime_ns_val, ctime_ns_val, new_oshash, generation, existing.id),
                        )
                        outcome = _drift.detect_rename(
                            conn,
                            disk.id,
                            path_id,
                            entry.name,
                            new_oshash,
                        )
                        if outcome == "no_match":
                            # No rename candidate found — this is real content drift.
                            _drift.enqueue_repair(conn, existing.id, "content_drift")
                            log.info(
                                "indexer.scan.incremental.content_drift",
                                file_id=existing.id,
                                filename=entry.name,
                            )
                        # rename_applied and oshash_collision are handled by drift module.
                    else:
                        # Non-video file (no oshash available) with tier-1 mismatch —
                        # treat as content drift; update tier-1 and enqueue repair.
                        conn.execute(
                            """
                            UPDATE media_file
                               SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
                                   scan_generation = ?
                             WHERE id = ?
                            """,
                            (st.st_size, mtime_ns_val, ctime_ns_val, generation, existing.id),
                        )
                        _drift.enqueue_repair(conn, existing.id, "content_drift")
                        log.info(
                            "indexer.scan.incremental.content_drift_no_oshash",
                            file_id=existing.id,
                            filename=entry.name,
                        )

            # --- checkpoint / budget check ---
            if files_since_checkpoint is not None and budget_exhausted is not None:
                files_since_checkpoint[0] += 1
                parent_rel_c = _relpath(disk.mount_path, dir_abs)
                current_path_str_c = f"{disk.label}/{parent_rel_c}/{entry.name}"
                new_counter, exhausted = _maybe_checkpoint(
                    conn,
                    scan_run_id,
                    current_path_str_c,
                    files_since_checkpoint[0],
                    checkpoint_every,
                    started_at_monotonic,
                    budget_seconds,
                )
                files_since_checkpoint[0] = new_counter
                if exhausted:
                    budget_exhausted[0] = True
                    return


# ---------------------------------------------------------------------------
# Artwork filename constants
# ---------------------------------------------------------------------------

# Canonical artwork filenames checked during enrich (case-insensitive on macOS
# but we match lowercase to avoid double-hitting).
_ARTWORK_FILENAMES: dict[str, str] = {
    "poster.jpg": "poster",
    "poster.png": "poster",
    "fanart.jpg": "fanart",
    "fanart.png": "fanart",
    "banner.jpg": "banner",
    "banner.png": "banner",
    "landscape.jpg": "landscape",
    "landscape.png": "landscape",
    "clearlogo.png": "clearlogo",
    "clearlogo.jpg": "clearlogo",
    "clearart.png": "clearart",
    "clearart.jpg": "clearart",
    "discart.png": "discart",
    "discart.jpg": "discart",
    "characterart.png": "characterart",
    "characterart.jpg": "characterart",
}


def _inventory_artwork(parent_dir: str) -> ArtworkInventory | None:
    """Scan *parent_dir* for known artwork filenames and return an :class:`ArtworkInventory`.

    Only the presence of a file is checked — no content validation is performed.
    Each artwork type resolves to ``True`` as soon as *any* matching filename is
    found in the directory.

    Args:
        parent_dir: Absolute path of the directory to scan.

    Returns:
        :class:`ArtworkInventory` instance reflecting what artwork files exist,
        or ``None`` when the directory is not readable (transient OS error).
        Callers must skip the DB column update when ``None`` is returned so that
        previously-valid data is not overwritten on a transient permission error.
    """
    found: dict[str, bool] = {}
    try:
        with os.scandir(parent_dir) as it:
            for entry in it:
                key = _ARTWORK_FILENAMES.get(entry.name.lower())
                if key is not None:
                    found[key] = True
    except OSError as exc:
        # Directory temporarily unreadable — preserve the existing DB value.
        log.warning(
            "indexer.enrich.artwork_inventory_failed",
            parent_dir=parent_dir,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None

    return ArtworkInventory(
        poster=found.get("poster", False),
        fanart=found.get("fanart", False),
        landscape=found.get("landscape", False),
        banner=found.get("banner", False),
        clearlogo=found.get("clearlogo", False),
        clearart=found.get("clearart", False),
        discart=found.get("discart", False),
        characterart=found.get("characterart", False),
    )


def _check_nfo_status(parent_dir: str) -> Literal["missing", "invalid", "valid"] | None:
    """Check whether a ``.nfo`` file exists in *parent_dir* and return a status string.

    Full NFO parsing (XML validation) is deferred to the scraper integration phases.
    This function performs only a file-existence check:

    - ``'valid'`` — a ``.nfo`` file is present (we cannot validate content yet).
    - ``'missing'`` — no ``.nfo`` file found.
    - ``None`` — the directory scan raised an :exc:`OSError` (transient permission
      error or filesystem hiccup); the caller must skip the DB column update so that
      previously-valid data is not overwritten.

    Args:
        parent_dir: Absolute path of the directory to inspect.

    Returns:
        ``'valid'`` if any ``.nfo`` file exists in *parent_dir*, ``'missing'`` if
        none are found, or ``None`` when the directory is not readable.
    """
    try:
        with os.scandir(parent_dir) as it:
            for entry in it:
                if entry.name.lower().endswith(".nfo"):
                    return "valid"
    except OSError as exc:
        # Directory temporarily unreadable — preserve the existing DB value.
        log.warning(
            "indexer.enrich.nfo_check_failed",
            parent_dir=parent_dir,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None
    return "missing"


def _enrich_one_file(
    conn: sqlite3.Connection,
    file_id: int,
    file_path: Path,
    item_id: int | None,
    wrapper: MediaInfoWrapper | None,
) -> None:
    """Enrich a single ``media_file`` row with streams, NFO status, and artwork.

    Performs three enrichment steps in order:

    1. **Stream extraction** — if *wrapper* is not ``None`` and the file is large
       enough, call :meth:`~personalscraper.indexer.mediainfo.MediaInfoWrapper.extract_streams`
       and INSERT the resulting :class:`~personalscraper.indexer.schema.MediaStreamRow` objects
       into ``media_stream``, replacing any existing rows for this ``file_id``.
    2. **NFO presence check** — inspect the parent directory for ``.nfo`` files and
       update ``media_item.nfo_status`` when *item_id* is not ``None``.
    3. **Artwork inventory** — scan the parent directory for known artwork filenames
       and update ``media_item.artwork_json`` when *item_id* is not ``None``.

    Finally, set ``media_file.enriched_at`` to the current epoch seconds.

    Args:
        conn: Open SQLite connection.  Caller is responsible for committing.
        file_id: PK of the ``media_file`` row to enrich.
        file_path: Absolute :class:`~pathlib.Path` to the media file.
        item_id: PK of the owning ``media_item``, or ``None`` if release linkage
            has not been performed yet.
        wrapper: Configured :class:`~personalscraper.indexer.mediainfo.MediaInfoWrapper`
            instance, or ``None`` when pymediainfo is unavailable.
    """
    now_s = int(time.time())
    parent_dir = str(file_path.parent)

    # --- Step 1: stream extraction ---
    if wrapper is not None:
        try:
            stream_rows: list[MediaStreamRow] = wrapper.extract_streams(file_path)
        except Exception:  # noqa: BLE001
            # Corrupt / unreadable file — skip stream extraction but still update
            # enriched_at so we do not re-attempt on every future enrich run.
            stream_rows = []

        if stream_rows:
            # Delete stale stream rows before re-inserting to keep the table clean.
            conn.execute("DELETE FROM media_stream WHERE file_id = ?", (file_id,))
            # Use a global 0-based index (enumerate) rather than the per-kind index
            # from MediaStreamRow.idx, which may collide across track types when the
            # UNIQUE(file_id, idx) constraint is file-scoped.
            conn.executemany(
                """
                INSERT INTO media_stream (file_id, idx, kind, codec, lang,
                    channels, width, height, duration_ms, bitrate,
                    hdr_format, is_atmos, is_default, forced, format)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        file_id,
                        global_idx,
                        row.kind,
                        row.codec,
                        row.lang,
                        row.channels,
                        row.width,
                        row.height,
                        row.duration_ms,
                        row.bitrate,
                        row.hdr_format,
                        None if row.is_atmos is None else int(row.is_atmos),
                        None if row.is_default is None else int(row.is_default),
                        None if row.forced is None else int(row.forced),
                        row.format,
                    )
                    for global_idx, row in enumerate(stream_rows)
                ],
            )

    # --- Steps 2 + 3: NFO status and artwork (only when release linkage exists) ---
    if item_id is not None:
        nfo_status = _check_nfo_status(parent_dir)
        artwork = _inventory_artwork(parent_dir)

        # Skip column updates when either scan returned None — a transient OS error
        # occurred and the existing DB values must be preserved rather than overwritten
        # with a spurious 'missing' / empty-inventory result.
        if nfo_status is not None and artwork is not None:
            conn.execute(
                "UPDATE media_item SET nfo_status = ?, artwork_json = ? WHERE id = ?",
                (nfo_status, artwork.model_dump_json(), item_id),
            )
        elif nfo_status is not None:
            conn.execute(
                "UPDATE media_item SET nfo_status = ? WHERE id = ?",
                (nfo_status, item_id),
            )
        elif artwork is not None:
            conn.execute(
                "UPDATE media_item SET artwork_json = ? WHERE id = ?",
                (artwork.model_dump_json(), item_id),
            )

    # --- Set enriched_at ---
    conn.execute(
        "UPDATE media_file SET enriched_at = ? WHERE id = ?",
        (now_s, file_id),
    )


def _scan_disk_enrich(
    conn: sqlite3.Connection,
    disk: DiskRow,
    budget_seconds: float | None,
    started_at_monotonic: float,
    budget_exhausted: list[bool],
    scan_run_id: int,
    quick_enrich: bool = False,
) -> None:
    """Run the enrich-mode pass for a single disk.

    Iterates ``media_file`` rows on this disk where ``enriched_at IS NULL`` or
    ``enriched_at < (mtime_ns / 1_000_000_000)`` (file has been modified since
    last enrichment), in priority order: files whose owning ``media_item`` was
    most recently modified first (``media_item.date_modified DESC``), with
    files that have no release linkage last.

    Per-file enrichment:

    1. Recompute file path from ``path.rel_path`` and ``media_file.filename``.
    2. Extract media streams via :class:`~personalscraper.indexer.mediainfo.MediaInfoWrapper`
       (skipped silently if ``libmediainfo`` is not installed).
    3. Check NFO presence in the file's parent directory.
    4. Inventory artwork in the file's parent directory.
    5. Update ``media_file.enriched_at`` to the current epoch seconds.
    6. **Commit after each file** so partial progress survives interruption.

    If the *budget_seconds* wall-clock limit is reached between files, the loop
    exits early and ``budget_exhausted[0]`` is set to ``True``.  Any files not
    yet enriched retain ``enriched_at=NULL`` and will be picked up by the next
    enrich run.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` to enrich.
        budget_seconds: Maximum wall-clock seconds for the entire enrich pass.
            ``None`` = unlimited.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start.
        budget_exhausted: Single-element flag; set to ``True`` when the budget
            is exceeded.  Mutated in-place so the caller can check it after return.
        scan_run_id: PK of the active ``scan_run`` row (used for stats update on
            budget exhaustion).
        quick_enrich: When ``True``, uses ``parse_speed=0.5`` for pymediainfo
            (faster but may skip optional tags).  Default ``False`` → ``parse_speed=1.0``.
    """
    if disk.mount_path is None:
        log.warning("indexer.enrich.disk_no_mount", disk_id=disk.id, label=disk.label)
        return

    parse_speed: float = 0.5 if quick_enrich else 1.0

    # Attempt to create the pymediainfo wrapper; degrade gracefully if unavailable.
    wrapper: MediaInfoWrapper | None
    try:
        wrapper = MediaInfoWrapper(min_size_mb=0, parse_speed=parse_speed)
    except MediaInfoUnavailableError:
        log.warning(
            "indexer.enrich.mediainfo_unavailable",
            disk_id=disk.id,
            label=disk.label,
        )
        wrapper = None

    # Query files that need enrichment, ordered by owning item's date_modified DESC.
    # Files with no release linkage (release_id IS NULL) sort last.
    conn.row_factory = sqlite3.Row
    pending = conn.execute(
        """
        SELECT mf.id            AS file_id,
               mf.filename      AS filename,
               mf.mtime_ns      AS mtime_ns,
               mf.release_id    AS release_id,
               p.rel_path       AS rel_path,
               mr.item_id       AS item_id
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
          LEFT JOIN media_release mr ON mr.id = mf.release_id
         WHERE p.disk_id = ?
           AND mf.deleted_at IS NULL
           AND (
                 mf.enriched_at IS NULL
              OR mf.enriched_at < (mf.mtime_ns / 1000000000)
           )
         ORDER BY
               CASE WHEN mf.release_id IS NULL THEN 1 ELSE 0 END ASC,
               (
                 SELECT mi.date_modified
                   FROM media_item mi
                  WHERE mi.id = mr.item_id
               ) DESC NULLS LAST
        """,
        (disk.id,),
    ).fetchall()
    conn.row_factory = None

    files_enriched = 0

    for row in pending:
        # Budget check at each file boundary.
        if budget_seconds is not None:
            elapsed = time.monotonic() - started_at_monotonic
            if elapsed >= budget_seconds:
                log.info(
                    "indexer.enrich.budget_exhausted",
                    disk_id=disk.id,
                    label=disk.label,
                    files_enriched=files_enriched,
                    elapsed=elapsed,
                )
                conn.execute(
                    "UPDATE scan_run SET stats_json = ? WHERE id = ?",
                    (json.dumps({"budget_exhausted": True, "files_enriched": files_enriched}), scan_run_id),
                )
                conn.commit()
                budget_exhausted[0] = True
                return

        # Reconstruct absolute file path from disk mount + rel_path + filename.
        rel_path: str = row["rel_path"]
        filename: str = row["filename"]
        if rel_path == ".":
            file_path = Path(disk.mount_path) / filename
        else:
            file_path = Path(disk.mount_path) / rel_path / filename

        file_id: int = row["file_id"]
        item_id: int | None = row["item_id"]
        release_id: int | None = row["release_id"]

        # Skip pymediainfo for non-video extensions: ``libmediainfo`` is the
        # parse bottleneck (~500 ms-1 s per call) and accounts for >80% of
        # the wall clock on a typical library where the bulk of files are
        # ``.jpg`` / ``.nfo`` / ``.srt`` sidecars. Pass a ``None`` wrapper to
        # ``_enrich_one_file`` for these so it skips stream extraction but
        # still runs the NFO presence check, artwork inventory, and
        # ``enriched_at`` update — the sidecar still needs to be marked as
        # processed so the next pass does not pick it up again.
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        effective_wrapper = wrapper if ext in _VIDEO_EXTENSIONS else None

        if not file_path.exists():
            # File no longer on disk — skip without updating enriched_at so the
            # scanner's miss-strikes logic handles it on the next full/incremental pass.
            log.debug(
                "indexer.enrich.file_missing",
                file_id=file_id,
                path=str(file_path),
            )
            continue

        # Stage B linkage: when a file has not been attached to a release yet
        # (cold Stage A inserts release_id=NULL), resolve the owning item via
        # the dispatch_path attribute chain and create the release / season /
        # episode rows on demand. Item id is then re-derived for downstream
        # NFO + artwork updates in _enrich_one_file.
        if release_id is None:
            try:
                new_release_id = link_file_to_release(conn, file_id, str(file_path))
            except sqlite3.Error as exc:
                log.warning(
                    "indexer.enrich.release_link_failed",
                    file_id=file_id,
                    path=str(file_path),
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                new_release_id = None

            if new_release_id is not None:
                resolved = conn.execute(
                    "SELECT mr.item_id, s.item_id AS show_item_id "
                    "FROM media_release mr "
                    "LEFT JOIN episode e ON e.id = mr.episode_id "
                    "LEFT JOIN season s ON s.id = e.season_id "
                    "WHERE mr.id = ?",
                    (new_release_id,),
                ).fetchone()
                if resolved is not None:
                    item_id = resolved[0] if resolved[0] is not None else resolved[1]

        try:
            _enrich_one_file(conn, file_id, file_path, item_id, effective_wrapper)
        except Exception:  # noqa: BLE001
            log.warning(
                "indexer.enrich.file_error",
                file_id=file_id,
                path=str(file_path),
            )
            continue

        # Per-file commit: partial progress is saved on any interruption.
        conn.commit()
        files_enriched += 1

        log.debug(
            "indexer.enrich.file_done",
            file_id=file_id,
            path=str(file_path),
        )

    log.info(
        "indexer.enrich.disk_done",
        disk_id=disk.id,
        label=disk.label,
        files_enriched=files_enriched,
    )


def _scan_disk_verify(
    conn: sqlite3.Connection,
    disk: DiskRow,
    files_visited: list[int],
    generation: int,
    budget_seconds: float | None,
    started_at_monotonic: float,
    budget_exhausted: list[bool],
    scan_run_id: int,
) -> None:
    """Re-stat every indexed file on a disk and enqueue repair on mismatch.

    Drift (size or mtime) and absence both produce a ``repair_queue`` row.
    Verify mode is non-destructive: it never soft-deletes, never recomputes
    fingerprints, and never updates ``size_bytes`` or ``mtime_ns`` on the
    DB row.  When a file's on-disk state matches the row, only
    ``last_verified_at`` and ``scan_generation`` are bumped to record that
    verification ran cleanly.  Mismatches are escalated to ``repair_queue``
    with ``scope='file'`` so an operator (or the repair worker) can
    investigate before any destructive action is taken.

    Per-file commit: partial progress survives interruption.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` to verify.
        files_visited: Single-element counter mutated in place (mirrors the
            convention of the other ``_scan_disk_*`` drivers).
        generation: Current scan generation; written to ``media_file.scan_generation``
            on every visited row so callers can detect orphaned rows from
            previous generations.
        budget_seconds: Maximum wall-clock seconds for the entire verify pass.
            ``None`` = unlimited.
        started_at_monotonic: :func:`time.monotonic` timestamp captured at scan start.
        budget_exhausted: Single-element flag set to ``True`` when the budget
            is reached.
        scan_run_id: PK of the active ``scan_run`` row for stats updates on
            budget exhaustion.
    """
    if disk.mount_path is None:
        log.warning("indexer.verify.disk_no_mount", disk_id=disk.id, label=disk.label)
        return

    # Lazy imports keep the module-level import surface small and avoid a
    # circular dependency with outbox_repo (which transitively imports schema).
    from personalscraper.indexer.repos import outbox_repo as _outbox_repo  # noqa: PLC0415
    from personalscraper.indexer.schema import RepairQueueRow  # noqa: PLC0415

    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT mf.id        AS file_id,
               mf.filename  AS filename,
               mf.size_bytes AS size_bytes,
               mf.mtime_ns  AS mtime_ns,
               p.rel_path   AS rel_path
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
         WHERE p.disk_id = ?
           AND mf.deleted_at IS NULL
         ORDER BY mf.id
        """,
        (disk.id,),
    ).fetchall()
    conn.row_factory = None

    files_verified = 0
    mismatches = 0
    missing = 0

    for row in rows:
        if budget_seconds is not None:
            elapsed = time.monotonic() - started_at_monotonic
            if elapsed >= budget_seconds:
                log.info(
                    "indexer.verify.budget_exhausted",
                    disk_id=disk.id,
                    label=disk.label,
                    files_verified=files_verified,
                    mismatches=mismatches,
                    missing=missing,
                    elapsed=elapsed,
                )
                conn.execute(
                    "UPDATE scan_run SET stats_json = ? WHERE id = ?",
                    (
                        json.dumps(
                            {
                                "budget_exhausted": True,
                                "files_verified": files_verified,
                                "mismatches": mismatches,
                                "missing": missing,
                            }
                        ),
                        scan_run_id,
                    ),
                )
                conn.commit()
                budget_exhausted[0] = True
                return

        rel_path: str = row["rel_path"]
        filename: str = row["filename"]
        if rel_path == ".":
            file_path = Path(disk.mount_path) / filename
        else:
            file_path = Path(disk.mount_path) / rel_path / filename

        file_id: int = row["file_id"]
        now_s: int = int(time.time())

        try:
            st = os.stat(file_path, follow_symlinks=False)
        except FileNotFoundError:
            _outbox_repo.insert_repair_queue(
                conn,
                RepairQueueRow(
                    id=0,
                    scope="file",
                    scope_id=file_id,
                    reason="verify: file missing on disk",
                    payload_json=None,
                    enqueued_at=now_s,
                    status="pending",
                    attempted_at=None,
                    attempts=0,
                ),
            )
            missing += 1
            files_visited[0] += 1
            files_verified += 1
            conn.commit()
            continue
        except OSError as exc:
            log.warning(
                "indexer.verify.stat_failed",
                file_id=file_id,
                path=str(file_path),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            files_visited[0] += 1
            continue

        size_match = st.st_size == row["size_bytes"]
        mtime_match = st.st_mtime_ns == row["mtime_ns"]

        if size_match and mtime_match:
            # Clean verification — bump last_verified_at and scan_generation.
            conn.execute(
                "UPDATE media_file SET last_verified_at = ?, scan_generation = ? WHERE id = ?",
                (now_s, generation, file_id),
            )
        else:
            _outbox_repo.insert_repair_queue(
                conn,
                RepairQueueRow(
                    id=0,
                    scope="file",
                    scope_id=file_id,
                    reason=(f"verify: drift detected (size_match={size_match}, mtime_match={mtime_match})"),
                    payload_json=json.dumps(
                        {
                            "expected_size": row["size_bytes"],
                            "actual_size": st.st_size,
                            "expected_mtime_ns": row["mtime_ns"],
                            "actual_mtime_ns": st.st_mtime_ns,
                        }
                    ),
                    enqueued_at=now_s,
                    status="pending",
                    attempted_at=None,
                    attempts=0,
                ),
            )
            mismatches += 1
            # Still bump scan_generation so the row is reachable in this run.
            conn.execute(
                "UPDATE media_file SET scan_generation = ? WHERE id = ?",
                (generation, file_id),
            )

        files_visited[0] += 1
        files_verified += 1
        conn.commit()

    log.info(
        "indexer.verify.disk_done",
        disk_id=disk.id,
        label=disk.label,
        files_verified=files_verified,
        mismatches=mismatches,
        missing=missing,
    )

"""Quick scan mode driver."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer.fingerprint import round_mtime_ns
from personalscraper.indexer.scanner._merkle_gate import (
    guard_bulk_change,
    merkle_short_circuit,
    recompute_disk_merkle_after_walk,
)
from personalscraper.indexer.scanner._shutdown import is_shutdown_requested
from personalscraper.indexer.scanner._walker import (
    DirMtimeSkipVisitor,
    WalkBudget,
    WalkCheckpoint,
    walk,
)
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

__all__ = [
    "QuickVisitor",
    "_run_paranoia_branch",
    "_scan_disk_quick",
]


class QuickVisitor(DirMtimeSkipVisitor):
    """Quick-mode visitor over :func:`~personalscraper.indexer.scanner._walker.walk`.

    Records files exactly like :class:`SkeletonVisitor` (tier-1 fields, no oshash
    recompute in quick mode) via the inherited
    :meth:`~personalscraper.indexer.scanner._walker.SkeletonVisitor.visit_file`,
    and inherits the dir-mtime subtree short-circuit from
    :class:`~personalscraper.indexer.scanner._walker.DirMtimeSkipVisitor` — an
    unchanged directory (stored ``dir_mtime_ns`` equals the live value, both
    bucketed by the disk capability) is skipped entirely, zero file reads in that
    subtree, exactly like the legacy ``_walk_dir_quick``.
    """


def _run_paranoia_branch(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    paranoia_window_seconds: int,
    capability: FilesystemCapability = NTFS_MACFUSE,
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
        capability: Per-disk :class:`FilesystemCapability`.  The mtime
            comparison is bucketed via :func:`round_mtime_ns` so coarse-grained
            filesystems (HFS+ 1 s, exFAT 2 s) do not flag sub-bucket jitter as a
            mismatch.  Defaults to ``NTFS_MACFUSE`` (granularity 1 → identity).
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

        if st.st_size != stored_size or round_mtime_ns(st.st_mtime_ns, capability) != round_mtime_ns(
            stored_mtime_ns, capability
        ):
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
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> None:
    """Run the quick-mode walk for a single disk.

    Implements two levels of short-circuiting:

    1. **Merkle short-circuit** (cheapest): recompute the Merkle root from the
       existing ``media_file`` rows in the database.  If it equals
       ``disk.merkle_root``, the disk has not changed since the last scan —
       skip all filesystem access for this disk.

    2. **Dir-mtime walk** (on Merkle miss): drive the shared
       :func:`~personalscraper.indexer.scanner._walker.walk` skeleton with a
       :class:`QuickVisitor`, which skips unchanged subtrees by comparing the
       stored ``path.dir_mtime_ns`` to the current filesystem value.

    On Merkle miss (stored root differs from DB-computed root), a bulk-change
    check is performed by sampling fresh tier-1 fingerprints from the filesystem
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
            checkpoint (or ``None``).  Forwarded to the walk skeleton's
            :class:`~personalscraper.indexer.scanner._walker.WalkCheckpoint`.
        files_since_checkpoint: Single-element mutable counter forwarded to the
            walk skeleton's checkpoint context.
        budget_exhausted: Single-element flag; set to ``True`` when the time budget
            is exceeded inside the walk.
        started_at_monotonic: :func:`time.monotonic` timestamp forwarded to the
            walk skeleton's budget context.
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
        capability: Per-disk :class:`FilesystemCapability` forwarded to
            :func:`_run_paranoia_branch` so the tier-1 mtime comparison is
            granularity-aware.  Defaults to ``NTFS_MACFUSE`` (granularity 1 →
            identity, byte-identical to the legacy compare).

    Raises:
        DiskBulkChangeDetected: When the Merkle delta exceeds
            *merkle_delta_freeze_threshold* and *confirm_bulk_change* is
            ``False``.  The caller should skip this disk and surface an
            actionable message to the user.
    """
    # --- Merkle short-circuit (shared single-impl) ---
    # Returns the DB-side fingerprints on a miss (walk needed) or None on a match
    # (disk unchanged → skip; disks_skipped already bumped inside the helper).
    fingerprints = merkle_short_circuit(conn, disk, disks_skipped, capability)
    if fingerprints is None:
        return

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
        _run_paranoia_branch(conn, disk, mount, paranoia_window_seconds, capability)

    # --- Bulk-change guard (quick-mode only, on Merkle miss; shared single-impl) ---
    # A high delta (many files changed at once) suggests a bulk restore or disk
    # swap rather than organic drift — freeze unless confirmed by the caller.
    guard_bulk_change(
        conn,
        disk,
        mount,
        fingerprints,
        confirm_bulk_change=confirm_bulk_change,
        merkle_delta_freeze_threshold=merkle_delta_freeze_threshold,
        capability=capability,
    )

    # --- Dir-mtime walk ---
    visitor = QuickVisitor(
        conn,
        disk,
        generation,
        files_visited,
        dirs_visited,
        dir_mtime_reliable,
        capability,
    )
    walk(
        mount,
        visitor,
        budget=WalkBudget(
            budget_seconds=budget_seconds,
            started_at_monotonic=started_at_monotonic,
            budget_exhausted=budget_exhausted if budget_exhausted is not None else [False],
        ),
        shutdown=is_shutdown_requested,
        checkpoint=WalkCheckpoint(
            scan_run_id=scan_run_id,
            checkpoint_every=checkpoint_every,
            files_since_checkpoint=files_since_checkpoint if files_since_checkpoint is not None else [0],
            resume_from=resume_from if resume_from is not None else [None],
        ),
    )

    # Skip post-walk bookkeeping if the budget was exhausted during the walk —
    # the partial state is preserved for crash-resume; Merkle root must not be
    # updated to an incomplete snapshot.
    if budget_exhausted is not None and budget_exhausted[0]:
        return

    # Write-through the disk-root path row and recompute + persist the Merkle
    # root so the next quick scan can short-circuit (shared single-impl).
    recompute_disk_merkle_after_walk(conn, disk, mount, capability)

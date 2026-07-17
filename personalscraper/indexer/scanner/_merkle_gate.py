"""Shared Merkle short-circuit / bulk-freeze / root-recompute for scan modes.

Quick and incremental modes both gate their per-disk walk on the Merkle root and
re-stamp it afterwards. Those three steps used to be byte-identical copies in
``_scan_disk_quick`` and ``_scan_disk_incremental``; this module is the ONE
implementation both drivers call (DESIGN §5 / P7.5, MECHANICAL-DUP). Full mode
does not short-circuit — it always walks and lets
:func:`personalscraper.indexer.scanner._finalize_disk_after_walk` write the
first-ever root via the same :func:`_build_disk_fingerprints` builder — so it is
already single-source and does not route through here.

The three seams:

- :func:`merkle_short_circuit` — recompute the DB-side root; on a match the disk
  is unchanged (skip the walk), on a miss return the fingerprints for the guard.
- :func:`guard_bulk_change` — freeze the disk when the sampled Merkle delta
  exceeds the threshold (mass restore / disk swap) unless the operator confirmed.
- :func:`recompute_disk_merkle_after_walk` — write-through the disk-root path row
  and persist the freshly-recomputed root so the next scan can short-circuit.
"""

from __future__ import annotations

import os
import sqlite3

from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.indexer.merkle import (
    DiskBulkChangeDetected,
    FileFingerprint,
    compute_merkle_delta,
    compute_merkle_root,
)
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner._db_writes import _upsert_path_row
from personalscraper.indexer.scanner._walker import (
    _build_disk_fingerprints,
    _sample_fresh_fingerprints,
)
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")

__all__ = [
    "guard_bulk_change",
    "merkle_short_circuit",
    "recompute_disk_merkle_after_walk",
]


def merkle_short_circuit(
    conn: sqlite3.Connection,
    disk: DiskRow,
    disks_skipped: list[int],
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> list[FileFingerprint] | None:
    """Recompute the DB-side Merkle root and decide whether the disk needs a walk.

    Builds FS-aware fingerprints (mtime bucketed by *capability*) so the root
    gate, the dir-mtime walk, and the bulk-change delta are all bucketed
    consistently; for NTFS this is the identity transform (byte-identical to the
    legacy root). When the DB-computed root equals the stored ``disk.merkle_root``
    the disk is unchanged since the last scan: ``disks_skipped`` is bumped and
    ``None`` is returned so the caller skips all filesystem access for the disk.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being scanned.
        disks_skipped: Single-element mutable counter for Merkle-hit skips.
        capability: Per-disk :class:`FilesystemCapability` governing mtime
            bucketing. Defaults to ``NTFS_MACFUSE`` (granularity 1 → identity).

    Returns:
        The DB-side fingerprint list (reused by :func:`guard_bulk_change`) when
        the root MISSED (a walk is needed), or ``None`` when the root MATCHED and
        the walk must be skipped.
    """
    fingerprints = _build_disk_fingerprints(conn, disk.id, capability)
    current_root = compute_merkle_root(fingerprints)

    if disk.merkle_root is not None and current_root == disk.merkle_root:
        log.info("indexer.scan.merkle_match", disk_uuid=disk.uuid, label=disk.label, merkle_root=current_root)
        disks_skipped[0] += 1
        return None

    log.info(
        "indexer.scan.merkle_miss",
        disk_uuid=disk.uuid,
        label=disk.label,
        stored_root=disk.merkle_root,
        computed_root=current_root,
    )
    return fingerprints


def guard_bulk_change(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    fingerprints: list[FileFingerprint],
    *,
    confirm_bulk_change: bool,
    merkle_delta_freeze_threshold: float,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> None:
    """Freeze the disk when the Merkle delta suggests a mass change (unless confirmed).

    On a Merkle miss, samples fresh tier-1 fingerprints from the filesystem and
    compares them against *fingerprints* (both sides bucketed with the SAME
    *capability* so sub-bucket jitter on a coarse FS cannot inflate the delta and
    trip a spurious freeze). A high delta (many files changed at once) suggests a
    bulk restore or disk swap rather than organic drift, so the walk is aborted
    unless the operator passed ``--confirm-bulk-change``. Only guards when a
    stored root exists (a first-ever scan has nothing to compare against).

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` being scanned.
        mount: Absolute mount point path.
        fingerprints: The DB-side fingerprints from :func:`merkle_short_circuit`.
        confirm_bulk_change: When ``True``, bypass the freeze and walk anyway.
        merkle_delta_freeze_threshold: Halt if the delta exceeds this fraction
            (0.0–1.0).
        capability: Per-disk :class:`FilesystemCapability` governing mtime
            bucketing of the freshly-sampled fingerprints.

    Raises:
        DiskBulkChangeDetected: When the delta exceeds
            *merkle_delta_freeze_threshold* and *confirm_bulk_change* is ``False``.
    """
    if not confirm_bulk_change and disk.merkle_root is not None:
        fresh_fps = _sample_fresh_fingerprints(conn, disk.id, mount, capability)
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


def recompute_disk_merkle_after_walk(
    conn: sqlite3.Connection,
    disk: DiskRow,
    mount: str,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> None:
    """Write-through the disk-root path row and persist the recomputed Merkle root.

    Called after a successful quick/incremental walk (the caller has already
    verified the budget was not exhausted, so the DB snapshot is complete). The
    root is bucketed by *capability* so it byte-matches what the next scan's
    short-circuit recomputes for this disk.

    Args:
        conn: Open SQLite connection.
        disk: :class:`~personalscraper.indexer.schema.DiskRow` just walked.
        mount: Absolute mount point path.
        capability: Per-disk :class:`FilesystemCapability` governing mtime bucketing.
    """
    # Write-through the path row for the disk root itself.
    try:
        root_st = os.stat(mount, follow_symlinks=False)
        _upsert_path_row(conn, disk.id, ".", root_st.st_mtime_ns)
    except OSError:
        log.warning("indexer.scan.root_stat_failed", mount_path=mount)

    # Recompute and persist the updated Merkle root so the next scan can
    # short-circuit if the FS state is unchanged (FS-aware bucketing so the
    # stored root matches what the next scan's short-circuit recomputes).
    updated_fingerprints = _build_disk_fingerprints(conn, disk.id, capability)
    new_root = compute_merkle_root(updated_fingerprints)
    disk_repo.update_merkle_root(conn, disk.id, new_root)
    log.debug("indexer.scan.merkle_root_updated", disk_id=disk.id, merkle_root=new_root)

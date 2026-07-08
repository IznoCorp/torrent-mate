"""Repair queue management for the media indexer.

Provides functions to enqueue repair requests, drain pending repairs within a
time budget, and inspect queue health for monitoring.

Functions:
- :func:`enqueue_repair` — insert a new ``repair_queue`` row with ``status='pending'``.
- :func:`drain` — process pending repair rows in FIFO order within a wall-clock budget.
- :func:`get_queue_health` — return ``(oldest_pending_age_seconds, pending_depth)``
  for use by ``library-status``.
- :func:`soft_delete_subtree` — soft-delete every ``media_file`` row under a given
  ``path.id`` (the ``soft_delete_subtree`` action consumed by ``library-repair``).
- :func:`repair_content_drift` — refresh the content-derived columns (oshash,
  xxh3_partial, enrichment invalidation) of a drifted ``media_file`` row.
- :func:`repair_processor` — default repair processor wired into ``library-repair``;
  dispatches on ``scope`` + ``payload_json['action']`` (or ``reason``).
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from personalscraper.indexer.schema import RepairQueueRow, RepairScope
from personalscraper.logger import get_logger

log = get_logger("indexer.repair")


# ---------------------------------------------------------------------------
# enqueue_repair
# ---------------------------------------------------------------------------


def enqueue_repair(
    conn: sqlite3.Connection,
    *,
    scope: RepairScope,
    scope_id: int,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> int:
    """Insert a new repair queue entry and return the assigned rowid.

    The row is created with ``status='pending'``, ``attempts=0``, and
    ``attempted_at=NULL``.  The caller is responsible for managing the
    enclosing transaction.

    Args:
        conn: Open SQLite connection.
        scope: Logical scope of the repair, e.g. ``'file'``, ``'item'``,
            ``'release'``, ``'disk'``.
        scope_id: Application-managed soft FK whose meaning depends on *scope*.
        reason: Human-readable reason string, e.g. ``'content_drift'`` or
            ``'oshash_collision'``.
        payload: Optional dict of additional context.  Serialised to JSON.
            Defaults to an empty dict when ``None``.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.
    """
    payload_json: str = json.dumps(payload or {})
    now: int = int(time.time())

    row = RepairQueueRow(
        id=0,  # ignored on insert
        scope=scope,
        scope_id=scope_id,
        reason=reason,
        payload_json=payload_json,
        enqueued_at=now,
        status="pending",
        attempted_at=None,
        attempts=0,
    )

    # Migration 003 added a partial UNIQUE index keyed on
    # ``(scope, scope_id) WHERE status='pending'`` so that repeated drift
    # events targeting the same artefact do not pile up redundant queue
    # entries.  ``INSERT OR IGNORE`` makes the dedup invisible to callers.
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO repair_queue (
            scope, scope_id, reason, payload_json,
            enqueued_at, status, attempted_at, attempts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.scope,
            row.scope_id,
            row.reason,
            row.payload_json,
            row.enqueued_at,
            row.status,
            row.attempted_at,
            row.attempts,
        ),
    )
    rowid: int | None = cursor.lastrowid
    if rowid is None or cursor.rowcount == 0:
        existing = conn.execute(
            "SELECT id FROM repair_queue WHERE scope = ? AND scope_id = ? AND status = 'pending'",
            (scope, scope_id),
        ).fetchone()
        rowid = int(existing[0]) if existing is not None else 0
        log.debug("indexer.repair.enqueue_deduped", scope=scope, scope_id=scope_id, existing_rowid=rowid)
        return rowid
    log.debug("indexer.repair.enqueued", scope=scope, scope_id=scope_id, reason=reason, rowid=rowid)
    return rowid


# ---------------------------------------------------------------------------
# RepairStats
# ---------------------------------------------------------------------------


@dataclass
class RepairStats:
    """Statistics returned by :func:`drain` after processing the repair queue.

    Args:
        processed: Total number of rows visited (regardless of outcome).
        succeeded: Number of rows transitioned to ``status='done'``.
        failed: Number of rows transitioned to ``status='failed'``.
        budget_exhausted: ``True`` if the drain loop was halted because the
            wall-clock budget was exceeded before the queue was empty.
        oldest_pending_age_seconds: Age of the oldest *still-pending* row at
            drain-end in seconds.  ``None`` if no pending rows remain.
        pending_depth: Number of rows still in ``status='pending'`` at drain-end.
    """

    processed: int
    succeeded: int
    failed: int
    budget_exhausted: bool
    oldest_pending_age_seconds: int | None
    pending_depth: int


# ---------------------------------------------------------------------------
# drain
# ---------------------------------------------------------------------------

#: Batch size for the SELECT-pending loop.
_DRAIN_BATCH: int = 100


def drain(
    conn: sqlite3.Connection,
    *,
    budget_seconds: float,
    processor: Callable[[sqlite3.Connection, RepairQueueRow], None] | None = None,
) -> RepairStats:
    """Process pending repair rows in FIFO order within a wall-clock time budget.

    Algorithm:

    1. SELECT up to :data:`_DRAIN_BATCH` rows with ``status='pending'`` ordered by
       ``enqueued_at ASC``.
    2. For each row, check whether the elapsed wall time exceeds *budget_seconds*.
       If so, set ``budget_exhausted=True`` and return early.
    3. Within a short transaction: set ``attempted_at=now``, increment ``attempts``.
    4. Call *processor(conn, row)*.  The default processor (``None``) is a no-op
       that logs ``indexer.repair.noop`` — real handlers are wired in later phases.
    5. On success set ``status='done'``; on any exception set ``status='failed'``
       and log the error.
    6. Commit and log ``indexer.repair.processed``.
    7. When the batch is exhausted (no more pending rows), return.

    Args:
        conn: Open SQLite connection.  Transaction management is handled
            internally — do **not** hold an open transaction when calling.
        budget_seconds: Maximum wall-clock seconds to spend draining.  The check
            is performed **before** processing each row, so the actual runtime
            may slightly exceed the budget by the duration of one processor call.
        processor: Optional callable taking ``(conn, row)`` that performs the
            actual repair for a single queue entry.  When ``None`` the default
            noop processor is used.

    Returns:
        :class:`RepairStats` with counts and queue-health snapshot at drain-end.
    """
    deadline: float = time.monotonic() + budget_seconds
    processed = 0
    succeeded = 0
    failed = 0
    budget_exhausted = False

    while True:
        # Fetch the next batch of pending rows in FIFO order.
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, scope, scope_id, reason, payload_json,
                   enqueued_at, status, attempted_at, attempts
              FROM repair_queue
             WHERE status = 'pending'
             ORDER BY enqueued_at ASC
             LIMIT ?
            """,
            (_DRAIN_BATCH,),
        ).fetchall()
        conn.row_factory = None

        if not rows:
            # Queue empty — normal termination.
            break

        for raw in rows:
            # Budget check before each row.
            if time.monotonic() >= deadline:
                budget_exhausted = True
                oldest, depth = get_queue_health(conn)
                return RepairStats(
                    processed=processed,
                    succeeded=succeeded,
                    failed=failed,
                    budget_exhausted=True,
                    oldest_pending_age_seconds=oldest,
                    pending_depth=depth,
                )

            row = RepairQueueRow(
                id=raw["id"],
                scope=raw["scope"],
                scope_id=raw["scope_id"],
                reason=raw["reason"],
                payload_json=raw["payload_json"],
                enqueued_at=raw["enqueued_at"],
                status=raw["status"],
                attempted_at=raw["attempted_at"],
                attempts=raw["attempts"],
            )

            now = int(time.time())
            # Update attempt metadata before calling the processor.
            conn.execute(
                "UPDATE repair_queue SET attempted_at = ?, attempts = attempts + 1 WHERE id = ?",
                (now, row.id),
            )

            try:
                if processor is not None:
                    processor(conn, row)
                else:
                    # Default noop processor — real handlers wired in later phases.
                    log.debug("indexer.repair.noop", row_id=row.id, scope=row.scope, reason=row.reason)

                conn.execute(
                    "UPDATE repair_queue SET status = 'done' WHERE id = ?",
                    (row.id,),
                )
                conn.commit()
                succeeded += 1

            except Exception as exc:  # noqa: BLE001 — catch-all to mark failed
                conn.execute(
                    "UPDATE repair_queue SET status = 'failed' WHERE id = ?",
                    (row.id,),
                )
                conn.commit()
                failed += 1
                log.error(
                    "indexer.repair.failed",
                    row_id=row.id,
                    scope=row.scope,
                    reason=row.reason,
                    error=str(exc),
                )

            processed += 1
            log.debug("indexer.repair.processed", row_id=row.id, scope=row.scope, reason=row.reason)

    oldest, depth = get_queue_health(conn)
    return RepairStats(
        processed=processed,
        succeeded=succeeded,
        failed=failed,
        budget_exhausted=budget_exhausted,
        oldest_pending_age_seconds=oldest,
        pending_depth=depth,
    )


# ---------------------------------------------------------------------------
# get_queue_health
# ---------------------------------------------------------------------------


def get_queue_health(conn: sqlite3.Connection) -> tuple[int | None, int]:
    """Return the age of the oldest pending row and the total pending depth.

    Used by ``library-status`` to emit a WARNING when the queue is stale or deep.

    Args:
        conn: Open SQLite connection.

    Returns:
        A ``(oldest_pending_age_seconds, pending_depth)`` tuple.  When no
        pending rows exist, ``oldest_pending_age_seconds`` is ``None`` and
        ``pending_depth`` is ``0``.
    """
    row = conn.execute(
        """
        SELECT MIN(enqueued_at) AS oldest_enqueued_at, COUNT(*) AS depth
          FROM repair_queue
         WHERE status = 'pending'
        """
    ).fetchone()

    if row is None:
        return (None, 0)

    depth: int = row[1] if isinstance(row, tuple) else row["depth"]
    oldest_enqueued_at: int | None = row[0] if isinstance(row, tuple) else row["oldest_enqueued_at"]

    if depth == 0 or oldest_enqueued_at is None:
        return (None, 0)

    age_seconds: int = int(time.time()) - oldest_enqueued_at
    return (age_seconds, depth)


# ---------------------------------------------------------------------------
# soft_delete_subtree
# ---------------------------------------------------------------------------


def _refresh_disk_merkle(
    conn: sqlite3.Connection,
    disk_id: int,
    fs_type_overrides: dict[str, str] | None = None,
) -> str | None:
    """Recompute and persist ``disk.merkle_root`` from the current live file set.

    Reads every live (``deleted_at IS NULL``, ``oshash IS NOT NULL``)
    ``media_file`` row whose path belongs to *disk_id*, recomputes the merkle
    root via :func:`compute_merkle_root`, and writes it back into the
    ``disk`` row.  Used after destructive operations (e.g.
    :func:`soft_delete_subtree`) so the stored root stays coherent with the
    live file set — without this, ``library-index --mode quick`` later trips
    the bulk-change protection because the stored vs computed delta is huge.

    The recomputed root MUST be FS-aware and match the scanner's bucketing,
    otherwise the next scan's Merkle short-circuit can never reproduce the
    root this function wrote and a coarse filesystem (exFAT 2 s, HFS+ 1 s)
    re-walks (or bulk-change-freezes) forever.  The recomputation therefore
    goes through the SAME helper the scanner uses —
    :func:`~personalscraper.indexer.scanner._walker._build_disk_fingerprints` —
    with the per-disk capability resolved exactly the way the scanner resolves
    it (:func:`~personalscraper.indexer._fs_capability.resolve_capability`).
    On NTFS/APFS/ext4 (granularity 1) the bucketing is the identity transform,
    so the written root is byte-identical to the legacy raw behaviour.

    .. note::
       The repair cascade (``library-repair`` → :func:`drain` →
       :func:`repair_processor` → :func:`soft_delete_subtree`) calls this with
       *fs_type_overrides* left at ``None`` because the
       ``Callable[[conn, row], None]`` processor protocol consumed by
       :func:`drain` has no channel for the operator override map.  Auto-detect
       (``resolve_capability(mount_path, None)``) is correct for that path: it
       probes the live mount and matches the scanner for the common
       no-override case.  The operator ``DiskConfig.fs_type`` override is
       honoured end-to-end via the scan and ``library-doctor`` paths, which DO
       thread the map; *fs_type_overrides* is exposed here so a direct caller
       that already holds the map (e.g. a future batched end-of-drain refresh)
       can pass it.

    Args:
        conn: Open SQLite connection with an active transaction.
        disk_id: PK of the ``disk`` row whose ``merkle_root`` should be
            refreshed. If the disk row has ``merkle_root IS NULL`` (never
            scanned), this is a no-op.
        fs_type_overrides: Optional mapping of the STABLE disk identity
            (``DiskConfig.id`` == ``DiskRow.label``) to a canonical fs-type
            override token.  ``None`` (the default, used by the repair cascade)
            means auto-detect the capability from the disk's ``mount_path``.

    Returns:
        The new merkle root that was written, or ``None`` if the disk had no
        prior merkle (no-op).
    """
    # Lazy imports keep the (scanner ↔ repair) import edge acyclic — the
    # scanner package transitively reaches repair during normal runs.
    from personalscraper.indexer._fs_capability import resolve_capability  # noqa: PLC0415
    from personalscraper.indexer.merkle import compute_merkle_root  # noqa: PLC0415
    from personalscraper.indexer.scanner._walker import _build_disk_fingerprints  # noqa: PLC0415

    row = conn.execute("SELECT label, mount_path, merkle_root FROM disk WHERE id = ?", (disk_id,)).fetchone()
    if row is None or row[2] is None:
        return None
    overrides = fs_type_overrides or {}
    # Resolve the per-disk capability the SAME way the scanner does: override
    # keyed on the STABLE label, else auto-detect from mount_path.
    capability = resolve_capability(row[1] or "", overrides.get(row[0]))
    fingerprints = _build_disk_fingerprints(conn, disk_id, capability)
    new_root = compute_merkle_root(fingerprints)
    conn.execute("UPDATE disk SET merkle_root = ? WHERE id = ?", (new_root, disk_id))
    log.info(
        "indexer.repair.merkle_refreshed",
        disk_id=disk_id,
        new_root=new_root,
        files_hashed=len(fingerprints),
    )
    return new_root


def soft_delete_subtree(conn: sqlite3.Connection, path_id: int) -> int:
    """Soft-delete, then hard-prune a phantom path subtree.

    Four-step cascade so the path row is actually removed AND the disk's
    stored merkle stays coherent with the live file set:

    1. Soft-delete every live ``media_file`` row (``deleted_at = now``) — the
       count returned reflects this step (audit trail).
    2. Hard-DELETE every ``media_file`` row under the path (including any
       already tombstoned) — the foreign key
       ``media_file.path_id REFERENCES path(id) ON DELETE RESTRICT`` would
       otherwise block step 3.
    3. Hard-DELETE the ``path`` row itself. ``detect_path_missing`` then
       stops seeing it (closes the reconcile loop).
    4. Refresh ``disk.merkle_root`` for the disk that owned the path so that
       a subsequent ``library-index --mode quick`` does not trip the
       bulk-change-detected protection (each pruned subtree shifts the merkle
       — without this refresh, deleting N paths makes the stored merkle
       diverge by N×files / total ratio and the next quick scan refuses to
       commit).  No-op when the disk has no stored merkle.

    Steps 1-4 run in the caller's enclosing transaction; the caller commits.

    .. note::
       Step 4 cost is O(files-on-disk).  When called inside a tight loop
       (e.g. ``library-repair`` draining 300+ pending rows for the same
       disk), each call re-hashes the whole disk.  Future work: batch the
       refresh at end-of-drain via a "dirty disks" set in
       :func:`repair_processor`.

    Args:
        conn: Open SQLite connection with an active transaction.
        path_id: PK of the ``path`` row whose subtree should be pruned.

    Returns:
        Number of ``media_file`` rows that this call tombstoned (step 1 only
        — does NOT include files already tombstoned by a previous run).
    """
    # Capture disk_id BEFORE the path row is deleted (step 3).
    disk_row = conn.execute("SELECT disk_id FROM path WHERE id = ?", (path_id,)).fetchone()
    disk_id: int | None = int(disk_row[0]) if disk_row else None

    now = int(time.time())
    n_soft: int = conn.execute(
        "UPDATE media_file SET deleted_at = ? WHERE path_id = ? AND deleted_at IS NULL",
        (now, path_id),
    ).rowcount
    n_hard: int = conn.execute(
        "DELETE FROM media_file WHERE path_id = ?",
        (path_id,),
    ).rowcount
    conn.execute("DELETE FROM path WHERE id = ?", (path_id,))

    new_merkle: str | None = None
    if disk_id is not None:
        new_merkle = _refresh_disk_merkle(conn, disk_id)

    log.info(
        "indexer.repair.soft_delete_subtree",
        path_id=path_id,
        files_soft_deleted=n_soft,
        files_hard_deleted=n_hard,
        path_row_deleted=True,
        disk_merkle_refreshed=new_merkle is not None,
        deleted_at=now,
    )
    return n_soft


# ---------------------------------------------------------------------------
# repair_content_drift
# ---------------------------------------------------------------------------


def repair_content_drift(conn: sqlite3.Connection, file_id: int) -> None:
    """Refresh the content-derived columns of a drifted ``media_file`` row.

    ``reconcile_file`` already rewrites the tier-1 tuple and ``xxh3_partial``
    at detection time, but the columns *derived from the file content* stay
    stale: ``oshash`` (tier-3 rename detection + release linking), ``xxh3_full``,
    and the Stage-B enrichment (``media_stream`` rows keyed off ``enriched_at``).
    The enrich pass only recomputes ``oshash`` when it is NULL, so without this
    handler a drifted video file keeps its OLD content identity forever.

    Steps:

    1. Re-stat the live file and recompute ``xxh3_partial`` (the file may have
       changed again since the scan that enqueued the row).
    2. Recompute ``oshash`` — only when the stored row has one (non-video
       sidecars keep ``oshash IS NULL``).
    3. Reset ``xxh3_full`` to NULL (unknown after a content change) and
       ``enriched_at`` to NULL so the next enrich pass replaces the
       ``media_stream`` rows and re-checks NFO/artwork state.
    4. When the oshash actually changed, refresh ``disk.merkle_root`` so the
       stored root stays coherent with the live fingerprint set (same
       contract as :func:`soft_delete_subtree`).

    Rows whose ``media_file`` is gone, tombstoned, or whose live file is
    unreachable complete as graceful no-ops: disappearance is owned by the
    scan's miss-strikes path, and a raise here would park the row in
    ``status='failed'`` where it re-trips the 7-day ``library-status`` WARN.

    Args:
        conn: Open SQLite connection.  The caller (drain loop) commits.
        file_id: PK of the ``media_file`` row to refresh.
    """
    # Lazy imports keep the (drift ↔ repair) edge acyclic — drift.py imports
    # this module at module level.
    from personalscraper.indexer import fingerprint as _fp  # noqa: PLC0415
    from personalscraper.indexer.drift import clamp_mtime_ns  # noqa: PLC0415

    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT mf.filename, mf.oshash, mf.deleted_at,
               p.rel_path, p.disk_id, d.mount_path
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
          JOIN disk d ON d.id = p.disk_id
         WHERE mf.id = ?
        """,
        (file_id,),
    ).fetchone()
    conn.row_factory = None

    if row is None:
        log.warning("indexer.repair.content_drift_row_missing", file_id=file_id)
        return
    if row["deleted_at"] is not None:
        log.info("indexer.repair.content_drift_tombstoned_skip", file_id=file_id)
        return

    full_path = Path(row["mount_path"]) / row["rel_path"] / row["filename"]
    stored_oshash: str | None = row["oshash"]
    try:
        stat = os.stat(full_path)
        new_xxh3: str = _fp.xxh3_partial(full_path)
        new_oshash: str | None = _fp.oshash(full_path) if stored_oshash is not None else None
    except OSError as exc:
        log.warning(
            "indexer.repair.content_drift_file_unreadable",
            file_id=file_id,
            path=str(full_path),
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return

    clamped_mtime_ns = clamp_mtime_ns(stat.st_mtime_ns, time.time_ns())
    conn.execute(
        """
        UPDATE media_file
           SET size_bytes = ?, mtime_ns = ?, ctime_ns = ?,
               oshash = ?, xxh3_partial = ?, xxh3_full = NULL,
               enriched_at = NULL
         WHERE id = ?
        """,
        (stat.st_size, clamped_mtime_ns, stat.st_ctime_ns, new_oshash, new_xxh3, file_id),
    )

    oshash_changed = stored_oshash is not None and new_oshash != stored_oshash
    if oshash_changed:
        _refresh_disk_merkle(conn, int(row["disk_id"]))

    log.info(
        "indexer.repair.content_drift_repaired",
        file_id=file_id,
        oshash_refreshed=oshash_changed,
        size_bytes=stat.st_size,
    )


# ---------------------------------------------------------------------------
# repair_processor
# ---------------------------------------------------------------------------


def repair_processor(conn: sqlite3.Connection, row: RepairQueueRow) -> None:
    """Default repair processor dispatched by ``library-repair``.

    Dispatches on ``scope`` and the ``action`` key inside ``payload_json``
    (falling back to ``reason`` for detector rows enqueued without a payload).
    Currently handles:

    - ``scope='path'`` + ``action='soft_delete_subtree'``:
      soft-delete every ``media_file`` row under the path identified by
      ``scope_id``.  Enqueued by ``library-reconcile --enqueue-repairs`` when
      ``detect_path_missing`` detects a missing directory (BD-D).
    - ``scope='file'`` + ``reason='content_drift'``:
      refresh the content-derived columns (oshash, xxh3_partial, enrichment)
      of the file identified by ``scope_id``.  Enqueued by the scanner's
      tier-2 escalation (``drift.reconcile_file`` and the incremental mode).

    Unknown (scope, action) combinations are logged as a warning and treated
    as a no-op so that future actions added by later phases do not cause
    existing ``repair_queue`` rows to fail.

    Args:
        conn: Open SQLite connection.  The drain loop has already set
            ``attempted_at`` and incremented ``attempts`` before calling this
            function; the caller commits on success.
        row: The ``RepairQueueRow`` being processed.

    Raises:
        ValueError: When ``scope_id`` is ``None`` for a scope that requires it
            (e.g. ``'path'``), since there is no meaningful repair without a
            target ID.
    """
    payload: dict[str, Any] = json.loads(row.payload_json or "{}")
    action: str | None = payload.get("action")

    if row.scope == "path" and action == "soft_delete_subtree":
        if row.scope_id is None:
            raise ValueError(f"repair_queue row {row.id}: scope='path' requires a non-NULL scope_id")
        soft_delete_subtree(conn, row.scope_id)
        return

    if row.scope == "file" and row.reason == "content_drift":
        if row.scope_id is None:
            raise ValueError(f"repair_queue row {row.id}: scope='file' requires a non-NULL scope_id")
        repair_content_drift(conn, row.scope_id)
        return

    # Unknown combination — log and skip rather than fail hard so that rows
    # enqueued by detectors added in future phases degrade gracefully here.
    log.warning(
        "indexer.repair.unknown_action",
        row_id=row.id,
        scope=row.scope,
        action=action,
        reason=row.reason,
    )

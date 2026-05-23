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
- :func:`repair_processor` — default repair processor wired into ``library-repair``;
  dispatches on ``scope`` + ``payload_json['action']``.
"""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
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


def _refresh_disk_merkle(conn: sqlite3.Connection, disk_id: int) -> str | None:
    """Recompute and persist ``disk.merkle_root`` from the current live file set.

    Reads every live (``deleted_at IS NULL``, ``oshash IS NOT NULL``)
    ``media_file`` row whose path belongs to *disk_id*, recomputes the merkle
    root via :func:`compute_merkle_root`, and writes it back into the
    ``disk`` row.  Used after destructive operations (e.g.
    :func:`soft_delete_subtree`) so the stored root stays coherent with the
    live file set — without this, ``library-index --mode quick`` later trips
    the bulk-change protection because the stored vs computed delta is huge.

    Args:
        conn: Open SQLite connection with an active transaction.
        disk_id: PK of the ``disk`` row whose ``merkle_root`` should be
            refreshed. If the disk row has ``merkle_root IS NULL`` (never
            scanned), this is a no-op.

    Returns:
        The new merkle root that was written, or ``None`` if the disk had no
        prior merkle (no-op).
    """
    from personalscraper.indexer.merkle import FileFingerprint, compute_merkle_root  # noqa: PLC0415

    row = conn.execute("SELECT merkle_root FROM disk WHERE id = ?", (disk_id,)).fetchone()
    if row is None or row[0] is None:
        return None
    rows = conn.execute(
        """
        SELECT mf.path_id, mf.size_bytes, mf.mtime_ns, mf.oshash
          FROM media_file mf
          JOIN path p ON p.id = mf.path_id
         WHERE p.disk_id = ?
           AND mf.deleted_at IS NULL
           AND mf.oshash IS NOT NULL
        """,
        (disk_id,),
    ).fetchall()
    fingerprints = [
        FileFingerprint(path_id=int(r[0]), size=int(r[1]), mtime_ns=int(r[2]), oshash=str(r[3]))
        for r in rows
    ]
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
# repair_processor
# ---------------------------------------------------------------------------


def repair_processor(conn: sqlite3.Connection, row: RepairQueueRow) -> None:
    """Default repair processor dispatched by ``library-repair``.

    Dispatches on ``scope`` and the ``action`` key inside ``payload_json``.
    Currently handles:

    - ``scope='path'`` + ``action='soft_delete_subtree'``:
      soft-delete every ``media_file`` row under the path identified by
      ``scope_id``.  Enqueued by ``library-reconcile --enqueue-repairs`` when
      ``detect_path_missing`` detects a missing directory (BD-D).

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

    # Unknown combination — log and skip rather than fail hard so that rows
    # enqueued by detectors added in future phases degrade gracefully here.
    log.warning(
        "indexer.repair.unknown_action",
        row_id=row.id,
        scope=row.scope,
        action=action,
        reason=row.reason,
    )

"""Repair queue management for the media indexer.

Provides functions to enqueue repair requests, drain pending repairs within a
time budget, and inspect queue health for monitoring.

Functions:
- :func:`enqueue_repair` — insert a new ``repair_queue`` row with ``status='pending'``.
- :func:`drain` — process pending repair rows in FIFO order within a wall-clock budget.
- :func:`get_queue_health` — return ``(oldest_pending_age_seconds, pending_depth)``
  for use by ``library-status``.
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

    cursor = conn.execute(
        """
        INSERT INTO repair_queue (
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
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
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

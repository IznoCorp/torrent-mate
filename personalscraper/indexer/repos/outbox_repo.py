"""Repository for the ``index_outbox``, ``pending_op``, and ``repair_queue`` tables.

Provides write-through and queue-management operations for the indexer's
transactional outbox, pending-operation handoff, and repair queue.
All write methods emit structlog events following the
``indexer.{component}.{action}`` convention (DESIGN §6.6).

Only raw ``sqlite3`` is used — no ORM.
"""

from __future__ import annotations

import sqlite3

from personalscraper.indexer.schema import IndexOutboxRow, PendingOpRow, RepairQueueRow
from personalscraper.logger import get_logger

log = get_logger("indexer.outbox")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_row_factory(conn: sqlite3.Connection) -> None:
    """Set ``conn.row_factory = sqlite3.Row`` before any SELECT.

    Args:
        conn: Open SQLite connection to configure.
    """
    conn.row_factory = sqlite3.Row


def _row_to_outbox(row: sqlite3.Row) -> IndexOutboxRow:
    """Convert a ``sqlite3.Row`` from ``index_outbox`` to an :class:`IndexOutboxRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`IndexOutboxRow` instance.
    """
    return IndexOutboxRow(
        id=row["id"],
        source=row["source"],
        op=row["op"],
        payload_json=row["payload_json"],
        created_at=row["created_at"],
        processed_at=row["processed_at"],
        status=row["status"],
    )


def _row_to_pending_op(row: sqlite3.Row) -> PendingOpRow:
    """Convert a ``sqlite3.Row`` from ``pending_op`` to a :class:`PendingOpRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`PendingOpRow` instance.
    """
    return PendingOpRow(
        id=row["id"],
        disk_id=row["disk_id"],
        op=row["op"],
        payload_json=row["payload_json"],
        created_at=row["created_at"],
        replayed_at=row["replayed_at"],
    )


def _row_to_repair_queue(row: sqlite3.Row) -> RepairQueueRow:
    """Convert a ``sqlite3.Row`` from ``repair_queue`` to a :class:`RepairQueueRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`RepairQueueRow` instance.
    """
    return RepairQueueRow(
        id=row["id"],
        scope=row["scope"],
        scope_id=row["scope_id"],
        reason=row["reason"],
        payload_json=row["payload_json"],
        enqueued_at=row["enqueued_at"],
        status=row["status"],
        attempted_at=row["attempted_at"],
        attempts=row["attempts"],
    )


# ---------------------------------------------------------------------------
# index_outbox table operations
# ---------------------------------------------------------------------------


def insert_outbox_event(conn: sqlite3.Connection, row: IndexOutboxRow) -> int:
    """Insert a new outbox event row and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`IndexOutboxRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.
    """
    cursor = conn.execute(
        """
        INSERT INTO index_outbox (source, op, payload_json, created_at, processed_at, status)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (row.source, row.op, row.payload_json, row.created_at, row.processed_at, row.status),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.outbox.insert", source=row.source, op=row.op, rowid=rowid)
    return rowid


def claim_pending_op(conn: sqlite3.Connection, id: int) -> IndexOutboxRow | None:
    """Fetch an outbox row and atomically mark it as ``'running'`` (optimistic claim).

    This is a read-and-flag helper for drain loops.  The caller is expected to
    complete the op and then call :func:`complete_pending_op`.

    Note: the ``index_outbox`` table has no ``'running'`` status; in practice the
    drain loop reads ``status='pending'`` rows and processes them one at a time
    within a ``BEGIN IMMEDIATE`` transaction.  This function returns the row for
    the caller to process; status update is deferred to :func:`complete_pending_op`.

    Args:
        conn: Open SQLite connection.
        id: PK of the outbox row to claim.

    Returns:
        :class:`IndexOutboxRow` if found and status is ``'pending'``, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT * FROM index_outbox WHERE id = ? AND status = 'pending'",
        (id,),
    ).fetchone()
    if row is None:
        return None
    result = _row_to_outbox(row)
    log.debug("indexer.outbox.claimed", id=id, source=result.source, op=result.op)
    return result


def complete_pending_op(
    conn: sqlite3.Connection,
    id: int,
    status: str,
    processed_at: int,
) -> bool:
    """Mark an outbox row as completed (``'done'``, ``'failed'``, or ``'deferred'``).

    Args:
        conn: Open SQLite connection.
        id: PK of the outbox row to update.
        status: Final status: ``'done'``, ``'failed'``, or ``'deferred'``.
        processed_at: Unix epoch seconds when the op was processed.

    Returns:
        ``True`` if a row was updated, ``False`` if no row matched ``id``.
    """
    cursor = conn.execute(
        "UPDATE index_outbox SET status = ?, processed_at = ? WHERE id = ?",
        (status, processed_at, id),
    )
    updated = cursor.rowcount > 0
    if updated:
        log.info("indexer.outbox.complete", id=id, status=status, processed_at=processed_at)
    return updated


# ---------------------------------------------------------------------------
# pending_op table operations
# ---------------------------------------------------------------------------


def insert_pending_op(conn: sqlite3.Connection, row: PendingOpRow) -> int:
    """Insert a hinted-handoff pending op row and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`PendingOpRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.
    """
    cursor = conn.execute(
        """
        INSERT INTO pending_op (disk_id, op, payload_json, created_at, replayed_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (row.disk_id, row.op, row.payload_json, row.created_at, row.replayed_at),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.pending_op.insert", disk_id=row.disk_id, op=row.op, rowid=rowid)
    return rowid


def get_pending_op_by_id(conn: sqlite3.Connection, id: int) -> PendingOpRow | None:
    """Fetch a pending op row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`PendingOpRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM pending_op WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _row_to_pending_op(row)


# ---------------------------------------------------------------------------
# repair_queue table operations
# ---------------------------------------------------------------------------


def insert_repair_queue(conn: sqlite3.Connection, row: RepairQueueRow) -> int:
    """Insert a repair queue entry and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`RepairQueueRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.
    """
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
    log.info("indexer.repair.enqueued", scope=row.scope, scope_id=row.scope_id, reason=row.reason, rowid=rowid)
    return rowid


def get_repair_queue_by_id(conn: sqlite3.Connection, id: int) -> RepairQueueRow | None:
    """Fetch a repair queue row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`RepairQueueRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM repair_queue WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _row_to_repair_queue(row)

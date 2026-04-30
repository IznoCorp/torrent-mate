"""Repository for the ``index_outbox``, ``pending_op``, and ``repair_queue`` tables.

Provides write-through and queue-management operations for the indexer's
transactional outbox, pending-operation handoff, and repair queue.
All write methods emit structlog events following the
``indexer.{component}.{action}`` convention (DESIGN §6.6).

Only raw ``sqlite3`` is used — no ORM.

Public API (plan §5.1):
- ``insert(conn, source, op, payload_json) -> int`` — insert a pending outbox row.
- ``fetch_pending(conn, limit=100) -> list[IndexOutboxRow]`` — fetch pending rows FIFO.
- ``mark_done(conn, row_id) -> None`` — mark a row as done.
- ``mark_failed(conn, row_id) -> None`` — mark a row as failed.
- ``mark_deferred(conn, row_id) -> None`` — mark a row as deferred.
- ``insert_pending_op_row(conn, disk_id, op, payload_json) -> int`` — insert a pending_op row.
- ``fetch_for_disk(conn, disk_id) -> list[PendingOpRow]`` — fetch pending_op rows for a disk.
- ``mark_replayed(conn, row_id) -> None`` — mark a pending_op row as replayed.
- ``purge_expired(conn, ttl_days=30) -> int`` — purge old pending_op rows.
"""

from __future__ import annotations

import sqlite3
import time

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


# ---------------------------------------------------------------------------
# Plan §5.1 — OutboxRepo public API (module-level functions)
# ---------------------------------------------------------------------------


def insert(conn: sqlite3.Connection, source: str, op: str, payload_json: str) -> int:
    """Insert a new outbox row with ``status='pending'`` and ``created_at=now``.

    This is the primary write path for pipeline mutation points.  The caller
    supplies the logical source and op type; timestamps and status are set here.

    Args:
        conn: Open SQLite connection.
        source: Originating subsystem: ``'dispatch'``, ``'scraper'``,
            ``'trailers'``, or ``'scanner'``.
        op: Operation type: ``'move'``, ``'nfo_write'``, ``'artwork_write'``,
            or ``'trailer_download'``.
        payload_json: Serialised JSON payload (per-op shape — see DESIGN §9.3).

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.
    """
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO index_outbox (source, op, payload_json, created_at, processed_at, status)
        VALUES (?, ?, ?, ?, NULL, 'pending')
        """,
        (source, op, payload_json, now),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.outbox.insert", source=source, op=op, rowid=rowid)
    return rowid


def fetch_pending(conn: sqlite3.Connection, limit: int = 100) -> list[IndexOutboxRow]:
    """Fetch up to *limit* pending outbox rows in FIFO (``id ASC``) order.

    Args:
        conn: Open SQLite connection.
        limit: Maximum number of rows to return (default 100).

    Returns:
        List of :class:`IndexOutboxRow` instances with ``status='pending'``,
        ordered by ascending ``id``.
    """
    _set_row_factory(conn)
    rows = conn.execute(
        "SELECT * FROM index_outbox WHERE status = 'pending' ORDER BY id ASC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_outbox(r) for r in rows]


def mark_done(conn: sqlite3.Connection, row_id: int) -> None:
    """Mark an outbox row as ``'done'``, recording ``processed_at=now``.

    Args:
        conn: Open SQLite connection.
        row_id: PK of the outbox row to update.
    """
    now = int(time.time())
    conn.execute(
        "UPDATE index_outbox SET status = 'done', processed_at = ? WHERE id = ?",
        (now, row_id),
    )
    log.info("indexer.outbox.mark_done", row_id=row_id, processed_at=now)


def mark_failed(conn: sqlite3.Connection, row_id: int) -> None:
    """Mark an outbox row as ``'failed'``, recording ``processed_at=now``.

    Used by the drainer after retry exhaustion (DESIGN §9.2).
    Logs ``indexer.outbox.row_failed`` per DESIGN §6.6.

    Args:
        conn: Open SQLite connection.
        row_id: PK of the outbox row to update.
    """
    now = int(time.time())
    conn.execute(
        "UPDATE index_outbox SET status = 'failed', processed_at = ? WHERE id = ?",
        (now, row_id),
    )
    log.warning("indexer.outbox.row_failed", row_id=row_id, processed_at=now)


def mark_deferred(conn: sqlite3.Connection, row_id: int) -> None:
    """Mark an outbox row as ``'deferred'``, recording ``processed_at=now``.

    Used when the target disk is unreachable at drain time; the op is moved to
    ``pending_op`` for replay on remount (DESIGN §9.2).

    Args:
        conn: Open SQLite connection.
        row_id: PK of the outbox row to update.
    """
    now = int(time.time())
    conn.execute(
        "UPDATE index_outbox SET status = 'deferred', processed_at = ? WHERE id = ?",
        (now, row_id),
    )
    log.info("indexer.outbox.deferred", row_id=row_id, processed_at=now)


# ---------------------------------------------------------------------------
# Plan §5.1 — PendingOpRepo public API (module-level functions)
# ---------------------------------------------------------------------------


def insert_pending_op_row(conn: sqlite3.Connection, disk_id: int, op: str, payload_json: str) -> int:
    """Insert a hinted-handoff row into ``pending_op`` and return its rowid.

    Called by the drainer when the target disk is unreachable; the row is
    replayed on the next scan that finds the disk mounted (DESIGN §9.2).

    Args:
        conn: Open SQLite connection.
        disk_id: FK → ``disk.id`` of the target disk.
        op: Operation type string (mirrors the originating outbox row's ``op``).
        payload_json: Serialised JSON payload (same shape as the outbox row).

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.
    """
    now = int(time.time())
    cursor = conn.execute(
        """
        INSERT INTO pending_op (disk_id, op, payload_json, created_at, replayed_at)
        VALUES (?, ?, ?, ?, NULL)
        """,
        (disk_id, op, payload_json, now),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.pending_op.insert", disk_id=disk_id, op=op, rowid=rowid)
    return rowid


def fetch_for_disk(conn: sqlite3.Connection, disk_id: int) -> list[PendingOpRow]:
    """Fetch all ``pending_op`` rows for a given disk, ordered by ``id ASC``.

    Used by the scanner at remount time to replay deferred operations.

    Args:
        conn: Open SQLite connection.
        disk_id: FK → ``disk.id`` of the target disk.

    Returns:
        List of :class:`PendingOpRow` instances for the disk, oldest first.
    """
    _set_row_factory(conn)
    rows = conn.execute(
        "SELECT * FROM pending_op WHERE disk_id = ? ORDER BY id ASC",
        (disk_id,),
    ).fetchall()
    return [_row_to_pending_op(r) for r in rows]


def mark_replayed(conn: sqlite3.Connection, row_id: int) -> None:
    """Mark a ``pending_op`` row as replayed by setting ``replayed_at=now``.

    Args:
        conn: Open SQLite connection.
        row_id: PK of the ``pending_op`` row to update.
    """
    now = int(time.time())
    conn.execute(
        "UPDATE pending_op SET replayed_at = ? WHERE id = ?",
        (now, row_id),
    )
    log.info("indexer.pending_op.replayed", row_id=row_id, replayed_at=now)


def purge_expired(conn: sqlite3.Connection, ttl_days: int = 30) -> int:
    """Delete ``pending_op`` rows older than *ttl_days* days and return the count.

    Rows are considered expired when ``created_at < now - ttl_days * 86400``.
    Each purged row is logged individually as ``indexer.pending_op.ttl_expired``
    per DESIGN §6.6.

    Args:
        conn: Open SQLite connection.
        ttl_days: Age threshold in days (default 30).

    Returns:
        Number of rows deleted.
    """
    cutoff = int(time.time()) - ttl_days * 86400
    # Fetch IDs before deletion so we can log each one individually.
    rows = conn.execute(
        "SELECT id FROM pending_op WHERE created_at < ?",
        (cutoff,),
    ).fetchall()
    if not rows:
        return 0
    ids = [r[0] for r in rows]
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM pending_op WHERE id IN ({placeholders})", ids)  # noqa: S608
    for row_id in ids:
        log.info("indexer.pending_op.ttl_expired", row_id=row_id, cutoff=cutoff)
    return len(ids)

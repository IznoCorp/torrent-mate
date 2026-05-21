"""Repository for the ``scan_run``, ``scan_event``, and ``deleted_item`` tables.

Provides write operations for audit/logging rows produced by the scanner and
drift-detection engine.  All write methods emit structlog events following the
``indexer.{component}.{action}`` convention (DESIGN §6.6).

Only raw ``sqlite3`` is used — no ORM.
"""

from __future__ import annotations

import sqlite3

from personalscraper.indexer.schema import DeletedItemRow, ScanEventRow, ScanRunRow
from personalscraper.logger import get_logger

log = get_logger("indexer.scan")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_row_factory(conn: sqlite3.Connection) -> None:
    """Set ``conn.row_factory = sqlite3.Row`` before any SELECT.

    Args:
        conn: Open SQLite connection to configure.
    """
    conn.row_factory = sqlite3.Row


def _row_to_scan_run(row: sqlite3.Row) -> ScanRunRow:
    """Convert a ``sqlite3.Row`` from ``scan_run`` to a :class:`ScanRunRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`ScanRunRow` instance.
    """
    return ScanRunRow(
        id=row["id"],
        generation=row["generation"],
        mode=row["mode"],
        disk_filter=row["disk_filter"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        last_path=row["last_path"],
        status=row["status"],
        stats_json=row["stats_json"],
    )


def _row_to_scan_event(row: sqlite3.Row) -> ScanEventRow:
    """Convert a ``sqlite3.Row`` from ``scan_event`` to a :class:`ScanEventRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`ScanEventRow` instance.
    """
    return ScanEventRow(
        id=row["id"],
        scan_id=row["scan_id"],
        ts=row["ts"],
        item_id=row["item_id"],
        file_id=row["file_id"],
        event=row["event"],
        payload_json=row["payload_json"],
    )


def _row_to_deleted_item(row: sqlite3.Row) -> DeletedItemRow:
    """Convert a ``sqlite3.Row`` from ``deleted_item`` to a :class:`DeletedItemRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`DeletedItemRow` instance.
    """
    return DeletedItemRow(
        id=row["id"],
        kind=row["kind"],
        original_id=row["original_id"],
        deleted_at=row["deleted_at"],
        reason=row["reason"],
        payload_json=row["payload_json"],
    )


# ---------------------------------------------------------------------------
# scan_run table operations
# ---------------------------------------------------------------------------


# A scan that has been ``running`` for more than this many seconds is
# considered stale (process killed, host rebooted, …). The next scan's
# pre-insert sweep marks it ``aborted`` so the DB doesn't accumulate
# perpetually-running rows that confuse ``library-status`` and the
# resume-from-crash heuristics.
_SCAN_RUN_STALE_AFTER_S = 6 * 3600  # 6 hours — well past any legitimate full scan


def _sweep_stale_scan_runs(conn: sqlite3.Connection, now_s: int) -> int:
    """Mark abandoned ``status='running'`` scan_run rows as ``aborted``.

    Called from :func:`insert_scan_run` so every new scan startup cleans
    up after a crashed predecessor. Without this, the DB grows a row
    per crashed scan that ``library-status`` (and the resume logic)
    treats as legitimately running.

    Args:
        conn: Open SQLite connection.
        now_s: Current unix epoch seconds.

    Returns:
        Number of stale rows marked aborted.
    """
    cutoff = now_s - _SCAN_RUN_STALE_AFTER_S
    cursor = conn.execute(
        """
        UPDATE scan_run
        SET status = 'aborted', finished_at = ?
        WHERE status = 'running' AND started_at < ?
        """,
        (now_s, cutoff),
    )
    swept: int = cursor.rowcount or 0
    if swept > 0:
        log.warning("indexer.scan.stale_run_aborted", count=swept, cutoff_at=cutoff)
    return swept


def insert_scan_run(conn: sqlite3.Connection, row: ScanRunRow) -> int:
    """Insert a new scan run row and return the assigned rowid.

    Before inserting, sweeps any stale ``status='running'`` rows
    (``started_at`` older than 6 hours) to ``aborted`` so the
    ``library-status`` report and crash-resume heuristics never see
    perpetually-running ghosts from killed processes.

    Args:
        conn: Open SQLite connection.
        row: :class:`ScanRunRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.
    """
    _sweep_stale_scan_runs(conn, row.started_at)
    cursor = conn.execute(
        """
        INSERT INTO scan_run (generation, mode, disk_filter, started_at, finished_at, last_path, status, stats_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.generation,
            row.mode,
            row.disk_filter,
            row.started_at,
            row.finished_at,
            row.last_path,
            row.status,
            row.stats_json,
        ),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.scan.insert_run", generation=row.generation, mode=row.mode, rowid=rowid)
    return rowid


def update_scan_run_status(
    conn: sqlite3.Connection,
    id: int,
    status: str,
    finished_at: int | None = None,
    stats_json: str | None = None,
    last_path: str | None = None,
) -> bool:
    """Update the status (and optional finish metadata) of a scan run row.

    Args:
        conn: Open SQLite connection.
        id: PK of the scan run to update.
        status: New status string: ``'running'``, ``'ok'``, ``'failed'``, or ``'aborted'``.
        finished_at: Unix epoch seconds when the scan finished; ``None`` = not yet finished.
        stats_json: Serialised :class:`~personalscraper.indexer.schema.ScanStats` JSON; ``None`` = unchanged.
        last_path: Last visited path for crash-resume; ``None`` = unchanged.

    Returns:
        ``True`` if a row was updated, ``False`` if no row matched ``id``.
    """
    cursor = conn.execute(
        """
        UPDATE scan_run
        SET status = ?,
            finished_at = COALESCE(?, finished_at),
            stats_json = COALESCE(?, stats_json),
            last_path = COALESCE(?, last_path)
        WHERE id = ?
        """,
        (status, finished_at, stats_json, last_path, id),
    )
    updated = cursor.rowcount > 0
    if updated:
        log.info("indexer.scan.update_run_status", id=id, status=status)
    return updated


def get_scan_run_by_id(conn: sqlite3.Connection, id: int) -> ScanRunRow | None:
    """Fetch a scan run row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`ScanRunRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM scan_run WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _row_to_scan_run(row)


# ---------------------------------------------------------------------------
# scan_event table operations
# ---------------------------------------------------------------------------


def insert_scan_event(conn: sqlite3.Connection, row: ScanEventRow) -> int:
    """Insert a new scan event row and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`ScanEventRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.
    """
    cursor = conn.execute(
        """
        INSERT INTO scan_event (scan_id, ts, item_id, file_id, event, payload_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (row.scan_id, row.ts, row.item_id, row.file_id, row.event, row.payload_json),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.debug("indexer.scan.insert_event", scan_id=row.scan_id, event_name=row.event, rowid=rowid)
    return rowid


# ---------------------------------------------------------------------------
# deleted_item table operations
# ---------------------------------------------------------------------------


def insert_deleted_item(conn: sqlite3.Connection, row: DeletedItemRow) -> int:
    """Insert a tombstone record for a deleted item/file/release.

    Args:
        conn: Open SQLite connection.
        row: :class:`DeletedItemRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.
    """
    cursor = conn.execute(
        """
        INSERT INTO deleted_item (kind, original_id, deleted_at, reason, payload_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (row.kind, row.original_id, row.deleted_at, row.reason, row.payload_json),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info(
        "indexer.scan.insert_deleted_item",
        kind=row.kind,
        original_id=row.original_id,
        rowid=rowid,
    )
    return rowid

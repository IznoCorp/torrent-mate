"""Repository for the ``media_file`` and ``media_stream`` tables.

Provides CRUD operations for physical file rows and their associated stream metadata.
All write methods emit structlog events following the ``indexer.{component}.{action}``
convention (DESIGN §6.6).

Only raw ``sqlite3`` is used — no ORM.
"""

from __future__ import annotations

import sqlite3

from personalscraper.indexer.schema import MediaFileRow, MediaStreamRow
from personalscraper.logger import get_logger

log = get_logger("indexer.file")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_row_factory(conn: sqlite3.Connection) -> None:
    """Set ``conn.row_factory = sqlite3.Row`` before any SELECT.

    Args:
        conn: Open SQLite connection to configure.
    """
    conn.row_factory = sqlite3.Row


def _row_to_file(row: sqlite3.Row) -> MediaFileRow:
    """Convert a ``sqlite3.Row`` from ``media_file`` to a :class:`MediaFileRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`MediaFileRow` instance.
    """
    return MediaFileRow(
        id=row["id"],
        release_id=row["release_id"],
        path_id=row["path_id"],
        filename=row["filename"],
        size_bytes=row["size_bytes"],
        mtime_ns=row["mtime_ns"],
        ctime_ns=row["ctime_ns"],
        oshash=row["oshash"],
        xxh3_partial=row["xxh3_partial"],
        xxh3_full=row["xxh3_full"],
        scan_generation=row["scan_generation"],
        last_verified_at=row["last_verified_at"],
        enriched_at=row["enriched_at"],
        miss_strikes=row["miss_strikes"],
        deleted_at=row["deleted_at"],
    )


def _row_to_stream(row: sqlite3.Row) -> MediaStreamRow:
    """Convert a ``sqlite3.Row`` from ``media_stream`` to a :class:`MediaStreamRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`MediaStreamRow` instance.
    """
    keys = row.keys()

    def _opt_bool(name: str) -> bool | None:
        if name not in keys:
            return None
        v = row[name]
        return None if v is None else bool(v)

    return MediaStreamRow(
        id=row["id"],
        file_id=row["file_id"],
        idx=row["idx"],
        kind=row["kind"],
        codec=row["codec"],
        lang=row["lang"],
        channels=row["channels"],
        width=row["width"],
        height=row["height"],
        duration_ms=row["duration_ms"],
        bitrate=row["bitrate"],
        hdr_format=row["hdr_format"] if "hdr_format" in keys else None,
        is_atmos=_opt_bool("is_atmos"),
        is_default=_opt_bool("is_default"),
        forced=_opt_bool("forced"),
        format=row["format"] if "format" in keys else None,
    )


# ---------------------------------------------------------------------------
# media_file table operations
# ---------------------------------------------------------------------------


def insert(conn: sqlite3.Connection, row: MediaFileRow) -> int:
    """Insert a new file row and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`MediaFileRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.

    Raises:
        sqlite3.IntegrityError: If the ``(path_id, filename)`` pair is not unique.
    """
    cursor = conn.execute(
        """
        INSERT INTO media_file (
            release_id, path_id, filename, size_bytes, mtime_ns, ctime_ns,
            oshash, xxh3_partial, xxh3_full, scan_generation,
            last_verified_at, enriched_at, miss_strikes, deleted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.release_id,
            row.path_id,
            row.filename,
            row.size_bytes,
            row.mtime_ns,
            row.ctime_ns,
            row.oshash,
            row.xxh3_partial,
            row.xxh3_full,
            row.scan_generation,
            row.last_verified_at,
            row.enriched_at,
            row.miss_strikes,
            row.deleted_at,
        ),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.file.insert", filename=row.filename, path_id=row.path_id, rowid=rowid)
    return rowid


def get_by_id(conn: sqlite3.Connection, id: int) -> MediaFileRow | None:
    """Fetch a file row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`MediaFileRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM media_file WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _row_to_file(row)


def find_by_path_and_filename(conn: sqlite3.Connection, path_id: int, filename: str) -> MediaFileRow | None:
    """Fetch a file row by its ``(path_id, filename)`` unique key.

    Args:
        conn: Open SQLite connection.
        path_id: FK referencing the ``path`` table.
        filename: Bare filename (no directory component).

    Returns:
        :class:`MediaFileRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT * FROM media_file WHERE path_id = ? AND filename = ?",
        (path_id, filename),
    ).fetchone()
    if row is None:
        return None
    return _row_to_file(row)


def soft_delete(conn: sqlite3.Connection, id: int, deleted_at: int) -> bool:
    """Set ``deleted_at`` on a file row (soft-delete tombstone).

    Args:
        conn: Open SQLite connection.
        id: PK of the file row to soft-delete.
        deleted_at: Unix epoch seconds of deletion.

    Returns:
        ``True`` if a row was updated, ``False`` if no row matched ``id``.
    """
    cursor = conn.execute(
        "UPDATE media_file SET deleted_at = ? WHERE id = ?",
        (deleted_at, id),
    )
    updated = cursor.rowcount > 0
    if updated:
        log.info("indexer.file.soft_delete", id=id, deleted_at=deleted_at)
    return updated


def increment_miss_strike(conn: sqlite3.Connection, id: int) -> bool:
    """Increment the ``miss_strikes`` counter for a file row.

    Args:
        conn: Open SQLite connection.
        id: PK of the file row.

    Returns:
        ``True`` if a row was updated, ``False`` if no row matched ``id``.
    """
    cursor = conn.execute(
        "UPDATE media_file SET miss_strikes = miss_strikes + 1 WHERE id = ?",
        (id,),
    )
    updated = cursor.rowcount > 0
    if updated:
        log.info("indexer.file.increment_miss_strike", id=id)
    return updated


# ---------------------------------------------------------------------------
# media_stream table operations
# ---------------------------------------------------------------------------


def insert_stream(conn: sqlite3.Connection, row: MediaStreamRow) -> int:
    """Insert a new stream metadata row and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`MediaStreamRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.

    Raises:
        sqlite3.IntegrityError: If the ``(file_id, idx)`` pair is not unique.
    """
    cursor = conn.execute(
        """
        INSERT INTO media_stream (
            file_id, idx, kind, codec, lang, channels, width, height, duration_ms, bitrate,
            hdr_format, is_atmos, is_default, forced, format
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.file_id,
            row.idx,
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
        ),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.file.insert_stream", file_id=row.file_id, idx=row.idx, kind=row.kind, rowid=rowid)
    return rowid


def get_streams_for_file(conn: sqlite3.Connection, file_id: int) -> list[MediaStreamRow]:
    """Fetch all stream rows associated with a file, ordered by stream index.

    Args:
        conn: Open SQLite connection.
        file_id: FK of the owning file row.

    Returns:
        List of :class:`MediaStreamRow` instances, possibly empty.
    """
    _set_row_factory(conn)
    rows = conn.execute(
        "SELECT * FROM media_stream WHERE file_id = ? ORDER BY idx",
        (file_id,),
    ).fetchall()
    return [_row_to_stream(r) for r in rows]

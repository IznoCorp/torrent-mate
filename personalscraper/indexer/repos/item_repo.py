"""Repository for the ``media_item`` and ``item_attribute`` tables.

Provides CRUD operations for media items and their flexible attributes.
All write methods emit structlog events following the ``indexer.{component}.{action}``
convention (DESIGN §6.6).

Only raw ``sqlite3`` is used — no ORM.
"""

from __future__ import annotations

import sqlite3

from personalscraper.indexer.schema import ItemAttributeRow, MediaItemRow
from personalscraper.logger import get_logger

log = get_logger("indexer.item")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_row_factory(conn: sqlite3.Connection) -> None:
    """Set ``conn.row_factory = sqlite3.Row`` before any SELECT.

    Args:
        conn: Open SQLite connection to configure.
    """
    conn.row_factory = sqlite3.Row


def _row_to_item(row: sqlite3.Row) -> MediaItemRow:
    """Convert a ``sqlite3.Row`` from ``media_item`` to a :class:`MediaItemRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`MediaItemRow` instance.
    """
    return MediaItemRow(
        id=row["id"],
        kind=row["kind"],
        title=row["title"],
        title_sort=row["title_sort"],
        original_title=row["original_title"],
        year=row["year"],
        category_id=row["category_id"],
        tmdb_id=row["tmdb_id"],
        imdb_id=row["imdb_id"],
        tvdb_id=row["tvdb_id"],
        nfo_status=row["nfo_status"],
        artwork_json=row["artwork_json"],
        date_created=row["date_created"],
        date_modified=row["date_modified"],
        date_metadata_refreshed=row["date_metadata_refreshed"],
        is_locked=row["is_locked"],
        preferred_lang=row["preferred_lang"],
    )


def _row_to_attr(row: sqlite3.Row) -> ItemAttributeRow:
    """Convert a ``sqlite3.Row`` from ``item_attribute`` to an :class:`ItemAttributeRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`ItemAttributeRow` instance.
    """
    return ItemAttributeRow(
        item_id=row["item_id"],
        key=row["key"],
        value=row["value"],
    )


# ---------------------------------------------------------------------------
# media_item table operations
# ---------------------------------------------------------------------------


def insert(conn: sqlite3.Connection, row: MediaItemRow) -> int:
    """Insert a new media item and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`MediaItemRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.

    Raises:
        sqlite3.IntegrityError: On constraint violation.
    """
    cursor = conn.execute(
        """
        INSERT INTO media_item (
            kind, title, title_sort, original_title, year, category_id,
            tmdb_id, imdb_id, tvdb_id, nfo_status, artwork_json,
            date_created, date_modified, date_metadata_refreshed,
            is_locked, preferred_lang
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row.kind,
            row.title,
            row.title_sort,
            row.original_title,
            row.year,
            row.category_id,
            row.tmdb_id,
            row.imdb_id,
            row.tvdb_id,
            row.nfo_status,
            row.artwork_json,
            row.date_created,
            row.date_modified,
            row.date_metadata_refreshed,
            row.is_locked,
            row.preferred_lang,
        ),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.item.insert", title=row.title, kind=row.kind, rowid=rowid)
    return rowid


def get_by_id(conn: sqlite3.Connection, id: int) -> MediaItemRow | None:
    """Fetch a media item row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`MediaItemRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT id, kind, title, title_sort, original_title, year, category_id, "
        "tmdb_id, imdb_id, tvdb_id, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang "
        "FROM media_item WHERE id = ?",
        (id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_item(row)


def find_by_tmdb_id(conn: sqlite3.Connection, tmdb_id: int) -> MediaItemRow | None:
    """Fetch the first media item matching a TMDB numeric ID.

    Args:
        conn: Open SQLite connection.
        tmdb_id: TMDB numeric ID to search for.

    Returns:
        :class:`MediaItemRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT id, kind, title, title_sort, original_title, year, category_id, "
        "tmdb_id, imdb_id, tvdb_id, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang "
        "FROM media_item WHERE tmdb_id = ?",
        (tmdb_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_item(row)


def delete(conn: sqlite3.Connection, id: int) -> bool:
    """Hard-delete a media item row (cascades to child tables via ON DELETE CASCADE).

    Args:
        conn: Open SQLite connection.
        id: PK of the media item to delete.

    Returns:
        ``True`` if a row was deleted, ``False`` if no row matched ``id``.
    """
    cursor = conn.execute("DELETE FROM media_item WHERE id = ?", (id,))
    deleted = cursor.rowcount > 0
    if deleted:
        log.info("indexer.item.delete", id=id)
    return deleted


# ---------------------------------------------------------------------------
# item_attribute table operations
# ---------------------------------------------------------------------------


def upsert_attr(conn: sqlite3.Connection, row: ItemAttributeRow) -> int:
    """Upsert a flex attribute, replacing ``value`` on conflict.

    Args:
        conn: Open SQLite connection.
        row: :class:`ItemAttributeRow` to upsert.

    Returns:
        The ``rowid`` of the upserted row.
    """
    cursor = conn.execute(
        """
        INSERT INTO item_attribute (item_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(item_id, key) DO UPDATE SET value = excluded.value
        """,
        (row.item_id, row.key, row.value),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.item.upsert_attr", item_id=row.item_id, key=row.key, rowid=rowid)
    return rowid


def get_attr(conn: sqlite3.Connection, item_id: int, key: str) -> ItemAttributeRow | None:
    """Fetch a single flex attribute by ``(item_id, key)``.

    Args:
        conn: Open SQLite connection.
        item_id: FK of the owning media item.
        key: Attribute key string.

    Returns:
        :class:`ItemAttributeRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT item_id, key, value FROM item_attribute WHERE item_id = ? AND key = ?",
        (item_id, key),
    ).fetchone()
    if row is None:
        return None
    return _row_to_attr(row)

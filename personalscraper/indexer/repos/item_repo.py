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


# ---------------------------------------------------------------------------
# Dispatch-layer helpers
# ---------------------------------------------------------------------------

#: Attribute key for the config-level disk identifier stored by the dispatch
#: layer (e.g. ``"drive_a"``).  This is distinct from ``disk.label`` in the
#: DB, which is the volume display name.  The dispatch layer stores config IDs
#: so it can map back to ``DiskConfig`` objects without a secondary DB lookup.
_ATTR_DISPATCH_DISK = "dispatch_disk"

#: Attribute key for the full filesystem path of the media item root directory
#: as seen by the dispatch layer (e.g. ``"/Volumes/Disk1/movies/Inception (2010)"``).
_ATTR_DISPATCH_PATH = "dispatch_path"

#: Attribute key for the NFC-normalized, lowercased title used as the dispatch
#: lookup key.  Stored as an attribute so that cross-filesystem Unicode
#: normalization differences (APFS precomposed vs NTFS decomposed) are resolved
#: at write time rather than at query time (SQLite's ``lower()`` is ASCII-only
#: and does not perform Unicode NFC normalization).
_ATTR_DISPATCH_NORM_TITLE = "dispatch_normalized_title"


def upsert(conn: sqlite3.Connection, row: MediaItemRow) -> int:
    """Insert or update a :class:`MediaItemRow` keyed by ``(kind, title)``.

    Performs a SELECT-then-UPDATE-or-INSERT to handle the dispatch layer's
    one-row-per-``(kind, title)`` invariant without requiring a UNIQUE
    constraint on the underlying table.  When a matching row already exists,
    ``category_id`` and ``date_modified`` are refreshed.  Otherwise a new
    row is inserted.

    Args:
        conn: Open SQLite connection.
        row: :class:`MediaItemRow` to upsert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the inserted or updated row.
    """
    existing = get_by_title_and_kind(conn, row.title, row.kind)
    if existing is not None:
        conn.execute(
            "UPDATE media_item SET category_id = ?, date_modified = ? WHERE id = ?",
            (row.category_id, row.date_modified, existing.id),
        )
        log.info("indexer.item.upsert_update", title=row.title, kind=row.kind, id=existing.id)
        return existing.id
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
    log.info("indexer.item.upsert_insert", title=row.title, kind=row.kind, rowid=rowid)
    return rowid


def get_by_title_and_kind(conn: sqlite3.Connection, title: str, kind: str) -> MediaItemRow | None:
    """Fetch a media item row by its ``(title, kind)`` unique pair.

    Args:
        conn: Open SQLite connection.
        title: Exact display title as stored in the DB.
        kind: ``'movie'`` or ``'show'``.

    Returns:
        :class:`MediaItemRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT id, kind, title, title_sort, original_title, year, category_id, "
        "tmdb_id, imdb_id, tvdb_id, nfo_status, artwork_json, "
        "date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang "
        "FROM media_item WHERE title = ? AND kind = ?",
        (title, kind),
    ).fetchone()
    if row is None:
        return None
    return _row_to_item(row)


def find_by_normalized_name(
    conn: sqlite3.Connection,
    normalized_name: str,
    kind: str,
) -> tuple[MediaItemRow, str, str] | None:
    """Find a media item by its NFC-normalized title and retrieve dispatch attrs.

    Queries ``media_item`` joined with ``item_attribute`` rows keyed by
    :data:`_ATTR_DISPATCH_NORM_TITLE` (lookup key), :data:`_ATTR_DISPATCH_DISK`,
    and :data:`_ATTR_DISPATCH_PATH`.  The ``normalized_name`` must already be
    NFC-lowercased (the caller is responsible for normalization via
    ``_normalize_key``).

    Using a stored normalized-title attribute (rather than ``lower(m.title)``)
    is intentional: SQLite's ``lower()`` is ASCII-only and cannot perform
    Unicode NFC normalization, so matching NFD-encoded titles stored by
    macFUSE-NTFS disks against NFC queries from APFS would silently fail.

    Args:
        conn: Open SQLite connection.
        normalized_name: NFC-normalized, lowercased title (output of
            ``_normalize_key`` in ``dispatch/media_index.py``).
        kind: ``'movie'`` or ``'show'``.

    Returns:
        A ``(MediaItemRow, dispatch_disk, dispatch_path)`` triple when found,
        or ``None`` when no matching item exists.
    """
    _set_row_factory(conn)
    row = conn.execute(
        "SELECT m.id, m.kind, m.title, m.title_sort, m.original_title, m.year, m.category_id, "
        "m.tmdb_id, m.imdb_id, m.tvdb_id, m.nfo_status, m.artwork_json, "
        "m.date_created, m.date_modified, m.date_metadata_refreshed, m.is_locked, m.preferred_lang, "
        "a1.value AS dispatch_disk, a2.value AS dispatch_path "
        "FROM media_item m "
        "INNER JOIN item_attribute anorm ON anorm.item_id = m.id AND anorm.key = ? AND anorm.value = ? "
        "LEFT JOIN item_attribute a1 ON a1.item_id = m.id AND a1.key = ? "
        "LEFT JOIN item_attribute a2 ON a2.item_id = m.id AND a2.key = ? "
        "WHERE m.kind = ? "
        "ORDER BY m.date_modified DESC "
        "LIMIT 1",
        (_ATTR_DISPATCH_NORM_TITLE, normalized_name, _ATTR_DISPATCH_DISK, _ATTR_DISPATCH_PATH, kind),
    ).fetchone()
    if row is None:
        return None
    item = _row_to_item(row)
    dispatch_disk: str = row["dispatch_disk"] or ""
    dispatch_path: str = row["dispatch_path"] or ""
    return (item, dispatch_disk, dispatch_path)


def remove_by_id(conn: sqlite3.Connection, item_id: int) -> bool:
    """Hard-delete a media item by primary key (cascades to item_attribute).

    Args:
        conn: Open SQLite connection.
        item_id: Primary key of the media item to delete.

    Returns:
        ``True`` if a row was deleted, ``False`` if no row matched.
    """
    cursor = conn.execute("DELETE FROM media_item WHERE id = ?", (item_id,))
    deleted = cursor.rowcount > 0
    if deleted:
        log.info("indexer.item.remove", id=item_id)
    return deleted


def list_all_dispatch_items(conn: sqlite3.Connection) -> list[tuple[MediaItemRow, str, str]]:
    """List all media items that have dispatch attributes stored.

    Returns all ``media_item`` rows that have :data:`_ATTR_DISPATCH_NORM_TITLE`,
    :data:`_ATTR_DISPATCH_DISK`, and :data:`_ATTR_DISPATCH_PATH` attributes
    set, along with the disk and path attribute values.  Items inserted
    directly by the scanner (without dispatch attrs) are excluded.

    Args:
        conn: Open SQLite connection.

    Returns:
        List of ``(MediaItemRow, dispatch_disk, dispatch_path)`` triples.
    """
    _set_row_factory(conn)
    rows = conn.execute(
        "SELECT m.id, m.kind, m.title, m.title_sort, m.original_title, m.year, m.category_id, "
        "m.tmdb_id, m.imdb_id, m.tvdb_id, m.nfo_status, m.artwork_json, "
        "m.date_created, m.date_modified, m.date_metadata_refreshed, m.is_locked, m.preferred_lang, "
        "a1.value AS dispatch_disk, a2.value AS dispatch_path "
        "FROM media_item m "
        "INNER JOIN item_attribute anorm ON anorm.item_id = m.id AND anorm.key = ? "
        "INNER JOIN item_attribute a1 ON a1.item_id = m.id AND a1.key = ? "
        "INNER JOIN item_attribute a2 ON a2.item_id = m.id AND a2.key = ? ",
        (_ATTR_DISPATCH_NORM_TITLE, _ATTR_DISPATCH_DISK, _ATTR_DISPATCH_PATH),
    ).fetchall()
    result: list[tuple[MediaItemRow, str, str]] = []
    for row in rows:
        item = _row_to_item(row)
        dispatch_disk: str = row["dispatch_disk"] or ""
        dispatch_path: str = row["dispatch_path"] or ""
        result.append((item, dispatch_disk, dispatch_path))
    return result

"""Repository for the ``media_release`` table.

Provides CRUD operations for media release rows.
All write methods emit structlog events following the ``indexer.{component}.{action}``
convention (DESIGN §6.6).

Only raw ``sqlite3`` is used — no ORM.
"""

from __future__ import annotations

import sqlite3

from personalscraper.indexer.schema import MediaReleaseRow
from personalscraper.logger import get_logger

log = get_logger("indexer.release")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_row_factory(conn: sqlite3.Connection) -> None:
    """Set ``conn.row_factory = sqlite3.Row`` before any SELECT.

    Args:
        conn: Open SQLite connection to configure.
    """
    conn.row_factory = sqlite3.Row


def _row_to_release(row: sqlite3.Row) -> MediaReleaseRow:
    """Convert a ``sqlite3.Row`` from ``media_release`` to a :class:`MediaReleaseRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`MediaReleaseRow` instance.
    """
    return MediaReleaseRow(
        id=row["id"],
        item_id=row["item_id"],
        episode_id=row["episode_id"],
        quality=row["quality"],
        edition=row["edition"],
        primary_lang=row["primary_lang"],
    )


# ---------------------------------------------------------------------------
# media_release table operations
# ---------------------------------------------------------------------------


def insert(conn: sqlite3.Connection, row: MediaReleaseRow) -> int:
    """Insert a new release row and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`MediaReleaseRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.

    Raises:
        sqlite3.IntegrityError: If neither or both of ``item_id``/``episode_id`` are set,
            or if the ``(item_id, episode_id, quality, edition, primary_lang)`` combination
            is not unique.
    """
    cursor = conn.execute(
        """
        INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang)
        VALUES (?, ?, ?, ?, ?)
        """,
        (row.item_id, row.episode_id, row.quality, row.edition, row.primary_lang),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.release.insert", item_id=row.item_id, episode_id=row.episode_id, rowid=rowid)
    return rowid


def get_by_id(conn: sqlite3.Connection, id: int) -> MediaReleaseRow | None:
    """Fetch a release row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`MediaReleaseRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM media_release WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _row_to_release(row)


def upsert(conn: sqlite3.Connection, row: MediaReleaseRow) -> int:
    """Upsert a release row, updating ``quality``, ``edition``, ``primary_lang`` on conflict.

    The conflict key is ``(item_id, episode_id, quality, edition, primary_lang)``.
    When all nullable columns are NULL, SQLite treats each NULL as distinct, so
    the upsert degrades to an insert for the "default release" pattern.

    Args:
        conn: Open SQLite connection.
        row: :class:`MediaReleaseRow` to upsert.

    Returns:
        The ``rowid`` (= ``id``) of the upserted row.
    """
    cursor = conn.execute(
        """
        INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(item_id, episode_id, quality, edition, primary_lang) DO UPDATE SET
          quality = excluded.quality,
          edition = excluded.edition,
          primary_lang = excluded.primary_lang
        """,
        (row.item_id, row.episode_id, row.quality, row.edition, row.primary_lang),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.release.upsert", item_id=row.item_id, episode_id=row.episode_id, rowid=rowid)
    return rowid

"""Repository for the ``season`` and ``episode`` tables.

Provides CRUD operations for TV season and episode rows.
The ``trg_season_requires_show`` trigger enforces that seasons can only be
attached to ``media_item`` rows with ``kind='show'``; callers must handle
:exc:`sqlite3.IntegrityError` when this invariant is violated.

All write methods emit structlog events following the ``indexer.{component}.{action}``
convention (DESIGN §6.6).

Only raw ``sqlite3`` is used — no ORM.
"""

from __future__ import annotations

import sqlite3

from personalscraper.indexer.schema import EpisodeRow, SeasonRow
from personalscraper.logger import get_logger

log = get_logger("indexer.tv")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_row_factory(conn: sqlite3.Connection) -> None:
    """Set ``conn.row_factory = sqlite3.Row`` before any SELECT.

    Args:
        conn: Open SQLite connection to configure.
    """
    conn.row_factory = sqlite3.Row


def _row_to_season(row: sqlite3.Row) -> SeasonRow:
    """Convert a ``sqlite3.Row`` from ``season`` to a :class:`SeasonRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`SeasonRow` instance.
    """
    return SeasonRow(
        id=row["id"],
        item_id=row["item_id"],
        number=row["number"],
        episode_count=row["episode_count"],
        has_poster=row["has_poster"],
        episodes_with_nfo=row["episodes_with_nfo"],
    )


def _row_to_episode(row: sqlite3.Row) -> EpisodeRow:
    """Convert a ``sqlite3.Row`` from ``episode`` to an :class:`EpisodeRow`.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.

    Returns:
        Populated :class:`EpisodeRow` instance.
    """
    return EpisodeRow(
        id=row["id"],
        season_id=row["season_id"],
        number=row["number"],
        title=row["title"],
    )


# ---------------------------------------------------------------------------
# season table operations
# ---------------------------------------------------------------------------


def insert_season(conn: sqlite3.Connection, row: SeasonRow, *, ignore_conflict: bool = False) -> int:
    """Insert a new season row and return the assigned rowid.

    The ``trg_season_requires_show`` trigger aborts the insert if
    ``row.item_id`` references a ``media_item`` with ``kind != 'show'``.

    Args:
        conn: Open SQLite connection.
        row: :class:`SeasonRow` to insert.  The ``id`` field is ignored.
        ignore_conflict: When True, use ``INSERT OR IGNORE`` so a conflict
            on the ``UNIQUE(item_id, number)`` constraint silently skips
            the insert.  Callers that want idempotence across rescans
            should pass True and re-fetch the row's id with a follow-up
            SELECT.  Returned rowid is ``0`` when the insert was skipped.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row, or ``0`` when
        ``ignore_conflict=True`` and the row was skipped due to UNIQUE conflict.

    Raises:
        sqlite3.IntegrityError: If ``item_id`` references a non-show media item,
            or (when ``ignore_conflict=False``) if the ``(item_id, number)``
            pair is not unique.
    """
    verb = "INSERT OR IGNORE" if ignore_conflict else "INSERT"
    cursor = conn.execute(
        f"""
        {verb} INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo)
        VALUES (?, ?, ?, ?, ?)
        """,
        (row.item_id, row.number, row.episode_count, row.has_poster, row.episodes_with_nfo),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    if cursor.rowcount > 0:
        log.info("indexer.tv.insert_season", item_id=row.item_id, number=row.number, rowid=rowid)
    return rowid


def upsert_season(conn: sqlite3.Connection, row: SeasonRow) -> int:
    """Insert a season row or refresh the denormalized columns on conflict.

    Differs from :func:`insert_season` with ``ignore_conflict=True``: on
    a UNIQUE(item_id, number) conflict, this variant **updates**
    ``episode_count``, ``has_poster`` and ``episodes_with_nfo`` from the
    incoming row instead of silently dropping the new values. This is
    the right primitive for the library scanner — without it, a season
    row inserted before its poster / sibling NFOs landed on disk would
    keep ``has_poster=0`` and ``episodes_with_nfo=0`` forever.

    Args:
        conn: Open SQLite connection.
        row: :class:`SeasonRow` carrying the latest counts/flags. ``id``
            is ignored on the insert path.

    Returns:
        The PK of the inserted-or-updated row.

    Raises:
        sqlite3.IntegrityError: If ``item_id`` references a non-show
            ``media_item`` (trigger ``trg_season_requires_show``).
    """
    conn.execute(
        """
        INSERT INTO season (item_id, number, episode_count, has_poster, episodes_with_nfo)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(item_id, number) DO UPDATE SET
            episode_count = excluded.episode_count,
            has_poster = excluded.has_poster,
            episodes_with_nfo = excluded.episodes_with_nfo
        """,
        (row.item_id, row.number, row.episode_count, row.has_poster, row.episodes_with_nfo),
    )
    season_id_row = conn.execute(
        "SELECT id FROM season WHERE item_id = ? AND number = ?",
        (row.item_id, row.number),
    ).fetchone()
    if season_id_row is None:
        msg = f"season upsert lost the row (item_id={row.item_id}, number={row.number})"
        raise RuntimeError(msg)
    return int(season_id_row[0])


def get_season_by_id(conn: sqlite3.Connection, id: int) -> SeasonRow | None:
    """Fetch a season row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`SeasonRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM season WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _row_to_season(row)


# ---------------------------------------------------------------------------
# episode table operations
# ---------------------------------------------------------------------------


def insert_episode(conn: sqlite3.Connection, row: EpisodeRow) -> int:
    """Insert a new episode row and return the assigned rowid.

    Args:
        conn: Open SQLite connection.
        row: :class:`EpisodeRow` to insert.  The ``id`` field is ignored.

    Returns:
        The ``rowid`` (= ``id``) of the newly inserted row.

    Raises:
        sqlite3.IntegrityError: If the ``(season_id, number)`` pair is not unique.
    """
    cursor = conn.execute(
        "INSERT INTO episode (season_id, number, title) VALUES (?, ?, ?)",
        (row.season_id, row.number, row.title),
    )
    rowid: int = cursor.lastrowid  # type: ignore[assignment]
    log.info("indexer.tv.insert_episode", season_id=row.season_id, number=row.number, rowid=rowid)
    return rowid


def get_episode_by_id(conn: sqlite3.Connection, id: int) -> EpisodeRow | None:
    """Fetch an episode row by its primary key.

    Args:
        conn: Open SQLite connection.
        id: Primary key value.

    Returns:
        :class:`EpisodeRow` if found, ``None`` otherwise.
    """
    _set_row_factory(conn)
    row = conn.execute("SELECT * FROM episode WHERE id = ?", (id,)).fetchone()
    if row is None:
        return None
    return _row_to_episode(row)


def get_episodes_for_season(conn: sqlite3.Connection, season_id: int) -> list[EpisodeRow]:
    """Fetch all episode rows for a season, ordered by episode number.

    Args:
        conn: Open SQLite connection.
        season_id: FK of the owning season row.

    Returns:
        List of :class:`EpisodeRow` instances, possibly empty.
    """
    _set_row_factory(conn)
    rows = conn.execute(
        "SELECT * FROM episode WHERE season_id = ? ORDER BY number",
        (season_id,),
    ).fetchall()
    return [_row_to_episode(r) for r in rows]

"""Indexer query helpers.

Provides read-only query functions that span multiple tables in the indexer
database.  These functions are intentionally kept separate from the repository
modules (which are table-scoped) so that cross-table queries have a single,
discoverable home.

Note:
    This is a stub module introduced in Phase 7.5.  The full query parser
    (structured filtering, sorting, pagination) is implemented in Phase 8.
    Only the queries required by Phase 7 consumers are present here.
"""

from __future__ import annotations

import sqlite3

from personalscraper.indexer.schema import MediaItemRow

# ---------------------------------------------------------------------------
# Row helper (mirrors item_repo._row_to_item but kept local to avoid coupling)
# ---------------------------------------------------------------------------


def _row_to_media_item(row: sqlite3.Row) -> MediaItemRow:
    """Convert a ``sqlite3.Row`` that contains the ``media_item`` columns to a dataclass.

    Args:
        row: A row fetched with ``conn.row_factory = sqlite3.Row``.  Must
            expose the standard ``media_item`` column set.

    Returns:
        Populated :class:`~personalscraper.indexer.schema.MediaItemRow` instance.
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


# ---------------------------------------------------------------------------
# Trailer-related queries
# ---------------------------------------------------------------------------


def find_items_without_trailer(conn: sqlite3.Connection) -> list[MediaItemRow]:
    """Return all media items that have no ``trailer_found`` attribute.

    Executes a LEFT JOIN between ``media_item`` and ``item_attribute``
    (filtered to ``key='trailer_found'``).  Rows where the attribute is
    absent (``ia.value IS NULL``) are returned — these are the items for
    which the trailer orchestrator has not yet recorded a successful download.

    Items whose ``trailer_found`` attribute exists (regardless of its string
    value) are excluded because the trailers subsystem treats any non-NULL
    value as a confirmation that a trailer is available.

    Args:
        conn: Open, read-capable SQLite connection to the indexer database.

    Returns:
        List of :class:`~personalscraper.indexer.schema.MediaItemRow` instances
        for every media item lacking a ``trailer_found`` attribute.  The list
        is ordered by ``media_item.id`` for deterministic output.
    """
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT media_item.id, media_item.kind, media_item.title, media_item.title_sort, "
        "media_item.original_title, media_item.year, media_item.category_id, "
        "media_item.tmdb_id, media_item.imdb_id, media_item.tvdb_id, "
        "media_item.nfo_status, media_item.artwork_json, "
        "media_item.date_created, media_item.date_modified, "
        "media_item.date_metadata_refreshed, media_item.is_locked, media_item.preferred_lang "
        "FROM media_item "
        "LEFT JOIN item_attribute ia "
        "  ON ia.item_id = media_item.id AND ia.key = 'trailer_found' "
        "WHERE ia.value IS NULL "
        "ORDER BY media_item.id",
    ).fetchall()
    return [_row_to_media_item(row) for row in rows]

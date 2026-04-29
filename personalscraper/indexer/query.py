"""Indexer query helpers.

Provides read-only query functions that span multiple tables in the indexer
database.  These functions are intentionally kept separate from the repository
modules (which are table-scoped) so that cross-table queries have a single,
discoverable home.

Note:
    The full flex-attr query parser (tokeniser, FIELD_REGISTRY, SQL composer)
    is implemented in Phase 8.2.  The :class:`QueryError` exception and
    :func:`execute` function are stubbed here so the Phase 8.1 CLI can import
    them; the stubs raise ``NotImplementedError`` until Phase 8.2 fills them in.
"""

from __future__ import annotations

import sqlite3

from personalscraper.indexer.schema import MediaItemRow

# ---------------------------------------------------------------------------
# QueryError — raised by the query parser for unknown fields / syntax errors
# ---------------------------------------------------------------------------


class QueryError(ValueError):
    """Raised by :func:`execute` when the query string is invalid.

    Phase 8.2 implements the full tokeniser and FIELD_REGISTRY.  Until then
    this is a plain ``ValueError`` subclass so callers can catch it uniformly.

    Args:
        message: Human-readable error description, e.g.
            ``"unknown field 'foo'; recognised fields: kind, title, year, ..."``.
    """

    def __init__(self, message: str) -> None:
        """Initialize with an actionable error message."""
        super().__init__(message)


# ---------------------------------------------------------------------------
# execute — top-level query entry point (stub until Phase 8.2)
# ---------------------------------------------------------------------------


def execute(
    conn: sqlite3.Connection,
    query_str: str,
    limit: int = 50,
) -> list[MediaItemRow]:
    """Tokenise *query_str*, compile a WHERE clause, and return matching items.

    This is a Phase 8.2 stub.  The full implementation (tokeniser,
    FIELD_REGISTRY, SQL fragment composer) lives in Phase 8.2.  Calling this
    stub raises :class:`NotImplementedError` with a clear message.

    Args:
        conn: Open, read-capable SQLite connection to the indexer database.
        query_str: Query string in the flex-attr syntax.
        limit: Maximum number of rows to return.

    Returns:
        List of :class:`~personalscraper.indexer.schema.MediaItemRow` instances.

    Raises:
        NotImplementedError: Always — full implementation is in Phase 8.2.
        QueryError: On invalid query syntax (Phase 8.2+).
    """
    raise NotImplementedError("execute() is a Phase 8.2 stub; the full query parser is not yet implemented.")


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

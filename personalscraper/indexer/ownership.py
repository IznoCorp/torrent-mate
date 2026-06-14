"""Indexer ownership predicate (RP6) — SELECT-only query layer.

Public API (Phase 2):
- :func:`is_owned` — answers "does the library contain a live file for
  this work?" via a chain of EXISTS sub-queries.

The ``IndexerOwnershipChecker`` adapter that wraps this function and
implements ``core.ownership.OwnershipChecker`` is added in Phase 3.

Import direction: stdlib + personalscraper.logger only.
No core.ownership import at runtime in this module (the adapter adds it).
"""

from __future__ import annotations

import sqlite3

from personalscraper.logger import get_logger

log = get_logger("indexer.ownership")


def is_owned(
    conn: sqlite3.Connection,
    *,
    kind: str,
    tvdb_id: int | None,
    tmdb_id: int | None,
    imdb_id: str | None,
    season: int | None = None,
    episode: int | None = None,
) -> bool:
    """Return True iff the library contains a live file for the given work.

    Matches ``media_item`` on the first available provider ID in priority
    order tvdb_id → tmdb_id → imdb_id, then follows the release chain to
    ``media_file`` and checks ``deleted_at IS NULL`` (live-file liveness
    filter). A soft-deleted file does not count as owned.

    Movie path:
        media_item(kind='movie', <provider_id>=?) →
        media_release(item_id) →
        media_file(deleted_at IS NULL)

    Episode path:
        media_item(kind='show', <provider_id>=?) →
        season(number=season) →
        episode(number=episode) →
        media_release(episode_id) →
        media_file(deleted_at IS NULL)

    Args:
        conn: Open, read-capable SQLite connection to the indexer database.
        kind: ``"movie"`` or ``"episode"``.
        tvdb_id: TVDB numeric ID (primary); matched first when not None.
        tmdb_id: TMDB numeric ID (fallback); matched when tvdb_id is None.
        imdb_id: IMDB string ID e.g. ``"tt0000001"`` (last resort).
        season: Season number; required when ``kind="episode"``.
        episode: Episode number; required when ``kind="episode"``.

    Returns:
        ``True`` if a live (non-soft-deleted) file exists for the work.
        ``False`` when the work is not found, has no file, or all files are
        soft-deleted.

    Raises:
        Nothing — callers must never crash on a predicate failure; the
        ``IndexerOwnershipChecker`` adapter (Phase 3) wraps this in a
        try/except for fail-soft behaviour.
    """
    if kind == "movie":
        return _is_owned_movie(conn, tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id)
    if kind == "episode":
        if season is None or episode is None:
            log.warning("is_owned.episode_missing_season_or_episode", kind=kind, season=season, episode=episode)
            return False
        return _is_owned_episode(
            conn, tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id, season=season, episode=episode
        )
    log.warning("is_owned.unknown_kind", kind=kind)
    return False


# ---------------------------------------------------------------------------
# Internal helpers — one per kind
# ---------------------------------------------------------------------------
#
# Provider IDs live in ``media_item.external_ids_json`` (migration 005 dropped
# the flat ``tvdb_id`` / ``tmdb_id`` / ``imdb_id`` columns and consolidated them
# into a hierarchical JSON column ``{provider: {series_id, episode_id}}``).
# The match clauses below mirror ``indexer/query.py``: numeric providers
# (tvdb, tmdb) ``CAST(... AS INTEGER)`` so an int bind param matches the
# string-stored ``series_id``; IMDb stays raw TEXT because its IDs carry the
# ``tt`` prefix. The indexes ``idx_external_ids_{tvdb,tmdb,imdb}`` (migration
# 005) cover the raw ``json_extract`` path.
_PROVIDER_CLAUSES: dict[str, str] = {
    "tvdb": "CAST(json_extract(mi.external_ids_json, '$.tvdb.series_id') AS INTEGER)=?",
    "tmdb": "CAST(json_extract(mi.external_ids_json, '$.tmdb.series_id') AS INTEGER)=?",
    "imdb": "json_extract(mi.external_ids_json, '$.imdb.series_id')=?",
}

# Base EXISTS clause for a live file linked to a movie-level media_item.
# The {provider_clause} placeholder is replaced by the caller with a concrete
# WHERE fragment from ``_PROVIDER_CLAUSES``.
_MOVIE_EXISTS_TMPL = (
    "SELECT EXISTS("
    "SELECT 1 FROM media_item mi"
    " JOIN media_release mr ON mr.item_id = mi.id"
    " JOIN media_file mf ON mf.release_id = mr.id"
    " WHERE mi.kind='movie' AND {provider_clause}"
    " AND mf.deleted_at IS NULL"
    ")"
)

_EPISODE_EXISTS_TMPL = (
    "SELECT EXISTS("
    "SELECT 1 FROM media_item mi"
    " JOIN season s ON s.item_id = mi.id"
    " JOIN episode e ON e.season_id = s.id"
    " JOIN media_release mr ON mr.episode_id = e.id"
    " JOIN media_file mf ON mf.release_id = mr.id"
    " WHERE mi.kind='show' AND {provider_clause}"
    " AND s.number=? AND e.number=?"
    " AND mf.deleted_at IS NULL"
    ")"
)


def _run_exists(conn: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> bool:
    """Execute a single-row EXISTS query and return the boolean result.

    Args:
        conn: Open SQLite connection.
        sql: SQL SELECT EXISTS(…) string.
        params: Bind parameters.

    Returns:
        ``True`` if EXISTS returns 1, ``False`` otherwise.
    """
    row = conn.execute(sql, params).fetchone()
    return bool(row[0]) if row else False


def _is_owned_movie(
    conn: sqlite3.Connection,
    *,
    tvdb_id: int | None,
    tmdb_id: int | None,
    imdb_id: str | None,
) -> bool:
    """Check movie ownership via the provider-id priority chain.

    Args:
        conn: Open SQLite connection.
        tvdb_id: TVDB ID (tried first).
        tmdb_id: TMDB ID (tried second).
        imdb_id: IMDB ID (tried last).

    Returns:
        ``True`` if a live file exists for any matched movie item.
    """
    if tvdb_id is not None:
        sql = _MOVIE_EXISTS_TMPL.format(provider_clause=_PROVIDER_CLAUSES["tvdb"])
        if _run_exists(conn, sql, (tvdb_id,)):
            return True
    if tmdb_id is not None:
        sql = _MOVIE_EXISTS_TMPL.format(provider_clause=_PROVIDER_CLAUSES["tmdb"])
        if _run_exists(conn, sql, (tmdb_id,)):
            return True
    if imdb_id is not None:
        sql = _MOVIE_EXISTS_TMPL.format(provider_clause=_PROVIDER_CLAUSES["imdb"])
        if _run_exists(conn, sql, (imdb_id,)):
            return True
    return False


def _is_owned_episode(
    conn: sqlite3.Connection,
    *,
    tvdb_id: int | None,
    tmdb_id: int | None,
    imdb_id: str | None,
    season: int,
    episode: int,
) -> bool:
    """Check episode ownership via the provider-id priority chain.

    Args:
        conn: Open SQLite connection.
        tvdb_id: TVDB ID (tried first).
        tmdb_id: TMDB ID (tried second).
        imdb_id: IMDB ID (tried last).
        season: Season number to match.
        episode: Episode number to match.

    Returns:
        ``True`` if a live file exists for the matched episode.
    """
    if tvdb_id is not None:
        sql = _EPISODE_EXISTS_TMPL.format(provider_clause=_PROVIDER_CLAUSES["tvdb"])
        if _run_exists(conn, sql, (tvdb_id, season, episode)):
            return True
    if tmdb_id is not None:
        sql = _EPISODE_EXISTS_TMPL.format(provider_clause=_PROVIDER_CLAUSES["tmdb"])
        if _run_exists(conn, sql, (tmdb_id, season, episode)):
            return True
    if imdb_id is not None:
        sql = _EPISODE_EXISTS_TMPL.format(provider_clause=_PROVIDER_CLAUSES["imdb"])
        if _run_exists(conn, sql, (imdb_id, season, episode)):
            return True
    return False


__all__ = ["is_owned"]

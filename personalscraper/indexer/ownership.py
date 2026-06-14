"""Indexer ownership predicate + adapter (RP6).

Public API:
- :func:`is_owned` (Phase 2) — SELECT-only predicate answering "does the
  library contain a live file for this work?" via a chain of EXISTS
  sub-queries.
- :class:`IndexerOwnershipChecker` (Phase 3) — the port implementation of
  ``core.ownership.OwnershipChecker``. Wraps :func:`is_owned` over a
  **lazy, read-only, lock-free** ``library.db`` connection and is
  **fail-soft**: any DB / open error → log + return ``False``.

Import direction: stdlib + ``personalscraper.core`` (port + identity) +
``personalscraper.logger``. ``indexer/`` may import ``core/`` (downward,
allowed). It does NOT import ``acquire/``.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Literal

from personalscraper.core.identity import MediaRef
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


# ---------------------------------------------------------------------------
# Port implementation — IndexerOwnershipChecker (Phase 3)
# ---------------------------------------------------------------------------


class IndexerOwnershipChecker:
    """Port implementation of :class:`~personalscraper.core.ownership.OwnershipChecker`.

    Wraps :func:`is_owned` over a **lazy, read-only, lock-free** connection to
    ``library.db``. The connection is NOT opened at construction (no boot I/O,
    no lock taken at the composition root — directly honouring the acquire.db
    lifetime-lock regression lesson): it is opened on the first :meth:`owns`
    call in autocommit + ``PRAGMA query_only=ON`` mode, so reads never take a
    writer lock and never serialise unrelated commands.

    Fail-soft contract (LOAD-BEARING): any exception from opening the database
    or running the predicate is caught, logged, and ``False`` is returned. The
    ownership check must never crash the caller (e.g. a future Follow/Ratio
    grab loop) — an unverifiable lookup degrades to "not owned" (fail-open at
    the policy level), never to a raised exception.

    This adapter lives in ``indexer/`` because it imports ``sqlite3`` +
    :func:`is_owned`; ``acquire/`` depends only on the ``core.ownership`` port
    and receives this implementation injected at the composition root.

    Import direction: imports ``core.ownership`` (port, via duck-typing — no
    runtime import needed) + ``core.identity`` (:class:`MediaRef`) only. Does
    NOT import ``acquire/`` — the allowed downward direction.

    Attributes:
        _db_path: Path to ``library.db`` (resolved by the config layer).
        _conn: Lazily-opened read-only SQLite connection, or ``None`` until the
            first :meth:`owns` call (and after :meth:`close`).
        _closed: ``True`` once :meth:`close` has run (prevents reopen).
    """

    def __init__(self, db_path: Path) -> None:
        """Initialise an INERT checker for ``db_path`` (no I/O).

        No connection is opened, no lock is taken, and the file is not touched
        until the first :meth:`owns` call.

        Args:
            db_path: Path to ``library.db`` (resolved by the config layer).
                The file need not exist at construction time; a missing or
                broken file surfaces as fail-soft ``False`` at lookup time.
        """
        self._db_path = db_path
        self._conn: sqlite3.Connection | None = None
        self._closed = False

    def _ensure_open(self) -> sqlite3.Connection:
        """Open the read-only, lock-free connection on first access.

        Opens ``library.db`` in autocommit mode (``isolation_level=None``) and
        applies ``PRAGMA query_only=ON`` so the connection can never take a
        writer lock. No ``BEGIN`` is issued and no lifetime lock is held — WAL
        reads are lock-free. After the first call ``self._conn`` stays open and
        subsequent calls return it directly.

        Returns:
            The open read-only :class:`sqlite3.Connection` to ``library.db``.

        Raises:
            RuntimeError: If the checker has already been closed.
            sqlite3.Error: If the database cannot be opened. The caller
                (:meth:`owns`) catches this for the fail-soft contract.
        """
        if self._closed:
            raise RuntimeError("IndexerOwnershipChecker is closed")
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(str(self._db_path), isolation_level=None, check_same_thread=False)
        conn.execute("PRAGMA query_only=ON")
        self._conn = conn
        log.info("indexer.ownership.opened", db_path=str(self._db_path))
        return conn

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Return True iff the library contains a live file for this work.

        Opens the read-only connection lazily, then delegates to
        :func:`is_owned`. Any exception — a missing/broken ``library.db``, a
        closed connection, or a predicate error — is caught and logged; ``False``
        is returned instead of propagating (fail-soft, LOAD-BEARING).

        Args:
            media_ref: Provider IDs (tvdb primary, tmdb fallback, imdb last).
            kind: ``"movie"`` or ``"episode"``.
            season: Season number; required when ``kind="episode"``.
            episode: Episode number; required when ``kind="episode"``.

        Returns:
            ``True`` if ownership is confirmed; ``False`` on any error or when
            the work is not found / all files are soft-deleted.
        """
        try:
            conn = self._ensure_open()
            return is_owned(
                conn,
                kind=kind,
                tvdb_id=media_ref.tvdb_id,
                tmdb_id=media_ref.tmdb_id,
                imdb_id=media_ref.imdb_id,
                season=season,
                episode=episode,
            )
        except Exception as exc:  # noqa: BLE001 — fail-soft: never raise into the caller
            log.warning(
                "indexer.ownership.lookup_failed",
                db_path=str(self._db_path),
                kind=kind,
                tvdb_id=media_ref.tvdb_id,
                tmdb_id=media_ref.tmdb_id,
                imdb_id=media_ref.imdb_id,
                error=str(exc),
            )
            return False

    def close(self) -> None:
        """Close the connection if one was opened (fail-soft, idempotent).

        Never raises (honours ``AcquireContext.close()``'s no-suppress
        contract): a connection-close error is swallowed and logged. Double-
        close is a no-op, and close-without-open (``owns`` never called) is a
        pure no-op — there is no lifetime lock to release.
        """
        if self._closed:
            return
        self._closed = True
        if self._conn is None:
            return
        try:
            self._conn.close()
        except Exception as exc:  # noqa: BLE001 — fail-soft close contract
            log.warning("indexer.ownership.close_conn_failed", error=str(exc))
        log.info("indexer.ownership.closed", db_path=str(self._db_path))


__all__ = ["IndexerOwnershipChecker", "is_owned"]

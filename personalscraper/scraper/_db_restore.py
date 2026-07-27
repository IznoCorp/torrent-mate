"""BDD-backed NFO/artwork restore subsystem for re-ingested movies.

Extracted verbatim from ``movie_service.py`` (SCRAPER-10: the movie service
embedded a raw-SQL restore subsystem that pushed it toward the module-size
ceiling). The behaviour is unchanged except that the ``library.db`` lookup now
runs through a **lock-free, read-only** connection (``file:...?mode=ro`` URI),
honouring the single-writer ``library.db`` discipline — restore only ever
SELECTs, so it must never take a writer lock nor serialise unrelated commands.

When a movie in staging produces no confident TMDB match but already has a
valid ``media_item`` row (from a previous successful scrape + dispatch), the
subsystem copies the NFO and artwork files back from the original dispatch
location to the staging directory. Every early return produces a typed
:class:`RestoreOutcome` variant instead of mutating a ``ScrapeResult`` — the
caller (:meth:`~personalscraper.scraper.movie_service.MovieServiceMixin.scrape_movie`)
maps the variant onto the result.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

log = get_logger("scraper")


@dataclass(frozen=True)
class RestoreOutcome:
    """Base for the ``_restore_from_db`` outcome sum type."""

    pass


@dataclass(frozen=True)
class Restored(RestoreOutcome):
    """Restore succeeded — caller sets ``result.action = 'restored_from_db'``."""

    files_copied: int
    nfo_path: Path


@dataclass(frozen=True)
class NoDb(RestoreOutcome):
    """Restoration unavailable — config/db_path missing or non-file."""

    reason: str  # e.g. "config_is_none" | "db_path_is_none" | "db_path_not_path" | "db_file_missing" | "connect_failed"


@dataclass(frozen=True)
class NoMatch(RestoreOutcome):
    """No ``media_item`` row matches the staging title."""

    title: str


@dataclass(frozen=True)
class NoDispatchPath(RestoreOutcome):
    """Matched item has no ``dispatch_path`` attribute or it points to a missing dir."""

    item_id: int


@dataclass(frozen=True)
class NoNfoAtDispatch(RestoreOutcome):
    """Dispatch directory exists but contains no NFO files."""

    item_id: int
    dispatch_path: str


@dataclass(frozen=True)
class AmbiguousNfo(RestoreOutcome):
    """Multiple NFO candidates at dispatch — manual review required."""

    item_id: int
    candidates: tuple[str, ...]


@dataclass(frozen=True)
class CopyFailed(RestoreOutcome):
    """Filesystem copy failed mid-way; rollback executed."""

    files_rolled_back: int
    error: str


def _open_readonly_conn(db_file: Path) -> sqlite3.Connection:
    """Open a lock-free, read-only connection to ``library.db``.

    Uses the SQLite ``file:...?mode=ro`` URI — mirroring
    :func:`personalscraper.cli_helpers.boundary._open_readonly_indexer_conn`
    (the CLI ``db-read`` boundary) — so the connection is genuinely read-only:
    any write raises :class:`sqlite3.OperationalError`, no write-ahead log or
    migration is ever created, and no writer lock is taken. This honours the
    single-writer ``library.db`` discipline; the restore lookup only SELECTs.

    Args:
        db_file: Absolute path to an existing ``library.db`` file.

    Returns:
        An open read-only :class:`sqlite3.Connection` with the ``sqlite3.Row``
        row factory installed.
    """
    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _restore_from_db(
    config: "Config | None",
    dry_run: bool,
    movie_dir: Path,
    title: str,
    year: int | None,
) -> RestoreOutcome:
    """Restore NFO and artwork from BDD when a re-ingested movie has a valid DB entry.

    When a movie in staging produces no confident TMDB match but already
    has a valid ``media_item`` row (from a previous successful
    scrape+dispatch), this copies the NFO and artwork files back from
    the original dispatch location to the staging directory.

    Fail-soft — every early return produces a typed ``RestoreOutcome``
    variant instead of mutating a ``ScrapeResult``.

    Args:
        config: Application config (may be None or test stub).
        dry_run: If True, log what would be copied without copying.
        movie_dir: Path to the staging movie directory.
        title: Parsed movie title for the DB lookup.
        year: Optional release year (informational for logging).

    Returns:
        A ``RestoreOutcome`` variant (``Restored`` on success, or a
        skip/failure variant describing why restoration didn't happen).
    """
    # 1. Guard: no config or no db_path
    if config is None:
        return NoDb(reason="config_is_none")
    db_path = config.indexer.db_path
    if db_path is None:
        return NoDb(reason="db_path_is_none")
    if isinstance(db_path, str):
        db_path = Path(db_path)
    if not isinstance(db_path, Path):
        log.info(
            "movie_db_restore_skipped_db_path_not_path",
            reason="config.indexer.db_path is not a string or Path (likely MagicMock test stub)",
            type=type(db_path).__name__,
        )
        return NoDb(reason="db_path_not_path")

    db_file = db_path.expanduser()
    if not db_file.is_absolute():
        db_file = Path.cwd() / db_file
    if not db_file.is_file():
        return NoDb(reason="db_file_missing")

    # 2. Open a lock-free, read-only connection (single-writer discipline).
    try:
        conn = _open_readonly_conn(db_file)
    except Exception:
        log.warning("movie_db_restore_connect_failed", db_path=str(db_file), exc_info=True)
        return NoDb(reason="connect_failed")

    copied_files: list[Path] = []
    try:
        # 3. Look up a valid BDD entry by title
        row = conn.execute(
            "SELECT mi.id, mi.year AS media_year, ia.value AS dispatch_path "
            "FROM media_item mi "
            "LEFT JOIN item_attribute ia ON ia.item_id = mi.id AND ia.key = 'dispatch_path' "
            "WHERE mi.kind = 'movie' AND mi.title = ? AND mi.nfo_status = 'valid' "
            "ORDER BY mi.date_modified DESC LIMIT 1",
            (title,),
        ).fetchone()

        if row is None:
            log.info("movie_db_restore_skipped_no_match", title=title, year=year)
            return NoMatch(title=title)

        item_id = row["id"]
        dispatch_path_str = row["dispatch_path"]

        if dispatch_path_str is None:
            log.info("movie_db_restore_skipped_no_dispatch_path", title=title, item_id=item_id)
            return NoDispatchPath(item_id=item_id)

        dispatch_dir = Path(dispatch_path_str)
        if not dispatch_dir.is_dir():
            log.info(
                "movie_db_restore_skipped_dispatch_path_missing",
                title=title,
                dispatch_path=str(dispatch_dir),
            )
            return NoDispatchPath(item_id=item_id)

        # 4. Locate NFO file at dispatch location
        from personalscraper.nfo_utils import glob_nfo_candidates  # noqa: PLC0415

        nfo_files = glob_nfo_candidates(dispatch_dir)
        if not nfo_files:
            log.info(
                "movie_db_restore_skipped_no_nfo_at_dispatch",
                title=title,
                dispatch_path=str(dispatch_dir),
            )
            return NoNfoAtDispatch(item_id=item_id, dispatch_path=str(dispatch_dir))
        if len(nfo_files) > 1:
            log.info(
                "movie_db_restore_skipped_ambiguous_nfo",
                title=title,
                dispatch_path=str(dispatch_dir),
                candidates=[f.name for f in nfo_files],
            )
            return AmbiguousNfo(
                item_id=item_id,
                candidates=tuple(f.name for f in nfo_files),
            )

        dispatch_nfo = nfo_files[0]
        dest_nfo = movie_dir / dispatch_nfo.name

        # 5. Locate artwork files (any image at the dispatch root)
        artwork_files: list[Path] = []
        for ext in (".jpg", ".png", ".jpeg"):
            artwork_files.extend(sorted(dispatch_dir.glob(f"*{ext}")))

        # 6. Copy (or log in dry-run mode)
        if dry_run:
            log.info(
                "movie_db_restore_would_copy",
                title=title,
                item_id=item_id,
                dispatch_path=str(dispatch_dir),
                nfo=dispatch_nfo.name,
                artwork=[f.name for f in artwork_files],
            )
            return Restored(files_copied=0, nfo_path=dest_nfo)

        import shutil

        shutil.copy2(dispatch_nfo, dest_nfo)
        copied_files.append(dest_nfo)
        log.info(
            "movie_db_restore_copied_nfo",
            src=str(dispatch_nfo),
            dst=str(dest_nfo),
        )

        for art_file in artwork_files:
            dest_art = movie_dir / art_file.name
            shutil.copy2(art_file, dest_art)
            copied_files.append(dest_art)
            log.info(
                "movie_db_restore_copied_artwork",
                src=str(art_file),
                dst=str(dest_art),
            )

        log.info(
            "movie_db_restore_success",
            title=title,
            item_id=item_id,
            dispatch_path=str(dispatch_dir),
            files_copied=len(copied_files),
        )
        return Restored(files_copied=len(copied_files), nfo_path=dest_nfo)

    except Exception as exc:
        log.warning(
            "movie_db_restore_failed",
            title=title,
            files_to_rollback=len(copied_files),
            exc_info=True,
        )
        for f in copied_files:
            try:
                f.unlink(missing_ok=True)
            except OSError as unlink_exc:
                log.warning(
                    "movie_db_restore_rollback_failed",
                    path=str(f),
                    error=str(unlink_exc),
                )
        return CopyFailed(files_rolled_back=len(copied_files), error=str(exc))
    finally:
        try:
            conn.close()
        except Exception:
            pass

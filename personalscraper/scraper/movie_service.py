"""Extracted scraper service module."""

from __future__ import annotations

import re
import sqlite3
from itertools import zip_longest
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from personalscraper.api.metadata._base import MediaDetails, Notations
from personalscraper.logger import get_logger
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.scraper._shared import ScrapeResult, _find_video_file
from personalscraper.scraper.classifier import _parse_folder_name
from personalscraper.scraper.confidence import LOW_CONFIDENCE
from personalscraper.scraper.rename_service import _cleanup_stale_files, _merge_dirs
from personalscraper.text_utils import sanitize_filename

if TYPE_CHECKING:
    from collections.abc import Callable

    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.conf.models.config import Config
    from personalscraper.naming_patterns import NamingPatterns
    from personalscraper.scraper.artwork import ArtworkDownloader
    from personalscraper.scraper.confidence import MatchResult
    from personalscraper.scraper.nfo_generator import NFOGenerator

log = get_logger("scraper")


def _media_details_to_movie_data(details: MediaDetails) -> dict[str, Any]:
    """Adapt typed MediaDetails into the legacy movie_data dict shape.

    Phase 27 transitional shim — mirrors the TV equivalent
    (``_tvdb_series_to_show_data``) for movies. The downstream NFO
    generator and artwork downloader still expect the historical
    TMDB-flavoured raw dict, so this helper renders the typed model
    into that dict at the boundary, leaving the consumers untouched
    until they migrate.

    Mapping:
    - title / original_title / overview / year → top-level fields
    - genres + genre_ids → ``genres: [{"id", "name"}]`` zipped
    - rating → ``vote_average``
    - runtime_minutes → ``runtime``
    - origin_countries / production_countries → both lists, dict shape
    - external_ids → ``external_ids: {"imdb_id", "tvdb_id", ...}``
    - images (curated ArtworkItem list) split by type into ``posters``
      and ``backdrops`` arrays under ``images: {posters, backdrops}``
    - primary_backdrop_url surfaces as top-level ``backdrop_path`` for
      the legacy fallback path in ``ArtworkDownloader``.

    Args:
        details: Typed metadata payload from a TMDB ``get_movie`` call.

    Returns:
        Dict whose keys match the legacy TMDB movie response shape used
        by NFO + artwork consumers.
    """
    posters = [
        {"file_path": a.url, "iso_639_1": a.language, "vote_average": a.vote_average}
        for a in details.images
        if a.type == "poster" and a.url
    ]
    backdrops = [
        {"file_path": a.url, "iso_639_1": a.language, "vote_average": a.vote_average}
        for a in details.images
        if a.type == "backdrop" and a.url
    ]
    logos = [
        {"file_path": a.url, "iso_639_1": a.language, "vote_average": a.vote_average}
        for a in details.images
        if a.type == "landscape" and a.url
    ]

    # Provider id is a string in the typed model; downstream often expects int
    # for ``id`` (TMDB numeric). Coerce when it parses cleanly.
    raw_id = details.provider_id
    pid: int | str = int(raw_id) if raw_id.isdigit() else raw_id

    return {
        "id": pid,
        "title": details.title,
        "original_title": details.original_title,
        "name": details.title,  # alias for code paths that branch on TV-style "name"
        "original_name": details.original_title,
        "overview": details.overview,
        "release_date": f"{details.year}-01-01" if details.year else "",
        "first_air_date": f"{details.year}-01-01" if details.year else "",
        "runtime": details.runtime_minutes,
        "vote_average": details.rating or 0.0,
        "vote_count": 0,
        "genres": [
            {"id": gid, "name": gname}
            for gid, gname in zip_longest(details.genre_ids, details.genres, fillvalue=None)
            if gid is not None or gname
        ],
        "origin_country": list(details.origin_countries),
        "production_countries": [{"iso_3166_1": c} for c in details.production_countries],
        "production_companies": [],
        "external_ids": {f"{k}_id": v for k, v in details.external_ids.items()},
        "imdb_id": details.external_ids.get("imdb", ""),
        "images": {"posters": posters, "backdrops": backdrops, "logos": logos},
        "backdrop_path": details.primary_backdrop_url,
        "credits": {"cast": [], "crew": []},
        "release_dates": {"results": []},
    }


def _coerce_to_movie_data(data: MediaDetails | dict[str, Any]) -> dict[str, Any]:
    """Return ``data`` as a movie_data-shaped dict.

    Accepts the typed MediaDetails emitted by api-unify clients or a
    legacy raw-dict from older callers / test fixtures.
    """
    if isinstance(data, MediaDetails):
        return _media_details_to_movie_data(data)
    return data


def _media_details_to_show_data(details: MediaDetails) -> dict[str, Any]:
    """Adapt typed MediaDetails into the legacy show_data dict for TV shows.

    Phase 27 transitional shim — extension of ``_media_details_to_movie_data``
    that also surfaces the ``seasons`` summary array. The artwork downloader
    uses ``show_data["seasons"]`` to find per-season posters keyed on
    ``season_number``; without this the season-poster path silently degrades
    to "show poster only" on every TMDB-resolved TV show repair.

    Args:
        details: Typed metadata from a TMDB ``get_tv`` call.

    Returns:
        Dict whose keys match the legacy TMDB TV-show response shape used by
        NFO + artwork consumers.
    """
    base = _media_details_to_movie_data(details)
    base["seasons"] = [
        {
            "season_number": s.season_number,
            "episode_count": s.episode_count,
            "poster_path": s.poster_url,
            "name": "",
            "overview": "",
        }
        for s in details.seasons
    ]
    return base


def _coerce_to_show_data(data: MediaDetails | dict[str, Any]) -> dict[str, Any]:
    """Return ``data`` as a show_data-shaped dict for TV consumers."""
    if isinstance(data, MediaDetails):
        return _media_details_to_show_data(data)
    return data


def _restore_from_db(
    config: "Config | None",
    dry_run: bool,
    movie_dir: Path,
    title: str,
    year: int | None,
    result: ScrapeResult,
) -> bool:
    """Restore NFO and artwork from BDD when a re-ingested movie has a valid DB entry.

    When a movie in staging produces no confident TMDB match but already
    has a valid ``media_item`` row (from a previous successful
    scrape+dispatch), this copies the NFO and artwork files back from
    the original dispatch location to the staging directory.

    Fail-soft — every early return is a logged ``False`` without
    touching ``result``.

    Args:
        config: Application config (may be None or test stub).
        dry_run: If True, log what would be copied without copying.
        movie_dir: Path to the staging movie directory.
        title: Parsed movie title for the DB lookup.
        year: Optional release year (informational for logging).
        result: ScrapeResult mutated on success (action set to
            ``"restored_from_db"``).

    Returns:
        True if restoration succeeded, False otherwise.
    """
    # 1. Guard: no config or no db_path
    if config is None:
        return False
    db_path = config.indexer.db_path
    if db_path is None:
        return False
    if isinstance(db_path, str):
        db_path = Path(db_path)
    if not isinstance(db_path, Path):
        log.info(
            "movie_db_restore_skipped_db_path_not_path",
            reason="config.indexer.db_path is not a string or Path (likely MagicMock test stub)",
            type=type(db_path).__name__,
        )
        return False

    db_file = db_path.expanduser()
    if not db_file.is_absolute():
        db_file = Path.cwd() / db_file
    if not db_file.is_file():
        return False

    # 2. Open connection with canonical PRAGMA
    try:
        from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415

        conn = sqlite3.connect(str(db_file))
        _apply_pragmas(conn)
        conn.row_factory = sqlite3.Row
    except Exception:
        log.warning("movie_db_restore_connect_failed", db_path=str(db_file), exc_info=True)
        return False

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
            return False

        item_id = row["id"]
        dispatch_path_str = row["dispatch_path"]

        if dispatch_path_str is None:
            log.info("movie_db_restore_skipped_no_dispatch_path", title=title, item_id=item_id)
            return False

        dispatch_dir = Path(dispatch_path_str)
        if not dispatch_dir.is_dir():
            log.info(
                "movie_db_restore_skipped_dispatch_path_missing",
                title=title,
                dispatch_path=str(dispatch_dir),
            )
            return False

        # 4. Locate NFO file at dispatch location
        from personalscraper.nfo_utils import glob_nfo_candidates  # noqa: PLC0415

        nfo_files = glob_nfo_candidates(dispatch_dir)
        if not nfo_files:
            log.info(
                "movie_db_restore_skipped_no_nfo_at_dispatch",
                title=title,
                dispatch_path=str(dispatch_dir),
            )
            return False
        if len(nfo_files) > 1:
            log.info(
                "movie_db_restore_skipped_ambiguous_nfo",
                title=title,
                dispatch_path=str(dispatch_dir),
                candidates=[f.name for f in nfo_files],
            )
            return False

        dispatch_nfo = nfo_files[0]

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
            result.action = "restored_from_db"
            return True

        import shutil

        dest_nfo = movie_dir / dispatch_nfo.name
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

        result.action = "restored_from_db"
        log.info(
            "movie_db_restore_success",
            title=title,
            item_id=item_id,
            dispatch_path=str(dispatch_dir),
            files_copied=len(copied_files),
        )
        return True

    except Exception:
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
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass


_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2} - .+\.\w+$")
_EPISODE_FALLBACK_RE = re.compile(r"^S\d{2}E0*(\d+) - Episode 0*\1\.\w+$", re.IGNORECASE)


class MovieServiceMixin:
    """Movie scrape service methods."""

    patterns: "NamingPatterns"
    dry_run: bool
    _tmdb: "TMDBClient"
    _artwork: "ArtworkDownloader"
    config: "Config | None"
    _nfo: "NFOGenerator"
    _classify_item: "Callable[..., str | None]"
    _resolve_title: "Callable[..., str]"
    _strip_trailing_year: "Callable[[str], str]"
    _check_missing_movie_artwork: "Callable[..., list[str]]"
    _recover_movie_artwork: "Callable[..., None]"
    _repair_movie_dir: "Callable[..., bool]"

    def _resolve_external_ids(
        self,
        canonical_provider: str,
        movie_ids: dict[str, str],
        expected_title: str,
        expected_year: int | None,
    ) -> tuple[dict[str, str], list["Notations"]]:
        """Resolve trusted cross-provider IDs + ratings for a movie (Q5=B).

        Thin delegate to
        :func:`personalscraper.scraper._xref.resolve_external_ids` —
        the TV and movie services share one implementation. Movies
        differ only in that there is no per-episode ``_xref_enrichment``
        companion step.
        """
        from personalscraper.scraper._xref import resolve_external_ids as _resolve  # noqa: PLC0415

        return _resolve(
            canonical_provider=canonical_provider,
            ids=movie_ids,
            expected_title=expected_title,
            expected_year=expected_year,
            family_to_client=self._family_to_client,
            imdb_client=getattr(self, "_imdb", None),
            rt_client=getattr(self, "_rotten_tomatoes", None),
        )

    def _family_to_client(self, family: str) -> Any | None:
        """Map a provider family to the wired client / façade (or ``None``)."""
        mapping: dict[str, Any] = {
            "tvdb": getattr(self, "_tvdb", None),
            "tmdb": getattr(self, "_tmdb", None),
            "imdb": getattr(self, "_imdb", None),
        }
        return mapping.get(family)

    def _match_movie_candidates(
        self,
        title: str,
        year: int | None,
        result: ScrapeResult,
    ) -> MatchResult | None:
        """Search TMDB for movie candidates matching the given title and year.

        Args:
            title: Movie title to search for.
            year: Optional release year to narrow the search.
            result: ScrapeResult for error tracking.

        Returns:
            MatchResult on successful API call (may be None when no candidate
            was found), or None when an API exception occurred (result.error
            is set).
        """
        try:
            from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

            return scraper_api.match_movie(self._tmdb, title, year)
        except Exception as e:
            result.error = f"Match failed: {e}"
            log.error("movie_match_failed", title=title, error=str(e), exc_info=True)
            return None

    def _select_best_candidate(
        self,
        match: MatchResult | None,
        title: str,
        year: int | None,
        result: ScrapeResult,
    ) -> bool:
        """Check confidence of the matched candidate and reject low-confidence matches.

        Args:
            match: MatchResult from TMDB (may be None).
            title: Movie title for logging.
            year: Optional release year for logging.
            result: ScrapeResult for action tracking.

        Returns:
            True if the candidate is accepted and result.match is set,
            False if skipped.
        """
        if match is None or match.confidence < LOW_CONFIDENCE:
            result.action = "skipped_low_confidence"
            log.warning(
                "movie_no_confident_match",
                title=title,
                year=year,
                score=round(match.confidence if match else 0.0, 2),
            )
            return False
        result.match = match
        log.info(
            "movie_matched",
            title=title,
            api_title=match.api_title,
            source=match.source,
            confidence=round(match.confidence, 2),
        )
        return True

    def scrape_movie(self, movie_dir: Path) -> ScrapeResult:
        """Scrape a single movie: match -> NFO -> artwork.

        Flow:
        1. Parse title + year from folder name
        2. If valid NFO exists: recover missing artwork if needed, then skip
        3. If corrupt NFO exists: delete it and re-scrape
        4. Match against TMDB
        5. Get full movie details + resolve local title
        6. Rename folder to canonical format
        7. Extract stream info from video file
        8. Generate and write NFO
        9. Download artwork (poster + landscape)

        Args:
            movie_dir: Path to the movie directory.

        Returns:
            ScrapeResult with action and details.
        """
        title, year = _parse_folder_name(movie_dir.name)
        result = ScrapeResult(media_path=movie_dir, media_type="movie")

        # Check for existing valid NFO
        nfo_name = self.patterns.format("movie_nfo", Title=title)
        nfo_path = movie_dir / nfo_name
        if _is_nfo_complete(nfo_path):
            # Check for missing artwork -- recover without re-scraping
            missing = self._check_missing_movie_artwork(movie_dir, title)
            if missing and not self.dry_run:
                self._recover_movie_artwork(nfo_path, movie_dir, result)
            # Set action: artwork_recovered if recovery succeeded, else skipped
            # Repair pass: remove residual NFOs
            repaired = self._repair_movie_dir(movie_dir, title)
            if repaired and result.action != "artwork_recovered":
                result.action = "repaired"
            elif result.action != "artwork_recovered":
                result.action = "skipped_already_done"
            log.info("nfo_valid", action=result.action, directory=movie_dir.name)
            return result

        # Corrupt NFO: delete before re-scrape.  Honor dry_run -- without
        # this guard a dry-run pass that detected drift would still
        # unlink the file, leaving the next real run thinking the NFO is
        # missing from the start (and downstream verify reports it as
        # blocked).  In dry_run mode we log the would-be deletion and
        # leave the file in place so the staging area is unchanged.
        if nfo_path.exists():
            if self.dry_run:
                log.info("nfo_corrupt_rescrape_would_delete", filename=nfo_path.name)
            else:
                log.warning("nfo_corrupt_rescrape", filename=nfo_path.name)
                try:
                    nfo_path.unlink()
                except OSError as exc:
                    result.error = f"Cannot delete corrupt NFO: {exc}"
                    log.error("nfo_corrupt_delete_failed", path=str(nfo_path), error=str(exc))
                    return result

        # Match against TMDB
        match = self._match_movie_candidates(title, year, result)
        if result.error:
            return result
        if not self._select_best_candidate(match, title, year, result):
            if _restore_from_db(self.config, self.dry_run, movie_dir, title, year, result):
                return result
            result.action = result.action or "skipped_low_confidence"
            return result
        assert match is not None  # narrowed by _select_best_candidate returning True

        # Get full movie details (needed for local title resolution)
        try:
            movie_data = self._tmdb.get_movie(match.api_id)
        except Exception as e:
            result.error = f"Get details failed: {e}"
            log.error("movie_details_failed", api_title=match.api_title, error=str(e), exc_info=True)
            return result

        # Resolve title: use local FR title if preferred and available
        resolved_title = self._strip_trailing_year(self._resolve_title(match.api_title, movie_data, "movie"))
        api_year = match.api_year or year
        # Folder name is filesystem-safe (sanitize_filename strips ``:``, ``?``,
        # ``"`` etc. for NTFS compatibility) while the NFO ``<title>`` keeps
        # the original punctuation for Plex/Kodi display. The two values are
        # *intentionally* allowed to diverge -- same item ``Some Show: Subtitle``
        # ends up as folder ``Some Show Subtitle`` and NFO title
        # ``Some Show: Subtitle``. Verified items downstream (verify/run.py)
        # compare on NFC-normalised, NTFS-sanitised forms so this asymmetry
        # does not cause false-positive drift.
        clean_name = sanitize_filename(f"{resolved_title} ({api_year})" if api_year else resolved_title)

        # Save old title before rename for stale file cleanup
        old_title = title

        # Rename folder to clean format if it doesn't match
        if movie_dir.name != clean_name:
            new_path = movie_dir.parent / clean_name
            if not self.dry_run:
                try:
                    if new_path.exists():
                        moved, merge_failed = _merge_dirs(movie_dir, new_path)
                        log.info("movie_folder_merged", source=movie_dir.name, dest=clean_name, items=moved)
                        if merge_failed:
                            result.warnings.append(f"Partial merge: {merge_failed} item(s) failed")
                    else:
                        movie_dir.rename(new_path)
                        log.info("movie_folder_renamed", source=movie_dir.name, dest=clean_name)
                    movie_dir = new_path
                    result.media_path = new_path
                    title = resolved_title
                    nfo_name = self.patterns.format("movie_nfo", Title=title)
                    nfo_path = movie_dir / nfo_name
                except OSError as exc:
                    result.error = f"Rename/merge failed: {exc}"
                    log.error("movie_folder_rename_failed", source=movie_dir.name, dest=clean_name, error=str(exc))
                    return result
                # Non-critical: clean stale artwork/NFO from before rename
                try:
                    _cleanup_stale_files(movie_dir, old_title, resolved_title)
                except OSError as exc:
                    log.warning("stale_cleanup_failed", directory=movie_dir.name, error=str(exc))
            else:
                action = "merge into" if new_path.exists() else "rename"
                log.info("movie_folder_would_rename", action=action, source=movie_dir.name, dest=clean_name)

        # Rename video file to clean title and extract stream info
        video_file = _find_video_file(movie_dir)
        stream_info = None
        if video_file:
            clean_video_name = (
                self.patterns.format(
                    "movie_video",
                    Title=title,
                )
                + video_file.suffix
            )
            if video_file.name != clean_video_name:
                new_video = movie_dir / clean_video_name
                if not self.dry_run:
                    try:
                        video_file.rename(new_video)
                        log.info("movie_video_renamed", source=video_file.name, dest=clean_video_name)
                        video_file = new_video
                    except OSError as exc:
                        log.warning(
                            "movie_video_rename_failed",
                            source=video_file.name,
                            dest=clean_video_name,
                            directory=movie_dir.name,
                            error=str(exc),
                        )
                        result.warnings.append(f"Video rename failed: {video_file.name}: {exc}")
                else:
                    log.info("movie_video_would_rename", source=video_file.name, dest=clean_video_name)
            from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

            stream_info = scraper_api.extract_stream_info(video_file)

        # Classify item -- must run before NFO write so the
        # category_id can be embedded in the NFO by nfo_generator.
        category_id = self._classify_item(
            media_type="movie",
            path=movie_dir,
            title=title,
            api_data=movie_data,
            tmdb_id=match.api_id,
            nfo_path=nfo_path if nfo_path.exists() else None,
        )
        result.category_id = category_id
        if category_id is None and self.config is not None:
            # Config is present but no category matched -- skip this item
            result.action = "skipped_no_category"
            return result

        # api-unify phase 27: movie_data arrives as MediaDetails from
        # ``self._tmdb.get_movie``. Adapt to the legacy raw-dict shape the
        # NFO generator + artwork downloader still consume. Once those two
        # consumers migrate to MediaDetails, this conversion can be deleted.
        movie_data_dict = _coerce_to_movie_data(movie_data)

        # Generate and write NFO
        try:
            xml = self._nfo.generate_movie_nfo(movie_data_dict, stream_info, category_id=category_id)
            if not self.dry_run:
                self._nfo.write_nfo(xml, nfo_path)
                result.nfo_written = True
                log.info("nfo_written", filename=nfo_path.name)
            else:
                log.info("nfo_would_write", filename=nfo_path.name)
        except Exception as e:
            result.error = f"NFO generation failed: {e}"
            log.error("nfo_generation_failed", title=title, error=str(e), exc_info=True)
            return result

        # Download artwork
        try:
            downloaded = self._artwork.download_movie_artwork(
                movie_data_dict,
                movie_dir,
                self.patterns,
            )
            result.artwork_downloaded = [p.name for p in downloaded]
        except (requests.RequestException, OSError, KeyError, AttributeError) as e:
            log.warning("movie_artwork_failed", title=title, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork failed: {e}")

        result.action = "scraped"
        return result

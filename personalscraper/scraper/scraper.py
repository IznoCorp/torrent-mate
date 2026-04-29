"""Main scraping orchestrator for movies and TV shows.

Coordinates metadata matching, NFO generation, artwork download, and
episode management into a complete scraping pipeline. Each media item
produces a ScrapeResult indicating what was done.

Movie flow: parse folder → match TMDB → get details → NFO → artwork
TV show flow: parse folder → match TVDB/TMDB → get details → tvshow.nfo →
              artwork → season dirs → episode titles → rename → episode NFOs
"""

import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import requests
from guessit.api import GuessitException

from personalscraper.conf import classifier as _classifier
from personalscraper.conf.models import Config
from personalscraper.config import Settings
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE, NamingPatterns
from personalscraper.nfo_utils import is_nfo_complete as _is_nfo_complete
from personalscraper.scraper.artwork import ArtworkDownloader
from personalscraper.scraper.confidence import (
    LOW_CONFIDENCE,
    MatchResult,
    match_movie,
    match_tvshow,
)
from personalscraper.scraper.episode_manager import (
    _extract_season_episode,
    create_season_dirs,
    match_episode_files,
    rename_episodes,
)
from personalscraper.scraper.keywords_cache import KeywordsCache
from personalscraper.scraper.mediainfo import extract_stream_info
from personalscraper.scraper.nfo_generator import NFOGenerator
from personalscraper.scraper.tmdb_client import TMDBClient
from personalscraper.scraper.tvdb_client import TVDBClient
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS
from personalscraper.text_utils import sanitize_filename

log = get_logger("scraper")

# Regex for parsing "Title (Year)" folder names
_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")

# Regex for extracting SxxExx episode identifiers from filenames
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)

# Strict episode filename pattern used by _verify_existing_scrape to detect
# legacy title-less fallbacks. Current scraper output always includes a title
# segment after ``SxxExx`` (real or synthetic); a bare ``SxxExx.ext`` means
# the show was scraped before the title-less fallback was upgraded.
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2} - .+\.\w+$")


def _merge_dirs(source: Path, target: Path) -> tuple[int, int]:
    """Merge contents of source directory into target, then remove source.

    Files in source that already exist in target are replaced
    (source always wins). Subdirectories are merged recursively.
    Per-item errors are logged and skipped — the merge continues
    with remaining items. Source is only removed if fully emptied.

    Args:
        source: Directory to merge from (removed only if fully emptied).
        target: Directory to merge into (must exist).

    Returns:
        Tuple of (moved_count, failed_count).
    """
    import shutil as _shutil

    moved = 0
    failed = 0
    for item in source.iterdir():
        dest = target / item.name
        try:
            if item.is_dir() and dest.is_dir():
                # Recursive merge for subdirectories (e.g. Saison 01/)
                sub_moved, sub_failed = _merge_dirs(item, dest)
                moved += sub_moved
                failed += sub_failed
            else:
                # Move file/dir, replacing if exists
                if dest.exists():
                    if dest.is_dir():
                        _shutil.rmtree(dest)
                    else:
                        dest.unlink()
                _shutil.move(str(item), str(dest))
                moved += 1
        except (OSError, _shutil.Error) as exc:
            failed += 1
            log.warning("merge_item_failed", item=item.name, dest=str(dest), error=str(exc))
    # Remove empty source after merge — preserve if items remain
    try:
        if source.exists() and not any(source.iterdir()):
            source.rmdir()
    except OSError as exc:
        log.warning("merge_source_rmdir_failed", source=source.name, error=str(exc))
    if failed:
        log.warning(
            "merge_partial",
            source=source.name,
            target=target.name,
            moved=moved,
            failed=failed,
        )
    return moved, failed


@dataclass
class ScrapeResult:
    """Result of scraping a single media item.

    Attributes:
        media_path: Path to the media directory.
        media_type: Type of media ("movie" or "tvshow").
        match: Matched API result, or None if no match.
        category_id: Category ID from classifier.classify(), or None.
        nfo_written: Whether an NFO file was written.
        artwork_downloaded: List of downloaded artwork filenames.
        episodes_renamed: Number of episodes renamed (0 for movies).
        action: Result action ("scraped", "skipped_low_confidence",
            "skipped_already_done", "artwork_recovered", "error",
            "skipped_no_category").
        error: Error message if action is "error".
        warnings: Non-fatal issues (e.g. artwork download failure).
    """

    media_path: Path
    media_type: str
    match: MatchResult | None = None
    category_id: str | None = None
    nfo_written: bool = False
    artwork_downloaded: list[str] = field(default_factory=list)
    episodes_renamed: int = 0
    action: str = "error"
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def _parse_folder_name(name: str) -> tuple[str, int | None]:
    """Parse a media folder name into title and year.

    First tries the clean "Title (Year)" format. If that fails,
    uses NameCleaner (guessit) to extract title and year from raw
    release names like "Movie.Title.2024.1080p.BluRay.x264-GROUP".
    This allows the scraper to handle files deposited directly into
    category folders without going through the sort step.

    Args:
        name: Folder name — either clean or raw release format.

    Returns:
        Tuple of (title, year). Year is None if not found.
    """
    # Try clean format first: "Title (Year)"
    m = _FOLDER_PATTERN.match(name)
    if m:
        return m.group(1).strip(), int(m.group(2))

    # Fall back to guessit for raw release names
    try:
        from personalscraper.sorter.cleaner import NameCleaner

        cleaner = NameCleaner()
        title = cleaner.clean(name)
        year = cleaner.extract_year(name)
        if title and title != name:
            log.info("folder_name_cleaned", raw=name, title=title, year=year)
            return title, year
    except ImportError:
        log.warning("folder_name_cleaner_unavailable", name=name)
    except (ValueError, AttributeError, TypeError, GuessitException) as exc:
        log.warning("folder_name_clean_failed", name=name, error=str(exc), exc_info=True)

    return name.strip(), None


def _find_video_file(directory: Path) -> Path | None:
    """Find the main video file in a directory tree.

    Searches recursively for video files. When multiple are found,
    returns the largest one (main feature, not sample/extra).
    Skips hidden files and .actors/ directories.

    Args:
        directory: Root directory to search.

    Returns:
        Path to the largest video file, or None if no video found.
    """
    candidates = [
        f
        for f in directory.rglob("*")
        if f.is_file()
        and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        and not f.name.startswith(".")
        and ".actors" not in f.parts
        and "Trailers" not in f.parts
    ]
    if not candidates:
        return None
    try:
        return max(candidates, key=lambda f: f.stat().st_size)
    except OSError:
        # stat() failed on a candidate (broken symlink, NTFS metadata issue)
        # — fall back to first candidate rather than crashing the scrape
        log.warning("video_stat_failed", directory=directory.name)
        return candidates[0]


def _cleanup_stale_files(directory: Path, old_prefix: str, new_prefix: str) -> int:
    """Remove stale files with old title prefix when sanitized versions exist.

    After a folder rename (e.g., stripping ':'), old artwork/NFO files
    may remain alongside the new sanitized versions. This function removes
    the old duplicates only when a corresponding new file exists.

    Args:
        directory: Directory to scan for stale files.
        old_prefix: The old title prefix (e.g., "Title : Subtitle").
        new_prefix: The new sanitized prefix (e.g., "Title Subtitle").

    Returns:
        Number of stale files removed.
    """
    if old_prefix == new_prefix:
        return 0

    removed = 0
    for f in list(directory.iterdir()):
        if not f.is_file() or not f.name.startswith(old_prefix):
            continue
        # Build the expected sanitized equivalent
        new_name = new_prefix + f.name[len(old_prefix) :]
        if (directory / new_name).exists():
            try:
                f.unlink()
                log.info("stale_file_removed", filename=f.name)
                removed += 1
            except OSError as exc:
                log.warning("stale_file_remove_failed", filename=f.name, error=str(exc))
    return removed


def _cleanup_empty_release_dirs(show_dir: Path) -> int:
    """Remove release-group subdirectories with no video files.

    After episodes are moved to Saison XX/ directories, the original
    release-group subdirectories (e.g., Show.S01E01.1080p.WEB-GROUP/)
    may be left empty or contain only residual NFOs. This function
    removes them if they have no video files (recursively).

    Skips hidden directories (.actors/) and season directories (Saison XX/).

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        Number of directories removed.
    """
    import shutil

    removed = 0
    for subdir in list(show_dir.iterdir()):
        if not subdir.is_dir():
            continue
        if subdir.name.startswith("."):
            continue
        if SEASON_DIR_RE.match(subdir.name):
            continue
        # Check if subdir has any video files (recursively)
        has_video = any(f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS for f in subdir.rglob("*"))
        if has_video:
            continue
        non_video_files = [f.name for f in subdir.rglob("*") if f.is_file()]
        if non_video_files:
            log.warning("release_dir_residual_files", directory=subdir.name, files=non_video_files)
        try:
            shutil.rmtree(subdir)
            log.info("release_dir_removed", directory=subdir.name)
            removed += 1
        except OSError as exc:
            log.warning("release_dir_remove_failed", directory=subdir.name, error=str(exc))
    return removed


def _local_show_seasons(show_dir: Path) -> set[int]:
    """Extract the set of seasons present in a TV show folder.

    Walks the folder recursively and parses S/E from each video filename.
    Feeds content-aware candidate disambiguation in ``match_tvshow_tvdb``:
    a candidate whose TVDB catalog does not cover the observed seasons is
    very likely the wrong show (e.g. a same-keyword spin-off).

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        Set of season numbers (> 0). Empty when no parseable S/E found.
    """
    seasons: set[int] = set()
    for f in show_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
            continue
        season, _ = _extract_season_episode(f.name)
        if season and season > 0:
            seasons.add(season)
    return seasons


def verify_tvshow_scrape_drift(
    show_dir: Path,
    nfo_path: Path,
    patterns: NamingPatterns,
) -> tuple[bool, str]:
    r"""Verify a previously-scraped TV show directory still matches current scraper output.

    Purely filesystem + NFO parsing — no external API calls. Drift found
    here triggers a full re-scrape upstream (caller deletes the NFO and
    falls through).

    Checks, all must pass:

    1. ``tvshow.nfo`` parses and exposes non-empty ``<title>``, ``<year>``,
       and at least one non-empty ``<uniqueid>``.
    2. Folder name equals the canonical ``sanitize("{title} ({year})")``
       — catches previous scrapes whose API-sourced folder name drifted
       from the current policy (e.g. "Top Chef (France) (2010)" vs the
       TVDB canonical "Top Chef (2010)").
    3. Every video file under ``Saison XX/`` matches
       ``S\d{2}E\d{2} - .+\.ext`` — a title segment is required. A bare
       ``SxxExx.ext`` indicates a legacy title-less fallback that must be
       upgraded to the synthetic-title form.
    4. Every episode video has a sibling ``.nfo`` with the same stem.
    5. ``poster.jpg`` and ``landscape.jpg`` are present.

    Args:
        show_dir: Path to the TV show directory.
        nfo_path: Path to ``tvshow.nfo`` (existence already confirmed).
        patterns: Naming patterns used to compute the canonical folder
            name and artwork filenames.

    Returns:
        Tuple ``(is_valid, reason)``. ``reason`` is a short slug suitable
        for a log field; ``"ok"`` on success.
    """
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314 — trusted NFO we just wrote
    except (ET.ParseError, OSError) as exc:
        return False, f"nfo_parse_failed:{exc}"

    # 1. Mandatory NFO fields.
    nfo_title = (root.findtext("title") or "").strip()
    nfo_year = (root.findtext("year") or "").strip()
    if not nfo_title:
        return False, "nfo_missing_title"
    if not nfo_year:
        return False, "nfo_missing_year"
    has_uniqueid = any((u.text or "").strip() for u in root.findall("uniqueid"))
    if not has_uniqueid:
        return False, "nfo_missing_uniqueid"

    # 2. Canonical folder name. Compare under NFC normalization so macOS's
    # NFD-stored filenames don't trip the check (the two strings can look
    # identical in logs but differ in codepoints — "è" as U+00E8 vs
    # "e" + U+0300). Without this, the drift check falsely fires and the
    # subsequent rename-into-itself corrupts the folder.
    canonical = patterns.format("movie_dir", Title=nfo_title, Year=nfo_year)
    if unicodedata.normalize("NFC", show_dir.name) != unicodedata.normalize("NFC", canonical):
        return False, f"folder_name_drift:{show_dir.name}!={canonical}"

    # 5. Show-level artwork.
    if not (show_dir / patterns.tvshow_poster).exists():
        return False, "poster_missing"
    if not (show_dir / patterns.tvshow_landscape).exists():
        return False, "landscape_missing"

    # 3 + 4. Episode naming + sibling NFO.
    for season_dir in show_dir.iterdir():
        if not (season_dir.is_dir() and SEASON_DIR_RE.match(season_dir.name)):
            continue
        for ep_file in season_dir.iterdir():
            if not ep_file.is_file():
                continue
            if ep_file.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                continue
            # Strict: require "SxxExx - Title.ext". A bare "SxxExx.ext" is a
            # legacy fallback name that must be upgraded.
            if not _EPISODE_STRICT_RE.match(ep_file.name):
                return False, f"episode_naming_drift:{ep_file.name}"
            sibling_nfo = ep_file.with_suffix(".nfo")
            if not sibling_nfo.exists():
                return False, f"episode_nfo_missing:{sibling_nfo.name}"

    return True, "ok"


def _tvdb_series_to_show_data(
    tvdb_data: dict[str, Any],
    tvdb_id: int,
    tvdb_client: Any = None,
    tmdb_id: int = 0,
    imdb_id: str = "",
) -> dict[str, Any]:
    """Convert TVDB series data to a TMDB-like show_data dict.

    Builds a show_data compatible with generate_tvshow_nfo() and
    download_tvshow_artwork() using TVDB fields. Whenever a TV show is
    matched via TVDB, this is the source of truth for folder naming,
    NFO content, artwork, and episode lookups — the TMDB id is only
    embedded as a secondary uniqueid cross-reference and never queried
    for content.

    TVDB field mapping:
    - name / originalName → name / original_name
    - overview → overview
    - status.name → status
    - genres[{name}] → genres[{name}]
    - contentRatings[{name}] → content_ratings.results[{rating}]
    - seasons[{number}] → seasons[{season_number}]
    - If tvdb_client is provided: posters (type=2) + backgrounds (type=3) are
      fetched and injected into ``images`` as absolute URLs (``{file_path}``).

    Args:
        tvdb_data: TVDB extended series dict (from get_series()).
        tvdb_id: TVDB series ID (embedded in external_ids for NFO generation).
        tvdb_client: Optional TVDB client used to fetch artworks. When None, the
            returned dict has empty ``images`` (legacy call sites that don't
            need artwork).
        tmdb_id: Optional TMDB cross-reference id. Embedded as the default
            ``uniqueid type="tmdb"`` when non-zero — strictly for Kodi/Jellyfin
            cross-linking, never used to fetch content.
        imdb_id: Optional IMDB cross-reference id (same rationale as tmdb_id).

    Returns:
        Dict with TMDB-compatible fields for NFO/artwork generation.
    """
    status_raw = tvdb_data.get("status", {})
    status_name = status_raw.get("name", "") if isinstance(status_raw, dict) else str(status_raw)

    # Build content_ratings in TMDB format: {results: [{rating, iso_3166_1}]}
    content_ratings_results: list[dict[str, str]] = []
    for cr in tvdb_data.get("contentRatings", []) or []:
        rating = cr.get("name", "")
        country = cr.get("country", "")
        if rating:
            content_ratings_results.append({"rating": rating, "iso_3166_1": country})

    # Build seasons list in TMDB format: [{season_number, poster_path}]
    seasons: list[dict[str, Any]] = []
    for s in tvdb_data.get("seasons", []) or []:
        s_num = s.get("number", s.get("season_number", 0))
        if s_num and s_num > 0:
            seasons.append({"season_number": s_num, "poster_path": ""})

    # Fetch TVDB artworks (posters type=2, backgrounds type=3) when a client
    # is provided. TVDB returns absolute URLs in the ``image`` field — we map
    # them into TMDB-like ``{file_path, iso_639_1}`` entries so
    # download_tvshow_artwork() can consume them unchanged.
    posters: list[dict[str, Any]] = []
    backdrops: list[dict[str, Any]] = []
    if tvdb_client is not None:
        try:
            poster_artworks = tvdb_client.get_series_artworks(tvdb_id, type_id=2)
            posters = [
                {"file_path": a["image"], "iso_639_1": a.get("language") or ""}
                for a in poster_artworks
                if a.get("image")
            ]
        except Exception as exc:  # noqa: BLE001 — artwork fetch is best-effort
            log.warning("tvdb_poster_fetch_failed", tvdb_id=tvdb_id, error=str(exc))
        try:
            bg_artworks = tvdb_client.get_series_artworks(tvdb_id, type_id=3)
            backdrops = [
                {"file_path": a["image"], "iso_639_1": a.get("language") or ""} for a in bg_artworks if a.get("image")
            ]
        except Exception as exc:  # noqa: BLE001 — artwork fetch is best-effort
            log.warning("tvdb_background_fetch_failed", tvdb_id=tvdb_id, error=str(exc))

    # first_air_date: TVDB uses firstAired ("YYYY-MM-DD"); fallback to year field.
    first_air = tvdb_data.get("firstAired") or ""
    if not first_air:
        year_val = tvdb_data.get("year")
        if isinstance(year_val, int) and year_val > 0:
            first_air = f"{year_val}-01-01"
        elif isinstance(year_val, str) and year_val.isdigit():
            first_air = f"{year_val}-01-01"

    return {
        "id": tmdb_id,  # Cross-ref TMDB id (0 when none) — NFO-only, never queried
        "name": tvdb_data.get("name", ""),
        "original_name": tvdb_data.get("originalName", tvdb_data.get("name", "")),
        "overview": tvdb_data.get("overview", ""),
        "status": status_name,
        "genres": [{"name": g.get("name", "")} for g in (tvdb_data.get("genres") or [])],
        "networks": [],
        "first_air_date": first_air,
        "vote_average": 0.0,
        "vote_count": 0,
        "number_of_episodes": 0,
        "number_of_seasons": len(seasons),
        "external_ids": {
            "tvdb_id": tvdb_id,
            "imdb_id": imdb_id,
        },
        "content_ratings": {"results": content_ratings_results},
        "seasons": seasons,
        "images": {"posters": posters, "backdrops": backdrops},
        "aggregate_credits": {"cast": []},
    }


class Scraper:
    """Main scraping orchestrator.

    Coordinates TMDB/TVDB matching, NFO generation, artwork download,
    and episode management for both movies and TV shows.

    Attributes:
        settings: Pipeline configuration.
        config: Config for classification and keyword rules.
        patterns: Naming patterns for file generation.
        dry_run: If True, log operations without writing files.
        interactive: If True, prompt user for ambiguous matches.
    """

    def __init__(
        self,
        settings: Settings,
        patterns: NamingPatterns,
        dry_run: bool = False,
        interactive: bool = False,
        config: Config | None = None,
    ):
        """Initialize the scraper with API clients and helpers.

        Args:
            settings: Pipeline configuration with API keys.
            patterns: MediaElch-compatible naming patterns.
            dry_run: If True, preview operations without writing.
            interactive: If True, prompt for ambiguous matches.
            config: Config for classification rules and paths. When provided,
                classifier.classify() is called for every scraped item to assign
                a category_id. When None, classification is skipped (legacy mode).
        """
        self.settings = settings
        self.config = config
        self.patterns = patterns
        self.dry_run = dry_run
        self.interactive = interactive

        # Initialize API clients with circuit breaker config from settings
        self._tmdb = TMDBClient(
            api_key=settings.tmdb_api_key,
            circuit_breaker_threshold=settings.circuit_breaker_threshold,
            circuit_breaker_cooldown=settings.circuit_breaker_cooldown,
        )
        self._tvdb = TVDBClient(
            api_key=settings.tvdb_api_key,
            circuit_breaker_threshold=settings.circuit_breaker_threshold,
            circuit_breaker_cooldown=settings.circuit_breaker_cooldown,
        )

        # Initialize helpers.  Pass db_path so write-through outbox publishes
        # land in the user-configured DB (DESIGN §9.4).  When config is None
        # (legacy/test mode) db_path is None and outbox publishing is skipped.
        _db_path = config.indexer.db_path if config is not None else None
        self._nfo = NFOGenerator(db_path=_db_path)
        self._artwork = ArtworkDownloader(
            dry_run=dry_run,
            artwork_language=settings.artwork_language,
            db_path=_db_path,
        )

        # Classification helpers — only set up when config is provided.
        # _needs_keywords caches whether any category_rule uses tmdb_keyword so
        # the /keywords endpoint is only called when actually required.
        if config is not None:
            self._keywords_cache: KeywordsCache | None = KeywordsCache(config.paths.data_dir)
            self._needs_keywords: bool = any(rule.tmdb_keyword is not None for rule in config.category_rules)
        else:
            self._keywords_cache = None
            self._needs_keywords = False

    def _classify_item(
        self,
        media_type: str,
        path: Path,
        title: str,
        api_data: dict[str, Any],
        tmdb_id: int | None,
        nfo_path: Path | None = None,
    ) -> str | None:
        """Classify a media item using the classifier pipeline.

        Fetches TMDB keywords first (using cache) when any category_rule uses
        ``tmdb_keyword``, then delegates to ``classifier.classify()``.

        Returns ``None`` when no config is set (legacy mode — classification
        is skipped) or when ``classify()`` returns ``None`` (unreachable in
        practice since defaults are always configured).

        Args:
            media_type: ``"movie"`` or ``"tv"`` (TMDB API convention).
            path: Source path of the media item.
            title: Resolved media title string.
            api_data: Full TMDB movie/show details dict.
            tmdb_id: TMDB numeric ID (used for /keywords fetch).
            nfo_path: Optional path to an existing NFO for priority-1 override.

        Returns:
            category_id string, or ``None`` if classification was skipped or
            produced no result.
        """
        if self.config is None:
            return None

        # Fetch TMDB keywords (via cache) only when needed
        tmdb_keywords: list[str] = []
        if self._needs_keywords and tmdb_id is not None and self._keywords_cache is not None:
            cached = self._keywords_cache.get(tmdb_id, media_type)  # type: ignore[arg-type]
            if cached is None:
                fetched = self._tmdb.get_keywords(tmdb_id, media_type)  # type: ignore[arg-type]
                self._keywords_cache.set(tmdb_id, media_type, fetched)  # type: ignore[arg-type]
                tmdb_keywords = fetched
            else:
                tmdb_keywords = cached

        # Extract genre data from TMDB API response
        genres_raw = api_data.get("genres", [])
        tmdb_genres = [g["name"] for g in genres_raw if isinstance(g, dict) and g.get("name")]
        tmdb_genre_ids = [g["id"] for g in genres_raw if isinstance(g, dict) and g.get("id") is not None]

        # Origin country (list for movies, list for TV shows)
        origin_country: list[str] = []
        raw_oc = api_data.get("origin_country") or api_data.get("production_countries") or []
        if isinstance(raw_oc, list):
            for item in raw_oc:
                if isinstance(item, str):
                    origin_country.append(item)
                elif isinstance(item, dict):
                    code = item.get("iso_3166_1") or item.get("iso_639_1")
                    if code:
                        origin_country.append(str(code))

        category_id, reason = _classifier.classify(
            self.config,
            media_type=media_type,  # type: ignore[arg-type]
            path=path,
            title=title,
            tmdb_genres=tmdb_genres or None,
            tmdb_genre_ids=tmdb_genre_ids or None,
            tmdb_keywords=tmdb_keywords or None,
            origin_country=origin_country or None,
            nfo_path=nfo_path,
        )

        if category_id is None:
            log.warning("classify_no_category", title=title, media_type=media_type, reason=reason)
            return None

        log.debug("classify_result", title=title, category_id=category_id, reason=reason)
        return category_id

    def _resolve_title(
        self,
        match_title: str,
        api_data: dict[str, Any],
        media_type: str,
    ) -> str:
        """Pick the best title for folder renaming.

        When scraper_prefer_local_title is True and the API data
        contains a local (FR) title, uses it. Falls back to
        match_title if the local title is empty or identical
        to the original title.

        Args:
            match_title: Title from the match result (API default).
            api_data: Full movie/show data from TMDB API.
            media_type: "movie" or "tvshow".

        Returns:
            Best title string for folder naming.
        """
        if not self.settings.scraper_prefer_local_title:
            return match_title

        # TMDB movies use "title", TV shows use "name"
        key = "title" if media_type == "movie" else "name"
        local_title = api_data.get(key, "")

        if not local_title:
            log.debug("title_no_local", match_title=match_title)
            return match_title

        # If local title is the same as original_title, it means
        # there's no translation — use match_title instead
        original = api_data.get("original_title" if media_type == "movie" else "original_name", "")
        if local_title == original and local_title != match_title:
            log.debug("title_no_translation", local_title=local_title, match_title=match_title)
            return match_title

        return cast(str, local_title)

    @staticmethod
    def _strip_trailing_year(title: str) -> str:
        """Remove a trailing (YYYY) suffix from a title.

        API sources (TVDB especially) include the year in the title as
        disambiguation (e.g. "Invincible (2021)"). Since callers always
        append the year separately via NamingPatterns, the trailing year
        must be stripped to avoid duplication like "Invincible (2021) (2021)".

        Args:
            title: Title that may contain a trailing year.

        Returns:
            Title with trailing (YYYY) removed, if present.
        """
        return re.sub(r"\s*\(\d{4}\)\s*$", "", title)

    def _check_missing_movie_artwork(self, movie_dir: Path, title: str) -> list[str]:
        """List missing essential artwork for a movie directory.

        Checks poster and landscape only (the two files required by
        the fast-skip gate in _has_unscraped_items).

        Args:
            movie_dir: Path to the movie directory.
            title: Movie title for filename patterns.

        Returns:
            List of missing artwork filenames. Empty if both present.
        """
        missing = []
        poster = self.patterns.format("movie_poster", Title=title)
        if not (movie_dir / poster).exists():
            missing.append(poster)
        landscape = self.patterns.format("movie_landscape", Title=title)
        if not (movie_dir / landscape).exists():
            missing.append(landscape)
        return missing

    def _check_missing_tvshow_artwork(self, show_dir: Path) -> list[str]:
        """List missing essential artwork for a TV show directory.

        Checks poster and landscape only (the two files required by
        the fast-skip gate in _has_unscraped_items).

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            List of missing artwork filenames. Empty if both present.
        """
        missing = []
        if not (show_dir / self.patterns.tvshow_poster).exists():
            missing.append(self.patterns.tvshow_poster)
        if not (show_dir / self.patterns.tvshow_landscape).exists():
            missing.append(self.patterns.tvshow_landscape)
        return missing

    @staticmethod
    def _extract_tmdb_id_from_nfo(nfo_path: Path) -> int | None:
        """Extract TMDB ID from a valid NFO file.

        Parses the NFO XML and finds the first <uniqueid type="tmdb">
        element with a numeric value.

        Args:
            nfo_path: Path to the NFO file (must exist and be valid XML).

        Returns:
            TMDB ID as int, or None if not found or not numeric.
        """
        try:
            root = ET.parse(nfo_path).getroot()  # noqa: S314
        except (ET.ParseError, OSError) as exc:
            log.warning("nfo_parse_failed", filename=nfo_path.name, error=str(exc))
            return None
        for uid in root.findall("uniqueid"):
            if uid.get("type") == "tmdb" and uid.text:
                try:
                    return int(uid.text)
                except ValueError:
                    log.warning("nfo_tmdb_id_non_numeric", tmdb_id=uid.text, path=str(nfo_path))
                    return None
        log.debug("nfo_no_tmdb_id", path=str(nfo_path))
        return None

    def _recover_movie_artwork(
        self,
        nfo_path: Path,
        movie_dir: Path,
        result: ScrapeResult,
    ) -> None:
        """Re-download missing artwork using TMDB ID from existing NFO.

        Extracts the TMDB ID, fetches movie data, and downloads artwork
        (existing files are automatically skipped by the downloader).

        Args:
            nfo_path: Path to the valid NFO file.
            movie_dir: Path to the movie directory.
            result: ScrapeResult to update with recovery info.
        """
        tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
        if not tmdb_id:
            return
        # Broad catch: get_movie() can raise TMDBError, CircuitOpenError, or requests
        # exceptions; download_movie_artwork() adds OSError. CircuitOpenError needs
        # a lazy import — narrowing this mixed path is not worthwhile here.
        try:
            movie_data = self._tmdb.get_movie(tmdb_id)
            downloaded = self._artwork.download_movie_artwork(
                movie_data,
                movie_dir,
                self.patterns,
            )
            if downloaded:
                result.action = "artwork_recovered"
                result.artwork_downloaded = [p.name for p in downloaded]
                log.info("artwork_recovered", count=len(downloaded), directory=movie_dir.name)
        except Exception as e:  # noqa: BLE001 — see block comment above
            log.warning("artwork_recovery_failed", directory=movie_dir.name, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork recovery failed: {e}")

    def _recover_tvshow_artwork(
        self,
        nfo_path: Path,
        show_dir: Path,
        result: ScrapeResult,
    ) -> None:
        """Re-download missing artwork for a TV show using NFO TMDB ID.

        Extracts the TMDB ID, fetches show data, and downloads artwork
        (existing files are automatically skipped by the downloader).

        Args:
            nfo_path: Path to the valid tvshow.nfo file.
            show_dir: Path to the TV show directory.
            result: ScrapeResult to update with recovery info.
        """
        tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
        if not tmdb_id:
            return
        # Broad catch: get_tv() can raise TMDBError, CircuitOpenError, or requests
        # exceptions; download_tvshow_artwork() adds OSError. CircuitOpenError needs
        # a lazy import — narrowing this mixed path is not worthwhile here.
        try:
            show_data = self._tmdb.get_tv(tmdb_id)
            downloaded = self._artwork.download_tvshow_artwork(
                show_data,
                show_dir,
                self.patterns,
            )
            if downloaded:
                result.action = "artwork_recovered"
                result.artwork_downloaded = [p.name for p in downloaded]
                log.info("artwork_recovered", count=len(downloaded), directory=show_dir.name)
        except Exception as e:  # noqa: BLE001 — mixed API+IO path; see comment above
            log.warning("artwork_recovery_failed", directory=show_dir.name, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork recovery failed: {e}")

    def _repair_movie_dir(self, movie_dir: Path, title: str) -> bool:
        """Repair a movie directory with valid NFO.

        Removes residual NFOs (keeps only {sanitized_title}.nfo).
        Does not re-scrape or re-match.

        Args:
            movie_dir: Path to the movie directory.
            title: Parsed movie title from folder name.

        Returns:
            True if any repair was applied.
        """
        repaired = False
        expected_nfo = sanitize_filename(title) + ".nfo"

        for nfo in movie_dir.glob("*.nfo"):
            if nfo.name != expected_nfo:
                if not self.dry_run:
                    try:
                        nfo.unlink()
                        log.info("repair_residual_nfo_removed", filename=nfo.name)
                        repaired = True
                    except OSError as exc:
                        log.warning("repair_residual_nfo_delete_failed", filename=nfo.name, error=str(exc))
                else:
                    log.info("repair_residual_nfo_would_remove", filename=nfo.name)
                    repaired = True

        return repaired

    def _verify_existing_scrape(self, show_dir: Path, nfo_path: Path) -> tuple[bool, str]:
        """Thin wrapper over ``verify_tvshow_scrape_drift``.

        Kept as an instance method so existing call sites keep threading
        ``self.patterns`` through the class.

        Args:
            show_dir: Path to the TV show directory.
            nfo_path: Path to ``tvshow.nfo``.

        Returns:
            ``(is_valid, reason)`` — see ``verify_tvshow_scrape_drift``.
        """
        return verify_tvshow_scrape_drift(show_dir, nfo_path, self.patterns)

    def _repair_tvshow_dir(self, show_dir: Path) -> bool:
        """Repair a TV show directory with valid NFO.

        1. Remove residual NFOs at root (keep only tvshow.nfo).
        2. Remove root MKV duplicates (same SxxExx in Saison XX/).
        3. Organize new root episodes not yet in Saison XX/ (if TMDB ID available).
           Dedup rule: when multiple root files match the same SxxExx, keep the
           newest by mtime and delete the others before organizing.
        4. Organize unstructured episodes from non-season subdirs (if TMDB ID available).

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            True if any repair was applied.
        """
        repaired = False

        # 1. Remove residual NFOs at root (keep tvshow.nfo)
        for nfo in show_dir.glob("*.nfo"):
            if nfo.name != "tvshow.nfo":
                if not self.dry_run:
                    try:
                        nfo.unlink()
                        log.info("repair_residual_nfo_removed", filename=nfo.name, show=show_dir.name)
                        repaired = True
                    except OSError as exc:
                        log.warning("repair_residual_nfo_delete_failed", filename=nfo.name, error=str(exc))
                else:
                    log.info("repair_residual_nfo_would_remove", filename=nfo.name)
                    repaired = True

        # 2. Collect organized episodes (SxxExx → set of (season, episode))
        organized: set[tuple[int, int]] = set()
        for season_dir in show_dir.iterdir():
            if season_dir.is_dir() and SEASON_DIR_RE.match(season_dir.name):
                for f in season_dir.iterdir():
                    if f.is_file():
                        m = _SXXEXX_RE.search(f.stem)
                        if m:
                            organized.add((int(m.group(1)), int(m.group(2))))

        # 3. Remove root MKV duplicates that match organized episodes
        if organized:
            for f in list(show_dir.iterdir()):
                if not f.is_file() or f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                    continue
                m = _SXXEXX_RE.search(f.stem)
                if m and (int(m.group(1)), int(m.group(2))) in organized:
                    if not self.dry_run:
                        try:
                            f.unlink()
                            log.info("repair_root_duplicate_removed", filename=f.name)
                            repaired = True
                        except OSError as exc:
                            log.warning("repair_root_duplicate_delete_failed", filename=f.name, error=str(exc))
                    else:
                        log.info("repair_root_duplicate_would_remove", filename=f.name)
                        repaired = True

        # 3b. Organize new root video files for episodes NOT yet in any Saison XX/.
        # Collect all root video files that parse as SxxExx and are not duplicates.
        root_new: dict[tuple[int, int], list[Path]] = {}
        for f in list(show_dir.iterdir()):
            if not f.is_file() or f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                continue
            m = _SXXEXX_RE.search(f.stem)
            if not m:
                continue
            key = (int(m.group(1)), int(m.group(2)))
            if key in organized:
                continue  # Already handled as duplicate in step 3
            root_new.setdefault(key, []).append(f)

        if root_new:
            nfo_path = show_dir / "tvshow.nfo"
            tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
            if not tmdb_id:
                log.warning("repair_root_episodes_no_tmdb_id", show=show_dir.name)
            else:
                try:
                    show_data = self._tmdb.get_tv(tmdb_id)
                    root_api_episodes: dict[tuple[int, int], dict[str, Any]] = {}
                    for season in show_data.get("seasons", []):
                        s_num = season.get("season_number", 0)
                        if s_num == 0:
                            continue
                        # Only fetch seasons that have new root files
                        if not any(s == s_num for s, _ in root_new):
                            continue
                        try:
                            s_detail = self._tmdb.get_tv_season(tmdb_id, s_num)
                            for ep in s_detail.get("episodes", []):
                                e_num = ep.get("episode_number", 0)
                                root_api_episodes[(s_num, e_num)] = {
                                    "title": ep.get("name", f"Episode {e_num}"),
                                    "still_path": ep.get("still_path", ""),
                                }
                        except (OSError, ConnectionError, TimeoutError) as e:
                            log.warning("repair_season_fetch_failed", season=s_num, error=str(e))

                    for (s_num, e_num), candidates in root_new.items():
                        # Dedup: keep newest by mtime, delete older ones
                        if len(candidates) > 1:
                            candidates_sorted = sorted(
                                candidates,
                                key=lambda f: f.stat().st_mtime,
                                reverse=True,
                            )
                            to_delete = candidates_sorted[1:]
                            keeper = candidates_sorted[0]
                            for old_f in to_delete:
                                if not self.dry_run:
                                    try:
                                        old_f.unlink()
                                        log.info(
                                            "repair_duplicate_deleted",
                                            deleted=old_f.name,
                                            kept=keeper.name,
                                        )
                                        repaired = True
                                    except OSError as exc:
                                        log.warning(
                                            "repair_duplicate_delete_failed",
                                            filename=old_f.name,
                                            error=str(exc),
                                        )
                                else:
                                    log.info(
                                        "repair_duplicate_would_delete",
                                        deleted=old_f.name,
                                        kept=keeper.name,
                                    )
                                    repaired = True
                        else:
                            keeper = candidates[0]

                        # Rename and move keeper to Saison XX/
                        ep_info = root_api_episodes.get((s_num, e_num))
                        ep_title = ep_info["title"] if ep_info else f"Episode {e_num}"
                        season_dir_name = self.patterns.format("season_dir", Season=s_num)
                        new_stem = self.patterns.format(
                            "episode_video",
                            Season=s_num,
                            Episode=e_num,
                            EpisodeTitle=ep_title,
                        )
                        season_dir = show_dir / season_dir_name
                        dest = season_dir / f"{new_stem}{keeper.suffix}"
                        if not self.dry_run:
                            season_dir.mkdir(parents=True, exist_ok=True)
                            try:
                                keeper.rename(dest)
                                log.info(
                                    "repair_episode_moved",
                                    source=keeper.name,
                                    season_dir=season_dir_name,
                                    dest=dest.name,
                                )
                                repaired = True
                            except OSError as exc:
                                log.warning("repair_episode_move_failed", filename=keeper.name, error=str(exc))
                        else:
                            log.info(
                                "repair_episode_would_move",
                                source=keeper.name,
                                season_dir=season_dir_name,
                                dest=dest.name,
                            )
                            repaired = True

                    # Generate episode NFOs for moved files
                    root_moved: dict[Path, dict[str, Any]] = {}
                    for (s_num, e_num), candidates in root_new.items():
                        ep_info = root_api_episodes.get((s_num, e_num))
                        if ep_info is None:
                            continue
                        ep_title = ep_info["title"]
                        season_dir_name = self.patterns.format("season_dir", Season=s_num)
                        new_stem = self.patterns.format(
                            "episode_video",
                            Season=s_num,
                            Episode=e_num,
                            EpisodeTitle=ep_title,
                        )
                        suffix = candidates[0].suffix
                        dest = show_dir / season_dir_name / f"{new_stem}{suffix}"
                        root_moved[dest] = {
                            "season": s_num,
                            "episode": e_num,
                            "api_title": ep_title,
                            "still_path": ep_info.get("still_path", ""),
                        }
                    if root_moved and not self.dry_run:
                        self._generate_episode_nfos(root_moved, show_dir, show_data)

                except (OSError, ConnectionError, TimeoutError, ValueError, KeyError) as e:
                    log.warning("repair_root_episodes_failed", show=show_dir.name, exc_info=True, error=str(e))

        # 4. Organize unstructured episodes (from raw torrent dirs)
        # Finds video files in non-season subdirs (not root, not .actors)
        unorganized = sorted(
            f
            for f in show_dir.rglob("*")
            if f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and not SEASON_DIR_RE.match(f.parent.name)
            and f.parent != show_dir
            and ".actors" not in f.parts
            and "Trailers" not in f.parts
        )

        if unorganized:
            nfo_path = show_dir / "tvshow.nfo"
            tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
            if tmdb_id:
                try:
                    show_data = self._tmdb.get_tv(tmdb_id)
                    api_episodes: dict[tuple[int, int], dict[str, Any]] = {}
                    for season in show_data.get("seasons", []):
                        s_num = season.get("season_number", 0)
                        if s_num == 0:
                            continue
                        try:
                            s_detail = self._tmdb.get_tv_season(
                                tmdb_id,
                                s_num,
                            )
                            for ep in s_detail.get("episodes", []):
                                e_num = ep.get("episode_number", 0)
                                api_episodes[(s_num, e_num)] = {
                                    "title": ep.get("name", f"Episode {e_num}"),
                                    "still_path": ep.get("still_path", ""),
                                }
                        except (OSError, ConnectionError, TimeoutError) as e:
                            log.warning("repair_season_fetch_failed", exc_info=True, season=s_num, error=str(e))

                    if api_episodes:
                        ep_list = [{"season_number": s, "episode_number": e} for s, e in api_episodes]
                        create_season_dirs(
                            show_dir,
                            ep_list,
                            self.patterns,
                            self.dry_run,
                        )
                        matched = match_episode_files(
                            unorganized,
                            api_episodes,
                        )
                        if matched:
                            count = rename_episodes(
                                matched,
                                show_dir,
                                self.patterns,
                                self.dry_run,
                            )
                            if count > 0:
                                repaired = True
                                log.info("repair_episodes_organized", count=count, show=show_dir.name)
                            self._generate_episode_nfos(
                                matched,
                                show_dir,
                                show_data,
                            )

                except (OSError, ConnectionError, TimeoutError, ValueError, KeyError) as e:
                    log.warning("repair_organize_episodes_failed", show=show_dir.name, exc_info=True, error=str(e))
            else:
                log.warning("repair_organize_episodes_no_tmdb_id", show=show_dir.name)

        # Always clean residual torrent dirs (even if no unorganized episodes)
        if not self.dry_run:
            try:
                cleaned = _cleanup_empty_release_dirs(show_dir)
                if cleaned > 0:
                    repaired = True
            except OSError as exc:
                log.warning("repair_clean_release_dirs_failed", show=show_dir.name, error=str(exc))

        return repaired

    def scrape_movie(self, movie_dir: Path) -> ScrapeResult:
        """Scrape a single movie: match → NFO → artwork.

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
            # Check for missing artwork — recover without re-scraping
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

        # Corrupt NFO: delete before re-scrape
        if nfo_path.exists():
            log.warning("nfo_corrupt_rescrape", filename=nfo_path.name)
            try:
                nfo_path.unlink()
            except OSError as exc:
                result.error = f"Cannot delete corrupt NFO: {exc}"
                log.error("nfo_corrupt_delete_failed", path=str(nfo_path), error=str(exc))
                return result

        # Match against TMDB
        try:
            match = match_movie(self._tmdb, title, year)
        except Exception as e:
            result.error = f"Match failed: {e}"
            log.error("movie_match_failed", title=title, error=str(e))
            return result

        if match is None or match.confidence < LOW_CONFIDENCE:
            result.action = "skipped_low_confidence"
            log.warning(
                "movie_no_confident_match",
                title=title,
                year=year,
                score=round(match.confidence if match else 0.0, 2),
            )
            return result

        result.match = match
        log.info(
            "movie_matched",
            title=title,
            api_title=match.api_title,
            source=match.source,
            confidence=round(match.confidence, 2),
        )

        # Get full movie details (needed for local title resolution)
        try:
            movie_data = self._tmdb.get_movie(match.api_id)
        except Exception as e:
            result.error = f"Get details failed: {e}"
            log.error("movie_details_failed", api_title=match.api_title, error=str(e))
            return result

        # Resolve title: use local FR title if preferred and available
        resolved_title = self._strip_trailing_year(self._resolve_title(match.api_title, movie_data, "movie"))
        api_year = match.api_year or year
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
            stream_info = extract_stream_info(video_file)

        # Classify item — must run before NFO write so the
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
            # Config is present but no category matched — skip this item
            result.action = "skipped_no_category"
            return result

        # Generate and write NFO
        try:
            xml = self._nfo.generate_movie_nfo(movie_data, stream_info, category_id=category_id)
            if not self.dry_run:
                self._nfo.write_nfo(xml, nfo_path)
                result.nfo_written = True
                log.info("nfo_written", filename=nfo_path.name)
            else:
                log.info("nfo_would_write", filename=nfo_path.name)
        except Exception as e:
            result.error = f"NFO generation failed: {e}"
            log.error("nfo_generation_failed", title=title, error=str(e))
            return result

        # Download artwork
        try:
            downloaded = self._artwork.download_movie_artwork(
                movie_data,
                movie_dir,
                self.patterns,
            )
            result.artwork_downloaded = [p.name for p in downloaded]
        except (requests.RequestException, OSError, KeyError, AttributeError) as e:
            log.warning("movie_artwork_failed", title=title, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork failed: {e}")

        result.action = "scraped"
        return result

    def process_movies(self, movies_dir: Path) -> list[ScrapeResult]:
        """Scrape all movies in a directory.

        Scans all subdirectories of movies_dir and calls scrape_movie()
        on each one. When the TMDB circuit breaker is OPEN, skips
        remaining movies (no viable fallback for movie metadata).

        Args:
            movies_dir: Path to the movies directory (e.g. {movies_dir}/).

        Returns:
            List of ScrapeResult for each processed movie.
        """
        from personalscraper.scraper.circuit_breaker import CircuitOpenError

        results: list[ScrapeResult] = []

        if not movies_dir.exists():
            log.warning("movies_dir_not_found", path=str(movies_dir))
            return results

        # Each subdirectory is a movie
        subdirs = sorted(d for d in movies_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

        log.info("movies_start", count=len(subdirs), directory=movies_dir.name)

        for movie_dir in subdirs:
            # Skip if TMDB circuit is OPEN (primary provider for movies)
            if not self._tmdb.circuit.can_proceed():
                log.warning("movies_tmdb_circuit_open", directory=movie_dir.name)
                results.append(
                    ScrapeResult(
                        media_path=movie_dir,
                        media_type="movie",
                        action="error",
                        error="TMDB circuit breaker OPEN",
                    )
                )
                continue

            try:
                result = self.scrape_movie(movie_dir)
                results.append(result)
            except CircuitOpenError as e:
                # Circuit opened during this item's processing
                log.warning("movies_circuit_opened", directory=movie_dir.name, error=str(e))
                results.append(
                    ScrapeResult(
                        media_path=movie_dir,
                        media_type="movie",
                        action="error",
                        error=str(e),
                    )
                )
            except Exception as e:
                log.error("movies_unexpected_error", directory=movie_dir.name, error=str(e))
                results.append(
                    ScrapeResult(
                        media_path=movie_dir,
                        media_type="movie",
                        action="error",
                        error=str(e),
                    )
                )

        # Summary
        scraped = sum(1 for r in results if r.action == "scraped")
        skipped = sum(1 for r in results if r.action.startswith("skipped"))
        unmatched = sum(1 for r in results if r.action == "skipped_low_confidence")
        errors = sum(1 for r in results if r.action == "error")
        log.info("movies_done", scraped=scraped, skipped=skipped, unmatched=unmatched, errors=errors)

        return results

    def scrape_tvshow(self, show_dir: Path) -> ScrapeResult:
        """Scrape a TV show: match → NFO → artwork → seasons → episodes.

        Args:
            show_dir: Path to the TV show directory.

        Returns:
            ScrapeResult with action and details.
        """
        title, year = _parse_folder_name(show_dir.name)
        result = ScrapeResult(media_path=show_dir, media_type="tvshow")

        # Check for existing valid NFO
        nfo_path = show_dir / self.patterns.tvshow_nfo
        if _is_nfo_complete(nfo_path):
            # Fast path only when the previous scrape is still coherent with
            # the current scraper output (folder name, episode naming, NFO
            # content, artwork). Any drift → delete the NFO so the normal
            # scrape flow below rebuilds from a clean slate.
            is_valid, drift_reason = self._verify_existing_scrape(show_dir, nfo_path)
            if not is_valid:
                log.info(
                    "show_rescrape_drift",
                    directory=show_dir.name,
                    reason=drift_reason,
                )
                if not self.dry_run:
                    try:
                        nfo_path.unlink()
                    except OSError as exc:
                        result.error = f"Cannot delete drifted NFO: {exc}"
                        log.error("nfo_drift_delete_failed", path=str(nfo_path), error=str(exc))
                        return result
                # Fall through to the full rescrape path below.
            else:
                # Existing fast path: artwork recovery + dir repair.
                missing_art = self._check_missing_tvshow_artwork(show_dir)
                if missing_art and not self.dry_run:
                    self._recover_tvshow_artwork(nfo_path, show_dir, result)
                # Repair pass: remove residual NFOs, root MKV duplicates, etc.
                repaired = self._repair_tvshow_dir(show_dir)
                if repaired and result.action != "artwork_recovered":
                    result.action = "repaired"
                elif result.action != "artwork_recovered":
                    result.action = "skipped_already_done"
                log.info("nfo_valid", action=result.action, directory=show_dir.name)
                return result

        # Corrupt NFO: delete before re-scrape
        if nfo_path.exists():
            log.warning("nfo_corrupt_rescrape", filename=nfo_path.name)
            try:
                nfo_path.unlink()
            except OSError as exc:
                result.error = f"Cannot delete corrupt NFO: {exc}"
                log.error("nfo_corrupt_delete_failed", path=str(nfo_path), error=str(exc))
                return result

        # Collect seasons present in the folder's video files — feeds
        # content-aware candidate disambiguation in match_tvshow_tvdb.
        local_seasons = _local_show_seasons(show_dir)

        # Match against TVDB/TMDB
        try:
            match = match_tvshow(
                self._tvdb,
                self._tmdb,
                title,
                year,
                local_seasons=local_seasons,
            )
        except Exception as e:
            result.error = f"Match failed: {e}"
            log.error("show_match_failed", title=title, error=str(e))
            return result

        if match is None or match.confidence < LOW_CONFIDENCE:
            result.action = "skipped_low_confidence"
            log.warning(
                "show_no_confident_match",
                title=title,
                year=year,
                score=round(match.confidence if match else 0.0, 2),
            )
            return result

        result.match = match
        log.info(
            "show_matched",
            title=title,
            api_title=match.api_title,
            source=match.source,
            confidence=round(match.confidence, 2),
        )

        # Fetch show details. Design: TVDB is the authoritative source for
        # every show identified via TVDB — NFO, folder name, artwork, and
        # episode titles all come from TVDB. The TMDB cross-reference id
        # (from remote_ids) is kept purely to embed as a secondary uniqueid
        # for Kodi/Jellyfin lookups — never queried for content. TMDB is
        # used for scraping ONLY when match.source == "tmdb" (fallback path
        # taken when TVDB returned no match above LOW_CONFIDENCE).
        tmdb_id: int | None = None
        show_data: dict[str, Any] = {}
        try:
            if match.source == "tvdb":
                tvdb_data = self._tvdb.get_series(match.api_id)
                remote_ids = self._tvdb.get_remote_ids(tvdb_data)
                raw_tmdb = remote_ids.get("tmdb_id")
                tmdb_id = int(raw_tmdb) if raw_tmdb else None
                imdb_id = remote_ids.get("imdb_id") or ""
                if not tmdb_id:
                    log.info("show_tvdb_only", tvdb_id=match.api_id)
                show_data = _tvdb_series_to_show_data(
                    tvdb_data,
                    match.api_id,
                    self._tvdb,
                    tmdb_id=tmdb_id or 0,
                    imdb_id=imdb_id,
                )
            else:
                # Fallback path: TVDB had no match → use TMDB for content.
                tmdb_id = match.api_id
                show_data = self._tmdb.get_tv(tmdb_id)
        except Exception as e:
            result.error = f"Get details failed: {e}"
            log.error("show_details_failed", error=str(e))
            return result

        # Resolve title: use local FR title if preferred and available
        resolved_title = self._strip_trailing_year(self._resolve_title(match.api_title, show_data, "tvshow"))

        # Rename folder to canonical name
        old_dir_name = show_dir.name  # Save before potential rename
        canonical = self.patterns.format(
            "movie_dir",
            Title=resolved_title,
            Year=match.api_year or year or "",
        )
        # NFC-compare: macOS stores filenames in NFD, Python strings are typically
        # NFC; a naive string compare treats them as different and triggers a
        # rename-into-self merge that empties the folder. See
        # ``verify_tvshow_scrape_drift`` for the matching normalization on the
        # read side.
        if unicodedata.normalize("NFC", show_dir.name) != unicodedata.normalize("NFC", canonical):
            new_dir = show_dir.parent / canonical
            if not self.dry_run:
                try:
                    if new_dir.exists():
                        moved, merge_failed = _merge_dirs(show_dir, new_dir)
                        log.info("show_folder_merged", title=title, dest=canonical, items=moved)
                        if merge_failed:
                            result.warnings.append(f"Partial merge: {merge_failed} item(s) failed")
                    else:
                        show_dir.rename(new_dir)
                        log.info("show_folder_renamed", title=title, dest=canonical)
                    show_dir = new_dir
                    result.media_path = new_dir
                except OSError as exc:
                    result.error = f"Rename/merge failed: {exc}"
                    log.error("show_folder_rename_failed", title=title, dest=canonical, error=str(exc))
                    return result
                # Non-critical: clean stale files from before rename.
                # TV show artwork uses fixed names (poster.jpg, tvshow.nfo),
                # so this is a no-op for standard shows. Kept as safety net.
                try:
                    _cleanup_stale_files(show_dir, old_dir_name, canonical)
                except OSError as exc:
                    log.warning("stale_cleanup_failed", directory=show_dir.name, error=str(exc))
            else:
                action = "merge into" if new_dir.exists() else "rename"
                log.info("show_folder_would_rename", action=action, title=title, dest=canonical)

        # Classify item — must run before NFO write so the
        # category_id can be embedded in the NFO by nfo_generator.
        # For TV shows matched via TVDB the source TMDB ID may differ from
        # match.api_id — use tmdb_id which was resolved above.
        nfo_path = show_dir / self.patterns.tvshow_nfo
        category_id = self._classify_item(
            media_type="tv",
            path=show_dir,
            title=resolved_title,
            api_data=show_data,
            tmdb_id=tmdb_id,
            nfo_path=nfo_path if nfo_path.exists() else None,
        )
        result.category_id = category_id
        if category_id is None and self.config is not None:
            # Config is present but no category matched — skip this item
            result.action = "skipped_no_category"
            return result

        # Generate tvshow.nfo
        try:
            xml = self._nfo.generate_tvshow_nfo(show_data, category_id=category_id)
            if not self.dry_run:
                self._nfo.write_nfo(xml, nfo_path)
                result.nfo_written = True
            else:
                log.info("nfo_would_write", filename="tvshow.nfo")
        except Exception as e:
            result.error = f"tvshow.nfo failed: {e}"
            return result

        # Download artwork
        try:
            downloaded = self._artwork.download_tvshow_artwork(
                show_data,
                show_dir,
                self.patterns,
            )
            result.artwork_downloaded = [p.name for p in downloaded]
        except (requests.RequestException, OSError, KeyError, AttributeError) as e:
            log.warning("show_artwork_failed", api_title=match.api_title, exc_info=True, error=str(e))
            result.warnings.append(f"Artwork failed: {e}")

        # Process episodes — rglob to find files nested in release-group subdirs,
        # but skip files already organized in Saison XX/ directories.
        # Trailers/ holds Plex-conformant trailer mp4s, never episodes.
        total_renamed = 0
        video_files = sorted(
            f
            for f in show_dir.rglob("*")
            if f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and not SEASON_DIR_RE.match(f.parent.name)
            and "Trailers" not in f.parts
        )

        if video_files:
            # Resolve the synthetic-title prefix once per show so in-provider
            # episodes with empty names and post-facto fallbacks share the same
            # user-configurable wording (default "Episode").
            episode_default_name = self.config.scraper.episode_default_name if self.config is not None else "Episode"
            api_episodes: dict[tuple[int, int], dict[str, Any]] = {}
            for season in show_data.get("seasons", []):
                s_num = season.get("season_number", 0)
                if s_num == 0:
                    continue
                try:
                    # Episode source follows the match source — TVDB matches
                    # never consult TMDB for episodes, even when a tmdb_id
                    # cross-ref exists.
                    if match.source == "tvdb":
                        # TVDB episodes + per-episode French translation.
                        tvdb_eps = self._tvdb.get_season_episodes(match.api_id, s_num)
                        for ep in tvdb_eps:
                            e_num = ep.get("number", ep.get("episode_number", 0))
                            ep_id = ep.get("id", 0)
                            title = ep.get("name") or f"{episode_default_name} {e_num}"
                            if ep_id:
                                trans = self._tvdb.get_episode_translation(ep_id, "fra")
                                if trans and trans.get("name"):
                                    title = trans["name"]
                                else:
                                    en_trans = self._tvdb.get_episode_translation(ep_id, "eng")
                                    if en_trans and en_trans.get("name"):
                                        title = en_trans["name"]
                            api_episodes[(s_num, e_num)] = {
                                "title": title,
                                "still_path": "",  # TVDB episode stills are separate API calls
                            }
                    else:
                        # match.source == "tmdb" (fallback path — TVDB had no match).
                        # tmdb_id was set to match.api_id just above, so it is non-None here.
                        assert tmdb_id is not None
                        s_detail = self._tmdb.get_tv_season(tmdb_id, s_num)
                        for ep in s_detail.get("episodes", []):
                            e_num = ep.get("episode_number", 0)
                            api_episodes[(s_num, e_num)] = {
                                "title": ep.get("name") or f"{episode_default_name} {e_num}",
                                "still_path": ep.get("still_path", ""),
                            }
                except Exception as e:  # noqa: BLE001 — mixed API + data-shape path: TMDB/TVDB paths raise TMDBError, TVDBError, requests.RequestException, CircuitOpenError (lazy imports); plus AttributeError/TypeError on malformed payloads (non-dict ep; non-iterable seasons/episodes)
                    log.warning("show_season_fetch_failed", season=s_num, exc_info=True, error=str(e))

            if api_episodes:
                ep_list = [{"season_number": s, "episode_number": e} for s, e in api_episodes]
                create_season_dirs(show_dir, ep_list, self.patterns, self.dry_run)
                matched = match_episode_files(
                    video_files,
                    api_episodes,
                    episode_default_name=episode_default_name,
                )
                if matched:
                    total_renamed = rename_episodes(matched, show_dir, self.patterns, self.dry_run)
                    self._generate_episode_nfos(matched, show_dir, show_data)

            # Clean empty release-group subdirectories left after episode moves
            if not self.dry_run:
                try:
                    _cleanup_empty_release_dirs(show_dir)
                except OSError as exc:
                    log.warning("show_clean_release_dirs_failed", show=show_dir.name, error=str(exc))

        result.episodes_renamed = total_renamed
        result.action = "scraped"
        return result

    def _download_episode_thumb(
        self,
        still_path: str,
        thumb_path: Path,
        season: int,
        episode: int,
    ) -> None:
        """Download an episode thumbnail from TMDB if available.

        Skips if still_path is empty, thumb already exists, or dry_run.
        Errors are logged and do not interrupt the caller.

        Args:
            still_path: TMDB still image path (e.g. "/abc123.jpg"), empty to skip.
            thumb_path: Local destination path for the thumbnail.
            season: Season number (for log messages).
            episode: Episode number (for log messages).
        """
        if not still_path or thumb_path.exists() or self.dry_run:
            return
        url = f"https://image.tmdb.org/t/p/original{still_path}"
        try:
            self._artwork.download_image(url, thumb_path)
        except requests.exceptions.RequestException:
            log.warning("episode_thumb_failed", season=season, episode=episode)

    def _generate_episode_nfos(
        self,
        matched: dict[Path, dict[str, Any]],
        show_dir: Path,
        show_data: dict[str, Any],
    ) -> None:
        """Generate NFO files and download episode thumbnails.

        For each matched episode, creates an NFO file with metadata and
        downloads the TMDB still image as a thumbnail file. Episodes with
        existing NFOs only get thumbnail recovery (if missing).

        Args:
            matched: Dict from match_episode_files().
            show_dir: Path to the TV show directory.
            show_data: Full TMDB show details.
        """
        show_title = show_data.get("name", "")
        mpaa = NFOGenerator._extract_content_rating_fr(show_data)
        networks = show_data.get("networks", [])
        studio = networks[0].get("name", "") if networks else ""

        for video_path, info in matched.items():
            season = info["season"]
            episode = info["episode"]
            api_title = info["api_title"]
            still_path = info.get("still_path", "")

            # Fallback entries (no provider record — synthetic "Episode N" title)
            # skip NFO/thumb generation: the file lands as "SxxExx - Episode N.mkv"
            # under its Saison XX/ dir so verify/dispatch don't block, but we refuse
            # to fabricate episode metadata.
            if info.get("fallback"):
                continue

            season_dir_name = self.patterns.format("season_dir", Season=season)
            new_stem = self.patterns.format(
                "episode_video",
                Season=season,
                Episode=episode,
                EpisodeTitle=api_title,
            )
            nfo_path = show_dir / season_dir_name / f"{new_stem}.nfo"
            thumb_name = self.patterns.format(
                "episode_thumb",
                Season=season,
                Episode=episode,
                EpisodeTitle=api_title,
            )
            thumb_path = show_dir / season_dir_name / thumb_name

            if nfo_path.exists():
                # Still download thumbnail if NFO exists but thumb doesn't
                self._download_episode_thumb(still_path, thumb_path, season, episode)
                continue

            episode_data = {
                "name": api_title,
                "showtitle": show_title,
                "id": "",
                "tvdb_id": "",
                "season_number": season,
                "episode_number": episode,
                "overview": "",
                "mpaa": mpaa,
                "studio": studio,
                "crew": [],
                "still_path": still_path,
            }

            # Stream info from the renamed video
            renamed_video = show_dir / season_dir_name / f"{new_stem}{video_path.suffix}"
            stream_info = None
            if renamed_video.exists():
                stream_info = extract_stream_info(renamed_video)

            try:
                xml = self._nfo.generate_episode_nfo(episode_data, stream_info)
                if not self.dry_run:
                    nfo_path.parent.mkdir(parents=True, exist_ok=True)
                    self._nfo.write_nfo(xml, nfo_path)
            except Exception as e:
                log.warning("episode_nfo_failed", season=season, episode=episode, error=str(e), exc_info=True)

            # Download episode thumbnail
            self._download_episode_thumb(still_path, thumb_path, season, episode)

    def process_tvshows(self, tvshows_dir: Path) -> list[ScrapeResult]:
        """Scrape all TV shows in a directory.

        When both TVDB and TMDB circuits are OPEN, skips remaining shows.
        When only TVDB is OPEN, TMDB fallback is used (handled in
        match_tvshow via CircuitOpenError catch).

        Args:
            tvshows_dir: Path to the TV shows directory (e.g. {tvshows_dir}/).

        Returns:
            List of ScrapeResult for each processed show.
        """
        from personalscraper.scraper.circuit_breaker import CircuitOpenError

        results: list[ScrapeResult] = []

        if not tvshows_dir.exists():
            log.warning("tvshows_dir_not_found", path=str(tvshows_dir))
            return results

        subdirs = sorted(d for d in tvshows_dir.iterdir() if d.is_dir() and not d.name.startswith("."))

        log.info("tvshows_start", count=len(subdirs), directory=tvshows_dir.name)

        for show_dir in subdirs:
            # Skip if both circuits are OPEN (no provider available)
            if not self._tvdb.circuit.can_proceed() and not self._tmdb.circuit.can_proceed():
                log.warning("tvshows_both_circuits_open", directory=show_dir.name)
                results.append(
                    ScrapeResult(
                        media_path=show_dir,
                        media_type="tvshow",
                        action="error",
                        error="Both TVDB and TMDB circuit breakers OPEN",
                    )
                )
                continue

            try:
                result = self.scrape_tvshow(show_dir)
                results.append(result)
            except CircuitOpenError as e:
                # Both providers went down during this item
                log.warning("tvshows_circuit_opened", directory=show_dir.name, error=str(e))
                results.append(
                    ScrapeResult(
                        media_path=show_dir,
                        media_type="tvshow",
                        action="error",
                        error=str(e),
                    )
                )
            except Exception as e:
                log.error("tvshows_unexpected_error", directory=show_dir.name, error=str(e))
                results.append(
                    ScrapeResult(
                        media_path=show_dir,
                        media_type="tvshow",
                        action="error",
                        error=str(e),
                    )
                )

        scraped = sum(1 for r in results if r.action == "scraped")
        skipped = sum(1 for r in results if r.action.startswith("skipped"))
        unmatched = sum(1 for r in results if r.action == "skipped_low_confidence")
        errors = sum(1 for r in results if r.action == "error")
        log.info("tvshows_done", scraped=scraped, skipped=skipped, unmatched=unmatched, errors=errors)

        return results

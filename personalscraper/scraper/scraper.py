"""Main scraping orchestrator for movies and TV shows.

Coordinates metadata matching, NFO generation, artwork download, and
episode management into a complete scraping pipeline. Each media item
produces a ScrapeResult indicating what was done.

Movie flow: parse folder → match TMDB → get details → NFO → artwork
TV show flow: parse folder → match TVDB/TMDB → get details → tvshow.nfo →
              artwork → season dirs → episode titles → rename → episode NFOs
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.naming_patterns import SEASON_DIR_RE, NamingPatterns
from personalscraper.scraper.artwork import ArtworkDownloader
from personalscraper.scraper.confidence import (
    LOW_CONFIDENCE,
    MatchResult,
    match_movie,
    match_tvshow,
)
from personalscraper.scraper.episode_manager import (
    create_season_dirs,
    match_episode_files,
    rename_episodes,
)
from personalscraper.scraper.mediainfo import extract_stream_info
from personalscraper.scraper.nfo_generator import NFOGenerator
from personalscraper.scraper.tmdb_client import TMDBClient
from personalscraper.scraper.tvdb_client import TVDBClient
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS
from personalscraper.text_utils import sanitize_filename

logger = logging.getLogger(__name__)

# Regex for parsing "Title (Year)" folder names
_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")

# Regex for extracting SxxExx episode identifiers from filenames
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)


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
            logger.warning("Merge failed for %s → %s: %s", item.name, dest, exc)
    # Remove empty source after merge — preserve if items remain
    try:
        if source.exists() and not any(source.iterdir()):
            source.rmdir()
    except OSError as exc:
        logger.warning("Could not remove source dir %s: %s", source.name, exc)
    if failed:
        logger.warning(
            "Merge %s → %s: %d moved, %d failed — source dir preserved",
            source.name, target.name, moved, failed,
        )
    return moved, failed


def _is_nfo_complete(nfo_path: Path) -> bool:
    """Check if an NFO file is complete and valid.

    A complete NFO must:
    1. Exist on disk
    2. Be parsable as XML
    3. Contain at least one <uniqueid> element with non-empty text

    Used to distinguish valid NFOs from crash-truncated or incomplete
    ones that should be re-scraped.

    Args:
        nfo_path: Path to the .nfo file.

    Returns:
        True if the NFO is complete and valid.
    """
    if not nfo_path.exists():
        return False
    try:
        tree = ET.parse(nfo_path)  # noqa: S314
        root = tree.getroot()
        # Must have at least one uniqueid with non-empty text
        for uid in root.findall("uniqueid"):
            if uid.text and uid.text.strip():
                return True
        return False
    except ET.ParseError:
        logger.debug("NFO not parsable as XML: %s", nfo_path.name)
        return False
    except OSError as exc:
        logger.warning("Cannot read NFO file %s: %s", nfo_path, exc)
        return False


@dataclass
class ScrapeResult:
    """Result of scraping a single media item.

    Attributes:
        media_path: Path to the media directory.
        media_type: Type of media ("movie" or "tvshow").
        match: Matched API result, or None if no match.
        nfo_written: Whether an NFO file was written.
        artwork_downloaded: List of downloaded artwork filenames.
        episodes_renamed: Number of episodes renamed (0 for movies).
        action: Result action ("scraped", "skipped_low_confidence",
            "skipped_already_done", "artwork_recovered", "error").
        error: Error message if action is "error".
        warnings: Non-fatal issues (e.g. artwork download failure).
    """

    media_path: Path
    media_type: str
    match: MatchResult | None = None
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
            logger.info("Cleaned raw folder name: %s → %s (%s)", name, title, year)
            return title, year
    except ImportError:
        logger.warning("NameCleaner/guessit not available, using raw folder name: %s", name)
    except Exception:
        logger.warning("NameCleaner failed for '%s', using raw name", name, exc_info=True)

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
        f for f in directory.rglob("*")
        if f.is_file()
        and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        and not f.name.startswith(".")
        and ".actors" not in f.parts
    ]
    if not candidates:
        return None
    try:
        return max(candidates, key=lambda f: f.stat().st_size)
    except OSError:
        # stat() failed on a candidate (broken symlink, NTFS metadata issue)
        # — fall back to first candidate rather than crashing the scrape
        logger.warning("Cannot stat some video files in %s, using first candidate", directory.name)
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
        new_name = new_prefix + f.name[len(old_prefix):]
        if (directory / new_name).exists():
            try:
                f.unlink()
                logger.info("Cleaned stale file: %s", f.name)
                removed += 1
            except OSError as exc:
                logger.warning("Cannot remove stale file %s: %s", f.name, exc)
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
        has_video = any(
            f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            for f in subdir.rglob("*")
        )
        if has_video:
            continue
        non_video_files = [f.name for f in subdir.rglob("*") if f.is_file()]
        if non_video_files:
            logger.warning(
                "Removing release dir %s with residual files: %s",
                subdir.name, non_video_files,
            )
        try:
            shutil.rmtree(subdir)
            logger.info("Removed release dir (no videos): %s", subdir.name)
            removed += 1
        except OSError as exc:
            logger.warning("Cannot remove dir %s: %s", subdir.name, exc)
    return removed


class Scraper:
    """Main scraping orchestrator.

    Coordinates TMDB/TVDB matching, NFO generation, artwork download,
    and episode management for both movies and TV shows.

    Attributes:
        settings: Pipeline configuration.
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
    ):
        """Initialize the scraper with API clients and helpers.

        Args:
            settings: Pipeline configuration with API keys.
            patterns: MediaElch-compatible naming patterns.
            dry_run: If True, preview operations without writing.
            interactive: If True, prompt for ambiguous matches.
        """
        self.settings = settings
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

        # Initialize helpers
        self._nfo = NFOGenerator()
        self._artwork = ArtworkDownloader(
            dry_run=dry_run, artwork_language=settings.artwork_language,
        )

    def _resolve_title(
        self,
        match_title: str,
        api_data: dict,
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
            logger.debug("No local title for '%s', using match title", match_title)
            return match_title

        # If local title is the same as original_title, it means
        # there's no translation — use match_title instead
        original = api_data.get("original_title" if media_type == "movie" else "original_name", "")
        if local_title == original and local_title != match_title:
            logger.debug("No translation for '%s', using match title '%s'", local_title, match_title)
            return match_title

        return local_title

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
        import re
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
            logger.warning("Cannot parse NFO for TMDB ID: %s: %s", nfo_path.name, exc)
            return None
        for uid in root.findall("uniqueid"):
            if uid.get("type") == "tmdb" and uid.text:
                try:
                    return int(uid.text)
                except ValueError:
                    logger.warning("Non-numeric TMDB ID '%s' in NFO: %s", uid.text, nfo_path)
                    return None
        logger.debug("No TMDB ID in NFO, cannot recover artwork: %s", nfo_path)
        return None

    def _recover_movie_artwork(
        self, nfo_path: Path, movie_dir: Path, result: ScrapeResult,
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
        try:
            movie_data = self._tmdb.get_movie(tmdb_id)
            downloaded = self._artwork.download_movie_artwork(
                movie_data, movie_dir, self.patterns,
            )
            if downloaded:
                result.action = "artwork_recovered"
                result.artwork_downloaded = [p.name for p in downloaded]
                logger.info(
                    "Recovered %d artwork(s) for %s", len(downloaded), movie_dir.name,
                )
        except Exception as e:
            logger.warning("Artwork recovery failed for %s: %s", movie_dir.name, e)
            result.warnings.append(f"Artwork recovery failed: {e}")

    def _recover_tvshow_artwork(
        self, nfo_path: Path, show_dir: Path, result: ScrapeResult,
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
        try:
            show_data = self._tmdb.get_tv(tmdb_id)
            downloaded = self._artwork.download_tvshow_artwork(
                show_data, show_dir, self.patterns,
            )
            if downloaded:
                result.action = "artwork_recovered"
                result.artwork_downloaded = [p.name for p in downloaded]
                logger.info(
                    "Recovered %d artwork(s) for %s", len(downloaded), show_dir.name,
                )
        except Exception as e:
            logger.warning("Artwork recovery failed for %s: %s", show_dir.name, e)
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
                        logger.info("Repair: removed residual NFO %s", nfo.name)
                        repaired = True
                    except OSError as exc:
                        logger.warning("Repair: cannot delete %s: %s", nfo.name, exc)
                else:
                    logger.info("[DRY RUN] Would remove residual NFO %s", nfo.name)
                    repaired = True

        return repaired

    def _repair_tvshow_dir(self, show_dir: Path) -> bool:
        """Repair a TV show directory with valid NFO.

        1. Remove residual NFOs at root (keep only tvshow.nfo).
        2. Remove root MKV duplicates (same SxxExx in Saison XX/).
        3. Organize unstructured episodes into Saison XX/ (if TMDB ID available).

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
                        logger.info(
                            "Repair: removed residual NFO %s in %s",
                            nfo.name, show_dir.name,
                        )
                        repaired = True
                    except OSError as exc:
                        logger.warning(
                            "Repair: cannot delete %s: %s", nfo.name, exc,
                        )
                else:
                    logger.info(
                        "[DRY RUN] Would remove residual NFO %s", nfo.name,
                    )
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
                if (
                    not f.is_file()
                    or f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS
                ):
                    continue
                m = _SXXEXX_RE.search(f.stem)
                if m and (int(m.group(1)), int(m.group(2))) in organized:
                    if not self.dry_run:
                        try:
                            f.unlink()
                            logger.info(
                                "Repair: removed root duplicate %s "
                                "(in Saison already)",
                                f.name,
                            )
                            repaired = True
                        except OSError as exc:
                            logger.warning(
                                "Repair: cannot delete %s: %s", f.name, exc,
                            )
                    else:
                        logger.info(
                            "[DRY RUN] Would remove root duplicate %s",
                            f.name,
                        )
                        repaired = True

        # 4. Organize unstructured episodes (from raw torrent dirs)
        # Finds video files in non-season subdirs (not root, not .actors)
        unorganized = sorted(
            f for f in show_dir.rglob("*")
            if f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and not SEASON_DIR_RE.match(f.parent.name)
            and f.parent != show_dir
            and ".actors" not in f.parts
        )

        if unorganized:
            nfo_path = show_dir / "tvshow.nfo"
            tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
            if tmdb_id:
                try:
                    show_data = self._tmdb.get_tv(tmdb_id)
                    api_episodes: dict[tuple[int, int], dict] = {}
                    for season in show_data.get("seasons", []):
                        s_num = season.get("season_number", 0)
                        if s_num == 0:
                            continue
                        try:
                            s_detail = self._tmdb.get_tv_season(
                                tmdb_id, s_num,
                            )
                            for ep in s_detail.get("episodes", []):
                                e_num = ep.get("episode_number", 0)
                                api_episodes[(s_num, e_num)] = {
                                    "title": ep.get("name", f"Episode {e_num}"),
                                    "still_path": ep.get("still_path", ""),
                                }
                        except (OSError, ConnectionError, TimeoutError) as e:
                            logger.warning(
                                "Repair: failed to get season %d: %s",
                                s_num, e,
                            )

                    if api_episodes:
                        ep_list = [
                            {"season_number": s, "episode_number": e}
                            for s, e in api_episodes
                        ]
                        create_season_dirs(
                            show_dir, ep_list, self.patterns, self.dry_run,
                        )
                        matched = match_episode_files(
                            unorganized, api_episodes,
                        )
                        if matched:
                            count = rename_episodes(
                                matched, show_dir, self.patterns,
                                self.dry_run,
                            )
                            if count > 0:
                                repaired = True
                                logger.info(
                                    "Repair: organized %d episodes in %s",
                                    count, show_dir.name,
                                )
                            self._generate_episode_nfos(
                                matched, show_dir, show_data,
                            )

                except (OSError, ConnectionError, TimeoutError, ValueError, KeyError) as e:
                    logger.warning(
                        "Repair: failed to organize episodes in %s: %s",
                        show_dir.name, e,
                    )
            else:
                logger.warning(
                    "Repair: cannot organize episodes in %s "
                    "— no TMDB ID in NFO",
                    show_dir.name,
                )

        # Always clean residual torrent dirs (even if no unorganized episodes)
        if not self.dry_run:
            try:
                cleaned = _cleanup_empty_release_dirs(show_dir)
                if cleaned > 0:
                    repaired = True
            except OSError as exc:
                logger.warning(
                    "Repair: failed to clean release dirs in %s: %s",
                    show_dir.name, exc,
                )

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
            logger.info("NFO valid, %s: %s", result.action, movie_dir.name)
            return result

        # Corrupt NFO: delete before re-scrape
        if nfo_path.exists():
            logger.warning("Corrupt NFO detected, re-scraping: %s", nfo_path.name)
            try:
                nfo_path.unlink()
            except OSError as exc:
                result.error = f"Cannot delete corrupt NFO: {exc}"
                logger.error("Cannot delete corrupt NFO %s: %s", nfo_path, exc)
                return result

        # Match against TMDB
        try:
            match = match_movie(self._tmdb, title, year)
        except Exception as e:
            result.error = f"Match failed: {e}"
            logger.error("Failed to match movie %s: %s", title, e)
            return result

        if match is None or match.confidence < LOW_CONFIDENCE:
            result.action = "skipped_low_confidence"
            logger.info(
                "No confident match for: %s (score=%.2f)",
                title, match.confidence if match else 0.0,
            )
            return result

        result.match = match
        logger.info(
            "Matched: %s → %s (%s, confidence=%.2f)",
            title, match.api_title, match.source, match.confidence,
        )

        # Get full movie details (needed for local title resolution)
        try:
            movie_data = self._tmdb.get_movie(match.api_id)
        except Exception as e:
            result.error = f"Get details failed: {e}"
            logger.error("Failed to get movie details for %s: %s", match.api_title, e)
            return result

        # Resolve title: use local FR title if preferred and available
        resolved_title = self._strip_trailing_year(
            self._resolve_title(match.api_title, movie_data, "movie")
        )
        api_year = match.api_year or year
        clean_name = sanitize_filename(
            f"{resolved_title} ({api_year})" if api_year else resolved_title
        )

        # Save old title before rename for stale file cleanup
        old_title = title

        # Rename folder to clean format if it doesn't match
        if movie_dir.name != clean_name:
            new_path = movie_dir.parent / clean_name
            if not self.dry_run:
                try:
                    if new_path.exists():
                        moved, merge_failed = _merge_dirs(movie_dir, new_path)
                        logger.info("Merged duplicate: %s → %s (%d items)", movie_dir.name, clean_name, moved)
                        if merge_failed:
                            result.warnings.append(
                                f"Partial merge: {merge_failed} item(s) failed"
                            )
                    else:
                        movie_dir.rename(new_path)
                        logger.info("Renamed folder: %s → %s", movie_dir.name, clean_name)
                    movie_dir = new_path
                    result.media_path = new_path
                    title = resolved_title
                    nfo_name = self.patterns.format("movie_nfo", Title=title)
                    nfo_path = movie_dir / nfo_name
                except OSError as exc:
                    result.error = f"Rename/merge failed: {exc}"
                    logger.error("Failed to rename %s → %s: %s", movie_dir.name, clean_name, exc)
                    return result
                # Non-critical: clean stale artwork/NFO from before rename
                try:
                    _cleanup_stale_files(movie_dir, old_title, resolved_title)
                except OSError as exc:
                    logger.warning("Stale file cleanup failed for %s: %s", movie_dir.name, exc)
            else:
                action = "merge into" if new_path.exists() else "rename"
                logger.info("[DRY RUN] Would %s: %s → %s", action, movie_dir.name, clean_name)

        # Rename video file to clean title and extract stream info
        video_file = _find_video_file(movie_dir)
        stream_info = None
        if video_file:
            clean_video_name = self.patterns.format(
                "movie_video", Title=title,
            ) + video_file.suffix
            if video_file.name != clean_video_name:
                new_video = movie_dir / clean_video_name
                if not self.dry_run:
                    try:
                        video_file.rename(new_video)
                        logger.info("Renamed video: %s → %s", video_file.name, clean_video_name)
                        video_file = new_video
                    except OSError as exc:
                        logger.warning(
                            "Failed to rename video %s → %s in %s: %s",
                            video_file.name, clean_video_name, movie_dir.name, exc,
                        )
                        result.warnings.append(
                            f"Video rename failed: {video_file.name}: {exc}"
                        )
                else:
                    logger.info("[DRY RUN] Would rename video: %s → %s", video_file.name, clean_video_name)
            stream_info = extract_stream_info(video_file)

        # Generate and write NFO
        try:
            xml = self._nfo.generate_movie_nfo(movie_data, stream_info)
            if not self.dry_run:
                self._nfo.write_nfo(xml, nfo_path)
                result.nfo_written = True
                logger.info("Wrote NFO: %s", nfo_path.name)
            else:
                logger.info("[DRY RUN] Would write NFO: %s", nfo_path.name)
        except Exception as e:
            result.error = f"NFO generation failed: {e}"
            logger.error("Failed to generate NFO for %s: %s", title, e)
            return result

        # Download artwork
        try:
            downloaded = self._artwork.download_movie_artwork(
                movie_data, movie_dir, self.patterns,
            )
            result.artwork_downloaded = [p.name for p in downloaded]
        except Exception as e:
            logger.warning("Artwork download failed for %s: %s", title, e)
            result.warnings.append(f"Artwork failed: {e}")

        result.action = "scraped"
        return result

    def process_movies(self, movies_dir: Path) -> list[ScrapeResult]:
        """Scrape all movies in a directory.

        Scans all subdirectories of movies_dir and calls scrape_movie()
        on each one. When the TMDB circuit breaker is OPEN, skips
        remaining movies (no viable fallback for movie metadata).

        Args:
            movies_dir: Path to the movies directory (e.g. 001-MOVIES/).

        Returns:
            List of ScrapeResult for each processed movie.
        """
        from personalscraper.scraper.circuit_breaker import CircuitOpenError

        results: list[ScrapeResult] = []

        if not movies_dir.exists():
            logger.warning("Movies directory not found: %s", movies_dir)
            return results

        # Each subdirectory is a movie
        subdirs = sorted(
            d for d in movies_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

        logger.info("Processing %d movies in %s", len(subdirs), movies_dir.name)

        for movie_dir in subdirs:
            # Skip if TMDB circuit is OPEN (primary provider for movies)
            if not self._tmdb.circuit.can_proceed():
                logger.warning(
                    "TMDB circuit OPEN, skipping movie: %s", movie_dir.name,
                )
                results.append(ScrapeResult(
                    media_path=movie_dir,
                    media_type="movie",
                    action="error",
                    error="TMDB circuit breaker OPEN",
                ))
                continue

            try:
                result = self.scrape_movie(movie_dir)
                results.append(result)
            except CircuitOpenError as e:
                # Circuit opened during this item's processing
                logger.warning(
                    "TMDB circuit opened while processing %s: %s",
                    movie_dir.name, e,
                )
                results.append(ScrapeResult(
                    media_path=movie_dir,
                    media_type="movie",
                    action="error",
                    error=str(e),
                ))
            except Exception as e:
                logger.error("Unexpected error processing %s: %s", movie_dir.name, e)
                results.append(ScrapeResult(
                    media_path=movie_dir,
                    media_type="movie",
                    action="error",
                    error=str(e),
                ))

        # Summary
        scraped = sum(1 for r in results if r.action == "scraped")
        skipped = sum(1 for r in results if r.action.startswith("skipped"))
        errors = sum(1 for r in results if r.action == "error")
        logger.info(
            "Movies done: %d scraped, %d skipped, %d errors",
            scraped, skipped, errors,
        )

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
            # Check for missing artwork — recover without re-scraping
            missing_art = self._check_missing_tvshow_artwork(show_dir)
            if missing_art and not self.dry_run:
                self._recover_tvshow_artwork(nfo_path, show_dir, result)
            # Repair pass: remove residual NFOs, root MKV duplicates, etc.
            repaired = self._repair_tvshow_dir(show_dir)
            if repaired and result.action != "artwork_recovered":
                result.action = "repaired"
            elif result.action != "artwork_recovered":
                result.action = "skipped_already_done"
            logger.info("NFO valid, %s: %s", result.action, show_dir.name)
            return result

        # Corrupt NFO: delete before re-scrape
        if nfo_path.exists():
            logger.warning("Corrupt NFO detected, re-scraping: %s", nfo_path.name)
            try:
                nfo_path.unlink()
            except OSError as exc:
                result.error = f"Cannot delete corrupt NFO: {exc}"
                logger.error("Cannot delete corrupt NFO %s: %s", nfo_path, exc)
                return result

        # Match against TVDB/TMDB
        try:
            match = match_tvshow(self._tvdb, self._tmdb, title, year)
        except Exception as e:
            result.error = f"Match failed: {e}"
            logger.error("Failed to match show %s: %s", title, e)
            return result

        if match is None or match.confidence < LOW_CONFIDENCE:
            result.action = "skipped_low_confidence"
            logger.info(
                "No confident match for show: %s (score=%.2f)",
                title, match.confidence if match else 0.0,
            )
            return result

        result.match = match
        logger.info(
            "Matched show: %s → %s (%s, confidence=%.2f)",
            title, match.api_title, match.source, match.confidence,
        )

        # Get full TMDB details (even if matched via TVDB)
        tmdb_id: int | None = match.api_id
        try:
            if match.source == "tvdb":
                tvdb_data = self._tvdb.get_series(match.api_id)
                remote_ids = self._tvdb.get_remote_ids(tvdb_data)
                raw_id = remote_ids.get("tmdb_id")
                tmdb_id = int(raw_id) if raw_id else None
                if not tmdb_id:
                    logger.warning("No TMDB cross-ref for TVDB show %d", match.api_id)
            if tmdb_id:
                show_data = self._tmdb.get_tv(tmdb_id)
            else:
                result.error = "No TMDB ID available"
                return result
        except Exception as e:
            result.error = f"Get details failed: {e}"
            logger.error("Failed to get show details: %s", e)
            return result

        # Resolve title: use local FR title if preferred and available
        resolved_title = self._strip_trailing_year(
            self._resolve_title(match.api_title, show_data, "tvshow")
        )

        # Rename folder to canonical name (V2→V3 handoff)
        old_dir_name = show_dir.name  # Save before potential rename
        canonical = self.patterns.format(
            "movie_dir", Title=resolved_title,
            Year=match.api_year or year or "",
        )
        if show_dir.name != canonical:
            new_dir = show_dir.parent / canonical
            if not self.dry_run:
                try:
                    if new_dir.exists():
                        moved, merge_failed = _merge_dirs(show_dir, new_dir)
                        logger.info("Merged duplicate: %s → %s (%d items)", title, canonical, moved)
                        if merge_failed:
                            result.warnings.append(
                                f"Partial merge: {merge_failed} item(s) failed"
                            )
                    else:
                        show_dir.rename(new_dir)
                        logger.info("Renamed folder: %s → %s", title, canonical)
                    show_dir = new_dir
                    result.media_path = new_dir
                except OSError as exc:
                    result.error = f"Rename/merge failed: {exc}"
                    logger.error("Failed to rename %s → %s: %s", title, canonical, exc)
                    return result
                # Non-critical: clean stale files from before rename.
                # TV show artwork uses fixed names (poster.jpg, tvshow.nfo),
                # so this is a no-op for standard shows. Kept as safety net.
                try:
                    _cleanup_stale_files(show_dir, old_dir_name, canonical)
                except OSError as exc:
                    logger.warning("Stale file cleanup failed for %s: %s", show_dir.name, exc)
            else:
                action = "merge into" if new_dir.exists() else "rename"
                logger.info("[DRY RUN] Would %s: %s → %s", action, title, canonical)

        # Generate tvshow.nfo
        try:
            xml = self._nfo.generate_tvshow_nfo(show_data)
            nfo_path = show_dir / self.patterns.tvshow_nfo
            if not self.dry_run:
                self._nfo.write_nfo(xml, nfo_path)
                result.nfo_written = True
            else:
                logger.info("[DRY RUN] Would write tvshow.nfo")
        except Exception as e:
            result.error = f"tvshow.nfo failed: {e}"
            return result

        # Download artwork
        try:
            downloaded = self._artwork.download_tvshow_artwork(
                show_data, show_dir, self.patterns,
            )
            result.artwork_downloaded = [p.name for p in downloaded]
        except Exception as e:
            logger.warning("Artwork failed for %s: %s", match.api_title, e)
            result.warnings.append(f"Artwork failed: {e}")

        # Process episodes — rglob to find files nested in release-group subdirs,
        # but skip files already organized in Saison XX/ directories
        total_renamed = 0
        video_files = sorted(
            f for f in show_dir.rglob("*")
            if f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and not SEASON_DIR_RE.match(f.parent.name)
        )

        if video_files:
            api_episodes: dict[tuple[int, int], dict] = {}
            for season in show_data.get("seasons", []):
                s_num = season.get("season_number", 0)
                if s_num == 0:
                    continue
                try:
                    s_detail = self._tmdb.get_tv_season(tmdb_id, s_num)
                    for ep in s_detail.get("episodes", []):
                        e_num = ep.get("episode_number", 0)
                        api_episodes[(s_num, e_num)] = {
                            "title": ep.get("name", f"Episode {e_num}"),
                            "still_path": ep.get("still_path", ""),
                        }
                except Exception as e:
                    logger.warning("Failed to get season %d: %s", s_num, e)

            if api_episodes:
                ep_list = [{"season_number": s, "episode_number": e} for s, e in api_episodes]
                create_season_dirs(show_dir, ep_list, self.patterns, self.dry_run)
                matched = match_episode_files(video_files, api_episodes)
                if matched:
                    total_renamed = rename_episodes(matched, show_dir, self.patterns, self.dry_run)
                    self._generate_episode_nfos(matched, show_dir, show_data)

            # Clean empty release-group subdirectories left after episode moves
            if not self.dry_run:
                try:
                    _cleanup_empty_release_dirs(show_dir)
                except OSError as exc:
                    logger.warning("Failed to clean empty release dirs in %s: %s", show_dir.name, exc)

        result.episodes_renamed = total_renamed
        result.action = "scraped"
        return result

    def _generate_episode_nfos(
        self,
        matched: dict[Path, dict],
        show_dir: Path,
        show_data: dict,
    ) -> None:
        """Generate NFO files for each matched/renamed episode.

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

            season_dir_name = self.patterns.format("season_dir", Season=season)
            new_stem = self.patterns.format(
                "episode_video",
                Season=season, Episode=episode, EpisodeTitle=api_title,
            )
            nfo_path = show_dir / season_dir_name / f"{new_stem}.nfo"

            if nfo_path.exists():
                # Still download thumbnail if NFO exists but thumb doesn't
                thumb_name = self.patterns.format(
                    "episode_thumb",
                    Season=season, Episode=episode, EpisodeTitle=api_title,
                )
                thumb_path = show_dir / season_dir_name / thumb_name
                if still_path and not thumb_path.exists() and not self.dry_run:
                    url = f"https://image.tmdb.org/t/p/original{still_path}"
                    self._artwork.download_image(url, thumb_path)
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
                logger.warning(
                    "Episode NFO failed for S%02dE%02d: %s", season, episode, e,
                    exc_info=True,
                )

            # Download episode thumbnail
            if still_path and not self.dry_run:
                thumb_name = self.patterns.format(
                    "episode_thumb",
                    Season=season, Episode=episode, EpisodeTitle=api_title,
                )
                thumb_path = show_dir / season_dir_name / thumb_name
                if not thumb_path.exists():
                    url = f"https://image.tmdb.org/t/p/original{still_path}"
                    self._artwork.download_image(url, thumb_path)

    def process_tvshows(self, tvshows_dir: Path) -> list[ScrapeResult]:
        """Scrape all TV shows in a directory.

        When both TVDB and TMDB circuits are OPEN, skips remaining shows.
        When only TVDB is OPEN, TMDB fallback is used (handled in
        match_tvshow via CircuitOpenError catch).

        Args:
            tvshows_dir: Path to the TV shows directory (e.g. 002-TVSHOWS/).

        Returns:
            List of ScrapeResult for each processed show.
        """
        from personalscraper.scraper.circuit_breaker import CircuitOpenError

        results: list[ScrapeResult] = []

        if not tvshows_dir.exists():
            logger.warning("TV shows directory not found: %s", tvshows_dir)
            return results

        subdirs = sorted(
            d for d in tvshows_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

        logger.info("Processing %d TV shows in %s", len(subdirs), tvshows_dir.name)

        for show_dir in subdirs:
            # Skip if both circuits are OPEN (no provider available)
            if (
                not self._tvdb.circuit.can_proceed()
                and not self._tmdb.circuit.can_proceed()
            ):
                logger.warning(
                    "Both TVDB and TMDB circuits OPEN, skipping show: %s",
                    show_dir.name,
                )
                results.append(ScrapeResult(
                    media_path=show_dir,
                    media_type="tvshow",
                    action="error",
                    error="Both TVDB and TMDB circuit breakers OPEN",
                ))
                continue

            try:
                result = self.scrape_tvshow(show_dir)
                results.append(result)
            except CircuitOpenError as e:
                # Both providers went down during this item
                logger.warning(
                    "Circuit opened while processing %s: %s",
                    show_dir.name, e,
                )
                results.append(ScrapeResult(
                    media_path=show_dir,
                    media_type="tvshow",
                    action="error",
                    error=str(e),
                ))
            except Exception as e:
                logger.error("Unexpected error processing %s: %s", show_dir.name, e)
                results.append(ScrapeResult(
                    media_path=show_dir,
                    media_type="tvshow",
                    action="error",
                    error=str(e),
                ))

        scraped = sum(1 for r in results if r.action == "scraped")
        skipped = sum(1 for r in results if r.action.startswith("skipped"))
        errors = sum(1 for r in results if r.action == "error")
        logger.info(
            "TV shows done: %d scraped, %d skipped, %d errors",
            scraped, skipped, errors,
        )

        return results

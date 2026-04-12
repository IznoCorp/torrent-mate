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
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.artwork import ArtworkDownloader
from personalscraper.scraper.confidence import (  # noqa: F401
    LOW_CONFIDENCE,
    MatchResult,
    match_movie,
    match_tvshow,
)
from personalscraper.scraper.episode_manager import (  # noqa: F401
    create_season_dirs,
    match_episode_files,
    rename_episodes,
)
from personalscraper.scraper.mediainfo import extract_stream_info
from personalscraper.scraper.nfo_generator import NFOGenerator
from personalscraper.scraper.tmdb_client import TMDBClient
from personalscraper.scraper.tvdb_client import TVDBClient
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)

# Regex for parsing "Title (Year)" folder names
_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")


def _merge_dirs(source: Path, target: Path) -> int:
    """Merge contents of source directory into target, then remove source.

    Files in source that already exist in target are replaced (newer wins).
    Subdirectories are merged recursively. Used to deduplicate folders
    like "Shrinking" + "Shrinking (2023)".

    Args:
        source: Directory to merge from (will be removed after).
        target: Directory to merge into (must exist).

    Returns:
        Number of items moved.
    """
    import shutil as _shutil

    moved = 0
    for item in source.iterdir():
        dest = target / item.name
        if item.is_dir() and dest.is_dir():
            # Recursive merge for subdirectories (e.g. Saison 01/)
            moved += _merge_dirs(item, dest)
        else:
            # Move file/dir, replacing if exists
            if dest.exists():
                if dest.is_dir():
                    _shutil.rmtree(dest)
                else:
                    dest.unlink()
            _shutil.move(str(item), str(dest))
            moved += 1
    # Remove empty source after merge
    if source.exists() and not any(source.iterdir()):
        source.rmdir()
    return moved


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
            "skipped_already_done", "error").
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
    except Exception:
        pass  # Guessit unavailable — use raw name

    return name.strip(), None


def _find_video_file(directory: Path) -> Path | None:
    """Find the first video file in a directory.

    Args:
        directory: Path to search for video files.

    Returns:
        Path to the first video file found, or None.
    """
    for f in sorted(directory.iterdir()):
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS:
            return f
    return None


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
        self._artwork = ArtworkDownloader(dry_run=dry_run)

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
            api_data: Full movie/show data from TMDB/TVDB API.
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
            return match_title

        # If local title is the same as original_title, it means
        # there's no translation — use match_title instead
        original = api_data.get("original_title" if media_type == "movie" else "original_name", "")
        if local_title == original and local_title != match_title:
            return match_title

        return local_title

    def scrape_movie(self, movie_dir: Path) -> ScrapeResult:
        """Scrape a single movie: match → NFO → artwork.

        Flow:
        1. Parse title + year from folder name
        2. Skip if .nfo already exists
        3. Match against TMDB
        4. Get full movie details
        5. Extract stream info from video file
        6. Generate and write NFO
        7. Download artwork (poster + landscape)

        Args:
            movie_dir: Path to the movie directory.

        Returns:
            ScrapeResult with action and details.
        """
        title, year = _parse_folder_name(movie_dir.name)
        result = ScrapeResult(media_path=movie_dir, media_type="movie")

        # Check for existing NFO
        nfo_name = self.patterns.format("movie_nfo", Title=title)
        nfo_path = movie_dir / nfo_name
        if nfo_path.exists():
            result.action = "skipped_already_done"
            logger.info("NFO already exists, skipping: %s", movie_dir.name)
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
        resolved_title = self._resolve_title(match.api_title, movie_data, "movie")
        api_year = match.api_year or year
        clean_name = f"{resolved_title} ({api_year})" if api_year else resolved_title

        # Rename folder to clean format if it doesn't match
        if movie_dir.name != clean_name:
            new_path = movie_dir.parent / clean_name
            if not self.dry_run:
                if new_path.exists():
                    count = _merge_dirs(movie_dir, new_path)
                    logger.info("Merged duplicate: %s → %s (%d items)", movie_dir.name, clean_name, count)
                else:
                    movie_dir.rename(new_path)
                    logger.info("Renamed folder: %s → %s", movie_dir.name, clean_name)
                movie_dir = new_path
                result.media_path = new_path
                title = resolved_title
                nfo_name = self.patterns.format("movie_nfo", Title=title)
                nfo_path = movie_dir / nfo_name
            else:
                action = "merge into" if new_path.exists() else "rename"
                logger.info("[DRY RUN] Would %s: %s → %s", action, movie_dir.name, clean_name)

        # Extract stream info from video file
        video_file = _find_video_file(movie_dir)
        stream_info = None
        if video_file:
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

        # Check for existing NFO
        nfo_path = show_dir / self.patterns.tvshow_nfo
        if nfo_path.exists():
            result.action = "skipped_already_done"
            logger.info("tvshow.nfo already exists, skipping: %s", show_dir.name)
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
        resolved_title = self._resolve_title(match.api_title, show_data, "tvshow")

        # Rename folder to canonical name (V2→V3 handoff)
        canonical = self.patterns.format(
            "movie_dir", Title=resolved_title,
            Year=match.api_year or year or "",
        )
        if show_dir.name != canonical:
            new_dir = show_dir.parent / canonical
            if not self.dry_run:
                if new_dir.exists():
                    # Duplicate detected — merge contents into existing folder
                    count = _merge_dirs(show_dir, new_dir)
                    logger.info("Merged duplicate: %s → %s (%d items)", title, canonical, count)
                else:
                    show_dir.rename(new_dir)
                    logger.info("Renamed folder: %s → %s", title, canonical)
                show_dir = new_dir
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

        # Process episodes
        total_renamed = 0
        video_files = sorted(
            f for f in show_dir.iterdir()
            if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        )

        if video_files:
            api_episodes: dict[tuple[int, int], str] = {}
            for season in show_data.get("seasons", []):
                s_num = season.get("season_number", 0)
                if s_num == 0:
                    continue
                try:
                    s_detail = self._tmdb.get_tv_season(tmdb_id, s_num)
                    for ep in s_detail.get("episodes", []):
                        e_num = ep.get("episode_number", 0)
                        api_episodes[(s_num, e_num)] = ep.get("name", f"Episode {e_num}")
                except Exception as e:
                    logger.warning("Failed to get season %d: %s", s_num, e)

            if api_episodes:
                ep_list = [{"season_number": s, "episode_number": e} for s, e in api_episodes]
                create_season_dirs(show_dir, ep_list, self.patterns, self.dry_run)
                matched = match_episode_files(video_files, api_episodes)
                if matched:
                    total_renamed = rename_episodes(matched, show_dir, self.patterns, self.dry_run)
                    self._generate_episode_nfos(matched, show_dir, show_data)

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

            season_dir_name = self.patterns.format("season_dir", Season=season)
            new_stem = self.patterns.format(
                "episode_video",
                Season=season, Episode=episode, EpisodeTitle=api_title,
            )
            nfo_path = show_dir / season_dir_name / f"{new_stem}.nfo"

            if nfo_path.exists():
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
                logger.warning("Episode NFO failed for S%02dE%02d: %s", season, episode, e)

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

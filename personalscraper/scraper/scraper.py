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
from personalscraper.scraper.confidence import (
    MatchResult,
    match_movie,
)
from personalscraper.scraper.mediainfo import extract_stream_info
from personalscraper.scraper.nfo_generator import NFOGenerator
from personalscraper.scraper.tmdb_client import TMDBClient
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)

# Regex for parsing "Title (Year)" folder names
_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")


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
    """

    media_path: Path
    media_type: str
    match: MatchResult | None = None
    nfo_written: bool = False
    artwork_downloaded: list[str] = field(default_factory=list)
    episodes_renamed: int = 0
    action: str = "error"
    error: str | None = None


def _parse_folder_name(name: str) -> tuple[str, int | None]:
    """Parse a media folder name into title and year.

    Handles "Title (Year)" format used by the pipeline.
    Falls back to using the full name as title with no year.

    Args:
        name: Folder name (e.g. "The Matrix (1999)").

    Returns:
        Tuple of (title, year). Year is None if not found.
    """
    m = _FOLDER_PATTERN.match(name)
    if m:
        return m.group(1).strip(), int(m.group(2))
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

        # Initialize API clients
        self._tmdb = TMDBClient(api_key=settings.tmdb_api_key)

        # Initialize helpers
        self._nfo = NFOGenerator()
        self._artwork = ArtworkDownloader(dry_run=dry_run)

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

        if match is None:
            result.action = "skipped_low_confidence"
            logger.info("No confident match for: %s", title)
            return result

        result.match = match
        logger.info(
            "Matched: %s → %s (%s, confidence=%.2f)",
            title, match.api_title, match.source, match.confidence,
        )

        # Get full movie details
        try:
            movie_data = self._tmdb.get_movie(match.api_id)
        except Exception as e:
            result.error = f"Get details failed: {e}"
            logger.error("Failed to get movie details for %s: %s", match.api_title, e)
            return result

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

        result.action = "scraped"
        return result

    def process_movies(self, movies_dir: Path) -> list[ScrapeResult]:
        """Scrape all movies in a directory.

        Scans all subdirectories of movies_dir and calls scrape_movie()
        on each one.

        Args:
            movies_dir: Path to the movies directory (e.g. 001-MOVIES/).

        Returns:
            List of ScrapeResult for each processed movie.
        """
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
            try:
                result = self.scrape_movie(movie_dir)
                results.append(result)
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

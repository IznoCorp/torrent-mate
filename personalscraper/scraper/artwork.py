"""Artwork downloader for movie and TV show images.

Downloads poster and landscape images from TMDB. Uses language-priority
selection (fr > en > null) and tenacity retry for reliability.

Only poster + landscape are downloaded automatically for movies. TV shows
also get season posters. Other artwork types (fanart, clearlogo, etc.)
are defined in NamingPatterns for compatibility with manually added files
but are NOT downloaded by this module.

Mapping notes (from docs/TVDB-API.md):
- TMDB: posters[] → poster, backdrops[] → landscape
- TVDB: type 2 = Poster, type 3 = Background (≈landscape), type 7 = Season poster
- TVDB has no "landscape" type — Background is the closest equivalent
"""

import logging
from pathlib import Path

import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_fixed,
)

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.http_retry import make_retryable_predicate

logger = logging.getLogger(__name__)

# TMDB image base URL (HTTPS)
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
IMAGE_SIZE = "original"

# Default language priority for image selection (lower = better)
_DEFAULT_LANG_PRIORITY: dict[str | None, int] = {"en": 0, "fr": 1}


_is_retryable = make_retryable_predicate()


def build_lang_priority(preferred: str = "en") -> dict[str | None, int]:
    """Build a language priority map with the preferred language first.

    Args:
        preferred: ISO 639-1 code for the preferred artwork language.

    Returns:
        Dict mapping language codes to priority (0 = best).
    """
    if preferred == "en":
        return {"en": 0, "fr": 1}
    return {preferred: 0, "en": 1}


def select_best_image(
    images: list[dict],
    lang_priority: dict[str | None, int] | None = None,
) -> str | None:
    """Select the best image by language priority then vote average.

    Priority order (default, artwork_language="en"):
    1. English (iso_639_1 == "en")
    2. French (iso_639_1 == "fr")
    3. Neutral/no language (iso_639_1 is None) — textless images
    4. Within same priority level, highest vote_average wins

    Args:
        images: List of image dicts from TMDB API (with iso_639_1,
            vote_average, file_path keys).
        lang_priority: Language priority map. If None, uses default.

    Returns:
        Relative image path (file_path), or None if no images.
    """
    if not images:
        return None

    priority_map = lang_priority or _DEFAULT_LANG_PRIORITY

    def sort_key(img: dict) -> tuple:
        lang: str | None = img.get("iso_639_1")
        priority = priority_map.get(lang, 2)
        vote = img.get("vote_average", 0.0)
        return (priority, -vote)

    sorted_images = sorted(images, key=sort_key)
    return sorted_images[0].get("file_path")


class ArtworkDownloader:
    """Download artwork images from TMDB.

    Downloads images with 30s timeout, retries twice on connection/server
    errors, and validates that downloaded files are non-empty. Existing
    files are skipped (no re-download).

    Attributes:
        dry_run: If True, log planned downloads without writing files.
    """

    def __init__(self, dry_run: bool = False, artwork_language: str = "en"):
        """Initialize the artwork downloader.

        Args:
            dry_run: If True, only log what would be downloaded.
            artwork_language: Preferred language for artwork selection (ISO 639-1).
        """
        self.dry_run = dry_run
        self._lang_priority = build_lang_priority(artwork_language)
        self._session = requests.Session()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception(_is_retryable),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def download_image(self, url: str, dest: Path) -> bool:
        """Download a single image to the destination path.

        Skips if the destination file already exists. In dry_run mode,
        logs the planned download without writing the file.

        Args:
            url: Full URL to the image.
            dest: Destination file path.

        Returns:
            True if downloaded successfully, False if skipped.

        Raises:
            requests.exceptions.HTTPError: On non-retryable HTTP errors (4xx).
            requests.exceptions.ConnectionError: After retry exhaustion.
        """
        if dest.exists():
            logger.info("Artwork already exists, skipping: %s", dest.name)
            return False

        if self.dry_run:
            logger.info("[DRY RUN] Would download %s → %s", url, dest.name)
            return False

        response = self._session.get(url, timeout=30)
        response.raise_for_status()

        if len(response.content) == 0:
            logger.warning("Downloaded empty file from %s, skipping", url)
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        logger.info("Downloaded artwork: %s (%d bytes)", dest.name, len(response.content))
        return True

    def download_movie_artwork(
        self, movie_data: dict, movie_dir: Path, patterns: NamingPatterns,
    ) -> list[Path]:
        """Download poster + landscape for a movie.

        Selects the best poster and landscape/backdrop images using
        language priority (fr > en > null), then downloads them using
        the naming patterns for filenames.

        Args:
            movie_data: TMDB movie details dict (from get_movie()).
            movie_dir: Path to the movie directory.
            patterns: Naming patterns for file names.

        Returns:
            List of paths to successfully downloaded files.
        """
        downloaded: list[Path] = []
        images = movie_data.get("images", {})
        title = movie_data.get("title", "")

        # Poster
        poster_path = select_best_image(images.get("posters", []), self._lang_priority)
        if poster_path:
            poster_name = patterns.format("movie_poster", Title=title)
            dest = movie_dir / poster_name
            url = f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{poster_path}"
            try:
                if self.download_image(url, dest):
                    downloaded.append(dest)
            except requests.exceptions.RequestException:
                logger.warning("Failed to download movie poster: %s", poster_name)

        # Landscape (from backdrops)
        landscape_path = select_best_image(images.get("backdrops", []), self._lang_priority)
        if landscape_path:
            landscape_name = patterns.format("movie_landscape", Title=title)
            dest = movie_dir / landscape_name
            url = f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{landscape_path}"
            try:
                if self.download_image(url, dest):
                    downloaded.append(dest)
            except requests.exceptions.RequestException:
                logger.warning("Failed to download movie landscape: %s", landscape_name)

        return downloaded

    def download_tvshow_artwork(
        self, show_data: dict, show_dir: Path, patterns: NamingPatterns,
    ) -> list[Path]:
        """Download poster + landscape + season posters for a TV show.

        Show-level images use fixed filenames (poster.jpg, landscape.jpg).
        Season posters use season{NN}-poster.jpg from NamingPatterns.
        Season poster paths come from the seasons[] array in the TMDB
        get_tv() response (one poster per season).

        Args:
            show_data: TMDB TV show details dict (from get_tv()).
            show_dir: Path to the TV show directory.
            patterns: Naming patterns for file names.

        Returns:
            List of paths to successfully downloaded files.
        """
        downloaded: list[Path] = []
        images = show_data.get("images", {})

        # Show poster (fixed name: poster.jpg)
        poster_path = select_best_image(images.get("posters", []), self._lang_priority)
        if poster_path:
            dest = show_dir / patterns.tvshow_poster
            url = f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{poster_path}"
            try:
                if self.download_image(url, dest):
                    downloaded.append(dest)
            except requests.exceptions.RequestException:
                logger.warning("Failed to download show poster")

        # Show landscape (fixed name: landscape.jpg)
        landscape_path = select_best_image(images.get("backdrops", []), self._lang_priority)
        if landscape_path:
            dest = show_dir / patterns.tvshow_landscape
            url = f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{landscape_path}"
            try:
                if self.download_image(url, dest):
                    downloaded.append(dest)
            except requests.exceptions.RequestException:
                logger.warning("Failed to download show landscape")

        # Season posters (only for seasons that exist on disk)
        for season in show_data.get("seasons", []):
            season_num = season.get("season_number", 0)
            # Skip specials (season 0)
            if season_num == 0:
                continue
            # Only download poster if Saison XX/ directory exists
            season_dir_name = patterns.format("season_dir", Season=season_num)
            if not (show_dir / season_dir_name).is_dir():
                continue
            season_poster = season.get("poster_path", "")
            if season_poster:
                poster_name = patterns.format("season_poster", Season=season_num)
                dest = show_dir / poster_name
                url = f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{season_poster}"
                try:
                    if self.download_image(url, dest):
                        downloaded.append(dest)
                except requests.exceptions.RequestException:
                    logger.warning(
                        "Failed to download season %d poster", season_num,
                    )

        return downloaded

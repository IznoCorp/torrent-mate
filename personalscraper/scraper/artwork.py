"""Artwork downloader for movie and TV show images.

Downloads poster and landscape images from TMDB. Uses configurable
language-priority selection (default en > fr > null) and tenacity retry.

Only poster + landscape are downloaded automatically for movies. TV shows
also get season posters. Other artwork types (fanart, clearlogo, etc.)
are defined in NamingPatterns for compatibility with manually added files
but are NOT downloaded by this module.

Mapping notes (from docs/TVDB-API.md):
- TMDB: posters[] → poster, backdrops[] → landscape
- TVDB: type 2 = Poster, type 3 = Background (≈landscape), type 7 = Season poster
- TVDB has no "landscape" type — Background is the closest equivalent
"""

from pathlib import Path
from typing import Any

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_fixed,
)

from personalscraper.core.http_helpers import build_retry_logger, make_retryable_predicate
from personalscraper.indexer.outbox._disk import disk_id_for_path
from personalscraper.indexer.outbox._publish import publish_event
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns

log = get_logger("artwork")

# TMDB image base URL (HTTPS)
IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
IMAGE_SIZE = "original"

# Default language priority for image selection (lower = better)
_DEFAULT_LANG_PRIORITY: dict[str | None, int] = {"en": 0, "fr": 1}

# Stem substrings → outbox artwork ``kind`` value.
# Order matters: the first match in iteration wins, so put the more specific
# tokens first (``clearlogo``/``clearart`` before ``logo``/``art``, etc.).
# Kinds must remain a subset of
# :data:`personalscraper.indexer.outbox._ALLOWED_ARTWORK_KINDS`; stems that
# match no entry skip the outbox publish entirely (best-effort contract).
_KIND_BY_STEM_TOKEN: tuple[tuple[str, str], ...] = (
    ("poster", "poster"),
    ("landscape", "landscape"),
    ("fanart", "fanart"),
    ("backdrop", "fanart"),
    ("banner", "banner"),
    ("clearlogo", "clearlogo"),
    ("clearart", "clearart"),
    ("discart", "discart"),
    ("characterart", "characterart"),
)


def _kind_from_stem(stem: str) -> str | None:
    """Resolve the outbox ``kind`` for an artwork file by stem.

    Args:
        stem: Filename stem (lower-cased), e.g. ``"poster"`` or
            ``"my-movie-fanart"``.

    Returns:
        A whitelisted ``kind`` value (subset of
        :data:`~personalscraper.indexer.outbox._ALLOWED_ARTWORK_KINDS`)
        when the stem contains a known token, otherwise ``None`` so the
        caller can skip the outbox publish.
    """
    lowered = stem.lower()
    for token, kind in _KIND_BY_STEM_TOKEN:
        if token in lowered:
            return kind
    return None


_is_retryable = make_retryable_predicate()


def build_lang_priority(preferred: str = "en") -> dict[str | None, int]:
    """Build a language priority map with the preferred language first.

    English and French are always included as fallbacks (this project
    targets French media). Languages not in the map get priority 3
    (same as textless/null images).

    Args:
        preferred: ISO 639-1 code for the preferred artwork language.

    Returns:
        Dict mapping language codes to priority (0 = best).
    """
    if preferred == "en":
        return {"en": 0, "fr": 1}
    if preferred == "fr":
        return {"fr": 0, "en": 1}
    return {preferred: 0, "en": 1, "fr": 2}


def select_best_image(
    images: list[dict[str, Any]],
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

    def sort_key(img: dict[str, Any]) -> tuple[int, float]:
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
        _db_path: Path to the indexer SQLite database used for best-effort
            outbox publish on :meth:`download_image`.  ``None`` disables publishing.
    """

    def __init__(self, dry_run: bool = False, artwork_language: str = "en", db_path: Path | None = None):
        """Initialize the artwork downloader.

        Args:
            dry_run: If True, only log what would be downloaded.
            artwork_language: Preferred language for artwork selection (ISO 639-1).
            db_path: Resolved ``Config.indexer.db_path`` passed through from
                the caller.  When ``None``, the write-through outbox publish
                in :meth:`download_image` is silently skipped (best-effort contract).
        """
        self.dry_run = dry_run
        self._lang_priority = build_lang_priority(artwork_language)
        self._session = requests.Session()
        self._db_path = db_path

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(2),
        retry=retry_if_exception(_is_retryable),
        before_sleep=build_retry_logger(log, "artwork_download_retry"),
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
            log.info("artwork_exists_skip", filename=dest.name)
            return False

        if self.dry_run:
            log.info("artwork_would_download", url=url, dest=dest.name)
            return False

        response = self._session.get(url, timeout=30)
        response.raise_for_status()

        if len(response.content) == 0:
            log.warning("artwork_empty_response", url=url)
            return False

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)

        # Best-effort outbox publish for the indexer (DESIGN §9.1).
        # Skipped when _db_path is None (no config available at construction time)
        # or when the stem does not map to a whitelisted artwork ``kind`` — the
        # outbox drainer would otherwise mark the row permanently failed
        # (DESIGN §9.6 producer guard, IMPLEMENTATION cycle 2).
        if self._db_path is not None:
            kind = _kind_from_stem(dest.stem)
            if kind is None:
                log.debug("artwork_outbox_skipped_unknown_kind", filename=dest.name, stem=dest.stem)
            else:
                resolved = disk_id_for_path(dest, self._db_path)
                if resolved is not None:
                    disk_id, rel_path = resolved
                    publish_event(
                        disk_id,
                        op="artwork_write",
                        payload={
                            "rel_path": rel_path,
                            "kind": kind,
                        },
                        db_path=self._db_path,
                        source="scraper",
                    )

        log.info("artwork_downloaded", filename=dest.name, bytes=len(response.content))
        return True

    def download_movie_artwork(
        self,
        movie_data: dict[str, Any],
        movie_dir: Path,
        patterns: NamingPatterns,
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
        posters_count = len(images.get("posters", []))
        poster_path = select_best_image(images.get("posters", []), self._lang_priority)
        if poster_path:
            poster_name = patterns.format("movie_poster", Title=title)
            dest = movie_dir / poster_name
            url = f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{poster_path}"
            try:
                if self.download_image(url, dest):
                    downloaded.append(dest)
            except requests.exceptions.RequestException:
                log.warning("artwork_movie_poster_failed", filename=poster_name)
        else:
            # Surface gaps in upstream metadata (TMDB returned 0 posters for
            # this movie). Without this log a missing poster.jpg looks like
            # a local code failure when it is really an upstream data gap.
            log.warning("artwork_movie_poster_missing_source", title=title, source="tmdb", candidates=posters_count)

        # Landscape (from backdrops). TMDB exposes the show-/movie-level
        # backdrop both as ``backdrop_path`` on the main detail payload and
        # as a list under ``images.backdrops``; fall back to the former when
        # the list is empty so a single backdrop still produces a landscape.
        backdrops = images.get("backdrops", [])
        backdrops_count = len(backdrops)
        landscape_path = select_best_image(backdrops, self._lang_priority)
        if not landscape_path:
            fallback_backdrop = movie_data.get("backdrop_path")
            if fallback_backdrop:
                landscape_path = fallback_backdrop
                log.info(
                    "artwork_movie_landscape_fallback",
                    title=title,
                    source="tmdb_main_detail_backdrop_path",
                )
        if landscape_path:
            landscape_name = patterns.format("movie_landscape", Title=title)
            dest = movie_dir / landscape_name
            url = f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{landscape_path}"
            try:
                if self.download_image(url, dest):
                    downloaded.append(dest)
            except requests.exceptions.RequestException:
                log.warning("artwork_movie_landscape_failed", filename=landscape_name)
        else:
            # Surface upstream metadata gaps so the operator can distinguish
            # "TMDB has no backdrop" (this log) from "downloader failed"
            # (artwork_movie_landscape_failed log above).
            log.warning(
                "artwork_movie_landscape_missing_source",
                title=title,
                source="tmdb",
                candidates=backdrops_count,
            )

        return downloaded

    def download_tvshow_artwork(
        self,
        show_data: dict[str, Any],
        show_dir: Path,
        patterns: NamingPatterns,
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
            # TVDB images arrive as absolute URLs; TMDB paths need the CDN prefix.
            url = poster_path if poster_path.startswith("http") else f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{poster_path}"
            try:
                if self.download_image(url, dest):
                    downloaded.append(dest)
            except requests.exceptions.RequestException:
                log.warning("artwork_show_poster_failed")

        # Show landscape (fixed name: landscape.jpg)
        landscape_path = select_best_image(images.get("backdrops", []), self._lang_priority)
        if landscape_path:
            dest = show_dir / patterns.tvshow_landscape
            # TVDB images arrive as absolute URLs; TMDB paths need the CDN prefix.
            url = (
                landscape_path
                if landscape_path.startswith("http")
                else f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{landscape_path}"
            )
            try:
                if self.download_image(url, dest):
                    downloaded.append(dest)
            except requests.exceptions.RequestException:
                log.warning("artwork_show_landscape_failed")

        handled_seasons: set[int] = set()
        disk_seasons = {
            int(path.name.split()[-1])
            for path in show_dir.iterdir()
            if path.is_dir() and path.name.startswith("Saison ") and path.name.split()[-1].isdigit()
        }

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
            handled_seasons.add(season_num)
            season_poster = season.get("poster_path", "") or poster_path
            if season_poster:
                poster_name = patterns.format("season_poster", Season=season_num)
                dest = show_dir / poster_name
                url = (
                    season_poster
                    if season_poster.startswith("http")
                    else f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{season_poster}"
                )
                try:
                    if self.download_image(url, dest):
                        downloaded.append(dest)
                except requests.exceptions.RequestException:
                    log.warning("artwork_season_poster_failed", season=season_num)

        for season_num in sorted(disk_seasons - handled_seasons):
            if not poster_path:
                continue
            poster_name = patterns.format("season_poster", Season=season_num)
            dest = show_dir / poster_name
            url = poster_path if poster_path.startswith("http") else f"{IMAGE_BASE_URL}/{IMAGE_SIZE}{poster_path}"
            try:
                if self.download_image(url, dest):
                    downloaded.append(dest)
            except requests.exceptions.RequestException:
                log.warning("artwork_season_poster_failed", season=season_num)

        return downloaded

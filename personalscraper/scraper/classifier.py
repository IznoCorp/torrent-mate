"""Extracted scraper service module."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from guessit.api import GuessitException

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.conf.models.config import Config
    from personalscraper.scraper.keywords_cache import KeywordsCache

log = get_logger("scraper")

_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2} - .+\.\w+$")
_EPISODE_FALLBACK_RE = re.compile(r"^S\d{2}E0*(\d+) - Episode 0*\1\.\w+$", re.IGNORECASE)


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


class ClassifierMixin:
    """Classification and title helper methods for Scraper."""

    config: "Config | None"
    _needs_keywords: bool
    _keywords_cache: "KeywordsCache | None"
    _prefer_local_title: bool
    _tmdb: "TMDBClient"

    def _classify_item(
        self,
        media_type: Literal["movie", "tv"],
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
            cached = self._keywords_cache.get(tmdb_id, media_type)
            if cached is None:
                fetched = self._tmdb.get_keywords(str(tmdb_id), media_type)
                self._keywords_cache.set(tmdb_id, media_type, fetched)
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

        from personalscraper.scraper import scraper as scraper_api  # noqa: PLC0415

        category_id, reason = scraper_api._classifier.classify(
            self.config,
            media_type=media_type,
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

        When config.scraper.prefer_local_title is True and the API data
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
        if not self._prefer_local_title:
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

"""TMDB-first / YouTube-fallback trailer discovery orchestrator.

Implements a two-tier strategy (DESIGN §4):
  1. Try TMDB video endpoints per language (fr-FR before en-US, etc.).
  2. Fall back to ``YoutubeSearch`` when TMDB returns no usable videos.

Results are cached via ``TrailersCache`` (backed by ``JsonTTLCache``)
so repeated calls for the same media are answered from disk.

No downloading happens here — this module returns a YouTube URL string
or ``None``.

Cache-poisoning protection (C5/C6):
- ``_fetch_tmdb_videos`` now calls ``_fetch_videos_strict`` on the TMDB client,
  which raises on transport/circuit-open/JSON errors.  ``find()`` catches those
  exceptions and skips the cache write so a 30-second TMDB blip does not pin an
  empty result for 7 days.
- ``_youtube_fallback`` re-raises transport / breaker-open / yt-dlp parser errors
  so ``find()`` can skip caching the ``__no_result__`` sentinel on outage.  Only a
  successful query with genuinely no results is cached as ``__no_result__``.
- ``TrailersCache.contains_search`` (TTL-aware) is used instead of the old
  ``has_cached_search`` (which bypassed TTL), so an expired entry is treated as a
  cache miss and triggers a fresh YouTube search.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import requests

from personalscraper.logger import get_logger
from personalscraper.scraper.circuit_breaker import CircuitOpenError
from personalscraper.scraper.tmdb_client import TMDBError
from personalscraper.scraper.trailers_cache import TrailersCache

if TYPE_CHECKING:
    from personalscraper.scraper.tmdb_client import TMDBClient, Video
    from personalscraper.scraper.youtube_search import YoutubeSearch

logger = get_logger(__name__)

# YouTube watch URL template — only valid for ``site == "YouTube"`` entries.
_YT_WATCH_URL = "https://www.youtube.com/watch?v={key}"

# Default season-level YouTube query format. French: matches the project's
# primary library language. Callers can override via TrailerFinder.find when a
# different season-aware template is needed.
_DEFAULT_SEASON_QUERY_FORMAT = "{title} {year} saison {season} bande annonce"


def _best_video(videos: list[Video]) -> Video | None:
    """Select the best YouTube video from a TMDB video list.

    Non-YouTube entries are dropped first (TMDB /videos includes Vimeo and
    DailyMotion entries; a ``watch?v=`` URL only makes sense for YouTube).
    Within the YouTube subset the preference order is:

      1. Official Trailer
      2. Any Trailer
      3. Official Teaser
      4. Any Teaser
      5. Any remaining YouTube video

    Args:
        videos: Raw list of Video instances from TMDB (may include non-YouTube).

    Returns:
        The best matching Video instance, or None when no YouTube video exists.
    """
    youtube_only = [v for v in videos if v.site == "YouTube"]
    if not youtube_only:
        return None

    # Preference passes — return on first non-empty result.
    for predicate in (
        lambda v: v.type == "Trailer" and v.official,
        lambda v: v.type == "Trailer",
        lambda v: v.type == "Teaser" and v.official,
        lambda v: v.type == "Teaser",
        lambda v: True,  # any YouTube video
    ):
        matches = [v for v in youtube_only if predicate(v)]
        if matches:
            return matches[0]

    return None  # unreachable given the `any` pass, but satisfies mypy


def _video_to_url(video: Video) -> str:
    """Build a YouTube watch URL from a Video entry.

    Args:
        video: TMDB Video dataclass instance (``site`` must be ``"YouTube"``).

    Returns:
        Full ``https://www.youtube.com/watch?v=<key>`` URL string.
    """
    return _YT_WATCH_URL.format(key=video.key)


class TrailerFinder:
    """Orchestrates TMDB-first / YouTube-fallback trailer discovery.

    For each configured language the finder queries the TMDB video endpoint
    (cache-first), picks the best YouTube-hosted video, and returns early on
    the first hit. If TMDB yields nothing, it falls back to ``YoutubeSearch``
    and caches the result.

    Supports season-level discovery: when ``season_number`` is provided to
    ``find()``, the TMDB season-specific endpoint is used instead of the
    show-level one, and the YouTube fallback query uses the season format.

    Attributes:
        _tmdb_client: TMDBClient instance for TMDB API calls.
        _youtube_search: YoutubeSearch instance for fallback queries.
        _cache: TrailersCache for TMDB video lists and YouTube results.
        _languages: Ordered list of BCP-47 language tags (tried in order).
    """

    def __init__(
        self,
        tmdb_client: TMDBClient,
        youtube_search: YoutubeSearch,
        cache: TrailersCache,
        languages: list[str],
    ) -> None:
        """Initialize TrailerFinder with its dependencies.

        Args:
            tmdb_client: Authenticated TMDB API client.
            youtube_search: YouTube search layer (primary API + yt-dlp fallback).
            cache: File-backed cache for TMDB video lists and search results.
            languages: Ordered list of BCP-47 language tags to query TMDB with.
                       Queried in order; the first language that returns a
                       usable video wins.
        """
        self._tmdb_client = tmdb_client
        self._youtube_search = youtube_search
        self._cache = cache
        self._languages = languages

    def find(
        self,
        tmdb_id: int,
        media_type: str,
        *,
        title: str,
        year: int | None,
        season_number: int | None = None,
    ) -> str | None:
        """Discover the best YouTube trailer URL for the given media.

        Strategy (DESIGN §4):
          1. For each language in ``self._languages``:
             a. Check ``TrailersCache`` for a cached TMDB video list.
             b. On miss, call the appropriate TMDBClient strict fetch method.
                Store the result only when no transport/circuit error occurred.
             c. Run ``_best_video()`` on the (cached) list.
             d. Return immediately on the first hit.
          2. If TMDB yields nothing across all languages:
             a. Check ``TrailersCache`` for a cached YouTube search result
                (TTL-aware via ``contains_search``).
             b. On miss, call ``_youtube_fallback_strict()`` and cache the result
                (including a no-result sentinel so we don't re-query soon).
                On transport/breaker-open/parser error, skip cache write and
                fall through to return None.
             c. Return the URL or None.

        Season-level behaviour (``season_number is not None``):
          - Uses ``fetch_tv_season_videos`` instead of ``fetch_tv_videos``.
          - TMDB cache keys include the season number automatically via the
            ``media_type`` suffix written by ``_tmdb_season_media_type()``.
          - YouTube fallback uses a season-specific query format.

        Args:
            tmdb_id: TMDB numeric identifier for the movie or TV show.
            media_type: ``"movie"`` or ``"tv"``.
            title: Human-readable title (used for YouTube fallback query).
            year: Release year, or None.  Used in YouTube fallback query.
            season_number: When provided, targets season-specific TMDB videos
                           and a season-aware YouTube query.

        Returns:
            A ``https://www.youtube.com/watch?v=<id>`` URL, or ``None`` when
            no trailer could be found via either tier.
        """
        # ------------------------------------------------------------------
        # Tier 1: TMDB video lookup (per language, cache-first)
        # ------------------------------------------------------------------
        # The cache key for seasons uses a synthetic media_type like
        # "tv-season-3" so season-level results don't collide with show-level.
        cache_media_type = self._cache_media_type(media_type, season_number)

        for language in self._languages:
            cached = self._cache.get_tmdb_videos(tmdb_id, cache_media_type, language)
            if cached is None:
                # Cache miss — fetch from TMDB via the strict variant so we can
                # distinguish a genuine empty result from an outage error.
                try:
                    videos = self._fetch_tmdb_videos(tmdb_id, media_type, language, season_number)
                except (TMDBError, CircuitOpenError, requests.RequestException, json.JSONDecodeError) as exc:
                    # TMDB outage / circuit open / decode error — do NOT cache
                    # the empty list.  Log and fall through to YouTube fallback.
                    logger.warning(
                        "trailer_tmdb_fetch_error_skip_cache",
                        tmdb_id=tmdb_id,
                        media_type=cache_media_type,
                        language=language,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                    continue
                # Genuine result (empty or not) — safe to cache.
                self._cache.set_tmdb_videos(tmdb_id, cache_media_type, language, videos)
                cached = videos

            best = _best_video(cached)
            if best is not None:
                url = _video_to_url(best)
                logger.info(
                    "trailer_found_tmdb",
                    tmdb_id=tmdb_id,
                    media_type=cache_media_type,
                    language=language,
                    video_type=best.type,
                    url=url,
                )
                return url

        # ------------------------------------------------------------------
        # Tier 2: YouTube search fallback
        # ------------------------------------------------------------------
        # Use TTL-aware contains_search so expired entries are treated as misses
        # (the old has_cached_search bypassed TTL by reading _load() directly).
        if self._cache.contains_search(title, year):
            cached_yt = self._cache.get_youtube_search(title, year)
            # Sentinel "__no_result__" means we already searched and found nothing.
            if cached_yt == "__no_result__" or cached_yt is None:
                logger.info(
                    "trailer_cache_no_result",
                    title=title,
                    year=year,
                )
                return None
            return cached_yt

        # Build the search query; use season-specific format when applicable.
        try:
            yt_url = self._youtube_fallback_strict(title, year, season_number)
        except (CircuitOpenError, requests.RequestException, KeyError, AttributeError) as exc:
            # Transport error / breaker-open / yt-dlp parser bug — do NOT cache
            # the __no_result__ sentinel so we retry on the next run.
            logger.warning(
                "trailer_youtube_fallback_error_skip_cache",
                title=title,
                year=year,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None

        # Cache the outcome: real URL or __no_result__ sentinel.
        self._cache.set_youtube_search(title, year, yt_url)

        if yt_url is not None:
            logger.info(
                "trailer_found_youtube",
                title=title,
                year=year,
                url=yt_url,
            )
        else:
            logger.info(
                "trailer_not_found",
                title=title,
                year=year,
            )

        return yt_url

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _fetch_tmdb_videos(
        self,
        tmdb_id: int,
        media_type: str,
        language: str,
        season_number: int | None,
    ) -> list[Video]:
        """Dispatch to the correct TMDBClient strict fetch method.

        Calls ``_fetch_videos_strict`` indirectly via the per-type public
        wrappers re-routed through the strict path so the caller (``find()``)
        receives transport / circuit-open / JSON errors instead of a silent
        empty list.

        Args:
            tmdb_id: TMDB ID.
            media_type: ``"movie"`` or ``"tv"``.
            language: BCP-47 language tag.
            season_number: Season number, or None for show-level.

        Returns:
            List of Video instances (may be empty for a genuine no-result).

        Raises:
            TMDBError: On non-404 TMDB HTTP errors.
            CircuitOpenError: If the TMDB circuit breaker is OPEN.
            requests.RequestException: On transport / connection errors.
            json.JSONDecodeError: If the response body is not valid JSON.
        """
        endpoint: str
        if media_type == "movie":
            endpoint = f"/movie/{tmdb_id}/videos"
            return self._tmdb_client._fetch_videos_strict(endpoint, tmdb_id, "movie", language)
        if season_number is not None:
            endpoint = f"/tv/{tmdb_id}/season/{season_number}/videos"
            return self._tmdb_client._fetch_videos_strict(endpoint, tmdb_id, f"tv-season-{season_number}", language)
        endpoint = f"/tv/{tmdb_id}/videos"
        return self._tmdb_client._fetch_videos_strict(endpoint, tmdb_id, "tv", language)

    def _youtube_fallback_strict(
        self,
        title: str,
        year: int | None,
        season_number: int | None,
    ) -> str | None:
        """Build the YouTube query, call YoutubeSearch, and propagate errors.

        Unlike ``YoutubeSearch.search()`` (which is fail-soft), this method
        re-raises transport errors, breaker-open signals, and ``KeyError`` /
        ``AttributeError`` from yt-dlp parser bugs so ``find()`` can skip
        caching the ``__no_result__`` sentinel on outage.

        Only a successful call whose search returned zero results returns
        ``None`` — that is the only case that should be cached as
        ``__no_result__``.

        Args:
            title: Media title.
            year: Release year, or None.
            season_number: Season number for season-specific query, or None.

        Returns:
            YouTube URL string, or ``None`` when the search genuinely returned
            no results.

        Raises:
            CircuitOpenError: When the YouTube circuit breaker is OPEN.
            requests.RequestException: On network transport errors.
            KeyError: On yt-dlp parser schema drift (missing expected fields).
            AttributeError: On yt-dlp parser schema drift (unexpected None).
        """
        if season_number is not None:
            year_str = str(year) if year else ""
            query_text = _DEFAULT_SEASON_QUERY_FORMAT.format(
                title=title,
                year=year_str,
                season=season_number,
            )
            # Create a one-shot searcher with a passthrough format so the
            # pre-formatted season query is used verbatim.
            from personalscraper.scraper.youtube_search import YoutubeSearch  # noqa: PLC0415

            passthrough_searcher = YoutubeSearch(
                "{title}",
                api_key=self._youtube_search._api_key,
                quota_cache=self._youtube_search._quota,
                breaker=self._youtube_search._breaker,
                daily_quota_units=self._youtube_search._daily_quota_units,
                search_list_cost_units=self._youtube_search._search_list_cost_units,
            )
            return self._call_youtube_search(passthrough_searcher, query_text, None)

        return self._call_youtube_search(self._youtube_search, title, year)

    def _call_youtube_search(
        self,
        searcher: YoutubeSearch,
        title: str,
        year: int | None,
    ) -> str | None:
        """Call ``searcher.search()`` and re-raise transient errors.

        ``YoutubeSearch.search()`` is fail-soft (never raises).  This thin
        wrapper detects the breaker-open condition before the call and
        re-raises ``CircuitOpenError`` so ``find()`` can skip caching.

        Transport errors that caused the breaker to open on a previous call are
        surfaced on the *next* call when ``can_proceed()`` returns False.  There
        is no way to distinguish "breaker just opened during this call" from a
        genuine empty result inside ``search()`` without modifying YoutubeSearch
        itself.  The conservative policy is:

        - If the breaker is OPEN before the call → raise ``CircuitOpenError``
          (cache-poisoning prevention).
        - Otherwise, call ``search()`` normally; a ``None`` return is treated
          as "no results" and cached accordingly.

        Args:
            searcher: ``YoutubeSearch`` instance to call.
            title: Media title for the query.
            year: Release year or None.

        Returns:
            YouTube URL string, or ``None`` when the search returned no results.

        Raises:
            CircuitOpenError: When the YouTube circuit breaker is OPEN before
                the search call.
        """
        # guard() raises CircuitOpenError(provider, remaining_seconds) when OPEN.
        searcher._breaker.guard()
        return searcher.search(title, year)

    @staticmethod
    def _cache_media_type(media_type: str, season_number: int | None) -> str:
        """Build the cache media_type key, including season suffix when needed.

        Args:
            media_type: ``"movie"`` or ``"tv"``.
            season_number: Season number, or None.

        Returns:
            ``"movie"``, ``"tv"``, or ``"tv-season-{n}"``.
        """
        if season_number is not None and media_type == "tv":
            return f"tv-season-{season_number}"
        return media_type

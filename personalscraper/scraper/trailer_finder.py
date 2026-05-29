"""Provider-agnostic / YouTube-fallback trailer discovery orchestrator.

Implements a two-tier strategy (DESIGN §4):
  1. Try the configured VideoProvider via ``registry.locked(VideoProvider, match)``
     for each language (fr-FR before en-US, etc.).
  2. Fall back to ``YoutubeSearch`` when the provider returns no usable videos.

Results are cached via ``TrailersCache`` (backed by ``JsonTTLCache``)
so repeated calls for the same media are answered from disk.

No downloading happens here — this module returns a YouTube URL string
or ``None``.

Cache-poisoning protection (C5/C6):
- ``_fetch_videos_via_registry`` uses ``registry.locked(VideoProvider, match)``
  to obtain a provider.  The provider's ``get_videos()`` is used for the
  Protocol path; for TV seasons the TMDB-specific ``_fetch_videos_strict`` is
  accessed via duck-typing as a transitional measure (no season support in the
  VideoProvider Protocol).
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
import yt_dlp.utils

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.logger import get_logger
from personalscraper.scraper.trailers_cache import TrailersCache

if TYPE_CHECKING:
    from personalscraper.api.metadata._base import Video
    from personalscraper.api.metadata.registry import ProviderRegistry  # noqa: F811
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
    youtube_only = [v for v in videos if v.site == "youtube"]
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
    """Orchestrates provider-agnostic / YouTube-fallback trailer discovery.

    For each configured language the finder queries the VideoProvider via
    ``registry.locked(VideoProvider, match)`` (cache-first), picks the best
    YouTube-hosted video, and returns early on the first hit. If the provider
    yields nothing, it falls back to ``YoutubeSearch`` and caches the result.

    Supports season-level discovery: when ``season_number`` is provided to
    ``find()``, the TMDB season-specific endpoint is used instead of the
    show-level one (via duck-typing on the locked provider, since the
    VideoProvider Protocol does not expose season-level lookups), and the
    YouTube fallback query uses the season format.

    Attributes:
        _registry: ProviderRegistry for resolving VideoProvider per match.
        _youtube_search: YoutubeSearch instance for fallback queries.
        _cache: TrailersCache for video lists and YouTube results.
        _languages: Ordered list of BCP-47 language tags (tried in order).
    """

    def __init__(
        self,
        registry: "ProviderRegistry",  # noqa: F821
        youtube_search: YoutubeSearch,
        cache: TrailersCache,
        languages: list[str],
    ) -> None:
        """Initialize TrailerFinder with its dependencies.

        Args:
            registry: ProviderRegistry for resolving the VideoProvider
                      capability per match via ``registry.locked()``.
            youtube_search: YouTube search layer (primary API + yt-dlp fallback).
            cache: File-backed cache for video lists and search results.
            languages: Ordered list of BCP-47 language tags to query the
                       provider with.  Queried in order; the first language
                       that returns a usable video wins.
        """
        self._registry = registry
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
             a. Check ``TrailersCache`` for a cached video list.
             b. On miss, call ``_fetch_videos_via_registry()`` which resolves
                the VideoProvider via ``registry.locked(VideoProvider, match)``.
                Store the result only when no transport/circuit error occurred.
             c. Run ``_best_video()`` on the (cached) list.
             d. Return immediately on the first hit.
          2. If the provider yields nothing across all languages:
             a. Check ``TrailersCache`` for a cached YouTube search result
                (TTL-aware via ``contains_search``).
             b. On miss, call ``_youtube_fallback_strict()`` and cache the result
                (including a no-result sentinel so we don't re-query soon).
                On transport/breaker-open/parser error, skip cache write and
                fall through to return None.
             c. Return the URL or None.

        Season-level behaviour (``season_number is not None``):
          - Uses the TMDB season-specific endpoint via duck-typing on the locked
            provider (``_fetch_videos_strict``), since the VideoProvider Protocol
            does not expose season-level lookups.
          - Cache keys include the season number automatically via the
            ``media_type`` suffix written by ``_cache_media_type()``.
          - YouTube fallback uses a season-specific query format.

        Args:
            tmdb_id: TMDB numeric identifier for the movie or TV show.
            media_type: ``"movie"`` or ``"tv"``.
            title: Human-readable title (used for YouTube fallback query).
            year: Release year, or None.  Used in YouTube fallback query.
            season_number: When provided, targets season-specific videos
                           and a season-aware YouTube query.

        Returns:
            A ``https://www.youtube.com/watch?v=<id>`` URL, or ``None`` when
            no trailer could be found via either tier.
        """
        # ------------------------------------------------------------------
        # Tier 1: Provider video lookup (per language, cache-first)
        # ------------------------------------------------------------------
        # The cache key for seasons uses a synthetic media_type like
        # "tv-season-3" so season-level results don't collide with show-level.
        cache_media_type = self._cache_media_type(media_type, season_number)

        for language in self._languages:
            cached = self._cache.get_tmdb_videos(tmdb_id, cache_media_type, language)
            if cached is None:
                # Cache miss — fetch via registry.locked(VideoProvider, match)
                # so we can distinguish a genuine empty result from an outage error.
                try:
                    videos = self._fetch_videos_via_registry(
                        media_type=media_type,
                        tmdb_id=tmdb_id,
                        season_number=season_number,
                        language=language,
                    )
                except CircuitOpenError:
                    # Circuit breaker is OPEN — re-raise so the orchestrator can
                    # tally circuit_open and skip the cache write.  Swallowing it
                    # here would leave counts["circuit_open"] permanently at zero
                    # (dead observability counter).
                    raise
                except (ApiError, requests.RequestException, json.JSONDecodeError) as exc:
                    # Provider transport / HTTP / decode error — do NOT cache the
                    # empty list.  Log and continue to the next language or fall
                    # through to the YouTube fallback.
                    logger.warning(
                        "trailer_provider_fetch_error_skip_cache",
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
        except CircuitOpenError:
            # Circuit breaker is OPEN — re-raise so the orchestrator can tally
            # circuit_open.  The cache write below is skipped inherently because
            # the exception unwinds the stack before we reach it.
            raise
        except (
            requests.RequestException,
            KeyError,
            AttributeError,
            TypeError,
            yt_dlp.utils.DownloadError,  # re-raised by _fallback_search (sub-phase 11.2)
        ) as exc:
            # Transport error / yt-dlp parser bug / download error — do NOT cache
            # the __no_result__ sentinel so we retry on the next run.
            # DownloadError is re-raised by _fallback_search (sub-phase 11.2) and
            # propagates through _youtube_fallback_strict; without this catch it
            # would escape find() entirely and crash the orchestrator.
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

    def _fetch_videos_via_registry(
        self,
        *,
        media_type: str,
        tmdb_id: int,
        season_number: int | None,
        language: str,
    ) -> list[Video]:
        """Fetch videos via ``registry.locked(VideoProvider, match)``.

        The Protocol method ``get_videos(media_id, media_type, language)`` is
        provider-agnostic. For TV seasons the season_number is encoded in the
        endpoint by duck-typing ``_fetch_videos_strict`` on the locked provider
        (the VideoProvider Protocol does not expose season-level lookups).

        Args:
            media_type: ``"movie"`` or ``"tv"``.
            tmdb_id: TMDB numeric identifier.
            season_number: Season number, or None for show-level.
            language: BCP-47 language tag.

        Returns:
            List of Video instances (may be empty for a genuine no-result).

        Raises:
            ApiError: On non-404 provider HTTP errors.
            CircuitOpenError: If the provider circuit breaker is OPEN.
        """
        from personalscraper.api._contracts import MediaType
        from personalscraper.api.metadata._contracts import VideoProvider
        from personalscraper.api.metadata.registry import ProviderMatch, RegistryProviderName

        mt = MediaType(media_type)
        match = ProviderMatch(
            provider=RegistryProviderName("tmdb"),
            id=str(tmdb_id),
            media_type=mt,
        )
        locked = self._registry.locked(VideoProvider, match)  # type: ignore[type-abstract, type-var]
        if locked is None:
            logger.warning(
                "trailer_video_provider_unresolved",
                tmdb_id=tmdb_id,
                media_type=str(mt),
            )
            return []

        if season_number is not None:
            # TV season trailers — TMDB-specific endpoint not in Protocol.
            # Use duck-typing to call the private method on TMDB only.
            endpoint = f"/tv/{tmdb_id}/season/{season_number}/videos"
            fetch_strict = getattr(locked.provider, "_fetch_videos_strict", None)
            if fetch_strict is None:
                logger.info(
                    "trailer_season_videos_protocol_only",
                    tmdb_id=tmdb_id,
                    season=season_number,
                    provider=locked.bound_id,
                    note="provider lacks _fetch_videos_strict; falling back to root TV videos",
                )
                return locked.provider.get_videos(locked.bound_id, mt, language)
            return fetch_strict(endpoint, language)  # type: ignore[no-any-return]

        # Movies + main TV — provider-agnostic Protocol path
        return locked.provider.get_videos(locked.bound_id, mt, language)

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
            CircuitOpenError: When the YouTube circuit breaker is OPEN before
                the call, or when it transitions closed → open during this call
                (re-raised from ``_call_youtube_search``).
            KeyError: On yt-dlp parser schema drift — missing expected dict field
                (re-raised from ``_fallback_search`` via ``_call_youtube_search``).
            AttributeError: On yt-dlp parser schema drift — unexpected None value
                (re-raised from ``_fallback_search`` via ``_call_youtube_search``).
            TypeError: On yt-dlp parser schema drift — unexpected type in result
                (re-raised from ``_fallback_search`` via ``_call_youtube_search``).
            requests.RequestException: On network / transport errors (re-raised
                from ``_fallback_search`` via ``_call_youtube_search``).
            OSError: On OS-level I/O errors during the yt-dlp download probe
                (re-raised from ``_fallback_search`` via ``_call_youtube_search``).
            yt_dlp.utils.DownloadError: On yt-dlp download errors (re-raised
                from ``_fallback_search`` via ``_call_youtube_search``).
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
                daily_quota_units=self._youtube_search.daily_quota_units,
                search_list_cost_units=self._youtube_search.search_list_cost_units,
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

        ``YoutubeSearch.search()`` is fail-soft (never raises) for most paths,
        but after sub-phase 11.2 ``_fallback_search`` re-raises parser/transport
        errors.  This wrapper adds two layers of circuit-open detection:

        1. Pre-call guard: if the breaker is already OPEN, raise immediately so
           ``find()`` can skip caching ``__no_result__``.
        2. Post-call check: if the breaker *transitioned* closed → open during
           this call (a fresh transport failure that tripped the threshold),
           raise ``CircuitOpenError`` post-hoc so the cache write is skipped.
           Without this, a ``None`` return from ``search()`` on the very call
           that opens the breaker would be indistinguishable from "no results".

        Args:
            searcher: ``YoutubeSearch`` instance to call.
            title: Media title for the query.
            year: Release year or None.

        Returns:
            YouTube URL string, or ``None`` when the search returned no results.

        Raises:
            CircuitOpenError: When the YouTube circuit breaker is OPEN before
                the search call, or when it opened during this call.
            KeyError: On yt-dlp parser schema drift (re-raised from
                ``_fallback_search``).
            AttributeError: On yt-dlp parser schema drift (re-raised from
                ``_fallback_search``).
            TypeError: On yt-dlp parser schema drift (re-raised from
                ``_fallback_search``).
            requests.RequestException: On network transport errors (re-raised
                from ``_fallback_search``).
            OSError: On OS-level I/O errors (re-raised from ``_fallback_search``).
        """
        # guard() raises CircuitOpenError(provider, remaining_seconds) when OPEN.
        searcher._breaker.guard()

        # Snapshot breaker state before the call to detect a fresh trip.
        was_open_before = not searcher._breaker.can_proceed()

        result = searcher.search(title, year)

        # If the breaker transitioned closed → open during this call, a fresh
        # transport failure tripped the threshold.  Raise so find() skips caching
        # __no_result__ — the None return is not a genuine "no results" signal.
        is_open_after = not searcher._breaker.can_proceed()
        if not was_open_before and is_open_after:
            logger.warning(
                "trailer_youtube_breaker_opened_during_call",
                title=title,
                year=year,
            )
            raise CircuitOpenError("breaker opened during call", 0.0)

        return result

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

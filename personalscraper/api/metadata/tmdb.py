"""TMDB metadata provider — migrated from scraper/tmdb_client.py.

Implements MetadataClient + MetadataProvider Protocol. All HTTP calls go
through HttpTransport consuming a TransportPolicy. Returns typed models
from _base.py via _tmdb_parsers.py. Zero untyped dicts in public signatures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from personalscraper.api.metadata._base import (
    ArtworkItem,
    MediaDetails,
    MetadataClient,
    SearchResult,
    SeasonDetails,
    Video,
)
from personalscraper.api.metadata._tmdb_parsers import (
    _build_image_url,
    parse_artwork,
    parse_keywords,
    parse_media_details,
    parse_search_result,
    parse_season_details,
    parse_video,
)
from personalscraper.api.transport._auth import BearerAuth
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport

log = get_logger("api.tmdb")

# TMDB-specific defaults
_DEFAULT_CIRCUIT = CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0)
_DEFAULT_RATE = RateLimitPolicy(requests_per_second=40.0)
_DEFAULT_RETRY = RetryPolicy(max_attempts=4)


class TMDBClient(MetadataClient):
    """TMDB API v3 metadata provider.

    Authentication via Bearer token (API Read Access Token).
    All HTTP calls go through HttpTransport, which enforces retry,
    circuit breaker, and rate limiting uniformly.

    Implements MetadataProvider Protocol: search, get_details,
    get_artwork_urls, get_keywords, get_videos, get_season.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = ["TMDB_API_KEY"]

    def __init__(
        self,
        transport: HttpTransport,
        *,
        language: str = "fr-FR",
        fallback_language: str = "en-US",
        prefer_local_title: bool = True,
    ) -> None:
        """Initialize the TMDB client.

        Args:
            transport: HttpTransport pre-configured with TMDB policy.
            language: Default language for API queries.
            fallback_language: Fallback when primary language returns empty results.
            prefer_local_title: Use localized titles when available.
        """
        super().__init__(transport, language=language)
        self._fallback_language = fallback_language
        self._prefer_local_title = prefer_local_title

    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "tmdb"

    @property
    def circuit(self) -> Any:  # CircuitBreaker, but avoid circular import
        """Expose the underlying circuit breaker for external consumers."""
        return self._transport._circuit

    @classmethod
    def policy(
        cls,
        api_key: str,
        *,
        circuit: CircuitPolicy | None = None,
    ) -> TransportPolicy:
        """Build the TransportPolicy for TMDB.

        Args:
            api_key: TMDB API Read Access Token (Bearer token).
            circuit: Optional custom CircuitPolicy override.

        Returns:
            A TransportPolicy configured for TMDB.
        """
        return TransportPolicy(
            provider_name="TMDB",
            base_url="https://api.themoviedb.org/3",
            auth=BearerAuth(api_key),
            timeout_seconds=10.0,
            retry=_DEFAULT_RETRY,
            circuit=circuit if circuit is not None else _DEFAULT_CIRCUIT,
            rate_limit=_DEFAULT_RATE,
        )

    # -- Protocol: search ---------------------------------------------------

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: str = "movie",
    ) -> list[SearchResult]:
        """Search for a movie or TV show by title.

        Args:
            title: Search query.
            year: Optional release/first-air year filter.
            media_type: "movie" or "tv".

        Returns:
            List of SearchResult, sorted by TMDB relevance.
        """
        if media_type == "tv":
            return self.search_tv(title, year=year)
        return self.search_movie(title, year=year)

    # -- Protocol: get_details ----------------------------------------------

    def get_details(
        self,
        media_id: str,
        media_type: str = "movie",
    ) -> MediaDetails:
        """Fetch full details for a movie or TV show.

        Uses append_to_response to fetch images, videos, keywords, and
        external_ids in a single request.

        Args:
            media_id: TMDB movie or TV ID.
            media_type: "movie" or "tv".

        Returns:
            Populated MediaDetails with artwork, genres, and external IDs.
        """
        if media_type == "tv":
            return self.get_tv(int(media_id))
        return self.get_movie(int(media_id))

    # -- TMDB-specific: movie search ----------------------------------------

    def search_movie(
        self,
        title: str,
        year: int | None = None,
        *,
        language: str | None = None,
        max_pages: int = 5,
    ) -> list[SearchResult]:
        """Search TMDB for movies.

        Args:
            title: Movie title to search for.
            year: Optional release year filter.
            language: Override default language.
            max_pages: Max pages to fetch (20 results/page).

        Returns:
            List of SearchResult, sorted by TMDB relevance.
        """
        params: dict[str, object] = {
            "query": title,
            "language": language or self._language,
        }
        if year is not None:
            params["year"] = year
        return self._search_paginated("/search/movie", params, max_pages)

    def search_tv(
        self,
        title: str,
        year: int | None = None,
        *,
        language: str | None = None,
        max_pages: int = 5,
    ) -> list[SearchResult]:
        """Search TMDB for TV shows.

        Args:
            title: Show title to search for.
            year: Optional first-air year filter.
            language: Override default language.
            max_pages: Max pages to fetch (20 results/page).

        Returns:
            List of SearchResult, sorted by TMDB relevance.
        """
        params: dict[str, object] = {
            "query": title,
            "language": language or self._language,
        }
        if year is not None:
            params["first_air_date_year"] = year
        return self._search_paginated("/search/tv", params, max_pages)

    # -- TMDB-specific: details ---------------------------------------------

    def get_movie(self, movie_id: int) -> MediaDetails:
        """Fetch full movie details with artwork, videos, keywords.

        Args:
            movie_id: TMDB movie ID.

        Returns:
            Populated MediaDetails.
        """
        params: dict[str, object] = {
            "language": self._language,
            "append_to_response": "videos,images,keywords,external_ids",
            "include_image_language": f"{self._language},{self._fallback_language},en,null",
        }
        raw = self._transport.get(f"/movie/{movie_id}", params=params)
        if not isinstance(raw, dict):
            raise TypeError(f"Expected dict response, got {type(raw).__name__}")
        return parse_media_details(raw, "tmdb")

    def get_tv(self, tv_id: int) -> MediaDetails:
        """Fetch full TV show details with artwork, videos, keywords.

        Args:
            tv_id: TMDB TV show ID.

        Returns:
            Populated MediaDetails.
        """
        params: dict[str, object] = {
            "language": self._language,
            "append_to_response": "videos,images,keywords,external_ids",
            "include_image_language": f"{self._language},{self._fallback_language},en,null",
        }
        raw = self._transport.get(f"/tv/{tv_id}", params=params)
        if not isinstance(raw, dict):
            raise TypeError(f"Expected dict response, got {type(raw).__name__}")
        return parse_media_details(raw, "tmdb")

    def get_tv_season(self, tv_id: int, season: int) -> SeasonDetails:
        """Fetch season details with episodes and artwork.

        Args:
            tv_id: TMDB TV show ID.
            season: Season number (1-indexed; 0 = specials).

        Returns:
            SeasonDetails with episodes parsed.
        """
        params: dict[str, object] = {
            "language": self._language,
            "append_to_response": "images",
            "include_image_language": f"{self._language},{self._fallback_language},en,null",
        }
        raw = self._transport.get(f"/tv/{tv_id}/season/{season}", params=params)
        if not isinstance(raw, dict):
            raise TypeError(f"Expected dict response, got {type(raw).__name__}")
        raw["_tv_id"] = str(tv_id)
        return parse_season_details(raw, "tmdb")

    # -- Protocol: get_artwork_urls -----------------------------------------

    def get_artwork_urls(
        self,
        media_id: str,
        media_type: str = "movie",
    ) -> list[ArtworkItem]:
        """Fetch artwork images for a movie or TV show.

        Uses the images sub-resource from the details endpoint to avoid
        a separate API call.

        Args:
            media_id: TMDB media ID.
            media_type: "movie" or "tv".

        Returns:
            List of ArtworkItem (posters, backdrops, logos).
        """
        params: dict[str, object] = {
            "language": self._language,
            "include_image_language": f"{self._language},{self._fallback_language},en,null",
        }
        endpoint = f"/{media_type}/{media_id}/images"
        raw = self._transport.get(endpoint, params=params)
        if not isinstance(raw, dict):
            return []
        return parse_artwork(raw)

    # -- Protocol: get_videos -----------------------------------------------

    def get_videos(
        self,
        media_id: str,
        media_type: str,
        language: str,
    ) -> list[Video]:
        """Fetch videos for a movie or TV show.

        Args:
            media_id: TMDB media ID.
            media_type: "movie" or "tv".
            language: ISO 639-1 language filter.

        Returns:
            List of Video objects.
        """
        return self._fetch_videos(f"/{media_type}/{media_id}/videos", language)

    def fetch_tv_season_videos(
        self,
        tv_id: int,
        season_number: int,
        language: str,
    ) -> list[Video]:
        """Fetch videos for a specific TV season.

        Args:
            tv_id: TMDB TV show ID.
            season_number: Season number (1-indexed).
            language: ISO 639-1 language filter.

        Returns:
            List of Video objects for this season (may be empty).
        """
        return self._fetch_videos(
            f"/tv/{tv_id}/season/{season_number}/videos",
            language,
        )

    def _fetch_videos(self, endpoint: str, language: str) -> list[Video]:
        """Fetch videos, fail-soft on unexpected response shapes.

        Transport/circuit errors propagate. Only unexpected response shapes
        (non-dict body) are silently downgraded to an empty list.

        Args:
            endpoint: Videos API path.
            language: ISO 639-1 language filter.

        Returns:
            List of Video objects (empty on malformed response).
        """
        try:
            return self._fetch_videos_strict(endpoint, language)
        except (TypeError, KeyError, ValueError):
            return []

    def _fetch_videos_strict(self, endpoint: str, language: str) -> list[Video]:
        """Fetch videos with full error propagation.

        Unlike ``_fetch_videos``, this method does not catch parser errors.
        Transport errors, circuit-open, and API errors propagate to the caller.

        Args:
            endpoint: Videos API path.
            language: ISO 639-1 language filter.

        Returns:
            List of Video objects.

        Raises:
            ApiError: On TMDB HTTP errors.
            CircuitOpenError: If the TMDB circuit breaker is OPEN.
            TypeError: On unexpected response shape.
        """
        params: dict[str, object] = {"language": language}
        raw = self._transport.get(endpoint, params=params)
        if not isinstance(raw, dict):
            raise TypeError(f"TMDB videos: expected dict, got {type(raw).__name__}")
        results = raw.get("results", []) or []
        return [parse_video(v) for v in results]

    # -- Protocol: get_keywords ---------------------------------------------

    def get_keywords(self, media_id: str, media_type: str) -> list[str]:
        """Fetch keywords for a movie or TV show.

        Handles TMDB's envelope inconsistency: movies use ``keywords``,
        TV shows use ``results``.

        Args:
            media_id: TMDB media ID.
            media_type: "movie" or "tv".

        Returns:
            List of keyword name strings.
        """
        endpoint = f"/{media_type}/{media_id}/keywords"
        raw = self._transport.get(endpoint)
        if not isinstance(raw, dict):
            return []
        return parse_keywords(raw, media_type)

    # -- Protocol: get_season -----------------------------------------------

    def get_season(self, tv_id: str, season: int) -> SeasonDetails:
        """Fetch TV season details.

        Args:
            tv_id: TMDB TV show ID.
            season: Season number (1-indexed).

        Returns:
            SeasonDetails with parsed episodes.
        """
        return self.get_tv_season(int(tv_id), season)

    # -- Helpers ------------------------------------------------------------

    def get_image_url(self, path: str, size: str = "w780") -> str:
        """Build a full TMDB image URL from a file_path and size.

        Args:
            path: Image file_path from TMDB (e.g. "/abc.jpg").
            size: Width code (e.g. "w500", "w780", "original").

        Returns:
            Full CDN URL, or empty string if path is empty.
        """
        return _build_image_url(path, size)

    def _search_paginated(
        self,
        endpoint: str,
        params: dict[str, object],
        max_pages: int = 5,
    ) -> list[SearchResult]:
        """Paginated search helper.

        TMDB returns 20 results per page, with total_pages capped at 500.
        Empty results on first page = no matches.

        Args:
            endpoint: Search endpoint path.
            params: Query parameters (query, language, year, etc.).
            max_pages: Maximum pages to fetch (default 5 = 100 results).

        Returns:
            List of SearchResult across all fetched pages.
        """
        all_results: list[SearchResult] = []
        for page in range(1, max_pages + 1):
            page_params = {**params, "page": page}
            raw = self._transport.get(endpoint, params=page_params)
            if not isinstance(raw, dict):
                break
            results = raw.get("results", []) or []
            if not results:
                break
            for item in results:
                all_results.append(parse_search_result(item, "tmdb"))
            total_pages = raw.get("total_pages", 0)
            if page >= total_pages:
                break
        return all_results

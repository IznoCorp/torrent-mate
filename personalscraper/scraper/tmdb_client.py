"""TMDB API v3 client for movie and TV show metadata.

Handles authentication (Bearer token), retry with exponential backoff
(tenacity), and language configuration. Implements the MetadataProvider
protocol for polymorphic usage alongside TVDBClient.

All HTTP calls go through _get() which retries on 429/5xx and connection
errors, but fails immediately on 401/403/404 (fatal errors).

See docs/TMDB-API.md for the full API reference.
See docs/tenacity-reference.md for retry strategy details.
"""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

import requests
from requests.adapters import HTTPAdapter
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)
from urllib3.util.retry import Retry as Urllib3Retry

from personalscraper.logger import get_logger
from personalscraper.scraper.http_retry import build_retry_logger, make_retryable_predicate

if TYPE_CHECKING:
    from personalscraper.scraper.circuit_breaker import CircuitBreaker

log = get_logger("tmdb_client")


# TMDB internal error codes (not HTTP codes)
TMDB_INVALID_KEY = 7
TMDB_SUSPENDED_KEY = 10
TMDB_RATE_LIMIT = 25
TMDB_NOT_FOUND = 34


class TMDBError(Exception):
    """TMDB API error with both HTTP and internal status codes.

    Attributes:
        http_status: HTTP status code from the response.
        tmdb_code: TMDB internal status_code (e.g. 7=invalid key, 34=not found).
        message: TMDB status_message.
    """

    def __init__(self, http_status: int, tmdb_code: int, message: str) -> None:
        """Initialize TMDBError.

        Args:
            http_status: HTTP status code.
            tmdb_code: TMDB internal error code.
            message: TMDB error message.
        """
        self.http_status = http_status
        self.tmdb_code = tmdb_code
        self.message = message
        super().__init__(f"TMDB {http_status} (code {tmdb_code}): {message}")


@dataclass(frozen=True)
class Video:
    """A video entry from the TMDB /videos endpoint.

    Attributes:
        id: TMDB internal video UUID.
        site: Hosting platform, typically "YouTube".
        key: Platform video identifier (YouTube video ID).
        type: Video category: "Trailer", "Teaser", "Clip", "Featurette", etc.
        official: Whether the video is from an official channel.
        size: Vertical resolution in pixels (e.g. 1080, 720, 480).
        iso_639_1: Language code (e.g. "en", "fr").
    """

    id: str
    site: str
    key: str
    type: str
    official: bool
    size: int
    iso_639_1: str


_is_retryable = make_retryable_predicate(TMDBError)


class TMDBClient:
    """Client for The Movie Database API v3.

    All HTTP calls use tenacity retry (exponential backoff on 429/5xx).
    Auth via Bearer token (recommended by TMDB over query param).

    Attributes:
        BASE_URL: TMDB API v3 base URL.
        IMAGE_BASE_URL: Base URL for TMDB image CDN.
    """

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p"

    def __init__(
        self,
        api_key: str,
        language: str = "fr-FR",
        circuit_breaker_threshold: int = 5,
        circuit_breaker_cooldown: int = 300,
    ) -> None:
        """Initialize the TMDB client with Bearer token auth.

        Sets up a requests Session with transport-level retry (urllib3)
        for DNS/TCP/TLS errors, and application-level retry (tenacity)
        for 429/5xx via _get().

        Args:
            api_key: TMDB API read access token (Bearer token).
            language: Default language for API queries (e.g. "fr-FR").
            circuit_breaker_threshold: Consecutive failures before opening circuit.
            circuit_breaker_cooldown: Seconds to wait before half-open test.
        """
        self._api_key = api_key
        self._language = language

        # Transport-level retry for low-level network issues
        transport_retry = Urllib3Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=transport_retry)

        self._session = requests.Session()
        self._session.mount("https://", adapter)
        self._session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
            }
        )

        # Circuit breaker for sustained outage detection (above tenacity)
        from personalscraper.scraper.circuit_breaker import CircuitBreaker

        self._circuit = CircuitBreaker(
            name="TMDB",
            failure_threshold=circuit_breaker_threshold,
            cooldown_seconds=circuit_breaker_cooldown,
        )

    def close(self) -> None:
        """Release the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> "TMDBClient":
        """Return self for use as a context manager."""
        return self

    def __exit__(self, *exc: object) -> None:
        """Close the HTTP session on context exit."""
        self.close()

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential_jitter(initial=0.5, max=10, jitter=0.5),
        stop=stop_after_attempt(4),
        before_sleep=build_retry_logger(log, "tmdb_retry"),
        reraise=True,
    )
    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a GET request to the TMDB API with automatic retry.

        Adds the language parameter automatically. Retries on 429/5xx
        with exponential backoff (4 attempts max). Parses TMDB error
        responses and raises TMDBError with the internal status_code.

        Circuit breaker check runs before the HTTP call — if the provider
        is considered down (OPEN state), CircuitOpenError is raised
        immediately without making a network request.

        Args:
            endpoint: API endpoint path (e.g. "/search/movie").
            params: Optional query parameters.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            CircuitOpenError: If the circuit breaker is OPEN.
            TMDBError: On TMDB-specific errors (invalid key, not found, etc.).
            requests.exceptions.HTTPError: On non-TMDB HTTP errors.
            requests.exceptions.ConnectionError: On network errors (after retries).
            requests.exceptions.Timeout: On timeout (after retries).
        """
        from personalscraper.scraper.circuit_breaker import CircuitOpenError

        # Fail fast if provider is down
        self._circuit.guard()

        if params is None:
            params = {}
        params.setdefault("language", self._language)

        try:
            resp = self._session.get(
                f"{self.BASE_URL}{endpoint}",
                params=params,
                timeout=10,
            )

            # Parse TMDB error format before raise_for_status
            if not resp.ok:
                try:
                    error_data = resp.json()
                    tmdb_code = error_data.get("status_code", 0)
                    tmdb_msg = error_data.get("status_message", resp.reason)
                    raise TMDBError(resp.status_code, tmdb_code, tmdb_msg)
                except (ValueError, KeyError):
                    # Not a TMDB error format — fall through to raise_for_status
                    pass
                resp.raise_for_status()

            self._circuit.record_success()
            return cast(dict[str, Any], resp.json())
        except CircuitOpenError:
            raise
        except Exception as exc:
            self._circuit.record_failure(exc)
            raise

    @property
    def circuit(self) -> "CircuitBreaker":
        """Expose circuit breaker for scraper fallback logic.

        Returns:
            The CircuitBreaker instance for this client.
        """
        return self._circuit

    # -- Protocol methods (MetadataProvider) --

    def search(self, title: str, year: int | None = None, media_type: str = "movie") -> list[dict[str, Any]]:
        """Search for a media item by title (Protocol method).

        Dispatches to search_movie() or search_tv() based on media_type.

        Args:
            title: Media title to search for.
            year: Optional release year to boost relevance.
            media_type: "movie" or "tv".

        Returns:
            List of raw API result dicts.
        """
        if media_type == "tv":
            return self.search_tv(title, year)
        return self.search_movie(title, year)

    def get_details(self, media_id: int, media_type: str = "movie") -> dict[str, Any]:
        """Get full details for a media item (Protocol method).

        Dispatches to get_movie() or get_tv() based on media_type.

        Args:
            media_id: TMDB media ID.
            media_type: "movie" or "tv".

        Returns:
            Dict with full metadata, images, and external IDs.
        """
        if media_type == "tv":
            return self.get_tv(media_id)
        return self.get_movie(media_id)

    def get_artwork_urls(self, media_id: int, media_type: str = "movie") -> list[dict[str, Any]]:
        """Get artwork URLs from already-fetched details (Protocol method).

        Images are embedded in get_movie()/get_tv() responses via
        append_to_response — no additional API call needed.

        Args:
            media_id: TMDB media ID.
            media_type: "movie" or "tv".

        Returns:
            List of artwork dicts with type, url, language, season keys.
        """
        details = self.get_details(media_id, media_type)
        images = details.get("images", {})
        artworks = []

        # Posters
        for img in images.get("posters", []):
            artworks.append(
                {
                    "type": "poster",
                    "url": self.get_image_url(img["file_path"]),
                    "language": img.get("iso_639_1"),
                    "season": None,
                }
            )

        # Backdrops → landscape equivalent
        for img in images.get("backdrops", []):
            artworks.append(
                {
                    "type": "landscape",
                    "url": self.get_image_url(img["file_path"]),
                    "language": img.get("iso_639_1"),
                    "season": None,
                }
            )

        return artworks

    # -- Type-specific methods --

    def search_movie(self, title: str, year: int | None = None) -> list[dict[str, Any]]:
        """Search for movies by title.

        The year parameter boosts relevance but does NOT exclude other years.
        Client-side filtering by release_date is needed for strict year matching.
        An empty result is HTTP 200 with results:[] (not 404).

        Args:
            title: Movie title to search for.
            year: Optional release year to boost relevance.

        Returns:
            List of movie result dicts from the API.
        """
        params: dict[str, Any] = {"query": title}
        if year is not None:
            params["year"] = year
        data = self._get("/search/movie", params)
        return cast(list[dict[str, Any]], data.get("results", []))

    def search_tv(self, title: str, year: int | None = None) -> list[dict[str, Any]]:
        """Search for TV shows by title.

        Uses first_air_date_year (not year) for TV show searches.

        Args:
            title: TV show title to search for.
            year: Optional first air date year to boost relevance.

        Returns:
            List of TV show result dicts from the API.
        """
        params: dict[str, Any] = {"query": title}
        if year is not None:
            # TMDB uses first_air_date_year for TV, not year
            params["first_air_date_year"] = year
        data = self._get("/search/tv", params)
        return cast(list[dict[str, Any]], data.get("results", []))

    def get_movie(self, movie_id: int) -> dict[str, Any]:
        """Get full movie details with credits, images, IDs, and certifications.

        Uses append_to_response to fetch everything in a single API call.
        include_image_language=fr,en,null is MANDATORY — without it,
        5x-31x fewer images are returned (backdrops especially).

        Args:
            movie_id: TMDB movie ID.

        Returns:
            Dict with full movie metadata including credits, images,
            external_ids, and release_dates (for FR certification).
        """
        return self._get(
            f"/movie/{movie_id}",
            {
                "append_to_response": "credits,images,external_ids,release_dates",
                "include_image_language": "fr,en,null",
            },
        )

    def get_tv(self, tv_id: int) -> dict[str, Any]:
        """Get full TV show details with credits, images, IDs, and ratings.

        Uses aggregate_credits (not credits) for TV shows — it groups
        multiple roles via roles[]/jobs[]. episode_run_time may be empty
        for recent shows — use per-episode runtime from season details.

        Args:
            tv_id: TMDB TV show ID.

        Returns:
            Dict with full TV show metadata including aggregate_credits,
            images, external_ids, and content_ratings.
        """
        return self._get(
            f"/tv/{tv_id}",
            {
                "append_to_response": "aggregate_credits,images,external_ids,content_ratings",
                "include_image_language": "fr,en,null",
            },
        )

    def get_tv_season(self, tv_id: int, season: int) -> dict[str, Any]:
        """Get season details with episodes and images.

        Returns all episodes with crew, guest_stars, and per-episode
        runtime (more reliable than show-level episode_run_time).
        Season images only return posters (no backdrops).

        Args:
            tv_id: TMDB TV show ID.
            season: Season number.

        Returns:
            Dict with season details, episodes list, and images.
        """
        return self._get(
            f"/tv/{tv_id}/season/{season}",
            {
                "append_to_response": "images",
            },
        )

    def get_image_url(self, path: str, size: str = "original") -> str:
        """Build a full TMDB image URL.

        Args:
            path: Image file path from API response (e.g. "/abc123.jpg").
            size: Image size (e.g. "original", "w500", "w185").

        Returns:
            Full HTTPS URL to the image.
        """
        return f"{self.IMAGE_BASE_URL}/{size}{path}"

    def get_keywords(self, tmdb_id: int, media_type: Literal["movie", "tv"]) -> list[str]:
        """Fetch keyword names from the TMDB /keywords endpoint.

        Endpoints:
        - ``GET /movie/{id}/keywords`` → response ``{"id": N, "keywords": [...]}``
        - ``GET /tv/{id}/keywords``    → response ``{"id": N, "results":  [...]}``

        Each keyword object has the shape ``{"id": N, "name": "..."}``.

        Fail-soft policy:
        - HTTP 404 (item not found): returns ``[]`` silently.
        - Timeout / 5xx after retries: returns ``[]`` and logs a warning.
        - Any other unexpected exception: returns ``[]`` and logs a warning.

        This means callers never need to guard against exceptions from this
        method, and a TMDB keywords outage does not block the scrape pipeline.

        Args:
            tmdb_id: TMDB numeric identifier.
            media_type: ``"movie"`` or ``"tv"``.

        Returns:
            List of keyword name strings. Empty list on any error or when the
            item has no keywords.
        """
        from personalscraper.scraper.circuit_breaker import CircuitOpenError as _CircuitOpenError  # noqa: F401

        endpoint = f"/{media_type}/{tmdb_id}/keywords"
        try:
            data = self._get(endpoint)
        except TMDBError as exc:
            if exc.http_status == 404:
                return []
            log.warning(
                "tmdb_keywords_failed_http",
                media_type=media_type,
                tmdb_id=tmdb_id,
                http_status=exc.http_status,
                message=exc.message,
                fallback="empty_list",
                exc_info=True,
            )
            return []
        except (requests.RequestException, json.JSONDecodeError, _CircuitOpenError) as exc:
            log.warning(
                "tmdb_keywords_failed",
                media_type=media_type,
                tmdb_id=tmdb_id,
                error=str(exc),
                fallback="empty_list",
                exc_info=True,
            )
            return []

        # Movies use "keywords" key; TV shows use "results" key.
        raw_list = data.get("keywords") or data.get("results") or []
        return [str(kw["name"]) for kw in raw_list if isinstance(kw, dict) and kw.get("name")]

    def fetch_movie_videos(self, tmdb_id: int, language: str) -> list[Video]:
        """Fetch video entries (trailers, teasers) for a movie.

        Calls ``GET /movie/{id}/videos``.

        Fail-soft policy identical to ``get_keywords()``: HTTP 404, timeout,
        and any unexpected exception all return ``[]`` and log a warning.

        Args:
            tmdb_id: TMDB movie ID.
            language: BCP-47 language tag (e.g. "fr-FR", "en-US").

        Returns:
            List of Video dataclass instances. Empty on any error.
        """
        return self._fetch_videos(f"/movie/{tmdb_id}/videos", tmdb_id, "movie", language)

    def fetch_tv_videos(self, tmdb_id: int, language: str) -> list[Video]:
        """Fetch video entries (trailers, teasers) for a TV show.

        Calls ``GET /tv/{id}/videos``.

        Fail-soft policy identical to ``get_keywords()``: HTTP 404, timeout,
        and any unexpected exception all return ``[]`` and log a warning.

        Args:
            tmdb_id: TMDB TV show ID.
            language: BCP-47 language tag (e.g. "fr-FR", "en-US").

        Returns:
            List of Video dataclass instances. Empty on any error.
        """
        return self._fetch_videos(f"/tv/{tmdb_id}/videos", tmdb_id, "tv", language)

    def fetch_tv_season_videos(self, tv_id: int, season_number: int, language: str) -> list[Video]:
        """Fetch videos for a specific TV show season from TMDB.

        Calls ``GET /tv/{tv_id}/season/{season_number}/videos``. TMDB indexes
        seasons starting at 1 (specials are season 0).

        Args:
            tv_id: TMDB TV show id.
            season_number: TMDB season number (1-indexed; specials = 0).
            language: BCP-47 language code (e.g. "fr-FR", "en-US").

        Returns:
            List of Video dataclass instances. Empty list on 404 (no videos
            for this season — common for older shows or non-flagship seasons)
            or any other error (fail-soft, same as show-level).

        Raises:
            Same as fetch_tv_videos — propagates circuit-breaker open, fails
            fast on unrecoverable 5xx after retries, fail-soft on 404 (returns []).
        """
        return self._fetch_videos(
            f"/tv/{tv_id}/season/{season_number}/videos",
            tv_id,
            f"tv-season-{season_number}",
            language,
        )

    def _fetch_videos(self, endpoint: str, tmdb_id: int, media_type: str, language: str) -> list[Video]:
        """Internal: call /videos endpoint and deserialize into Video list.

        Args:
            endpoint: Full endpoint path (e.g. "/movie/550/videos").
            tmdb_id: TMDB ID for logging context.
            media_type: "movie" or "tv" for log messages.
            language: BCP-47 language tag passed as query parameter.

        Returns:
            List of Video instances; empty list on any error.
        """
        try:
            data = self._get(endpoint, {"language": language})
        except TMDBError as exc:
            if exc.http_status == 404:
                return []
            log.warning(
                "tmdb_videos_failed_http",
                media_type=media_type,
                tmdb_id=tmdb_id,
                http_status=exc.http_status,
                message=exc.message,
                fallback="empty_list",
                exc_info=True,
            )
            return []
        except Exception as exc:
            log.warning(
                "tmdb_videos_failed",
                media_type=media_type,
                tmdb_id=tmdb_id,
                error=str(exc),
                fallback="empty_list",
                exc_info=True,
            )
            return []

        raw_list = data.get("results") or []
        videos: list[Video] = []
        for item in raw_list:
            if not isinstance(item, dict):
                continue
            try:
                videos.append(
                    Video(
                        id=str(item["id"]),
                        site=str(item.get("site", "")),
                        key=str(item.get("key", "")),
                        type=str(item.get("type", "")),
                        official=bool(item.get("official", False)),
                        size=int(item.get("size", 0)),
                        iso_639_1=str(item.get("iso_639_1", "")),
                    )
                )
            except (KeyError, TypeError, ValueError):
                log.debug("tmdb_video_entry_malformed", item=repr(item))
                continue
        return videos

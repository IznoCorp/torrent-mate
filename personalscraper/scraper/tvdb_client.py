"""TVDB API v4 client for TV show metadata.

Handles JWT authentication (login with API key, auto re-login on 401),
retry with exponential backoff (tenacity), and language code mapping.
Implements the MetadataProvider protocol alongside TMDBClient.

TVDB is the primary provider for TV series; TMDB is used as fallback.

Key differences from TMDB:
- JWT bearer token obtained via POST /login (valid 1 month)
- 3-char language codes (fra, eng) — not 2-char like TMDB
- Responses wrapped in {"status": "success", "data": {...}}
- Two error formats: login errors vs endpoint errors

See docs/TVDB-API.md for the full API reference.
See docs/tenacity-reference.md for retry strategy details.
"""

import logging
from typing import TYPE_CHECKING, Any, cast

import requests
from requests.adapters import HTTPAdapter
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)
from urllib3.util.retry import Retry as Urllib3Retry

from personalscraper.scraper.http_retry import make_retryable_predicate

if TYPE_CHECKING:
    from personalscraper.scraper.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

# TVDB source type IDs for cross-referencing
TVDB_SOURCE_IMDB = 2
TVDB_SOURCE_TMDB_MOVIE = 10
TVDB_SOURCE_TMDB_TV = 12
TVDB_SOURCE_TMDB_PERSON = 15
TVDB_SOURCE_TMDB_COLLECTION = 28

# TVDB artwork type IDs (from GET /artwork/types)
ARTWORK_POSTER_SERIES = 2
ARTWORK_BACKGROUND_SERIES = 3
ARTWORK_POSTER_SEASON = 7
ARTWORK_POSTER_MOVIE = 14
ARTWORK_BACKGROUND_MOVIE = 15
ARTWORK_CLEARLOGO_SERIES = 23


class TVDBError(Exception):
    """TVDB API error.

    Attributes:
        http_status: HTTP status code.
        message: TVDB error message.
    """

    def __init__(self, http_status: int, message: str) -> None:
        """Initialize TVDBError.

        Args:
            http_status: HTTP status code.
            message: Error message from TVDB.
        """
        self.http_status = http_status
        self.message = message
        super().__init__(f"TVDB {http_status}: {message}")



_is_retryable = make_retryable_predicate(TVDBError)


class TVDBClient:
    """Client for TheTVDB API v4.

    All HTTP calls use tenacity retry (exponential backoff on 429/5xx).
    Auth via JWT bearer token obtained from POST /login.

    Attributes:
        BASE_URL: TVDB API v4 base URL.
        LANG_MAP: Mapping from 2-char pipeline codes to 3-char TVDB codes.
    """

    BASE_URL = "https://api4.thetvdb.com/v4"

    # Pipeline uses 2-char codes internally; TVDB API requires 3-char
    # shortCode in /languages is always null — manual mapping required
    LANG_MAP: dict[str, str] = {
        "fr": "fra", "en": "eng", "es": "spa",
        "de": "deu", "it": "ita", "ja": "jpn",
        "ko": "kor", "pt": "por", "ru": "rus",
        "zh": "zho", "ar": "ara", "nl": "nld",
    }

    def __init__(
        self,
        api_key: str,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_cooldown: int = 300,
    ) -> None:
        """Initialize the TVDB client.

        Does NOT automatically login — call login() explicitly or let
        _get() handle auto-login on first request.

        Args:
            api_key: TVDB API key (Negotiated Contract type, no PIN needed).
            circuit_breaker_threshold: Consecutive failures before opening circuit.
            circuit_breaker_cooldown: Seconds to wait before half-open test.
        """
        self._api_key = api_key
        self._token: str | None = None
        self._artwork_types: dict[int, str] | None = None

        # Transport-level retry for low-level network issues
        transport_retry = Urllib3Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=transport_retry)

        self._session = requests.Session()
        self._session.mount("https://", adapter)
        self._session.headers.update({"Accept": "application/json"})

        # Circuit breaker for sustained outage detection (above tenacity)
        from personalscraper.scraper.circuit_breaker import CircuitBreaker

        self._circuit = CircuitBreaker(
            name="TVDB",
            failure_threshold=circuit_breaker_threshold,
            cooldown_seconds=circuit_breaker_cooldown,
        )

    def login(self) -> None:
        """Authenticate with the TVDB API and store the JWT token.

        Uses Negotiated Contract key (no PIN field). Token is valid
        for 1 month. Called automatically by _get() if no token exists
        or if the token has expired (HTTP 401).

        Raises:
            TVDBError: If authentication fails (invalid key, PIN required, etc.).
            requests.exceptions.ConnectionError: If the API is unreachable.
        """
        resp = self._session.post(
            f"{self.BASE_URL}/login",
            json={"apikey": self._api_key},
            timeout=10,
        )

        if not resp.ok:
            try:
                error_data = resp.json()
                msg = error_data.get("message", resp.reason)
            except (ValueError, KeyError):
                msg = resp.reason
            raise TVDBError(resp.status_code, msg)

        data = resp.json()
        self._token = data["data"]["token"]
        self._session.headers["Authorization"] = f"Bearer {self._token}"
        logger.info("TVDB login successful")

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        """Send a GET request to the TVDB API with automatic retry.

        Auto-login on first call or re-login on 401 (expired token).
        Retries on 429/5xx with exponential backoff (3 attempts max).

        Circuit breaker check runs before the HTTP call — if the provider
        is considered down (OPEN state), CircuitOpenError is raised
        immediately without making a network request. The 401 re-login
        is NOT blocked by the circuit breaker (401 is not a circuit error).

        Args:
            endpoint: API endpoint path (e.g. "/search").
            params: Optional query parameters.

        Returns:
            The "data" field from the TVDB response envelope.

        Raises:
            CircuitOpenError: If the circuit breaker is OPEN.
            TVDBError: On TVDB errors after re-login attempt.
            requests.exceptions.HTTPError: On non-TVDB HTTP errors.
            requests.exceptions.ConnectionError: On network errors (after retries).
        """
        from personalscraper.scraper.circuit_breaker import CircuitOpenError

        # Fail fast if provider is down
        self._circuit.guard()

        # Auto-login if no token
        if self._token is None:
            self.login()

        try:
            resp = self._session.get(
                f"{self.BASE_URL}{endpoint}",
                params=params or {},
                timeout=15,
            )

            # Re-login on 401 (token expired) — one retry
            # 401 is NOT a circuit error — it's a normal auth flow
            if resp.status_code == 401:
                logger.warning("TVDB token expired, re-authenticating")
                self.login()
                resp = self._session.get(
                    f"{self.BASE_URL}{endpoint}",
                    params=params or {},
                    timeout=15,
                )

            if not resp.ok:
                try:
                    error_data = resp.json()
                    msg = error_data.get("message", resp.reason)
                except (ValueError, KeyError):
                    msg = resp.reason
                raise TVDBError(resp.status_code, msg)

            self._circuit.record_success()
            return cast("dict[str, Any] | list[Any]", resp.json().get("data", {}))
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

    def _map_lang(self, lang: str) -> str:
        """Convert 2-char language code to 3-char TVDB code.

        Args:
            lang: 2-char language code (e.g. "fr").

        Returns:
            3-char TVDB code (e.g. "fra"). Returns input unchanged
            if already 3+ chars or not in LANG_MAP.
        """
        if len(lang) <= 2:
            return self.LANG_MAP.get(lang, lang)
        return lang

    # -- Protocol methods (MetadataProvider) --

    def search(self, title: str, year: int | None = None, media_type: str = "movie") -> list[dict[str, Any]]:
        """Search for a media item by title (Protocol method).

        Dispatches to search_series() for TV shows.

        Args:
            title: Media title to search for.
            year: Optional year to narrow results.
            media_type: "movie" or "tv" (TVDB is primarily for TV).

        Returns:
            List of raw search result dicts.
        """
        return self.search_series(title, year)

    def get_details(self, media_id: int, media_type: str = "movie") -> dict[str, Any]:
        """Get full details for a media item (Protocol method).

        Dispatches to get_series().

        Args:
            media_id: TVDB series ID.
            media_type: Ignored — TVDB client only handles series.

        Returns:
            Dict with series details, genres, seasons, and remote IDs.
        """
        return self.get_series(media_id)

    def get_artwork_urls(self, media_id: int, media_type: str = "movie") -> list[dict[str, Any]]:
        """Get artwork URLs for a series (Protocol method).

        Fetches all artworks and maps TVDB types to our standard types.

        Args:
            media_id: TVDB series ID.
            media_type: Ignored — TVDB client only handles series.

        Returns:
            List of artwork dicts with type, url, language, season keys.
        """
        artworks_data = self.get_series_artworks(media_id)
        result: list[dict[str, Any]] = []
        for art in artworks_data:
            art_type_id = art.get("type", 0)
            # Map TVDB artwork types to our standard types
            if art_type_id == ARTWORK_POSTER_SERIES:
                art_type = "poster"
            elif art_type_id == ARTWORK_BACKGROUND_SERIES:
                art_type = "landscape"  # TVDB has no "landscape" — Background is equivalent
            elif art_type_id == ARTWORK_POSTER_SEASON:
                art_type = "season_poster"
            else:
                continue  # Skip other types

            result.append({
                "type": art_type,
                "url": art.get("image", ""),
                "language": art.get("language"),
                "season": art.get("season"),
            })
        return result

    # -- Type-specific methods --

    def search_series(self, title: str, year: int | None = None) -> list[dict[str, Any]]:
        """Search for TV series by title.

        Uses /search endpoint with type=series. Results use snake_case
        field names (image_url, first_air_time, tvdb_id).

        Args:
            title: Series title to search for.
            year: Optional first air date year to narrow results.

        Returns:
            List of search result dicts.
        """
        params: dict[str, Any] = {"query": title, "type": "series"}
        if year is not None:
            params["year"] = year
        data = self._get("/search", params)
        # /search returns a list directly in data (envelope flattened via cast in _get)
        return cast(list[dict[str, Any]], data) if isinstance(data, list) else []

    def get_series(self, series_id: int) -> dict[str, Any]:
        """Get extended series details.

        Uses short=true to exclude artworks/characters/trailers
        (reduces payload). Returns genres, seasons, remoteIds,
        contentRatings, and basic series info.

        Note: short=true sets excluded arrays to null (not []).

        Args:
            series_id: TVDB series ID.

        Returns:
            Dict with extended series data.
        """
        data = self._get(f"/series/{series_id}/extended", {"short": "true"})
        return data if isinstance(data, dict) else {}

    def get_season_episodes(self, series_id: int, season: int) -> list[dict[str, Any]]:
        """Get episodes for a specific season.

        Uses /series/{id}/episodes/default with season filter.
        Pagination is 0-indexed (page=0 is the first page).
        Without season filter, returns ALL episodes including specials.

        Args:
            series_id: TVDB series ID.
            season: Season number to filter.

        Returns:
            List of episode dicts with id, name, number, seasonNumber,
            aired, runtime, overview, and image.
        """
        data = self._get(
            f"/series/{series_id}/episodes/default",
            {"season": season, "page": 0},
        )
        # Response wraps episodes in data.episodes
        if isinstance(data, dict):
            return cast(list[dict[str, Any]], data.get("episodes", []))
        return []

    def get_episode_translation(self, episode_id: int, lang: str = "fra") -> dict[str, Any] | None:
        """Get translated title and overview for an episode.

        Uses 3-char language codes (fra, eng, spa).
        Auto-converts 2-char codes via LANG_MAP.

        Args:
            episode_id: TVDB episode ID.
            lang: Language code (3-char preferred, 2-char auto-converted).

        Returns:
            Dict with name, overview, and language. None if translation
            is not available.
        """
        lang_3 = self._map_lang(lang)
        try:
            data = self._get(f"/episodes/{episode_id}/translations/{lang_3}")
            return data if isinstance(data, dict) else None
        except TVDBError as e:
            if e.http_status == 404:
                logger.debug("No %s translation for episode %d", lang_3, episode_id)
                return None
            raise

    def get_series_artworks(self, series_id: int, type_id: int | None = None) -> list[dict[str, Any]]:
        """Get artworks for a series.

        Returns a SeriesExtendedRecord — artworks are in data.artworks.
        Filter by type via ?type={id} for efficiency.

        TVDB has no "landscape" type — Background (type 3, 1920x1080)
        is the closest equivalent.

        Args:
            series_id: TVDB series ID.
            type_id: Optional artwork type ID to filter (e.g. 2=poster).

        Returns:
            List of artwork dicts with image URL, language, type, etc.
        """
        params: dict[str, Any] = {}
        if type_id is not None:
            params["type"] = type_id
        data = self._get(f"/series/{series_id}/artworks", params)
        # Artworks are nested in the extended record
        if isinstance(data, dict):
            return cast(list[dict[str, Any]], data.get("artworks") or [])
        return []

    def get_artwork_types(self) -> dict[int, str]:
        """Get and cache all artwork type definitions.

        Called once at startup — data is stable (27 types).
        Caches the result for subsequent calls.

        Returns:
            Dict mapping type ID to type name.
        """
        if self._artwork_types is not None:
            return self._artwork_types

        data = self._get("/artwork/types")
        self._artwork_types = {}
        if isinstance(data, list):
            for item in data:
                self._artwork_types[item["id"]] = item["name"]
        return self._artwork_types

    @staticmethod
    def get_remote_ids(series_data: dict[str, Any]) -> dict[str, str | None]:
        """Extract IMDB and TMDB IDs from series remoteIds.

        TMDB source types: 10=movies, 12=TV series, 15=people, 28=collections.
        For series, use type=12 (not 10 which is for movies).
        IMDB uses type=2.

        Args:
            series_data: Extended series data from get_series().

        Returns:
            Dict with "imdb_id" and "tmdb_id" (None if not found).
        """
        remote_ids = series_data.get("remoteIds") or []
        result: dict[str, str | None] = {"imdb_id": None, "tmdb_id": None}

        for rid in remote_ids:
            source_type = rid.get("type")
            source_name = rid.get("sourceName", "")
            rid_id = rid.get("id", "")

            if source_type == TVDB_SOURCE_IMDB or "IMDB" in source_name:
                result["imdb_id"] = rid_id
            elif source_type == TVDB_SOURCE_TMDB_TV or "TheMovieDB" in source_name:
                result["tmdb_id"] = rid_id

        return result

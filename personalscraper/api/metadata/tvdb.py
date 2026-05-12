"""TVDB v4 metadata provider.

Bootstrap login at init: one-shot HttpTransport(NoAuth) → POST /login → JWT.
Main client uses BearerAuth(jwt). All responses unwrapped via _tvdb_parsers.unwrap().
Returns typed models from _base.py. Zero untyped dicts in public signatures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from personalscraper.api._contracts import TVDB_BOOTSTRAP, MediaType, ProviderName
from personalscraper.api.metadata._base import (
    ArtworkItem,
    MediaDetails,
    MetadataClient,
    SearchResult,
    SeasonDetails,
    Video,
)
from personalscraper.api.metadata._tvdb_parsers import (
    map_language,
    parse_artworks,
    parse_media_details,
    parse_search_result,
    parse_season_details,
    parse_videos,
    unwrap,
)
from personalscraper.api.transport._auth import BearerAuth, NoAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus

log = get_logger("api.tvdb")

_DEFAULT_CIRCUIT = CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0)
_DEFAULT_RATE = RateLimitPolicy(requests_per_second=20.0)
_DEFAULT_RETRY = RetryPolicy(max_attempts=4)


class TVDBClient(MetadataClient):
    """TVDB v4 API metadata provider.

    Authentication: POST /login with API key → JWT Bearer token (TTL = 30 days).
    Bootstrap done once at __init__ via a one-shot HttpTransport(NoAuth).
    Main transport uses BearerAuth(jwt).

    Implements MetadataProvider Protocol for TV series (primary) and movies (secondary).
    get_keywords() and get_notations() raise NotImplementedError — TVDB has no equivalent.
    """

    REQUIRED_CREDS: ClassVar[list[str]] = ["TVDB_API_KEY"]
    provider_name: ClassVar[str] = "tvdb"

    def __init__(
        self,
        api_key: str,
        *,
        language: str = "fr-FR",
        circuit: CircuitPolicy | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize TVDB client with bootstrap login.

        Args:
            api_key: TVDB API key (Negotiated Contract type, no PIN needed).
            language: Default language for API queries (2-char pipeline code, e.g. "fr").
            circuit: Optional custom CircuitPolicy override for bootstrap + main transport.
            event_bus: Optional :class:`EventBus` propagated to the bootstrap
                and main HTTP transports so their circuit breakers emit
                :class:`CircuitBreakerOpened` / ``Closed`` / ``HalfOpened``
                on transitions. Optional in Phase 4; required in Phase 5.2.
        """
        self._api_key = api_key
        self._tvdb_lang = map_language(language)
        _cb = circuit or _DEFAULT_CIRCUIT

        # Bootstrap login with NoAuth
        bootstrap_policy = TransportPolicy(
            provider_name=TVDB_BOOTSTRAP,
            base_url="https://api4.thetvdb.com/v4",
            auth=NoAuth(),
            timeout_seconds=15.0,
            retry=_DEFAULT_RETRY,
            circuit=_cb,
            rate_limit=_DEFAULT_RATE,
        )
        with HttpTransport(bootstrap_policy, event_bus=event_bus) as bootstrap:
            resp = bootstrap.post("/login", data={"apikey": api_key})
        if not isinstance(resp, dict):
            raise TypeError(f"Expected dict response from TVDB login, got {type(resp).__name__}")
        jwt = resp["data"]["token"]

        # Main transport with JWT
        main_policy = TVDBClient.policy(jwt, circuit=_cb)
        super().__init__(transport=HttpTransport(main_policy, event_bus=event_bus), language=language)

    @property
    def circuit(self) -> Any:
        """Expose the underlying circuit breaker for external consumers."""
        return self._transport._circuit

    @classmethod
    def policy(
        cls,
        jwt_token: str,
        *,
        circuit: CircuitPolicy | None = None,
    ) -> TransportPolicy:
        """Build the TransportPolicy for TVDB.

        Args:
            jwt_token: JWT Bearer token from POST /login.
            circuit: Optional custom CircuitPolicy override.

        Returns:
            A TransportPolicy configured for TVDB v4.
        """
        return TransportPolicy(
            provider_name=ProviderName.TVDB,
            base_url="https://api4.thetvdb.com/v4",
            auth=BearerAuth(jwt_token),
            timeout_seconds=15.0,
            retry=_DEFAULT_RETRY,
            circuit=circuit if circuit is not None else _DEFAULT_CIRCUIT,
            rate_limit=_DEFAULT_RATE,
        )

    # -- Helpers ------------------------------------------------------------

    def _get(self, path: str, params: dict[str, object] | None = None) -> Any:
        """GET request with envelope unwrapping.

        Args:
            path: API path appended to base URL.
            params: Optional query parameters.

        Returns:
            Unwrapped data payload (dict or list).
        """
        raw = self._transport.get(path, params=params)
        if not isinstance(raw, dict):
            raise TypeError(f"Expected dict response from TVDB, got {type(raw).__name__}")
        return unwrap(raw)

    def _get_dict(self, path: str, params: dict[str, object] | None = None) -> Any:
        """GET request returning unwrapped dict.

        Args:
            path: API path.
            params: Optional query parameters.

        Returns:
            Unwrapped data payload as dict.

        Raises:
            TypeError: If the unwrapped data is a list.
        """
        result = self._get(path, params=params)
        if isinstance(result, list):
            raise TypeError(f"Expected dict from {path}, got list")
        return result

    def map_language(self, pipeline_code: str) -> str:
        """Map a 2-char pipeline language code to 3-char TVDB code.

        Args:
            pipeline_code: 2-char ISO code (e.g. "fr").

        Returns:
            3-char TVDB code (e.g. "fra").
        """
        return map_language(pipeline_code)

    # -- Protocol: search ---------------------------------------------------

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[SearchResult]:
        """Search TVDB for series or movies.

        Args:
            title: Search query.
            year: Optional year filter.
            media_type: "movie" or "tv" (→ "series" for TVDB).

        Returns:
            List of SearchResult.
        """
        tvdb_type = "series" if media_type == "tv" else "movie"
        params: dict[str, object] = {"query": title, "type": tvdb_type}
        if year is not None:
            params["year"] = str(year)
        return self.search_series(title, year=year) if media_type == "tv" else self.search_movie(title, year=year)

    def search_series(
        self,
        title: str,
        year: int | None = None,
    ) -> list[SearchResult]:
        """Search TVDB for TV series.

        Args:
            title: Series title.
            year: Optional first-air year filter.

        Returns:
            List of SearchResult.
        """
        params: dict[str, object] = {"query": title, "type": "series"}
        if year is not None:
            params["year"] = str(year)
        data = self._get("/search", params=params)
        if not isinstance(data, list):
            return []
        return [parse_search_result(item, "tvdb") for item in data]

    def search_movie(
        self,
        title: str,
        year: int | None = None,
    ) -> list[SearchResult]:
        """Search TVDB for movies.

        Args:
            title: Movie title.
            year: Optional release year filter.

        Returns:
            List of SearchResult.
        """
        params: dict[str, object] = {"query": title, "type": "movie"}
        if year is not None:
            params["year"] = str(year)
        data = self._get("/search", params=params)
        if not isinstance(data, list):
            return []
        return [parse_search_result(item, "tvdb") for item in data]

    # -- Protocol: get_details ----------------------------------------------

    def get_details(self, media_id: str, media_type: MediaType = MediaType.MOVIE) -> MediaDetails:
        """Fetch full details for a series or movie.

        Args:
            media_id: TVDB ID.
            media_type: "movie" or "tv".

        Returns:
            Populated MediaDetails.
        """
        if media_type == "tv":
            return self.get_series(int(media_id))
        return self.get_movie(int(media_id))

    def get_series(self, series_id: int) -> MediaDetails:
        """Fetch extended series details.

        Args:
            series_id: TVDB series ID.

        Returns:
            Populated MediaDetails.
        """
        raw = self._get_dict(f"/series/{series_id}/extended")
        return parse_media_details(raw, "tvdb")

    def get_movie(self, movie_id: int) -> MediaDetails:
        """Fetch extended movie details.

        Args:
            movie_id: TVDB movie ID.

        Returns:
            Populated MediaDetails.
        """
        raw = self._get_dict(f"/movies/{movie_id}/extended")
        return parse_media_details(raw, "tvdb")

    # -- Protocol: get_artwork_urls -----------------------------------------

    def get_artwork_urls(self, media_id: str, media_type: MediaType = MediaType.MOVIE) -> list[ArtworkItem]:
        """Fetch artwork for a series or movie.

        Args:
            media_id: TVDB ID.
            media_type: "movie" or "tv".

        Returns:
            List of ArtworkItem.
        """
        # TVDB v4 endpoints: /movies/{id}/extended and /series/{id}/extended.
        # "tv" → "series" — naive pluralization (/tvs/) returns 400.
        endpoint = "series" if media_type == "tv" else "movies"
        raw = self._get_dict(f"/{endpoint}/{media_id}/extended")
        return parse_artworks(raw.get("artworks", []) or [])

    # -- Protocol: get_season -----------------------------------------------

    def get_season(self, tv_id: str, season: int) -> SeasonDetails:
        """Fetch TV season episodes.

        Uses /series/{id}/episodes/default with required page param.
        Iterates pages if more than 100 episodes.

        Args:
            tv_id: TVDB series ID.
            season: Season number (1-indexed).

        Returns:
            SeasonDetails with parsed episodes.
        """
        return self.get_series_episodes(int(tv_id), season)

    def get_series_episodes(self, series_id: int, season: int) -> SeasonDetails:
        """Fetch episodes for a specific season.

        Args:
            series_id: TVDB series ID.
            season: Season number.

        Returns:
            SeasonDetails.
        """
        all_episodes: list[dict[str, object]] = []
        page = 0
        while True:
            params: dict[str, object] = {"season": season, "page": page}
            raw = self._get_dict(f"/series/{series_id}/episodes/default", params=params)
            episodes = raw.get("episodes", []) or []
            all_episodes.extend(episodes)
            links = raw.get("links", {}) or {}
            if not links.get("next"):
                break
            page += 1

        raw["episodes"] = all_episodes
        return parse_season_details(raw, "tvdb", str(series_id), season)

    # -- Protocol: get_videos -----------------------------------------------

    def get_videos(self, media_id: str, media_type: MediaType, language: str) -> list[Video]:
        """Fetch videos/trailers for a series or movie.

        Videos are extracted from the extended response's ``trailers`` array.

        Args:
            media_id: TVDB ID.
            media_type: "movie" or "tv".
            language: ISO 639-1 language code.

        Returns:
            List of Video objects.
        """
        # TVDB v4 endpoints: /movies/{id}/extended and /series/{id}/extended.
        # "tv" → "series" — naive pluralization (/tvs/) returns 400.
        endpoint = "series" if media_type == "tv" else "movies"
        raw = self._get_dict(f"/{endpoint}/{media_id}/extended")
        return parse_videos(raw.get("trailers", []) or [])

    # -- Protocol: get_keywords / get_notations (not supported by TVDB) -----

    def get_keywords(self, media_id: str, media_type: MediaType) -> list[str]:
        """TVDB has no keywords endpoint. Falls back to TMDB."""
        raise NotImplementedError("tvdb does not support keywords")

    def get_notations(self, media_id: str, media_type: MediaType) -> None:
        """TVDB score is a popularity rank, not a rating."""
        raise NotImplementedError("tvdb does not support notations")

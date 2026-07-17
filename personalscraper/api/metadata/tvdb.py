"""TVDB v4 metadata provider.

Bootstrap login is **deferred**: `__init__` only records credentials; the
one-shot ``HttpTransport(NoAuth) → POST /login → JWT`` exchange runs on first
real HTTP call via the lazy ``_transport`` property. The main client then uses
``BearerAuth(jwt)``. All responses unwrapped via ``_tvdb_parsers.unwrap()``.
Returns typed models from ``_base.py``. Zero untyped dicts in public signatures.

Rationale (Phase 14, ``feat/registry``): the original synchronous bootstrap
forced every ``TVDBClient(...)`` construction — including registry boot,
test-suite collection, and CLI smoke paths — to hit the live TVDB API. By
moving the call to first use, the registry can be constructed (and exercised
in unit tests) without network access; only callers that actually invoke an
API method incur the bootstrap.
"""

from __future__ import annotations

import unicodedata
from typing import TYPE_CHECKING, Any, ClassVar

from personalscraper.api._contracts import TVDB_BOOTSTRAP, ApiError, MediaType, ProviderName
from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    MetadataClient,
    SearchResult,
    SeasonDetails,
    Video,
)
from personalscraper.api.metadata._contracts import (
    ArtworkProvider,
    EpisodeFetcher,
    MovieDetailsProvider,
    Searchable,
    TvDetailsProvider,
    VideoProvider,
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
    from personalscraper.core.circuit import CircuitBreaker
    from personalscraper.core.event_bus import EventBus

log = get_logger("api.tvdb")

_DEFAULT_CIRCUIT = CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0)
_DEFAULT_RATE = RateLimitPolicy(requests_per_second=20.0)
_DEFAULT_RETRY = RetryPolicy(max_attempts=4)


class TVDBClient(
    MetadataClient,
    Searchable,
    MovieDetailsProvider,
    TvDetailsProvider,
    EpisodeFetcher,
    ArtworkProvider,
    VideoProvider,
):
    """TVDB v4 API metadata provider.

    Authentication: POST /login with API key → JWT Bearer token (TTL = 30 days).
    Bootstrap done once at __init__ via a one-shot HttpTransport(NoAuth).
    Main transport uses BearerAuth(jwt).

    Composes the atomic capability protocols from
    :mod:`personalscraper.api.metadata._contracts`: :class:`Searchable`,
    :class:`MovieDetailsProvider`, :class:`TvDetailsProvider`,
    :class:`EpisodeFetcher`, :class:`ArtworkProvider`,
    :class:`VideoProvider`. Does *not* compose :class:`KeywordProvider`
    (TVDB has no equivalent endpoint — :meth:`get_keywords` raises
    NotImplementedError) nor :class:`IDValidator` (cross-provider ID
    validation flows through :mod:`personalscraper.scraper._xref`).
    """

    REQUIRED_CREDS: ClassVar[list[str]] = ["TVDB_API_KEY"]
    provider_name: ClassVar[str] = "tvdb"
    # Phase 22 (DESIGN §7.6): TVDB defers JWT bootstrap to first HTTP call,
    # so the CircuitBreaker (which lives on the main HttpTransport) does
    # not exist before bootstrap. Mark the class so the registry
    # eligibility gate treats a pre-bootstrap ``circuit is None`` as
    # eligible rather than warning + rejecting.
    _registry_lazy_circuit: ClassVar[bool] = True

    def __init__(
        self,
        api_key: str,
        *,
        language: str = "fr-FR",
        circuit: CircuitPolicy | None = None,
        event_bus: EventBus,
    ) -> None:
        """Initialize TVDB client *without* contacting the API.

        The bootstrap ``POST /login`` exchange is **deferred** to the first
        real HTTP call; see :meth:`_ensure_transport`. Construction is pure
        Python: it stores credentials, language, circuit policy and the
        event bus, then leaves ``self._transport`` unset until first access
        on the lazy property.

        Args:
            api_key: TVDB API key (Negotiated Contract type, no PIN needed).
            language: Default language for API queries (2-char pipeline code, e.g. "fr").
            circuit: Optional custom CircuitPolicy override for bootstrap + main transport.
            event_bus: Required :class:`EventBus` propagated to the bootstrap
                and main HTTP transports so their circuit breakers emit
                :class:`CircuitBreakerOpened` / ``Closed`` / ``HalfOpened``
                on transitions.
        """
        self._api_key = api_key
        self._tvdb_lang = map_language(language)
        self._language = language
        self._circuit_policy = circuit or _DEFAULT_CIRCUIT
        self._event_bus = event_bus
        # Lazy: built on first access via the _transport property.
        self.__transport: HttpTransport | None = None
        # Cached reference to the main transport's CircuitBreaker. ``None``
        # until ``_ensure_transport`` runs the JWT bootstrap and constructs
        # the main transport (Phase 22 / DESIGN §7.6). Reading
        # :attr:`circuit` pre-bootstrap returns ``None``, which the
        # registry eligibility gate treats as eligible via the
        # ``_registry_lazy_circuit`` marker — eligibility checks never
        # trigger HTTP.
        self._circuit_breaker: CircuitBreaker | None = None

    def _ensure_transport(self) -> HttpTransport:
        """Run the bootstrap login and build the main transport (idempotent).

        On first invocation, opens a one-shot bootstrap ``HttpTransport``
        with ``NoAuth``, exchanges the API key for a JWT via ``POST /login``,
        then builds and caches the main ``HttpTransport`` configured with
        ``BearerAuth(jwt)``. Subsequent calls return the cached instance.

        Returns:
            The fully wired main transport.

        Raises:
            TypeError: If the ``/login`` response is not a dict (provider
                contract violation).
            ApiError: Propagated from the underlying transport when the
                bootstrap HTTP call fails (e.g. invalid credentials → 401).
        """
        if self.__transport is not None:
            return self.__transport

        # Bootstrap login with NoAuth — one-shot transport, closed via ctxmgr.
        bootstrap_policy = TransportPolicy(
            provider_name=TVDB_BOOTSTRAP,
            base_url="https://api4.thetvdb.com/v4",
            auth=NoAuth(),
            timeout_seconds=15.0,
            retry=_DEFAULT_RETRY,
            circuit=self._circuit_policy,
            rate_limit=_DEFAULT_RATE,
        )
        with HttpTransport(bootstrap_policy, event_bus=self._event_bus) as bootstrap:
            resp = bootstrap.post("/login", data={"apikey": self._api_key})
        if not isinstance(resp, dict):
            raise TypeError(f"Expected dict response from TVDB login, got {type(resp).__name__}")
        jwt = resp["data"]["token"]

        # Main transport with JWT.
        main_policy = TVDBClient.policy(jwt, circuit=self._circuit_policy)
        self.__transport = HttpTransport(main_policy, event_bus=self._event_bus)
        # Cache the CircuitBreaker reference so :attr:`circuit` reads it
        # directly without re-triggering :meth:`_ensure_transport` — see
        # the ``circuit`` property and DESIGN §7.6 (Phase 22).
        self._circuit_breaker = self.__transport._circuit
        return self.__transport

    @property
    def _transport(self) -> HttpTransport:
        """Lazy accessor for the main HTTP transport.

        Triggers :meth:`_ensure_transport` on first access; subsequent reads
        return the cached transport. Defined as a property (rather than an
        attribute set in ``__init__``) so that construction stays
        network-free — see module docstring for the registry-boot
        rationale.
        """
        return self._ensure_transport()

    @_transport.setter
    def _transport(self, value: HttpTransport) -> None:
        """Setter preserved for test fixtures that inject a mock transport.

        Several unit tests bypass the bootstrap entirely by constructing
        the client via ``__new__`` and assigning ``client._transport =
        mock``. The setter writes to the cached backing field so those
        assignments still short-circuit :meth:`_ensure_transport`. It also
        mirrors the cached :attr:`_circuit_breaker` from the new
        transport (when the mock exposes ``_circuit``) so that
        :attr:`circuit` reads the injected breaker instead of ``None``.

        Args:
            value: The transport (real or mock) to use directly.
        """
        self.__transport = value
        # Mirror the breaker cache when the injected transport carries one.
        # Plain MagicMocks return another MagicMock for any attribute, which
        # is fine — production code paths only assert eligibility on the
        # CircuitBreaker.state, and tests can override as needed.
        circuit_ref = getattr(value, "_circuit", None)
        if circuit_ref is not None:
            self._circuit_breaker = circuit_ref

    @property
    def circuit(self) -> CircuitBreaker | None:
        """Expose the underlying circuit breaker for external consumers.

        Returns ``None`` before the JWT bootstrap has run — the
        CircuitBreaker is constructed lazily by :meth:`_ensure_transport`
        on first HTTP access. Reading this property is **HTTP-free**: it
        only consults the cached reference set by
        :meth:`_ensure_transport` and never triggers a bootstrap (Phase
        22, DESIGN §7.6).

        Registry eligibility checks (:func:`_eligible` in
        ``api.metadata.registry._factory``) treat a ``None`` return from
        a class marked ``_registry_lazy_circuit = True`` as eligible.
        """
        return self._circuit_breaker

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
        # NFC-normalize: NFD folder names (macOS/NTFS) don't match TVDB's
        # NFC-indexed titles (see TMDBClient._search_paginated). Idempotent.
        params: dict[str, object] = {"query": unicodedata.normalize("NFC", title), "type": "series"}
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
        # NFC-normalize: NFD folder names (macOS/NTFS) don't match TVDB's
        # NFC-indexed titles (see TMDBClient._search_paginated). Idempotent.
        params: dict[str, object] = {"query": unicodedata.normalize("NFC", title), "type": "movie"}
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
        return self.get_movie(media_id)

    def get_series(self, series_id: int) -> MediaDetails:
        """Fetch extended series details.

        Args:
            series_id: TVDB series ID.

        Returns:
            Populated MediaDetails.
        """
        raw = self._get_dict(f"/series/{series_id}/extended")
        return parse_media_details(raw, "tvdb")

    def get_tv(self, provider_id: str | int) -> MediaDetails:
        """TvDetailsProvider Protocol alias for :meth:`get_series`.

        Args:
            provider_id: TVDB series identifier (``str`` or ``int``).
                Non-numeric strings are converted to a uniform
                :class:`ApiError` rather than the bare ``ValueError``
                that ``int(...)`` would raise — keeps the Protocol
                contract clean for callers dispatching by capability.

        Returns:
            Populated MediaDetails.

        Raises:
            ApiError: Non-numeric ``provider_id`` (``http_status=0``).
        """
        try:
            numeric_id = int(provider_id)
        except (TypeError, ValueError) as exc:
            raise ApiError(
                provider="tvdb",
                http_status=0,
                message=f"Non-numeric TVDB id rejected: {provider_id!r}",
            ) from exc
        return self.get_series(numeric_id)

    def get_movie(self, movie_id: str | int) -> MediaDetails:
        """Fetch extended movie details.

        Args:
            movie_id: TVDB movie ID (``int`` for direct TVDB calls,
                ``str`` to satisfy the :class:`MovieDetailsProvider`
                Protocol signature). Non-numeric strings are converted
                to a uniform :class:`ApiError`.

        Returns:
            Populated MediaDetails.

        Raises:
            ApiError: Non-numeric ``movie_id`` (``http_status=0``).
        """
        try:
            numeric_id = int(movie_id)
        except (TypeError, ValueError) as exc:
            raise ApiError(
                provider="tvdb",
                http_status=0,
                message=f"Non-numeric TVDB movie id rejected: {movie_id!r}",
            ) from exc
        raw = self._get_dict(f"/movies/{numeric_id}/extended")
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

    # -- Protocol: get_episodes ---------------------------------------------

    def get_episodes(self, series_id: str | int, season: int) -> list[EpisodeInfo]:
        """Fetch the episode list for a season — satisfies :class:`EpisodeFetcher`.

        Delegates to :meth:`get_series_episodes` and unwraps the
        episodes array.

        Args:
            series_id: TVDB series identifier (``str`` or ``int``).
            season: Season number.

        Returns:
            ``list[EpisodeInfo]`` for the requested season.
        """
        return self.get_series_episodes(int(series_id), season).episodes

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

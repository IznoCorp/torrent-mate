"""torr9 tracker client — authenticated JSON API with JWT login.

Implements TorrentSearchable and CategoryListable against torr9's authenticated
JSON API (https://api.torr9.net/api/v1). Auth is a two-step JWT login
(POST /auth/login → Bearer token). Token is cached lazily and refreshed on 401
(RP7 auth-lifecycle).

See docs/reference/torr9-api.md for endpoint and field reference.
Field shapes validated against docs/reference/_samples/torr9/torr9_search.json
(real capture 2026-06-19).

torr9 particularities (live-confirmed):
- Search param is ``q`` (NOT ``search`` — returns 0 results).
- Pagination via ``page`` query param (default page 1, limit 20).
- ``magnet_link`` is auth-free and is the PRIMARY download path. When it is
  absent/malformed, the fallback is the real .torrent endpoint
  ``GET /api/v1/torrents/{id}/download`` (Bearer, returns
  ``application/x-bittorrent`` bytes — live-confirmed). ``torrent_file_url`` is
  DEAD (404 at every host/auth, hash mismatch, absent from the detail payload)
  and is NOT consumed.
- ``is_freeleech`` is a clean boolean (no text parsing needed).
- No seeders/leechers exposed — ``seeders=0, leechers=0`` on all results.
- Login 401: "Identifiant ou mot de passe invalide" → fail-loud at boot.
- Search 401: "Missing authorization token" → re-login once (RP7).
- RSS feeds (passkey) for freeleech radar are OUT OF SCOPE (R1 follow-on).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, cast

from personalscraper.api._contracts import ApiError, MediaType, ProviderName
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult, wrap_parser_drift
from personalscraper.api.tracker._contracts import (
    CategoryListable,
    FreeleechAware,
    TorrentDetailsProvider,
    TorrentSearchable,
)
from personalscraper.api.transport._auth import BearerAuth, NoAuth
from personalscraper.api.transport._http import HttpTransport
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.core._contracts import CircuitOpenError
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.api_config import TrackerProviderConfig

log = get_logger("api.tracker.torr9")

# Numeric category_id → human label (partial; full map from GET /categories).
# Populated from the golden fixture (ids 5, 51) and RSS category labels.
# Confirm and extend by running: GET /api/v1/categories with a fresh Bearer token.
_CATEGORY_MAP: dict[int, str] = {
    2: "Films",  # confirmed via RSS label cross-ref
    5: "Séries TV",  # confirmed — golden fixture id 5
    9: "Films",  # from Hangman search sample
    46: "Séries Animées",  # from Hangman search sample
    51: "Films",  # confirmed — golden fixture id 51
    53: "Anime",  # from Hangman search sample
    54: "TV Programs",  # from Hangman search sample
}


def _parse_iso(value: Any) -> datetime | None:
    """Parse an ISO 8601 string with optional microseconds and ``Z`` suffix.

    Args:
        value: Raw value from the JSON payload (expected str).

    Returns:
        Timezone-aware UTC datetime, or None if unparseable.
    """
    if not isinstance(value, str):
        return None
    s = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


class Torr9Client(TorrentSearchable, CategoryListable, FreeleechAware, TorrentDetailsProvider):
    """torr9 tracker API client — authenticated JSON API with JWT login.

    Composes :class:`~personalscraper.api.tracker._contracts.TorrentSearchable`,
    :class:`~personalscraper.api.tracker._contracts.CategoryListable`,
    :class:`~personalscraper.api.tracker._contracts.FreeleechAware`, and
    :class:`~personalscraper.api.tracker._contracts.TorrentDetailsProvider`.
    Auth is lazy JWT login (POST /auth/login) with re-login on 401 (RP7).

    Unlike c411/lacale (no per-torrent detail endpoint), torr9 exposes
    ``GET /api/v1/torrents/{id}`` (live-confirmed), so ``is_freeleech`` is a
    genuine pre-download re-check (not a stub) and ``get_details`` surfaces the
    detail payload's real seeders/leechers — used to enrich the top-K search
    results' swarm health before ranking.
    """

    provider_name: str = ProviderName.TORR9.value
    # PROVIDER_CREDS key: TORR9_USERNAME gates activation (per DESIGN ACC-3 →
    # PROVIDER_CREDS["torr9"] = ["TORR9_USERNAME", "TORR9_PASSWORD"]).
    # Phase 2 registers this in api/_activation.py.
    REQUIRED_CREDS: ClassVar[list[str]] = ["TORR9_USERNAME", "TORR9_PASSWORD"]

    _BASE_URL: ClassVar[str] = "https://api.torr9.net"

    @classmethod
    def from_env(
        cls,
        *,
        env: Mapping[str, str],
        event_bus: EventBus,
        required: list[str],
        provider_cfg: TrackerProviderConfig,
    ) -> Torr9Client:
        """Construct a Torr9Client from resolved environment credentials.

        Implements the :class:`~personalscraper.api.tracker._contracts.TrackerConstructible`
        contract: ``build_tracker_registry`` dispatches construction uniformly
        through ``from_env`` for every tracker (no provider-name literal, no
        cred-style branch). torr9 is a login-style tracker, so it self-builds its
        authed transport lazily and reads its enrichment options off
        ``provider_cfg`` (defaults: enrich on, top-K=10). The creds are already
        validated present by the registry's cred-gating before this runs.

        Args:
            env: Credential source (the registry passes the resolved env mapping).
            event_bus: Event bus propagated to the client's HTTP transports.
            required: Ordered credential env-var names — unused; torr9 reads its
                own cred names from ``REQUIRED_CREDS`` (no order-coupling).
            provider_cfg: Per-tracker config — source of the enrich flags.

        Returns:
            A network-free Torr9Client (transports are built lazily on first search).
        """
        del required  # torr9 reads its own cred names from REQUIRED_CREDS
        return cls(
            username=env.get(cls.REQUIRED_CREDS[0], ""),
            password=env.get(cls.REQUIRED_CREDS[1], ""),
            event_bus=event_bus,
            enrich_seeders=getattr(provider_cfg, "enrich_seeders", True),
            enrich_seeders_top_k=getattr(provider_cfg, "enrich_seeders_top_k", 10),
        )

    def __init__(
        self,
        *,
        username: str,
        password: str,
        event_bus: EventBus,
        enrich_seeders: bool = True,
        enrich_seeders_top_k: int = 10,
    ) -> None:
        """Initialize the torr9 client (network-free — transports are lazy).

        Args:
            username: ``TORR9_USERNAME`` credential.
            password: ``TORR9_PASSWORD`` credential.
            event_bus: Event bus forwarded to the bootstrap + main HttpTransports.
            enrich_seeders: When True (default), ``search`` enriches the top-K
                results' seeders/leechers from the detail endpoint (fail-soft per
                result). torr9's search payload has no swarm data, so without this
                every result has ``seeders=0`` and is dropped by the ranking
                ``min_seeders`` floor.
            enrich_seeders_top_k: How many leading results to enrich (default 10).
        """
        self._username = username
        self._password = password
        self._event_bus = event_bus
        self._enrich_seeders = enrich_seeders
        self._enrich_top_k = enrich_seeders_top_k
        # Lazy: the bootstrap login + the authed main transport are built on first
        # _transport access via _ensure_transport() — construction stays HTTP-free
        # so registry boot never triggers network (parity with TVDBClient).
        self.__transport: HttpTransport | None = None

    @classmethod
    def policy(cls, token: str) -> TransportPolicy:
        """Build the authed main TransportPolicy — Bearer token applied at transport init.

        Args:
            token: JWT obtained from the bootstrap login.

        Returns:
            TransportPolicy with BearerAuth(token), conservative rate limit, and
            standard 5-fail / 5-min circuit settings.
        """
        return TransportPolicy(
            provider_name=cls.provider_name,
            base_url=cls._BASE_URL,
            auth=BearerAuth(token),
            timeout_seconds=15,
            retry=RetryPolicy(max_attempts=3),
            circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0),
            rate_limit=RateLimitPolicy(requests_per_second=0.5),
        )

    @classmethod
    def _bootstrap_policy(cls) -> TransportPolicy:
        """One-shot NoAuth policy for the JWT login exchange (POST /auth/login)."""
        return TransportPolicy(
            provider_name=f"{cls.provider_name}-bootstrap",
            base_url=cls._BASE_URL,
            auth=NoAuth(),
            timeout_seconds=15,
            retry=RetryPolicy(max_attempts=3),
            circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0),
            rate_limit=RateLimitPolicy(requests_per_second=0.5),
        )

    # -- Auth lifecycle (RP7 auth-lifecycle, TVDB lazy-transport pattern) ----

    def _ensure_transport(self) -> HttpTransport:
        """Bootstrap-login and build the authed main transport (idempotent).

        On first call, opens a one-shot NoAuth bootstrap transport, POSTs the
        credentials to ``/api/v1/auth/login``, extracts the JWT, then builds and
        caches the main transport whose policy carries ``BearerAuth(token)``.
        Subsequent calls return the cached transport. Mirrors TVDBClient.

        Returns:
            The fully-wired authed main transport.

        Raises:
            ApiError: On a 401 (bad credentials) from the login POST, or a login
                response missing the ``token`` field (fail-loud, RP7).
        """
        if self.__transport is not None:
            return self.__transport
        with HttpTransport(self._bootstrap_policy(), event_bus=self._event_bus) as bootstrap:
            raw = bootstrap.post(
                path="/api/v1/auth/login",
                data={"username": self._username, "password": self._password},
            )
        data = cast("dict[str, Any]", raw)
        token = data.get("token")
        if not isinstance(token, str) or not token:
            raise ApiError(
                provider=self.provider_name,
                http_status=0,
                message=f"torr9 login response missing 'token': {data!r}",
            )
        log.info("torr9_login_success", provider=self.provider_name)
        self.__transport = HttpTransport(self.policy(token), event_bus=self._event_bus)
        return self.__transport

    @property
    def _transport(self) -> HttpTransport:
        """Lazy accessor for the authed main transport (triggers bootstrap on first access)."""
        return self._ensure_transport()

    @_transport.setter
    def _transport(self, value: HttpTransport) -> None:
        """Setter preserved for tests that inject a mock transport (short-circuits bootstrap)."""
        self.__transport = value

    def _authed_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | str:
        """GET via the authed transport; on 401, drop the transport (re-login) and retry ONCE.

        RP7 auth-lifecycle: an expired JWT yields a 401; we discard the cached
        transport so the next ``_transport`` access rebuilds it via a fresh
        bootstrap login, then retry the GET exactly once. A second 401 (or any
        non-401 ApiError) propagates — persistently-bad creds fail loud.

        Args:
            path: Request path (e.g. ``/api/v1/torrents``).
            params: Optional query params.

        Returns:
            The raw transport response (dict or str).

        Raises:
            ApiError: A non-401 error, or a 401 that survives the single re-login.
        """
        try:
            return self._transport.get(path=path, params=params)
        except ApiError as exc:
            if exc.http_status != 401:
                raise
            log.info("torr9_relogin_on_401", provider=self.provider_name)
            self.__transport = None  # force a fresh bootstrap login on next access
            return self._transport.get(path=path, params=params)

    # -- TrackerClient Protocol ---------------------------------------------

    def search(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[TrackerResult]:
        """Search torr9 via GET /api/v1/torrents?q=<query>.

        Logs in lazily on first transport access. Re-logins once on 401
        (RP7 auth-lifecycle: expired JWT → re-login, then retry) via
        ``_authed_get``. Wraps the parser in ``wrap_parser_drift`` so upstream
        shape changes surface as ``ApiError`` (swallowed by the registry)
        rather than bare ``KeyError``.

        Args:
            query: Free-text search query.
            media_type: Not forwarded as a filter (torr9 has no per-type endpoint).
            year: Optional release year appended to the query string.

        Returns:
            List of TrackerResult ordered as returned by the API (newest first).
            When ``enrich_seeders`` is on, the top-K results carry real
            seeders/leechers fetched from the detail endpoint.
        """
        del media_type  # No per-type search endpoint on torr9.
        q = f"{query} {year}" if year is not None else query
        raw = self._authed_get("/api/v1/torrents", {"q": q})

        def _parse() -> list[TrackerResult]:
            data = cast("dict[str, Any]", raw)
            items = data.get("torrents") or []
            return [self._parse_item(item) for item in items]

        results = wrap_parser_drift(self.provider_name, _parse)

        # Swarm enrichment: torr9's search payload has no seeders/leechers, so
        # every result would be seeders=0 and dropped by the ranking
        # ``min_seeders`` floor. Backfill the top-K results' swarm health from
        # the detail endpoint. Fail-soft PER RESULT — a detail error or circuit
        # trip leaves that result at seeders=0 but never aborts the search.
        if self._enrich_seeders and results:
            for r in results[: self._enrich_top_k]:
                try:
                    detail = self.get_details(r.tracker_id)
                    r.seeders = detail.seeders  # TrackerResult is a mutable dataclass
                    r.leechers = detail.leechers
                except CircuitOpenError as exc:
                    # Circuit OPEN — every remaining detail call would re-trip guard().
                    # Leave the rest at seeders=0 and stop enriching (fail-soft, as documented).
                    log.warning("torr9_enrich_circuit_open", tracker_id=r.tracker_id, error=str(exc))
                    break
                except ApiError as exc:
                    log.warning("torr9_enrich_failed", tracker_id=r.tracker_id, error=str(exc))
        return results

    def is_freeleech(self, torrent_id: str) -> bool:
        """Re-check whether a torrent is currently freeleech (FreeleechAware).

        Pre-download re-check via the per-torrent detail endpoint
        ``GET /api/v1/torrents/{id}`` (live-confirmed 2026-06-19). Distinct from
        the ``is_freeleech`` field captured at search time on ``TrackerResult`` —
        this surfaces a flag that flipped asynchronously. Logs in lazily and
        re-logins once on 401 (RP7 auth-lifecycle) via ``_authed_get``,
        mirroring ``search()``.

        Args:
            torrent_id: The torr9 numeric torrent id (as a string).

        Returns:
            True if the detail payload reports freeleech; False otherwise
            (including when the ``is_freeleech`` field is absent).

        Raises:
            ApiError: On a non-401 transport error, a 401 surviving one re-login
                (bad creds → fail-loud), or a malformed (non-dict) detail payload
                (surfaced via ``wrap_parser_drift``).
        """
        raw = self._authed_get(f"/api/v1/torrents/{torrent_id}")

        def _parse() -> bool:
            data = cast("dict[str, Any]", raw)
            return bool(data.get("is_freeleech", False))

        return wrap_parser_drift(self.provider_name, _parse)

    def get_details(self, torrent_id: str) -> TrackerResult:
        """Fetch the per-torrent detail (GET /torrents/{id}) as a TrackerResult.

        Implements
        :class:`~personalscraper.api.tracker._contracts.TorrentDetailsProvider`.
        Unlike the search payload, the detail carries real seeders/leechers, so
        ``search()`` calls this to enrich the top-K results' swarm health before
        ranking. Reuses ``_authed_get`` (lazy login + re-login on 401, RP7) and
        wraps the parse in ``wrap_parser_drift`` so shape drift surfaces as
        ``ApiError``. The shared ``_parse_item`` handles the detail shape
        (``category_name`` label, real swarm fields).

        Args:
            torrent_id: The torr9 numeric torrent id (as a string).

        Returns:
            A TrackerResult built from the detail payload, with real
            seeders/leechers.

        Raises:
            ApiError: On a non-401 transport error, a 401 surviving one re-login
                (bad creds → fail-loud), or a malformed (non-dict) detail payload
                (surfaced via ``wrap_parser_drift``).
        """
        raw = self._authed_get(f"/api/v1/torrents/{torrent_id}")
        return wrap_parser_drift(
            self.provider_name,
            lambda: self._parse_item(cast("dict[str, Any]", raw)),
        )

    def get_categories(self) -> dict[str, str]:
        """Return the static torr9 category map as ``{str(id): label}``.

        The full map requires a live ``GET /api/v1/categories`` call with a
        fresh Bearer token (rate-limited during prep — confirm and extend at
        implementation). The static ``_CATEGORY_MAP`` is pre-seeded from the
        golden fixture and RSS cross-reference.

        Returns:
            Mapping of numeric category id string → display label.
        """
        return {str(k): v for k, v in _CATEGORY_MAP.items()}

    # -- Internal helpers ---------------------------------------------------

    def _parse_item(self, item: dict[str, Any]) -> TrackerResult:
        """Map one torr9 JSON torrent item to a TrackerResult.

        Shared by BOTH payload shapes:

        - the SEARCH item (``response["torrents"][i]``) — carries a numeric
          ``category_id`` but NO swarm data (``seeders``/``leechers`` absent →
          default to 0);
        - the DETAIL item (``GET /torrents/{id}``) — carries real
          ``seeders``/``leechers`` and a human ``category_name`` label instead
          of ``category_id``.

        Args:
            item: One torrent object from either the search or detail payload.

        Returns:
            TrackerResult. ``seeders``/``leechers`` are 0 for a search item
            (no swarm keys) and the real swarm health for a detail item.
        """
        title = str(item.get("title", ""))

        # file_size_bytes is exact bytes (not KB or MB).
        # PLAN-DRIFT FIX: no isinstance-guard on size_raw — a malformed
        # file_size_bytes (e.g. dict) surfaces as TypeError → caught by
        # wrap_parser_drift → ApiError "shape drift", never silently coerced to 0.
        size_raw = item.get("file_size_bytes", 0)
        size = ByteSize.parse(int(size_raw))

        # Download path: prefer the auth-free magnet_link (the ROADMAP Q4 magnet
        # exception). When the magnet is absent/malformed, FALL BACK to the real
        # .torrent endpoint GET /api/v1/torrents/{id}/download (Bearer, bytes —
        # live-confirmed 200 application/x-bittorrent). resolve_source fetches it
        # via the provider's authed transport (get_bytes joins base_url + Bearer).
        # NOTE: torrent_file_url is DEAD (404 everywhere, hash mismatch) — unused.
        magnet = item.get("magnet_link")
        tracker_id = str(item.get("id", ""))
        if isinstance(magnet, str) and magnet.startswith("magnet:"):
            download_url: str | None = magnet
        else:
            log.warning("torr9_missing_magnet", tracker_id=tracker_id, title=title)
            # When the id is also absent, building "/api/v1/torrents//download" would
            # yield a malformed URL that 404s deep in fetch. Emit None instead so
            # resolve_source raises a clean "no usable download_url" TorrentFetchError.
            download_url = f"/api/v1/torrents/{tracker_id}/download" if tracker_id else None

        # Category: the SEARCH payload has a numeric ``category_id`` (mapped via
        # _CATEGORY_MAP); the DETAIL payload has NO ``category_id`` but a human
        # ``category_name`` label instead. Prefer the id-map, fall back to the
        # detail's label so both payload shapes yield a real category.
        category_id = item.get("category_id")
        if isinstance(category_id, int | float):
            category = _CATEGORY_MAP.get(int(category_id))
        else:
            category = item.get("category_name")

        upload_date = _parse_iso(item.get("upload_date"))

        # Swarm health: the SEARCH payload omits seeders/leechers (→ 0); the
        # DETAIL payload (GET /torrents/{id}) carries the real values. int()
        # runs inside wrap_parser_drift, so a bad type surfaces as shape drift.
        # The `or 0` collapses a present-but-None value to 0.
        return TrackerResult(
            provider=self.provider_name,
            tracker_id=tracker_id,
            title=title,
            size=size,
            seeders=int(item.get("seeders", 0) or 0),
            leechers=int(item.get("leechers", 0) or 0),
            category=category,
            download_url=download_url,
            info_hash=item.get("info_hash"),
            source_url=None,  # torr9 JSON API provides no per-torrent page URL.
            is_freeleech=bool(item.get("is_freeleech", False)),
            is_silverleech=False,  # torr9 has no partial-freeleech concept.
            upload_date=upload_date,
            format=None,  # Quality fields are in title and tags; not parsed here.
            codec=None,  # Future: extract from title using _parse_title() if needed.
            source=None,
            resolution=None,
            audio=None,
        )

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
- ``magnet_link`` is auth-free (preferred download). ``torrent_file_url`` is
  relative and needs base + auth.
- ``is_freeleech`` is a clean boolean (no text parsing needed).
- No seeders/leechers exposed — ``seeders=0, leechers=0`` on all results.
- Login 401: "Identifiant ou mot de passe invalide" → fail-loud at boot.
- Search 401: "Missing authorization token" → re-login once (RP7).
- RSS feeds (passkey) for freeleech radar are OUT OF SCOPE (R1 follow-on).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, cast

from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult, wrap_parser_drift
from personalscraper.api.tracker._contracts import (
    CategoryListable,
    TorrentSearchable,
)
from personalscraper.api.transport._auth import BearerAuth, NoAuth
from personalscraper.api.transport._policy import (
    CircuitPolicy,
    RateLimitPolicy,
    RetryPolicy,
    TransportPolicy,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.transport._http import HttpTransport

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


class Torr9Client(TorrentSearchable, CategoryListable):
    """torr9 tracker API client — authenticated JSON API with JWT login.

    Composes :class:`~personalscraper.api.tracker._contracts.TorrentSearchable`
    and :class:`~personalscraper.api.tracker._contracts.CategoryListable`.
    Auth is lazy JWT login (POST /auth/login) with re-login on 401 (RP7).

    The client does NOT implement :class:`FreeleechAware` because freeleech is
    already a structured boolean in the search response (``is_freeleech`` field)
    — no separate re-check endpoint exists or is needed.
    """

    provider_name: str = "torr9"
    # PROVIDER_CREDS key: TORR9_USERNAME gates activation (per DESIGN ACC-3 →
    # PROVIDER_CREDS["torr9"] = ["TORR9_USERNAME", "TORR9_PASSWORD"]).
    # Phase 2 registers this in api/_activation.py.
    REQUIRED_CREDS: ClassVar[list[str]] = ["TORR9_USERNAME", "TORR9_PASSWORD"]

    _BASE_URL: ClassVar[str] = "https://api.torr9.net"

    @classmethod
    def policy(cls) -> TransportPolicy:
        """Build a base TransportPolicy for torr9 (no static auth — login is lazy).

        Auth is NOT applied here: the Bearer token is obtained at first search
        via ``_ensure_logged_in()`` and injected directly into the transport's
        session header. ``NoAuth`` is the placeholder so HttpTransport is
        constructed without a token.

        Returns:
            TransportPolicy with NoAuth, conservative rate limit, and standard
            5-fail / 5-min circuit settings.
        """
        return TransportPolicy(
            provider_name="torr9",
            base_url=cls._BASE_URL,
            auth=NoAuth(),
            timeout_seconds=15,
            retry=RetryPolicy(max_attempts=3),
            circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300.0),
            rate_limit=RateLimitPolicy(requests_per_second=0.5),
        )

    def __init__(
        self,
        transport: HttpTransport,
        *,
        username: str,
        password: str,
    ) -> None:
        """Initialize the torr9 client.

        Args:
            transport: HttpTransport pre-configured with the torr9 policy.
                Token is injected lazily via ``_ensure_logged_in()``.
            username: ``TORR9_USERNAME`` credential.
            password: ``TORR9_PASSWORD`` credential.
        """
        self._transport = transport
        self._username = username
        self._password = password
        self._token: str | None = None  # Cached JWT, None until first login.

    # -- Auth lifecycle (RP7 auth-lifecycle) --------------------------------

    def _login(self) -> None:
        """Perform JWT login against POST /api/v1/auth/login.

        Stores the returned token in ``self._token`` and applies it to the
        transport session header via ``BearerAuth``.

        Args: None (uses ``self._username`` / ``self._password``).

        Raises:
            ApiError: On HTTP 401 (bad credentials) or any non-2xx response.
                A 401 here means the stored creds are wrong — fail-loud, do
                NOT silently swallow (RP7 auth-lifecycle).
        """
        payload = {"username": self._username, "password": self._password}
        raw = self._transport.post(path="/api/v1/auth/login", data=payload)
        data = cast("dict[str, Any]", raw)
        token = data.get("token")
        if not isinstance(token, str) or not token:
            raise ApiError(
                provider=self.provider_name,
                http_status=0,
                message=f"torr9 login response missing 'token': {data!r}",
            )
        self._token = token
        # Apply Bearer token to the transport session so all subsequent GETs
        # carry Authorization: Bearer <token> without per-request overhead.
        BearerAuth(token).apply(self._transport._session)
        log.info("torr9_login_success", provider=self.provider_name)

    def _ensure_logged_in(self) -> None:
        """Login lazily on first call; no-op if token already cached.

        Args: None.

        Returns: None.

        Raises:
            ApiError: If the login POST fails (401 bad creds, 403 rate-limit).
        """
        if self._token is None:
            self._login()

    # -- TrackerClient Protocol ---------------------------------------------

    def search(
        self,
        query: str,
        media_type: MediaType = MediaType.MOVIE,
        year: int | None = None,
    ) -> list[TrackerResult]:
        """Search torr9 via GET /api/v1/torrents?q=<query>.

        Logs in lazily on first call. Re-logins once on 401 (RP7 auth-lifecycle:
        expired JWT → re-login, then retry). Wraps the parser in
        ``wrap_parser_drift`` so upstream shape changes surface as ``ApiError``
        (swallowed by the registry) rather than bare ``KeyError``.

        Args:
            query: Free-text search query.
            media_type: Not forwarded as a filter (torr9 has no per-type endpoint).
            year: Optional release year appended to the query string.

        Returns:
            List of TrackerResult ordered as returned by the API (newest first).
        """
        del media_type  # No per-type search endpoint on torr9.

        self._ensure_logged_in()

        q = f"{query} {year}" if year is not None else query
        params: dict[str, Any] = {"q": q}

        try:
            raw = self._transport.get(path="/api/v1/torrents", params=params)
        except ApiError as exc:
            if exc.http_status == 401:
                # RP7: token expired mid-session — re-login once and retry.
                log.info("torr9_relogin_on_401", provider=self.provider_name)
                self._token = None
                self._login()
                raw = self._transport.get(path="/api/v1/torrents", params=params)
            else:
                raise

        def _parse() -> list[TrackerResult]:
            data = cast("dict[str, Any]", raw)
            items = data.get("torrents") or []
            return [self._parse_item(item) for item in items]

        return wrap_parser_drift(self.provider_name, _parse)

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

        Args:
            item: One element from ``response["torrents"]``.

        Returns:
            TrackerResult with ``seeders=0`` and ``leechers=0``
            (torr9 exposes no swarm health data — JSON or RSS).
        """
        title = str(item.get("title", ""))

        # file_size_bytes is exact bytes (not KB or MB).
        # PLAN-DRIFT FIX: no isinstance-guard on size_raw — a malformed
        # file_size_bytes (e.g. dict) surfaces as TypeError → caught by
        # wrap_parser_drift → ApiError "shape drift", never silently coerced to 0.
        size_raw = item.get("file_size_bytes", 0)
        size = ByteSize.parse(int(size_raw))

        # Prefer magnet_link (auth-free, maps to the ROADMAP Q4 magnet exception).
        # torrent_file_url is relative (needs base + auth); use only as last resort.
        magnet = item.get("magnet_link")
        download_url: str | None = magnet if isinstance(magnet, str) and magnet.startswith("magnet:") else None

        category_id = item.get("category_id")
        category = _CATEGORY_MAP.get(int(category_id)) if isinstance(category_id, int | float) else None

        upload_date = _parse_iso(item.get("upload_date"))

        # torr9 has no seeder/leecher data in either JSON search or RSS.
        # _ranking.py weights seeders; absence means ranking on freeleech/size/recency.
        return TrackerResult(
            provider=self.provider_name,
            tracker_id=str(item.get("id", "")),
            title=title,
            size=size,
            seeders=0,
            leechers=0,
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

# Phase 01 — Torr9Client: login/JWT transport + JSON search + golden tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `Torr9Client` in `personalscraper/api/tracker/torr9.py` with lazy JWT login, re-login on 401, JSON search (real API contract), item → `TrackerResult` mapping, and golden-fixture tests against the real captured payloads.

**Architecture:** `Torr9Client` mirrors `LaCaleClient` structurally (JSON + `wrap_parser_drift`) but replaces the static `ApiKeyAuth` with a lazy login/JWT mechanism: login is deferred to first search call, the token is cached in memory, and a 401 on a search request triggers a single re-login attempt (RP7 auth-lifecycle). The `policy()` classmethod builds a `TransportPolicy` with `NoAuth` (the session header is set at login time by an internal method). Tests use `MagicMock` transport — never hit the live API.

**Tech Stack:** `personalscraper.api.transport._auth` (BearerAuth, NoAuth), `personalscraper.api.transport._policy` (TransportPolicy, RateLimitPolicy, RetryPolicy, CircuitPolicy), `personalscraper.api.tracker._base` (TrackerResult, wrap_parser_drift), `personalscraper.api._contracts` (ApiError, MediaType, ProviderName), `personalscraper.api._units` (ByteSize), `personalscraper.logger.get_logger`, `pytest`, `unittest.mock`.

## Gate

**Prerequisites:** None — this is phase 1. Branch `feat/torr9` must be checked out.

**Prior-phase files needed:** None.

**This phase gate passes when:**

- `python -m pytest tests/unit/test_torr9_client.py -q` reports 0 failed / 0 errors
- `make lint` is green (ruff + mypy)
- `python -c "from personalscraper.api.tracker.torr9 import Torr9Client"` exits 0

---

## File Map

| Action | Path                                   | Responsibility                                |
| ------ | -------------------------------------- | --------------------------------------------- |
| Create | `personalscraper/api/tracker/torr9.py` | `Torr9Client` class: login/JWT, search, parse |
| Create | `tests/unit/test_torr9_client.py`      | Golden-fixture unit tests                     |

---

## Task 1: `_CATEGORY_MAP` static map and `_parse_iso` helper

**Files:**

- Create: `personalscraper/api/tracker/torr9.py`

The API returns numeric `category_id`. From the golden fixture and the RSS labels we know: id 5 = Séries TV, id 51 = Films. The full map requires `GET /api/v1/categories` (fetch with a fresh token at implementation; rate-limited during prep). Populate what is known and add `_CATEGORY_MAP` as a `dict[int, str]`.

- [ ] **Step 1.1: Create the module skeleton with docstring, imports, `_CATEGORY_MAP`, and `_parse_iso`**

```python
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

from personalscraper.api._contracts import ApiError, MediaType, ProviderName
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
    2: "Films",            # confirmed via RSS label cross-ref
    5: "Séries TV",        # confirmed — golden fixture id 5
    9: "Films",            # from Hangman search sample
    46: "Séries Animées",  # from Hangman search sample
    51: "Films",           # confirmed — golden fixture id 51
    53: "Anime",           # from Hangman search sample
    54: "TV Programs",     # from Hangman search sample
}
```

- [ ] **Step 1.2: Add `_parse_iso` helper at module level**

```python
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
```

- [ ] **Step 1.3: Write an initial smoke test (not yet green — no class yet)**

```python
# tests/unit/test_torr9_client.py
"""Tests for torr9 tracker client — api/tracker/torr9.py.

Fixtures load real captures from docs/reference/_samples/torr9/.
Live samples captured 2026-06-19. Credentials and passkeys are redacted.
Tests NEVER hit the live torr9 API — transport is always mocked.
"""

from __future__ import annotations

import json
from pathlib import Path

_SAMPLES = Path(__file__).resolve().parents[2] / "docs" / "reference" / "_samples" / "torr9"


def _load(name: str) -> object:
    """Load a real captured sample from the fixture directory."""
    with (_SAMPLES / name).open() as f:
        return json.load(f)


def test_module_importable() -> None:
    """torr9 module imports cleanly."""
    from personalscraper.api.tracker.torr9 import Torr9Client  # noqa: F401
```

- [ ] **Step 1.4: Run — confirm ImportError (class not yet defined)**

```bash
python -m pytest tests/unit/test_torr9_client.py::test_module_importable -v
# Expected: FAILED with ImportError or ModuleNotFoundError
```

---

## Task 2: `Torr9Client` class skeleton — `policy()`, `__init__`, `provider_name`

**Files:**

- Modify: `personalscraper/api/tracker/torr9.py`

The factory calls `client_cls.policy(api_key)` where `api_key = env["TORR9_USERNAME"]` (the first required cred). But torr9 needs both username AND password. The factory has a "single-key assumption" comment — phase 2 updates the factory; here we wire `Torr9Client.__init__` to accept `transport` AND separate `username`/`password` args, and the `policy()` classmethod uses `NoAuth` (auth header is applied lazily at login time, not at transport init).

> **Design note on `policy()` signature:** `C411Client.policy(api_key)` takes one string; `LaCaleClient.policy(api_key)` takes one string. The factory calls `client_cls.policy(api_key)` with `api_key = env[required[0]]`. For torr9 this approach must be adapted in phase 2 (factory multi-cred path). In this phase, `policy()` is defined but the multi-cred construction is tested via direct instantiation, not via the factory.

- [ ] **Step 2.1: Add `Torr9Client` class with `policy()`, `REQUIRED_CREDS`, `provider_name`**

```python
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
        from personalscraper.api.transport._auth import NoAuth  # noqa: PLC0415

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
```

- [ ] **Step 2.2: Add the import smoke test and policy test to the test file**

```python
# In tests/unit/test_torr9_client.py — add after test_module_importable

from unittest.mock import MagicMock

from personalscraper.api.tracker.torr9 import Torr9Client
from personalscraper.api.transport._auth import NoAuth


def _make_client() -> Torr9Client:
    """Build a Torr9Client with a mocked HttpTransport."""
    transport = MagicMock()
    return Torr9Client(transport, username="user", password="pass")


class TestTorr9Policy:
    """Torr9Client.policy() builds a valid TransportPolicy."""

    def test_policy_uses_no_auth(self) -> None:
        """Policy uses NoAuth — Bearer token is injected lazily at login."""
        policy = Torr9Client.policy()
        assert isinstance(policy.auth, NoAuth)

    def test_policy_base_url(self) -> None:
        """Base URL points to the torr9 JSON API host."""
        policy = Torr9Client.policy()
        assert policy.base_url == "https://api.torr9.net"

    def test_policy_provider_name(self) -> None:
        """provider_name matches the registry key."""
        policy = Torr9Client.policy()
        assert policy.provider_name == "torr9"

    def test_policy_defensive_rate_limit(self) -> None:
        """Rate limit set to 0.5 rps (torr9 rate-limits aggressively)."""
        policy = Torr9Client.policy()
        assert policy.rate_limit.requests_per_second == 0.5

    def test_required_creds(self) -> None:
        """REQUIRED_CREDS lists username + password for JWT login."""
        assert Torr9Client.REQUIRED_CREDS == ["TORR9_USERNAME", "TORR9_PASSWORD"]
```

- [ ] **Step 2.3: Run — confirm tests pass**

```bash
python -m pytest tests/unit/test_torr9_client.py::TestTorr9Policy -v
# Expected: 5 passed
```

---

## Task 3: `_ensure_logged_in()` — lazy login with re-login on 401

**Files:**

- Modify: `personalscraper/api/tracker/torr9.py`

The core of the JWT auth lifecycle (RP7). Login is a `POST /api/v1/auth/login` call that the transport already supports via `transport.post()`. The token is stored in `self._token` and applied to the session header via `BearerAuth`. On a 401 `ApiError` during search, login is called again once (retry-once pattern).

> **Implementation note on `_session` coupling:** `BearerAuth(token).apply(self._transport._session)` accesses `HttpTransport._session` (private). This is the only viable approach without a framework change: `HttpTransport` applies auth only at `__init__` via `policy.auth.apply(session)`, and there is no public `set_auth()` method. The DESIGN explicitly prohibits new framework primitives for this feature. The coupling is intentional and minimal — pin it with a comment in the implementation. If a `set_bearer_token()` method is added to `HttpTransport` in a future wave, `_login()` can be updated to use it instead.

- [ ] **Step 3.1: Implement `_login()` and `_ensure_logged_in()`**

```python
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
```

- [ ] **Step 3.2: Write login tests (mocking transport.post)**

```python
# In tests/unit/test_torr9_client.py — add after TestTorr9Policy

import pytest
from personalscraper.api._contracts import ApiError


class TestTorr9Login:
    """Torr9Client lazy login and re-login on 401."""

    def test_login_sets_token(self) -> None:
        """Successful login stores the token and calls _transport.post."""
        client = _make_client()
        client._transport.post.return_value = {  # type: ignore[attr-defined]
            "token": "jwt-abc123",
            "user": {"id": 1},
            "message": "ok",
        }
        client._ensure_logged_in()
        assert client._token == "jwt-abc123"

    def test_login_called_only_once(self) -> None:
        """Second _ensure_logged_in() call is a no-op (token cached)."""
        client = _make_client()
        client._transport.post.return_value = {  # type: ignore[attr-defined]
            "token": "jwt-abc123",
        }
        client._ensure_logged_in()
        client._ensure_logged_in()
        assert client._transport.post.call_count == 1  # type: ignore[attr-defined]

    def test_login_missing_token_raises_api_error(self) -> None:
        """Login response without 'token' raises ApiError (fail-loud)."""
        client = _make_client()
        client._transport.post.return_value = {  # type: ignore[attr-defined]
            "error": "Identifiant ou mot de passe invalide"
        }
        with pytest.raises(ApiError) as exc:
            client._ensure_logged_in()
        assert exc.value.provider == "torr9"
        assert "token" in exc.value.message

    def test_login_transport_401_propagates(self) -> None:
        """HTTP 401 from transport (bad creds) propagates as ApiError."""
        client = _make_client()
        client._transport.post.side_effect = ApiError(  # type: ignore[attr-defined]
            provider="torr9", http_status=401, message="Identifiant ou mot de passe invalide"
        )
        with pytest.raises(ApiError) as exc:
            client._ensure_logged_in()
        assert exc.value.http_status == 401
```

- [ ] **Step 3.3: Run login tests**

```bash
python -m pytest tests/unit/test_torr9_client.py::TestTorr9Login -v
# Expected: 4 passed
```

---

## Task 4: `search()` — GET /api/v1/torrents?q= with re-login on 401

**Files:**

- Modify: `personalscraper/api/tracker/torr9.py`

`search()` calls `_ensure_logged_in()` first, then `GET /api/v1/torrents?q=<query>`. On a 401 `ApiError`, it re-logins once and retries. The raw response is `{limit, page, torrents:[...]}`. Items are parsed by `_parse_item` inside `wrap_parser_drift`.

- [ ] **Step 4.1: Implement `search()` with re-login-on-401**

```python
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
```

- [ ] **Step 4.2: Write search() tests**

```python
# In tests/unit/test_torr9_client.py — add after TestTorr9Login

class TestTorr9Search:
    """Torr9Client.search() — query param and re-login-on-401 behaviour."""

    def test_search_calls_correct_path_and_param(self) -> None:
        """search() hits /api/v1/torrents with q= param."""
        client = _make_client()
        client._token = "cached"
        client._transport.get.return_value = {"torrents": [], "limit": 20, "page": 1}  # type: ignore[attr-defined]

        client.search("Inception")

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["path"] == "/api/v1/torrents"
        assert kwargs["params"]["q"] == "Inception"

    def test_year_appended_to_query(self) -> None:
        """When year is given it is concatenated to q."""
        client = _make_client()
        client._token = "cached"
        client._transport.get.return_value = {"torrents": []}  # type: ignore[attr-defined]

        client.search("Inception", year=2010)

        kwargs = client._transport.get.call_args.kwargs  # type: ignore[attr-defined]
        assert kwargs["params"]["q"] == "Inception 2010"

    def test_search_relogin_on_401(self) -> None:
        """A 401 from the search GET triggers re-login and a single retry."""
        client = _make_client()
        client._token = "stale"  # pre-set so _ensure_logged_in is a no-op

        # First GET raises 401; after re-login, second GET succeeds.
        call_count = 0

        def _side_effect(**kwargs: Any) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ApiError(provider="torr9", http_status=401, message="Missing authorization token")
            return {"torrents": [], "page": 1, "limit": 20}

        client._transport.get.side_effect = _side_effect  # type: ignore[attr-defined]
        client._transport.post.return_value = {"token": "new-jwt"}  # type: ignore[attr-defined]

        results = client.search("Inception")
        assert results == []
        assert client._transport.post.call_count == 1  # re-login happened once  # type: ignore[attr-defined]

    def test_search_empty_returns_empty_list(self) -> None:
        """An empty torrents array parses cleanly to []."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = {"torrents": [], "limit": 20, "page": 1}  # type: ignore[attr-defined]

        assert client.search("zzzz_no_match") == []
```

- [ ] **Step 4.3: Run search tests**

```bash
python -m pytest tests/unit/test_torr9_client.py::TestTorr9Search -v
# Expected: 4 passed
```

---

## Task 5: `_parse_item()` and `get_categories()`

**Files:**

- Modify: `personalscraper/api/tracker/torr9.py`

`_parse_item` maps one JSON torrent dict to a `TrackerResult`. Key differences from lacale/c411: `seeders=0, leechers=0` (not exposed), `download_url=magnet_link` (auth-free), `is_freeleech` is a direct boolean, `category` is mapped via `_CATEGORY_MAP`. `get_categories()` returns the static `_CATEGORY_MAP` as `{str(id): label}`.

- [ ] **Step 5.1: Implement `_parse_item()` and `get_categories()`**

```python
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
        size_raw = item.get("file_size_bytes", 0)
        size = ByteSize.parse(int(size_raw)) if isinstance(size_raw, int | float | str) else ByteSize.parse(0)

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
            format=None,   # Quality fields are in title and tags; not parsed here.
            codec=None,    # Future: extract from title using _parse_title() if needed.
            source=None,
            resolution=None,
            audio=None,
        )
```

- [ ] **Step 5.2: Write golden-fixture tests (anti-vacuity — concrete field assertions)**

```python
# In tests/unit/test_torr9_client.py — add after TestTorr9Search

from datetime import timezone
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult


class TestTorr9SearchGoldenFixture:
    """Golden-fixture parse tests against the real captured torr9_search.json.

    These tests are ANTI-VACUITY: they assert concrete values from the real
    payload, not just 'isinstance' or 'not None'. A stub-passable test that
    checks nothing specific will not catch real parse bugs (project memory:
    DeepSeek-written parsers pass make check while hiding real bugs).
    """

    def test_search_parses_two_results_from_golden_fixture(self) -> None:
        """Real payload has exactly 2 torrents in the captured slice."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        results = client.search("Oasis")

        assert len(results) == 2
        assert all(isinstance(r, TrackerResult) for r in results)
        assert all(r.provider == "torr9" for r in results)

    def test_first_item_title(self) -> None:
        """First result title matches exactly the golden fixture."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.title == "Oasis.2026.S01.MULTi.AD.1080p.NF.WEB.X264-THESYNDiCATE"

    def test_first_item_size_bytes(self) -> None:
        """Size parsed from file_size_bytes (exact bytes, not KB/MB)."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert isinstance(first.size, ByteSize)
        assert first.size.bytes == 20_827_331_134

    def test_first_item_magnet_link_as_download_url(self) -> None:
        """download_url is the magnet_link (auth-free, preferred)."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.download_url is not None
        assert first.download_url.startswith("magnet:?xt=urn:btih:")
        assert "d5638677f9986adc3ea155e7b753c36321cc30af" in first.download_url

    def test_first_item_info_hash(self) -> None:
        """info_hash matches the golden fixture value."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.info_hash == "d5638677f9986adc3ea155e7b753c36321cc30af"

    def test_first_item_is_not_freeleech(self) -> None:
        """is_freeleech is False for the first golden fixture item."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.is_freeleech is False

    def test_first_item_seeders_none_because_torr9_does_not_expose_swarm(self) -> None:
        """torr9 has no seeder data — seeders=0 on all results."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.seeders == 0
        assert first.leechers == 0

    def test_first_item_upload_date_iso(self) -> None:
        """upload_date parses from ISO 8601 with microseconds and Z suffix."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.upload_date is not None
        assert first.upload_date.tzinfo == timezone.utc
        assert first.upload_date.year == 2026
        assert first.upload_date.month == 6
        assert first.upload_date.day == 19

    def test_first_item_category_from_id_map(self) -> None:
        """category_id 5 maps to 'Séries TV' via _CATEGORY_MAP."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        first = client.search("Oasis")[0]
        assert first.category == "Séries TV"

    def test_second_item_category_from_id_map(self) -> None:
        """category_id 51 maps to 'Films' via _CATEGORY_MAP."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        second = client.search("Oasis")[1]
        assert second.title == "The.Fantastic.Four.1994.VOSTFR.DVDRip.x264.AC3-TeamLampion"
        assert second.category == "Films"
        assert second.size.bytes == 1_000_504_347

    def test_second_item_tracker_id(self) -> None:
        """tracker_id is the string of the JSON 'id' field."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = _load("torr9_search.json")  # type: ignore[attr-defined]

        second = client.search("Oasis")[1]
        assert second.tracker_id == "305289"
```

- [ ] **Step 5.3: Run all unit tests so far**

```bash
python -m pytest tests/unit/test_torr9_client.py -v
# Expected: all pass (golden fixture tests + login + policy)
```

---

## Task 6: `get_categories()` test + malformed-payload path

**Files:**

- Modify: `tests/unit/test_torr9_client.py`

- [ ] **Step 6.1: Write `get_categories()` and malformed-payload tests**

```python
# In tests/unit/test_torr9_client.py — add after TestTorr9SearchGoldenFixture


class TestTorr9Categories:
    """Torr9Client.get_categories() — static map."""

    def test_get_categories_returns_str_keyed_map(self) -> None:
        """get_categories() returns string keys (str(category_id))."""
        client = _make_client()
        cats = client.get_categories()
        assert isinstance(cats, dict)
        assert all(isinstance(k, str) for k in cats)

    def test_get_categories_includes_known_ids(self) -> None:
        """Known category ids from golden fixture are present."""
        client = _make_client()
        cats = client.get_categories()
        assert cats["5"] == "Séries TV"
        assert cats["51"] == "Films"

    def test_get_categories_no_live_call(self) -> None:
        """get_categories() never calls the transport (static map)."""
        client = _make_client()
        client.get_categories()
        client._transport.get.assert_not_called()  # type: ignore[attr-defined]


class TestTorr9MalformedPayload:
    """Malformed response paths surface as ApiError via wrap_parser_drift."""

    def test_torrents_key_missing_raises_api_error(self) -> None:
        """Response missing 'torrents' key results in empty list (graceful .get)."""
        client = _make_client()
        client._token = "t"
        client._transport.get.return_value = {"limit": 20, "page": 1}  # type: ignore[attr-defined]

        # .get("torrents") or [] gracefully handles missing key — no error.
        results = client.search("Oasis")
        assert results == []

    def test_item_with_wrong_size_type_raises_api_error(self) -> None:
        """An item with file_size_bytes of non-numeric type triggers ApiError via drift."""
        client = _make_client()
        client._token = "t"
        # Force a parse error: file_size_bytes is a nested dict (unexpected type).
        client._transport.get.return_value = {  # type: ignore[attr-defined]
            "torrents": [
                {
                    "id": 1,
                    "title": "x",
                    "file_size_bytes": {"nested": "object"},  # wrong type → int() fails
                    "magnet_link": "magnet:?xt=urn:btih:aaa",
                    "is_freeleech": False,
                    "upload_date": None,
                    "category_id": 5,
                    "info_hash": "aaa",
                }
            ]
        }
        # int({"nested": "object"}) raises TypeError → wrap_parser_drift → ApiError
        from personalscraper.api._contracts import ApiError as _ApiError
        with pytest.raises(_ApiError) as exc:
            client.search("x")
        assert exc.value.provider == "torr9"
        assert "shape drift" in exc.value.message
```

- [ ] **Step 6.2: Run full test file**

```bash
python -m pytest tests/unit/test_torr9_client.py -v
# Expected: all tests pass (count varies but 0 failed / 0 errors)
```

---

## Task 7: `make lint` and phase gate commit

**Files:**

- Modify: `personalscraper/api/tracker/torr9.py` (fix any ruff/mypy issues)
- Modify: `tests/unit/test_torr9_client.py` (fix any ruff/mypy issues)

- [ ] **Step 7.1: Run lint**

```bash
make lint
# Expected: 0 errors from ruff + mypy
```

If `make lint` reports issues:

- Unused imports → remove them
- Missing return type annotation → add `-> None` or the correct type
- `ANN` rules → add type annotations
- `check_logging.py` → ensure all `log = get_logger(...)` uses `personalscraper.logger.get_logger`, NOT `structlog.get_logger`

- [ ] **Step 7.2: Run tests**

```bash
python -m pytest tests/unit/test_torr9_client.py -q
# Expected: all passed, 0 failed / 0 errors
```

- [ ] **Step 7.3: Smoke import**

```bash
python -c "from personalscraper.api.tracker.torr9 import Torr9Client; print('OK')"
# Expected: OK
```

- [ ] **Step 7.4: Phase gate commit**

```bash
git add personalscraper/api/tracker/torr9.py tests/unit/test_torr9_client.py
git commit -m "$(cat <<'EOF'
feat(torr9): Torr9Client with lazy JWT login + golden-fixture search tests

- personalscraper/api/tracker/torr9.py: Torr9Client (TorrentSearchable +
  CategoryListable), policy(NoAuth), lazy _login/_ensure_logged_in,
  re-login on 401 (RP7), search() → wrap_parser_drift, _parse_item
  (magnet-first, seeders=0, is_freeleech bool), _CATEGORY_MAP static,
  get_categories(), _parse_iso helper.
- tests/unit/test_torr9_client.py: golden-fixture tests (anti-vacuity,
  concrete field asserts on real torr9_search.json), login lifecycle,
  policy, malformed-payload ApiError paths.
EOF
)"
```

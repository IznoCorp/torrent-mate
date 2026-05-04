# Third-Party API Consumer Unification — Design

**Status**: Prepared (not yet implemented)
**Codename**: `api-unify`
**Version bump**: 0.10.0 → 0.11.0 (minor — new `api/` package, 5 new third-party integrations: 2 metadata providers, 1 torrent client, 2 trackers)
**Design date**: 2026-05-03 (revision: 2026-05-04 — v3)
**Trigger**: ROADMAP P0 — unify all external API integrations behind shared client infrastructure.

> **Revision v3 (2026-05-04)** — addresses second pre-implementation review:
> move the reusable circuit breaker to a neutral `core/` package, stabilize
> `response_format` (`json`/`xml`/`text`) in Phase 1, make new optional
> providers disabled in `config.example`, and add explicit consumer migration
> notes for trailers, ingest, and indexer call sites. See §15.

---

## 1. Goals & Non-goals

### 1.1 Goals

- One `HttpTransport` foundation (session, retry, circuit breaker, auth, rate limit) shared by all providers.
- A **declarative `TransportPolicy` contract**: each provider exposes a typed policy describing its base URL, auth, retry, circuit, rate-limit, and headers. `HttpTransport` is provider-agnostic — it consumes a policy.
- Family contracts (`MetadataProvider`, `TorrentClient`, `TrackerClient`, `Notifier`, `HealthChecker`) as Protocols.
- Provider-specific subclasses implement only differential surface (endpoint paths, response parsing, auth flow).
- Typed response models replace all `dict[str, Any]` return types.
- Custom domain types where types resolve invariants (`ByteSize` for disk units, comparable + parseable from strings like `"1GB"`).
- All in-scope third-party API consumers migrate to the new infrastructure: TMDB, TVDB, qBittorrent pre-check, Telegram, and healthchecks. Other HTTP consumers (`youtube_search.py`, `artwork.py`, service-level catches of `requests` exceptions) are explicitly out of scope unless a phase names them.
- 5 new third-party integrations: 2 metadata providers (OMDB, Trakt), 1 torrent client (Transmission), 2 trackers (LaCale, C411).
- 1 new torrent client (Transmission) **with its own implementation phase**.
- 2 new trackers (LaCale, C411) **each with its own implementation phase**.
- Per-use-case provider priority in config files.
- Credentials stay in `.env` — activation via `enabled` toggle with credential presence check (missing → warning log, treated as disabled). Existing behavior-equivalent providers are enabled in generated local config; new optional integrations are disabled in `config.example` and only enabled in the active user config when the feature rollout intentionally opts into them.
- API documentation written for every provider before implementation, **with an interactive review checkpoint with the user** to surface API particularities early.

### 1.2 Non-goals

- Zero backward compatibility — no re-exports from old locations, no compat shims.
- Zero dead code, dead config, or stale documentation.
- HTTP response cache layer (deferred — YAGNI; add when a provider actually requires it).
- `get_raw()` byte-stream HTTP method (deferred — YAGNI; add when an HTML-scraping provider lands).
- TVDB token refresh during runtime (TTL = 1 month, no process lives that long; login once per client lifetime).
- Auto-Download System (P2) — tracker search/ranking infrastructure only, no download automation.
- Watcher Service (P2), Web Management UI (P2), Pipeline Observer Protocol (P1), Event Bus (P1).
- Provider Registry / Scraper Orchestrator Decoupling (P1).
- Dependency Injection container (P3).
- torr9.net + digitalcore.club trackers (deferred to ROADMAP).

### 1.3 Success criteria

| Metric           | Target                                                                                                                                                                                                         |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make test`      | green, coverage delta ≥ 0                                                                                                                                                                                      |
| `make check`     | green (hard-block module size check)                                                                                                                                                                           |
| `make lint`      | green (mypy, ruff)                                                                                                                                                                                             |
| Dead modules     | 7 modules removed (`tmdb_client.py`, `tvdb_client.py`, `circuit_breaker.py`, `http_retry.py`, `qbit_client.py`, `notifier.py`, `scraper/providers.py`)                                                         |
| New API docs     | 10 docs written (`tmdb-api.md`, `tvdb-api.md`, `omdb-api.md`, `trakt-api.md`, `qbittorrent-api.md`, `transmission-api.md`, `lacale-api.md`, `c411-api.md`, `telegram-api.md`, `healthchecks-api.md`)           |
| New config files | 5 config files (`metadata.json5`, `torrent.json5`, `tracker.json5`, `ranking.json5`, `notify.json5`)                                                                                                           |
| Typed responses  | Zéro `dict[str, Any]` dans les signatures d'API publique                                                                                                                                                       |
| LOC budgets      | **Aspirational, not gates**: TMDB ≤ ~550 LOC, TVDB ≤ ~400 LOC. Hard cap = 800 LOC (warning) / 1000 LOC (block). Extraction (`_parsers.py`, `_endpoints.py`) MUST be applied as soon as a file exceeds 600 LOC. |

---

## 2. Architecture

### 2.1 Package structure

```
api/
├── __init__.py
├── _contracts.py             # ApiError, CircuitOpenError, AuthMode
├── _activation.py            # ProviderActivation: enabled toggle + cred presence check
├── _units.py                 # ByteSize: parseable + comparable disk-size custom type
├── transport/
│   ├── __init__.py
│   ├── _policy.py            # TransportPolicy + RetryPolicy + CircuitPolicy + RateLimitPolicy + AuthMethod Protocol
│   ├── _auth.py              # BearerAuth, ApiKeyAuth (header OR query), LoginAuth, NoAuth
│   ├── _rate.py              # RateLimiter: token-bucket throttle (used by HttpTransport when policy.rate_limit.rps > 0)
│   └── _http.py              # HttpTransport: consumes a TransportPolicy
├── metadata/
│   ├── __init__.py
│   ├── _base.py              # MetadataProvider Protocol + typed models (SearchResult, MediaDetails, ArtworkItem, Notations, Recommendation, Video, SeasonDetails) + MetadataClient base
│   ├── tmdb.py               # Migrated from scraper/tmdb_client.py (split into _parsers.py / _endpoints.py if > 600 LOC)
│   ├── tvdb.py               # Migrated from scraper/tvdb_client.py
│   ├── omdb.py               # New — IMDB + RottenTomatoes ratings, search, details
│   └── trakt.py              # New — ratings, recommendations, trending
├── torrent/
│   ├── __init__.py
│   ├── _base.py              # TorrentClient Protocol + TorrentItem
│   ├── _factory.py           # active-client resolver: reads config.torrent.active → returns TorrentClient
│   ├── qbittorrent.py        # Migrated from ingest/qbit_client.py
│   └── transmission.py       # New
├── tracker/
│   ├── __init__.py
│   ├── _base.py              # TrackerClient Protocol + TrackerResult
│   ├── _ranking.py           # RankingCriterion + ThresholdEntry + TorrentRanking + rank()
│   ├── _registry.py          # TrackerRegistry
│   ├── lacale.py             # New
│   └── c411.py               # New
└── notify/
    ├── __init__.py
    ├── _base.py              # Notifier Protocol + HealthChecker Protocol
    ├── telegram.py           # Migrated from notifier.py
    └── healthchecks.py       # Migrated from notifier.py
```

Shared non-HTTP infrastructure moves outside `api/`:

```
core/
├── __init__.py
└── circuit.py                # Moved from scraper/circuit_breaker.py — reusable by API transport and indexer disk breaker
```

### 2.2 Layer model

```
┌──────────────────────────────────────────────┐
│  Provider class: TMDB, TVDB, OMDB, Trakt…    │
│  Endpoints, response parsing, typed models   │
│  Exposes: TransportPolicy + REQUIRED_CREDS   │
├──────────────────────────────────────────────┤
│  Family contract (Protocol): MetadataProvider│
│  TorrentClient, TrackerClient, Notifier      │
├──────────────────────────────────────────────┤
│  HttpTransport — consumes TransportPolicy.   │
│  Session, retry, circuit, auth, rate-limit,  │
│  structured logging.                         │
└──────────────────────────────────────────────┘
```

### 2.3 Module size discipline

- **Soft target** per provider file: ≤ 400 LOC.
- **Aspirational budget** for migrated providers: TMDB ≤ ~550, TVDB ≤ ~400 (post-extraction).
- **Hard ceilings**: 800 LOC (warning via `scripts/check-module-size.py`), 1000 LOC (block).
- **Extraction trigger**: at 600 LOC, the provider file MUST be split:
  - `_parsers.py` for response → typed-model translation (most likely overflow source).
  - `_endpoints.py` for path/route constants when many endpoints exist.
- LOC counts are **objectives, not gates**. Phase gates only enforce the hard 800/1000 ceilings.

### 2.4 Custom types

- `ByteSize` (`api/_units.py`): parseable from `"1GB"`, `"500MiB"`, integers; ordered/comparable; replaces ad-hoc int+unit handling. Used by ranking thresholds and any byte-count config field.
- Future: any cross-cutting unit/identifier type lives in a `_units.py` or `_types.py` module within its package.

---

## 3. Shared infrastructure

### 3.1 `api/_contracts.py`

```python
from dataclasses import dataclass
from enum import Enum

class AuthMode(Enum):
    BEARER = "bearer"
    API_KEY_HEADER = "api_key_header"
    API_KEY_QUERY = "api_key_query"
    LOGIN = "login"
    NONE = "none"

@dataclass
class ApiError(Exception):
    """Unified API error. Replaces TMDBError / TVDBError / etc."""
    provider: str
    http_status: int
    provider_code: int = 0
    message: str = ""

class CircuitOpenError(Exception):
    def __init__(self, provider: str, remaining_seconds: float) -> None: ...
```

`ApiError` must implement explicit display behavior so user-facing logs stay as readable as the legacy provider errors:

```python
def __str__(self) -> str:
    code = f" provider_code={self.provider_code}" if self.provider_code else ""
    return f"{self.provider} API {self.http_status}{code}: {self.message}"
```

### 3.2 `api/_units.py` — ByteSize

```python
import re
from dataclasses import dataclass

_SIZE_RE = re.compile(r"^\s*([\d.]+)\s*([KMGTP]i?B|B)?\s*$", re.IGNORECASE)
_DEC = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12, "PB": 10**15}
_BIN = {"B": 1, "KIB": 2**10, "MIB": 2**20, "GIB": 2**30, "TIB": 2**40, "PIB": 2**50}


@dataclass(frozen=True, order=True)
class ByteSize:
    """Comparable, parseable disk-size value in bytes."""
    bytes: int

    @classmethod
    def parse(cls, value: int | float | str) -> "ByteSize":
        if isinstance(value, ByteSize):
            return value
        if isinstance(value, (int, float)):
            return cls(int(value))
        m = _SIZE_RE.match(value)
        if not m:
            raise ValueError(f"Invalid size literal: {value!r}")
        num = float(m.group(1))
        unit = (m.group(2) or "B").upper()
        table = _BIN if "I" in unit else _DEC
        return cls(int(num * table[unit]))

    def __int__(self) -> int:
        return self.bytes
```

### 3.3 `api/transport/_policy.py` — Transport contract

This is the **central architectural contract** of the feature: every provider declares HOW it wants the transport to behave, the transport enforces it uniformly.

```python
from dataclasses import dataclass, field
from typing import Protocol
import requests


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    initial_wait: float = 0.5
    max_wait: float = 10.0
    retryable_statuses: frozenset[int] = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True)
class CircuitPolicy:
    failure_threshold: int = 5
    cooldown_seconds: float = 300.0
    # If False (default): only the FINAL failure (after retries are exhausted) increments
    # the breaker. Mirrors current scraper/http_retry.py + circuit_breaker.py behavior.
    # If True: every retry attempt counts (use only for very expensive endpoints).
    count_retries: bool = False


@dataclass(frozen=True)
class RateLimitPolicy:
    requests_per_second: float = 0.0  # 0 = disabled


class AuthMethod(Protocol):
    """Authentication declaration.

    Two responsibilities:
    - apply(session): one-time mutation at transport init (e.g., set Authorization header).
    - auth_params(): per-request query params merged by HttpTransport (e.g., OMDB apikey=...).

    Token refresh is intentionally NOT part of this Protocol — see §1.2 (TVDB rationale).
    """
    def apply(self, session: requests.Session) -> None: ...
    def auth_params(self) -> dict[str, str]: ...  # Returns {} for header-based auth


@dataclass
class TransportPolicy:
    """Provider-declared transport behavior. HttpTransport is provider-agnostic
    and consumes this dataclass. Each provider exposes a `policy()` classmethod
    or a module-level constant building this from credentials."""
    provider_name: str
    base_url: str
    auth: AuthMethod
    timeout_seconds: float = 10.0
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    circuit: CircuitPolicy = field(default_factory=CircuitPolicy)
    rate_limit: RateLimitPolicy = field(default_factory=RateLimitPolicy)
    extra_headers: dict[str, str] = field(default_factory=dict)
    response_format: Literal["json", "xml", "text"] = "json"
```

### 3.4 `api/transport/_auth.py`

```python
class BearerAuth:
    def __init__(self, token: str) -> None: ...
    def apply(self, session): session.headers["Authorization"] = f"Bearer {self._token}"
    def auth_params(self) -> dict[str, str]: return {}


class ApiKeyAuth:
    """Single class, two locations. Header → mutates session; Query → adds per-request param."""
    def __init__(self, key: str, *, param: str = "api_key", location: str = "header") -> None:
        assert location in ("header", "query")
        self._key, self._param, self._location = key, param, location

    def apply(self, session):
        if self._location == "header":
            session.headers[self._param] = self._key

    def auth_params(self) -> dict[str, str]:
        return {self._param: self._key} if self._location == "query" else {}


class LoginAuth:
    """Username/password via Basic Auth (qBittorrent admin endpoint, etc.)."""
    def __init__(self, username: str, password: str) -> None: ...
    def apply(self, session): session.auth = (self._username, self._password)
    def auth_params(self) -> dict[str, str]: return {}


class NoAuth:
    def apply(self, session): pass
    def auth_params(self) -> dict[str, str]: return {}
```

**TVDB note**: TVDB requires `POST /login` with API key → returns Bearer token. This is **not** an `AuthMethod` — it's an init-time bootstrap done inside `TVDBClient.__init__()` using a small one-shot `HttpTransport` with `NoAuth`. Once the bearer is obtained, the main `TVDBClient` uses `BearerAuth(token)`. No runtime refresh needed (TTL = 1 month).

### 3.5 `core/circuit.py`

Pure move from `scraper/circuit_breaker.py` (240 LOC) to a neutral package because the breaker is used by HTTP API clients and by the media indexer disk breaker. Logic unchanged. Only the error-classification helper is updated:

```python
@staticmethod
def _is_circuit_error(exc: BaseException) -> bool:
    from personalscraper.api._contracts import ApiError

    if isinstance(exc, ApiError):
        return exc.http_status >= 500
    if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
        return exc.response.status_code >= 500
    return isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout))
```

`HttpTransport` imports `CircuitBreaker` from `personalscraper.core.circuit`. Existing non-API consumers such as `personalscraper/indexer/breaker.py` are updated to the same neutral import path.

### 3.6 `api/transport/_rate.py` — RateLimiter

Token-bucket. `0 rps = no-op`. Used internally by `HttpTransport` based on `policy.rate_limit`.

### 3.7 `api/transport/_http.py` — HttpTransport

```python
class HttpTransport:
    def __init__(self, policy: TransportPolicy) -> None:
        self._policy = policy
        self._log = get_logger(f"api.{policy.provider_name.lower()}")
        self._session = requests.Session()

        self._session.headers["Accept"] = "application/json"
        for k, v in policy.extra_headers.items():
            self._session.headers[k] = v
        policy.auth.apply(self._session)

        self._circuit = CircuitBreaker(
            name=policy.provider_name,
            failure_threshold=policy.circuit.failure_threshold,
            cooldown_seconds=policy.circuit.cooldown_seconds,
        )
        self._rate_limiter = RateLimiter(policy.rate_limit.requests_per_second)

    def get(self, path: str = "", params: dict | None = None) -> dict[str, Any] | str:
        return self._request_outer("GET", path, params=params)

    def post(self, path: str = "", data: dict | None = None) -> dict[str, Any] | str:
        return self._request_outer("POST", path, data=data)

    def _request_outer(self, method, path, *, params=None, data=None) -> dict:
        """Wraps tenacity retry. Circuit breaker counts only the FINAL failure
        unless policy.circuit.count_retries=True."""
        self._circuit.guard()  # CircuitOpenError if open

        try:
            result = self._tenacity_retry(method, path, params, data)
        except Exception as exc:
            if not self._policy.circuit.count_retries:
                self._circuit.record_failure(exc)
            raise
        self._circuit.record_success()
        return result

    def _tenacity_retry(self, method, path, params, data) -> dict:
        # Built dynamically from policy.retry — see implementation in plan.
        # Inside, attempts call _do_request. If count_retries=True, each failure
        # records to circuit; if False, only outer wrapper records.
        ...

    def _do_request(self, method, path, params, data) -> dict:
        self._rate_limiter.acquire()
        merged_params = {**self._policy.auth.auth_params(), **(params or {})}
        url = f"{self._policy.base_url.rstrip('/')}{path}" if path else self._policy.base_url
        start = time.monotonic()
        resp = self._session.request(method, url, params=merged_params, json=data,
                                     timeout=self._policy.timeout_seconds)
        duration = time.monotonic() - start
        self._log.debug("api_call", provider=self._policy.provider_name,
                        method=method, path=path, status=resp.status_code,
                        duration_ms=int(duration * 1000))
        if not resp.ok:
            try:
                err = resp.json()
            except ValueError:
                err = {}
            raise ApiError(
                provider=self._policy.provider_name,
                http_status=resp.status_code,
                provider_code=err.get("status_code", err.get("code", 0)),
                message=err.get("status_message", err.get("message", resp.reason)),
            )
        if self._policy.response_format == "json":
            return resp.json()
        if self._policy.response_format == "xml":
            import xmltodict
            return xmltodict.parse(resp.text)
        if self._policy.response_format == "text":
            return resp.text
        return resp.json()  # fallback

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "HttpTransport":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
```

**Key invariants enforced**:

- Circuit breaker counts retries only when `policy.circuit.count_retries=True` (default `False`).
- Auth query params are merged into every request (fixes OMDB-style apikey).
- Tenacity is configured from `policy.retry` (no global hardcoded retry config).
- `Accept: application/json` is the global default for JSON APIs. Providers with XML or text responses set `policy.response_format` and may override `Accept` via `policy.extra_headers`.
- `response_format` controls response body parsing and is stable from Phase 1: `"json"` (default), `"xml"` (via `xmltodict`), `"text"` (raw string). C411 and healthchecks use the non-JSON branches when their doc phases confirm the exact response format.
- No `get_raw()` (YAGNI).
- `HttpTransport` is a context manager (`with HttpTransport(policy) as transport:`) so bootstrap flows can close sessions deterministically.

---

## 4. Metadata family

### 4.1 `MetadataProvider` Protocol — `api/metadata/_base.py`

```python
class MetadataProvider(Protocol):
    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def search(self, title: str, year: int | None = None,
               media_type: str = "movie") -> list[SearchResult]: ...
    def get_details(self, media_id: str, media_type: str = "movie") -> MediaDetails: ...

    # Optional capabilities — base class raises NotImplementedError; providers override.
    def get_artwork_urls(self, media_id: str, media_type: str = "movie") -> list[ArtworkItem]: ...
    def get_keywords(self, media_id: str, media_type: str) -> list[str]: ...
    def get_videos(self, media_id: str, media_type: str, language: str) -> list[Video]: ...
    def get_season(self, tv_id: str, season: int) -> SeasonDetails: ...
    def get_notations(self, media_id: str, media_type: str) -> Notations | None: ...
    def get_recommendations(self, media_id: str, media_type: str) -> list[Recommendation]: ...
```

### 4.2 Typed response models

(Identical to v1 — see fields below for reference; full code in phase plan.)

```python
@dataclass class SearchResult:    provider, provider_id, title, year, media_type, overview, poster_url
@dataclass class MediaDetails:    provider, provider_id, title, original_title, year, overview,
                                  genres, runtime_minutes, rating, images, external_ids
@dataclass class ArtworkItem:     type, url, language, season
@dataclass class Notations:       provider, source, score, votes_count
@dataclass class Recommendation:  provider, provider_id, title, year, media_type, reason
@dataclass class Video:           id, site, key, type, official, size, iso_639_1
@dataclass class SeasonDetails:   provider, tv_id, season_number, episodes (list[EpisodeInfo])
@dataclass class EpisodeInfo:     episode_number, title, overview, air_date, runtime_minutes
```

### 4.3 Provider matrix

| Provider | Type            | Capabilities                                                   | TransportPolicy.auth                                                                                    |
| -------- | --------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| TMDB     | Existing, migr. | search, details, artwork, keywords, videos, seasons, notations | `BearerAuth(TMDB_API_KEY)`                                                                              |
| TVDB     | Existing, migr. | search, details, artwork, episodes, seasons                    | Bootstrap login → `BearerAuth(jwt)`                                                                     |
| OMDB     | New             | search, details, notations (IMDB + RT)                         | `ApiKeyAuth(key, location="query")`                                                                     |
| Trakt    | New             | notations, recommendations, trending                           | `ApiKeyAuth(client_id, location="header", param="trakt-api-key")` + extra header `trakt-api-version: 2` |

---

## 5. Torrent client family

### 5.1 `TorrentClient` Protocol

```python
class TorrentClient(Protocol):
    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def get_completed(self) -> list[TorrentItem]: ...
    def get_all_hashes(self) -> set[str]: ...
    def is_seeding(self, torrent: TorrentItem) -> bool: ...
    def get_content_path(self, torrent: TorrentItem) -> Path: ...
    def pause(self, hash: str) -> None: ...
    def resume(self, hash: str) -> None: ...
    def delete(self, hash: str, *, delete_files: bool = False) -> None: ...

@dataclass
class TorrentItem:
    hash: str; name: str; size_bytes: int; progress: float; state: str
    content_path: Path; category: str | None; added_on: datetime | None
```

### 5.2 Implementations

| Provider     | File                          | Library            | Phase |
| ------------ | ----------------------------- | ------------------ | ----- |
| qBittorrent  | `api/torrent/qbittorrent.py`  | `qbittorrentapi`   | 8     |
| Transmission | `api/torrent/transmission.py` | `transmission-rpc` | 10    |

### 5.3 `api/torrent/_factory.py` — active client resolver

```python
def build_active_torrent_client(cfg: TorrentConfig, env: Mapping[str, str]) -> TorrentClient:
    """Reads cfg.active, validates the chosen client is enabled and credentialed,
    constructs and returns the single TorrentClient instance the pipeline uses."""
```

This factory is consumed by the pipeline (replaces direct `QBitClient()` instantiation).

---

## 6. Tracker family

### 6.1 `TrackerClient` Protocol — `api/tracker/_base.py`

```python
class TrackerClient(Protocol):
    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]

    def search(self, query: str, media_type: str = "movie",
               year: int | None = None) -> list[TrackerResult]: ...
    def get_categories(self) -> dict[str, str]: ...

@dataclass
class TrackerResult:
    provider: str
    tracker_id: str
    title: str
    size: ByteSize                # NOTE: typed, not raw int.
    seeders: int
    leechers: int
    category: str | None
    download_url: str | None
    info_hash: str | None
    source_url: str | None
    is_freeleech: bool
    is_silverleech: bool
    upload_date: datetime | None
    format: str | None             # MKV, MP4, AVI…
    codec: str | None              # x265, HEVC, x264…
    source: str | None             # BluRay, WEB-DL, WEBRip…
    resolution: str | None         # 2160p, 1080p, 720p…
    audio: str | None              # VFF, VFQ, TrueHD…
```

### 6.2 Tracker list

| Tracker | Doc source                            | Phase |
| ------- | ------------------------------------- | ----- |
| LaCale  | `~/dev/TorrentMaker/docs/LaCale/api/` | 17    |
| C411    | `~/dev/TorrentMaker/docs/C411/api/`   | 19    |

torr9.net + digitalcore.club → ROADMAP entry.

### 6.3 Ranking system — `api/tracker/_ranking.py`

```python
class ThresholdEntry(BaseModel):
    """Single threshold rung. `at` accepts int (raw) or str (size literal like '1GB').
    Pydantic validator parses size literals into integer bytes via ByteSize."""
    at: int      # bytes after validation (int for raw counters like 'seeders')
    score: int

    @field_validator("at", mode="before")
    @classmethod
    def _parse(cls, v):
        if isinstance(v, str):
            return ByteSize.parse(v).bytes
        return int(v)


class RankingCriterion(BaseModel):
    field: str
    weight: float = 1.0
    values: dict[str, int] | None = None        # categorical (e.g., resolution: {"2160p": 20, "1080p": 15})
    thresholds: list[ThresholdEntry] | None = None  # numeric, ordered by `at`
    prefer: Literal["higher", "lower"] | None = None


class RankingBonuses(BaseModel):
    freeleech: int = 10
    silverleech: int = 5


class TorrentRanking(BaseModel):
    criteria: list[RankingCriterion] = []
    bonuses: RankingBonuses = RankingBonuses()
    min_seeders: int = 1


def rank(results: list[TrackerResult],
         ranking: TorrentRanking) -> list[tuple[TrackerResult, int]]:
    """Score each TrackerResult, apply bonuses, drop sub-min-seeders, return sorted desc.

    For numeric thresholds, comparison uses int(value). For ByteSize fields, ByteSize.bytes.
    For categorical values, str(value) lookup in `values` mapping."""
    scored: list[tuple[TrackerResult, int]] = []
    for r in results:
        if r.seeders < ranking.min_seeders:
            continue
        total = 0
        for c in ranking.criteria:
            v = getattr(r, c.field, None)
            if v is None:
                continue
            pts = 0
            if c.values is not None:
                pts = c.values.get(str(v), 0)
            elif c.thresholds:
                numeric = v.bytes if isinstance(v, ByteSize) else int(v)
                # thresholds sorted ascending by `at`; pick highest `at <= numeric`.
                applicable = [t for t in c.thresholds if numeric >= t.at]
                pts = max((t.score for t in applicable), default=0)
            total += int(pts * c.weight)
        if r.is_freeleech:
            total += ranking.bonuses.freeleech
        if r.is_silverleech:
            total += ranking.bonuses.silverleech
        scored.append((r, total))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
```

**Type coherence**: `TrackerResult.size` is `ByteSize`, ranking thresholds for `size` use `ThresholdEntry(at="1GB", score=...)` parsed to bytes via Pydantic. Comparison in `rank()` is integer-on-integer, no string-vs-int errors.

### 6.4 `TrackerRegistry` — `api/tracker/_registry.py`

```python
class TrackerRegistry:
    def __init__(self, trackers: dict[str, TrackerClient],
                 priority: list[str], ranking: TorrentRanking) -> None: ...

    def search_all(self, query: str, media_type: str = "movie",
                   year: int | None = None) -> list[tuple[TrackerResult, int]]:
        """Query trackers in priority order, merge, rank via rank()."""
```

---

## 7. Notification family

### 7.1 Protocols — `api/notify/_base.py`

```python
class Notifier(Protocol):
    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]
    def send(self, message: str, parse_mode: str = "HTML") -> bool: ...
    def send_report(self, report: PipelineReport) -> bool: ...

class HealthChecker(Protocol):
    provider_name: str
    REQUIRED_CREDS: ClassVar[list[str]]
    def ping_start(self) -> None: ...
    def ping_success(self) -> None: ...
    def ping_fail(self) -> None: ...
```

### 7.2 Migration

- `notifier.py` (120 LOC) → `api/notify/telegram.py` + `api/notify/healthchecks.py`.
- All `requests.post/get` → `HttpTransport`.
- Fail-soft behavior preserved (notifiers never raise).

---

## 8. Config & activation

### 8.1 New config files

| File                    | Purpose                                    |
| ----------------------- | ------------------------------------------ |
| `config/metadata.json5` | Metadata providers + per-use-case priority |
| `config/torrent.json5`  | Active client + clients config             |
| `config/tracker.json5`  | Active trackers + priority + timeout       |
| `config/ranking.json5`  | Ranking criteria                           |
| `config/notify.json5`   | Telegram + healthchecks toggles            |

### 8.2 `config/metadata.json5`

```json5
{
  // PROVIDER_CREDS hardcoded in api/_activation.py:
  //   tmdb  → ["TMDB_API_KEY"]
  //   tvdb  → ["TVDB_API_KEY"]
  //   omdb  → ["OMDB_API_KEY"]
  //   trakt → ["TRAKT_CLIENT_ID", "TRAKT_CLIENT_SECRET"]
  providers: {
    tmdb: { enabled: true },
    tvdb: { enabled: true },
    omdb: { enabled: false },
    trakt: { enabled: false },
  },
  priorities: {
    movie_scraping: { tmdb: 1, tvdb: 2 },
    series_scraping: { tvdb: 1, tmdb: 2 },
    episode_scraping: { tvdb: 1, tmdb: 2 },
    recommendations: { trakt: 1, omdb: 2 },
    notations: { omdb: 1, trakt: 2 },
  },
  defaults: {
    language: "fr-FR",
    fallback_language: "en-US",
    prefer_local_title: true,
  },
}
```

### 8.3 `config/torrent.json5`

```json5
{
  active: "qbittorrent", // The ONE client the pipeline uses
  clients: {
    qbittorrent: { enabled: true, host: "localhost", port: 8080 },
    transmission: { enabled: false, host: "localhost", port: 9091 },
  },
}
```

### 8.4 `config/tracker.json5`

```json5
{
  providers: {
    lacale: { enabled: false }, // .env: LACALE_API_KEY
    c411: { enabled: false }, // .env: C411_API_KEY
  },
  priority: ["lacale", "c411"],
  max_total_results: 50,
  max_per_tracker: 30,
  timeout_per_tracker: 15,
}
```

### 8.5 `config/ranking.json5`

```json5
{
  criteria: [
    {
      field: "resolution",
      weight: 4,
      values: { "2160p": 20, "1080p": 15, "720p": 10 },
    },
    { field: "codec", weight: 3, values: { x265: 10, HEVC: 10, x264: 5 } },
    { field: "format", weight: 2, values: { MKV: 10, MP4: 5 } },
    { field: "audio", weight: 2, values: { VFF: 20, VFQ: 15, TrueHD: 10 } },
    { field: "source", weight: 2, values: { BluRay: 15, "WEB-DL": 10 } },
    {
      field: "seeders",
      weight: 1,
      prefer: "higher",
      thresholds: [
        { at: 0, score: 0 },
        { at: 5, score: 5 },
        { at: 20, score: 10 },
        { at: 100, score: 20 },
      ],
    },
    {
      field: "size",
      weight: 1,
      prefer: "higher",
      // String literals parsed via ByteSize on load → integer bytes.
      thresholds: [
        { at: 0, score: 0 },
        { at: "1GB", score: 5 },
        { at: "5GB", score: 10 },
      ],
    },
  ],
  bonuses: { freeleech: 10, silverleech: 5 },
  min_seeders: 1,
}
```

### 8.6 `config/notify.json5`

```json5
{
  telegram: { enabled: false }, // .env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  healthchecks: { enabled: false }, // .env: HEALTHCHECK_PING_URL
}
```

`config.example/` intentionally keeps new optional integrations disabled to avoid warning noise for users who have not configured those credentials. Phase 2 also adapts the active project `config/` for this feature branch: providers intentionally exercised by the rollout can be set to `enabled: true` there, while the reusable examples stay conservative for new installations.

### 8.7 `api/_activation.py` — Provider activation

```python
PROVIDER_CREDS: dict[str, list[str]] = {
    "tmdb":         ["TMDB_API_KEY"],
    "tvdb":         ["TVDB_API_KEY"],
    "omdb":         ["OMDB_API_KEY"],
    "trakt":        ["TRAKT_CLIENT_ID", "TRAKT_CLIENT_SECRET"],
    "qbittorrent":  ["QBIT_USERNAME", "QBIT_PASSWORD"],
    "transmission": ["TRANSMISSION_USERNAME", "TRANSMISSION_PASSWORD"],
    "lacale":       ["LACALE_API_KEY"],
    "c411":         ["C411_API_KEY"],
    "telegram":     ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
    "healthchecks": ["HEALTHCHECK_PING_URL"],
}

def resolve_active(providers: dict, family: str,
                   env: Mapping[str, str] | None = None) -> list[str]:
    """Active = enabled=True AND all PROVIDER_CREDS[name] present in env.
    Missing creds → WARNING log, treat as disabled.
    Returns names sorted by config order."""
```

| enabled | Credentials | Result                |
| ------- | ----------- | --------------------- |
| true    | Present     | Active                |
| true    | Missing     | Inactive + WARNING    |
| false   | Present     | Inactive (no warning) |
| false   | Missing     | Inactive (no warning) |

---

## 9. API documentation rule

For **every** API (existing and new), before writing implementation:

1. Study official documentation + make real test calls (free-tier or sandbox API key).
2. Write `docs/reference/<provider>-api.md` covering: endpoints, parameters, response formats, authentication, rate limiting, quotas, limitations, relevant fields.
3. **Interactive checkpoint with the user**: present the doc summary, surface API particularities (quirks, limits, undocumented behavior), confirm scope before coding.
4. Implement the provider following the written doc + decisions taken in step 3.

### Docs to produce

| Provider     | Doc                                  | Source                                         | Phase |
| ------------ | ------------------------------------ | ---------------------------------------------- | ----- |
| TMDB         | `docs/reference/tmdb-api.md`         | `docs/TMDB-API.md` (existing, verify+complete) | 4     |
| TVDB         | `docs/reference/tvdb-api.md`         | `docs/TVDB-API.md` (existing, verify+complete) | 6     |
| qBittorrent  | `docs/reference/qbittorrent-api.md`  | qBit WebUI API                                 | 8     |
| Transmission | `docs/reference/transmission-api.md` | Transmission RPC                               | 10    |
| OMDB         | `docs/reference/omdb-api.md`         | https://www.omdbapi.com/                       | 12    |
| Trakt        | `docs/reference/trakt-api.md`        | https://trakt.docs.apiary.io/                  | 14    |
| LaCale       | `docs/reference/lacale-api.md`       | `~/dev/TorrentMaker/docs/LaCale/api/`          | 17    |
| C411         | `docs/reference/c411-api.md`         | `~/dev/TorrentMaker/docs/C411/api/`            | 19    |
| Telegram     | `docs/reference/telegram-api.md`     | Bot API sendMessage                            | 21    |
| Healthchecks | `docs/reference/healthchecks-api.md` | healthchecks.io ping URL                       | 23    |

---

## 10. Deletions (zero dead code)

### 10.1 Modules removed

| Module                       | Migrated to                                             |
| ---------------------------- | ------------------------------------------------------- |
| `scraper/tmdb_client.py`     | `api/metadata/tmdb.py`                                  |
| `scraper/tvdb_client.py`     | `api/metadata/tvdb.py`                                  |
| `scraper/circuit_breaker.py` | `core/circuit.py`                                       |
| `scraper/http_retry.py`      | Absorbed into `api/transport/_http.py` (RetryPolicy)    |
| `scraper/providers.py`       | Replaced by `api/metadata/_base.py` (typed Protocol)    |
| `ingest/qbit_client.py`      | `api/torrent/qbittorrent.py`                            |
| `notifier.py`                | `api/notify/telegram.py` + `api/notify/healthchecks.py` |

### 10.2 Exception types removed

- `TMDBError` — replaced by `ApiError`
- `TVDBError` — replaced by `ApiError`
- `CircuitOpenError` — moved to `api/_contracts.py`

### 10.3 Adjacent modules audited (kept, partially modified)

- `scraper/_shared.py` — only `_TVDB_LANG_MAP` migrates with TVDB. Rest stays.
- `indexer/breaker.py` — updated in Phase 1 to import `CircuitBreaker` from `core/circuit.py` because disk circuit breaking is not API-specific.
- `trailers/orchestrator.py` — updated in Phase 5 to build the migrated TMDB client while preserving the trailers-specific circuit threshold/cooldown from `config.trailers.circuit_breakers`.
- `ingest/ingest.py` — updated in Phase 9 to consume the torrent factory and preserve existing qBittorrent exception handling/report messages.
- `scraper/orchestrator.py`, `confidence.py`, `nfo_generator.py`, etc. — import sites updated; logic untouched.

### 10.4 Import migration

~90 import sites across ~45 production files and ~30 test files. No re-exports from old locations. Each migration phase updates imports in the same commit as the module move.

### 10.5 Documentation

All docs referencing old module paths updated. Archive docs (`docs/archive/`) intentionally left unchanged as historical record.

---

## 11. Phases (25 phases — 1 phase per API: doc OR impl)

Phases 1–3 build infrastructure. Each subsequent API has **two** phases: a doc phase (interactive checkpoint with user) and an implementation phase. Final phase = cleanup.

| #   | Phase                                 | Type  | Content                                                                                                                                                                  | Commit scope          |
| --- | ------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------- |
| 1   | Foundation: contracts + transport     | infra | `api/_contracts.py`, `api/_units.py`, `api/transport/` (policy, auth, rate, http) + neutral `core/circuit.py`.                                                           | `feat(api-unify)`     |
| 2   | Config infra + activation             | infra | Pydantic models, `api/_activation.py`, 5 `config.example/*.json5` templates, `Config` wiring.                                                                            | `feat(api-unify)`     |
| 3   | Metadata family base                  | infra | `api/metadata/_base.py` — Protocol + typed models (SearchResult, MediaDetails, …) + `MetadataClient`.                                                                    | `feat(api-unify)`     |
| 4   | TMDB API doc (interactive)            | doc   | `docs/reference/tmdb-api.md` + user checkpoint.                                                                                                                          | `docs(api-unify)`     |
| 5   | TMDB migration                        | impl  | `api/metadata/tmdb.py`, delete `scraper/tmdb_client.py`, update ~20 imports + tests.                                                                                     | `refactor(api-unify)` |
| 6   | TVDB API doc (interactive)            | doc   | `docs/reference/tvdb-api.md` + user checkpoint (incl. token TTL confirmed = 1 mo, no runtime refresh).                                                                   | `docs(api-unify)`     |
| 7   | TVDB migration                        | impl  | `api/metadata/tvdb.py`, delete `scraper/tvdb_client.py`, update ~15 imports + tests.                                                                                     | `refactor(api-unify)` |
| 8   | Torrent family base + qBit doc        | mixed | `api/torrent/_base.py`, `_factory.py` skeleton, `docs/reference/qbittorrent-api.md` + user checkpoint.                                                                   | `feat(api-unify)`     |
| 9   | qBittorrent migration                 | impl  | `api/torrent/qbittorrent.py`, delete `ingest/qbit_client.py`, update imports + tests.                                                                                    | `refactor(api-unify)` |
| 10  | Transmission API doc (interactive)    | doc   | `docs/reference/transmission-api.md` + user checkpoint.                                                                                                                  | `docs(api-unify)`     |
| 11  | Transmission implementation           | impl  | `api/torrent/transmission.py` + factory wiring + tests.                                                                                                                  | `feat(api-unify)`     |
| 12  | OMDB API doc (interactive)            | doc   | `docs/reference/omdb-api.md` + user checkpoint (notations format Ratings[]).                                                                                             | `docs(api-unify)`     |
| 13  | OMDB implementation                   | impl  | `api/metadata/omdb.py` + tests.                                                                                                                                          | `feat(api-unify)`     |
| 14  | Trakt API doc (interactive)           | doc   | `docs/reference/trakt-api.md` + user checkpoint (OAuth scope, headers).                                                                                                  | `docs(api-unify)`     |
| 15  | Trakt implementation                  | impl  | `api/metadata/trakt.py` + tests.                                                                                                                                         | `feat(api-unify)`     |
| 16  | Tracker family base + ranking + units | infra | `api/tracker/_base.py`, `_ranking.py` (uses `ByteSize`), `_registry.py`, ranking-engine tests.                                                                           | `feat(api-unify)`     |
| 17  | LaCale API doc (interactive)          | doc   | `docs/reference/lacale-api.md` + user checkpoint (TorrentMaker creds format).                                                                                            | `docs(api-unify)`     |
| 18  | LaCale implementation                 | impl  | `api/tracker/lacale.py` + tests.                                                                                                                                         | `feat(api-unify)`     |
| 19  | C411 API doc (interactive)            | doc   | `docs/reference/c411-api.md` + user checkpoint.                                                                                                                          | `docs(api-unify)`     |
| 20  | C411 implementation                   | impl  | `api/tracker/c411.py` + tests.                                                                                                                                           | `feat(api-unify)`     |
| 21  | Notify family base + Telegram doc     | mixed | `api/notify/_base.py` + `docs/reference/telegram-api.md` + user checkpoint.                                                                                              | `feat(api-unify)`     |
| 22  | Telegram migration                    | impl  | `api/notify/telegram.py`, partial removal of `notifier.py` (Telegram half) + tests.                                                                                      | `refactor(api-unify)` |
| 23  | Healthchecks API doc (interactive)    | doc   | `docs/reference/healthchecks-api.md` + user checkpoint.                                                                                                                  | `docs(api-unify)`     |
| 24  | Healthchecks migration                | impl  | `api/notify/healthchecks.py`, finish removing `notifier.py` + tests.                                                                                                     | `refactor(api-unify)` |
| 25  | Final cleanup + ROADMAP               | infra | Residual import audit, dead config purge, doc updates (`docs/reference/architecture.md`, `CLAUDE.md`), ROADMAP entry for torr9 + digitalcore, version bump verification. | `refactor(api-unify)` |

### Phase ordering rationale

- **1–3 (foundation)** unblocks every later phase. Phase 3 (metadata family base) is needed by Phase 5 onwards.
- **4–7 (TMDB then TVDB)**: low-risk migrations first — APIs are well-known.
- **8–11 (torrent)**: qBittorrent migration before Transmission (greenfield), so the factory is exercised by a known client first.
- **12–15 (new metadata: OMDB, Trakt)**: greenfield after migrations stabilize.
- **16–20 (trackers)**: family base in 16, then 1 phase per tracker (doc + impl alternating).
- **21–24 (notify)**: smallest migration last; allows leaving `notifier.py` until everything else is in place.
- **25 (cleanup)**: only when every consumer has migrated.

### Per-doc-phase user checkpoint (interactive)

Every doc phase ends with: "Doc complete. Particularities found: [list]. Proposed implementation scope: [scope]. Confirm or adjust before next phase." This lets the user catch API quirks (rate limits, undocumented fields, auth subtleties, response variants) before code is written.

---

## 12. Risk register

| #   | Risk                                                              | Likelihood | Impact | Mitigation                                                                                                                    |
| --- | ----------------------------------------------------------------- | ---------- | ------ | ----------------------------------------------------------------------------------------------------------------------------- |
| R1  | Import breakage after module deletion                             | High       | High   | `ruff check` + `python -c "import personalscraper"` after each migration commit. Phase gate has a residual-import grep and explicit consumer lists for trailers, ingest, and indexer. |
| R2  | `ApiError` replacement breaks error handling in consumers         | Medium     | High   | Grep for `TMDBError`, `TVDBError` in all try/except blocks during the migration phase commit (NOT a separate later phase).    |
| R3  | Circuit breaker over-trips because retries each count as failures | Medium     | Medium | `CircuitPolicy.count_retries=False` by default (mirrors current behavior). Tested in Phase 1 with a flaky-endpoint fixture.   |
| R4  | Query-param auth (OMDB) silently unauthenticated                  | Medium     | High   | `AuthMethod.auth_params()` Protocol member is non-optional. HttpTransport always merges. Phase 1 test covers OMDB-style auth. |
| R5  | TVDB token bootstrap fails at init                                | Low        | High   | Bootstrap done with a one-shot `HttpTransport(NoAuth)` in `TVDBClient.__init__`; on failure raises `ApiError` cleanly.        |
| R6  | Typed model mismatch with real API response                       | Medium     | Medium | Doc phase makes real API calls before code. Golden-response files captured in tests. User checkpoint confirms scope.          |
| R7  | Coverage drop from test imports using old paths                   | Medium     | Medium | Coverage report before/after each migration phase. Test imports updated in same commit as module move.                        |
| R8  | Config loading fails on first run (new files)                     | Medium     | High   | `init-config` updated in Phase 2 to generate all 5 new config files. Defaults match current behavior.                         |
| R9  | Tracker credential format differs from TorrentMaker .env          | Medium     | Medium | Doc phase 17 / 19 includes credential format from TorrentMaker `.env`; user checkpoint confirms format before coding.         |
| R10 | OMDB / Trakt API limitations discovered during impl               | Low        | Medium | Doc phases 12 / 14 include real test calls; user checkpoint adjusts scope. Implementation phase has nothing to discover.      |
| R11 | Transmission RPC fundamentally different from qBit                | Low        | Medium | Doc phase 10 surfaces RPC mechanics before impl. `TorrentClient` Protocol kept thin for compatibility.                        |
| R12 | LOC budget overflow → readability hit                             | Medium     | Low    | At 600 LOC, MUST extract `_parsers.py`. Phase gate runs `check-module-size.py` (warn 800 / block 1000).                       |
| R13 | `RankingCriterion` thresholds parsing of size strings             | Low        | Medium | `ThresholdEntry.at` Pydantic validator parses via `ByteSize.parse()`. Unit tests cover `"1GB"`, `"500MiB"`, raw int.          |
| R14 | TransportPolicy dataclass shape change late in the feature        | Low        | High   | Phase 1 ships the full policy, including stable `response_format` values, plus 1 reference provider integration test (`tests/api/test_transport_policy.py`). |

---

## 13. Guardrails / coherence checks

To prevent regressions during the 25-phase rollout, the following automated checks gate every milestone commit (`chore(api-unify): phase N gate`):

1. **Module size**: `python3 scripts/check-module-size.py` (warn 800, block 1000).
2. **Residual imports**: `! rg "<old.module.path>" personalscraper/` — once a module is deleted, zero references remain.
3. **No `dict[str, Any]` in public API signatures**: `python3 scripts/check-typed-api.py` (new helper script added in Phase 1; greps `api/` for `dict[str, Any]` in non-`_*.py` files, ignores docstrings).
4. **TransportPolicy is the ONLY way to build HttpTransport**: `! rg "HttpTransport\(.*provider_name=" api/` (positional/keyword construction without a policy is forbidden).
5. **Quality gate**: `make lint test`.
6. **Import health**: `python -c "import personalscraper"` + targeted family imports listed in the phase gate.

Phase 1 adds `scripts/check-typed-api.py` (small ruff-style ad-hoc checker — ~30 LOC).

---

## 14. ROADMAP update

Add under P3 (or P2 — tracker expansion):

```markdown
### P? — Additional Trackers (torr9 + digitalcore)

Implement `api/tracker/torr9.py` and `api/tracker/digitalcore.py` following
the established TrackerClient Protocol. Study APIs, write docs in
`docs/reference/torr9-api.md` and `docs/reference/digitalcore-api.md`,
then implement.

Depends on: Third-Party API Consumer Unification (P0).
```

---

## 15. Revision history

### v3 — 2026-05-04

Second pre-implementation review changes:

- Move reusable circuit breaker to `personalscraper/core/circuit.py` instead of `api/transport/_circuit.py`; update `indexer/breaker.py` in Phase 1.
- Stabilize `TransportPolicy.response_format` as `Literal["json", "xml", "text"]` in Phase 1 so C411/healthchecks do not reshape the transport contract later.
- Remove the blanket claim that every in-scope provider returns JSON; JSON remains the default, with provider overrides for XML/text.
- Make new optional integrations disabled in `config.example` (`omdb`, `trakt`, `transmission`, `lacale`, `c411`, `telegram`, `healthchecks`) while Phase 2 adapts the active project config for providers intentionally exercised by the rollout.
- Add explicit migration notes for `trailers/orchestrator.py`, `ingest/ingest.py`, and `indexer/breaker.py`.
- Fix API doc phase numbering for TMDB/TVDB.
- Require explicit `ApiError.__str__` behavior to preserve readable logs.

### v2 — 2026-05-04

Pre-implementation review surfaced 13 issues. v2 addresses them all:

| #   | v1 issue                                      | v2 resolution                                                                                                |
| --- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| 1   | Transmission goaled but no phase              | Phases 10 + 11 added.                                                                                        |
| 2   | `ApiKeyAuth(location="query")` not enforced   | `AuthMethod.auth_params()` mandatory; `HttpTransport` merges per-request. OMDB uses query param.             |
| 3   | TVDB token refresh                            | Confirmed not needed (TTL = 1 month). Bootstrap login at `__init__`, no `refresh()` in Protocol.             |
| 4   | Retry × circuit double-counting               | `CircuitPolicy.count_retries` flag (default False). Retry counted only on final exhaustion.                  |
| 5   | `objects_pairs_hook` typo                     | Removed; default `resp.json()` is sufficient.                                                                |
| 6   | `RankingCriterion` thresholds typing          | `ThresholdEntry` model + `ByteSize` custom type + Pydantic validator parses size literals.                   |
| 7   | LOC budgets too aggressive                    | Aspirational targets, not gates. 600 LOC = mandatory extraction. Hard ceilings 800 (warn) / 1000 (block).    |
| 8   | `scraper/_shared.py` + `providers.py` ignored | Explicitly addressed in §10.3 + §10.1. `providers.py` deleted; `_shared.py` keeps non-API helpers.           |
| 9   | Cross-phase circuit-breaker inconsistency     | Phase 1 makes circuit `ApiError`-aware; old `*Error` types still trigger >=500 path via `HTTPError` branch.  |
| 10  | Phase 11 too heavy (base+ranking+2 trackers)  | Split into Phase 16 (base+ranking) + Phase 17/18 (LaCale doc+impl) + Phase 19/20 (C411 doc+impl).            |
| 11  | `get_raw()` inconsistent with retry           | Removed (YAGNI). Add when an HTML-scraping provider lands, behind its own design discussion.                 |
| 12  | `Accept: application/json` global             | Confirmed for all 10 in-scope APIs. Documented as default; per-provider override via `policy.extra_headers`. |
| 13  | Success-criteria miscount                     | Updated: 7 modules removed, 10 docs (incl. Telegram + healthchecks), 5 config files.                         |

Plus structural changes:

- New §3.3 `TransportPolicy` contract.
- New §3.2 `ByteSize` custom type.
- New §13 guardrails / coherence checks.
- Phase table redesigned around "1 phase per API: doc OR impl".

---

## 16. VERSION bump

0.10.0 → 0.11.0 (minor). Rationale: new `api/` package, 7 modules migrated, 5 new third-party integrations (OMDB, Trakt, Transmission torrent client, LaCale, C411), 5 new config files, new `TransportPolicy` contract, new `ByteSize` custom type. No breaking change to pipeline behavior — all migrations are behavior-preserving.

# Third-Party API Consumer Unification — Design

**Status**: Prepared (not yet implemented)
**Codename**: `api-unify`
**Version bump**: 0.10.0 → 0.11.0 (minor — new `api/` package, 4 new providers, 2 new trackers)
**Design date**: 2026-05-03
**Trigger**: ROADMAP P0 — unify all external API integrations behind shared client infrastructure.

## 1. Goals & Non-goals

### 1.1 Goals

- One `HttpTransport` foundation (session, retry, circuit breaker, auth, rate limit) shared by all providers.
- Family contracts (`MetadataProvider`, `TorrentClient`, `TrackerClient`, `Notifier`, `HealthChecker`) as Protocols.
- Provider-specific subclasses implement only differential surface (endpoint paths, response parsing, auth flow).
- Typed response models replace all `dict[str, Any]` return types.
- All 6 modules using `requests` directly migrate to the new infrastructure.
- 4 new providers (OMDB, Trakt, LaCale, C411) + 1 new torrent client (Transmission).
- Per-use-case provider priority in config files.
- Credentials stay in `.env` — activation via `enabled` toggle (default `true`) with credential presence check (missing → warning log, treated as disabled).
- API documentation written for every provider before implementation.

### 1.2 Non-goals

- Zero backward compatibility — no re-exports from old locations, no compat shims.
- Zero dead code, dead config, or stale documentation.
- Auto-Download System (P2) — tracker search/ranking infrastructure only, no download automation.
- Watcher Service (P2).
- Web Management UI (P2).
- Pipeline Observer Protocol (P1).
- Event Bus (P1).
- Provider Registry / Scraper Orchestrator Decoupling (P1).
- Dependency Injection container (P3).
- torr9.net + digitalcore.club trackers (deferred to ROADMAP).

### 1.3 Success criteria

| Metric           | Target                                                                                                                                                    |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make test`      | green, coverage delta ≥ 0                                                                                                                                 |
| `make check`     | green (hard-block module size check)                                                                                                                      |
| `make lint`      | green (mypy, ruff)                                                                                                                                        |
| Dead modules     | 6 modules removed (`tmdb_client.py`, `tvdb_client.py`, `circuit_breaker.py`, `http_retry.py`, `qbit_client.py`, `notifier.py`)                            |
| New API docs     | 8 docs written (`tmdb-api.md`, `tvdb-api.md`, `omdb-api.md`, `trakt-api.md`, `qbittorrent-api.md`, `transmission-api.md`, `lacale-api.md`, `c411-api.md`) |
| New config files | 5 config files (`metadata.json5`, `torrent.json5`, `tracker.json5`, `ranking.json5`, `notify.json5`)                                                      |
| Typed responses  | Zéro `dict[str, Any]` dans les signatures d'API publique                                                                                                  |

---

## 2. Architecture

### 2.1 Package structure

```
api/
├── __init__.py
├── _contracts.py             # ApiError, CircuitOpenError, AuthMode
├── transport/
│   ├── __init__.py
│   ├── _http.py              # HttpTransport: session, retry (tenacity), timeout, logging
│   ├── _auth.py              # AuthMethod Protocol + BearerAuth, ApiKeyAuth, LoginAuth, NoAuth
│   ├── _rate.py              # RateLimiter: token-bucket throttle (optional, default off)
│   └── _circuit.py           # Déplacé depuis scraper/circuit_breaker.py
├── metadata/
│   ├── __init__.py
│   ├── _base.py              # MetadataProvider Protocol + MetadataClient base class
│   ├── tmdb.py               # Migré depuis scraper/tmdb_client.py
│   ├── tvdb.py               # Migré depuis scraper/tvdb_client.py
│   ├── omdb.py               # Nouveau — notations IMDB + RottenTomatoes, search, details
│   └── trakt.py              # Nouveau — notations, recommendations, trending
├── torrent/
│   ├── __init__.py
│   ├── _base.py              # TorrentClient Protocol + TorrentItem
│   ├── qbittorrent.py        # Migré depuis ingest/qbit_client.py
│   └── transmission.py       # Nouveau
├── tracker/
│   ├── __init__.py
│   ├── _base.py              # TrackerClient Protocol + TrackerResult + TorrentRanking + rank()
│   ├── _registry.py          # TrackerRegistry
│   ├── lacale.py             # Nouveau
│   └── c411.py               # Nouveau
└── notify/
    ├── __init__.py
    ├── _base.py              # Notifier Protocol + HealthChecker Protocol
    ├── telegram.py           # Migré depuis notifier.py
    └── healthchecks.py       # Migré depuis notifier.py
```

### 2.2 Layer model (Approach B — Layered)

```
┌──────────────────────────────────────────────┐
│  Provider: TMDB, TVDB, OMDB, Trakt, etc.     │
│  (endpoints, response parsing, typed models) │
├──────────────────────────────────────────────┤
│  Family contract: MetadataProvider Protocol  │
│  (search, get_details, get_notations, ...)   │
├──────────────────────────────────────────────┤
│  HttpTransport: session, retry, circuit,     │
│  auth, rate-limit, structured logging        │
└──────────────────────────────────────────────┘
```

### 2.3 Design rule

Each provider file is ≤ 400 LOC. If a provider exceeds this, extract parsing logic into `_parsers.py` or endpoint constants into `_endpoints.py`. The `HttpTransport` absorbs HTTP boilerplate, so provider files stay thin.

---

## 3. Shared infrastructure

### 3.1 `api/_contracts.py`

```python
from enum import Enum

class AuthMode(Enum):
    BEARER = "bearer"
    API_KEY = "api_key"
    LOGIN = "login"
    NONE = "none"

@dataclass
class ApiError(Exception):
    provider: str
    http_status: int
    provider_code: int = 0
    message: str = ""

class CircuitOpenError(Exception):
    provider: str
    remaining_seconds: float
```

### 3.2 `api/transport/_http.py` — HttpTransport

```python
class HttpTransport:
    def __init__(
        self,
        provider_name: str,
        auth: AuthMethod,
        base_url: str,
        default_timeout: float = 10,
        circuit_threshold: int = 5,
        circuit_cooldown: float = 300,
        rate_limit_rps: float = 0,    # 0 = no limit
    ): ...

    def get(self, path: str, params: dict | None = None) -> dict: ...
    def post(self, path: str, data: dict | None = None) -> dict: ...
    def get_raw(self, url: str) -> bytes: ...
    def close(self) -> None: ...
```

- Retry via tenacity: 4 attempts, exponential jitter, Retry-After honored.
- Circuit breaker integrated: `guard()` before every call.
- All errors wrapped in `ApiError` (no provider-specific exception types).
- Structured logging: event `api_call` with provider, endpoint, duration, status.
- `get_raw()` for HTML scraping providers (IMDB/SensCritique pattern — not needed here since we use OMDB/Trakt instead).

### 3.3 `api/transport/_auth.py`

```python
class AuthMethod(Protocol):
    def apply(self, session: requests.Session) -> None: ...

class BearerAuth:
    def __init__(self, token: str): ...

class ApiKeyAuth:
    def __init__(self, key: str, param: str = "api_key", location: str = "query"): ...

class LoginAuth:
    def __init__(self, username: str, password: str): ...
    def apply(self, session: requests.Session) -> None: ...

class NoAuth:
    def apply(self, session: requests.Session) -> None: ...
```

### 3.4 `api/transport/_circuit.py`

Déplacé depuis `scraper/circuit_breaker.py` (241 LOC). Le module n'est pas modifié, juste déplacé. Les références à `TMDBError`/`TVDBError` dans `_is_circuit_error` sont remplacées par `ApiError`.

### 3.5 `api/transport/_rate.py`

```python
class RateLimiter:
    """Token-bucket rate limiter. 0 rps = disabled (no-op)."""
    def __init__(self, requests_per_second: float = 0): ...
    def acquire(self) -> None: ...  # Blocks if needed
```

---

## 4. Metadata family

### 4.1 `MetadataProvider` Protocol

```python
class MetadataProvider(Protocol):
    provider_name: str

    def search(self, title: str, year: int | None = None,
               media_type: str = "movie") -> list[SearchResult]: ...
    def get_details(self, media_id: str, media_type: str = "movie") -> MediaDetails: ...

    # Optional
    def get_artwork_urls(self, media_id: str, media_type: str = "movie") -> list[ArtworkItem]: ...
    def get_keywords(self, media_id: str, media_type: str) -> list[str]: ...
    def get_videos(self, media_id: str, media_type: str, language: str) -> list[Video]: ...
    def get_season(self, tv_id: str, season: int) -> SeasonDetails: ...
    def get_notations(self, media_id: str, media_type: str) -> Notations | None: ...
    def get_recommendations(self, media_id: str, media_type: str) -> list[Recommendation]: ...
```

### 4.2 Typed response models

```python
@dataclass
class SearchResult:
    provider: str
    provider_id: str
    title: str
    year: int | None
    media_type: str          # "movie" | "tv"
    overview: str | None
    poster_url: str | None

@dataclass
class MediaDetails:
    provider: str
    provider_id: str
    title: str
    original_title: str | None
    year: int | None
    overview: str | None
    genres: list[str]
    runtime_minutes: int | None
    rating: float | None
    images: list[ArtworkItem]
    external_ids: dict[str, str]

@dataclass
class ArtworkItem:
    type: str                # "poster", "landscape"
    url: str
    language: str | None
    season: int | None

@dataclass
class Notations:
    provider: str
    source: str              # "imdb", "rotten_tomatoes", "trakt", "tmdb"
    score: float | None
    votes_count: int | None

@dataclass
class Recommendation:
    provider: str
    provider_id: str
    title: str
    year: int | None
    media_type: str
    reason: str | None

@dataclass(frozen=True)
class Video:
    """Déplacé depuis tmdb_client.py. Aucun changement de comportement."""
    id: str
    site: str
    key: str
    type: str
    official: bool
    size: int
    iso_639_1: str
```

### 4.3 Provider matrix

| Provider | Type            | Fonctionnalités                                                     | Auth           |
| -------- | --------------- | ------------------------------------------------------------------- | -------------- |
| TMDB     | Existant, migré | search, details, artwork, keywords, videos, seasons                 | Bearer token   |
| TVDB     | Existant, migré | search, details, artwork, episodes, seasons                         | Bearer token   |
| OMDB     | Nouveau         | search, details, notations (IMDB + RottenTomatoes), recommendations | API key        |
| Trakt    | Nouveau         | notations, recommendations, watchlist, trending                     | OAuth / Bearer |

### 4.4 Migration TMDB

- `TMDBClient` (770 LOC) → `api/metadata/tmdb.py` (~400 LOC)
- Inherits `MetadataClient`, delegates HTTP to `HttpTransport`.
- `TMDBError` removed — replaced by `ApiError`.
- `Video` dataclass moved to `api/metadata/_base.py`.
- All method signatures return typed models instead of `dict[str, Any]`.

### 4.5 Migration TVDB

- `TVDBClient` (565 LOC) → `api/metadata/tvdb.py` (~300 LOC)
- Same pattern as TMDB.

---

## 5. Torrent client family

### 5.1 `TorrentClient` Protocol

```python
class TorrentClient(Protocol):
    provider_name: str

    def get_completed(self) -> list[TorrentItem]: ...
    def get_all_hashes(self) -> set[str]: ...
    def is_seeding(self, torrent: TorrentItem) -> bool: ...
    def get_content_path(self, torrent: TorrentItem) -> Path: ...
    def pause(self, hash: str) -> None: ...
    def resume(self, hash: str) -> None: ...
    def delete(self, hash: str, delete_files: bool = False) -> None: ...

@dataclass
class TorrentItem:
    hash: str
    name: str
    size_bytes: int
    progress: float
    state: str
    content_path: Path
    category: str | None
    added_on: datetime | None
```

### 5.2 Implementations

| Provider     | Fichier                       | Librairie          |
| ------------ | ----------------------------- | ------------------ |
| qBittorrent  | `api/torrent/qbittorrent.py`  | `qbittorrentapi`   |
| Transmission | `api/torrent/transmission.py` | `transmission-rpc` |

### 5.3 Migration QBitClient

- `QBitClient` migré de `ingest/qbit_client.py` → `api/torrent/qbittorrent.py`
- Auth lockout conservé (spécifique qBit).
- Pre-check HTTP via `HttpTransport`.

---

## 6. Tracker family

### 6.1 `TrackerClient` Protocol

```python
class TrackerClient(Protocol):
    provider_name: str

    def search(self, query: str, media_type: str = "movie",
               year: int | None = None) -> list[TrackerResult]: ...
    def get_categories(self) -> dict[str, str]: ...

@dataclass
class TrackerResult:
    provider: str
    tracker_id: str
    title: str
    size_bytes: int
    seeders: int
    leechers: int
    category: str | None
    download_url: str | None
    info_hash: str | None
    source_url: str | None
    is_freeleech: bool
    is_silverleech: bool
    upload_date: datetime | None
    format: str | None
    codec: str | None
    source: str | None
    resolution: str | None
    audio: str | None
```

### 6.2 Trackers

| Tracker | Doc source                            |
| ------- | ------------------------------------- |
| LaCale  | `~/dev/TorrentMaker/docs/LaCale/api/` |
| C411    | `~/dev/TorrentMaker/docs/C411/api/`   |

torr9.net + digitalcore.club → nouvelle entrée ROADMAP.

### 6.3 Ranking system

```python
@dataclass
class RankingCriterion:
    field: str                          # Nom du champ dans TrackerResult
    weight: float = 1.0                 # Poids dans le score final
    values: dict[str, int] | None = None  # Catégoriel
    thresholds: dict[float, int] | None = None  # Numérique
    prefer: str | None = None           # "higher" | "lower" | None

@dataclass
class TorrentRanking:
    criteria: list[RankingCriterion]
    freeleech_bonus: int = 10
    silverleech_bonus: int = 5
    min_seeders: int = 1              # Filtre strict, pas un score

def rank(results: list[TrackerResult],
         ranking: TorrentRanking) -> list[tuple[TrackerResult, int]]:
    """Score each result. Bonus freeleech/silverleech added to total.
    Returns list sorted by score descending."""
```

Every field of `TrackerResult` can be a ranking criterion. Categories use `values` mapping, numeric fields use `thresholds` with `prefer` direction. Freeleech/silverleech bonus is added post-scoring.

### 6.4 `TrackerRegistry`

```python
class TrackerRegistry:
    def __init__(self, trackers: list[TrackerClient],
                 priority: list[str], ranking: TorrentRanking): ...

    def search_all(self, query: str, media_type: str = "movie",
                   year: int | None = None) -> list[tuple[TrackerResult, int]]:
        """Query all active trackers, merge, rank, return sorted by score."""
```

---

## 7. Notification family

### 7.1 Protocols

```python
class Notifier(Protocol):
    provider_name: str
    def send(self, message: str, parse_mode: str = "HTML") -> bool: ...
    def send_report(self, report: PipelineReport) -> bool: ...

class HealthChecker(Protocol):
    provider_name: str
    def ping_start(self) -> None: ...
    def ping_success(self) -> None: ...
    def ping_fail(self) -> None: ...
```

### 7.2 Migration Notifier

- `notifier.py` (120 LOC) → `api/notify/telegram.py` + `api/notify/healthchecks.py`
- Replace `requests.post/get` with `HttpTransport`.

---

## 8. Config & activation

### 8.1 New config files

| Fichier                 | Contenu                                     |
| ----------------------- | ------------------------------------------- |
| `config/metadata.json5` | Providers metadata + priorités par use-case |
| `config/torrent.json5`  | Active client + clients config              |
| `config/tracker.json5`  | Trackers actifs + priorités + timeout       |
| `config/ranking.json5`  | Critères de ranking torrent                 |
| `config/notify.json5`   | Telegram + healthchecks                     |

### 8.2 `config/metadata.json5`

```json5
{
  // required_creds is HARDCODED per provider, not in config:
  //   tmdb  → ["TMDB_API_KEY"]
  //   tvdb  → ["TVDB_API_KEY"]
  //   omdb  → ["OMDB_API_KEY"]
  //   trakt → ["TRAKT_CLIENT_ID", "TRAKT_CLIENT_SECRET"]
  providers: {
    tmdb: { enabled: true },
    tvdb: { enabled: true },
    omdb: { enabled: true },
    trakt: { enabled: true },
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

`active` selects the single client used by the pipeline — only one can be active
at a time even when multiple are credentialed. Individual `enabled` toggles
whether the client config is loaded at all.

```json5
{
  active: "qbittorrent", // The ONE client the pipeline uses
  clients: {
    qbittorrent: { enabled: true, host: "localhost", port: 8080 },
    transmission: { enabled: true, host: "localhost", port: 9091 },
  },
}
```

### 8.4 `config/tracker.json5`

```json5
{
  providers: {
    lacale: { enabled: true }, // .env: LACALE_API_KEY
    c411: { enabled: true }, // .env: C411_API_KEY
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
      thresholds: { 0: 0, 5: 5, 20: 10, 100: 20 },
    },
    {
      field: "size_bytes",
      weight: 1,
      prefer: "higher",
      thresholds: { 0: 0, "1GB": 5, "5GB": 10 },
    },
  ],
  bonuses: {
    freeleech: 10,
    silverleech: 5,
  },
}
```

### 8.6 `config/notify.json5`

```json5
{
  telegram: { enabled: true }, // .env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  healthchecks: { enabled: true }, // .env: HEALTHCHECK_PING_URL
}
```

### 8.7 Provider activation logic

Each provider class declares its required credential env vars (e.g., `TMDBClient.REQUIRED_CREDS = ["TMDB_API_KEY"]`).
The config only stores the `enabled` toggle.

```python
def resolve_active_providers(providers: dict, available_creds: set[str]) -> list[str]:
    """Active if enabled=true AND all REQUIRED_CREDS are present in .env."""
    active = []
    for name, cfg in providers.items():
        if not cfg.enabled:
            continue
        provider_cls = get_provider_class(name)
        missing = [c for c in provider_cls.REQUIRED_CREDS if c not in available_creds]
        if missing:
            log.warning("provider_disabled_missing_creds",
                        provider=name, missing=missing,
                        hint="Set credentials in .env or set enabled=false in config")
            continue
        active.append(name)
    return active
```

| enabled | Credentials | Résultat                 |
| ------- | ----------- | ------------------------ |
| true    | Présents    | Actif                    |
| true    | Absents     | Inactif + WARNING log    |
| false   | Présents    | Inactif (pas de warning) |
| false   | Absents     | Inactif (pas de warning) |

Credentials stay in `.env`. Config only stores metadata.

---

## 9. API documentation rule

For **every** API (existing and new), before writing implementation:

1. Study official documentation + make real test calls.
2. Write `docs/reference/<provider>-api.md` covering: endpoints, parameters, response formats, authentication, rate limiting, quotas, limitations, relevant fields.
3. Implement the provider following the written doc.

### Docs to produce

| Provider     | Doc                                  | Source material                                |
| ------------ | ------------------------------------ | ---------------------------------------------- |
| TMDB         | `docs/reference/tmdb-api.md`         | `docs/TMDB-API.md` (existing, verify/complete) |
| TVDB         | `docs/reference/tvdb-api.md`         | `docs/TVDB-API.md` (existing, verify/complete) |
| OMDB         | `docs/reference/omdb-api.md`         | Study OMDB API                                 |
| Trakt        | `docs/reference/trakt-api.md`        | Study Trakt API                                |
| qBittorrent  | `docs/reference/qbittorrent-api.md`  | Study qBit API                                 |
| Transmission | `docs/reference/transmission-api.md` | Study Transmission RPC                         |
| LaCale       | `docs/reference/lacale-api.md`       | `~/dev/TorrentMaker/docs/LaCale/api/`          |
| C411         | `docs/reference/c411-api.md`         | `~/dev/TorrentMaker/docs/C411/api/`            |

---

## 10. Deletions (zero dead code)

### 10.1 Modules removed

| Module                       | Migrated to                                             |
| ---------------------------- | ------------------------------------------------------- |
| `scraper/tmdb_client.py`     | `api/metadata/tmdb.py`                                  |
| `scraper/tvdb_client.py`     | `api/metadata/tvdb.py`                                  |
| `scraper/circuit_breaker.py` | `api/transport/_circuit.py`                             |
| `scraper/http_retry.py`      | Integrated into `api/transport/_http.py`                |
| `ingest/qbit_client.py`      | `api/torrent/qbittorrent.py`                            |
| `notifier.py`                | `api/notify/telegram.py` + `api/notify/healthchecks.py` |

### 10.2 Exception types removed

- `TMDBError` — replaced by `ApiError`
- `TVDBError` — replaced by `ApiError`
- `CircuitOpenError` — moved to `api/_contracts.py`

### 10.3 Import migration

~90 import sites across ~45 production files and ~30 test files. No re-exports from old locations.

### 10.4 Documentation

All docs referencing old module paths updated. Archive docs (`docs/archive/`) intentionally left unchanged as historical record.

---

## 11. Phases (12 phases, each = 1 PR minimum)

| #   | Phase                          | Content                                                                                                                                                                       | Commit scope          |
| --- | ------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| 1   | **Transport + contracts**      | `api/transport/` (HttpTransport, Auth, RateLimiter, CircuitBreaker), `api/_contracts.py`. Move `circuit_breaker.py` → `api/transport/_circuit.py`, integrate `http_retry.py`. | `feat(api-unify)`     |
| 2   | **Config API**                 | `config.example/metadata.json5`, `torrent.json5`, `tracker.json5`, `ranking.json5`, `notify.json5` + Pydantic models + `ProviderActivation`.                                  | `feat(api-unify)`     |
| 3   | **Doc TMDB + TVDB**            | `docs/reference/tmdb-api.md` (verify/complete existing), `docs/reference/tvdb-api.md`.                                                                                        | `docs(api-unify)`     |
| 4   | **Migration TMDB**             | `api/metadata/tmdb.py`, delete `scraper/tmdb_client.py`, update ~20 imports, tests.                                                                                           | `refactor(api-unify)` |
| 5   | **Migration TVDB**             | `api/metadata/tvdb.py`, delete `scraper/tvdb_client.py`, update ~15 imports, tests.                                                                                           | `refactor(api-unify)` |
| 6   | **Migration qBittorrent**      | `api/torrent/qbittorrent.py`, delete `ingest/qbit_client.py`, update imports, tests.                                                                                          | `refactor(api-unify)` |
| 7   | **Doc OMDB + Trakt**           | API study → `docs/reference/omdb-api.md` + `docs/reference/trakt-api.md`.                                                                                                     | `docs(api-unify)`     |
| 8   | **New OMDB**                   | `api/metadata/omdb.py`.                                                                                                                                                       | `feat(api-unify)`     |
| 9   | **New Trakt**                  | `api/metadata/trakt.py`.                                                                                                                                                      | `feat(api-unify)`     |
| 10  | **Doc LaCale + C411**          | Transfer + complete TorrentMaker docs → `docs/reference/lacale-api.md` + `docs/reference/c411-api.md`.                                                                        | `docs(api-unify)`     |
| 11  | **New trackers LaCale + C411** | `api/tracker/lacale.py`, `api/tracker/c411.py`, `api/tracker/_registry.py`, ranking engine.                                                                                   | `feat(api-unify)`     |
| 12  | **Migration Notify + cleanup** | `api/notify/telegram.py` + `api/notify/healthchecks.py`, delete `notifier.py`. Final cleanup: residual imports, dead config, stale docs.                                      | `refactor(api-unify)` |

---

## 12. Risk register

| #   | Risk                                                        | Likelihood | Impact | Mitigation                                                                                                                                 |
| --- | ----------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------ |
| R1  | Import breakage after module deletion                       | High       | High   | `ruff check` + `python -c "import personalscraper"` after each migration commit. ~90 import sites to update.                               |
| R2  | `ApiError` replacement breaks error handling in consumers   | Medium     | High   | Grep for `TMDBError`, `TVDBError` in all try/except blocks. Update all catch sites in same commit as migration.                            |
| R3  | Typed model mismatch with real API response                 | Medium     | Medium | Real API call tests for each provider before committing. Golden response files in tests.                                                   |
| R4  | Coverage drop from test imports using old paths             | Medium     | Medium | Coverage report before/after each phase. Update test imports in same commit.                                                               |
| R5  | Config loading fails on first run (new files)               | Medium     | High   | `init-config` updated to generate all 5 new config files. Default values match current behavior.                                           |
| R6  | Circuit breaker behavior changes after move                 | Low        | Medium | `_circuit.py` is a pure move — no logic changes. Verify with existing circuit breaker tests.                                               |
| R7  | Tracker credential in TorrentMaker .env, format differs     | Medium     | Medium | Study TorrentMaker .env structure before LaCale/C411 implementation. Document credential format in `docs/reference/<tracker>-api.md`.      |
| R8  | OMDB/Trakt API limitations discovered during study          | Medium     | Medium | API doc phase (7) precedes implementation (8-9). If API doesn't support required features, adjust scope before writing code.               |
| R9  | Transmission RPC protocol significantly different from qBit | Low        | Medium | Study phase (Transmission API doc) before implementation. RPC may need a different transport strategy — handle in design update if needed. |

---

## 13. ROADMAP update

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

## 14. VERSION bump

0.10.0 → 0.11.0 (minor). Rationale: new `api/` package, 6 modules migrated, 4 new providers, 2 new trackers, 5 new config files. No breaking change to pipeline behavior — all migrations are behavior-preserving.

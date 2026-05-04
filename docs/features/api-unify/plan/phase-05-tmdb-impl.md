# Phase 5 — TMDB Migration

**Type**: impl
**Goal**: Migrate `scraper/tmdb_client.py` (770 LOC) → `api/metadata/tmdb.py`. Delete old module, update all imports, return typed models.

## Gate (prereq)

Phase 4 complete. `docs/reference/tmdb-api.md` exists. User checkpoint captured.

## Sub-phases

### 5.1 — Build `api/metadata/tmdb.py`

Rewrite `tmdb_client.py` against the new contract:

1. Class `TMDBClient(MetadataClient)`. `REQUIRED_CREDS = ["TMDB_API_KEY"]`.
2. Class method `policy(cls, api_key: str, *, circuit: CircuitPolicy | None = None) -> TransportPolicy`:
   ```python
   @classmethod
   def policy(cls, api_key: str, *, circuit: CircuitPolicy | None = None) -> TransportPolicy:
       return TransportPolicy(
           provider_name="tmdb",
           base_url="https://api.themoviedb.org/3",
           auth=BearerAuth(api_key),
           timeout_seconds=10,
           retry=RetryPolicy(max_attempts=4),
           circuit=circuit or CircuitPolicy(failure_threshold=5, cooldown_seconds=300),
           rate_limit=RateLimitPolicy(requests_per_second=40),  # below 50 rps cap
       )
   ```
3. `__init__(self, transport: HttpTransport, language: str = "fr-FR", fallback_language: str = "en-US", prefer_local_title: bool = True)`.
4. All HTTP calls go through `self._transport.get(path, params=...)`.
5. Drop: `requests.Session`, `HTTPAdapter`, `Urllib3Retry`, tenacity decorators, `CircuitBreaker` instantiation, `TMDBError`.
6. All public methods return typed models from `_base.py`. **Zero `dict[str, Any]` in signatures.**
7. `Video` is imported from `_base.py`, not redefined.
8. `circuit` property returns `self._transport.circuit` (CircuitBreaker instance).

Methods to migrate:

- `search()` (Protocol)
- `get_details()` (Protocol)
- `get_artwork_urls()`
- `search_movie()`, `search_tv()` (TMDB-specific, kept as public)
- `get_movie()`, `get_tv()`, `get_tv_season()` (TMDB-specific)
- `get_image_url()` (helper)
- `get_keywords()`
- `fetch_movie_videos()`, `fetch_tv_videos()`, `fetch_tv_season_videos()` → consolidated as `get_videos(media_id, media_type, language)` per Protocol; TMDB-specific season variant kept as separate method.

`_search_paginated()` → kept as `_search_paginated()` private helper.

### 5.2 — Extraction at 600 LOC trigger

If `api/metadata/tmdb.py` exceeds 600 LOC after migration, MUST extract:

- `api/metadata/_tmdb_parsers.py` — `_parse_search_result(raw) -> SearchResult`, `_parse_media_details(raw) -> MediaDetails`, `_parse_artwork(raw) -> list[ArtworkItem]`, `_parse_videos(raw) -> list[Video]`.
- `api/metadata/_tmdb_endpoints.py` — path constants if many.

Re-run `python3 scripts/check-module-size.py` after extraction.

**Commit (this sub-phase)**: `feat(api-unify): migrate TMDB client to api/metadata/tmdb.py`

### 5.3 — Update consumers + test imports

Find every importer:

```bash
rg "from personalscraper\.scraper\.tmdb_client import|from personalscraper\.scraper import tmdb_client" personalscraper/ tests/
rg "TMDBError" personalscraper/ tests/
```

Rewrite:

- `from personalscraper.scraper.tmdb_client import TMDBClient` → `from personalscraper.api.metadata.tmdb import TMDBClient`
- `from personalscraper.scraper.tmdb_client import TMDBError` → `from personalscraper.api._contracts import ApiError`
- Any `Video` import from old path → `from personalscraper.api.metadata._base import Video`
- Any consumer that did `result["title"]` on a TMDB return (dict-shaped) → `result.title` (typed model).

Construction site: TMDBClient was likely instantiated as `TMDBClient(api_key=...)`. New form:

```python
policy = TMDBClient.policy(api_key=os.environ["TMDB_API_KEY"])
transport = HttpTransport(policy)
client = TMDBClient(transport=transport, language=cfg.metadata.defaults.language)
```

This boilerplate likely belongs in a small builder in `personalscraper/scraper/run.py` or `orchestrator.py`.

Explicit consumer work:

- `personalscraper/scraper/orchestrator.py`: this is the **main** TMDB
  construction site. Rewrite `TMDBClient(...)` instantiation to use
  `TMDBClient.policy(api_key, circuit=CircuitPolicy(...))` + `HttpTransport(policy)`,
  preserving the existing `circuit_breaker_threshold` /
  `circuit_breaker_cooldown` fields read from `conf/models/scraper.py` as
  `CircuitPolicy(failure_threshold=..., cooldown_seconds=...)` arguments.
- `personalscraper/library/rescraper.py`: update type imports and construction.
- `personalscraper/trailers/orchestrator.py`: preserve the trailers-specific
  TMDB circuit configuration from `config.trailers.circuit_breakers.tmdb_videos`
  by passing a custom `CircuitPolicy` to `TMDBClient.policy(...)` before
  constructing the `HttpTransport`. Do not collapse this into the main scraper
  TMDB circuit; trailer lookup intentionally has separate outage tolerance.
- Any consumer still using dict-shaped TMDB results must be converted to typed
  attributes in the same commit.

Update test files in the same commit.

**Commit**: `refactor(api-unify): rewire TMDB consumers and tests to api/metadata/tmdb`

### 5.4 — Delete `scraper/tmdb_client.py`

```bash
git rm personalscraper/scraper/tmdb_client.py
```

Also delete `scraper/providers.py` IF its only consumer was `tmdb_client.py` and `tvdb_client.py`. Otherwise wait for Phase 7. Verify:

```bash
rg "from personalscraper\.scraper\.providers import" personalscraper/ tests/
```

If still imported by `tvdb_client.py` (Phase 7 not yet done), `providers.py` stays for one more phase.

**Commit**: `refactor(api-unify): delete scraper/tmdb_client.py`

### 5.5 — Phase 5 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.metadata.tmdb import TMDBClient; assert TMDBClient.REQUIRED_CREDS == ['TMDB_API_KEY']"
! rg "tmdb_client" personalscraper/ tests/ --files-with-matches
! rg "TMDBError" personalscraper/ tests/
```

Coverage delta vs Phase 4 baseline: ≥ 0.

**Commit**: `chore(api-unify): phase 5 gate — tmdb migration done`

# Phase 7 — TVDB Migration

**Type**: impl
**Goal**: Migrate `scraper/tvdb_client.py` (565 LOC) → `api/metadata/tvdb.py`. Bootstrap auth at init.

## Gate (prereq)

Phase 6 complete. `docs/reference/tvdb-api.md` exists. User checkpoint captured.

## Sub-phases

### 7.1 — Build `api/metadata/tvdb.py`

1. Class `TVDBClient(MetadataClient)`. `REQUIRED_CREDS = ["TVDB_API_KEY"]`.
2. Bootstrap login at init:

```python
class TVDBClient(MetadataClient):
    REQUIRED_CREDS: ClassVar[list[str]] = ["TVDB_API_KEY"]

    def __init__(self, api_key: str, language: str = "fr-FR") -> None:
        # Step 1: bootstrap login with NoAuth transport
        bootstrap_policy = TransportPolicy(
            provider_name="tvdb-bootstrap",
            base_url="https://api4.thetvdb.com/v4",
            auth=NoAuth(),
            timeout_seconds=15,
        )
        with HttpTransport(bootstrap_policy) as bootstrap:
            resp = bootstrap.post("/login", data={"apikey": api_key})
            jwt = resp["data"]["token"]

        # Step 2: build main transport with BearerAuth(jwt)
        main_policy = TransportPolicy(
            provider_name="tvdb",
            base_url="https://api4.thetvdb.com/v4",
            auth=BearerAuth(jwt),
            timeout_seconds=15,
            retry=RetryPolicy(max_attempts=4),
            circuit=CircuitPolicy(failure_threshold=5, cooldown_seconds=300),
        )
        super().__init__(transport=HttpTransport(main_policy), language=language)
```

3. Drop `TVDBError`, `requests`, manual retry, etc.
4. Migrate `_TVDB_LANG_MAP` from `scraper/_shared.py` into `api/metadata/tvdb.py` (TVDB-specific).
5. All public methods return typed models.

Methods: `search()`, `get_details()`, `get_artwork_urls()`, `get_series()`, `get_episodes()`, `get_movie()`, `get_season()`.

### 7.2 — Extraction at 600 LOC trigger

If file > 600 LOC after migration:

- `_tvdb_parsers.py` — typed-model assembly.
- `_tvdb_endpoints.py` — path constants.

### 7.3 — Update consumers + delete old

```bash
rg "from personalscraper\.scraper\.tvdb_client import|TVDBError" personalscraper/ tests/
```

Rewrite imports + `TVDBError` → `ApiError`.

Explicit consumer work:

- `personalscraper/library/rescraper.py`: update type imports, construction,
  and any dict-shaped TVDB result access to typed attributes.
- Any remaining TVDB imports in tests must move to
  `personalscraper.api.metadata.tvdb`.

Remove `_TVDB_LANG_MAP` from `scraper/_shared.py` (already moved into `api/metadata/tvdb.py`). Verify no other consumer:

```bash
rg "_TVDB_LANG_MAP" personalscraper/ tests/
# Expected: only api/metadata/tvdb.py — zero hits in scraper/ or other modules.
```

Delete:

- `scraper/tvdb_client.py`
- `scraper/providers.py` (now zero consumers — TMDB and TVDB both use `api/metadata/_base.MetadataProvider`).

```bash
git rm personalscraper/scraper/tvdb_client.py
git rm personalscraper/scraper/providers.py
```

**Commit**: `refactor(api-unify): migrate TVDB client and remove tvdb_client / providers`

### 7.4 — Move tenacity helpers to `core/http_helpers.py` + rewire `artwork.py`

`scraper/http_retry.py` exposes two helpers still consumed by
`scraper/artwork.py`: `build_retry_logger` and `make_retryable_predicate`.
After this phase, `tmdb_client.py` and `tvdb_client.py` are gone, so the only
remaining consumer is `artwork.py`. The helpers move to a neutral location so
`scraper/http_retry.py` can be deleted.

Steps:

1. Create `personalscraper/core/http_helpers.py` with ONLY the two helpers
   (and their direct private dependencies: `_RETRYABLE_STATUS_CODES`,
   `_retry_after_from_exception`, `RetryAfterAwareWait` if still required by
   `artwork.py`). Drop everything else (provider-error-types coupling, etc.).
   The content is extracted from `scraper/http_retry.py`, which still exists
   at this point — it will be deleted in the next sub-phase.
2. Update `scraper/artwork.py` import:
   `from personalscraper.scraper.http_retry import ...` →
   `from personalscraper.core.http_helpers import build_retry_logger, make_retryable_predicate`.
3. Verify no other consumer of the moved file:

```bash
rg "from personalscraper\.scraper\.http_retry import|from personalscraper\.scraper import http_retry" personalscraper/ tests/
# Expected: zero hits.
```

**Commit**: `refactor(api-unify): move tenacity helpers to core/http_helpers.py and rewire artwork.py`

### 7.5 — Delete `scraper/http_retry.py`

```bash
git rm personalscraper/scraper/http_retry.py
```

**Commit**: `refactor(api-unify): delete scraper/http_retry.py`

### 7.6 — Phase 7 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.metadata.tvdb import TVDBClient; assert TVDBClient.REQUIRED_CREDS == ['TVDB_API_KEY']"
python -c "from personalscraper.core.http_helpers import build_retry_logger, make_retryable_predicate"
! rg "scraper\.tvdb_client|scraper/providers\.py|scraper\.http_retry" personalscraper/ tests/ --files-with-matches
! rg "TVDBError" personalscraper/ tests/
```

**Commit**: `chore(api-unify): phase 7 gate — tvdb migration done`

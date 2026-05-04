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

Delete:

- `scraper/tvdb_client.py`
- `scraper/providers.py` (now zero consumers — TMDB and TVDB both use `api/metadata/_base.MetadataProvider`).
- `scraper/http_retry.py` (last consumers were tmdb_client and tvdb_client).

Remove `_TVDB_LANG_MAP` from `scraper/_shared.py` (already moved into `api/metadata/tvdb.py`). Verify no other consumer:

```bash
rg "_TVDB_LANG_MAP" personalscraper/ tests/
# Expected: only api/metadata/tvdb.py — zero hits in scraper/ or other modules.
```

```bash
git rm personalscraper/scraper/tvdb_client.py
git rm personalscraper/scraper/providers.py
git rm personalscraper/scraper/http_retry.py
```

**Commit**: `refactor(api-unify): migrate TVDB client and remove tvdb_client / providers / http_retry`

### 7.4 — Phase 7 gate

```bash
make check && python3 scripts/check-module-size.py && python3 scripts/check-typed-api.py
make lint test
python -c "from personalscraper.api.metadata.tvdb import TVDBClient; assert TVDBClient.REQUIRED_CREDS == ['TVDB_API_KEY']"
! rg "tvdb_client|providers\.py|http_retry" personalscraper/ tests/ --files-with-matches
! rg "TVDBError" personalscraper/ tests/
```

**Commit**: `chore(api-unify): phase 7 gate — tvdb migration done`

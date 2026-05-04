# Phase 4 — Migration TMDB

## Gate

**Prerequisites**: Phase 3 complete. `docs/reference/tmdb-api.md` exists. `api/transport/` and `api/_contracts.py` exist and tested.

## Goal

Migrate `scraper/tmdb_client.py` (770 LOC) → `api/metadata/tmdb.py` (~400 LOC). All method signatures return typed models. `TMDBError` → `ApiError`. Delete old module.

## Sub-phases

### 4.1 — Create `api/metadata/` package + `_base.py`

**Files**:

- `personalscraper/api/metadata/__init__.py`
- `personalscraper/api/metadata/_base.py`

`_base.py` contains:

- `MetadataProvider` Protocol (from DESIGN §4.1)
- `SearchResult`, `MediaDetails`, `ArtworkItem`, `Notations`, `Recommendation`, `Video` dataclasses (from DESIGN §4.2)
- `SeasonDetails` dataclass
- `MetadataClient` base class with `__init__(self, transport: HttpTransport, language: str = "fr-FR")` and default `NotImplementedError` stubs for optional methods

**Commit**: `feat(api-unify): add metadata package with base types and protocol`

### 4.2 — Create `api/metadata/tmdb.py`

Copy `scraper/tmdb_client.py` → `api/metadata/tmdb.py`. Rewrite:

1. Remove: `requests.Session`, `HTTPAdapter`, `Urllib3Retry`, tenacity decorators, `CircuitBreaker` creation — all handled by `HttpTransport`
2. Remove: `TMDBError`, `CircuitOpenError` imports — use `ApiError` from `api/_contracts.py`
3. `__init__` → accepts `transport: HttpTransport` and `language: str`, stores `self._transport = transport`, `self._language = language`
4. `_get` → delegates to `self._transport.get()`
5. All public methods → return typed models instead of `dict[str, Any]`
6. `Video` → imported from `api/metadata/_base.py` (not defined here)
7. `TMDBClient.circuit` property → delegates to `transport.circuit`
8. Class-level `REQUIRED_CREDS = ["TMDB_API_KEY"]`

Methods to migrate: `search()`, `get_details()`, `get_artwork_urls()`, `search_movie()`, `search_tv()`, `get_movie()`, `get_tv()`, `get_tv_season()`, `get_image_url()`, `get_keywords()`, `fetch_movie_videos()`, `fetch_tv_videos()`, `fetch_tv_season_videos()`.

`_search_paginated` → kept as internal helper.

### 4.3 — Update all TMDB consumers (~20 import sites)

```bash
rg "from personalscraper.scraper.tmdb_client import" personalscraper/ --files-with-matches
rg "from personalscraper.scraper import tmdb_client" personalscraper/ --files-with-matches
rg "TMDBError" personalscraper/ --files-with-matches
```

Update every import:

- `from personalscraper.scraper.tmdb_client import TMDBClient` → `from personalscraper.api.metadata.tmdb import TMDBClient`
- `TMDBError` → `ApiError`
- Any `dict[str, Any]` usage of TMDB results → typed model attribute access

Update test files with same import changes.

**Commit**: `refactor(api-unify): migrate TMDB client to api/metadata/tmdb.py`

### 4.4 — Delete `scraper/tmdb_client.py`

```bash
git rm personalscraper/scraper/tmdb_client.py
```

Verify: `python -c "import personalscraper"` and `make lint test` pass.

**Commit**: `refactor(api-unify): delete scraper/tmdb_client.py`

### 4.5 — Phase 4 gate

```bash
make check && python3 scripts/check-module-size.py
python -c "from personalscraper.api.metadata.tmdb import TMDBClient"
```

Verify no residual `tmdb_client` imports exist:

```bash
! rg "tmdb_client" personalscraper/ --files-with-matches
```

**Commit**: `chore(api-unify): phase 4 gate — tmdb migration done`

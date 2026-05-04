# Phase 5 — Migration TVDB

## Gate

**Prerequisites**: Phase 4 complete. `api/metadata/` package exists, TMDB migration verified.

## Goal

Migrate `scraper/tvdb_client.py` (565 LOC) → `api/metadata/tvdb.py` (~300 LOC). Same pattern as Phase 4.

## Sub-phases

### 5.1 — Create `api/metadata/tvdb.py`

Copy `scraper/tvdb_client.py` → `api/metadata/tvdb.py`. Rewrite:

1. All HTTP → delegated to `HttpTransport`
2. Auth token refresh logic → handled by `AuthMethod` on transport
3. `TVDBError` → `ApiError`
4. Return types → typed models from `api/metadata/_base.py`
5. `REQUIRED_CREDS = ["TVDB_API_KEY"]`

**Commit**: `refactor(api-unify): migrate TVDB client to api/metadata/tvdb.py`

### 5.2 — Update all TVDB consumers (~15 import sites)

```bash
rg "from personalscraper.scraper.tvdb_client import" personalscraper/ --files-with-matches
rg "TVDBError" personalscraper/ --files-with-matches
```

Update all imports and `TVDBError` → `ApiError`.

**Commit**: `refactor(api-unify): update TVDB imports and error handling`

### 5.3 — Delete `scraper/tvdb_client.py`

```bash
git rm personalscraper/scraper/tvdb_client.py
```

**Commit**: `refactor(api-unify): delete scraper/tvdb_client.py`

### 5.4 — Phase 5 gate

```bash
make check && python3 scripts/check-module-size.py
! rg "tvdb_client" personalscraper/ --files-with-matches
```

**Commit**: `chore(api-unify): phase 5 gate — tvdb migration done`

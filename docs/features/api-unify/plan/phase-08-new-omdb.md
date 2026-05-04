# Phase 8 — New OMDB

## Gate

**Prerequisites**: Phase 7 complete. `docs/reference/omdb-api.md` exists. `api/metadata/_base.py` exists.

## Goal

Implement `api/metadata/omdb.py` — notations (IMDB + RottenTomatoes), search, details. Follow `docs/reference/omdb-api.md`.

## Sub-phases

### 8.1 — Create `api/metadata/omdb.py`

Implement `OMDBClient`:

```python
class OMDBClient:
    """OMDB API client — IMDB/RottenTomatoes notations, search, details."""
    REQUIRED_CREDS = ["OMDB_API_KEY"]

    def __init__(self, transport: HttpTransport) -> None:
        self._transport = transport
        # ApiKeyAuth with param="apikey" — the key is already in the session
        # OMDB uses query param, not header

    def search(self, title: str, year: int | None = None,
               media_type: str = "movie") -> list[SearchResult]: ...

    def get_details(self, media_id: str, media_type: str = "movie") -> MediaDetails: ...

    def get_notations(self, media_id: str, media_type: str = "movie") -> Notations | None: ...
        # Returns IMDB + RottenTomatoes scores from the Ratings[] array

    def get_recommendations(self, media_id: str, media_type: str = "movie") -> list[Recommendation]: ...
        # OMDB doesn't natively support recommendations — return []
```

- ≤ 150 LOC. OMDB API is minimal (single endpoint, simple params).
- `REQUIRED_CREDS = ["OMDB_API_KEY"]`
- ApiKeyAuth with param "apikey" as query parameter

### 8.2 — Tests

Write unit/integration tests for OMDBClient:

- `test_omdb_search_movie` — mock response, verify typed SearchResult list
- `test_omdb_get_details` — mock response, verify MediaDetails fields
- `test_omdb_get_notations` — mock response with IMDB + RT ratings
- `test_omdb_no_api_key` — verify behavior when creds missing

**Commit**: `test(api-unify): add OMDB client tests`

### 8.3 — Phase 8 gate

```bash
make check && python3 scripts/check-module-size.py
python -c "from personalscraper.api.metadata.omdb import OMDBClient"
```

**Commit**: `chore(api-unify): phase 8 gate — omdb done`

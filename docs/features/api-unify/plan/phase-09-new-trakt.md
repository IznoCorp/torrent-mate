# Phase 9 — New Trakt

## Gate

**Prerequisites**: Phase 8 complete. `docs/reference/trakt-api.md` exists. `api/metadata/_base.py` exists.

## Goal

Implement `api/metadata/trakt.py` — notations, recommendations, trending, watchlist.

## Sub-phases

### 9.1 — Create `api/metadata/trakt.py`

Implement `TraktClient`:

```python
class TraktClient:
    """Trakt API client — notations, recommendations, trending."""
    REQUIRED_CREDS = ["TRAKT_CLIENT_ID", "TRAKT_CLIENT_SECRET"]

    def __init__(self, transport: HttpTransport) -> None:
        self._transport = transport

    def search(self, title: str, year: int | None = None,
               media_type: str = "movie") -> list[SearchResult]: ...

    def get_details(self, media_id: str, media_type: str = "movie") -> MediaDetails: ...

    def get_notations(self, media_id: str, media_type: str = "movie") -> Notations | None: ...
        # Trakt rating + vote count

    def get_recommendations(self, media_id: str, media_type: str = "movie") -> list[Recommendation]: ...
        # /recommendations/movies or /recommendations/shows

    def get_trending(self, media_type: str = "movie", limit: int = 20) -> list[SearchResult]: ...
        # /movies/trending or /shows/trending

    def get_watchlist(self, username: str) -> list[SearchResult]: ...
        # User-specific — requires OAuth token
```

- Auth: `trakt-api-key` header (client_id) + optional Bearer token for user endpoints
- `REQUIRED_CREDS = ["TRAKT_CLIENT_ID", "TRAKT_CLIENT_SECRET"]`

### 9.2 — Tests

Write tests for TraktClient:

- `test_trakt_get_notations` — mock response
- `test_trakt_get_recommendations` — mock response
- `test_trakt_get_trending_movies` — mock response
- `test_trakt_get_trending_shows` — mock response

**Commit**: `test(api-unify): add Trakt client tests`

### 9.3 — Phase 9 gate

```bash
make check && python3 scripts/check-module-size.py
python -c "from personalscraper.api.metadata.trakt import TraktClient"
```

**Commit**: `chore(api-unify): phase 9 gate — trakt done`

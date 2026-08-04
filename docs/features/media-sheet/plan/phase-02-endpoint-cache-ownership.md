# Phase 2 - Endpoint + cache + croisement mediatheque

**Codename**: `media-sheet` . **Gate**: Phase 1 complete - `MediaDetails` carries 4 new fields, TMDB/TVDB parsers extract them, golden tests pass.

## Gate

> Phase 1 [x] - `MediaDetails` has `director`, `series_status`, `episode_count`, `trailer_url` (all `None` by default). TMDB parser extracts all 4; TVDB parser extracts `series_status`. Golden tests green.

## ANCHOR CORRECTION

- **DESIGN says** `indexer/ownership.py` already used by acquisition, `guarded_api` in `app.py`.
- **Reality**: confirmed. `IndexerOwnershipChecker` at `personalscraper/indexer/ownership.py:311` with `owns()` (:357) and `owned_pairs()` (:405). Already imported at `acquisition.py:200` - same pattern. `guarded_api` at `app.py:220` - mounts routers with pattern `from personalscraper.web.routes.X import router as X_router; guarded_api.include_router(X_router)`. Web models live in `personalscraper/web/models/` - new `media.py` there. All route files use `APIRouter(prefix="/api/...", tags=["..."])`. `MediaRef` at `personalscraper/core/identity.py:21`.
- **DESIGN doesn't mention** where the config/indexer-db path comes from at runtime. The route must read it from `request.app.state.config` (the boot-cached `Config` object attached during `lifespan`). Follow the pattern in `acquisition.py:414` which constructs `Path(indexer_db)` from `library.path` config.

## Sub-phases

### 2.1 Web models: `MediaSheetResponse`

**Files**:
- `personalscraper/web/models/media.py` (create)

**Implementation**:
- Pydantic models for the media sheet endpoint:
```python
class SeasonOwnership(BaseModel):
    season_number: int
    episode_count: int
    owned_count: int
    aired_count: int

class OwnershipBlock(BaseModel):
    owned: bool
    seasons: list[SeasonOwnership] = []

class MediaSheetResponse(BaseModel):
    provider: str
    provider_id: str
    title: str
    year: int | None
    poster_url: str
    overview: str
    director: str | None
    genres: list[str]
    trailer_url: str | None
    series_status: str | None
    seasons: list[dict]  # SeasonInfo shape from _base.py
    ownership: OwnershipBlock | None
    degraded_reason: str | None
```
- Follow conventions from `models/staging.py`: `from __future__ import annotations`, Pydantic `BaseModel`.
- `ownership` is `None` when the library database is unavailable (fail-soft).

**Tests**:
- `tests/web/test_media_sheet_models.py` - verify model instantiation, serialization roundtrip, `degraded_reason` present when set.

**Gate**:
```bash
python -m pytest tests/web/test_media_sheet_models.py -v
```

### 2.2 Endpoint `GET /api/media/{provider}/{provider_id}` with cache

**Files**:
- `personalscraper/web/routes/media.py` (create)
- `personalscraper/web/app.py` (modify - mount the router at line ~252, after staging_router)

**Implementation**:
- New router at `personalscraper/web/routes/media.py`:
```python
router = APIRouter(prefix="/api/media", tags=["media"])
```
- Single endpoint:
```python
@router.get("/{provider}/{provider_id}", response_model=MediaSheetResponse)
async def get_media_sheet(
    provider: str,
    provider_id: str,
    request: Request,
) -> MediaSheetResponse:
```
- Logic (6-step, implementing D1-D9):
  1. Validate `provider` in `("tmdb", "tvdb")` -> else 404.
  2. Check in-memory cache (simple dict at module level, `(provider, id) -> (response, expiry)` with 300s TTL) -> return if hit.
  3. Instantiate the right provider client. Follow the pattern from the scraper pipeline or `_factory` module. If no factory exists, import `TMDBClient`/`TVDBClient` from `personalscraper.api.metadata.tmdb`/`.tvdb`.
  4. Call provider `.get_movie()` or `.get_tv()` -> get `MediaDetails`. Catch exceptions -> set `degraded_reason` in French, serve partial response built from whatever we have.
  5. Cross library ownership: read `indexer_db_path` from `request.app.state.config`, open `IndexerOwnershipChecker(db_path)`. For movies: `checker.owns(media_ref, kind="movie")`. For TV: `checker.owned_pairs(media_ref)` -> build per-season `SeasonOwnership`. Close the checker after use.
  6. Build `MediaSheetResponse`, set cache entry, return.
- Read-only -> no `require_not_staging`, no `pipeline.lock`. Auth via `guarded_api` mount (inherits `Depends(require_session)`).
- In-memory cache: module-level `_cache: dict` + `_CACHE_TTL = 300`. Simple, no eviction in v1 (endpoint is low-traffic). Add a comment noting future LRU if needed.
- Mount in `app.py` (after line 252):
```python
from personalscraper.web.routes.media import router as media_router
guarded_api.include_router(media_router)
```

**IMPORTANT**: any route/model/docstring change -> `make openapi` + commit regenerated `frontend/openapi.json` + `frontend/src/api/schema.d.ts`.

**Tests**:
- `tests/web/test_media_sheet_endpoint.py`:
  - 200 with full response (mock provider via `unittest.mock.patch`, mock ownership checker).
  - 200 with degraded response (provider raises `ApiError` -> `degraded_reason` filled, partial data served, never 500).
  - Cache: two successive calls with same params -> provider mock called exactly once.
  - Movie: `series_status` null, `ownership` has `owned: bool`.
  - TV: `series_status` non-null, `ownership.seasons` populated.
  - 401 when session absent (auth guard test via `TestClient`).
  - Provider not in `["tmdb", "tvdb"]` -> 404 with French detail.

**Gate**:
```bash
python -m pytest tests/web/test_media_sheet_endpoint.py -v
make openapi
git diff --stat frontend/openapi.json frontend/src/api/schema.d.ts
```

### 2.3 Gate - Phase 2 complete

```bash
make lint
python -m pytest tests/web/test_media_sheet_endpoint.py tests/web/test_media_sheet_models.py -v
make openapi  # verify no uncommitted drift
python -c "import personalscraper"
```

**Commit**: `feat(media-sheet): GET /api/media/{provider}/{id} with cache + ownership crossing (D1,D2,D5,D6,D9)`

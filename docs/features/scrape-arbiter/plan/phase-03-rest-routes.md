# Phase 3 — REST Routes + Models + OpenAPI Regen

## Gate

- [ ] Phase 2 complete — `scrape-resolve` CLI functional, web runner executable
- [ ] `DecisionWriter.resolve()` and `DecisionWriter.dismiss()` tested
- [ ] Web runner spawns and finalizes `pipeline_run` rows correctly
- [ ] `make lint` + `make test` green

---

### Sub-phase 3.1 — Pydantic models for decisions API

**Creates:** `personalscraper/web/models/decisions.py`
**Modifies:** `personalscraper/web/models/__init__.py` (re-export new models)
**Test:** `tests/unit/web/test_decision_models.py`

**DESIGN ref:** §6 route contracts — `DecisionsResponse`, `DecisionDetail`,
`DecisionCandidate`

Models:

- `DecisionCandidate(BaseModel)`: `provider: Literal['tmdb', 'tvdb']`, `provider_id: int`,
  `title: str`, `year: int | None`, `score: float`, `poster_url: str | None`,
  `overview: str | None`.
- `DecisionListItem(BaseModel)`: `id: int`, `staging_path: str`, `media_kind: str`,
  `extracted_title: str`, `extracted_year: int | None`, `trigger: str`,
  `candidates_count: int`, `status: str`, `created_at: float`.
- `DecisionsResponse(BaseModel)`: `items: list[DecisionListItem]`,
  `pending_count: int`, `total: int`, `page: int`, `page_size: int`.
- `DecisionDetail(BaseModel)`: all `DecisionListItem` fields + `candidates:
list[DecisionCandidate]` + `resolution_json: dict | None`.
- `SearchRequest(BaseModel)`: `title: str`, `year: int | None = None`.
- `SearchResponse(BaseModel)`: `candidates: list[DecisionCandidate]`.
- `ResolveRequest(BaseModel)`: `provider: Literal['tmdb', 'tvdb']`, `provider_id: int`.
- `ResolveResponse(BaseModel)`: `run_uid: str`.

**Commit:** `feat(scrape-arbiter): add Pydantic models for decisions API`

---

### Sub-phase 3.2 — Decision routes implementation

**Creates:** `personalscraper/web/routes/decisions.py`
**Test:** `tests/unit/web/routes/test_decisions.py`

**DESIGN ref:** §6 full route table — 5 endpoints, typed models, `guarded_api` perimeter,
XRW on mutations, `require_not_staging` on writes

Route file: `router = APIRouter(prefix="/api/decisions", tags=["decisions"])`.

1. `GET /` → `DecisionsResponse`: paginated (`page`, `page_size` query params), `status`
   filter (default `pending`). Queries `scrape_decision` table, NFC-normalizes. Runs
   `DecisionWriter.mark_superseded_orphans()` before query. Includes `pending_count` (COUNT
   WHERE status='pending').

2. `GET /{id}` → `DecisionDetail`: fetches single row by `id`. 404 if not found, 410 if
   `status = 'superseded'`. Deserializes `candidates_json` into `list[DecisionCandidate]`.

3. `POST /{id}/search` → `SearchResponse`: body `SearchRequest`. Read-only — no state
   change. Calls live TMDB/TVDB search via existing provider clients (injected from
   `AppContext` on `request.app.state`). Returns fresh `DecisionCandidate[]`. Session
   identity required (inherited from `guarded_api`), XRW gated.

4. `POST /{id}/resolve` → `ResolveResponse` (202): body `ResolveRequest`. 404/410 on
   decision id. **409** if pipeline lock held (`is_lock_held`) or a resolve already
   running (check `pipeline_run` rows). **403** if staging (`require_not_staging`).
   Reserves `pipeline_run` row via `_reserve_decision_run()`, spawns runner subprocess
   (same env contract as `_spawn_runner`), returns `202 {run_uid}`. XRW gated.

5. `POST /{id}/dismiss` → `200`: marks decision `dismissed` via
   `DecisionWriter.dismiss()`. 403 staging. No body. XRW gated.

**Commit:** `feat(scrape-arbiter): implement /api/decisions routes`

---

### Sub-phase 3.3 — Mount in app.py + OpenAPI regen

**Modifies:** `personalscraper/web/app.py` (add decisions router to `guarded_api`),
`frontend/openapi.json`, `frontend/src/api/schema.d.ts`
**Test:** `tests/unit/web/test_app.py` (assert decisions routes registered)

**DESIGN ref:** §6 — `guarded_api` perimeter, `make openapi` → schema.d.ts; CI diff-guard

In `app.py:118-130`: add `from personalscraper.web.routes.decisions import router as
decisions_router` and `guarded_api.include_router(decisions_router)`. Run `make openapi` to
regenerate `frontend/openapi.json` and `frontend/src/api/schema.d.ts`. Run frontend CI
lint+typecheck+vitest to confirm no drift. Commit all three files together (OpenAPI +
schema.d.ts + app.py change).

**Commit:** `feat(scrape-arbiter): mount decisions router and regenerate OpenAPI`

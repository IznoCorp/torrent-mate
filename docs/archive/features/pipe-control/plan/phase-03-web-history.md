# Phase 3 — Web history: history + detail routes

## Gate

Phase 2 must have produced:

- `personalscraper/web/routes/pipeline.py` with the 6 control routes passing auth + XRW guard tests
- `StatusResponse` model returning correct `state`/`run_uid`/`step`/`paused`/`watcher_enabled`/`pid`
- Pipeline routes mounted in `guarded_api`, `make test` passes
- Control routes integration-tested (run 202/409, pause/resume/kill state changes, status shape)

## Scope

Two read-only GET routes for run history, backed by the `pipeline_run` table (migration 011).
No new mutations — history is written by the pipeline engine (Phase 1.3).

## Sub-phases

### 3.1 — History routes + models

**Files:**

- Modify: `personalscraper/web/models/pipeline.py` (add history Pydantic models)
- Modify: `personalscraper/web/routes/pipeline.py` (add `GET /history` + `GET /history/{run_uid}`)

**Commit:** `feat(pipe-control): add pipeline history routes + models`

- Add models to `web/models/pipeline.py`:
  - `RunSummary(BaseModel)`: `run_uid: str`, `trigger: str`, `dry_run: bool`, `started_at: str` (ISO 8601), `ended_at: str | None`, `outcome: PipelineOutcome | None`, `duration_s: float | None`
  - `StepTiming(BaseModel)`: `name: str`, `status: str`, `started_at: str | None`, `ended_at: str | None`, `elapsed_s: float | None`
  - `RunDetail(BaseModel)`: all `RunSummary` fields + `steps: list[StepTiming]`, `error: str | None`
  - `HistoryResponse(BaseModel)`: `runs: list[RunSummary]`, `total: int`

- Add routes to `web/routes/pipeline.py`:
  - `GET /api/pipeline/history`:
    - Query params: `limit: int = 50`, `offset: int = 0`, `sort: str = "-started_at"` (supports `started_at`, `-started_at`, `duration`, `-duration`).
    - Opens library.db (read-only), does not need the indexer lock.
    - `SELECT COUNT(*) FROM pipeline_run` for `total`.
    - `SELECT ... FROM pipeline_run ORDER BY ... LIMIT ? OFFSET ?` for `runs`.
    - Compute `duration_s` in Python: `ended_at - started_at` if both set.
  - `GET /api/pipeline/history/{run_uid}`:
    - `SELECT ... FROM pipeline_run WHERE run_uid = ?` → 404 if not found.
    - Parse `steps_json` (JSON array of step objects) into `list[StepTiming]`.
    - Return `RunDetail`.
  - Both routes are read-only, guarded by `require_session` only (no XRW needed).

- Design decision: routes open a **fresh read-only connection** to library.db on each request (no connection pooling).
  Matches the pre-1.0 simplicity rule; the indexer DB uses WAL mode so concurrent reads are safe.

- Test: route tests with a pre-populated test DB (in-memory or tmp file with migration 011 applied). Verify:
  - Pagination (limit/offset), sort order works.
  - Empty DB returns `{runs: [], total: 0}`.
  - `/{run_uid}` returns 404 for unknown uid.
  - `/{run_uid}` returns correct RunDetail with parsed steps_json.
  - Auth guard (401 without cookie).

## Files touched this phase

| Operation | File                                     |
| --------- | ---------------------------------------- |
| Modify    | `personalscraper/web/models/pipeline.py` |
| Modify    | `personalscraper/web/routes/pipeline.py` |

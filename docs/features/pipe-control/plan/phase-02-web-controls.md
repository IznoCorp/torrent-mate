# Phase 2 — Web controls: run/pause/resume/kill/watcher/status

## Gate

Phase 1 must have produced:

- `personalscraper/pause.py` — `PauseController` class with `checkpoint()` and `is_paused()`
- `personalscraper/pipeline_history.py` — `PipelineRunWriter` with `insert`/`update_step`/`finalize`
- `Pipeline.run()` accepts `trigger_reason: str` kwarg
- `PipelinePaused` / `PipelineResumed` events registered and flowing through the bus
- Migration 011 applied, `pipeline_run` table exists, `PipelineRunRow` in schema.py
- `make test` passes, at least the migration contract test + pause + history unit tests

## Scope

Six REST routes under `/api/pipeline/*`, guarded by `require_session` and (for mutating POSTs)
`X-Requested-With: TorrentMate`. Also: Pydantic request/response models, wiring into the guarded
API router, and producer wiring (new events → Redis → WS).

## Sub-phases

### 2.1 — Pydantic models for pipeline API

**Files:**

- Create: `personalscraper/web/models/__init__.py`
- Create: `personalscraper/web/models/pipeline.py`

**Commit:** `feat(pipe-control): add Pydantic models for pipeline API routes`

Models (all inherit `pydantic.BaseModel`):

- `PipelineState(str, Enum)`: `idle | running | paused`
- `PipelineOutcome(str, Enum)`: `success | error | killed | running | paused`
- `RunRequest(BaseModel)`: `dry_run: bool = False`
- `WatcherRequest(BaseModel)`: `enabled: bool`
- `RunResponse(BaseModel)`: `run_uid: str`
- `StatusResponse(BaseModel)`: `state: PipelineState`, `run_uid: str | None`, `step: str | None`, `paused: bool`, `watcher_enabled: bool`, `pid: int | None`
- `WatcherResponse(BaseModel)`: `watcher_enabled: bool`

### 2.2 — Pipeline control routes + guard

**Files:**

- Create: `personalscraper/web/routes/pipeline.py`
- Modify: `personalscraper/web/deps.py` (add `require_x_requested_with` dependency)

**Commit:** `feat(pipe-control): add pipeline control routes with X-Requested-With guard`

- Add `require_x_requested_with(request: Request) -> None` dependency in `deps.py`:
  - Checks `request.headers.get("X-Requested-With") == "TorrentMate"`; raises `HTTPException(400)` if not.
- Create `personalscraper/web/routes/pipeline.py` with `router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])`.
- Implement the 6 routes (DESIGN §4):

| Route      | Method | Guard         | Implementation                                                                                                                                                                                                                                            |
| ---------- | ------ | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/run`     | POST   | session + XRW | Read lock via `is_lock_held()` → `409` if held. Assemble `[sys.executable, "-m", "personalscraper", "run", "--no-console", f"--trigger-reason=web"]` + `--dry-run` if requested. `subprocess.Popen(..., start_new_session=True)`. Return `202 {run_uid}`. |
| `/pause`   | POST   | session + XRW | `touch data_dir / "pipeline.pause"`. Return `{state}`. No-op if idle.                                                                                                                                                                                     |
| `/resume`  | POST   | session + XRW | `unlink data_dir / "pipeline.pause" (missing_ok=True)`. Return `{state}`.                                                                                                                                                                                 |
| `/kill`    | POST   | session + XRW | Read pid from lock file. `os.kill(pid, signal.SIGTERM)`. Clear pause sentinel. Return `{state}`.                                                                                                                                                          |
| `/watcher` | POST   | session + XRW | Set/clear `watcher.paused` sentinel at `data_dir / "watcher.paused"`. Return `{watcher_enabled}`.                                                                                                                                                         |
| `/status`  | GET    | session only  | Read lock (`is_lock_held`), pause sentinel (`PauseController.is_paused`), watcher sentinel, latest `pipeline_run` row. Compose `StatusResponse`.                                                                                                          |

- Status resolution logic:
  - Lock not held → `state = "idle"`, no `run_uid`/`step`/`pid`
  - Lock held + pause sentinel present → `state = "paused"`
  - Lock held + no pause sentinel → `state = "running"`
  - Query latest `pipeline_run` row by `started_at DESC LIMIT 1` for `run_uid`, parse `steps_json` for current step name.

### 2.3 — Wire routes into app + producer wiring

**Files:**

- Modify: `personalscraper/web/app.py` (include pipeline router in guarded_api)
- Modify: `personalscraper/web/routes/pipeline.py` (add producer wiring)

**Commit:** `feat(pipe-control): wire pipeline routes into FastAPI app`

- In `create_app()`: add to the guarded_api block:
  ```python
  from personalscraper.web.routes.pipeline import router as pipeline_router
  guarded_api.include_router(pipeline_router)
  ```
- Producer wiring: the new events (`PipelinePaused`, `PipelineResumed`) already flow through the
  existing EventBus → `RedisEventPublisher` → Redis Stream → `read_stream_loop` → WS broadcast.
  No new wiring needed — the pipeline-side subscriber registration in `commands/pipeline.py`
  already covers all `Event` subclasses via the catch-all. Verify this with a test that the
  events appear in the WS feed.
- Test route auth (401 without cookie), XRW guard (400 without header), and status shape.
- Update `tests/web/conftest.py` if needed for the new router.

## Files touched this phase

| Operation | File                                     |
| --------- | ---------------------------------------- |
| Create    | `personalscraper/web/models/__init__.py` |
| Create    | `personalscraper/web/models/pipeline.py` |
| Create    | `personalscraper/web/routes/pipeline.py` |
| Modify    | `personalscraper/web/deps.py`            |
| Modify    | `personalscraper/web/app.py`             |

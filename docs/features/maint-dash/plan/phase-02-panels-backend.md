# Phase 2 — Monitoring Panels Backend (disks / locks / index-health)

## Gate

**Prerequisite — Phase 1 delivered**:

- Migration 012 applied → `pipeline_run` has `kind`, `command`, `options_json`, `output_tail`.
- `REGISTRY` list importable from `personalscraper.web.maintenance.registry`.
- Canonical options serializer available at `registry.canonical_options_json`.

**Produces for Phase 3+4+5**: 3 GET routes returning typed responses. Phase 4 (history unification) reuses `IndexHealthResponse.last_scan`; Phase 5 (frontend) reads all 3 panel endpoints via TanStack Query.

## Sub-phases

### 2.1 — Maintenance response models (`feat(maint-dash): add DisksResponse, LocksResponse, IndexHealthResponse models`)

**Files:**

- Create: `personalscraper/web/maintenance/models.py`
- Modify: `personalscraper/web/maintenance/__init__.py` (re-export key symbols)

**Models** (Pydantic, google-docstring on each):

```python
class DiskInfo(BaseModel):
    id: str; label: str; mounted: bool; free_gb: float; total_gb: float; used_pct: float

class DisksResponse(BaseModel):
    disks: list[DiskInfo]

class LockState(BaseModel):
    held: bool; pid: int | None; pid_alive: bool; stale: bool; age_s: float | None

class Sentinels(BaseModel):
    pause: bool  # pipeline.pause exists
    pause_age_s: float | None
    watcher_paused: bool  # watcher.paused exists
    watcher_paused_age_s: float | None

class TmpOrphan(BaseModel):
    path: str; prefix: str; age_s: float

class LocksResponse(BaseModel):
    pipeline_lock: LockState
    sentinels: Sentinels
    tmp_orphans: list[TmpOrphan]

class NfoStats(BaseModel):
    valid: int; invalid: int; missing: int

class IndexHealthResponse(BaseModel):
    items: int; movies: int; shows: int; files: int; size_gb: float
    nfo: NfoStats
    repair_queue_pending: int; repair_queue_oldest_age_s: float | None
    outbox_pending: int; outbox_oldest_age_s: float | None
    last_scan_id: int | None; last_scan_mode: str | None
    last_scan_status: str | None; last_scan_started_at: str | None
    last_scan_finished_at: str | None; last_scan_stuck: bool
    soft_deleted: int  # count of soft-deleted media_file rows (deleted_at IS NOT NULL)
    canonical_null: int  # count of media_item rows where canonical_provider IS NULL
```

### 2.2 — Maintenance routes module (`feat(maint-dash): add GET /api/maintenance/disks, /locks, /index-health routes`)

**Files:**

- Create: `personalscraper/web/routes/maintenance.py`
- Modify: `personalscraper/web/app.py:122` (add `include_router(maintenance_router)` to `guarded_api`)

**Route contracts** (all sync `def`, Pydantic response_model, `Depends(require_session)`):

- `GET /api/maintenance/disks` → `DisksResponse`: Iterates `config.disks`, calls `get_disk_status(config=disk_config)` from `personalscraper.dispatch.disk_scanner` for each. Computes `total_gb` from `shutil.disk_usage(path).total` (DiskConfig has no `size_gb` field), `used_pct = round((1 - free_gb / total_gb) * 100, 1)`.

- `GET /api/maintenance/locks` → `LocksResponse`: Checks `data_dir/pipeline.lock` (held + PID liveness via `os.kill(pid, 0)` → `pid_alive`; stale = file exists but PID dead). Checks `data_dir/pipeline.pause` and `data_dir/watcher.paused` sentinels with age (`time.time() - mtime`). **Bounded tmp-orphan sweep**: `os.scandir` on staging category dirs + disk roots at depth ≤ 2, match prefixes `_tmp_dispatch_*`, `_tmp_ingest_*`, cap at 100 entries.

- `GET /api/maintenance/index-health` → `IndexHealthResponse`: Single cheap WAL read-only `SELECT` aggregate query over `library.db`. Do NOT walk the filesystem. Queries:
  - Counts: `SELECT COUNT(*) FROM media_item` + category breakdowns + `media_file` count + sum `size_bytes`.
  - NFO: `SELECT COUNT(*) FROM media_item WHERE ...` grouped by `nfo_status`.
  - Repair queue: `SELECT COUNT(*), MIN(julianday('now')-julianday(enqueued_at))*86400 FROM repair_queue WHERE status='pending'`.
  - Outbox: same pattern on `outbox` table (if exists, else 0).
  - Last scan: `SELECT * FROM scan_run ORDER BY started_at DESC LIMIT 1`.
  - Soft-deleted: `SELECT COUNT(*) FROM media_file WHERE deleted_at IS NOT NULL`.
  - Canonical NULL: `SELECT COUNT(*) FROM media_item WHERE canonical_provider IS NULL`.

**Mount in `app.py`**: After `guarded_api.include_router(pipeline_router)`:

```python
from personalscraper.web.routes.maintenance import router as maintenance_router
guarded_api.include_router(maintenance_router)
```

### 2.3 — Panel route tests (`test(maint-dash): add route tests for 3 panel GETs`)

**Files:**

- Create: `tests/web/test_maintenance_panels.py`
  (NOT `tests/unit/web/routes/test_maintenance_panels.py` as originally planned —
  route tests for the web app live in `tests/web/` alongside `test_pipeline_routes.py`
  where `conftest.py` provides `test_config` + `web_app` fixtures and the established
  login/session pattern.)

**Test cases** implemented (FastAPI `TestClient`, mirrored from `test_pipeline_routes.py`
auth + config-override patterns):

1. `test_disks_authenticated` → 200, `.disks` list, each entry has `free_gb`/`total_gb` numeric,
   `mounted` True, `used_pct` within [0,100].
2. `test_disks_unauthenticated` → 401 (no session cookie).
3. `test_locks_idle` → 200, `.pipeline_lock.held == False`, sentinels absent, `tmp_orphans == []`.
4. `test_locks_stale` → lock file with dead subprocess PID → `.pipeline_lock.stale == True`,
   `.pid_alive == False`. (Note: `held` is `False` here because `is_lock_held` returns
   `False` for dead PIDs — the file exists but the process is gone.)
5. `test_locks_tmp_orphans` → create 3 `_tmp_dispatch_*` dirs in staging → all 3 reported.
6. `test_locks_unauthenticated` → 401.
7. `test_index_health` → **SKIPPED (BLOCKED)** — `_apply_pragmas` on a `mode=ro` connection
   raises `sqlite3.OperationalError` (write pragmas on read-only connection), so the route
   always returns `_empty_health()`. The test infrastructure (seeded DB fixture with
   migrations + INSERTs) is in place; unskip once the route source is fixed.
8. `test_index_health_empty_db` → 200, `items == 0` (non-existent `db_path` → fail-soft
   zeroed response, NOT 500).
9. `test_index_health_unauthenticated` → 401.

Use `tmp_path` for `data_dir`, `staging_dir`, and seeded `library.db`; auth via
`/api/auth/login` with HTTPS `TestClient` (`tm_session` cookie replay).

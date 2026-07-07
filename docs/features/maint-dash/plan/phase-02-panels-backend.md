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

- Create: `tests/unit/web/routes/test_maintenance_panels.py`

**Test cases** (FastAPI `TestClient`, all wrapped in `patch('personalscraper.conf.loader.load_config', return_value=test_config)` per project rule):

1. `test_disks_authenticated` → 200, `.disks` list, each has `free_gb` numeric.
2. `test_disks_unauthenticated` → 401.
3. `test_locks_idle` → 200, `.pipeline_lock.held == False` (no lock file in test `data_dir`).
4. `test_locks_stale` → lock file with dead PID → `.pipeline_lock.stale == True`.
5. `test_index_health` → 200, `.items > 0` (seed test DB with known rows).
6. `test_index_health_empty_db` → 200, `.items == 0`.

Use `tmp_path` for `data_dir` and a seeded in-memory `library.db` with pre-applied migrations.

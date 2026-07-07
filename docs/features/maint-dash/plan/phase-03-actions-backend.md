# Phase 3 — Actions Backend (listing, POST run, runner, live relay)

## Gate

**Prerequisite — Phase 1 & 2 delivered**:

- `REGISTRY` importable from `personalscraper.web.maintenance.registry`.
- `canonical_options_json` function available.
- `maintenance_router` mounted in `guarded_api` in `app.py` (Phase 2.2).
- Panel route tests pass.

**Produces for Phase 4+5+6**: all action endpoints; runner writes `pipeline_run` rows (`kind='maintenance'`) that Phase 4 unifies; frontend ActionCatalog + ActionForm consume `GET /actions` + `POST .../run`.

## Sub-phases

### 3.1 — GET /api/maintenance/actions (`feat(maint-dash): add GET /api/maintenance/actions endpoint`)

**Files:**

- Modify: `personalscraper/web/routes/maintenance.py` (add route)
- Create: `tests/unit/web/routes/test_maintenance_actions_list.py`

**Route**: `GET /api/maintenance/actions` → `ActionsResponse(actions=REGISTRY)`. Adds `category_counts: dict[str, int]` to `ActionsResponse` for UI grouping chips.

**Test** (`test_maintenance_actions_list.py`):

1. `test_actions_count_matches_registry` → `len(response.actions) == len(REGISTRY)`.
2. `test_actions_all_ids_unique` → set of `action.id` has no duplicates.
3. `test_actions_unauthenticated` → 401.

### 3.2 — POST /api/maintenance/actions/{action_id}/run (`feat(maint-dash): add POST run handler with validation and 409/428 rules`)

**Files:**

- Modify: `personalscraper/web/routes/maintenance.py` (add POST route + helpers)
- Create: `tests/unit/web/routes/test_maintenance_actions_run.py`

**Request body model**:

```python
class ActionRunRequest(BaseModel):
    options: dict[str, object] = {}
    dry_run: bool = True  # default safe
```

**Route logic** (POST, `Depends(require_x_requested_with)`):

1. Lookup `action_id` in `REGISTRY` → 404 if unknown.
2. Validate `options` against `action.options` (unknown key → 422, missing required → 422, bad enum → 422, type mismatch → 422). Build canonical `options_json` via `canonical_options_json`.
3. **Lock check** (write + destructive actions only): if `is_lock_held(data_dir / "pipeline.lock")` → 409. RO actions skip.
4. **Single concurrent maintenance run check** (write/destructive): query `SELECT run_uid, pid FROM pipeline_run WHERE kind='maintenance' AND outcome='running'`. For each row, check liveness via `os.kill(pid, 0)` (the same idiom as :func:`is_lock_held`). A row is **alive** iff `pid IS NOT NULL` AND `os.kill(pid, 0)` succeeds (`ProcessLookupError` → dead; `PermissionError` → alive, owned by another user). Any alive row → 409 `"A maintenance action is already running"`. Dead-or-NULL-pid rows are stale (crashed runner) → silently ignored (no mutation). This guard is **independent** of the pipeline-lock check — a maintenance action may be genuinely running without holding the pipeline lock (e.g. an RO long-running action, or a write CLI that doesn't take the lock).
5. **428 dry-run-first** (destructive + `dry_run=false` only): query `SELECT 1 FROM pipeline_run WHERE kind='maintenance' AND command=? AND options_json=? AND dry_run=1 AND outcome='success' AND ended_at > ?` (30 min window). No row → 428 with detail saying which precondition failed.
6. Spawn runner (3.3). Return `202 {"run_uid": "..."}`.

**Test** (`test_maintenance_actions_run.py`):

1. Unknown action → 404.
2. Invalid option → 422 with detail.
3. Write action while lock held → 409.
4. Destructive apply without prior dry-run → 428.
5. Fresh dry-run exists → apply → 202.
6. Stale dry-run (>30 min) → apply → 428.
7. RO action with lock held → 202 (bypasses lock check).
8. Unauthenticated → 401; missing X-Requested-With → 403.

### 3.3 — Maintenance runner (`feat(maint-dash): add maintenance runner subprocess wrapper`)

**Files:**

- Create: `personalscraper/web/maintenance/runner.py`
- Create: `tests/unit/web/maintenance/test_runner.py`

**`runner.py`** — executable as `python -m personalscraper.web.maintenance.runner`. Reads env:

- `PERSONALSCRAPER_RUN_UID`: run_uid assigned by POST handler.
- `PERSONALSCRAPER_MAINT_COMMAND`: e.g. `library-clean`.
- `PERSONALSCRAPER_MAINT_OPTIONS_JSON`: canonical options.
- `PERSONALSCRAPER_MAINT_DRY_RUN`: `"1"` or `"0"`.

**NOTE (plan corrected 2026-07-07):** `PERSONALSCRAPER_MAINT_KIND` was removed —
the spawner does NOT pass it. `kind="maintenance"` is hardcoded in the runner.
The four vars above are the canonical env contract (match :func:`_spawn_runner`).

Lifecycle:

1. Insert `pipeline_run` row: `kind='maintenance'` (hardcoded), `command=<cmd>`,
   `options_json=<opts>`, `dry_run=<bool>`, `outcome='running'`,
   `pid=os.getpid()`, `started_at=time.time()`, `trigger='web'`,
   `run_uid=<env>`. The `PipelineRunWriter` was extended additively in the same
   sub-phase (`kind`, `command`, `options_json` defaulted so S2 callers unchanged).
2. Build CLI args from validated options: `[sys.executable, "-m", "personalscraper",
<command-id>]` + per-option mapping (required → positional, bool True →
   `--<name>`, str/int/enum → `--<name> value`). Dry-run mapping per command-id
   (module-level table in runner.py): 8 "flag"-style (`--dry-run` appended when
   `DRY_RUN=1`), 8 "apply"-style (`--apply` appended only when `DRY_RUN=0`
   because the default is already dry-run). **Out-of-scope finding:** this table
   belongs in the registry alongside `dry_run` / `options` but registry changes
   are deferred.
3. `subprocess.Popen(cmd, stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)` —
   line-buffered.
4. For each stdout line: (a) append to in-memory ring buffer (last 64 KiB =
   `output_tail`), (b) publish to Redis stream (key from `config.web.stream_key`)
   with envelope `{"_type": "maintenance.run_log", "data": {"run_uid", "line",
"seq"}}` — same `{"_type", "data"}` shape as :func:`event_to_envelope` so the
   WS relay forwards it verbatim. No `Event` subclass was added to the core catalog
   (the envelope is crafted as a plain dict). Fail-soft: Redis errors are logged
   once, never abort the command.
5. On subprocess exit: update row → `outcome='success'|'error'` (exit code 0 →
   success), `ended_at=time.time()`, `error=<tail of output on failure>`,
   `output_tail=<ring buffer>`. Exit with subprocess rc.

**Test** (`test_runner.py`): mock `subprocess.Popen`, verify row lifecycle (insert → running outcome → final outcome), verify `output_tail` truncation at 64 KiB, verify Redis publish called per line (or skipped gracefully on Redis failure).

### 3.4 — Runner integration tests (`test(maint-dash): add integration tests for action spawn → completion flow`)

**Files:**

- Modify: `tests/unit/web/routes/test_maintenance_actions_run.py` (extend)
- Create: `tests/unit/web/maintenance/test_runner_lifecycle.py`

**Test cases**: (1) RO action spawns and completes without lock. (2) Write action acquires lock via CLI. (3) `output_tail` captured in completed row. (4) Canonical `options_json` round-trips (store → read → deserialize matches input). (5) Redis publish failure doesn't crash runner.

# Phase 1 — Engine: pause checkpoint + run-history

## Gate

No prior phase. This is the first phase — no dependency gates.
Verify: `make test` passes (baseline), `personalscraper run --dry-run` works end-to-end.

## Scope

Two cooperative additions to `personalscraper/pipeline.py` and the indexer DB:

1. **Pause checkpoint** — `PauseController` polls a sentinel file at each of the 9 step boundaries. If
   the sentinel exists, the pipeline blocks until it is cleared or SIGTERM arrives.
2. **Run history** — new `pipeline_run` table (indexer migration 011) + a writer that inserts/updates/
   finalizes rows from inside `Pipeline.run()`.

## Sub-phases

### 1.1 — Migration 011: `pipeline_run` table

**Files:**

- Create: `personalscraper/indexer/migrations/011_pipeline_run.sql`
- Modify: `personalscraper/indexer/schema.py` (add `PipelineRunRow` dataclass)

**Commit:** `feat(pipe-control): add pipeline_run indexer migration`

- Create the SQL migration file following the canonical pattern (see `010_media_item_dedup_year.sql`):
  - `CREATE TABLE pipeline_run (id INTEGER PRIMARY KEY AUTOINCREMENT, run_uid TEXT UNIQUE NOT NULL, trigger TEXT NOT NULL, dry_run INTEGER NOT NULL DEFAULT 0, started_at REAL NOT NULL, ended_at REAL, outcome TEXT, steps_json TEXT, error TEXT, pid INTEGER)`
  - `CREATE INDEX idx_pipeline_run_started ON pipeline_run(started_at)`
  - `INSERT INTO schema_version(version) VALUES (11); PRAGMA user_version = 11;`
- Add `PipelineRunRow` frozen dataclass to `schema.py` following existing patterns (`ScanRunRow`, `SchemaVersionRow`).
- Test: `tests/indexer/test_migrations.py` — add version 11 to the contract assertions.

### 1.2 — PauseController + checkpoint()

**Files:**

- Create: `personalscraper/pause.py` (new module)
- Modify: `personalscraper/pipeline.py` (integrate checkpoint into `_run_step`)
- Modify: `personalscraper/pipeline_events.py` (add `PipelinePaused`, `PipelineResumed` events)
- Modify: `personalscraper/events/__init__.py` (eager-import new events)

**Commit:** `feat(pipe-control): add PauseController with step-boundary checkpoint`

- `PauseController(pause_file: Path, poll_interval: float = 0.5)`:
  - `checkpoint() -> None`: if `pause_file` exists → emit `PipelinePaused`, then `while pause_file.exists()` poll `poll_interval` then `time.sleep(0.5)`; if not yet cleared, emit `PipelineResumed` and return. If `_shutdown_requested` → raise `_PipelineInterrupted`.
  - The pause file path is `config.paths.data_dir / "pipeline.pause"`.
  - `is_paused(pause_file) -> bool`: read-only probe (for the web status route).
  - No new dependency: pure `pathlib` + `time` + existing `os.kill` for signal awareness.
- `PipelinePaused` / `PipelineResumed` event dataclasses in `pipeline_events.py` (frozen, `kw_only=True`, no extra fields needed).
- Integrate in `Pipeline.run()`: construct `PauseController` once, pass to `_run_step()`.
- In `Pipeline._run_step()`: call `self._pause.checkpoint()` at the existing `_check_shutdown_requested` site (line 615), BEFORE `StepStarted` emit. This ensures the step boundary is the pause point.
- Test: unit tests for `PauseController` (sentinel present → polls, cleared → proceeds, SIGTERM → exits). Mock `event_bus` to verify events fire.

### 1.3 — Run-history writer + wire into Pipeline.run()

**Files:**

- Create: `personalscraper/pipeline_history.py` (new module)
- Modify: `personalscraper/pipeline.py` (insert at start, update per step, finalize at end)
- Modify: `personalscraper/commands/pipeline.py` (open indexer DB + pass conn to Pipeline)

**Commit:** `feat(pipe-control): add run-history writer + pipeline_run lifecycle`

- `PipelineRunWriter(db_path: Path, event_bus: EventBus)`:
  - `insert(run_uid, trigger, dry_run, pid) -> None`: INSERT into pipeline_run.
  - `update_step(run_uid, step_name, started_at, ended_at, status) -> None`: UPDATE steps_json (append step entry).
  - `finalize(run_uid, outcome, error=None) -> None`: SET ended_at + outcome + error.
  - Fail-soft: all methods catch and log exceptions; never raise. The pipeline must not abort because history writing failed.
- Wire into `Pipeline.run()`:
  - **Start**: after `PipelineStarted` emit, `writer.insert(run_uid, trigger, dry_run, os.getpid())`.
  - **Per step** (in `_run_step`): after `StepCompleted` / `StepErrored`, `writer.update_step(...)`.
  - **End** (in `finally`): `writer.finalize(run_uid, outcome)` where outcome = `"success"` / `"error"` / `"killed"`.
- The `trigger` argument is a new kwarg on `Pipeline.run()`: `trigger_reason: str = "cli"`. The CLI handler passes it through.
- Test: unit tests for `PipelineRunWriter` (insert/update/finalize with tmp DB), integration test that a `--dry-run` creates a row with correct outcome.

## Files touched this phase

| Operation | File                                                      |
| --------- | --------------------------------------------------------- |
| Create    | `personalscraper/indexer/migrations/011_pipeline_run.sql` |
| Modify    | `personalscraper/indexer/schema.py`                       |
| Create    | `personalscraper/pause.py`                                |
| Modify    | `personalscraper/pipeline_events.py`                      |
| Modify    | `personalscraper/events/__init__.py`                      |
| Create    | `personalscraper/pipeline_history.py`                     |
| Modify    | `personalscraper/pipeline.py`                             |
| Modify    | `personalscraper/commands/pipeline.py`                    |
| Modify    | `tests/indexer/test_migrations.py`                        |

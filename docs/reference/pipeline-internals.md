# Pipeline Internals

Circuit breaker, fast-skip behavior, dispatch/verify internals, idempotence.

## Circuit Breaker

- Sits **ABOVE** tenacity: tenacity retries transient errors (429, single timeout), circuit breaker detects sustained outages.
- Trip condition: 5 consecutive 5xx / timeout / connection errors → **OPEN for 5 min**.
- Only counts 5xx / timeout / connection — **NOT** 429 (tenacity handles) or 4xx (client errors).
- `guard()` method centralizes check-then-raise: clients call `self._circuit.guard()` instead of manually checking `can_proceed()` + constructing `CircuitOpenError`.

## Step Contracts

The orchestrator executes `PipelineStep` objects through
`personalscraper.pipeline_protocol.StepContext`. Production steps are registered
in `personalscraper.pipeline_steps.DEFAULT_STEPS`; tests can still pass legacy
callables through `step_overrides`, which are adapted by the compatibility shim.

Each executed step returns a `StepReport`. The legacy `details: list[str]`
field remains for CLI and HTML rendering; `details_payload` is the additive
typed payload. The registry in `personalscraper.reports.STEP_REPORT_CONTRACT`
maps the nine public step names to their `*Details` dataclass.

## Fast-Skip (idempotence)

All 9 pipeline steps are idempotent — re-running produces no changes if everything is already processed.

### Scrape fast-skip

- `_has_unscraped_items()` scans all movie/show dirs before starting
- If all have valid NFOs, the entire scrape step is skipped
- If NFO valid but artwork missing → re-download artwork only (no re-scrape)

### Clean fast-skip

- `_has_polluted_folders()` scans category dirs
- If no polluted names found, skip reclean entirely (dedup always runs — lightweight fuzzy comparison)

## Dispatch

### rsync flags

Uses `-a --no-perms --no-owner --no-group` — NTFS via macFUSE does not support Unix permissions, plain `-a` (which includes `-pgo`) fails with EPERM on all 4 disks.

### Staging→commit pattern

- `_move_new()`: rsync to `_tmp_dispatch_{name}`, then atomic `os.rename`. Crash leaves only tmp dir (cleaned on next run).
- `_merge()`: rsync `--backup --backup-dir=.merge_backup/` for rollback. On failure, `_restore_merge_backup()` restores per-file (continues on individual errors).

### Disk selection

The `Dispatcher` class selects the target disk for new items via `conf.resolver.pick_disk_for()` which considers only mounted disks accepting the category. If no disk has both the category and enough space, the item is skipped (INFO log).

### Standalone invocation

`personalscraper dispatch` auto-runs verify first to get the dispatchable item list — there is no separate staging_dir scan mode.

## Verify

- Movie `nfo_ids` check: both TMDB and IMDB required for a pass. Missing one → WARNING (check fails but non-blocking); missing both → ERROR (blocking).
- TV show `nfo_ids` check: either TVDB or TMDB required for a pass (IMDB not required).

## Event Bus

The pipeline broadcasts lifecycle and per-item activity through an
in-process typed bus
(`personalscraper.core.event_bus.EventBus`). The bus is the **sole**
emit substrate — there is no parallel callback channel and no legacy
per-item observer protocol (deleted in Phase 3 of the event-bus
feature; archived material lives under `docs/archive/`).

For the full reference — wiring, the 13-event v1 catalog, subscriber
recipes, the boundary-only `AppContext` rule, the
`current_correlation_id` ContextVar convention, the JSON
serialization contract, performance notes, and the testing-pattern
catalogue — see [`event-bus.md`](event-bus.md). That document is the
authoritative source; the per-step emit sites described in
`Pipeline._run_step` route through the API it documents.

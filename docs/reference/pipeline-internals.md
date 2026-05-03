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
- If no polluted names found, skip reclean+dedup entirely

## Dispatch

### rsync flags

Uses `-a --no-perms --no-owner --no-group` — NTFS via macFUSE does not support Unix permissions, plain `-a` (which includes `-pgo`) fails with EPERM on all 4 disks.

### Staging→commit pattern

- `_move_new()`: rsync to `_tmp_dispatch_{name}`, then atomic `os.rename`. Crash leaves only tmp dir (cleaned on next run).
- `_merge()`: rsync `--backup --backup-dir=.merge_backup/` for rollback. On failure, `_restore_merge_backup()` restores per-file (continues on individual errors).

### Disk selection

The `Dispatcher` class selects the target disk for new items: falls back to any disk with space if no disk has the category. Logs WARNING for overflow (category not in disk config).

### Standalone invocation

`personalscraper dispatch` auto-runs verify first to get the dispatchable item list — there is no separate staging_dir scan mode.

## Verify

- `nfo_ids` check: both TMDB and IMDB required for a pass
- Missing one → WARNING (check fails)
- Missing both → ERROR
- Missing one → WARNING (check fails but non-blocking); missing both → ERROR (blocking).

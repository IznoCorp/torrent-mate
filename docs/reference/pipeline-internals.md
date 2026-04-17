# Pipeline Internals

Circuit breaker, fast-skip behavior, dispatch/verify internals, idempotence.

## Circuit Breaker (V8)

- Sits **ABOVE** tenacity: tenacity retries transient errors (429, single timeout), circuit breaker detects sustained outages.
- Trip condition: 5 consecutive 5xx / timeout / connection errors → **OPEN for 5 min**.
- Only counts 5xx / timeout / connection — **NOT** 429 (tenacity handles) or 4xx (client errors).
- `guard()` method centralizes check-then-raise: clients call `self._circuit.guard()` instead of manually checking `can_proceed()` + constructing `CircuitOpenError`.

## Fast-Skip (V10 idempotence)

All 8 pipeline steps are idempotent — re-running produces no changes if everything is already processed.

### Scrape fast-skip

- `_all_nfos_valid()` scans all movie/show dirs before starting
- If all have valid NFOs, the entire scrape step is skipped
- If NFO valid but artwork missing → re-download artwork only (no re-scrape)

### Clean fast-skip

- `_has_polluted_folders()` scans category dirs
- If no polluted names found, skip reclean+dedup entirely

## Dispatch (V5 + V8)

### rsync flags

Uses `-a --no-perms --no-owner --no-group` — NTFS via macFUSE does not support Unix permissions, plain `-a` (which includes `-pgo`) fails with EPERM on all 4 disks.

### Staging→commit pattern

- `_move_new()`: rsync to `_tmp_dispatch_{name}`, then atomic `os.rename`. Crash leaves only tmp dir (cleaned on next run).
- `_merge()`: rsync `--backup --backup-dir=.merge_backup/` for rollback. On failure, `_restore_merge_backup()` restores per-file (continues on individual errors).

### Disk selection

`choose_disk(allow_create_category=True)` for new items: falls back to any disk with space if no disk has the category. Logs WARNING for overflow (category not in disk config).

### Standalone invocation

`personalscraper dispatch` auto-runs verify first to get the dispatchable item list — there is no separate staging_dir scan mode.

## Verify (V4 + V9)

- `nfo_ids` check: at least one of TMDB or IMDB required (not both)
- Missing one → WARNING
- Missing both → ERROR
- Some recent films have TMDB but no IMDB yet (acceptable).

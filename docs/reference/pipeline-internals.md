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

The pipeline broadcasts lifecycle and per-item activity through an in-process
typed bus (`personalscraper.core.event_bus.EventBus`). The bus is the **sole**
emit substrate — there is no parallel callback channel and no legacy per-item
observer protocol (deleted in Phase 3 of the event-bus feature; archived
material lives under `docs/archive/`).

### Wiring

- The bus is constructed once in `personalscraper.core.app_context.AppContext`
  and carried on every `StepContext` as `ctx.app.event_bus`. Steps emit through
  this single handle.
- CLI bootstrap (`personalscraper.commands.pipeline._build_app_context`) builds
  the `AppContext`, then attaches subscribers. `Pipeline.run()` has no
  subscriber kwarg — headless runs (no subscriber attached) produce zero stdout.
- Subscribers self-subscribe in `__init__` and tear down in `close()`. The
  registry is copy-on-write, so emit is allocation-free in the steady state and
  safe to call from inside a subscriber callback.
- Dispatch walks the MRO: subscribing to `Event` receives every event;
  subscribing to a concrete class receives that class only.

### Pipeline event catalog

Six frozen dataclasses in `personalscraper.pipeline_events` flow through the
bus on every run:

| Event             | Emitted by                                      | Carries                                             |
| ----------------- | ----------------------------------------------- | --------------------------------------------------- |
| `PipelineStarted` | `Pipeline.run` (once, before step loop)         | `report` (empty `PipelineReport`, `started_at` set) |
| `PipelineEnded`   | `Pipeline.run` (once, in `finally`)             | `report` (fully populated, `finished_at` set)       |
| `StepStarted`     | `Pipeline._run_step` (before invoking the step) | `step` (one of the 9 step names)                    |
| `StepCompleted`   | `Pipeline._run_step` (after success)            | `step`, `report` (`StepReport`), `elapsed_s`        |
| `StepErrored`     | `Pipeline._run_step` (on raised exception)      | `step`, `error_class`, `error_message`              |
| `ItemProgressed`  | Each pipeline step (per-item)                   | `step`, `item`, `status`, JSON-safe `details`       |

All six inherit from `Event` (`event_id`, `timestamp`, `source`,
`correlation_id`); subclasses declare `kw_only=True` explicitly because
dataclass machinery does not inherit it transitively.

### Subscribers (production)

- `personalscraper.subscribers.RichConsoleSubscriber` — renders the Rich UI
  (banners, per-step panels, error tracebacks, item progress). Subscribes to
  the six pipeline events; visual output is locked against
  `tests/snapshots/rich_console_canonical.txt` (byte-identical).
- `personalscraper.subscribers.TelegramSubscriber` — fires `PipelineEnded`
  summary + `StepErrored` alerts. Network I/O runs on a daemon thread so the
  emitting bus thread stays under a 50 ms wall-clock budget even when the
  Telegram endpoint is slow.

### Subscribers (tests)

- `tests.fixtures.event_bus.CollectingSubscriber[E]` — records every event of
  type `E` for assertion in unit/integration tests. Replaces the legacy
  `CollectorObserver` test helper.
- Every emit site is double-log audited (Sub-phase 3.8): a `log.<level>` call
  alongside an `event_bus.emit(...)` is only allowed when it carries
  information distinct from the event payload (e.g., `exc_info=True` next to
  `StepErrored`).

### Correlation id

`Pipeline.run` generates a fresh `run_id` (UUID) per call and binds it to the
`current_correlation_id` `ContextVar` for the lifetime of the run. The base
`Event.correlation_id` reads this var at construction time, so every event in
a single run shares the same id and downstream consumers (log lines, NDJSON
audit, future indexer outbox) can join on it.

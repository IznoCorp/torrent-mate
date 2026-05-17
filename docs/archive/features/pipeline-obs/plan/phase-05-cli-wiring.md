# Phase 5 — CLI Wiring

**Type**: wire
**Codename**: pipeline-obs

## NO DEFERRAL

Every CLI command is updated. Panel/Table inline code removed. All observers
wired. No leftover Console direct usage in pipeline command.

## Gate (pre-phase)

- [x] Phase 4 complete — `StepContext` uses `observers`, `Pipeline.__init__` accepts `observers`

## Sub-phases

### Sub-phase 5.1 — Wire observers in `commands/pipeline.py`

**Files:**

- Modify: `personalscraper/commands/pipeline.py`
- Modify: any test files that mock `commands/pipeline.py`

Changes to the `run` command:

1. Import `RichConsoleObserver` and `TelegramObserver`
2. Build `observers = [RichConsoleObserver(console=console, verbose=verbose)]`
3. If Telegram configured, append `TelegramObserver(settings)`
4. Pass `observers` to `Pipeline(...)`
5. Remove the inline `Panel`/`Table` block after `report = pipeline.run()`
6. Remove the inline `TelegramNotifier.send_report(report)` call
7. Keep the banner before `Pipeline.run()` (mode + run_id) — move to `on_pipeline_start`

The `Pipeline` constructor call changes from:

```python
pipeline = Pipeline(
    config,
    settings,
    dry_run=dry_run,
    interactive=interactive,
    verbose=verbose,
    console=console,
    skip_trailers=effective_skip_trailers,
    continue_on_trailer_error=effective_continue_on_trailer_error,
)
```

To:

```python
observers: list[PipelineObserver] = [
    RichConsoleObserver(console=console, verbose=verbose),
]
if TelegramNotifier.is_configured(settings):
    observers.append(TelegramObserver(settings))
pipeline = Pipeline(
    config,
    settings,
    dry_run=dry_run,
    interactive=interactive,
    verbose=verbose,
    observers=observers,
    skip_trailers=effective_skip_trailers,
    continue_on_trailer_error=effective_continue_on_trailer_error,
)
```

After `report = pipeline.run()`, remove:

- The `dur = report.duration()` → `dur_str` block
- The `Table(...)` → `Panel(...)` block
- The `if TelegramNotifier.is_configured(...)` → `notifier.send_report(report)` block

Keep:

- Healthcheck (ping_start/ping_success/ping_fail) — wraps the whole invocation
- Lock acquire/release
- `TrailerStepFailed` exception handling
- Structlog context binding

### Sub-phase 5.2 — Update import for `PipelineReport` in `pipeline.py`

In `pipeline.py`, add `on_pipeline_start` notification at the beginning of `run()`:

```python
def run(self) -> PipelineReport:
    from datetime import datetime

    ensure_staging_tree(self.config)
    report = PipelineReport(started_at=datetime.now())

    for obs in self._observers:
        obs.on_pipeline_start(report)

    # ... rest ...
```

And in the `finally`-like section at the bottom:

```python
    report.finished_at = datetime.now()
    for obs in self._observers:
        obs.on_pipeline_end(report)
    return report
```

### Sub-phase 5.3 — Adapt existing CLI tests

Update `tests/` references to `Pipeline(... console=...)` to use `observers=[...]`.

## Gate (post-phase)

- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass
- [ ] `rg "console=console" personalscraper/commands/pipeline.py` — zero matches (except single-step commands which keep `console` for their own output)
- [ ] `rg "Panel\(|Table\(" personalscraper/commands/pipeline.py` — zero matches
- [ ] `rg "send_report" personalscraper/commands/pipeline.py` — zero matches
- [ ] Commit: `chore(pipeline-obs): phase 5 gate — CLI wiring`

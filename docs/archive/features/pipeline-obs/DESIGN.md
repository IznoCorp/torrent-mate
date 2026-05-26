# Pipeline Observer Protocol — Design

> **⚠ STATUS** : This DESIGN.md is an archived as-designed snapshot. **The entire
> Observer Protocol architecture is superseded by feat/event-bus** (shipped v0.14.0).
> See `docs/reference/event-bus.md` for the current source-of-truth.
>
> **Old → New mapping** :
>
> | Old (DESIGN.md)               | New (current)                          | Replaced by              |
> | ----------------------------- | -------------------------------------- | ------------------------ |
> | `PipelineObserver` Protocol   | `EventBus` subscriber pattern          | `feat/event-bus` v0.14.0 |
> | `StepEvent`                   | `StepProgress` event (typed dataclass) | `feat/event-bus`         |
> | `notify_progress()`           | `event_bus.emit(...)`                  | `feat/event-bus`         |
> | `CollectorObserver` (testing) | `RecordingSubscriber` (testing)        | `feat/event-bus`         |
> | `RichConsoleObserver`         | `RichConsoleSubscriber`                | `feat/event-bus`         |
> | `TelegramObserver`            | `TelegramSubscriber`                   | `feat/event-bus`         |

**Feature**: Pipeline Observer Protocol (Headless Mode)
**Type**: minor
**Status**: spec
**Date**: 2026-05-09

## NO DEFERRAL — MANDATORY

**Every step is adapted. Every test is written. Nothing is skipped, nothing is
deferred, nothing is left for "later". This applies to every phase and every
sub-phase of the implementation plan. Each phase gate MUST verify that all
planned work for that phase is complete — no partial implementations, no
"foundation first, integration later".**

## Purpose

Decouple the pipeline from `rich.Console`. Today `pipeline.py` creates a Console
internally and passes it to every step via `StepContext`. This makes the pipeline
impossible to drive from anything other than a TTY: no Web UI, no watcher service,
no headless cron mode with programmatic status polling.

## Design

### 1. PipelineObserver Protocol

```python
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

@runtime_checkable
class PipelineObserver(Protocol):
    """Observer contract for pipeline lifecycle + per-item progress."""

    name: str

    def on_pipeline_start(self, report: PipelineReport) -> None: ...
    def on_pipeline_end(self, report: PipelineReport) -> None: ...
    def on_step_start(self, step: str) -> None: ...
    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None: ...
    def on_step_error(self, step: str, error: Exception) -> None: ...
    def on_progress(self, event: StepEvent) -> None: ...
```

**`PipelineObserverBase`** — no-op base for observers that only implement a subset:

```python
class PipelineObserverBase:
    name = "base"

    def on_pipeline_start(self, report): pass
    def on_pipeline_end(self, report): pass
    def on_step_start(self, step): pass
    def on_step_end(self, step, report, elapsed): pass
    def on_step_error(self, step, error): pass
    def on_progress(self, event): pass
```

### 2. StepEvent

```python
@dataclass(frozen=True)
class StepEvent:
    """Per-item progress event emitted by pipeline steps.

    Frozen (immutable) — events are fire-and-forget snapshots.
    """

    step: str          # "ingest", "sort", "clean", "scrape", "cleanup",
                       # "enforce", "verify", "trailers", "dispatch"
    item: str          # Human-readable identifier
    status: str        # "started", "completed", "skipped", "failed"
    details: dict[str, object] = field(default_factory=dict)
```

### 3. Helper

```python
def notify_progress(
    observers: tuple[PipelineObserver, ...],
    event: StepEvent,
) -> None:
    """Call on_progress on every observer. Survives individual observer failures.

    A failing observer must not crash the pipeline, but the failure is logged
    (``observer_progress_failed`` at WARNING with ``exc_info=True``) so operators
    can debug broken observers without a silent swallow.
    """
    for obs in observers:
        try:
            obs.on_progress(event)
        except Exception as exc:
            _log.warning(
                "observer_progress_failed",
                observer=getattr(obs, "name", type(obs).__name__),
                error=str(exc),
                exc_info=True,
            )
```

### 4. StepContext Changes

- **Drop** `console: Console` — zero step implementations use it
- **Add** `observers: tuple[PipelineObserver, ...]` — immutable tuple

### 5. Pipeline Changes

- `__init__` parameter `console: Console | None` **replaced** by `observers: Sequence[PipelineObserver] | None`
- **Default**: `None` → auto-creates `[RichConsoleObserver()]` (identical behavior to today)
- **Explicit empty**: `observers=[]` → headless silent (Web UI / cron / tests)
- `_run_step` notifies observers instead of calling `self.console.print`
- `_step_context` passes `observers` tuple instead of `console`

### 6. RichConsoleObserver

Extracts ALL console output from `pipeline.py` and `commands/pipeline.py` into one observer:

| Callback            | Output                                                       |
| ------------------- | ------------------------------------------------------------ |
| `on_pipeline_start` | Banner "PersonalScraper Pipeline LIVE/Dry-Run run_id"        |
| `on_step_start`     | Step icon + name: `"\n[cyan]1/9[/cyan] [bold]INGEST[/bold]"` |
| `on_step_end`       | Summary: `"   3 OK, 1 skip (2.1s)"` + verbose details        |
| `on_step_error`     | `"   [red]FATAL: ErrorName: message[/red]"`                  |
| `on_progress`       | Per-item detail (only when `verbose=True`)                   |
| `on_pipeline_end`   | Final Panel/Table + duration                                 |

### 7. TelegramObserver

Replaces the inline `TelegramNotifier.send_report()` call in `commands/pipeline.py`:

- `on_pipeline_end` → `report.to_html()` → send via TelegramNotifier
- Created when `TelegramNotifier.is_configured(settings)` is True

**Constructor (DI choice)**: `TelegramObserver(notifier: TelegramNotifier)` — the
CLI builds the `HttpTransport` + `TelegramNotifier` and injects the ready notifier.
The observer itself stays transport-agnostic, which keeps unit tests trivial
(`TelegramObserver(Mock(spec=TelegramNotifier))`) and matches the rest of the
codebase's dependency-injection style.

### 8. Command-Line Wiring (`commands/pipeline.py`)

```python
observers: list[PipelineObserver] = []
if not headless:
    observers.append(RichConsoleObserver(console=console, verbose=verbose, ...))
    if TelegramNotifier.is_configured(settings):
        tg_transport = HttpTransport(TelegramNotifier.policy(settings.telegram_bot_token))
        tg_notifier = TelegramNotifier(tg_transport, settings.telegram_chat_id)
        observers.append(TelegramObserver(tg_notifier))
pipeline = Pipeline(config, settings, observers=observers, ...)
report = pipeline.run()
# Panel + send_report removed — observers handle it
```

**`--headless` CLI flag**: when set, the observer list stays empty — no Rich
console output, no Telegram. Intended for cron, CI, watcher services, and any
non-TTY context. Programmatic callers achieve the same with `observers=[]`.

### 9. Step Progress Integration

Each `run_*` function receives `observers: tuple[PipelineObserver, ...] = ()` and calls
`notify_progress(observers, StepEvent(...))` for per-item lifecycle events.

**Every step is adapted. Nothing is deferred. No step is skipped.**

| Step           | Precision                                                       |
| -------------- | --------------------------------------------------------------- |
| `run_ingest`   | Per-torrent: started → copied / skipped / failed                |
| `run_sort`     | Per-item: started → moved / skipped / error                     |
| `run_clean`    | Per-folder: started → cleaned / skipped / error                 |
| `run_scrape`   | Per-folder: started → matched / skipped_low_confidence / error  |
| `run_cleanup`  | Per-folder: started → removed / skipped                         |
| `run_enforce`  | Per-item: started → fixed / skipped / error                     |
| `run_verify`   | Per-item: started → ok / blocked                                |
| `run_trailers` | Per-item: started → downloaded / skipped / bot_detected / error |
| `run_dispatch` | Per-item: started → moved / merged / replaced / error           |

### 10. Files Touched

| File                                        | Action                                                               |
| ------------------------------------------- | -------------------------------------------------------------------- |
| `personalscraper/pipeline_observer.py`      | **new** — Protocol, StepEvent, notify_progress, PipelineObserverBase |
| `personalscraper/observers/__init__.py`     | **new** — package init                                               |
| `personalscraper/observers/rich_console.py` | **new** — RichConsoleObserver                                        |
| `personalscraper/observers/telegram.py`     | **new** — TelegramObserver                                           |
| `personalscraper/pipeline.py`               | mod — `observers` replaces `console`, `_run_step` notifies           |
| `personalscraper/pipeline_protocol.py`      | mod — `StepContext.console` → `observers`                            |
| `personalscraper/commands/pipeline.py`      | mod — build observers, wire into Pipeline                            |
| `personalscraper/ingest/ingest.py`          | mod — `notify_progress` per torrent                                  |
| `personalscraper/sorter/run.py`             | mod — `notify_progress` per item                                     |
| `personalscraper/process/run.py`            | mod — `on_progress` per sub-step                                     |
| `personalscraper/scraper/run.py`            | mod — `notify_progress` per folder                                   |
| `personalscraper/enforce/run.py`            | mod — `on_progress` per item                                         |
| `personalscraper/verify/run.py`             | mod — `on_progress` per item                                         |
| `personalscraper/trailers/step.py`          | mod — `on_progress` per trailer                                      |
| `personalscraper/dispatch/run.py`           | mod — `on_progress` per item                                         |

### 11. Tests

**New tests — NO test is skipped.**

| File                                        | Tests                                                                                                                         |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `tests/unit/test_pipeline_observer.py`      | Protocol runtime check, PipelineObserverBase no-op, StepEvent frozen + defaults, notify_progress fan-out + exception survival |
| `tests/unit/test_rich_console_observer.py`  | Each callback produces expected output, verbose mode toggles per-item details, output matches current format                  |
| `tests/unit/test_telegram_observer.py`      | on_pipeline_end calls send_report with correct HTML, is_configured gate                                                       |
| `tests/unit/test_ingest_progress.py`        | `run_ingest` emits events via CollectorObserver                                                                               |
| `tests/unit/test_sort_progress.py`          | `run_sort` emits events                                                                                                       |
| `tests/unit/test_scrape_progress.py`        | `run_scrape` emits events                                                                                                     |
| `tests/unit/test_process_progress.py`       | `run_process` emits events per sub-step                                                                                       |
| `tests/unit/test_enforce_progress.py`       | `run_enforce` emits events                                                                                                    |
| `tests/unit/test_verify_progress.py`        | `run_verify` emits events                                                                                                     |
| `tests/unit/test_trailers_progress.py`      | `run_trailers` emits events                                                                                                   |
| `tests/unit/test_dispatch_progress.py`      | `run_dispatch` emits events                                                                                                   |
| `tests/unit/test_pipeline_headless.py`      | `Pipeline(observers=[])` runs without console, all 9 steps complete                                                           |
| `tests/unit/test_pipeline_with_observer.py` | `Pipeline(observers=[CollectorObserver()])` — all 6 callbacks called in order                                                 |

**Existing test adaptation** — mocks that used `console=MagicMock()` switch to
`observers=[CollectorObserver()]`. No test is silently bypassed.

## Non-Goals

- Async pipeline execution (deferred to Watcher Service)
- Event Bus (separate P1 feature, built ON TOP of this one)
- Cross-process events
- HealthcheckObserver (healthcheck stays in CLI layer for now — it wraps the whole
  pipeline invocation, not individual steps)

## Design Decisions

- **`observers` in `StepContext` is a tuple, not a list** — frozen, hashable, signals
  "you don't modify this"
- **`notify_progress` catches observer exceptions and LOGS them** — one broken
  observer must not crash the pipeline, but failures are emitted as
  `observer_progress_failed` warnings (with `exc_info=True`) rather than a silent
  swallow, so operators can debug broken observers.
- **`PipelineObserver` is a Protocol, not an ABC** — structural subtyping, no
  mandatory base class, testable with `@runtime_checkable`
- **`RichConsoleObserver` is the default** — `observers=None` auto-creates it, so
  existing CLI users see zero difference
- **`StepEvent` is frozen** — events are snapshots, consumers shouldn't mutate them
- **`StepEvent.status` vocabulary is per-step** — DESIGN §9 lists the canonical
  statuses per step (e.g. `matched`, `bot_detected`, `merged`). The four-value
  axis `started/completed/skipped/failed` from §2 is the lifecycle pattern, not
  an enum constraint; each step uses the domain-appropriate label so observers
  can render meaningful output (e.g. RichConsole displays `🤖 bot_detected`).
- **`CollectorObserver`** — a recording observer for tests, shipped in
  `pipeline_observer.py` as a public testing utility. Lives in the production
  package (not under `tests/`) so that downstream consumers and integration
  tests outside the repo can import it from a stable path.

## SOLID Compliance

- **S**: Observer extracted from Pipeline core; events typed; each observer has one job
- **O**: New observers (WebSocket, log, metrics) without touching Pipeline
- **L**: Any PipelineObserver implementation can replace RichConsoleObserver
- **I**: PipelineObserver has 6 cohesive methods — no observer is forced to implement
  unused callbacks (PipelineObserverBase is no-op)
- **D**: Pipeline depends on PipelineObserver Protocol, not on rich.Console

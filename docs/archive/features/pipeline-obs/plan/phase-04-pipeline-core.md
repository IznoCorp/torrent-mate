# Phase 4 — StepContext + Pipeline Core Refactor

**Type**: core
**Codename**: pipeline-obs

## NO DEFERRAL

All changes in this phase are complete and tested. No partial migration, no
dual-path (console + observers) during the transition.

## Gate (pre-phase)

- [x] Phase 1 complete — `PipelineObserver`, `StepEvent`, `notify_progress` exist
- [x] Phase 2 complete — `RichConsoleObserver` exists
- [x] Phase 3 complete — `TelegramObserver` exists

## Sub-phases

### Sub-phase 4.1 — StepContext: drop `console`, add `observers`

**Files:**

- Modify: `personalscraper/pipeline_protocol.py`

Change `StepContext.console` to `StepContext.observers`:

```python
"""Pipeline step protocol and context bundle."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.models import StepReport
    from personalscraper.pipeline_observer import PipelineObserver


@dataclass(frozen=True)
class StepContext:
    """Immutable context bundle passed to every pipeline step adapter.

    Attributes:
        config: Loaded configuration with disk definitions and category mapping.
        settings: Pipeline settings with numeric thresholds and credentials.
        dry_run: If True, preview operations without side effects.
        interactive: If True, prompt before destructive actions.
        verbose: If True, emit detailed progress output.
        observers: Tuple of pipeline observers for progress + lifecycle notifications.
        upstream: Reports from previously executed steps, keyed by step name.
        extras: Mutable mapping for ad-hoc cross-step data (e.g. verified paths).
    """

    config: "Config"
    settings: "Settings"
    dry_run: bool
    interactive: bool
    verbose: bool
    observers: tuple["PipelineObserver", ...]
    upstream: Mapping[str, "StepReport"]
    extras: MutableMapping[str, Any]


@runtime_checkable
class PipelineStep(Protocol):
    """Callable pipeline step contract."""

    name: str

    def __call__(self, ctx: StepContext) -> "StepReport | tuple[StepReport, Any]": ...


def is_pipeline_step(obj: Any) -> bool:
    """Return True when *obj* satisfies the runtime step convention."""
    if not isinstance(obj, PipelineStep):
        return False
    name = getattr(obj, "name", None)
    return isinstance(name, str) and bool(name)


__all__ = ["PipelineStep", "StepContext", "is_pipeline_step"]
```

### Sub-phase 4.2 — Pipeline: `observers` replaces `console`

**Files:**

- Modify: `personalscraper/pipeline.py`

Key changes to `Pipeline.__init__` and `_run_step`:

1. `__init__` signature: replace `console: Console | None = None` with `observers: Sequence[PipelineObserver] | None = None`
2. Default: `None` → `[RichConsoleObserver()]`
3. Store as `self._observers: list[PipelineObserver]`
4. `_step_context` passes `tuple(self._observers)` (immutable snapshot)
5. `_run_step` notifies observers instead of `self.console.print`

```python
"""Sequential exhaustive pipeline orchestrator."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import ensure_staging_tree, find_ingest_dir, staging_path
from personalscraper.config import Settings
from personalscraper.logger import get_logger
from personalscraper.models import PipelineReport, StepReport
from personalscraper.observers.rich_console import RichConsoleObserver
from personalscraper.pipeline_observer import PipelineObserver
from personalscraper.pipeline_protocol import StepContext
from personalscraper.pipeline_steps import DEFAULT_STEPS, apply_step_overrides
from personalscraper.reports import STEP_REPORT_CONTRACT


class _CriticalStepError(Exception):
    """Raised internally when a critical pipeline step crashes."""


class Pipeline:
    """Sequential exhaustive pipeline orchestrator.

    Attributes:
        config: Config with paths and disk layout.
        settings: Pipeline configuration (secrets, thresholds).
        dry_run: Preview mode — no filesystem changes.
        interactive: Prompt user for ambiguous matches.
        verbose: Show per-item details in console output.
        skip_trailers: Skip the trailers download step entirely.
        continue_on_trailer_error: Continue to dispatch even when the
            trailers step returns status=error.
    """

    def __init__(
        self,
        config: Config,
        settings: Settings,
        dry_run: bool = False,
        interactive: bool = False,
        verbose: bool = False,
        observers: Sequence[PipelineObserver] | None = None,
        step_overrides: Mapping[str, Callable[..., Any]] | None = None,
        skip_trailers: bool = False,
        continue_on_trailer_error: bool = False,
    ) -> None:
        """Initialize the pipeline.

        Args:
            config: Config with paths and disk layout.
            settings: Pipeline configuration (secrets, thresholds).
            dry_run: If True, preview operations without modifying files.
            interactive: If True, prompt for ambiguous matches.
            verbose: If True, show per-item details.
            observers: Pipeline observers. Default ``None`` auto-creates
                ``[RichConsoleObserver()]``. Pass an empty sequence for
                headless/silent mode.
            step_overrides: Optional mapping of step name to replacement callable.
            skip_trailers: If True, skip the trailers download step.
            continue_on_trailer_error: Non-blocking by default.
        """
        self.config = config
        self.settings = settings
        self.dry_run = dry_run
        self.interactive = interactive
        self.verbose = verbose
        if observers is None:
            self._observers = [RichConsoleObserver(verbose=verbose)]
        else:
            self._observers = list(observers)
        self._log = get_logger("pipeline")
        self._steps = apply_step_overrides(DEFAULT_STEPS, step_overrides)
        self.skip_trailers = skip_trailers
        self.continue_on_trailer_error = continue_on_trailer_error

    def _step_context(self, report: PipelineReport, extras: dict[str, Any]) -> StepContext:
        """Build a StepContext for the current pipeline state."""
        return StepContext(
            config=self.config,
            settings=self.settings,
            dry_run=self.dry_run,
            interactive=self.interactive,
            verbose=self.verbose,
            observers=tuple(self._observers),
            upstream=report.steps,
            extras=extras,
        )

    # ... (rest of Pipeline unchanged except _run_step) ...

    def _run_step(
        self,
        name: str,
        fn: Callable[[], Any],
        report: PipelineReport,
        *,
        critical: bool = False,
    ) -> Any:
        """Execute a pipeline step with logging, timing, and observer notification."""

        for obs in self._observers:
            obs.on_step_start(name)

        self._log.info("step_started", step=name)
        t0 = time.monotonic()
        extra = None
        crashed = False

        try:
            result = fn()
            if isinstance(result, tuple):
                step_report, extra = result
            else:
                step_report = result
            step_report = self._with_details_payload(name, step_report)
            report.add_step(name, step_report)
        except Exception as exc:
            crashed = True
            self._log.exception("step_fatal", step=name, error=str(exc))
            for obs in self._observers:
                obs.on_step_error(name, exc)
            error_msg = f"{type(exc).__name__}: {exc}"
            step_report = StepReport(
                name=name,
                error_count=1,
                details=[f"Fatal: {error_msg}"],
            )
            step_report = self._with_details_payload(name, step_report)
            report.add_step(name, step_report)

        elapsed = time.monotonic() - t0
        if not crashed:
            for obs in self._observers:
                obs.on_step_end(name, step_report, elapsed)

        ok = step_report.success_count
        skip = step_report.skip_count
        err = step_report.error_count

        self._log.info(
            "step_finished",
            step=name,
            ok=ok,
            skip=skip,
            err=err,
            elapsed_s=round(elapsed, 1),
        )

        if crashed and critical:
            raise _CriticalStepError(f"Critical step '{name}' crashed")

        return extra

    # ... (rest of Pipeline unchanged: _recover_from_previous_run, run, etc.) ...
```

### Sub-phase 4.3 — Update all callers that pass `console=` to `Pipeline`

Search and update every `Pipeline(...)` constructor call to use `observers=` instead.

### Sub-phase 4.4 — Tests

**Files:**

- Create: `tests/unit/test_pipeline_headless.py`
- Create: `tests/unit/test_pipeline_with_observer.py`
- Modify: all existing test files that pass `console=MagicMock()` to `Pipeline()`

**`tests/unit/test_pipeline_headless.py`:**

```python
"""Tests for pipeline running in headless mode (no observers)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.models import PipelineReport
from personalscraper.pipeline import Pipeline


class TestPipelineHeadless:
    """Pipeline with observers=[] must not import or use rich.Console."""

    def test_pipeline_constructs_with_empty_observers(self):
        """Pipeline accepts observers=[] without error."""
        config = MagicMock()
        config.disks = []
        config.paths.data_dir = MagicMock()
        settings = MagicMock()

        pipeline = Pipeline(config, settings, observers=[])
        assert pipeline._observers == []

    def test_pipeline_default_creates_rich_console_observer(self):
        """observers=None auto-creates RichConsoleObserver."""
        config = MagicMock()
        config.disks = []
        config.paths.data_dir = MagicMock()
        settings = MagicMock()

        pipeline = Pipeline(config, settings)
        assert len(pipeline._observers) == 1
        assert pipeline._observers[0].name == "rich-console"

    def test_pipeline_run_with_no_observers(self):
        """pipeline runs to completion with observers=[] using mocked steps."""
        config = MagicMock()
        config.disks = []
        config.paths.data_dir = MagicMock()
        config.trailers.pipeline.skip = False
        config.trailers.pipeline.continue_on_error = False
        settings = MagicMock()

        from personalscraper.models import StepReport

        def fake_step(ctx):
            return StepReport(name=ctx.name, success_count=1)

        # Build overrides for all 9 steps
        overrides = {name: fake_step for name in [
            "ingest", "sort", "clean", "scrape", "cleanup",
            "enforce", "verify", "trailers", "dispatch",
        ]}
        # VerifyStep returns a tuple
        overrides["verify"] = lambda ctx: (
            StepReport(name="verify", success_count=1),
            ["/fake/path"],
        )

        pipeline = Pipeline(config, settings, observers=[], step_overrides=overrides)

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                report = pipeline.run()

        assert isinstance(report, PipelineReport)
        assert "ingest" in report.steps
```

**`tests/unit/test_pipeline_with_observer.py`:**

```python
"""Tests for pipeline running with a collector observer."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline import Pipeline
from personalscraper.pipeline_observer import (
    PipelineObserver,
    PipelineObserverBase,
    StepEvent,
)


class CollectorObserver(PipelineObserverBase):
    """Records every callback for test assertions."""

    name = "collector"

    def __init__(self):
        super().__init__()
        self.pipeline_starts: list[PipelineReport] = []
        self.pipeline_ends: list[PipelineReport] = []
        self.starts: list[str] = []
        self.ends: list[tuple[str, StepReport, float]] = []
        self.errors: list[tuple[str, Exception]] = []
        self.progress: list[StepEvent] = []

    def on_pipeline_start(self, report): self.pipeline_starts.append(report)
    def on_pipeline_end(self, report): self.pipeline_ends.append(report)
    def on_step_start(self, step): self.starts.append(step)
    def on_step_end(self, step, report, elapsed): self.ends.append((step, report, elapsed))
    def on_step_error(self, step, error): self.errors.append((step, error))
    def on_progress(self, event): self.progress.append(event)


class TestPipelineWithObserver:
    """Pipeline observer integration tests."""

    def test_all_step_callbacks_called_in_order(self):
        """on_step_start + on_step_end called for each step in order."""
        config = MagicMock()
        config.disks = []
        config.paths.data_dir = MagicMock()
        config.trailers.pipeline.skip = False
        config.trailers.pipeline.continue_on_error = False
        settings = MagicMock()

        collector = CollectorObserver()

        def fake_step(ctx):
            return StepReport(name="fake", success_count=1)

        overrides = {name: fake_step for name in [
            "ingest", "sort", "clean", "scrape", "cleanup",
            "enforce", "verify", "trailers", "dispatch",
        ]}
        overrides["verify"] = lambda ctx: (
            StepReport(name="verify", success_count=1),
            ["/f"],
        )

        pipeline = Pipeline(config, settings, observers=[collector], step_overrides=overrides)

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                pipeline.run()

        # 9 steps → 9 starts + 9 ends
        assert len(collector.starts) == 9
        assert len(collector.ends) == 9
        assert collector.starts[0] == "ingest"
        assert collector.ends[-1][0] == "dispatch"

    def test_on_step_error_called_on_failure(self):
        """on_step_error is called when a step raises."""
        config = MagicMock()
        config.disks = []
        config.paths.data_dir = MagicMock()
        config.trailers.pipeline.skip = False
        config.trailers.pipeline.continue_on_error = False
        settings = MagicMock()

        collector = CollectorObserver()

        def crash_step(ctx):
            raise ValueError("boom")

        overrides = {
            "ingest": crash_step,
            "sort": lambda ctx: StepReport(name="sort"),
            "clean": lambda ctx: StepReport(name="clean"),
            "scrape": lambda ctx: StepReport(name="scrape"),
            "cleanup": lambda ctx: StepReport(name="cleanup"),
            "enforce": lambda ctx: StepReport(name="enforce"),
            "verify": lambda ctx: (StepReport(name="verify"), ["/f"]),
            "trailers": lambda ctx: StepReport(name="trailers"),
            "dispatch": lambda ctx: StepReport(name="dispatch"),
        }

        pipeline = Pipeline(config, settings, observers=[collector], step_overrides=overrides)

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                pipeline.run()

        assert len(collector.errors) == 1
        assert "boom" in str(collector.errors[0][1])

    def test_on_pipeline_end_called(self):
        """on_pipeline_end is called after all steps."""
        config = MagicMock()
        config.disks = []
        config.paths.data_dir = MagicMock()
        config.trailers.pipeline.skip = False
        config.trailers.pipeline.continue_on_error = False
        settings = MagicMock()

        collector = CollectorObserver()

        def fake_step(ctx):
            return StepReport(name="fake", success_count=1)

        overrides = {name: fake_step for name in [
            "ingest", "sort", "clean", "scrape", "cleanup",
            "enforce", "verify", "trailers", "dispatch",
        ]}
        overrides["verify"] = lambda ctx: (
            StepReport(name="verify", success_count=1),
            ["/f"],
        )

        pipeline = Pipeline(config, settings, observers=[collector], step_overrides=overrides)

        with patch("personalscraper.pipeline.ensure_staging_tree"):
            with patch.object(Pipeline, "_check_temp_empty_gate"):
                pipeline.run()

        assert len(collector.pipeline_ends) == 1
        assert isinstance(collector.pipeline_ends[0], PipelineReport)
```

## Gate (post-phase)

- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass
- [ ] `rg "from rich.console import Console" personalscraper/pipeline.py` — zero matches
- [ ] `rg "self\.console" personalscraper/pipeline.py` — zero matches
- [ ] `rg 'console=MagicMock\(\)' tests/` — zero matches (all migrated)
- [ ] Commit: `chore(pipeline-obs): phase 4 gate — pipeline core refactor`

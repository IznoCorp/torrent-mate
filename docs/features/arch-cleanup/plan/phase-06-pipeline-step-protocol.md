# Phase 6 — `PipelineStep` Protocol + `StepContext`

**Goal:** Introduce a formal `PipelineStep` Protocol and a `StepContext` dataclass. Wrap each of the 9 existing `run_*` functions in a thin Step class. Pipeline orchestration becomes a registry-driven loop. The existing `step_overrides` parameter is preserved as a compatibility shim — **zero test changes**.

**Risk:** Medium. The Protocol is additive (no removal of existing call paths until 0.10.0). The `pipeline.run()` loop change is the riskiest single edit; rollback safety comes from a compat shim (`_step_overrides_to_protocol`) that wraps legacy callables into anonymous PipelineStep instances — the legacy `step_overrides=` API stays operational throughout, so any sub-phase revert leaves the pipeline running.

**Files affected (estimate):**

- Create: `personalscraper/pipeline_protocol.py` (populate the stub from phase 1.4), `personalscraper/pipeline_steps.py`, `tests/test_pipeline_protocol.py`, `tests/test_pipeline_step_overrides_shim.py`
- Modify: `personalscraper/pipeline.py`

## Sub-phases

### 6.1 — Define `PipelineStep` Protocol + `StepContext` (TDD)

**Files:**

- Modify: `personalscraper/pipeline_protocol.py` (was a stub from phase 1.4)
- Create: `tests/test_pipeline_protocol.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pipeline_protocol.py
"""Tests for the PipelineStep Protocol and StepContext."""
from __future__ import annotations

import pytest

from personalscraper.pipeline_protocol import PipelineStep, StepContext
from personalscraper.models import StepReport


def test_step_context_is_frozen():
    ctx = StepContext(
        config=None, settings=None, dry_run=False, interactive=False,
        verbose=False, console=None, upstream={}, extras={},
    )
    with pytest.raises((AttributeError, TypeError)):
        ctx.dry_run = True  # frozen dataclass forbids mutation


def test_protocol_runtime_check_accepts_compliant_class():
    class FakeStep:
        name = "fake"

        def __call__(self, ctx: StepContext) -> StepReport:
            return StepReport(name=self.name)

    assert isinstance(FakeStep(), PipelineStep)


def test_protocol_runtime_check_rejects_missing_call():
    class NoCall:
        name = "x"

    assert not isinstance(NoCall(), PipelineStep)


def test_protocol_runtime_check_rejects_missing_name():
    class NoName:
        def __call__(self, ctx: StepContext) -> StepReport:
            return StepReport(name="anon")

    # `name` is a Protocol attribute — runtime_checkable Protocols only
    # check method presence, not attributes. Document this and accept it.
    # The test asserts the convention via a separate helper.
    from personalscraper.pipeline_protocol import is_pipeline_step

    assert not is_pipeline_step(NoName())


def test_step_context_upstream_is_mapping():
    prior = StepReport(name="ingest", success_count=3)
    ctx = StepContext(
        config=None, settings=None, dry_run=False, interactive=False,
        verbose=False, console=None, upstream={"ingest": prior}, extras={},
    )
    assert ctx.upstream["ingest"].success_count == 3
```

- [ ] **Step 2: Run tests, expect FAIL** (Protocol/StepContext not implemented yet).

- [ ] **Step 3: Implement `pipeline_protocol.py`**

```python
# personalscraper/pipeline_protocol.py
"""PipelineStep Protocol and StepContext.

Formalises the step orchestration interface so personalscraper/pipeline.py
no longer depends on the concrete signatures of each domain's run_*().
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from rich.console import Console

    from personalscraper.conf.models import Config
    from personalscraper.config import Settings
    from personalscraper.models import StepReport


@dataclass(frozen=True)
class StepContext:
    """Context bundle passed to every PipelineStep.__call__.

    Attributes:
        config: Project Config (paths, disks, categories).
        settings: Pipeline runtime Settings (secrets, thresholds).
        dry_run: True to preview without filesystem mutation.
        interactive: True to prompt for ambiguous matches.
        verbose: True to render per-item details on the console.
        console: Rich console for human output.
        upstream: Mapping of previous step name -> StepReport.
        extras: Mutable artifact map shared across steps (e.g., verify -> dispatchable list).
    """

    config: "Config"
    settings: "Settings"
    dry_run: bool
    interactive: bool
    verbose: bool
    console: "Console"
    upstream: Mapping[str, "StepReport"]
    extras: MutableMapping[str, Any]


@runtime_checkable
class PipelineStep(Protocol):
    """Contract every pipeline step implements.

    `name` is a class- or instance-level string identifying the step.
    `__call__` accepts a StepContext and returns a StepReport.
    """

    name: str

    def __call__(self, ctx: StepContext) -> "StepReport": ...


def is_pipeline_step(obj: Any) -> bool:
    """Stricter helper than isinstance(obj, PipelineStep).

    runtime_checkable Protocols only verify method presence; this helper
    also requires `name` to be a non-empty string attribute.
    """
    if not isinstance(obj, PipelineStep):
        return False
    name = getattr(obj, "name", None)
    return isinstance(name, str) and bool(name)


__all__ = ["PipelineStep", "StepContext", "is_pipeline_step"]
```

- [ ] **Step 4: Run tests, expect 5/5 PASS**

```bash
pytest tests/test_pipeline_protocol.py -v
```

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(arch-cleanup): introduce PipelineStep Protocol and StepContext"
```

### 6.2 — Create step wrappers

**Files:**

- Create: `personalscraper/pipeline_steps.py`
- Create: `tests/test_pipeline_step_wrappers.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pipeline_step_wrappers.py
"""Tests verifying each step wrapper conforms to PipelineStep."""
import pytest

from personalscraper.pipeline_protocol import PipelineStep, is_pipeline_step
from personalscraper.pipeline_steps import (
    IngestStep, SortStep, CleanStep, ScrapeStep, CleanupStep,
    EnforceStep, VerifyStep, TrailersStep, DispatchStep, DEFAULT_STEPS,
)

ALL_STEP_CLASSES = [
    IngestStep, SortStep, CleanStep, ScrapeStep, CleanupStep,
    EnforceStep, VerifyStep, TrailersStep, DispatchStep,
]


@pytest.mark.parametrize("cls", ALL_STEP_CLASSES)
def test_step_class_conforms_to_protocol(cls):
    instance = cls()
    assert is_pipeline_step(instance), f"{cls.__name__} does not satisfy PipelineStep"


def test_default_steps_registry_has_nine_entries():
    assert len(DEFAULT_STEPS) == 9
    assert set(DEFAULT_STEPS) == {
        "ingest", "sort", "clean", "scrape", "cleanup",
        "enforce", "verify", "trailers", "dispatch",
    }


def test_default_steps_names_match_keys():
    for key, step in DEFAULT_STEPS.items():
        assert step.name == key
```

- [ ] **Step 2: Run, FAIL.**

- [ ] **Step 3: Implement `pipeline_steps.py`**

```python
# personalscraper/pipeline_steps.py
"""Step wrappers and default registry.

Each Step class is a thin adapter implementing PipelineStep around the
existing run_*() function in its domain module. Behaviour-preserving.
"""

from __future__ import annotations

from personalscraper.pipeline_protocol import PipelineStep, StepContext
from personalscraper.models import StepReport


class IngestStep:
    name = "ingest"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.ingest.ingest import run_ingest
        return run_ingest(ctx.settings, dry_run=ctx.dry_run, config=ctx.config)


class SortStep:
    name = "sort"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.sorter.run import run_sort
        return run_sort(
            ctx.settings,
            staging_dir=ctx.config.paths.staging_dir,
            dry_run=ctx.dry_run,
            config=ctx.config,
        )


class CleanStep:
    name = "clean"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.process.run import run_clean
        return run_clean(ctx.settings, config=ctx.config, dry_run=ctx.dry_run)


class ScrapeStep:
    name = "scrape"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.scraper.run import run_scrape
        return run_scrape(
            ctx.settings,
            config=ctx.config,
            dry_run=ctx.dry_run,
            interactive=ctx.interactive,
        )


class CleanupStep:
    name = "cleanup"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.process.run import run_cleanup
        return run_cleanup(ctx.settings, config=ctx.config, dry_run=ctx.dry_run)


class EnforceStep:
    name = "enforce"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.enforce.run import run_enforce
        return run_enforce(ctx.settings, ctx.config, dry_run=ctx.dry_run)


class VerifyStep:
    name = "verify"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.verify.run import run_verify
        report, dispatchable = run_verify(ctx.settings, ctx.config, dry_run=ctx.dry_run, fix=False)
        ctx.extras["verified"] = dispatchable
        return report


class TrailersStep:
    name = "trailers"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.trailers.step import run_trailers
        verified = list(ctx.extras.get("verified", []))
        skip_trailers = bool(ctx.extras.get("skip_trailers", False))
        return run_trailers(
            ctx.config,
            staging_dir=ctx.config.paths.staging_dir,
            verified=verified,
            skip_trailers=skip_trailers,
        )


class DispatchStep:
    name = "dispatch"

    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.dispatch.run import run_dispatch
        verified = list(ctx.extras.get("verified", []))
        return run_dispatch(ctx.settings, config=ctx.config, dry_run=ctx.dry_run, verified=verified)


DEFAULT_STEPS: dict[str, PipelineStep] = {
    cls().name: cls()
    for cls in [
        IngestStep, SortStep, CleanStep, ScrapeStep, CleanupStep,
        EnforceStep, VerifyStep, TrailersStep, DispatchStep,
    ]
}

__all__ = [
    "IngestStep", "SortStep", "CleanStep", "ScrapeStep", "CleanupStep",
    "EnforceStep", "VerifyStep", "TrailersStep", "DispatchStep",
    "DEFAULT_STEPS",
]
```

> **Note**: signatures of each `run_*` are **examples** based on phase-1 inventory expectations. The implementer must align each wrapper to the actual signature in the current code (which may differ — e.g., `run_sort` may take more kwargs). Per-step adjustments are local to each wrapper class.

- [ ] **Step 4: Run, expect 11/11 PASS** (9 parametrized + 2 registry tests).

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(arch-cleanup): add Step wrappers and DEFAULT_STEPS registry"
```

### 6.3 — Add `step_overrides` shim test

**Files:**

- Create: `tests/test_pipeline_step_overrides_shim.py`

- [ ] **Step 1: Write a test verifying the legacy `step_overrides=` API still works**

```python
# tests/test_pipeline_step_overrides_shim.py
"""Compat shim: legacy step_overrides=Mapping[str, Callable] still works."""
from unittest.mock import MagicMock

from personalscraper.pipeline import Pipeline
from personalscraper.models import StepReport


def test_step_overrides_legacy_callable_still_invoked(tmp_path, monkeypatch):
    """A pre-arch-cleanup test using step_overrides= must still pass."""
    fake_ingest = MagicMock(return_value=StepReport(name="ingest", success_count=1))
    fake_sort = MagicMock(return_value=StepReport(name="sort", success_count=1))

    # ... build minimal Config + Settings using existing test fixtures ...
    from tests.fixtures.config import minimal_config  # adapt to actual fixture path
    config = minimal_config(tmp_path)
    settings = ...  # likewise

    pipeline = Pipeline(
        config=config, settings=settings, dry_run=True,
        step_overrides={"ingest": fake_ingest, "sort": fake_sort},
    )
    pipeline.run()
    fake_ingest.assert_called_once()
    fake_sort.assert_called_once()
```

> **Note**: this test mirrors the existing test patterns from `tests/test_pipeline.py` and `tests/test_pipeline_orchestration.py` — the implementer must adapt fixture imports to the actual fixtures in those files. The point is to assert that the **shim does not break** the existing call style.

- [ ] **Step 2: Run; it may FAIL until 6.4 if the new test asserts the future shim behaviour.** Keep the test in the same commit as the shim if existing tests already cover current `step_overrides=`, otherwise add it immediately before the 6.4 implementation commit.

If pre-existing tests under `tests/test_pipeline.py` or `tests/test_pipeline_orchestration.py` already cover this surface, skip this sub-phase and rely on those.

- [ ] **Step 3: Commit (if added)**

```bash
git commit -m "test(arch-cleanup): freeze step_overrides shim contract"
```

### 6.4 — Rewrite `Pipeline.run()` to use the registry + shim

**Files:**

- Modify: `personalscraper/pipeline.py`

The current `Pipeline.run()` uses `self._step_overrides.get("ingest", run_ingest)` per step. Refactor to:

1. Resolve the step registry: `steps = DEFAULT_STEPS | (self._step_overrides_to_protocol())` where `_step_overrides_to_protocol()` wraps any callable in an anonymous Protocol-conforming class.
2. Loop over the registry in order, building the `StepContext` with accumulated `upstream` reports.
3. Preserve all existing gates (ingest crash → abort, dispatch only if verified items exist, etc.).

- [ ] **Step 1: Add `_step_overrides_to_protocol` helper**

```python
# Inside Pipeline class
def _step_overrides_to_protocol(self) -> dict[str, PipelineStep]:
    """Wrap any legacy callable overrides into anonymous PipelineStep instances."""
    result: dict[str, PipelineStep] = {}
    for name, override in self._step_overrides.items():
        # If it's already a PipelineStep, pass through.
        if is_pipeline_step(override):
            result[name] = override  # type: ignore[assignment]
            continue
        # Else wrap the callable (signature unknown — call with positional unpack of ctx fields).
        result[name] = _LegacyCallableStep(name, override)
    return result
```

- [ ] **Step 2: Define `_LegacyCallableStep`** below the Pipeline class

```python
class _LegacyCallableStep:
    """Wraps a pre-Protocol callable into a PipelineStep.

    Invokes the wrapped callable with the same positional/keyword args that
    the original Pipeline.run loop used to pass.
    """

    def __init__(self, name: str, fn: Callable[..., StepReport]) -> None:
        self.name = name
        self._fn = fn

    def __call__(self, ctx: StepContext) -> StepReport:
        try:
            adapter = _LEGACY_ADAPTERS[self.name]
        except KeyError as exc:
            raise ValueError(f"Unknown step name: {self.name}") from exc
        result = adapter(self._fn, ctx)
        # verify-style overrides may still return (StepReport, dispatchable).
        if isinstance(result, tuple):
            return result[0]
        return result
```

> **Important**: the legacy callable shapes differ per step and must match the current production calls in `Pipeline.run()`, not the illustrative snippets above. For this repo snapshot the key shapes are: `sort(settings, staging_dir=..., dry_run=..., config=...)`, `clean(settings, config=..., dry_run=...)`, `scrape(settings, config=..., dry_run=..., interactive=...)`, `verify(settings, config, dry_run=..., fix=False) -> (StepReport, dispatchable)`, `trailers(config, staging_dir=..., verified=..., skip_trailers=...)`, and `dispatch(settings, config=..., dry_run=..., verified=...)`. The shim must therefore be a small per-step lookup table. Implement as a `_LEGACY_ADAPTERS` mapping each step name to a closure that knows how to call the override with the right shape. The verify adapter must write the returned dispatchable list into `ctx.extras["verified"]`.

- [ ] **Step 3: Replace per-step `run_fn = self._step_overrides.get(...)` blocks with the unified loop**

```python
def run(self) -> PipelineReport:
    # ... existing pre-step bootstrap (staging, recovery) ...
    steps: dict[str, PipelineStep] = {**DEFAULT_STEPS, **self._step_overrides_to_protocol()}

    report = PipelineReport(started_at=datetime.now())
    upstream: dict[str, StepReport] = {}
    extras: dict[str, Any] = {
        "skip_trailers": self.skip_trailers,
    }

    for name in ["ingest", "sort", "clean", "scrape", "cleanup",
                 "enforce", "verify", "trailers", "dispatch"]:
        # Apply existing gates BEFORE each step
        if name == "dispatch" and not _has_verified_items(upstream.get("verify")):
            self._log.info("dispatch_skipped_no_verified_items")
            continue
        # ... other existing gates (ingest critical, sort critical, trailers skip flag) ...

        ctx = StepContext(
            config=self.config, settings=self.settings,
            dry_run=self.dry_run, interactive=self.interactive,
            verbose=self.verbose, console=self.console,
            upstream=upstream, extras=extras,
        )
        try:
            step_report = steps[name](ctx)
        except _CriticalStepError:
            raise
        except Exception as exc:
            # ... existing per-step error handling ...
            step_report = StepReport(name=name, error_count=1, ...)

        upstream[name] = step_report
        report.add_step(name, step_report)

    report.finished_at = datetime.now()
    return report
```

- [ ] **Step 4: Run the FULL test suite**

```bash
make check
pytest tests/test_pipeline.py tests/test_pipeline_orchestration.py -v
pytest tests/integration/ -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(arch-cleanup): Pipeline.run uses PipelineStep registry + legacy shim"
```

### 6.5 — Doc update

**Files:**

- Modify: `docs/reference/pipeline-internals.md`

- [ ] **Step 1: Document the Protocol section** with `PipelineStep`, `StepContext`, `DEFAULT_STEPS`, and the legacy-shim contract for `step_overrides=`.
- [ ] **Step 2: Note the 0.10.0 deprecation** of `step_overrides=` (encourages new test code to pass `steps=...` instead).
- [ ] **Step 3: Commit**

```bash
git commit -m "docs(arch-cleanup): document PipelineStep Protocol and StepContext"
```

### 6.6 — Phase gate

```bash
make check
pytest tests/test_pipeline.py tests/test_pipeline_orchestration.py -v
git commit --allow-empty -m "chore(arch-cleanup): phase 6 gate — PipelineStep Protocol complete"
```

## Quality gate

```bash
make check
pytest tests/test_pipeline.py tests/test_pipeline_orchestration.py tests/integration -v
```

## Success criteria

- `personalscraper/pipeline_protocol.py` defines `PipelineStep`, `StepContext`, `is_pipeline_step`
- `personalscraper/pipeline_steps.py` exposes 9 Step classes + `DEFAULT_STEPS` registry
- `Pipeline.run()` uses the registry-driven loop
- `step_overrides=` parameter still accepted; legacy tests pass without modification
- `docs/reference/pipeline-internals.md` documents the new contract
- All pipeline + integration tests pass

## Rollback plan

The legacy shim guarantees rollback safety: even if 6.4 introduces a bug, reverting it leaves 6.1-6.3 (Protocol declared, wrappers exist, registry exists) intact and harmless — the Pipeline simply doesn't use them yet.

## Estimated effort

4-6 commits, ~6 hours.

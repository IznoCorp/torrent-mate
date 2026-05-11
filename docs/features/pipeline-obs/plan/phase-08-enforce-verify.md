# Phase 8 — Step Integration: Enforce + Verify

**Type**: steps
**Codename**: pipeline-obs

## NO DEFERRAL

Both steps fully adapted. No step is left for later.

## Gate (pre-phase)

- [x] Phase 7 complete — process + scrape emit progress events

## Sub-phases

### Sub-phase 8.1 — Enforce progress

**Files:**

- Modify: `personalscraper/enforce/run.py`
- Modify: `personalscraper/pipeline_steps.py` (EnforceStep adapter)
- Create: `tests/unit/test_enforce_progress.py`

Add `observers` to `run_enforce`:

```python
def run_enforce(
    settings: Settings,
    config: Config,
    *,
    dry_run: bool = False,
    observers: tuple[PipelineObserver, ...] = (),
) -> StepReport:
```

Per-item progress:

```python
for item in items:
    notify_progress(observers, StepEvent(
        step="enforce", item=str(item.name), status="started",
    ))
    # ... enforce ...
    if fixed:
        notify_progress(observers, StepEvent(
            step="enforce", item=str(item.name), status="fixed",
            details={"renamed_to": new_name},
        ))
    elif skipped:
        notify_progress(observers, StepEvent(
            step="enforce", item=str(item.name), status="skipped",
        ))
    elif errored:
        notify_progress(observers, StepEvent(
            step="enforce", item=str(item.name), status="failed",
            details={"error": str(exc)},
        ))
```

Update adapter:

```python
class EnforceStep:
    name = "enforce"
    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.enforce.run import run_enforce
        return run_enforce(ctx.settings, ctx.config, dry_run=ctx.dry_run, observers=ctx.observers)
```

### Sub-phase 8.2 — Verify progress

**Files:**

- Modify: `personalscraper/verify/run.py`
- Modify: `personalscraper/pipeline_steps.py` (VerifyStep adapter)
- Create: `tests/unit/test_verify_progress.py`

Add `observers` to `run_verify`:

```python
def run_verify(
    settings: Settings,
    config: Config,
    *,
    dry_run: bool = False,
    fix: bool = False,
    movies_only: bool = False,
    tvshows_only: bool = False,
    observers: tuple[PipelineObserver, ...] = (),
) -> tuple[StepReport, list[Path]]:
```

Per-item progress:

```python
for item in items:
    notify_progress(observers, StepEvent(
        step="verify", item=str(item.name), status="started",
    ))
    # ... verify ...
    if passed:
        dispatchable.append(item)
        notify_progress(observers, StepEvent(
            step="verify", item=str(item.name), status="ok",
        ))
    else:
        notify_progress(observers, StepEvent(
            step="verify", item=str(item.name), status="blocked",
            details={"reasons": check_results},
        ))
```

Update adapter:

```python
class VerifyStep:
    name = "verify"
    def __call__(self, ctx: StepContext) -> tuple[StepReport, Any]:
        from personalscraper.verify.run import run_verify
        return run_verify(
            ctx.settings, ctx.config,
            dry_run=ctx.dry_run, fix=False,
            observers=ctx.observers,
        )
```

### Sub-phase 8.3 — Tests

**`tests/unit/test_enforce_progress.py`:**

```python
"""Tests for enforce progress events."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.enforce.run import run_enforce


class TestEnforceProgress:
    def test_run_enforce_accepts_observers(self):
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        config.categories = []

        with patch("personalscraper.enforce.run._collect_items", return_value=[]):
            report = run_enforce(settings, config, dry_run=True, observers=())
        assert report.name == "enforce"
```

**`tests/unit/test_verify_progress.py`:**

```python
"""Tests for verify progress events."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.verify.run import run_verify


class TestVerifyProgress:
    def test_run_verify_accepts_observers(self):
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        config.categories = []

        with patch("personalscraper.verify.run._collect_items", return_value=[]):
            report, dispatchable = run_verify(settings, config, dry_run=True, observers=())
        assert report.name == "verify"
        assert dispatchable == []
```

## Gate (post-phase)

- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass
- [ ] `rg "console" personalscraper/enforce/run.py` — zero matches
- [ ] `rg "console" personalscraper/verify/run.py` — zero matches
- [ ] Commit: `chore(pipeline-obs): phase 8 gate — enforce + verify progress`

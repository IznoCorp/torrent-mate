# Phase 9 — Step Integration: Trailers + Dispatch + Final Gate

**Type**: steps
**Codename**: pipeline-obs

## NO DEFERRAL

ALL remaining steps adapted. Final quality gate. Nothing left undone.

## Gate (pre-phase)

- [x] Phase 8 complete — enforce + verify emit progress events
- [x] Phases 1–8 all green

## Sub-phases

### Sub-phase 9.1 — Trailers progress

**Files:**

- Modify: `personalscraper/trailers/step.py`
- Modify: `personalscraper/pipeline_steps.py` (TrailersStep adapter)
- Create: `tests/unit/test_trailers_progress.py`

Add `observers` to `run_trailers`:

```python
def run_trailers(
    config: Config,
    *,
    staging_dir: Path,
    verified: list[Path],
    skip_trailers: bool = False,
    observers: tuple[PipelineObserver, ...] = (),
) -> StepReport:
```

Per-item progress:

```python
for item in verified:
    notify_progress(observers, StepEvent(
        step="trailers", item=str(item.name), status="started",
    ))
    # ... download trailer ...
    if downloaded:
        notify_progress(observers, StepEvent(
            step="trailers", item=str(item.name), status="downloaded",
            details={"url": url, "format": fmt},
        ))
    elif skipped:
        notify_progress(observers, StepEvent(
            step="trailers", item=str(item.name), status="skipped",
            details={"reason": reason},
        ))
    elif bot_detected:
        notify_progress(observers, StepEvent(
            step="trailers", item=str(item.name), status="bot_detected",
        ))
    elif errored:
        notify_progress(observers, StepEvent(
            step="trailers", item=str(item.name), status="failed",
            details={"error": str(exc)},
        ))
```

Update adapter:

```python
class TrailersStep:
    name = "trailers"
    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.trailers.step import run_trailers
        return run_trailers(
            ctx.config,
            staging_dir=ctx.config.paths.staging_dir,
            verified=ctx.extras.get("verified", []),
            skip_trailers=bool(ctx.extras.get("skip_trailers", False)),
            observers=ctx.observers,
        )
```

### Sub-phase 9.2 — Dispatch progress

**Files:**

- Modify: `personalscraper/dispatch/run.py`
- Modify: `personalscraper/pipeline_steps.py` (DispatchStep adapter)
- Create: `tests/unit/test_dispatch_progress.py`

Add `observers` to `run_dispatch`:

```python
def run_dispatch(
    settings: Settings,
    *,
    config: Config,
    dry_run: bool = False,
    verified: list[Path] | None = None,
    observers: tuple[PipelineObserver, ...] = (),
) -> StepReport:
```

Per-item progress:

```python
for item in items:
    notify_progress(observers, StepEvent(
        step="dispatch", item=str(item.name), status="started",
    ))
    if action == "moved":
        notify_progress(observers, StepEvent(
            step="dispatch", item=str(item.name), status="moved",
            details={"dest": str(destination), "disk": disk_name},
        ))
    elif action == "merged":
        notify_progress(observers, StepEvent(
            step="dispatch", item=str(item.name), status="merged",
            details={"dest": str(destination), "disk": disk_name},
        ))
    elif action == "replaced":
        notify_progress(observers, StepEvent(
            step="dispatch", item=str(item.name), status="replaced",
            details={"dest": str(destination), "disk": disk_name},
        ))
    elif action == "skipped":
        notify_progress(observers, StepEvent(
            step="dispatch", item=str(item.name), status="skipped",
            details={"reason": reason},
        ))
```

Update adapter:

```python
class DispatchStep:
    name = "dispatch"
    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.dispatch.run import run_dispatch
        return run_dispatch(
            ctx.settings, config=ctx.config,
            dry_run=ctx.dry_run,
            verified=ctx.extras.get("verified"),
            observers=ctx.observers,
        )
```

### Sub-phase 9.3 — LegacyCallableStep update

Update `LegacyCallableStep.__call__` to pass `ctx.observers` for each known step name:

```python
def __call__(self, ctx: StepContext) -> Any:
    if self.name == "ingest":
        return self._fn(ctx.settings, dry_run=ctx.dry_run, config=ctx.config, observers=ctx.observers)
    if self.name == "sort":
        return self._fn(ctx.settings, staging_dir=ctx.config.paths.staging_dir,
                        dry_run=ctx.dry_run, config=ctx.config, observers=ctx.observers)
    if self.name in {"clean", "cleanup"}:
        return self._fn(ctx.settings, dry_run=ctx.dry_run, config=ctx.config, observers=ctx.observers)
    if self.name == "scrape":
        return self._fn(ctx.settings, config=ctx.config, dry_run=ctx.dry_run,
                        interactive=ctx.interactive, observers=ctx.observers)
    if self.name == "enforce":
        return self._fn(ctx.settings, ctx.config, dry_run=ctx.dry_run, observers=ctx.observers)
    if self.name == "verify":
        return self._fn(ctx.settings, ctx.config, dry_run=ctx.dry_run,
                        fix=False, observers=ctx.observers)
    if self.name == "trailers":
        return self._fn(ctx.config, staging_dir=ctx.config.paths.staging_dir,
                        verified=ctx.extras.get("verified", []),
                        skip_trailers=bool(ctx.extras.get("skip_trailers", False)),
                        observers=ctx.observers)
    if self.name == "dispatch":
        return self._fn(ctx.settings, config=ctx.config, dry_run=ctx.dry_run,
                        verified=ctx.extras.get("verified"), observers=ctx.observers)
    return self._fn(ctx)
```

### Sub-phase 9.4 — Tests

**`tests/unit/test_trailers_progress.py`:**

```python
"""Tests for trailers progress events."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.trailers.step import run_trailers


class TestTrailersProgress:
    def test_run_trailers_accepts_observers(self):
        config = MagicMock()
        staging_dir = Path("/tmp/staging")

        with patch("personalscraper.trailers.step._download_trailers", return_value=[]):
            report = run_trailers(
                config, staging_dir=staging_dir,
                verified=[], observers=(),
            )
        assert report.name == "trailers"
```

**`tests/unit/test_dispatch_progress.py`:**

```python
"""Tests for dispatch progress events."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.dispatch.run import run_dispatch


class TestDispatchProgress:
    def test_run_dispatch_accepts_observers(self):
        settings = MagicMock()
        config = MagicMock()
        config.disks = []
        config.paths.staging_dir = Path("/tmp/staging")
        config.categories = []

        with patch("personalscraper.dispatch.run._collect_items", return_value=[]):
            report = run_dispatch(settings, config=config, dry_run=True, observers=())
        assert report.name == "dispatch"
```

### Sub-phase 9.5 — Final gate

Run the full quality gate:

```bash
make lint
make test
make check
python3 scripts/check-module-size.py
python3 scripts/check-typed-api.py
python -c "import personalscraper"
```

**Residual import grep:**

```bash
rg "from rich.console import Console" --type py personalscraper/ | grep -v observers/rich_console | grep -v cli
# Expected: zero matches (only RichConsoleObserver and CLI layer keep Console)

rg "self\.console" --type py personalscraper/pipeline.py
# Expected: zero matches

rg "console=MagicMock\(\)" --type py tests/
# Expected: zero matches (all migrated to observers=[CollectorObserver()])

rg "console=console" --type py personalscraper/commands/pipeline.py
# Expected: zero matches in the run command (single-step commands keep their own console)
```

## Gate (post-phase)

- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass
- [ ] `make check` — composite gate green
- [ ] `python3 scripts/check-module-size.py` — no module > 800 LOC advisory
- [ ] `python -c "import personalscraper"` — smoke
- [ ] `rg "self\.console" --type py personalscraper/pipeline.py` — zero matches
- [ ] `rg 'console=MagicMock\(\)' --type py tests/` — zero matches
- [ ] Commit: `chore(pipeline-obs): phase 9 gate — trailers + dispatch progress + final gate`

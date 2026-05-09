# Phase 7 — Step Integration: Process + Scrape

**Type**: steps
**Codename**: pipeline-obs

## NO DEFERRAL

Both steps fully adapted. No step is left for later.

## Gate (pre-phase)

- [x] Phase 6 complete — ingest + sort emit progress events

## Sub-phases

### Sub-phase 7.1 — Process progress

**Files:**

- Modify: `personalscraper/process/run.py`
- Modify: `personalscraper/pipeline_steps.py` (CleanStep, CleanupStep adapters)
- Create: `tests/unit/test_process_progress.py`

Add `observers` to `run_clean`, `run_cleanup`, and `run_process`:

```python
def run_clean(
    settings: Settings,
    *,
    dry_run: bool = False,
    config: Config | None = None,
    observers: tuple[PipelineObserver, ...] = (),
) -> StepReport:
```

Per-folder progress:

```python
for folder in movie_folders + tv_folders:
    notify_progress(observers, StepEvent(
        step="clean", item=str(folder.name), status="started",
    ))
    # ... clean ...
    if cleaned:
        notify_progress(observers, StepEvent(
            step="clean", item=str(folder.name), status="cleaned",
            details={"junk_removed": count},
        ))
    else:
        notify_progress(observers, StepEvent(
            step="clean", item=str(folder.name), status="skipped",
        ))
```

Same pattern for `run_cleanup` (step="cleanup", statuses: "started", "removed", "skipped").

Update adapters:

```python
class CleanStep:
    name = "clean"
    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.process.run import run_clean
        return run_clean(ctx.settings, dry_run=ctx.dry_run, config=ctx.config, observers=ctx.observers)

class CleanupStep:
    name = "cleanup"
    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.process.run import run_cleanup
        return run_cleanup(ctx.settings, dry_run=ctx.dry_run, config=ctx.config, observers=ctx.observers)
```

### Sub-phase 7.2 — Scrape progress

**Files:**

- Modify: `personalscraper/scraper/run.py`
- Modify: `personalscraper/pipeline_steps.py` (ScrapeStep adapter)
- Create: `tests/unit/test_scrape_progress.py`

Add `observers` to `run_scrape`:

```python
def run_scrape(
    settings: Settings,
    *,
    config: Config,
    dry_run: bool = False,
    interactive: bool = False,
    movies_only: bool = False,
    tvshows_only: bool = False,
    observers: tuple[PipelineObserver, ...] = (),
) -> StepReport:
```

Per-folder progress:

```python
for folder in folders:
    notify_progress(observers, StepEvent(
        step="scrape", item=str(folder.name), status="started",
    ))
    # ... scrape ...
    if matched:
        notify_progress(observers, StepEvent(
            step="scrape", item=str(folder.name), status="matched",
            details={"provider": provider, "confidence": confidence},
        ))
    elif low_confidence:
        notify_progress(observers, StepEvent(
            step="scrape", item=str(folder.name), status="skipped_low_confidence",
            details={"title": title, "year": year},
        ))
    elif errored:
        notify_progress(observers, StepEvent(
            step="scrape", item=str(folder.name), status="failed",
            details={"error": str(exc)},
        ))
```

Update adapter:

```python
class ScrapeStep:
    name = "scrape"
    def __call__(self, ctx: StepContext) -> StepReport:
        from personalscraper.scraper.run import run_scrape
        return run_scrape(
            ctx.settings, config=ctx.config,
            dry_run=ctx.dry_run, interactive=ctx.interactive,
            observers=ctx.observers,
        )
```

### Sub-phase 7.3 — Tests

**`tests/unit/test_process_progress.py`:**

```python
"""Tests for process progress events."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.process.run import run_clean, run_cleanup


class TestProcessProgress:
    def test_run_clean_accepts_observers(self):
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        config.categories = []

        with patch("personalscraper.process.run._collect_folders", return_value=[]):
            report = run_clean(settings, dry_run=True, config=config, observers=())
        assert report.name == "clean"

    def test_run_cleanup_accepts_observers(self):
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        config.categories = []

        with patch("personalscraper.process.run._collect_folders", return_value=[]):
            report = run_cleanup(settings, dry_run=True, config=config, observers=())
        assert report.name == "cleanup"
```

**`tests/unit/test_scrape_progress.py`:**

```python
"""Tests for scrape progress events."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.scraper.run import run_scrape


class TestScrapeProgress:
    def test_run_scrape_accepts_observers(self):
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        config.categories = []

        with patch("personalscraper.scraper.run._collect_folders", return_value=[]):
            report = run_scrape(
                settings, config=config, dry_run=True, observers=(),
            )
        assert report.name == "scrape"
```

## Gate (post-phase)

- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass
- [ ] `rg "console" personalscraper/process/run.py` — zero matches
- [ ] `rg "console" personalscraper/scraper/run.py` — zero matches
- [ ] Commit: `chore(pipeline-obs): phase 7 gate — process + scrape progress`

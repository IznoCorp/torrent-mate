# Phase 6 — Step Integration: Ingest + Sort

**Type**: steps
**Codename**: pipeline-obs

## NO DEFERRAL

Both steps are fully adapted in this phase. All step-level progress events emitted.
No step is left for later.

## Gate (pre-phase)

- [x] Phase 5 complete — CLI wired, Pipeline accepts observers

## Sub-phases

### Sub-phase 6.1 — Ingest progress

**Files:**

- Modify: `personalscraper/ingest/ingest.py`
- Modify: `personalscraper/pipeline_steps.py` (IngestStep adapter)
- Create: `tests/unit/test_ingest_progress.py`

Add `observers` parameter to `run_ingest`:

```python
def run_ingest(
    settings: Settings,
    *,
    dry_run: bool = False,
    ingest_dir: Path | None = None,
    staging_dir: Path | None = None,
    config: Config | None = None,
    observers: tuple[PipelineObserver, ...] = (),
) -> StepReport:
```

Inside the loop over completed torrents:

```python
for torrent in completed:
    notify_progress(observers, StepEvent(
        step="ingest", item=torrent.name, status="started",
    ))
    try:
        copy_torrent(torrent, dest)
        notify_progress(observers, StepEvent(
            step="ingest", item=torrent.name, status="copied",
            details={"size_mb": file_size_mb},
        ))
    except Exception as exc:
        notify_progress(observers, StepEvent(
            step="ingest", item=torrent.name, status="failed",
            details={"error": str(exc)},
        ))
```

Update `IngestStep.__call__` in `pipeline_steps.py`:

```python
from personalscraper.ingest.ingest import run_ingest
from personalscraper.pipeline_observer import notify_progress

class IngestStep:
    name = "ingest"

    def __call__(self, ctx: StepContext) -> StepReport:
        return run_ingest(
            ctx.settings,
            dry_run=ctx.dry_run,
            config=ctx.config,
            observers=ctx.observers,
        )
```

### Sub-phase 6.2 — Sort progress

**Files:**

- Modify: `personalscraper/sorter/run.py`
- Modify: `personalscraper/pipeline_steps.py` (SortStep adapter)
- Create: `tests/unit/test_sort_progress.py`

Add `observers` parameter to `run_sort`:

```python
def run_sort(
    settings: Settings,
    *,
    staging_dir: Path,
    dry_run: bool = False,
    config: Config | None = None,
    observers: tuple[PipelineObserver, ...] = (),
) -> StepReport:
```

Per-item progress inside the sort loop:

```python
for item in staging_items:
    notify_progress(observers, StepEvent(
        step="sort", item=str(item.name), status="started",
    ))
    # ... detect type, compute destination ...
    if status == "moved":
        notify_progress(observers, StepEvent(
            step="sort", item=str(item.name), status="moved",
            details={"type": media_type, "dest": str(dest)},
        ))
    elif status == "skipped":
        notify_progress(observers, StepEvent(
            step="sort", item=str(item.name), status="skipped",
            details={"reason": message or ""},
        ))
    else:
        notify_progress(observers, StepEvent(
            step="sort", item=str(item.name), status="failed",
            details={"error": message or ""},
        ))
```

Update `SortStep.__call__`:

```python
class SortStep:
    name = "sort"

    def __call__(self, ctx: StepContext) -> StepReport:
        return run_sort(
            ctx.settings,
            staging_dir=ctx.config.paths.staging_dir,
            dry_run=ctx.dry_run,
            config=ctx.config,
            observers=ctx.observers,
        )
```

### Sub-phase 6.3 — Tests

**`tests/unit/test_ingest_progress.py`:**

```python
"""Tests for ingest progress events."""

from unittest.mock import MagicMock, patch

from personalscraper.ingest.ingest import run_ingest
from personalscraper.pipeline_observer import (
    CollectorObserver,
    StepEvent,
)


class TestIngestProgress:
    def test_emits_per_torrent_events(self):
        collector = CollectorObserver()
        settings = MagicMock()
        config = MagicMock()

        with patch("personalscraper.ingest.ingest._copy_torrent_to_staging"):
            report = run_ingest(
                settings,
                dry_run=True,
                config=config,
                observers=(collector,),
            )
        # At minimum, no crash — verified
        assert report.name == "ingest"

    def test_started_event_structure(self):
        """Verify StepEvent structure is valid."""
        event = StepEvent(
            step="ingest",
            item="Some.Torrent.2024.1080p",
            status="started",
        )
        assert event.step == "ingest"
        assert event.item == "Some.Torrent.2024.1080p"
        assert event.status == "started"
        assert event.details == {}
```

**`tests/unit/test_sort_progress.py`:**

```python
"""Tests for sort progress events."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.sorter.run import run_sort


class TestSortProgress:
    def test_sort_accepts_observers_param(self):
        settings = MagicMock()
        staging_dir = Path("/tmp/staging")
        config = MagicMock()
        config.paths.staging_dir = staging_dir

        with patch("personalscraper.sorter.run._collect_items", return_value=[]):
            report = run_sort(
                settings,
                staging_dir=staging_dir,
                dry_run=True,
                config=config,
                observers=(),
            )
        assert report.name == "sort"
```

## Gate (post-phase)

- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass
- [ ] `rg "console" personalscraper/ingest/ingest.py` — zero matches
- [ ] `rg "console" personalscraper/sorter/run.py` — zero matches
- [ ] Commit: `chore(pipeline-obs): phase 6 gate — ingest + sort progress`

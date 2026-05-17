# Phase 1 — Protocol Foundation

**Type**: core
**Codename**: pipeline-obs

## NO DEFERRAL

Every sub-phase in this phase is fully implemented. No placeholders, no "to be done
later", no skipped tests.

## Gate (pre-phase)

- [x] On branch `feat/pipeline-obs`
- [x] IMPLEMENTATION.md header populated
- [x] DESIGN.md at `docs/features/pipeline-obs/DESIGN.md`

## Sub-phases

### Sub-phase 1.1 — PipelineObserver Protocol + StepEvent + helpers

**Files:**

- Create: `personalscraper/pipeline_observer.py`
- Create: `tests/unit/test_pipeline_observer.py`

**`personalscraper/pipeline_observer.py`:**

```python
"""Pipeline observer protocol and associated types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from personalscraper.models import PipelineReport, StepReport


@runtime_checkable
class PipelineObserver(Protocol):
    """Observer contract for pipeline lifecycle and per-item progress.

    Observers receive typed notifications at every pipeline boundary.
    Implement this Protocol to add custom behaviour (console output,
    Telegram notifications, WebSocket streaming, metrics collection)
    without modifying the pipeline core.
    """

    name: str

    def on_pipeline_start(self, report: PipelineReport) -> None: ...
    def on_pipeline_end(self, report: PipelineReport) -> None: ...
    def on_step_start(self, step: str) -> None: ...
    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None: ...
    def on_step_error(self, step: str, error: Exception) -> None: ...
    def on_progress(self, event: StepEvent) -> None: ...


class PipelineObserverBase:
    """No-op base class for observers that only implement a subset of callbacks.

    Inherit from this class and override only the methods you need.
    """

    name = "base"

    def on_pipeline_start(self, report: PipelineReport) -> None:
        pass

    def on_pipeline_end(self, report: PipelineReport) -> None:
        pass

    def on_step_start(self, step: str) -> None:
        pass

    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None:
        pass

    def on_step_error(self, step: str, error: Exception) -> None:
        pass

    def on_progress(self, event: StepEvent) -> None:
        pass


@dataclass(frozen=True)
class StepEvent:
    """Per-item progress event emitted by pipeline steps.

    Frozen (immutable) — events are fire-and-forget snapshots.

    Attributes:
        step: Step identifier ("ingest", "sort", "scrape", …).
        item: Human-readable item identifier (filename, folder name).
        status: Event status ("started", "completed", "skipped", "failed").
        details: Optional structured payload (provider, confidence, size_mb, …).
    """

    step: str
    item: str
    status: str
    details: dict[str, object] = field(default_factory=dict)


def notify_progress(
    observers: tuple[PipelineObserver, ...],
    event: StepEvent,
) -> None:
    """Call ``on_progress`` on every observer.

    Survives individual observer failures — one broken observer must not
    crash the pipeline.

    Args:
        observers: Tuple of observers to notify.
        event: The progress event to emit.
    """
    for obs in observers:
        try:
            obs.on_progress(event)
        except Exception:
            pass


__all__ = [
    "PipelineObserver",
    "PipelineObserverBase",
    "StepEvent",
    "notify_progress",
]
```

### Sub-phase 1.2 — Tests

**`tests/unit/test_pipeline_observer.py`:**

```python
"""Tests for the PipelineObserver protocol and associated types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

import pytest

from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline_observer import (
    PipelineObserver,
    PipelineObserverBase,
    StepEvent,
    notify_progress,
)


class TestPipelineObserverProtocol:
    """Protocol structural subtyping tests."""

    def test_runtime_checkable_valid_implementation(self):
        """A class implementing all 6 methods is recognised as PipelineObserver."""

        class ValidObserver:
            name = "valid"

            def on_pipeline_start(self, report): ...
            def on_pipeline_end(self, report): ...
            def on_step_start(self, step): ...
            def on_step_end(self, step, report, elapsed): ...
            def on_step_error(self, step, error): ...
            def on_progress(self, event): ...

        assert isinstance(ValidObserver(), PipelineObserver)

    def test_runtime_checkable_missing_name(self):
        """A class missing the ``name`` attribute is NOT a PipelineObserver."""

        class NoNameObserver:
            def on_pipeline_start(self, report): ...
            def on_pipeline_end(self, report): ...
            def on_step_start(self, step): ...
            def on_step_end(self, step, report, elapsed): ...
            def on_step_error(self, step, error): ...
            def on_progress(self, event): ...

        assert not isinstance(NoNameObserver(), PipelineObserver)

    def test_runtime_checkable_missing_method_is_not_observer(self):
        """Structural subtyping requires ALL methods to be present."""

        class PartialObserver:
            name = "partial"

            def on_pipeline_start(self, report): ...

        assert not isinstance(PartialObserver(), PipelineObserver)

    def test_pipeline_observer_base_is_observer(self):
        """PipelineObserverBase satisfies the Protocol structurally."""
        assert isinstance(PipelineObserverBase(), PipelineObserver)


class TestPipelineObserverBase:
    """No-op base class tests."""

    def test_all_methods_noop(self):
        """All 6 methods are callable and return None without side effects."""
        base = PipelineObserverBase()
        dummy_report = PipelineReport(started_at=MagicMock())
        dummy_step = StepReport(name="test")

        assert base.on_pipeline_start(dummy_report) is None
        assert base.on_pipeline_end(dummy_report) is None
        assert base.on_step_start("ingest") is None
        assert base.on_step_end("ingest", dummy_step, 1.5) is None
        assert base.on_step_error("ingest", ValueError("oops")) is None
        assert base.on_progress(StepEvent(step="ingest", item="x", status="ok")) is None

    def test_name_attr(self):
        """The base class provides a default name."""
        assert PipelineObserverBase().name == "base"


class TestStepEvent:
    """StepEvent dataclass tests."""

    def test_minimal_construction(self):
        """Only step, item, status are required."""
        event = StepEvent(step="sort", item="Inception.2010.mkv", status="moved")
        assert event.step == "sort"
        assert event.item == "Inception.2010.mkv"
        assert event.status == "moved"
        assert event.details == {}

    def test_with_details(self):
        """Details dict carries structured payload."""
        event = StepEvent(
            step="scrape",
            item="Inception (2010)",
            status="matched",
            details={"provider": "tmdb", "tmdb_id": 27205, "confidence": 96},
        )
        assert event.details["tmdb_id"] == 27205

    def test_frozen(self):
        """StepEvent is immutable."""
        event = StepEvent(step="ingest", item="x", status="ok")
        with pytest.raises(FrozenInstanceError):
            event.step = "sort"  # type: ignore[misc]

    def test_defaults(self):
        """details defaults to empty dict."""
        event = StepEvent(step="clean", item="folder", status="cleaned")
        assert event.details == {}
        assert isinstance(event.details, dict)


class TestNotifyProgress:
    """notify_progress helper tests."""

    def test_calls_on_progress_on_every_observer(self):
        """Each observer's on_progress is called with the event."""
        obs1 = MagicMock(spec=PipelineObserver)
        obs2 = MagicMock(spec=PipelineObserver)
        event = StepEvent(step="sort", item="a.mkv", status="moved")

        notify_progress((obs1, obs2), event)

        obs1.on_progress.assert_called_once_with(event)
        obs2.on_progress.assert_called_once_with(event)

    def test_survives_observer_exception(self):
        """One crashing observer does not prevent the next from being called."""
        obs1 = MagicMock(spec=PipelineObserver)
        obs1.on_progress.side_effect = RuntimeError("boom")
        obs2 = MagicMock(spec=PipelineObserver)
        event = StepEvent(step="sort", item="a.mkv", status="moved")

        notify_progress((obs1, obs2), event)

        obs2.on_progress.assert_called_once_with(event)

    def test_no_observers_noop(self):
        """Empty tuple does nothing."""
        notify_progress((), StepEvent(step="x", item="y", status="z"))
```

## Gate (post-phase)

- [ ] `make lint` — zero errors
- [ ] `make test` — all tests pass including new ones
- [ ] `python -c "import personalscraper"` — smoke
- [ ] `rg "from rich.console import Console" personalscraper/pipeline_observer.py` — zero matches
- [ ] Commit: `feat(pipeline-obs): add PipelineObserver protocol, StepEvent, notify_progress`

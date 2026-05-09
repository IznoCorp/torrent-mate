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

    def test_runtime_checkable_valid_implementation(self) -> None:
        """A class implementing all 6 methods is recognised as PipelineObserver."""

        class ValidObserver:
            name = "valid"

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

        assert isinstance(ValidObserver(), PipelineObserver)

    def test_runtime_checkable_missing_name(self) -> None:
        """A class missing the ``name`` attribute is NOT a PipelineObserver."""

        class NoNameObserver:
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

        assert not isinstance(NoNameObserver(), PipelineObserver)

    def test_runtime_checkable_missing_method_is_not_observer(self) -> None:
        """Structural subtyping requires ALL methods to be present."""

        class PartialObserver:
            name = "partial"

            def on_pipeline_start(self, report: PipelineReport) -> None:
                pass

        assert not isinstance(PartialObserver(), PipelineObserver)

    def test_pipeline_observer_base_is_observer(self) -> None:
        """PipelineObserverBase satisfies the Protocol structurally."""
        assert isinstance(PipelineObserverBase(), PipelineObserver)


class TestPipelineObserverBase:
    """No-op base class tests."""

    def test_all_methods_noop(self) -> None:
        """All 6 methods are callable and return None without side effects."""
        base = PipelineObserverBase()
        dummy_report = PipelineReport(started_at=MagicMock())
        dummy_step = StepReport(name="test")

        # All methods return None (no-op) — verify they don't raise.
        base.on_pipeline_start(dummy_report)
        base.on_pipeline_end(dummy_report)
        base.on_step_start("ingest")
        base.on_step_end("ingest", dummy_step, 1.5)
        base.on_step_error("ingest", ValueError("oops"))
        base.on_progress(StepEvent(step="ingest", item="x", status="ok"))
        # No assert — the test passes if no exception is raised.

    def test_name_attr(self) -> None:
        """The base class provides a default name."""
        assert PipelineObserverBase().name == "base"


class TestStepEvent:
    """StepEvent dataclass tests."""

    def test_minimal_construction(self) -> None:
        """Only step, item, status are required."""
        event = StepEvent(step="sort", item="Inception.2010.mkv", status="moved")
        assert event.step == "sort"
        assert event.item == "Inception.2010.mkv"
        assert event.status == "moved"
        assert event.details == {}

    def test_with_details(self) -> None:
        """Details dict carries structured payload."""
        event = StepEvent(
            step="scrape",
            item="Inception (2010)",
            status="matched",
            details={"provider": "tmdb", "tmdb_id": 27205, "confidence": 96},
        )
        assert event.details["tmdb_id"] == 27205

    def test_frozen(self) -> None:
        """StepEvent is immutable."""
        event = StepEvent(step="ingest", item="x", status="ok")
        with pytest.raises(FrozenInstanceError):
            event.step = "sort"  # type: ignore[misc]

    def test_defaults(self) -> None:
        """Details defaults to empty dict."""
        event = StepEvent(step="clean", item="folder", status="cleaned")
        assert event.details == {}
        assert isinstance(event.details, dict)


class TestNotifyProgress:
    """notify_progress helper tests."""

    def test_calls_on_progress_on_every_observer(self) -> None:
        """Each observer's on_progress is called with the event."""
        obs1 = MagicMock(spec=PipelineObserver)
        obs2 = MagicMock(spec=PipelineObserver)
        event = StepEvent(step="sort", item="a.mkv", status="moved")

        notify_progress((obs1, obs2), event)

        obs1.on_progress.assert_called_once_with(event)
        obs2.on_progress.assert_called_once_with(event)

    def test_survives_observer_exception(self) -> None:
        """One crashing observer does not prevent the next from being called."""
        obs1 = MagicMock(spec=PipelineObserver)
        obs1.on_progress.side_effect = RuntimeError("boom")
        obs2 = MagicMock(spec=PipelineObserver)
        event = StepEvent(step="sort", item="a.mkv", status="moved")

        notify_progress((obs1, obs2), event)

        obs2.on_progress.assert_called_once_with(event)

    def test_no_observers_noop(self) -> None:
        """Empty tuple does nothing."""
        notify_progress((), StepEvent(step="x", item="y", status="z"))

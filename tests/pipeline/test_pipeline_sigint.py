"""``Pipeline`` honors operator-requested shutdown at step boundaries.

Sub-phase 4.2 of the tech-debt feature adds a SIGINT / programmatic
shutdown signal that is honored AT STEP BOUNDARIES — the current step
completes its atomic unit, then the pipeline aborts before the next
step. ``PipelineEnded`` is still emitted so subscribers always see a
clean lifecycle pair.

The contract under test:

- :meth:`Pipeline.request_shutdown` sets a flag, never blocks, never
  interrupts mid-step.
- After the flag is set, the very next call to ``_run_step`` raises
  :class:`_PipelineInterrupted` BEFORE emitting ``StepStarted``, so the
  bus never sees a half-started step.
- ``PipelineEnded`` is emitted in the finally branch even on interrupt.
- The SIGINT handler installed at run start is restored after run end
  (including on interrupt).
- ``dry_run=True`` does NOT install a SIGINT handler — dry runs are
  observational and must not mutate process-wide signal state.
"""

from __future__ import annotations

import signal
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline, _PipelineInterrupted
from personalscraper.pipeline_events import (
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepStarted,
)
from personalscraper.pipeline_protocol import StepContext
from tests.fixtures.event_bus import CollectingSubscriber


def _stub_app() -> AppContext:
    """Minimal :class:`AppContext` with a real :class:`EventBus`."""
    config = MagicMock()
    config.disks = []
    config.paths.staging_dir = MagicMock()
    ingest_entry = MagicMock()
    ingest_entry.id = 97
    ingest_entry.role = "ingest"
    config.staging_dirs = [ingest_entry]
    config.paths.data_dir = Path(tempfile.mkdtemp())  # real empty dir: PauseController reads data_dir/'pipeline.pause'
    settings = MagicMock()
    return AppContext(
        config=config,
        settings=settings,
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
    )


class _NoOpStep:
    """PipelineStep stub returning a clean :class:`StepReport`.

    When ``shutdown_after=True``, calls :meth:`Pipeline.request_shutdown`
    inside the step body so the very next ``_run_step`` honors the flag.
    """

    def __init__(self, name: str, *, pipeline: Pipeline | None = None, shutdown_after: bool = False) -> None:
        self.name = name
        self._pipeline = pipeline
        self._shutdown_after = shutdown_after

    def __call__(self, ctx: StepContext) -> StepReport | tuple[StepReport, list[Any]]:
        report = StepReport(name=self.name, success_count=1)
        if self._shutdown_after and self._pipeline is not None:
            self._pipeline.request_shutdown(reason=f"test_after_{self.name}")
        if self.name == "verify":
            return report, []
        return report


def _step_registry(pipeline: Pipeline, shutdown_after_step: str | None = None) -> dict[str, _NoOpStep]:
    """Build a full no-op registry. Optionally one step triggers a shutdown."""
    return {
        name: _NoOpStep(
            name,
            pipeline=pipeline,
            shutdown_after=(name == shutdown_after_step),
        )
        for name in (
            "ingest",
            "sort",
            "clean",
            "scrape",
            "cleanup",
            "enforce",
            "verify",
            "trailers",
            "dispatch",
        )
    }


def _run_pipeline(pipeline: Pipeline, registry: dict[str, _NoOpStep], *, dry_run: bool = False) -> None:
    """Run ``pipeline`` with the stub registry, isolated from disk I/O."""
    with (
        patch("personalscraper.pipeline.ensure_staging_tree"),
        patch.object(Pipeline, "_check_temp_empty_gate"),
        patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
        patch("personalscraper.pipeline.apply_step_overrides", return_value=registry),
    ):
        pipeline.run(dry_run=dry_run)


class TestRequestShutdownSignalsFlag:
    """:meth:`request_shutdown` mutates the shutdown flag — no side effects."""

    def test_request_shutdown_sets_flag(self) -> None:
        """The public API sets the boolean flag and records the reason."""
        pipeline = Pipeline(_stub_app())
        assert pipeline._shutdown_requested is False
        pipeline.request_shutdown(reason="test_unit")
        assert pipeline._shutdown_requested is True
        assert pipeline._shutdown_reason == "test_unit"

    def test_request_shutdown_default_reason(self) -> None:
        """Default reason is ``"external_request"`` when none is given."""
        pipeline = Pipeline(_stub_app())
        pipeline.request_shutdown()
        assert pipeline._shutdown_reason == "external_request"

    def test_check_raises_when_flag_set(self) -> None:
        """:meth:`_check_shutdown_requested` raises only when the flag is set."""
        pipeline = Pipeline(_stub_app())
        pipeline._check_shutdown_requested(boundary="before_ingest")
        pipeline.request_shutdown(reason="boom")
        with pytest.raises(_PipelineInterrupted, match="boom"):
            pipeline._check_shutdown_requested(boundary="before_sort")


class TestShutdownHonoredAtStepBoundary:
    """Shutdown signalled mid-pipeline aborts at the next step boundary."""

    def test_shutdown_after_ingest_skips_remaining_steps(self) -> None:
        """If shutdown is set after ingest, sort and downstream never run."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, StepStarted) as started_sub:
            _run_pipeline(pipeline, _step_registry(pipeline, shutdown_after_step="ingest"))
        started_steps = [event.step for event in started_sub.received]
        # Only ingest's StepStarted was emitted; sort and downstream never
        # produced a bus event because the boundary check raises before emit.
        assert started_steps == ["ingest"]

    def test_shutdown_after_scrape_runs_only_through_scrape(self) -> None:
        """Shutdown after a mid-pipeline step preserves all earlier emits."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, StepStarted) as started_sub:
            _run_pipeline(pipeline, _step_registry(pipeline, shutdown_after_step="scrape"))
        started_steps = [event.step for event in started_sub.received]
        assert started_steps == ["ingest", "sort", "clean", "scrape"]


class TestPipelineEndedAlwaysEmittedOnInterrupt:
    """``PipelineEnded`` is emitted even when the run is interrupted."""

    def test_pipeline_ended_emitted_after_interrupt(self) -> None:
        """An interrupted run still produces exactly one ``PipelineEnded``."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, PipelineEnded) as ended_sub:
            _run_pipeline(pipeline, _step_registry(pipeline, shutdown_after_step="ingest"))
        assert len(ended_sub.received) == 1

    def test_pipeline_started_and_ended_pair_on_interrupt(self) -> None:
        """Both lifecycle events fire even on interrupt — clean pair."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with (
            CollectingSubscriber(app.event_bus, PipelineStarted) as started_sub,
            CollectingSubscriber(app.event_bus, PipelineEnded) as ended_sub,
        ):
            _run_pipeline(pipeline, _step_registry(pipeline, shutdown_after_step="ingest"))
        assert len(started_sub.received) == 1
        assert len(ended_sub.received) == 1

    def test_no_step_completed_for_interrupted_boundary(self) -> None:
        """The interrupted step never emits a ``StepCompleted`` event.

        The boundary check raises BEFORE the StepStarted emit, so the bus
        never sees an asymmetric started-without-completed pair for the
        interrupted step.
        """
        app = _stub_app()
        pipeline = Pipeline(app)
        with (
            CollectingSubscriber(app.event_bus, StepStarted) as started_sub,
            CollectingSubscriber(app.event_bus, StepCompleted) as completed_sub,
        ):
            _run_pipeline(pipeline, _step_registry(pipeline, shutdown_after_step="ingest"))
        # Every step that emitted StepStarted also emitted StepCompleted.
        started_steps = sorted(event.step for event in started_sub.received)
        completed_steps = sorted(event.step for event in completed_sub.received)
        assert started_steps == completed_steps


class TestSigintHandlerLifecycle:
    """SIGINT install / restore semantics around ``run``."""

    def test_handler_restored_after_clean_run(self) -> None:
        """After a clean run, the previous SIGINT handler is back in place."""
        sentinel_called: list[bool] = []

        def previous_handler(signum: int, frame: Any) -> None:
            sentinel_called.append(True)

        original = signal.signal(signal.SIGINT, previous_handler)
        try:
            app = _stub_app()
            pipeline = Pipeline(app)
            _run_pipeline(pipeline, _step_registry(pipeline))
            # After run, the handler must be back to the sentinel we set.
            current = signal.getsignal(signal.SIGINT)
            assert current is previous_handler
        finally:
            signal.signal(signal.SIGINT, original)

    def test_handler_restored_after_interrupted_run(self) -> None:
        """Even on interrupt, the previous handler is restored."""

        def previous_handler(signum: int, frame: Any) -> None:
            pass

        original = signal.signal(signal.SIGINT, previous_handler)
        try:
            app = _stub_app()
            pipeline = Pipeline(app)
            _run_pipeline(pipeline, _step_registry(pipeline, shutdown_after_step="ingest"))
            current = signal.getsignal(signal.SIGINT)
            assert current is previous_handler
        finally:
            signal.signal(signal.SIGINT, original)

    def test_dry_run_does_not_install_handler(self) -> None:
        """``dry_run=True`` is observational — process-wide signal state untouched."""

        def previous_handler(signum: int, frame: Any) -> None:
            pass

        original = signal.signal(signal.SIGINT, previous_handler)
        try:
            app = _stub_app()
            pipeline = Pipeline(app)
            _run_pipeline(pipeline, _step_registry(pipeline), dry_run=True)
            # The handler we installed is still in place — pipeline.run(dry_run=True)
            # never touched it.
            current = signal.getsignal(signal.SIGINT)
            assert current is previous_handler
        finally:
            signal.signal(signal.SIGINT, original)

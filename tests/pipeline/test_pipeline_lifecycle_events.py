"""``Pipeline.run`` emits ``PipelineStarted`` and ``PipelineEnded``.

The bus is the sole emit substrate. This module locks the emit contract:

- Exactly one ``PipelineStarted`` per run, before the first step.
- Exactly one ``PipelineEnded`` per run, even when a step raises.
- The events carry the live ``PipelineReport`` reference.
- ``correlation_id`` equals ``str(pipeline._run_id)`` for both events.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline
from personalscraper.pipeline_events import (
    PipelineEnded,
    PipelineStarted,
    StepCompleted,
    StepErrored,
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
    config.paths.data_dir = MagicMock()
    settings = MagicMock()
    return AppContext(
        config=config,
        settings=settings,
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
    )


class _NoOpStep:
    """PipelineStep stub that always returns a clean :class:`StepReport`.

    Implements the structural ``PipelineStep`` protocol so the registry can
    be substituted directly via ``apply_step_overrides`` patching.
    """

    def __init__(self, name: str, *, raises: bool = False) -> None:
        self.name = name
        self._raises = raises

    def __call__(self, ctx: StepContext) -> StepReport | tuple[StepReport, list[Any]]:
        if self._raises:
            raise RuntimeError(f"boom in {self.name}")
        if self.name == "verify":
            return StepReport(name=self.name, success_count=1), []
        return StepReport(name=self.name, success_count=1)


def _step_registry(*, raise_on: str | None = None) -> dict[str, _NoOpStep]:
    """Build a full no-op registry; optionally one step raises."""
    return {
        name: _NoOpStep(name, raises=(name == raise_on))
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


def _run_pipeline(pipeline: Pipeline, registry: dict[str, _NoOpStep]) -> None:
    """Run ``pipeline`` with the stub registry, isolated from disk I/O."""
    with (
        patch("personalscraper.pipeline.ensure_staging_tree"),
        patch.object(Pipeline, "_check_temp_empty_gate"),
        patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
        patch("personalscraper.pipeline.apply_step_overrides", return_value=registry),
    ):
        pipeline.run()


class TestPipelineStartedEmit:
    """``Pipeline.run`` emits exactly one ``PipelineStarted`` per call."""

    def test_pipeline_emits_started_before_first_step(self) -> None:
        """A no-op pipeline run records exactly one ``PipelineStarted`` event."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, PipelineStarted) as sub:
            _run_pipeline(pipeline, _step_registry())
        assert len(sub.received) == 1

    def test_pipeline_started_carries_live_report(self) -> None:
        """The emitted ``PipelineStarted.report`` is the run's :class:`PipelineReport`."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, PipelineStarted) as sub:
            _run_pipeline(pipeline, _step_registry())
        event = sub.received[0]
        assert isinstance(event, PipelineStarted)
        assert event.report.started_at is not None

    def test_pipeline_started_carries_correlation_id(self) -> None:
        """The emitted event's ``correlation_id`` mirrors the bound ``run_id``."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, PipelineStarted) as sub:
            _run_pipeline(pipeline, _step_registry())
        event = sub.received[0]
        assert event.correlation_id == str(pipeline._run_id)


class TestPipelineEndedEmit:
    """``Pipeline.run`` emits exactly one ``PipelineEnded`` per call (success & failure)."""

    def test_pipeline_emits_ended_after_last_step(self) -> None:
        """A no-op run records exactly one ``PipelineEnded`` after every step finishes."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, PipelineEnded) as sub:
            _run_pipeline(pipeline, _step_registry())
        assert len(sub.received) == 1
        event = sub.received[0]
        assert event.report.started_at <= event.report.finished_at  # type: ignore[operator]

    def test_pipeline_emits_ended_even_when_step_raises(self) -> None:
        """A crashing step does not suppress the ``PipelineEnded`` emit."""
        app = _stub_app()
        pipeline = Pipeline(app)
        # The trailers step is non-critical so its failure does not propagate;
        # the dispatch step is non-critical too. Use a non-pipeline-critical
        # step that does propagate: pick ``ingest`` (marked critical=True in
        # Pipeline.run, raises ``_CriticalStepError`` which is caught and the
        # pipeline returns early). The finally block still runs, so the emit
        # MUST fire either way.
        registry = _step_registry(raise_on="ingest")
        with CollectingSubscriber(app.event_bus, PipelineEnded) as sub:
            _run_pipeline(pipeline, registry)
        assert len(sub.received) == 1

    def test_pipeline_ended_correlation_id_matches_run_id(self) -> None:
        """The ``PipelineEnded.correlation_id`` mirrors the same ``run_id`` as Started."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with (
            CollectingSubscriber(app.event_bus, PipelineStarted) as started,
            CollectingSubscriber(app.event_bus, PipelineEnded) as ended,
        ):
            _run_pipeline(pipeline, _step_registry())
        assert started.received[0].correlation_id == ended.received[0].correlation_id
        assert ended.received[0].correlation_id == str(pipeline._run_id)


class TestPipelineEmitOrdering:
    """``PipelineStarted`` precedes ``PipelineEnded`` across all subscribers."""

    def test_started_precedes_ended(self) -> None:
        """A single base-class collector records Started before Ended."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, Event) as sub:
            _run_pipeline(pipeline, _step_registry())
        started_indices = [i for i, e in enumerate(sub.received) if isinstance(e, PipelineStarted)]
        ended_indices = [i for i, e in enumerate(sub.received) if isinstance(e, PipelineEnded)]
        assert started_indices and ended_indices
        assert started_indices[0] < ended_indices[0]


class TestPipelineEndedEmitDefensive:
    """An emit-side failure must NOT block ``current_correlation_id.reset``."""

    def test_pipeline_ended_emit_failure_is_logged_and_does_not_propagate(self) -> None:
        """A bus.emit that raises is caught; the ContextVar still resets cleanly."""
        app = _stub_app()
        pipeline = Pipeline(app)

        # Patch the bus emit to raise ONLY for PipelineEnded.
        original_emit = app.event_bus.emit

        def _emit(event: Event) -> None:
            if isinstance(event, PipelineEnded):
                raise RuntimeError("synthetic emit failure")
            original_emit(event)

        with patch.object(app.event_bus, "emit", side_effect=_emit):
            # The run must complete cleanly despite the failing emit; the
            # ContextVar reset MUST still happen so a follow-up emit shows
            # ``correlation_id=None`` outside the bound region.
            _run_pipeline(pipeline, _step_registry())

        # After the run, the bound ContextVar must be reset to its default.
        from personalscraper.core.event_bus import current_correlation_id

        assert current_correlation_id.get() is None

    def test_pre_emit_setup_failure_does_not_leak_correlation_id(self) -> None:
        """``ensure_staging_tree`` raising must NOT leak ``current_correlation_id``.

        Regression test for the pre-fix ``Pipeline.run`` shape where
        ``current_correlation_id.set(...)`` ran BEFORE the ``try:`` block.
        Any exception from ``ensure_staging_tree`` / ``PipelineReport()`` /
        ``PipelineStarted`` construction / the initial emit would propagate
        out of ``run`` without ever hitting the ``finally`` that resets the
        token — leaking the binding into the calling task.
        """
        from personalscraper.core.event_bus import current_correlation_id

        app = _stub_app()
        pipeline = Pipeline(app)

        # Make ``ensure_staging_tree`` raise — the very first call inside
        # the new ``try:`` body. The exception must propagate to the caller
        # (no swallowing), AND the ContextVar must be back to ``None``.
        with (
            patch(
                "personalscraper.pipeline.ensure_staging_tree",
                side_effect=RuntimeError("synthetic setup failure"),
            ),
            pytest.raises(RuntimeError, match="synthetic setup failure"),
        ):
            pipeline.run()

        assert current_correlation_id.get() is None


@pytest.mark.parametrize("event_cls", [PipelineStarted, PipelineEnded])
def test_pipeline_events_are_distinct_per_run(event_cls: type[Event]) -> None:
    """Two consecutive ``run`` calls produce two distinct events of each type."""
    app = _stub_app()
    pipeline = Pipeline(app)
    with CollectingSubscriber(app.event_bus, event_cls) as sub:
        _run_pipeline(pipeline, _step_registry())
        _run_pipeline(pipeline, _step_registry())
    assert len(sub.received) == 2
    assert sub.received[0].event_id != sub.received[1].event_id


# ---------------------------------------------------------------------------
# Sub-phase 3.3 — per-step lifecycle emits.
# ---------------------------------------------------------------------------

# The pipeline emits StepStarted on entry, StepCompleted on success, and
# StepErrored on exception INSIDE :meth:`_run_step`. The PROCESS phase
# (clean / scrape / cleanup) and TRAILERS / DISPATCH all go through
# ``_run_step`` so the count of step events tracks the number of step
# invocations. The "skipped dispatch" branch (when no items pass verify)
# also emits StepStarted + StepCompleted explicitly to keep the contract
# symmetric — verified in TestStepDispatchSkipPath.

EXPECTED_STEP_NAMES: tuple[str, ...] = (
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


class TestStepStartedEmit:
    """``Pipeline._run_step`` emits ``StepStarted`` before each step body."""

    def test_one_step_started_per_step_in_step_order(self) -> None:
        """A 9-step no-op run emits 9 ``StepStarted`` events in pipeline order."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, StepStarted) as sub:
            _run_pipeline(pipeline, _step_registry())
        names = [event.step for event in sub.received]
        assert names == list(EXPECTED_STEP_NAMES)


class TestStepCompletedEmit:
    """``Pipeline._run_step`` emits ``StepCompleted`` after each successful step."""

    def test_one_step_completed_per_successful_step(self) -> None:
        """All 9 steps succeed → 9 ``StepCompleted`` events with non-negative elapsed_s."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, StepCompleted) as sub:
            _run_pipeline(pipeline, _step_registry())
        names = [event.step for event in sub.received]
        assert names == list(EXPECTED_STEP_NAMES)
        for event in sub.received:
            assert event.elapsed_s >= 0.0
            assert event.report.name == event.step

    def test_step_completed_carries_step_report_with_counts(self) -> None:
        """Each ``StepCompleted.report`` is a live :class:`StepReport` whose name matches the step.

        Non-dispatch steps return ``success_count=1`` (stub contract); the
        ``dispatch`` step in the no-verified-items branch synthesizes a
        report with ``skip_count=1`` instead. Both are valid.
        """
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, StepCompleted) as sub:
            _run_pipeline(pipeline, _step_registry())
        for event in sub.received:
            assert event.report.name == event.step
            assert event.report.success_count + event.report.skip_count >= 1


class TestStepErroredEmit:
    """``Pipeline._run_step`` emits ``StepErrored`` when the step body raises."""

    def test_step_errored_on_step_exception(self) -> None:
        """A raising step produces exactly one ``StepErrored`` carrying the exception info."""
        app = _stub_app()
        pipeline = Pipeline(app)
        registry = _step_registry(raise_on="scrape")
        with CollectingSubscriber(app.event_bus, StepErrored) as sub:
            _run_pipeline(pipeline, registry)
        assert len(sub.received) == 1
        event = sub.received[0]
        assert event.step == "scrape"
        assert event.error_class == "RuntimeError"
        assert event.error_message == "boom in scrape"

    def test_step_errored_no_completed_for_same_step(self) -> None:
        """A crashing step emits ``StepErrored`` but NOT ``StepCompleted`` for that step."""
        app = _stub_app()
        pipeline = Pipeline(app)
        registry = _step_registry(raise_on="scrape")
        with (
            CollectingSubscriber(app.event_bus, StepErrored) as errored,
            CollectingSubscriber(app.event_bus, StepCompleted) as completed,
        ):
            _run_pipeline(pipeline, registry)
        # Scrape errors → no StepCompleted for scrape.
        completed_steps = {event.step for event in completed.received}
        assert "scrape" not in completed_steps
        # And exactly one StepErrored is recorded for scrape.
        assert [event.step for event in errored.received] == ["scrape"]


class TestStepLifecycleOrdering:
    """``StepStarted`` precedes ``StepCompleted`` / ``StepErrored`` for the same step."""

    def test_lifecycle_event_order_per_step(self) -> None:
        """For each step the bus sees ``Started`` then either ``Completed`` or ``Errored``."""
        app = _stub_app()
        pipeline = Pipeline(app)
        registry = _step_registry(raise_on="cleanup")
        with CollectingSubscriber(app.event_bus, Event) as sub:
            _run_pipeline(pipeline, registry)
        # Build the lifecycle sequence per step.
        per_step: dict[str, list[str]] = {}
        for event in sub.received:
            if isinstance(event, StepStarted):
                per_step.setdefault(event.step, []).append("started")
            elif isinstance(event, StepCompleted):
                per_step.setdefault(event.step, []).append("completed")
            elif isinstance(event, StepErrored):
                per_step.setdefault(event.step, []).append("errored")
        # Cleanup: started → errored. Every other step: started → completed.
        assert per_step["cleanup"] == ["started", "errored"]
        for step in (s for s in EXPECTED_STEP_NAMES if s != "cleanup"):
            assert per_step[step] == ["started", "completed"], f"step {step}: {per_step[step]}"

    def test_overall_event_envelope_order(self) -> None:
        """PipelineStarted comes first; PipelineEnded comes last; step events in between."""
        app = _stub_app()
        pipeline = Pipeline(app)
        with CollectingSubscriber(app.event_bus, Event) as sub:
            _run_pipeline(pipeline, _step_registry())
        assert isinstance(sub.received[0], PipelineStarted)
        assert isinstance(sub.received[-1], PipelineEnded)
        # Between the two pipeline events, every event is a step lifecycle event.
        middle = sub.received[1:-1]
        for event in middle:
            assert isinstance(event, (StepStarted, StepCompleted, StepErrored))

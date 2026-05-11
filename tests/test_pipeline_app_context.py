"""Sub-phase 2.3 invariants for ``Pipeline(app: AppContext)``.

Verifies that :class:`personalscraper.pipeline.Pipeline` accepts only an
:class:`AppContext` in ``__init__`` and that every run-scope flag plus
the observers tuple is now a keyword-only parameter of :meth:`run`.
Each call to :meth:`run` generates a fresh ``run_id``, binds
``current_correlation_id`` for the lifetime of the call, and resets the
binding in a ``try/finally`` clause — including when a step raises.
"""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus, current_correlation_id
from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline
from personalscraper.pipeline_observer import PipelineObserverBase
from personalscraper.pipeline_protocol import StepContext


def _stub_app() -> AppContext:
    """Build an :class:`AppContext` whose config/settings are MagicMocks.

    Suitable for tests that never reach disk I/O. The :class:`EventBus`
    is a real instance so subscribe/emit machinery behaves correctly.
    """
    config = MagicMock()
    config.disks = []
    config.paths.staging_dir = MagicMock()
    ingest_entry = MagicMock()
    ingest_entry.id = 97
    ingest_entry.role = "ingest"
    config.staging_dirs = [ingest_entry]
    config.paths.data_dir = MagicMock()
    settings = MagicMock()
    return AppContext(config=config, settings=settings, event_bus=EventBus())


class _CapturingStep:
    """PipelineStep stub that records every ``StepContext`` it receives.

    Implements the structural ``PipelineStep`` protocol directly so the
    captured contexts are the real :class:`StepContext` produced by the
    Pipeline — not the unpacked positional args produced by
    :class:`LegacyCallableStep`.
    """

    def __init__(self, name: str, captures: list[StepContext], *, raises: bool = False) -> None:
        self.name = name
        self._captures = captures
        self._raises = raises

    def __call__(self, ctx: StepContext) -> StepReport | tuple[StepReport, list[Any]]:
        self._captures.append(ctx)
        if self._raises:
            raise RuntimeError(f"boom in {self.name}")
        if self.name == "verify":
            return StepReport(name=self.name, success_count=1), []
        return StepReport(name=self.name, success_count=1)


def _capturing_step_registry(
    captures: list[StepContext],
    *,
    raise_on: str | None = None,
) -> dict[str, _CapturingStep]:
    """Build a full step registry of :class:`_CapturingStep` instances."""
    return {
        name: _CapturingStep(name, captures, raises=(name == raise_on))
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


def _run_with_steps(pipeline: Pipeline, steps: dict[str, _CapturingStep], **run_kwargs: Any) -> None:
    """Run ``pipeline`` after patching out disk I/O and the step adapter.

    ``apply_step_overrides`` is patched to return ``steps`` verbatim so
    the test's :class:`_CapturingStep` instances reach the run loop
    unchanged (instead of being wrapped by :class:`LegacyCallableStep`).
    """
    with (
        patch("personalscraper.pipeline.ensure_staging_tree"),
        patch.object(Pipeline, "_check_temp_empty_gate"),
        patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
        patch("personalscraper.pipeline.apply_step_overrides", return_value=steps),
    ):
        pipeline.run(**run_kwargs)


class TestPipelineInitSignature:
    """``Pipeline.__init__`` accepts ONLY ``app: AppContext``."""

    def test_pipeline_init_takes_app_context_only(self) -> None:
        """``inspect.signature(Pipeline.__init__).parameters`` is exactly ``{self, app}``."""
        params = set(inspect.signature(Pipeline.__init__).parameters)
        assert params == {"self", "app"}

    def test_pipeline_init_rejects_legacy_kwargs(self) -> None:
        """Passing the old ``config``/``settings``/``observers`` kwargs must fail."""
        app = _stub_app()
        with pytest.raises(TypeError):
            Pipeline(app, observers=[])  # type: ignore[call-arg]


class TestPipelineRunObserversKwarg:
    """``Pipeline.run`` accepts ``observers`` as a keyword-only parameter."""

    def test_pipeline_run_accepts_observers_kwarg(self) -> None:
        """``Pipeline.run`` exposes ``observers`` as a keyword-only parameter with default ``()``."""
        params = inspect.signature(Pipeline.run).parameters
        assert "observers" in params
        assert params["observers"].default == ()
        assert params["observers"].kind is inspect.Parameter.KEYWORD_ONLY

    def test_pipeline_run_propagates_observers_to_step_context(self) -> None:
        """The ``observers`` tuple passed to ``run`` reaches each ``StepContext`` unchanged."""
        captures: list[StepContext] = []
        observer_a = PipelineObserverBase()
        observer_b = PipelineObserverBase()
        pipeline = Pipeline(_stub_app())
        _run_with_steps(
            pipeline,
            _capturing_step_registry(captures),
            observers=(observer_a, observer_b),
        )
        assert captures, "stub steps must have run"
        for ctx in captures:
            assert ctx.observers == (observer_a, observer_b)


class TestPipelineRunIdGeneration:
    """``Pipeline.run`` produces a fresh ``run_id`` per call."""

    def test_pipeline_run_generates_unique_run_id(self) -> None:
        """Two consecutive ``run`` calls produce two distinct ``UUID`` ``run_id`` values."""
        pipeline = Pipeline(_stub_app())
        first_captures: list[StepContext] = []
        second_captures: list[StepContext] = []
        _run_with_steps(pipeline, _capturing_step_registry(first_captures))
        _run_with_steps(pipeline, _capturing_step_registry(second_captures))
        first_run_ids = {ctx.run_id for ctx in first_captures}
        second_run_ids = {ctx.run_id for ctx in second_captures}
        assert len(first_run_ids) == 1
        assert len(second_run_ids) == 1
        first_id = next(iter(first_run_ids))
        second_id = next(iter(second_run_ids))
        assert isinstance(first_id, UUID)
        assert isinstance(second_id, UUID)
        assert first_id != second_id

    def test_pipeline_run_propagates_run_id_to_step_context(self) -> None:
        """Every ``StepContext`` built during a ``run`` call exposes the same ``run_id``."""
        pipeline = Pipeline(_stub_app())
        captures: list[StepContext] = []
        _run_with_steps(pipeline, _capturing_step_registry(captures))
        bound_run_ids = {ctx.run_id for ctx in captures}
        assert bound_run_ids == {pipeline._run_id}


class TestPipelineRunCorrelationIdBinding:
    """``current_correlation_id`` reflects the active ``run_id`` and resets after."""

    def test_pipeline_run_binds_current_correlation_id_during_run(self) -> None:
        """Inside a step body, ``current_correlation_id.get()`` equals ``str(pipeline._run_id)``."""
        pipeline = Pipeline(_stub_app())
        captured_correlation: list[str | None] = []

        class _ProbeStep:
            name = "ingest"

            def __call__(self, ctx: StepContext) -> StepReport:  # noqa: ARG002
                captured_correlation.append(current_correlation_id.get())
                return StepReport(name="ingest", success_count=1)

        steps = _capturing_step_registry([])
        steps["ingest"] = _ProbeStep()  # type: ignore[assignment]
        _run_with_steps(pipeline, steps)
        assert captured_correlation == [str(pipeline._run_id)]

    def test_pipeline_run_resets_correlation_id_after_run(self) -> None:
        """``current_correlation_id`` returns to ``None`` after a clean ``run`` completes."""
        assert current_correlation_id.get() is None
        pipeline = Pipeline(_stub_app())
        _run_with_steps(pipeline, _capturing_step_registry([]))
        assert current_correlation_id.get() is None

    def test_pipeline_run_resets_correlation_id_after_exception(self) -> None:
        """``current_correlation_id`` resets in the ``finally`` clause even on critical-step crash."""
        assert current_correlation_id.get() is None
        pipeline = Pipeline(_stub_app())
        # The ingest step is critical — its crash returns the report early
        # but the ``finally`` clause must still reset the binding.
        _run_with_steps(
            pipeline,
            _capturing_step_registry([], raise_on="ingest"),
        )
        assert current_correlation_id.get() is None

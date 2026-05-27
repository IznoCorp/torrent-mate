"""Tests for headless pipeline mode after Phase 3.7b.

The ``observers`` kwarg is gone from :meth:`Pipeline.run`. Headless == no
subscriber attached to ``ctx.app.event_bus`` before ``Pipeline.run`` fires.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline import Pipeline


def _stub_app() -> AppContext:
    """Build an :class:`AppContext` whose config/settings are MagicMocks."""
    config = MagicMock()
    config.disks = []
    config.paths.staging_dir = MagicMock()
    ingest_entry = MagicMock()
    ingest_entry.id = 97
    ingest_entry.role = "ingest"
    config.staging_dirs = [ingest_entry]
    config.paths.data_dir = MagicMock()
    config.trailers.pipeline.skip = True
    config.trailers.pipeline.continue_on_error = True
    config.trailers.enabled = False
    settings = MagicMock()
    return AppContext(
        config=config,
        settings=settings,
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
    )


def _make_step_registry() -> dict[str, object]:
    """Build a fake registry of 9 steps that all succeed without I/O."""

    class _Step:
        def __init__(self, name: str) -> None:
            self.name = name

        def __call__(self, ctx) -> StepReport | tuple[StepReport, list]:  # type: ignore[no-untyped-def]
            if self.name == "verify":
                return StepReport(name=self.name, success_count=1), [MagicMock()]
            return StepReport(name=self.name, success_count=1)

    return {
        n: _Step(n)
        for n in ("ingest", "sort", "clean", "scrape", "cleanup", "enforce", "verify", "trailers", "dispatch")
    }


class TestPipelineHeadless:
    """Pipeline default contract: nothing on the bus unless wired by the caller."""

    def test_init_rejects_legacy_observers_kwarg(self) -> None:
        """The legacy ``observers`` kwarg on ``__init__`` is removed."""
        import pytest

        with pytest.raises(TypeError):
            Pipeline(_stub_app(), observers=[])  # type: ignore[call-arg]

    def test_run_signature_has_no_observers(self) -> None:
        """``Pipeline.run`` no longer exposes an ``observers`` parameter."""
        import inspect

        params = inspect.signature(Pipeline.run).parameters
        assert "observers" not in params

    def test_headless_run_produces_no_stdout(self, capsys) -> None:
        """Default ``Pipeline.run`` (no subscriber on the bus) emits zero stdout.

        With no :class:`RichConsoleSubscriber` registered on ``ctx.app.event_bus``,
        the bus has no console subscriber and nothing reaches stdout.
        """
        steps = _make_step_registry()
        pipeline = Pipeline(_stub_app())

        capsys.readouterr()  # drain setup
        with (
            patch("personalscraper.pipeline.ensure_staging_tree"),
            patch.object(Pipeline, "_check_temp_empty_gate"),
            patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
            patch("personalscraper.pipeline.apply_step_overrides", return_value=steps),
        ):
            pipeline.run()
        captured = capsys.readouterr()
        assert captured.out == "", f"Headless run must not write to stdout, got: {captured.out!r}"

    def test_run_without_subscribers_produces_full_report(self) -> None:
        """A headless ``Pipeline.run`` still produces a 9-step report."""
        steps = _make_step_registry()
        pipeline = Pipeline(_stub_app())

        with (
            patch("personalscraper.pipeline.ensure_staging_tree"),
            patch.object(Pipeline, "_check_temp_empty_gate"),
            patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
            patch("personalscraper.pipeline.apply_step_overrides", return_value=steps),
        ):
            report = pipeline.run()

        assert isinstance(report, PipelineReport)
        assert len(report.steps) == 9

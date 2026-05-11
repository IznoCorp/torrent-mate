"""Tests for pipeline headless mode (default ``observers=()`` on ``run``)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
    return AppContext(config=config, settings=settings, event_bus=EventBus())


class TestPipelineHeadless:
    """Pipeline default contract: no observers attached unless wired at ``run``."""

    def test_init_starts_with_empty_observers(self) -> None:
        """``Pipeline.__init__`` leaves ``_observers`` empty.

        Sub-phase 2.3 contract: observer wiring is exclusively the CLI
        bootstrap's responsibility (sub-phase 2.4). The Pipeline no
        longer auto-creates a :class:`RichConsoleObserver` — headless is
        the default. The CLI passes ``observers=...`` to
        :meth:`Pipeline.run` to opt into console output.
        """
        pipeline = Pipeline(_stub_app())
        assert pipeline._observers == []

    def test_init_rejects_legacy_observers_kwarg(self) -> None:
        """The legacy ``observers`` kwarg on ``__init__`` is removed.

        ``observers`` moved to :meth:`Pipeline.run` in sub-phase 2.3.
        Passing it to ``__init__`` must raise ``TypeError``.
        """
        import pytest

        with pytest.raises(TypeError):
            Pipeline(_stub_app(), observers=[])  # type: ignore[call-arg]

    def test_run_with_default_observers_is_headless(self) -> None:
        """``Pipeline.run`` with no observers kwarg keeps ``_observers`` empty."""
        pipeline = Pipeline(_stub_app())

        class _Step:
            def __init__(self, name: str) -> None:
                self.name = name

            def __call__(self, ctx) -> StepReport | tuple[StepReport, list]:  # type: ignore[no-untyped-def]
                if self.name == "verify":
                    return StepReport(name=self.name, success_count=1), []
                return StepReport(name=self.name, success_count=1)

        steps = {
            name: _Step(name)
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

        with (
            patch("personalscraper.pipeline.ensure_staging_tree"),
            patch.object(Pipeline, "_check_temp_empty_gate"),
            patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
            patch("personalscraper.pipeline.apply_step_overrides", return_value=steps),
        ):
            pipeline.run()
        assert pipeline._observers == []

    def test_headless_run_produces_no_stdout(self, capsys) -> None:
        """Default ``Pipeline.run`` (no observers) emits zero stdout.

        Whether the observer list is empty is the API check; what
        matters for cron/CI is that *nothing* is printed to the terminal.
        """

        class FakeStep:
            def __init__(self, step_name: str) -> None:
                self.name = step_name

            def __call__(self, ctx) -> StepReport | tuple[StepReport, list]:  # type: ignore[no-untyped-def]
                if self.name == "verify":
                    return StepReport(name=self.name, success_count=1), [MagicMock()]
                return StepReport(name=self.name, success_count=1)

        steps = {
            n: FakeStep(n)
            for n in (
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

        pipeline = Pipeline(_stub_app())

        # Drain stdout from setup, then run and check no further output.
        capsys.readouterr()
        with (
            patch("personalscraper.pipeline.ensure_staging_tree"),
            patch.object(Pipeline, "_check_temp_empty_gate"),
            patch.object(Pipeline, "_recover_from_previous_run", return_value=0),
            patch("personalscraper.pipeline.apply_step_overrides", return_value=steps),
        ):
            pipeline.run()
        captured = capsys.readouterr()

        # Pipeline lifecycle methods use structlog (logger), not print/console.
        # The headless contract: zero observer-driven console output.
        # Structlog may emit to stderr depending on config — assert on stdout only.
        assert captured.out == "", f"Headless run must not write to stdout, got: {captured.out!r}"

    def test_run_with_no_observers(self) -> None:
        """``Pipeline.run`` produces a 9-step report when invoked headless."""

        class FakeStep:
            def __init__(self, step_name: str) -> None:
                self.name = step_name

            def __call__(self, ctx) -> StepReport | tuple[StepReport, list]:  # type: ignore[no-untyped-def]
                if self.name == "verify":
                    return StepReport(name=self.name, success_count=1), [MagicMock()]
                return StepReport(name=self.name, success_count=1)

        steps = {
            n: FakeStep(n)
            for n in (
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

"""Sub-phase 2.4 invariants for the ``personalscraper run`` CLI entry — migrated for 3.7a.

Verifies that the CLI bootstrap in ``personalscraper.commands.pipeline`` builds an
:class:`AppContext` via ``_build_app_context`` and passes it verbatim to
:class:`Pipeline.__init__`. The Phase-2 visual-regression baseline (legacy
``RichConsoleObserver`` replay) has moved to
``tests/subscribers/test_rich_console_subscriber.py::test_rich_console_subscriber_snapshot_matches_baseline``
where the same baseline is asserted via the bus subscriber path.
"""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.models import PipelineReport, StepReport

runner = CliRunner()


def _make_pipeline_report() -> PipelineReport:
    """Build a minimal :class:`PipelineReport` for the ``Pipeline.run`` stub."""
    from datetime import datetime, timedelta

    report = PipelineReport(started_at=datetime(2026, 1, 1))
    for name in ("ingest", "sort", "clean", "scrape", "cleanup", "verify", "dispatch"):
        report.add_step(name, StepReport(name=name))
    report.finished_at = datetime(2026, 1, 1) + timedelta(seconds=1)
    return report


class TestPipelineCommandBuildsAppContext:
    """``_build_app_context`` is invoked at the ``run`` boundary."""

    @patch("personalscraper.pipeline.Pipeline.run")
    def test_pipeline_command_builds_app_context_and_passes_to_pipeline(self, mock_run) -> None:
        """``Pipeline.__init__`` receives the AppContext built by the CLI bootstrap.

        Captures the first positional argument passed to ``Pipeline.__init__``
        and asserts it is an :class:`AppContext` instance.
        """
        mock_run.return_value = _make_pipeline_report()
        captured: list[AppContext] = []
        real_init = __import__("personalscraper.pipeline", fromlist=["Pipeline"]).Pipeline.__init__

        def _capturing_init(self, app):  # type: ignore[no-untyped-def]
            captured.append(app)
            real_init(self, app)

        with patch("personalscraper.pipeline.Pipeline.__init__", _capturing_init):
            result = runner.invoke(app, ["run"])
        assert result.exit_code == 0, result.output
        assert len(captured) == 1
        app_context = captured[0]
        assert isinstance(app_context, AppContext)
        assert hasattr(app_context.config, "paths")
        assert hasattr(app_context.config.paths, "staging_dir")

    @patch("personalscraper.pipeline.Pipeline.run")
    def test_pipeline_command_constructs_event_bus(self, mock_run) -> None:
        """The AppContext carries a real :class:`EventBus` instance.

        After Phase 3 the CLI bootstrap also self-subscribes
        :class:`RichConsoleSubscriber` to that bus before ``Pipeline.run`` is
        invoked. Subscribers are removed in the CLI ``finally`` block, so we
        snapshot the bus state at :meth:`Pipeline.__init__` time — that is when
        production code first observes the configured bus.
        """
        mock_run.return_value = _make_pipeline_report()
        captured: list[AppContext] = []
        subscriber_count_at_init: list[int] = []
        real_init = __import__("personalscraper.pipeline", fromlist=["Pipeline"]).Pipeline.__init__

        def _capturing_init(self, app):  # type: ignore[no-untyped-def]
            captured.append(app)
            subscriber_count_at_init.append(sum(len(v) for v in app.event_bus._subscribers.values()))
            real_init(self, app)

        with patch("personalscraper.pipeline.Pipeline.__init__", _capturing_init):
            result = runner.invoke(app, ["run"])
        assert result.exit_code == 0, result.output
        app_context = captured[0]
        assert isinstance(app_context.event_bus, EventBus)
        assert subscriber_count_at_init[0] > 0, (
            "expected the CLI bootstrap to register at least one subscriber "
            "(RichConsoleSubscriber after 3.5) before Pipeline.__init__"
        )

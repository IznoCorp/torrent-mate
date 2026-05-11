"""Sub-phase 2.4 invariants for the ``personalscraper run`` CLI entry.

Verifies that the CLI bootstrap in ``personalscraper.commands.pipeline``
builds an :class:`AppContext` via ``_build_app_context`` and passes it
verbatim to :class:`Pipeline.__init__`. Also locks the Phase 2 visual
regression contract by replaying the canonical event sequence from
Pre-flight #7 through the legacy :class:`RichConsoleObserver` wired by
this command — the rendered output must match the immutable baseline at
``tests/snapshots/rich_console_canonical.txt`` bytes-identical.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from typer.testing import CliRunner

from personalscraper.cli import app
from personalscraper.core.app_context import AppContext
from personalscraper.core.event_bus import EventBus
from personalscraper.models import PipelineReport, StepReport
from personalscraper.observers.rich_console import RichConsoleObserver
from tests.snapshots._canonical_sequence import (
    CANONICAL_OBSERVER_CONFIGS,
    CANONICAL_SEQUENCE,
)

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
        and asserts it is the :class:`AppContext` returned by
        :func:`personalscraper.commands.pipeline._build_app_context`.
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
        # The config carried by the AppContext is the same one the global Typer
        # callback loaded — it must expose ``paths.staging_dir``.
        assert hasattr(app_context.config, "paths")
        assert hasattr(app_context.config.paths, "staging_dir")

    @patch("personalscraper.pipeline.Pipeline.run")
    def test_pipeline_command_constructs_event_bus(self, mock_run) -> None:
        """The AppContext carries a fresh :class:`EventBus` with zero subscribers."""
        mock_run.return_value = _make_pipeline_report()
        captured: list[AppContext] = []
        real_init = __import__("personalscraper.pipeline", fromlist=["Pipeline"]).Pipeline.__init__

        def _capturing_init(self, app):  # type: ignore[no-untyped-def]
            captured.append(app)
            real_init(self, app)

        with patch("personalscraper.pipeline.Pipeline.__init__", _capturing_init):
            result = runner.invoke(app, ["run"])
        assert result.exit_code == 0, result.output
        app_context = captured[0]
        assert isinstance(app_context.event_bus, EventBus)
        # The EventBus exposes ``_subscribers`` (dict[type, tuple[SubscriptionToken, ...]])
        # — an empty mapping confirms no Phase-3-or-later subscriber leaked in.
        assert app_context.event_bus._subscribers == {}


class TestPipelineCommandConsoleOutputUnchanged:
    """Phase 2 visual regression lock — Phase 3 §3.5 + §3.9 reference this baseline."""

    def test_pipeline_command_console_output_unchanged(self) -> None:
        """Replaying CANONICAL_SEQUENCE through the legacy observer matches the baseline.

        Drives the same two observer configurations that produced the
        baseline (live + verbose + run_id="canonical-live" and dry +
        non-verbose + run_id="") into a single deterministic
        :class:`rich.console.Console` buffer, then compares the captured
        bytes to ``tests/snapshots/rich_console_canonical.txt``.
        """
        buffer = StringIO()
        console = Console(
            width=120,
            color_system=None,
            force_terminal=False,
            file=buffer,
            record=True,
        )
        for config in CANONICAL_OBSERVER_CONFIGS:
            observer = RichConsoleObserver(console=console, **config)
            for callback_name, args in CANONICAL_SEQUENCE:
                getattr(observer, callback_name)(*args)
        rendered = console.export_text()

        baseline_path = Path(__file__).resolve().parents[1] / "snapshots" / "rich_console_canonical.txt"
        expected = baseline_path.read_text()
        assert rendered == expected, (
            "RichConsoleObserver output drifted from Pre-flight #7 baseline. Phase 2 must NOT change console output."
        )

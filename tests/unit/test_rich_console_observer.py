"""Tests for RichConsoleObserver."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from rich.console import Console

from personalscraper.models import PipelineReport, StepReport
from personalscraper.observers.rich_console import RichConsoleObserver
from personalscraper.pipeline_observer import StepEvent


class TestRichConsoleObserver:
    """RichConsoleObserver tests."""

    @staticmethod
    def _make_console() -> Console:
        return Console(force_terminal=True, width=120, color_system="truecolor")

    def test_name(self) -> None:
        """Observer has the expected name."""
        obs = RichConsoleObserver()
        assert obs.name == "rich-console"

    def test_on_step_start_prints_header(self) -> None:
        """on_step_start emits the step header with icon."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console)
            obs.on_step_start("ingest")
            mock_print.assert_called_once()

    def test_on_step_end_prints_summary(self) -> None:
        """on_step_end emits the OK/skip/err summary line."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console)
            report = StepReport(name="ingest", success_count=3, skip_count=1)
            obs.on_step_end("ingest", report, 2.1)
            assert mock_print.call_count >= 1

    def test_on_step_end_skips_already_done_in_verbose(self) -> None:
        """skipped_already_done details are filtered from verbose output."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console, verbose=True)
            report = StepReport(name="ingest", success_count=1, details=["skipped_already_done: foo"])
            obs.on_step_end("ingest", report, 0.5)
            printed_args = [str(call) for call in mock_print.call_args_list]
            assert not any("skipped_already_done" in arg for arg in printed_args)

    def test_on_step_error_prints_fatal(self) -> None:
        """on_step_error emits the red FATAL line."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console)
            obs.on_step_error("ingest", ValueError("bad data"))
            mock_print.assert_called_once()

    def test_on_progress_noop_when_not_verbose(self) -> None:
        """on_progress does nothing when verbose=False."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console, verbose=False)
            obs.on_progress(StepEvent(step="sort", item="x.mkv", status="moved"))
            mock_print.assert_not_called()

    def test_on_progress_prints_in_verbose_mode(self) -> None:
        """on_progress prints per-item detail when verbose=True."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console, verbose=True)
            obs.on_progress(StepEvent(step="sort", item="x.mkv", status="moved"))
            mock_print.assert_called_once()

    def test_on_pipeline_end_prints_table(self) -> None:
        """on_pipeline_end renders the final Panel/Table."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console)
            report = PipelineReport(started_at=datetime.now())
            report.add_step("ingest", StepReport(name="ingest", success_count=2))
            report.finished_at = datetime.now()
            obs.on_pipeline_end(report)
            assert mock_print.call_count >= 1

    def test_icon_mapping(self) -> None:
        """_icon returns correct step number for each known step."""
        obs = RichConsoleObserver()
        assert "1/9" in obs._icon("ingest")
        assert "9/9" in obs._icon("dispatch")
        assert obs._icon("unknown") == ""

    def test_on_pipeline_start_is_noop(self) -> None:
        """on_pipeline_start does nothing (banner is CLI responsibility)."""
        obs = RichConsoleObserver()
        report = PipelineReport(started_at=datetime.now())
        obs.on_pipeline_start(report)  # No exception = pass

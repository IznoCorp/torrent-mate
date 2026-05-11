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
        """on_step_start emits the step header with icon AND step name."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console)
            obs.on_step_start("ingest")
            mock_print.assert_called_once()
            rendered = str(mock_print.call_args)
            assert "INGEST" in rendered, "step header must contain uppercase step name"
            assert "1/9" in rendered, "step header must include the step icon"

    def test_on_step_end_prints_summary(self) -> None:
        """on_step_end emits OK/skip counts AND the elapsed time."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console)
            report = StepReport(name="ingest", success_count=3, skip_count=1)
            obs.on_step_end("ingest", report, 2.1)
            assert mock_print.call_count >= 1
            rendered = " ".join(str(call) for call in mock_print.call_args_list)
            assert "3 OK" in rendered, "summary must contain OK count"
            assert "1 skip" in rendered, "summary must contain skip count"
            assert "2.1s" in rendered, "summary must contain elapsed time"

    def test_on_step_end_includes_error_count(self) -> None:
        """When errors > 0, summary mentions them in red."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console)
            report = StepReport(name="ingest", success_count=2, error_count=1)
            obs.on_step_end("ingest", report, 0.5)
            rendered = " ".join(str(call) for call in mock_print.call_args_list)
            assert "1 err" in rendered
            assert "2 OK" in rendered

    def test_on_step_end_nothing_to_do(self) -> None:
        """Zero counts render 'nothing to do' rather than an empty summary."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console)
            obs.on_step_end("ingest", StepReport(name="ingest"), 0.0)
            rendered = " ".join(str(call) for call in mock_print.call_args_list)
            assert "nothing to do" in rendered

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
        """on_step_error emits the red FATAL line with exception class and message."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console)
            obs.on_step_error("ingest", ValueError("bad data"))
            mock_print.assert_called_once()
            rendered = str(mock_print.call_args)
            assert "FATAL" in rendered
            assert "ValueError" in rendered
            assert "bad data" in rendered

    def test_on_progress_noop_when_not_verbose(self) -> None:
        """on_progress does nothing when verbose=False."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console, verbose=False)
            obs.on_progress(StepEvent(step="sort", item="x.mkv", status="moved"))
            mock_print.assert_not_called()

    def test_on_progress_prints_in_verbose_mode(self) -> None:
        """on_progress prints per-item detail (step, item, status) when verbose=True."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console, verbose=True)
            obs.on_progress(StepEvent(step="sort", item="x.mkv", status="moved"))
            mock_print.assert_called_once()
            rendered = str(mock_print.call_args)
            assert "sort" in rendered
            assert "x.mkv" in rendered
            assert "moved" in rendered

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

    def test_on_pipeline_start_prints_banner(self) -> None:
        """on_pipeline_start prints the banner with LIVE/DRY-RUN label and run ID."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console, dry_run=False, run_id="2026-05-11T10:00")
            report = PipelineReport(started_at=datetime.now())
            obs.on_pipeline_start(report)
            mock_print.assert_called_once()
            rendered = str(mock_print.call_args)
            assert "PersonalScraper Pipeline" in rendered
            assert "LIVE" in rendered
            assert "2026-05-11T10:00" in rendered

    def test_on_pipeline_start_dry_run_label(self) -> None:
        """dry_run=True renders the DRY-RUN label rather than LIVE."""
        console = self._make_console()
        with patch.object(console, "print") as mock_print:
            obs = RichConsoleObserver(console=console, dry_run=True)
            obs.on_pipeline_start(PipelineReport(started_at=datetime.now()))
            rendered = str(mock_print.call_args)
            assert "DRY-RUN" in rendered
            assert "LIVE" not in rendered

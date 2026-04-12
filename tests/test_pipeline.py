"""Tests for personalscraper.pipeline — sequential exhaustive orchestrator."""

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline import Pipeline


@pytest.fixture
def pipeline_settings(tmp_path):
    """Provide a mock Settings with ingest_dir pointing to a temp dir."""
    s = MagicMock()
    s.staging_dir = tmp_path
    s.ingest_dir = tmp_path / "097-TEMP"
    s.ingest_dir.mkdir()
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    return s


@pytest.fixture
def quiet_console():
    """Console that suppresses output for clean test logs."""
    return Console(quiet=True)


class TestRunStep:
    """Tests for Pipeline._run_step method."""

    def test_normal_step_report(self, pipeline_settings, quiet_console):
        """Normal step function returning StepReport."""
        pipeline = Pipeline(pipeline_settings, console=quiet_console)
        report = PipelineReport(started_at=MagicMock())
        sr = StepReport(name="test", success_count=3)

        result = pipeline._run_step("test", lambda: sr, report)

        assert result is None
        assert report.steps["test"].success_count == 3

    def test_tuple_return_extracts_extra(self, pipeline_settings, quiet_console):
        """Step returning (StepReport, extra_data) extracts both."""
        pipeline = Pipeline(pipeline_settings, console=quiet_console)
        report = PipelineReport(started_at=MagicMock())
        sr = StepReport(name="verify", success_count=5)
        extra_data = [{"path": "/some/path"}]

        result = pipeline._run_step("verify", lambda: (sr, extra_data), report)

        assert result == extra_data
        assert report.steps["verify"].success_count == 5

    def test_exception_creates_error_report(self, pipeline_settings, quiet_console):
        """Fatal exception creates StepReport with error details."""
        pipeline = Pipeline(pipeline_settings, console=quiet_console)
        report = PipelineReport(started_at=MagicMock())

        def failing_step():
            raise RuntimeError("disk full")

        result = pipeline._run_step("ingest", failing_step, report)

        assert result is None
        assert report.steps["ingest"].error_count == 1
        assert "RuntimeError: disk full" in report.steps["ingest"].details[0]


class TestPipelineRun:
    """Tests for Pipeline.run orchestration."""

    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    def test_runs_all_phases_in_order(
        self, mock_ingest, mock_sort, pipeline_settings, quiet_console,
    ):
        """Pipeline executes ingest→sort→gate→process→verify→dispatch."""
        mock_ingest.return_value = StepReport(name="ingest", success_count=2)
        mock_sort.return_value = StepReport(name="sort", success_count=2)

        with (
            patch("personalscraper.sorter.run.assert_temp_empty", return_value=[]),
            patch("personalscraper.scraper.run.run_scrape", return_value=StepReport(name="scrape")),
            patch("personalscraper.verify.run.run_verify") as mock_verify,
            patch("personalscraper.dispatch.run.run_dispatch") as mock_dispatch,
        ):
            mock_verify.return_value = (
                StepReport(name="verify", success_count=2),
                [MagicMock()],  # dispatchable items
            )
            mock_dispatch.return_value = StepReport(name="dispatch", success_count=2)

            pipeline = Pipeline(pipeline_settings, console=quiet_console)
            report = pipeline.run()

        assert len(report.steps) == 7
        assert list(report.steps.keys()) == [
            "ingest", "sort", "clean", "scrape", "cleanup", "verify", "dispatch",
        ]

    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    def test_dispatch_skipped_when_no_verified(
        self, mock_ingest, mock_sort, pipeline_settings, quiet_console,
    ):
        """Dispatch is skipped when verify returns no dispatchable items."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")

        with (
            patch("personalscraper.sorter.run.assert_temp_empty", return_value=[]),
            patch("personalscraper.scraper.run.run_scrape", return_value=StepReport(name="scrape")),
            patch("personalscraper.verify.run.run_verify") as mock_verify,
        ):
            mock_verify.return_value = (
                StepReport(name="verify", error_count=3),
                [],  # no dispatchable items
            )

            pipeline = Pipeline(pipeline_settings, console=quiet_console)
            report = pipeline.run()

        assert report.steps["dispatch"].skip_count == 1
        assert "no verified items" in report.steps["dispatch"].details[0].lower()

    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    def test_dispatch_skipped_when_verify_crashes(
        self, mock_ingest, mock_sort, pipeline_settings, quiet_console,
    ):
        """Dispatch is skipped when verify step crashes (returns None)."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")

        with (
            patch("personalscraper.sorter.run.assert_temp_empty", return_value=[]),
            patch("personalscraper.scraper.run.run_scrape", return_value=StepReport(name="scrape")),
            patch("personalscraper.verify.run.run_verify", side_effect=RuntimeError("boom")),
        ):
            pipeline = Pipeline(pipeline_settings, console=quiet_console)
            report = pipeline.run()

        # verify has error, dispatch is skipped
        assert report.steps["verify"].error_count == 1
        assert report.steps["dispatch"].skip_count == 1

    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    def test_gate_warning_does_not_block(
        self, mock_ingest, mock_sort, pipeline_settings, quiet_console,
    ):
        """Gate 097-TEMP not empty logs warning but pipeline continues."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")

        with (
            patch("personalscraper.sorter.run.assert_temp_empty", return_value=["leftover.mkv"]),
            patch("personalscraper.scraper.run.run_scrape", return_value=StepReport(name="scrape")),
            patch("personalscraper.verify.run.run_verify") as mock_verify,
        ):
            mock_verify.return_value = (StepReport(name="verify"), [])

            pipeline = Pipeline(pipeline_settings, console=quiet_console)
            report = pipeline.run()

        # Pipeline continued despite gate warning
        assert "verify" in report.steps
        assert "dispatch" in report.steps

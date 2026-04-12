"""Integration tests for the 7-step pipeline — V9 sequential exhaustive flow.

These tests verify end-to-end behavior of the Pipeline class with
mocked API calls but real filesystem operations (reclean, dedup, cleanup).
"""

from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from personalscraper.models import StepReport
from personalscraper.pipeline import Pipeline


@pytest.fixture
def integration_settings(tmp_path):
    """Provide realistic Settings for integration tests."""
    s = MagicMock()
    s.staging_dir = tmp_path
    s.ingest_dir = tmp_path / "097-TEMP"
    s.ingest_dir.mkdir()
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    # Create category dirs
    (tmp_path / "001-MOVIES").mkdir()
    (tmp_path / "002-TVSHOWS").mkdir()
    return s


@pytest.fixture
def quiet_console():
    """Console that suppresses output."""
    return Console(quiet=True)


class TestPipelineIntegration:
    """Integration tests for the complete 7-step pipeline."""

    @patch("personalscraper.dispatch.run.run_dispatch")
    @patch("personalscraper.verify.run.run_verify")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    def test_full_pipeline_7_steps(
        self, mock_gate, mock_ingest, mock_sort, mock_scrape,
        mock_verify, mock_dispatch, integration_settings, quiet_console,
    ):
        """Full pipeline produces 7 StepReports in correct order."""
        mock_ingest.return_value = StepReport(name="ingest", success_count=2)
        mock_sort.return_value = StepReport(name="sort", success_count=2)
        mock_scrape.return_value = StepReport(name="scrape", success_count=2)
        mock_verify.return_value = (
            StepReport(name="verify", success_count=2),
            [MagicMock()],
        )
        mock_dispatch.return_value = StepReport(name="dispatch", success_count=2)

        pipeline = Pipeline(integration_settings, console=quiet_console)
        report = pipeline.run()

        assert len(report.steps) == 7
        assert list(report.steps.keys()) == [
            "ingest", "sort", "clean", "scrape", "cleanup", "verify", "dispatch",
        ]

    @patch("personalscraper.dispatch.run.run_dispatch")
    @patch("personalscraper.verify.run.run_verify")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=["leftover.mkv"])
    def test_gate_warning_pipeline_continues(
        self, mock_gate, mock_ingest, mock_sort, mock_scrape,
        mock_verify, mock_dispatch, integration_settings, quiet_console,
    ):
        """Gate warning (097-TEMP not empty) does not block pipeline."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")
        mock_scrape.return_value = StepReport(name="scrape")
        mock_verify.return_value = (StepReport(name="verify"), [])

        pipeline = Pipeline(integration_settings, console=quiet_console)
        report = pipeline.run()

        # Pipeline continued — verify and dispatch steps exist
        assert "verify" in report.steps
        assert "dispatch" in report.steps

    @patch("personalscraper.verify.run.run_verify")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    def test_dispatch_skipped_no_verified(
        self, mock_gate, mock_ingest, mock_sort, mock_scrape,
        mock_verify, integration_settings, quiet_console,
    ):
        """Dispatch is skipped when verify returns no dispatchable items."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")
        mock_scrape.return_value = StepReport(name="scrape")
        mock_verify.return_value = (StepReport(name="verify"), [])

        pipeline = Pipeline(integration_settings, console=quiet_console)
        report = pipeline.run()

        assert report.steps["dispatch"].skip_count == 1

    @patch("personalscraper.dispatch.run.run_dispatch")
    @patch("personalscraper.verify.run.run_verify")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    def test_dry_run_propagates_to_all_phases(
        self, mock_gate, mock_ingest, mock_sort, mock_scrape,
        mock_verify, mock_dispatch, integration_settings, quiet_console,
    ):
        """--dry-run flag propagates to all pipeline steps."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")
        mock_scrape.return_value = StepReport(name="scrape")
        mock_verify.return_value = (StepReport(name="verify"), [MagicMock()])
        mock_dispatch.return_value = StepReport(name="dispatch")

        pipeline = Pipeline(integration_settings, dry_run=True, console=quiet_console)
        pipeline.run()

        assert mock_ingest.call_args.kwargs["dry_run"] is True
        assert mock_sort.call_args.kwargs["dry_run"] is True
        assert mock_scrape.call_args.kwargs["dry_run"] is True

    @patch("personalscraper.dispatch.run.run_dispatch")
    @patch("personalscraper.verify.run.run_verify")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    def test_interactive_propagates_to_scrape(
        self, mock_gate, mock_ingest, mock_sort, mock_scrape,
        mock_verify, mock_dispatch, integration_settings, quiet_console,
    ):
        """--interactive flag propagates to scrape via run_process."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")
        mock_scrape.return_value = StepReport(name="scrape")
        mock_verify.return_value = (StepReport(name="verify"), [MagicMock()])
        mock_dispatch.return_value = StepReport(name="dispatch")

        pipeline = Pipeline(
            integration_settings, interactive=True, console=quiet_console,
        )
        pipeline.run()

        assert mock_scrape.call_args.kwargs["interactive"] is True

    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    def test_reclean_runs_on_polluted_folder(
        self, mock_gate, mock_ingest, mock_sort, mock_scrape,
        integration_settings, quiet_console,
    ):
        """Polluted folder in 001-MOVIES gets re-cleaned during process phase."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")
        mock_scrape.return_value = StepReport(name="scrape")

        # Create a polluted folder in movies dir
        movies = integration_settings.staging_dir / "001-MOVIES"
        polluted = movies / "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted.mkdir()
        (polluted / "movie.mkv").write_text("video")

        with patch("personalscraper.verify.run.run_verify") as mock_verify:
            mock_verify.return_value = (StepReport(name="verify"), [])
            pipeline = Pipeline(integration_settings, console=quiet_console)
            report = pipeline.run()

        # The clean step should have re-cleaned the polluted folder
        assert report.steps["clean"].success_count >= 1
        assert not polluted.exists()
        # Should be renamed to clean format
        assert (movies / "Movie Title (2024)").exists()

    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    def test_clean_crash_does_not_block_scrape(
        self, mock_gate, mock_ingest, mock_sort, mock_scrape,
        integration_settings, quiet_console,
    ):
        """If clean phase crashes, scrape and cleanup still run."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")
        mock_scrape.return_value = StepReport(name="scrape", success_count=3)

        with (
            patch("personalscraper.process.run.run_clean", side_effect=RuntimeError("reclean boom")),
            patch("personalscraper.verify.run.run_verify") as mock_verify,
        ):
            mock_verify.return_value = (StepReport(name="verify"), [])
            pipeline = Pipeline(integration_settings, console=quiet_console)
            report = pipeline.run()

        # Clean has error, but scrape ran successfully
        assert report.steps["clean"].error_count == 1
        assert "reclean boom" in report.steps["clean"].details[0]
        assert report.steps["scrape"].success_count == 3
        assert "cleanup" in report.steps

    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    @patch("personalscraper.sorter.run.assert_temp_empty", return_value=[])
    def test_reclean_oserror_counted_not_crash(
        self, mock_gate, mock_ingest, mock_sort, mock_scrape,
        integration_settings, quiet_console,
    ):
        """OSError in reclean_folders is counted as error, not a crash."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")
        mock_scrape.return_value = StepReport(name="scrape")

        # Create a polluted folder with a permission issue via mock
        movies = integration_settings.staging_dir / "001-MOVIES"
        polluted = movies / "Movie.Title.2024.1080p.BluRay.x264-GROUP"
        polluted.mkdir()
        (polluted / "movie.mkv").write_text("video")

        with (
            patch("personalscraper.process.reclean.reclean_folders") as mock_reclean,
            patch("personalscraper.verify.run.run_verify") as mock_verify,
        ):
            # reclean returns a report with errors (not a crash)
            mock_reclean.return_value = StepReport(
                name="reclean", error_count=1,
                warnings=["permission denied"],
            )
            mock_verify.return_value = (StepReport(name="verify"), [])
            pipeline = Pipeline(integration_settings, console=quiet_console)
            report = pipeline.run()

        # Clean step has the error but pipeline continued
        assert report.steps["clean"].error_count >= 1
        assert report.steps["scrape"].name == "scrape"

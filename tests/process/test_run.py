"""Tests for process/run.py — run_process assembler."""

from unittest.mock import MagicMock, patch

from personalscraper.models import StepReport
from personalscraper.process.run import run_clean, run_process
from tests.fixtures.config import CANONICAL_STAGING_DIRS


def _make_settings():
    """Create mock settings."""
    return MagicMock()


def _make_config(tmp_path):
    """Minimal config mock with canonical staging_dirs and staging path.

    Args:
        tmp_path: Temporary directory used as the staging root.

    Returns:
        MagicMock with staging_dirs and paths.staging_dir configured.
    """
    c = MagicMock()
    c.staging_dirs = CANONICAL_STAGING_DIRS
    c.paths.staging_dir = tmp_path
    return c


class TestRunProcess:
    """Tests for run_process() assembler function."""

    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.process.dedup.dedup_folders")
    @patch("personalscraper.process.reclean.reclean_folders")
    def test_returns_three_step_reports(
        self,
        mock_reclean,
        mock_dedup,
        mock_scrape,
        mock_cleanup,
        tmp_path,
    ):
        """run_process returns (clean, scrape, cleanup) StepReports."""
        mock_reclean.return_value = StepReport(name="reclean")
        mock_dedup.return_value = (0, 0)
        mock_scrape.return_value = StepReport(name="scrape", success_count=3)
        mock_cleanup.return_value = StepReport(name="cleanup")

        settings = _make_settings()
        clean, scrape, cleanup = run_process(settings, config=_make_config(tmp_path))

        assert clean.name == "clean"
        assert scrape.name == "scrape"
        assert scrape.success_count == 3
        assert cleanup.name == "cleanup"

    @patch("personalscraper.process.reclean._has_polluted_folders", return_value=True)
    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.process.dedup.dedup_folders")
    @patch("personalscraper.process.reclean.reclean_folders")
    def test_calls_reclean_for_both_categories(
        self,
        mock_reclean,
        mock_dedup,
        mock_scrape,
        mock_cleanup,
        mock_polluted,
        tmp_path,
    ):
        """reclean_folders is called for both movies and tvshows dirs."""
        mock_reclean.return_value = StepReport(name="reclean")
        mock_dedup.return_value = (0, 0)
        mock_scrape.return_value = StepReport(name="scrape")
        mock_cleanup.return_value = StepReport(name="cleanup")

        settings = _make_settings()
        run_process(settings, config=_make_config(tmp_path))

        assert mock_reclean.call_count == 2
        movies_call = mock_reclean.call_args_list[0]
        tvshows_call = mock_reclean.call_args_list[1]
        assert "001-MOVIES" in str(movies_call)
        assert "002-TVSHOWS" in str(tvshows_call)

    @patch("personalscraper.process.reclean._has_polluted_folders", return_value=True)
    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.process.dedup.dedup_folders")
    @patch("personalscraper.process.reclean.reclean_folders")
    def test_dedup_count_added_to_clean_report(
        self,
        mock_reclean,
        mock_dedup,
        mock_scrape,
        mock_cleanup,
        mock_polluted,
        tmp_path,
    ):
        """Dedup merge count is added to clean_report.success_count."""
        mock_reclean.return_value = StepReport(name="reclean", success_count=1)
        mock_dedup.return_value = (2, 0)  # 2 folders merged, 0 failed
        mock_scrape.return_value = StepReport(name="scrape")
        mock_cleanup.return_value = StepReport(name="cleanup")

        settings = _make_settings()
        clean, _, _ = run_process(settings, config=_make_config(tmp_path))

        # 1 reclean (movies) + 2 dedup (movies) + 1 reclean (tvshows) + 2 dedup (tvshows)
        assert clean.success_count == 1 + 2 + 1 + 2

    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.process.dedup.dedup_folders")
    @patch("personalscraper.process.reclean.reclean_folders")
    def test_dry_run_passed_through(
        self,
        mock_reclean,
        mock_dedup,
        mock_scrape,
        mock_cleanup,
        tmp_path,
    ):
        """dry_run flag is passed to all sub-functions."""
        mock_reclean.return_value = StepReport(name="reclean")
        mock_dedup.return_value = (0, 0)
        mock_scrape.return_value = StepReport(name="scrape")
        mock_cleanup.return_value = StepReport(name="cleanup")

        settings = _make_settings()
        run_process(settings, config=_make_config(tmp_path), dry_run=True)

        for mock_call in mock_reclean.call_args_list:
            assert mock_call.kwargs.get("dry_run") is True
        for mock_call in mock_dedup.call_args_list:
            assert mock_call.kwargs.get("dry_run") is True
        assert mock_scrape.call_args.kwargs.get("dry_run") is True
        for mock_call in mock_cleanup.call_args_list:
            assert mock_call.kwargs.get("dry_run") is True

    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    @patch("personalscraper.scraper.run.run_scrape")
    @patch("personalscraper.process.dedup.dedup_folders")
    @patch("personalscraper.process.reclean.reclean_folders")
    def test_interactive_passed_to_scrape(
        self,
        mock_reclean,
        mock_dedup,
        mock_scrape,
        mock_cleanup,
        tmp_path,
    ):
        """Interactive flag is passed to run_scrape."""
        mock_reclean.return_value = StepReport(name="reclean")
        mock_dedup.return_value = (0, 0)
        mock_scrape.return_value = StepReport(name="scrape")
        mock_cleanup.return_value = StepReport(name="cleanup")

        settings = _make_settings()
        run_process(settings, config=_make_config(tmp_path), interactive=True)

        assert mock_scrape.call_args.kwargs.get("interactive") is True


class TestRunCleanFastSkip:
    """Tests for run_clean fast-skip when no polluted folders."""

    def test_fast_skip_all_clean(self, tmp_path):
        """run_clean returns empty report when all folders are clean."""
        settings = _make_settings()
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        (movies / "The Matrix (1999)").mkdir()
        (movies / "Inception (2010)").mkdir()
        tvshows = tmp_path / "002-TVSHOWS"
        tvshows.mkdir()

        report = run_clean(settings, _make_config(tmp_path))

        assert report.name == "clean"
        assert report.success_count == 0
        assert report.error_count == 0

    def test_no_fast_skip_with_polluted(self, tmp_path):
        """run_clean processes when polluted folders exist."""
        settings = _make_settings()
        movies = tmp_path / "001-MOVIES"
        movies.mkdir()
        (movies / "Movie.Title.2024.1080p.BluRay.x264-GROUP").mkdir()
        tvshows = tmp_path / "002-TVSHOWS"
        tvshows.mkdir()

        report = run_clean(settings, _make_config(tmp_path))

        # Polluted folder was processed (re-cleaned)
        assert report.success_count >= 1

"""Tests for process/run.py — run_process assembler."""

from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.models import StepReport
from personalscraper.process.run import _revert_unmatched_recleans, run_clean, run_process
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
        clean, scrape, cleanup = run_process(settings, config=_make_config(tmp_path), event_bus=EventBus())

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
        run_process(settings, config=_make_config(tmp_path), event_bus=EventBus())

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
        clean, _, _ = run_process(settings, config=_make_config(tmp_path), event_bus=EventBus())

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
        run_process(settings, config=_make_config(tmp_path), dry_run=True, event_bus=EventBus())

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
        run_process(settings, config=_make_config(tmp_path), interactive=True, event_bus=EventBus())

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

        report = run_clean(settings, _make_config(tmp_path), event_bus=EventBus())

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

        report = run_clean(settings, _make_config(tmp_path), event_bus=EventBus())

        # Polluted folder was processed (re-cleaned)
        assert report.success_count >= 1


class TestRevertUnmatchedRecleans:
    """Tests for _revert_unmatched_recleans() helper."""

    def test_unmatched_dir_reverted_to_torrent_name(self, tmp_path):
        """An unmatched clean-named dir is renamed back to its original torrent name."""
        category_dir = tmp_path / "002-TVSHOWS"
        category_dir.mkdir()

        # Simulate what reclean produced: the polluted torrent folder was renamed.
        original_name = "Les.secrets.du.Prince.Andrew.2023.S01.DOC.FRENCH.1080p.WEB.H264-BOUBA"
        clean_name = "Les secrets du Prince Andrew S01 (2023)"
        clean_dir = category_dir / clean_name
        clean_dir.mkdir()

        rename_map = {clean_name: original_name}
        unmatched_names = {clean_name}

        reverted = _revert_unmatched_recleans(
            category_dirs=[category_dir],
            unmatched_names=unmatched_names,
            rename_map=rename_map,
        )

        assert reverted == 1
        # The clean-named dir should no longer exist.
        assert not clean_dir.exists()
        # The original torrent-named dir should be back.
        assert (category_dir / original_name).exists()

    def test_matched_dir_not_reverted(self, tmp_path):
        """A folder that was successfully scraped is left under its clean name."""
        category_dir = tmp_path / "001-MOVIES"
        category_dir.mkdir()

        clean_name = "The Butterfly Effect (2004)"
        clean_dir = category_dir / clean_name
        clean_dir.mkdir()

        rename_map = {clean_name: "The.Butterfly.Effect.2004.DC.MULTi.TRUEFRENCH.1080p.x264"}
        # This folder is NOT in unmatched_names — scraper succeeded.
        unmatched_names: set[str] = set()

        reverted = _revert_unmatched_recleans(
            category_dirs=[category_dir],
            unmatched_names=unmatched_names,
            rename_map=rename_map,
        )

        assert reverted == 0
        # Clean dir must remain untouched.
        assert clean_dir.exists()

    def test_empty_rename_map_returns_zero(self, tmp_path):
        """Returns 0 immediately when rename_map is empty (fast path)."""
        category_dir = tmp_path / "002-TVSHOWS"
        category_dir.mkdir()

        reverted = _revert_unmatched_recleans(
            category_dirs=[category_dir],
            unmatched_names={"Some Clean Name"},
            rename_map={},
        )

        assert reverted == 0

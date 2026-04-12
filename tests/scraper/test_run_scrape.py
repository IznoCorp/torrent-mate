"""Tests for the scrape step runner (run_scrape).

Tests the conversion from ScrapeResult to StepReport and the
orchestration of movie + tvshow processing.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.scraper.run import _to_step_report, run_scrape
from personalscraper.scraper.scraper import ScrapeResult

# ---------------------------------------------------------------------------
# StepReport conversion
# ---------------------------------------------------------------------------

class TestToStepReport:
    """Tests for _to_step_report conversion."""

    def test_empty_results(self) -> None:
        """Should return zero counts for empty list."""
        report = _to_step_report([])
        assert report.name == "scrape"
        assert report.success_count == 0
        assert report.skip_count == 0
        assert report.error_count == 0

    def test_counts_scraped(self) -> None:
        """Should count scraped items as success."""
        results = [
            ScrapeResult(media_path=Path("a"), media_type="movie", action="scraped", nfo_written=True),
            ScrapeResult(media_path=Path("b"), media_type="tvshow", action="scraped"),
        ]
        report = _to_step_report(results)
        assert report.success_count == 2

    def test_counts_skipped(self) -> None:
        """Should count skipped items."""
        results = [
            ScrapeResult(media_path=Path("a"), media_type="movie", action="skipped_already_done"),
            ScrapeResult(media_path=Path("b"), media_type="movie", action="skipped_low_confidence"),
        ]
        report = _to_step_report(results)
        assert report.skip_count == 2

    def test_counts_errors(self) -> None:
        """Should count error items and add to warnings."""
        results = [
            ScrapeResult(
                media_path=Path("bad"), media_type="movie",
                action="error", error="API down",
            ),
        ]
        report = _to_step_report(results)
        assert report.error_count == 1
        assert len(report.warnings) == 1
        assert "API down" in report.warnings[0]

    def test_details_include_artwork_count(self) -> None:
        """Details should show artwork download count."""
        results = [
            ScrapeResult(
                media_path=Path("Movie"), media_type="movie",
                action="scraped", artwork_downloaded=["poster.jpg", "landscape.jpg"],
            ),
        ]
        report = _to_step_report(results)
        assert "2 artwork" in report.details[0]

    def test_details_include_episode_count(self) -> None:
        """Details should show renamed episode count."""
        results = [
            ScrapeResult(
                media_path=Path("Show"), media_type="tvshow",
                action="scraped", episodes_renamed=8,
            ),
        ]
        report = _to_step_report(results)
        assert "8 episodes" in report.details[0]


# ---------------------------------------------------------------------------
# run_scrape integration
# ---------------------------------------------------------------------------

class TestRunScrape:
    """Tests for run_scrape function."""

    def test_processes_movies_and_tvshows(self, tmp_path: Path) -> None:
        """Should process both 001-MOVIES and 002-TVSHOWS."""
        settings = MagicMock()
        settings.staging_dir = str(tmp_path)
        settings.movies_dir_name = "001-MOVIES"
        settings.tvshows_dir_name = "002-TVSHOWS"
        settings.tmdb_api_key = "fake"
        settings.tvdb_api_key = "fake"

        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()

        with (
            patch("personalscraper.scraper.run.Scraper") as MockScraper,
        ):
            mock_scraper = MockScraper.return_value
            mock_scraper.process_movies.return_value = []
            mock_scraper.process_tvshows.return_value = []

            report = run_scrape(settings)

        assert report.name == "scrape"
        mock_scraper.process_movies.assert_called_once()
        mock_scraper.process_tvshows.assert_called_once()

    def test_movies_only(self, tmp_path: Path) -> None:
        """--movies-only should skip TV shows."""
        settings = MagicMock()
        settings.staging_dir = str(tmp_path)
        settings.movies_dir_name = "001-MOVIES"
        settings.tvshows_dir_name = "002-TVSHOWS"
        settings.tmdb_api_key = "fake"
        settings.tvdb_api_key = "fake"

        (tmp_path / "001-MOVIES").mkdir()
        (tmp_path / "002-TVSHOWS").mkdir()

        with patch("personalscraper.scraper.run.Scraper") as MockScraper:
            mock_scraper = MockScraper.return_value
            mock_scraper.process_movies.return_value = []

            run_scrape(settings, movies_only=True)

        mock_scraper.process_movies.assert_called_once()
        mock_scraper.process_tvshows.assert_not_called()

    def test_tvshows_only(self, tmp_path: Path) -> None:
        """--tvshows-only should skip movies."""
        settings = MagicMock()
        settings.staging_dir = str(tmp_path)
        settings.movies_dir_name = "001-MOVIES"
        settings.tvshows_dir_name = "002-TVSHOWS"
        settings.tmdb_api_key = "fake"
        settings.tvdb_api_key = "fake"

        (tmp_path / "001-MOVIES").mkdir()
        (tmp_path / "002-TVSHOWS").mkdir()

        with patch("personalscraper.scraper.run.Scraper") as MockScraper:
            mock_scraper = MockScraper.return_value
            mock_scraper.process_tvshows.return_value = []

            run_scrape(settings, tvshows_only=True)

        mock_scraper.process_movies.assert_not_called()
        mock_scraper.process_tvshows.assert_called_once()

"""Tests for scrape progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.pipeline_observer import CollectorObserver
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.run import run_scrape


def _base_config() -> MagicMock:
    config = MagicMock()
    config.paths.staging_dir = Path("/tmp/staging")
    movie_entry = MagicMock()
    movie_entry.id = 1
    movie_entry.file_type = "movie"
    movie_entry.role = "movies"
    tv_entry = MagicMock()
    tv_entry.id = 2
    tv_entry.file_type = "tvshow"
    tv_entry.role = "tvshows"
    config.staging_dirs = [movie_entry, tv_entry]
    config.categories = []
    return config


class TestScrapeProgress:
    """run_scrape emits started → matched / skipped_low_confidence / skipped / error per DESIGN §9."""

    def test_fast_skip_emits_no_events(self) -> None:
        """Fast-skip path: zero events when nothing to scrape and no repair needed."""
        collector = CollectorObserver()

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=False),
            patch("personalscraper.scraper.run._needs_repair", return_value=False),
        ):
            report = run_scrape(MagicMock(), config=_base_config(), dry_run=True, observers=(collector,))

        assert report.name == "scrape"
        assert collector.progress == []

    def test_emits_terminal_status_per_action(self) -> None:
        """Each ScrapeResult.action maps to a distinct StepEvent.status."""
        results = [
            ScrapeResult(media_path=Path("/m/A"), media_type="movie", action="scraped"),
            ScrapeResult(media_path=Path("/m/B"), media_type="movie", action="artwork_recovered"),
            ScrapeResult(media_path=Path("/m/C"), media_type="movie", action="skipped_low_confidence"),
            ScrapeResult(media_path=Path("/m/D"), media_type="movie", action="skipped_already_done"),
            ScrapeResult(media_path=Path("/m/E"), media_type="movie", action="skipped_no_category"),
            ScrapeResult(media_path=Path("/m/F"), media_type="movie", action="error", error="boom"),
        ]

        mock_scraper = MagicMock()
        mock_scraper.process_movies.return_value = results
        mock_scraper.process_tvshows.return_value = []

        collector = CollectorObserver()

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run._needs_repair", return_value=False),
            patch("personalscraper.scraper.run.Scraper", return_value=mock_scraper),
            patch("pathlib.Path.exists", return_value=True),
        ):
            run_scrape(MagicMock(), config=_base_config(), dry_run=True, observers=(collector,))

        statuses = [e.status for e in collector.progress]
        assert statuses.count("started") == 6
        # matched = scraped + artwork_recovered (both map to matched)
        assert statuses.count("matched") == 2
        assert "skipped_low_confidence" in statuses
        # both skipped_already_done and skipped_no_category map to "skipped"
        assert statuses.count("skipped") == 2
        assert "failed" in statuses or "error" in statuses

        # Verify details payload for matched events carries the original action label.
        matched = [e for e in collector.progress if e.status == "matched"]
        actions = {e.details.get("action") for e in matched}
        assert actions == {"scraped", "artwork_recovered"}

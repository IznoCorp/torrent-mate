"""Tests for scrape progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.scraper.run import run_scrape


class TestScrapeProgress:
    """Verify run_scrape accepts and uses observers."""

    @patch("personalscraper.scraper.run._has_unscraped_items", return_value=False)
    def test_accepts_observers_param(self, _has) -> None:
        """run_scrape accepts observers without error."""
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
        movie_entry = MagicMock()
        movie_entry.id = 1
        movie_entry.role = "movies"
        movie_entry.file_type = "movie"
        tv_entry = MagicMock()
        tv_entry.id = 2
        tv_entry.file_type = "tvshow"
        tv_entry.role = "tvshows"
        config.staging_dirs = [movie_entry, tv_entry]
        config.categories = []

        report = run_scrape(settings, config=config, dry_run=True, observers=())
        assert report.name == "scrape"

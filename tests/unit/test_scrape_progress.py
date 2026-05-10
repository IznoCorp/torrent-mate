"""Tests for scrape progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.scraper.run import run_scrape


class TestScrapeProgress:
    """Verify run_scrape accepts and uses observers."""

    def test_accepts_observers_param(self) -> None:
        """run_scrape accepts observers without error."""
        settings = MagicMock()
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

        with patch("personalscraper.scraper.run._has_unscraped_items", return_value=False):
            with patch("personalscraper.scraper.run._needs_repair", return_value=False):
                report = run_scrape(settings, config=config, dry_run=True, observers=())
        assert report.name == "scrape"

    def test_observers_survive_no_crash(self) -> None:
        """Scrape step does not crash with observers attached."""
        settings = MagicMock()
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

        with patch("personalscraper.scraper.run._has_unscraped_items", return_value=False):
            with patch("personalscraper.scraper.run._needs_repair", return_value=False):
                report = run_scrape(settings, config=config, dry_run=True, observers=())
        assert report.name == "scrape"

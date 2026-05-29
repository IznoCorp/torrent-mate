"""Tests for scrape progress events — migrated to EventBus + ``ItemProgressed``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.run import run_scrape
from tests.fixtures.event_bus import CollectingSubscriber


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
    """run_scrape emits started → matched / skipped_low_confidence / skipped / failed per DESIGN §9."""

    def test_fast_skip_emits_no_events(self) -> None:
        """Fast-skip path: zero events when nothing to scrape and no repair needed."""
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=False),
            patch("personalscraper.scraper.run._needs_repair", return_value=False),
        ):
            report = run_scrape(MagicMock(), config=_base_config(), dry_run=True, event_bus=bus, registry=MagicMock())

        assert report.name == "scrape"
        assert collector.received == []

    def test_emits_terminal_status_per_action(self) -> None:
        """Each ScrapeResult.action maps to a distinct ItemProgressed.status."""
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

        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        with (
            patch("personalscraper.scraper.run._has_unscraped_items", return_value=True),
            patch("personalscraper.scraper.run._needs_repair", return_value=False),
            patch("personalscraper.scraper.run.Scraper", return_value=mock_scraper),
            patch("pathlib.Path.exists", return_value=True),
        ):
            run_scrape(MagicMock(), config=_base_config(), dry_run=True, event_bus=bus, registry=MagicMock())

        statuses = [e.status for e in collector.received]
        assert statuses.count("started") == 6
        assert statuses.count("matched") == 2
        assert "skipped_low_confidence" in statuses
        assert statuses.count("skipped") == 2
        assert "failed" in statuses or "error" in statuses

        matched = [e for e in collector.received if e.status == "matched"]
        actions = {e.details.get("action") for e in matched}
        assert actions == {"scraped", "artwork_recovered"}

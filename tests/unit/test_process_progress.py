"""Tests for process progress events — migrated to EventBus + ``ItemProgressed``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.process.run import run_clean, run_cleanup
from tests.fixtures.event_bus import CollectingSubscriber


def _make_config() -> MagicMock:
    config = MagicMock()
    config.paths.staging_dir = Path("/tmp/staging")
    config.fuzzy_match = MagicMock()
    movie_e = MagicMock()
    movie_e.id = 1
    movie_e.file_type = "movie"
    movie_e.role = "movies"
    tv_e = MagicMock()
    tv_e.id = 2
    tv_e.file_type = "tvshow"
    tv_e.role = "tvshows"
    config.staging_dirs = [movie_e, tv_e]
    config.categories = []
    return config


class TestCleanProgress:
    """Verify run_clean emits ``ItemProgressed`` events."""

    @patch("personalscraper.process.reclean.reclean_folders")
    @patch("personalscraper.process.reclean._has_polluted_folders", return_value=False)
    @patch("personalscraper.process.dedup.dedup_folders", return_value=(0, 0))
    def test_accepts_event_bus(self, _dedup, _has, _reclean) -> None:
        """run_clean accepts ``event_bus`` without error."""
        report = run_clean(MagicMock(), config=_make_config(), dry_run=True, event_bus=EventBus())
        assert report.name == "clean"

    @patch("personalscraper.process.reclean.reclean_folders")
    @patch("personalscraper.process.reclean._has_polluted_folders", return_value=False)
    @patch("personalscraper.process.dedup.dedup_folders", return_value=(0, 0))
    def test_emits_started_per_category(self, _dedup, _has, _reclean) -> None:
        """Each category dir emits started + result events."""
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)
        run_clean(MagicMock(), config=_make_config(), dry_run=True, event_bus=bus)

        started = [e for e in collector.received if e.status == "started"]
        assert len(started) >= 2
        assert all(e.step == "clean" for e in started)


class TestCleanupProgress:
    """Verify run_cleanup emits ``ItemProgressed`` events."""

    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    def test_accepts_event_bus(self, _cleanup) -> None:
        """run_cleanup accepts ``event_bus`` without error."""
        _cleanup.return_value = MagicMock(success_count=0, details=[])
        report = run_cleanup(MagicMock(), config=_make_config(), dry_run=True, event_bus=EventBus())
        assert report.name == "cleanup"

    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    def test_emits_started_and_removed(self, _cleanup) -> None:
        """run_cleanup emits started + removed per category."""
        _cleanup.return_value = MagicMock(success_count=3, details=["removed /tmp/x"])
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)
        run_cleanup(MagicMock(), config=_make_config(), dry_run=True, event_bus=bus)

        started = [e for e in collector.received if e.status == "started"]
        removed = [e for e in collector.received if e.status == "removed"]
        assert len(started) >= 2
        assert len(removed) >= 2

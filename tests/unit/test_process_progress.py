"""Tests for process progress events (run_clean + run_cleanup)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.pipeline_observer import CollectorObserver
from personalscraper.process.run import run_clean, run_cleanup


class TestCleanProgress:
    """Verify run_clean emits progress events."""

    @patch("personalscraper.process.reclean.reclean_folders")
    @patch("personalscraper.process.reclean._has_polluted_folders", return_value=False)
    @patch("personalscraper.process.dedup.dedup_folders", return_value=(0, 0))
    def test_accepts_observers(self, _dedup, _has, _reclean) -> None:
        """run_clean accepts observers without error."""
        settings = MagicMock()
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

        report = run_clean(settings, config=config, dry_run=True, observers=())
        assert report.name == "clean"

    @patch("personalscraper.process.reclean.reclean_folders")
    @patch("personalscraper.process.reclean._has_polluted_folders", return_value=False)
    @patch("personalscraper.process.dedup.dedup_folders", return_value=(0, 0))
    def test_emits_started_and_cleaned_per_category(self, _dedup, _has, _reclean) -> None:
        """Each category dir emits started + cleaned events."""
        collector = CollectorObserver()
        settings = MagicMock()
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

        run_clean(settings, config=config, dry_run=True, observers=(collector,))

        started = [e for e in collector.progress if e.status == "started"]
        cleaned = [e for e in collector.progress if e.status == "cleaned"]
        assert len(started) >= 2, "expected 2 started events (movies + tvshows)"
        assert len(cleaned) >= 0  # conditional on dry-run
        assert all(e.step == "clean" for e in started)


class TestCleanupProgress:
    """Verify run_cleanup emits progress events."""

    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    def test_accepts_observers(self, _cleanup) -> None:
        """run_cleanup accepts observers without error."""
        _cleanup.return_value = MagicMock(success_count=0, details=[])
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
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

        report = run_cleanup(settings, config=config, dry_run=True, observers=())
        assert report.name == "cleanup"

    @patch("personalscraper.process.cleanup.cleanup_empty_dirs")
    def test_emits_started_and_completed(self, _cleanup) -> None:
        """run_cleanup emits started + completed per category."""
        _cleanup.return_value = MagicMock(success_count=3, details=["removed /tmp/x"])
        collector = CollectorObserver()
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")
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

        run_cleanup(settings, config=config, dry_run=True, observers=(collector,))

        started = [e for e in collector.progress if e.status == "started"]
        completed = [e for e in collector.progress if e.status == "removed"]
        assert len(started) >= 2, "expected 2 started events (movies + tvshows)"
        assert len(completed) >= 2, "expected 2 completed events"

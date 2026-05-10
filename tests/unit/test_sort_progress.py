"""Tests for sort progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.pipeline_observer import CollectorObserver
from personalscraper.sorter.run import run_sort


class TestSortProgress:
    """Verify run_sort emits per-item progress events."""

    def test_accepts_observers_param(self) -> None:
        """run_sort accepts observers without error."""
        settings = MagicMock()
        staging_dir = Path("/tmp/staging")
        config = MagicMock()
        config.paths.staging_dir = staging_dir
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]

        with patch("personalscraper.sorter.run._has_unsorted_items", return_value=False):
            report = run_sort(
                settings,
                staging_dir=staging_dir,
                dry_run=True,
                config=config,
                observers=(),
            )
        assert report.name == "sort"

    def test_emits_progress_per_item(self) -> None:
        """Each sorted item emits started + result events."""
        from personalscraper.sorter.sorter import Sorter

        collector = CollectorObserver()
        settings = MagicMock()
        staging_dir = Path("/tmp/staging")
        config = MagicMock()
        config.paths.staging_dir = staging_dir
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]

        fake_result = MagicMock()
        fake_result.source = MagicMock()
        fake_result.source.name = "Inception.2010.mkv"
        fake_result.status = "moved"
        fake_result.message = None
        fake_result.destination = Path("/tmp/staging/001-MOVIES/Inception (2010).mkv")

        with patch.object(Sorter, "process", return_value=[fake_result]):
            with patch("personalscraper.sorter.run._has_unsorted_items", return_value=True):
                report = run_sort(
                    settings,
                    staging_dir=staging_dir,
                    dry_run=False,
                    config=config,
                    observers=(collector,),
                )

        assert report.name == "sort"
        started = [e for e in collector.progress if e.status == "started"]
        moved = [e for e in collector.progress if e.status == "moved"]
        assert len(started) >= 1, "expected at least 1 started event"
        assert len(moved) >= 1, "expected at least 1 moved event"
        assert started[0].step == "sort"
        assert moved[0].step == "sort"

    def test_observers_survive_exception(self) -> None:
        """Step continues even if an observer raises."""

        class CrashingObserver(CollectorObserver):
            def on_progress(self, event):
                raise RuntimeError("observer crash")

        crashing = CrashingObserver()
        settings = MagicMock()
        staging_dir = Path("/tmp/staging")
        config = MagicMock()
        config.paths.staging_dir = staging_dir
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]

        with patch("personalscraper.sorter.run._has_unsorted_items", return_value=False):
            report = run_sort(
                settings,
                staging_dir=staging_dir,
                dry_run=True,
                config=config,
                observers=(crashing,),
            )
        # No crash = pass
        assert report.name == "sort"

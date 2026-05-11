"""Tests for ingest progress events."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.ingest.ingest import run_ingest
from personalscraper.pipeline_observer import CollectorObserver, StepEvent


class TestIngestProgress:
    """Verify run_ingest emits per-torrent progress events."""

    @staticmethod
    def _make_config() -> MagicMock:
        config = MagicMock()
        config.paths.staging_dir = MagicMock()
        config.paths.data_dir = MagicMock()
        config.thresholds.min_free_space_staging_gb = 1
        config.thresholds.min_free_space_gb = 10
        config.ingest.min_ratio = 0.0
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]
        return config

    @patch("personalscraper.ingest.ingest.build_active_torrent_client")
    @patch("personalscraper.ingest.ingest.IngestTracker")
    def test_accepts_observers_param(self, _mock_tracker, _mock_client) -> None:
        """run_ingest accepts observers without error."""
        settings = MagicMock()
        config = self._make_config()
        _mock_client.return_value.get_completed.return_value = []

        report = run_ingest(settings, dry_run=True, config=config, observers=())
        assert report.name == "ingest"

    @patch("personalscraper.ingest.ingest.build_active_torrent_client")
    @patch("personalscraper.ingest.ingest.IngestTracker")
    def test_emits_started_event_per_torrent(self, _mock_tracker, _mock_client) -> None:
        """Each torrent emits started and completed/skipped/failed progress events."""
        collector = CollectorObserver()
        settings = MagicMock()
        config = self._make_config()

        mock_torrent = MagicMock()
        mock_torrent.name = "Test.Movie.2024.1080p"
        mock_torrent.hash = "abc123"
        mock_torrent.ratio = 1.5
        _mock_client.return_value.get_completed.return_value = [mock_torrent]
        _mock_client.return_value.get_all_hashes.return_value = {"abc123"}
        _mock_tracker.return_value.is_ingested.return_value = False
        _mock_tracker.return_value.get_entry.return_value = None

        with patch("personalscraper.ingest.ingest._check_disk_space", return_value=True):
            with patch("personalscraper.ingest.ingest._get_dir_size", return_value=1000):
                with patch("personalscraper.ingest.ingest.transfer_torrent", return_value=True):
                    run_ingest(settings, dry_run=True, config=config, observers=(collector,))

        assert len(collector.progress) >= 1
        started = [e for e in collector.progress if e.status == "started"]
        assert len(started) == 1
        assert started[0].item == "Test.Movie.2024.1080p"

    def test_step_event_structure(self) -> None:
        """StepEvent fields are coherent."""
        event = StepEvent(
            step="ingest",
            item="Some.Torrent.2024.1080p",
            status="copied",
            details={"action": "copied", "dest": "/tmp/dest"},
        )
        assert event.step == "ingest"
        assert event.status == "copied"

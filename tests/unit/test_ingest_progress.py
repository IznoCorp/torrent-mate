"""Tests for ingest progress events — migrated to EventBus + ``ItemProgressed``."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.ingest.ingest import run_ingest
from personalscraper.pipeline_events import ItemProgressed
from tests.fixtures.event_bus import CollectingSubscriber


class TestIngestProgress:
    """Verify run_ingest emits per-torrent ``ItemProgressed`` events on the bus."""

    @staticmethod
    def _make_config() -> MagicMock:
        config = MagicMock()
        config.paths.staging_dir = MagicMock()
        config.paths.data_dir = Path(
            tempfile.mkdtemp()
        )  # real empty dir: PauseController reads data_dir/'pipeline.pause'
        config.thresholds.min_free_space_staging_gb = 1
        config.thresholds.min_free_space_gb = 10
        config.ingest.min_ratio = 0.0
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]
        return config

    @patch("personalscraper.ingest.ingest.IngestTracker")
    def test_accepts_event_bus_param(self, _mock_tracker) -> None:
        """run_ingest accepts ``event_bus`` without error."""
        mock_client = MagicMock()
        mock_client.get_completed.return_value = []
        report = run_ingest(
            MagicMock(), dry_run=True, config=self._make_config(), event_bus=EventBus(), torrent_client=mock_client
        )
        assert report.name == "ingest"

    @patch("personalscraper.ingest.ingest.IngestTracker")
    def test_emits_started_event_per_torrent(self, _mock_tracker) -> None:
        """Each torrent emits started and completed/skipped/failed progress events."""
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        mock_torrent = MagicMock()
        mock_torrent.name = "Test.Movie.2024.1080p"
        mock_torrent.hash = "abc123"
        mock_torrent.ratio = 1.5
        mock_client = MagicMock()
        mock_client.get_completed.return_value = [mock_torrent]
        mock_client.get_all_hashes.return_value = {"abc123"}
        _mock_tracker.return_value.is_ingested.return_value = False
        _mock_tracker.return_value.get_entry.return_value = None

        with patch("personalscraper.ingest.ingest._check_disk_space", return_value=True):
            with patch("personalscraper.ingest.ingest._get_dir_size", return_value=1000):
                with patch("personalscraper.ingest.ingest.transfer_torrent", return_value=True):
                    run_ingest(
                        MagicMock(), dry_run=True, config=self._make_config(), event_bus=bus, torrent_client=mock_client
                    )

        assert len(collector.received) >= 1
        started = [e for e in collector.received if e.status == "started"]
        assert len(started) == 1
        assert started[0].item == "Test.Movie.2024.1080p"

    def test_item_progressed_structure(self) -> None:
        """``ItemProgressed`` fields are coherent — replaces the legacy progress-event shape test."""
        event = ItemProgressed(
            step="ingest",
            item="Some.Torrent.2024.1080p",
            status="copied",
            details={"action": "copied", "dest": "/tmp/dest"},
        )
        assert event.step == "ingest"
        assert event.status == "copied"

    @patch("personalscraper.ingest.ingest.IngestTracker")
    def test_already_ingested_emits_skipped(self, _mock_tracker) -> None:
        """A torrent already recorded in the tracker emits a skipped event."""
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        torrent = MagicMock()
        torrent.name = "Already.Ingested.2024"
        torrent.hash = "deadbeef"
        torrent.ratio = 2.0
        mock_client = MagicMock()
        mock_client.get_completed.return_value = [torrent]
        mock_client.get_all_hashes.return_value = {"deadbeef"}
        _mock_tracker.return_value.is_ingested.return_value = True
        tracker_entry = MagicMock()
        tracker_entry.dest_path = "/non/existent/path"
        _mock_tracker.return_value.get_entry.return_value = tracker_entry

        run_ingest(MagicMock(), dry_run=True, config=self._make_config(), event_bus=bus, torrent_client=mock_client)

        skipped = [e for e in collector.received if e.status == "skipped"]
        assert len(skipped) == 1
        assert skipped[0].details["reason"] == "already_ingested"

    @patch("personalscraper.ingest.ingest.IngestTracker")
    def test_ratio_below_threshold_emits_skipped(self, _mock_tracker) -> None:
        """A torrent under config.ingest.min_ratio emits a skipped event."""
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)
        config = self._make_config()
        config.ingest.min_ratio = 2.0

        torrent = MagicMock()
        torrent.name = "LowRatio.2024"
        torrent.hash = "low1"
        torrent.ratio = 0.5
        mock_client = MagicMock()
        mock_client.get_completed.return_value = [torrent]
        mock_client.get_all_hashes.return_value = {"low1"}
        _mock_tracker.return_value.is_ingested.return_value = False
        _mock_tracker.return_value.get_entry.return_value = None

        run_ingest(MagicMock(), dry_run=True, config=config, event_bus=bus, torrent_client=mock_client)

        skipped = [e for e in collector.received if e.status == "skipped"]
        assert len(skipped) == 1
        assert skipped[0].details["reason"] == "ratio_below_threshold"

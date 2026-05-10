"""Tests for trailers progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.pipeline_observer import CollectorObserver
from personalscraper.trailers.step import run_trailers


class TestTrailersProgress:
    """Verify run_trailers accepts and uses observers."""

    @patch("personalscraper.trailers.orchestrator.TrailersOrchestrator")
    def test_accepts_observers(self, _orch) -> None:
        """run_trailers accepts observers without error."""
        _orch.return_value.run.return_value = {}
        _orch.return_value.failed_items = []
        _orch.return_value.item_results = []
        config = MagicMock()
        config.trailers.enabled = True
        staging_dir = Path("/tmp/staging")

        report = run_trailers(config, staging_dir=staging_dir, verified=[], observers=())
        assert report.name == "trailers"

    @patch("personalscraper.trailers.orchestrator.TrailersOrchestrator")
    def test_emits_per_item_from_orchestrator(self, _orch) -> None:
        """Per-item results from orchestrator are emitted as progress events."""
        _orch.return_value.run.return_value = {
            "downloaded": 1,
            "already_present": 0,
            "skipped_by_state": 0,
            "error": 0,
            "bot_detected": 0,
        }
        _orch.return_value.failed_items = []
        _orch.return_value.item_results = [("/tmp/Inception (2010)", "downloaded", "downloaded")]

        collector = CollectorObserver()
        config = MagicMock()
        config.trailers.enabled = True
        staging_dir = Path("/tmp/staging")

        run_trailers(config, staging_dir=staging_dir, verified=[MagicMock()], observers=(collector,))

        downloaded = [e for e in collector.progress if e.status == "downloaded"]
        assert len(downloaded) >= 1, f"expected >=1 downloaded event, got {len(downloaded)}"
        assert "Inception" in downloaded[0].item

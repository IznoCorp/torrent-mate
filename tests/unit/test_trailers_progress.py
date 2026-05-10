"""Tests for trailers progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.trailers.step import run_trailers


class TestTrailersProgress:
    """Verify run_trailers accepts and uses observers."""

    @patch("personalscraper.trailers.orchestrator.TrailersOrchestrator")
    def test_accepts_observers(self, _orch) -> None:
        """run_trailers accepts observers without error."""
        _orch.return_value.run.return_value = {}
        _orch.return_value.failed_items = []
        config = MagicMock()
        config.trailers.enabled = True
        staging_dir = Path("/tmp/staging")

        report = run_trailers(
            config,
            staging_dir=staging_dir,
            verified=[],
            observers=(),
        )
        assert report.name == "trailers"

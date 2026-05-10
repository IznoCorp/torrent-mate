"""Tests for dispatch progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.dispatch.run import run_dispatch


class TestDispatchProgress:
    """Verify run_dispatch emits per-item progress events."""

    @patch("personalscraper.dispatch.dispatcher.Dispatcher")
    @patch("personalscraper.dispatch.media_index.MediaIndex")
    
    def test_accepts_observers(self, _disp, _idx) -> None:
        """run_dispatch accepts observers without error."""
        _disp.return_value.process.return_value = []
        _idx.return_value.rebuild.return_value = 0
        settings = MagicMock()
        config = MagicMock()
        config.disks = []
        config.paths.staging_dir = Path("/tmp/staging")
        config.paths.data_dir = Path("/tmp/.data")
        config.indexer.db_path = Path("/tmp/.data/library.db")
        config.categories = []
        config.staging_dirs = []

        report = run_dispatch(
            settings, config=config, dry_run=True,
            verified=[], observers=(),
        )
        assert report.name == "dispatch"

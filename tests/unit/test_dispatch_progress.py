"""Tests for dispatch progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.dispatch.run import run_dispatch


class TestDispatchProgress:
    """Verify run_dispatch accepts and uses observers."""

    @patch("personalscraper.dispatch.dispatcher.Dispatcher")
    @patch("personalscraper.dispatch.media_index.MediaIndex")
    def test_accepts_observers(self, _idx, _disp) -> None:
        """run_dispatch accepts observers without error."""
        _disp.return_value.process.return_value = []
        _idx.return_value.rebuild.return_value = 0
        _idx.return_value.count = 0
        _idx.return_value.__enter__ = MagicMock(return_value=_idx.return_value)
        _idx.return_value.__exit__ = MagicMock(return_value=False)
        settings = MagicMock()
        config = MagicMock()
        config.disks = []
        config.paths.staging_dir = Path("/tmp/staging")
        config.paths.data_dir = Path("/tmp/.data")
        config.indexer.db_path = Path("/tmp/.data/library.db")
        config.categories = []
        config.staging_dirs = []

        report = run_dispatch(settings, config=config, dry_run=True, verified=[], observers=())
        assert report.name == "dispatch"

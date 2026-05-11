"""Tests for dispatch progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.run import run_dispatch
from personalscraper.pipeline_observer import CollectorObserver


def _base_config() -> MagicMock:
    """Build a minimal Config mock suitable for run_dispatch."""
    config = MagicMock()
    config.disks = []
    config.paths.staging_dir = Path("/tmp/staging")
    config.paths.data_dir = Path("/tmp/.data")
    config.indexer.db_path = Path("/tmp/.data/library.db")
    config.categories = []
    config.staging_dirs = []
    return config


def _patch_index(_idx) -> None:
    """Configure the MediaIndex mock so the context manager works."""
    _idx.return_value.rebuild.return_value = 0
    _idx.return_value.count = 0
    _idx.return_value.__enter__ = MagicMock(return_value=_idx.return_value)
    _idx.return_value.__exit__ = MagicMock(return_value=False)


class TestDispatchProgress:
    """run_dispatch emits started → moved/merged/replaced/skipped/error (DESIGN §9)."""

    @patch("personalscraper.dispatch.run.Dispatcher")
    @patch("personalscraper.dispatch.run.MediaIndex")
    def test_no_results_emits_no_events(self, _idx, _disp) -> None:
        """Empty dispatcher result set → no per-item events."""
        _patch_index(_idx)
        _disp.return_value.process.return_value = []
        collector = CollectorObserver()

        report = run_dispatch(MagicMock(), config=_base_config(), dry_run=True, verified=[], observers=(collector,))

        assert report.name == "dispatch"
        assert collector.progress == []

    @patch("personalscraper.dispatch.run.Dispatcher")
    @patch("personalscraper.dispatch.run.MediaIndex")
    def test_emits_terminal_status_per_action(self, _idx, _disp) -> None:
        """Each action label maps to a distinct terminal event status."""
        _patch_index(_idx)
        results = [
            DispatchResult(source=Path("/a"), destination=Path("/disk/a"), disk="d1", action="moved"),
            DispatchResult(source=Path("/b"), destination=Path("/disk/b"), disk="d1", action="merged"),
            DispatchResult(source=Path("/c"), destination=Path("/disk/c"), disk="d1", action="replaced"),
            DispatchResult(source=Path("/d"), action="skipped", reason="duplicate"),
            DispatchResult(source=Path("/e"), action="error", reason="disk_full"),
        ]
        _disp.return_value.process.return_value = results
        collector = CollectorObserver()

        run_dispatch(MagicMock(), config=_base_config(), dry_run=True, verified=[], observers=(collector,))

        statuses = [e.status for e in collector.progress]
        # Each result contributes started + terminal → 10 events total.
        assert statuses.count("started") == 5
        assert "moved" in statuses
        assert "merged" in statuses
        assert "replaced" in statuses
        assert "skipped" in statuses
        assert "error" in statuses

        skipped = [e for e in collector.progress if e.status == "skipped"][0]
        assert skipped.details["reason"] == "duplicate"
        error = [e for e in collector.progress if e.status == "error"][0]
        assert error.details["reason"] == "disk_full"

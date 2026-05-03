"""Tests for the dispatch step runner."""

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.conf.models.disks import DiskConfig
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.run import _to_step_report, run_dispatch
from tests.fixtures.config import CANONICAL_STAGING_DIRS


class TestToStepReport:
    """Tests for _to_step_report conversion."""

    def test_counts(self) -> None:
        """Should count replaced/merged/moved as success."""
        results = [
            DispatchResult(source=Path("a"), action="replaced", disk="Disk1"),
            DispatchResult(source=Path("b"), action="merged", disk="Disk2"),
            DispatchResult(source=Path("c"), action="moved", disk="Disk1"),
            DispatchResult(source=Path("d"), action="skipped", reason="no space"),
            DispatchResult(source=Path("e"), action="error", reason="rsync failed"),
        ]
        report = _to_step_report(results)
        assert report.success_count == 3
        assert report.skip_count == 1
        assert report.error_count == 1
        assert report.name == "dispatch"


class TestRunDispatch:
    """Tests for run_dispatch function."""

    def test_runs_with_mocked_dispatcher(self, tmp_path: Path) -> None:
        """Should create dispatcher and process."""
        settings = MagicMock()
        settings.movies_dir_name = "001-MOVIES"
        settings.tvshows_dir_name = "002-TVSHOWS"

        config = MagicMock()
        config.paths.staging_dir = tmp_path
        config.paths.data_dir = tmp_path / ".data"
        config.indexer.db_path = tmp_path / ".data" / "library.db"
        config.disks = []
        config.staging_dirs = CANONICAL_STAGING_DIRS

        with (
            patch("personalscraper.dispatch.run.Dispatcher") as MockDisp,
            patch("personalscraper.dispatch.run.MediaIndex") as MockIdx,
        ):
            mock_idx = MockIdx.return_value
            # run_dispatch now uses ``with MediaIndex(...) as index:``;
            # configure __enter__ to return the same mock instance so that
            # assertions on mock_idx still target the object inside the block.
            mock_idx.__enter__ = MagicMock(return_value=mock_idx)
            mock_idx.__exit__ = MagicMock(return_value=False)
            mock_idx.count = 5  # non-zero so rebuild branch is skipped
            mock_disp = MockDisp.return_value
            mock_disp.process.return_value = []

            report = run_dispatch(settings, config=config, dry_run=True)

        assert report.name == "dispatch"
        MockIdx.assert_called_once_with(config.indexer.db_path, config=config, auto_rebuild=False)
        mock_idx.begin_preview.assert_called_once()
        mock_idx.rebuild.assert_not_called()  # count=5 > 0 skips rebuild

    def test_dry_run_empty_index_rebuild_is_rolled_back(self, tmp_path: Path) -> None:
        """Dry-run can preview with a rebuilt index without persisting cache rows."""
        settings = MagicMock()
        settings.movies_dir_name = "001-MOVIES"
        settings.tvshows_dir_name = "002-TVSHOWS"

        disk_root = tmp_path / "disk" / "medias"
        (disk_root / "movies" / "Existing Movie (2024)").mkdir(parents=True)

        config = MagicMock()
        config.paths.staging_dir = tmp_path / "staging"
        config.paths.data_dir = tmp_path / ".data"
        config.indexer.db_path = tmp_path / ".data" / "library.db"
        config.disks = [DiskConfig(id="disk_1", path=disk_root, categories=["movies"])]
        config.categories = {}
        config.staging_dirs = CANONICAL_STAGING_DIRS

        report = run_dispatch(settings, config=config, dry_run=True, verified=[])

        assert report.name == "dispatch"
        with sqlite3.connect(config.indexer.db_path) as conn:
            media_items = conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0]
            dispatch_attrs = conn.execute(
                "SELECT COUNT(*) FROM item_attribute WHERE key = 'dispatch_normalized_title'"
            ).fetchone()[0]

        assert media_items == 0
        assert dispatch_attrs == 0

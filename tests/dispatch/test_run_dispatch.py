"""Tests for the dispatch step runner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.dispatch.dispatcher import DispatchResult
from personalscraper.dispatch.run import _to_step_report, run_dispatch


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
        config.disks = []

        with (
            patch("personalscraper.dispatch.run.Dispatcher") as MockDisp,
            patch("personalscraper.dispatch.run.MediaIndex") as MockIdx,
        ):
            mock_idx = MockIdx.return_value
            mock_disp = MockDisp.return_value
            mock_disp.process.return_value = []

            report = run_dispatch(settings, config=config, dry_run=True)

        assert report.name == "dispatch"
        mock_idx.load.assert_called_once()

"""Tests for personalscraper.pipeline — sequential exhaustive orchestrator."""

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline import Pipeline


@pytest.fixture
def pipeline_settings(tmp_path):
    """Provide a mock Settings for pipeline tests.

    V15 P6.5: ingest_dir is a method (not a property), staging_dir is
    supplied via Config.paths in production. The mock supports both
    patterns used in pipeline code.
    """
    s = MagicMock()
    s.staging_dir = tmp_path
    ingest_dir_path = tmp_path / "097-TEMP"
    ingest_dir_path.mkdir()
    s.ingest_dir.side_effect = lambda staging_dir: staging_dir / "097-TEMP"
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    return s


@pytest.fixture
def pipeline_config(tmp_path):
    """Provide a mock Config for pipeline tests."""
    config = MagicMock()
    config.paths.staging_dir = tmp_path
    config.paths.data_dir = tmp_path / ".data"
    config.disks = []
    return config


@pytest.fixture
def quiet_console():
    """Console that suppresses output for clean test logs."""
    return Console(quiet=True)


class TestRunStep:
    """Tests for Pipeline._run_step method."""

    def test_normal_step_report(self, pipeline_config, pipeline_settings, quiet_console):
        """Normal step function returning StepReport."""
        pipeline = Pipeline(pipeline_config, pipeline_settings, console=quiet_console)
        report = PipelineReport(started_at=MagicMock())
        sr = StepReport(name="test", success_count=3)

        result = pipeline._run_step("test", lambda: sr, report)

        assert result is None
        assert report.steps["test"].success_count == 3

    def test_tuple_return_extracts_extra(self, pipeline_config, pipeline_settings, quiet_console):
        """Step returning (StepReport, extra_data) extracts both."""
        pipeline = Pipeline(pipeline_config, pipeline_settings, console=quiet_console)
        report = PipelineReport(started_at=MagicMock())
        sr = StepReport(name="verify", success_count=5)
        extra_data = [{"path": "/some/path"}]

        result = pipeline._run_step("verify", lambda: (sr, extra_data), report)

        assert result == extra_data
        assert report.steps["verify"].success_count == 5

    def test_exception_creates_error_report(self, pipeline_config, pipeline_settings, quiet_console):
        """Fatal exception creates StepReport with error details."""
        pipeline = Pipeline(pipeline_config, pipeline_settings, console=quiet_console)
        report = PipelineReport(started_at=MagicMock())

        def failing_step():
            raise RuntimeError("disk full")

        result = pipeline._run_step("ingest", failing_step, report)

        assert result is None
        assert report.steps["ingest"].error_count == 1
        assert "RuntimeError: disk full" in report.steps["ingest"].details[0]


class TestPipelineRun:
    """Tests for Pipeline.run orchestration."""

    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    def test_runs_all_phases_in_order(
        self,
        mock_ingest,
        mock_sort,
        pipeline_config,
        pipeline_settings,
        quiet_console,
    ):
        """Pipeline executes ingest→sort→gate→process→enforce→verify→dispatch."""
        mock_ingest.return_value = StepReport(name="ingest", success_count=2)
        mock_sort.return_value = StepReport(name="sort", success_count=2)

        with (
            patch("personalscraper.sorter.run.assert_temp_empty", return_value=[]),
            patch("personalscraper.scraper.run.run_scrape", return_value=StepReport(name="scrape")),
            patch("personalscraper.enforce.run.run_enforce", return_value=StepReport(name="enforce")),
            patch("personalscraper.verify.run.run_verify") as mock_verify,
            patch("personalscraper.dispatch.run.run_dispatch") as mock_dispatch,
        ):
            mock_verify.return_value = (
                StepReport(name="verify", success_count=2),
                [MagicMock()],  # dispatchable items
            )
            mock_dispatch.return_value = StepReport(name="dispatch", success_count=2)

            pipeline = Pipeline(pipeline_config, pipeline_settings, console=quiet_console)
            report = pipeline.run()

        assert len(report.steps) == 8
        assert list(report.steps.keys()) == [
            "ingest",
            "sort",
            "clean",
            "scrape",
            "cleanup",
            "enforce",
            "verify",
            "dispatch",
        ]

    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    def test_dispatch_skipped_when_no_verified(
        self,
        mock_ingest,
        mock_sort,
        pipeline_config,
        pipeline_settings,
        quiet_console,
    ):
        """Dispatch is skipped when verify returns no dispatchable items."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")

        with (
            patch("personalscraper.sorter.run.assert_temp_empty", return_value=[]),
            patch("personalscraper.scraper.run.run_scrape", return_value=StepReport(name="scrape")),
            patch("personalscraper.verify.run.run_verify") as mock_verify,
        ):
            mock_verify.return_value = (
                StepReport(name="verify", error_count=3),
                [],  # no dispatchable items
            )

            pipeline = Pipeline(pipeline_config, pipeline_settings, console=quiet_console)
            report = pipeline.run()

        assert report.steps["dispatch"].skip_count == 1
        assert "no verified items" in report.steps["dispatch"].details[0].lower()

    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    def test_dispatch_skipped_when_verify_crashes(
        self,
        mock_ingest,
        mock_sort,
        pipeline_config,
        pipeline_settings,
        quiet_console,
    ):
        """Dispatch is skipped when verify step crashes (returns None)."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")

        with (
            patch("personalscraper.sorter.run.assert_temp_empty", return_value=[]),
            patch("personalscraper.scraper.run.run_scrape", return_value=StepReport(name="scrape")),
            patch("personalscraper.verify.run.run_verify", side_effect=RuntimeError("boom")),
        ):
            pipeline = Pipeline(pipeline_config, pipeline_settings, console=quiet_console)
            report = pipeline.run()

        # verify has error, dispatch is skipped
        assert report.steps["verify"].error_count == 1
        assert report.steps["dispatch"].skip_count == 1

    @patch("personalscraper.sorter.run.run_sort")
    @patch("personalscraper.ingest.ingest.run_ingest")
    def test_gate_warning_does_not_block(
        self,
        mock_ingest,
        mock_sort,
        pipeline_config,
        pipeline_settings,
        quiet_console,
    ):
        """Gate 097-TEMP not empty logs warning but pipeline continues."""
        mock_ingest.return_value = StepReport(name="ingest")
        mock_sort.return_value = StepReport(name="sort")

        with (
            patch("personalscraper.sorter.run.assert_temp_empty", return_value=["leftover.mkv"]),
            patch("personalscraper.scraper.run.run_scrape", return_value=StepReport(name="scrape")),
            patch("personalscraper.verify.run.run_verify") as mock_verify,
        ):
            mock_verify.return_value = (StepReport(name="verify"), [])

            pipeline = Pipeline(pipeline_config, pipeline_settings, console=quiet_console)
            report = pipeline.run()

        # Pipeline continued despite gate warning
        assert "verify" in report.steps
        assert "dispatch" in report.steps


class TestCrashRecovery:
    """Tests for _recover_from_previous_run cleanup."""

    def _make_config(self, staging_dir: Path) -> MagicMock:
        """Build a minimal Config mock for crash recovery tests.

        Includes a staging_dirs entry with role='ingest' (097-TEMP) so that
        find_ingest_dir() resolves correctly in _recover_from_previous_run.

        Args:
            staging_dir: Root staging directory for the test.

        Returns:
            A MagicMock Config with paths and staging_dirs configured.
        """
        config = MagicMock()
        config.paths.staging_dir = staging_dir
        config.paths.data_dir = staging_dir / ".data"
        config.disks = []
        # Provide a real ingest staging entry so find_ingest_dir() resolves.
        ingest_entry = MagicMock()
        ingest_entry.id = 97
        ingest_entry.name = "temp"
        ingest_entry.role = "ingest"
        config.staging_dirs = [ingest_entry]
        return config

    def test_expired_lockout_cleaned(self, tmp_path: Path) -> None:
        """Expired qBit lockout file (>1h) should be removed at startup."""
        lockout = tmp_path / ".cache" / "personalscraper" / "qbit_auth_lockout"
        lockout.parent.mkdir(parents=True)
        lockout.write_text("login_failed")
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        os.utime(lockout, (old_time, old_time))

        (tmp_path / "097-TEMP").mkdir()
        settings = MagicMock()

        pipeline = Pipeline(self._make_config(tmp_path), settings, dry_run=False)
        pipeline._recover_from_previous_run(lockout_path=lockout)

        assert not lockout.exists()

    def test_non_expired_lockout_kept(self, tmp_path: Path) -> None:
        """Recent lockout file (<1h) should NOT be removed."""
        lockout = tmp_path / ".cache" / "personalscraper" / "qbit_auth_lockout"
        lockout.parent.mkdir(parents=True)
        lockout.write_text("login_failed")

        (tmp_path / "097-TEMP").mkdir()
        settings = MagicMock()

        pipeline = Pipeline(self._make_config(tmp_path), settings, dry_run=False)
        pipeline._recover_from_previous_run(lockout_path=lockout)

        assert lockout.exists()

    def test_orphan_tmp_dispatch_cleaned(self, tmp_path: Path) -> None:
        """Orphan _tmp_dispatch_* dirs on storage disks should be removed."""
        # Simulate a storage disk with an orphan
        disk_path = tmp_path / "Disk1" / "medias"
        category = disk_path / "films"
        orphan = category / "_tmp_dispatch_Movie (2025)"
        orphan.mkdir(parents=True)
        (orphan / "file.mkv").write_bytes(b"\x00" * 100)

        disk_config = MagicMock()
        disk_config.path = disk_path

        (tmp_path / "097-TEMP").mkdir()
        settings = MagicMock()

        config = self._make_config(tmp_path)
        config.disks = [disk_config]  # inject disk with orphan directly
        pipeline = Pipeline(config, settings, dry_run=False)
        pipeline._recover_from_previous_run(lockout_path=tmp_path / "nonexistent_lockout")

        assert not orphan.exists()

    def test_orphan_ingest_tmp_cleaned(self, tmp_path: Path) -> None:
        """Orphan .ingest_tmp_* dirs in staging should be removed."""
        ingest_dir = tmp_path / "097-TEMP"
        ingest_dir.mkdir()
        orphan = ingest_dir / ".ingest_tmp_Movie"
        orphan.mkdir()
        (orphan / "file.mkv").write_bytes(b"\x00" * 100)

        settings = MagicMock()

        pipeline = Pipeline(self._make_config(tmp_path), settings, dry_run=False)
        pipeline._recover_from_previous_run(lockout_path=tmp_path / "nonexistent_lockout")

        assert not orphan.exists()

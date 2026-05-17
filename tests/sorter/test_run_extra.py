"""Additional coverage tests for ``personalscraper.sorter.run``.

Targets the residual gaps in ``run_sort``:

* ``status == "skipped"`` and ``status == "error"`` aggregation branches.
* The tracker prune fallback when ``IngestTracker`` raises.

These complement ``test_run.py`` which covers the happy paths and
``assert_temp_empty``.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.conf.models.config import Config
from personalscraper.core.event_bus import EventBus
from personalscraper.models import SortResult
from personalscraper.sorter.run import run_sort
from tests.fixtures.config import CANONICAL_STAGING_DIRS


@pytest.fixture
def gate_settings() -> MagicMock:
    """Return a minimal Settings mock used by ``run_sort``."""
    s = MagicMock()
    s.ingest_dir_name = "097-TEMP"
    return s


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Return a Config with canonical staging dirs rooted at ``tmp_path``."""
    return Config.model_validate(
        {
            "paths": {
                "torrent_complete_dir": str(tmp_path / "torrents"),
                "staging_dir": str(tmp_path / "staging"),
                "data_dir": str(tmp_path / ".data"),
            },
            "disks": [{"id": "disk_a", "path": str(tmp_path / "disk_a"), "categories": ["movies"]}],
            "staging_dirs": [s.model_dump() for s in CANONICAL_STAGING_DIRS],
        }
    )


def _seed_ingest(config: Config, name: str = "leftover.mkv") -> Path:
    """Create the ingest dir with a single visible item.

    Args:
        config: Pipeline config used to resolve the staging path.
        name: File name to create in the ingest directory.

    Returns:
        Path to the seeded item inside the ingest dir.
    """
    staging = config.paths.staging_dir
    staging.mkdir(parents=True, exist_ok=True)
    ingest = staging / "097-TEMP"
    ingest.mkdir(parents=True, exist_ok=True)
    item = ingest / name
    item.write_text("payload")
    return item


def _make_sort_result(
    source: Path,
    *,
    status: str,
    message: str | None = None,
) -> SortResult:
    """Build a minimal ``SortResult`` for ``run_sort`` aggregation tests."""
    return SortResult(
        source=source,
        destination=source.parent / "elsewhere" / source.name,
        media_type="movie",
        title=source.stem,
        year=None,
        season=None,
        episode=None,
        status=status,
        message=message,
    )


class TestRunSortStatusBranches:
    """Cover the skipped/error branches of ``run_sort``."""

    def test_skipped_status_increments_skip_count_with_message(self, gate_settings: MagicMock, config: Config) -> None:
        """A ``skipped`` SortResult with a message lands in warnings + skip_count."""
        item = _seed_ingest(config, "skip_me.mkv")
        skipped_result = _make_sort_result(item, status="skipped", message="Already exists")

        with patch("personalscraper.sorter.run.Sorter") as MockSorter:
            MockSorter.return_value.process.return_value = [skipped_result]
            report = run_sort(gate_settings, staging_dir=config.paths.staging_dir, config=config, event_bus=EventBus())

        assert report.skip_count == 1
        assert report.success_count == 0
        assert any("Already exists" in w for w in report.warnings)

    def test_skipped_status_without_message_no_warning(self, gate_settings: MagicMock, config: Config) -> None:
        """A ``skipped`` SortResult without a message increments skip_count silently."""
        item = _seed_ingest(config, "no_msg.mkv")
        skipped_result = _make_sort_result(item, status="skipped", message=None)

        with patch("personalscraper.sorter.run.Sorter") as MockSorter:
            MockSorter.return_value.process.return_value = [skipped_result]
            report = run_sort(gate_settings, staging_dir=config.paths.staging_dir, config=config, event_bus=EventBus())

        assert report.skip_count == 1
        assert report.warnings == []

    def test_error_status_increments_error_count_and_warnings(self, gate_settings: MagicMock, config: Config) -> None:
        """An ``error`` SortResult lands in error_count + a warning entry."""
        item = _seed_ingest(config, "broken.mkv")
        error_result = _make_sort_result(item, status="error", message="Permission denied")

        with patch("personalscraper.sorter.run.Sorter") as MockSorter:
            MockSorter.return_value.process.return_value = [error_result]
            report = run_sort(gate_settings, staging_dir=config.paths.staging_dir, config=config, event_bus=EventBus())

        assert report.error_count == 1
        assert any("Permission denied" in w for w in report.warnings)
        assert any("ERROR" in w for w in report.warnings)


class TestRunSortTrackerPruneFailure:
    """Cover the best-effort tracker prune fallback branch."""

    def test_tracker_prune_failure_logs_and_continues(self, gate_settings: MagicMock, config: Config) -> None:
        """A failure inside ``IngestTracker.prune_consumed_dest_paths`` is swallowed."""
        item = _seed_ingest(config, "ok.mkv")
        moved_result = _make_sort_result(item, status="moved")

        with (
            patch("personalscraper.sorter.run.Sorter") as MockSorter,
            patch("personalscraper.ingest.tracker.IngestTracker") as MockTracker,
        ):
            MockSorter.return_value.process.return_value = [moved_result]
            MockTracker.return_value.prune_consumed_dest_paths.side_effect = RuntimeError("tracker boom")

            report = run_sort(gate_settings, staging_dir=config.paths.staging_dir, config=config, event_bus=EventBus())

        # The success path still succeeded; tracker exception did not propagate.
        assert report.success_count == 1
        # No phantom error/warning bookkeeping leak from the swallowed exception.
        assert report.error_count == 0

    def test_tracker_prune_emits_log_when_pruned_paths_returned(self, gate_settings: MagicMock, config: Config) -> None:
        """When the tracker reports pruned paths the success branch still logs them.

        Exercises the ``if pruned: log.info(...)`` line that previously had no
        coverage when prune returned a truthy list.
        """
        item = _seed_ingest(config, "kept.mkv")
        moved_result = _make_sort_result(item, status="moved")

        with (
            patch("personalscraper.sorter.run.Sorter") as MockSorter,
            patch("personalscraper.ingest.tracker.IngestTracker") as MockTracker,
        ):
            MockSorter.return_value.process.return_value = [moved_result]
            MockTracker.return_value.prune_consumed_dest_paths.return_value = ["stale_entry"]

            report = run_sort(gate_settings, staging_dir=config.paths.staging_dir, config=config, event_bus=EventBus())

        assert report.success_count == 1

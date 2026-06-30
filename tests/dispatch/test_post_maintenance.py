"""Unit tests for post-dispatch index maintenance hook."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.dispatch.post_maintenance import run_post_dispatch_maintenance


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock Config with a resolved indexer.db_path."""
    cfg = MagicMock()
    cfg.indexer.db_path = "/tmp/test_library.db"
    cfg.indexer.post_dispatch_maintenance.enabled = True
    return cfg


def test_empty_touched_disks_no_op(mock_config: MagicMock) -> None:
    """Empty touched_disks set skips all steps — no scan nor relink nor fix."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental") as mock_scan,
        patch("personalscraper.dispatch.post_maintenance._run_relink") as mock_relink,
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts") as mock_fix,
    ):
        run_post_dispatch_maintenance(mock_config, set(), enabled=True)
        mock_scan.assert_not_called()
        mock_relink.assert_not_called()
        mock_fix.assert_not_called()


def test_disabled_no_op(mock_config: MagicMock) -> None:
    """When enabled=False, the function is a no-op even with touched disks."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental") as mock_scan,
        patch("personalscraper.dispatch.post_maintenance._run_relink") as mock_relink,
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts") as mock_fix,
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1", "disk_2"}, enabled=False)
        mock_scan.assert_not_called()
        mock_relink.assert_not_called()
        mock_fix.assert_not_called()


def test_sequential_per_disk_scan(mock_config: MagicMock) -> None:
    """Each touched disk gets an incremental scan call, sequentially."""
    touched = {"disk_1", "disk_2"}
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0) as mock_scan,
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
    ):
        run_post_dispatch_maintenance(mock_config, touched, enabled=True)
        assert mock_scan.call_count == 2
        # Verify per-disk calls (sorted order)
        mock_scan.assert_any_call(mock_config, "disk_1")
        mock_scan.assert_any_call(mock_config, "disk_2")


def test_relink_and_fix_called_after_scans(mock_config: MagicMock) -> None:
    """Relink and fix-season-counts are each called exactly once after all scans."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0) as mock_scan,
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 3, "unmatched": 0, "errors": 0},
        ) as mock_relink,
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=5) as mock_fix,
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)
        mock_scan.assert_called_once()
        mock_relink.assert_called_once()
        mock_fix.assert_called_once()


def test_fail_soft_scan_exception_swallowed(mock_config: MagicMock) -> None:
    """An exception in a scan step is caught and does NOT propagate."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", side_effect=RuntimeError("boom")),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
    ):
        # Must not raise
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)


def test_fail_soft_relink_exception_swallowed(mock_config: MagicMock) -> None:
    """An exception in relink is caught and does NOT propagate."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch("personalscraper.dispatch.post_maintenance._run_relink", side_effect=RuntimeError("boom")),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)


def test_fail_soft_fix_exception_swallowed(mock_config: MagicMock) -> None:
    """An exception in fix-season-counts is caught and does NOT propagate."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", side_effect=RuntimeError("boom")),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

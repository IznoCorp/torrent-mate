"""Unit tests for post-dispatch index maintenance hook."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Pre-load cli so personalscraper.indexer.commands.scan is importable.
# scan.py has a circular import with cli.py; patching its module path
# requires the module to already be in sys.modules as an attribute of
# the commands package.
import personalscraper.indexer.cli  # noqa: F401  # needed for mock patch path
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.post_maintenance import (
    collect_touched_disks,
    run_post_dispatch_maintenance,
)


@pytest.fixture
def mock_config() -> MagicMock:
    """Return a mock Config with a resolved indexer.db_path."""
    cfg = MagicMock()
    cfg.indexer.db_path = "/tmp/test_library.db"
    cfg.indexer.post_dispatch_maintenance.enabled = True
    return cfg


# ── collect_touched_disks ──


def test_collect_touched_disks_includes_moved_merged_replaced() -> None:
    """Results with action in (moved, merged, replaced) and non-None disk are included."""
    results = [
        DispatchResult(source=Path("/src/a"), disk="disk_1", action="moved"),
        DispatchResult(source=Path("/src/b"), disk="disk_2", action="merged"),
        DispatchResult(source=Path("/src/c"), disk="disk_1", action="replaced"),
    ]
    assert collect_touched_disks(results) == {"disk_1", "disk_2"}


def test_collect_touched_disks_excludes_skipped_error_none_disk() -> None:
    """Skipped items, errors, and None-disk results are excluded."""
    results = [
        DispatchResult(source=Path("/src/a"), disk=None, action="skipped"),
        DispatchResult(source=Path("/src/b"), disk=None, action="error"),
        DispatchResult(source=Path("/src/c"), disk="disk_1", action="moved"),
    ]
    assert collect_touched_disks(results) == {"disk_1"}


def test_collect_touched_disks_dedups() -> None:
    """Duplicate disk labels are deduplicated."""
    results = [
        DispatchResult(source=Path("/src/a"), disk="disk_1", action="moved"),
        DispatchResult(source=Path("/src/b"), disk="disk_1", action="merged"),
        DispatchResult(source=Path("/src/c"), disk="disk_2", action="moved"),
    ]
    assert collect_touched_disks(results) == {"disk_1", "disk_2"}


def test_collect_touched_disks_empty_results() -> None:
    """Empty results list returns empty set."""
    assert collect_touched_disks([]) == set()


# ── Core behaviour ──


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


# ── Fail-soft ──


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


# ── Fail-soft surfacing (DESIGN Decision #2) ──


def test_relink_exception_surfaces_post_maintenance_incomplete(
    mock_config: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """A total _run_relink exception causes post_maintenance_incomplete warning."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch("personalscraper.dispatch.post_maintenance._run_relink", side_effect=RuntimeError("relink boom")),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
        caplog.at_level(logging.WARNING),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    assert any("post_maintenance_incomplete" in r.message for r in caplog.records), (
        "post_maintenance_incomplete warning should be emitted when relink throws"
    )


def test_fix_exception_surfaces_post_maintenance_incomplete(
    mock_config: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """A total _run_fix_season_counts exception causes post_maintenance_incomplete warning."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", side_effect=RuntimeError("fix boom")),
        caplog.at_level(logging.WARNING),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    assert any("post_maintenance_incomplete" in r.message for r in caplog.records), (
        "post_maintenance_incomplete warning should be emitted when fix_season_counts throws"
    )


def test_scan_failure_surfaces_post_maintenance_incomplete(
    mock_config: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """A non-zero scan exit code causes post_maintenance_incomplete warning."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=1),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 0},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
        caplog.at_level(logging.WARNING),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    assert any("post_maintenance_incomplete" in r.message for r in caplog.records), (
        "post_maintenance_incomplete warning should be emitted when a scan fails"
    )
    # The manual_fallback should include library-index --mode full when scans failed
    assert any("library-index --mode full" in r.message for r in caplog.records), (
        "manual_fallback should include library-index --mode full when scan_failures is non-empty"
    )


def test_no_scan_failure_fallback_omits_full_scan(mock_config: MagicMock, caplog: pytest.LogCaptureFixture) -> None:
    """When only relink errors exist (no scan failures), fallback omits library-index."""
    with (
        patch("personalscraper.dispatch.post_maintenance._scan_disk_incremental", return_value=0),
        patch(
            "personalscraper.dispatch.post_maintenance._run_relink",
            return_value={"linked": 0, "unmatched": 0, "errors": 1},
        ),
        patch("personalscraper.dispatch.post_maintenance._run_fix_season_counts", return_value=0),
        caplog.at_level(logging.WARNING),
    ):
        run_post_dispatch_maintenance(mock_config, {"disk_1"}, enabled=True)

    assert any("post_maintenance_incomplete" in r.message for r in caplog.records), (
        "post_maintenance_incomplete warning should be emitted when relink has errors"
    )
    # Should NOT include full scan since there are no scan failures
    assert not any("library-index --mode full" in r.message for r in caplog.records), (
        "manual_fallback should NOT include library-index --mode full when scan_failures is empty"
    )

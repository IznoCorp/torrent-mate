"""E2E tests for ``personalscraper library-refresh-path`` (A6, 2026-07-15).

Targeted index reconciliation after a manual rename: the CLI resolves the
owning disk from config, then delegates to the post-dispatch maintenance
machinery (subtree invalidation + incremental scan + relink + season counts).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tests.commands._e2e_helpers import make_synthetic_db, make_test_config_with_db, run_cli

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_MAINT = "personalscraper.dispatch.post_maintenance.run_post_dispatch_maintenance"


def test_help_exits_zero(test_config) -> None:
    """--help exits 0 and shows the command."""
    result = run_cli(["library-refresh-path", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-refresh-path" in result.output


def test_refresh_resolves_disk_and_runs_maintenance(tmp_path, test_config) -> None:
    """A path under a configured disk triggers maintenance for that disk + path."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    disk = cfg.disks[0]
    target = Path(disk.path) / "series" / "Show (2020)"
    target.mkdir(parents=True)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_MAINT) as maint:
        result = run_cli(["library-refresh-path", str(target)])

    assert result.exit_code == 0, result.output
    maint.assert_called_once()
    args, kwargs = maint.call_args
    assert args[1] == {disk.id}
    assert kwargs["destinations"] == {disk.id: {target}}


def test_dry_run_touches_nothing(tmp_path, test_config) -> None:
    """--dry-run prints the plan and never calls the maintenance machinery."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    disk = cfg.disks[0]
    target = Path(disk.path) / "series" / "Show (2020)"
    target.mkdir(parents=True)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_MAINT) as maint:
        result = run_cli(["library-refresh-path", str(target), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    maint.assert_not_called()


def test_path_outside_disks_exits_2(tmp_path, test_config) -> None:
    """A path owned by no configured disk is refused with an actionable message."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    outside = tmp_path / "elsewhere" / "Show"
    outside.mkdir(parents=True)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_MAINT) as maint:
        result = run_cli(["library-refresh-path", str(outside)])

    assert result.exit_code == 2, result.output
    assert "No configured disk" in result.output
    maint.assert_not_called()


def test_missing_path_exits_2(tmp_path, test_config) -> None:
    """A non-existent path is refused (operator typo guard)."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg), patch(_PATCH_MAINT) as maint:
        result = run_cli(["library-refresh-path", str(tmp_path / "nope")])

    assert result.exit_code == 2, result.output
    maint.assert_not_called()

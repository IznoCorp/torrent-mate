"""E2E tests for ``personalscraper library-refresh-path`` (A6, 2026-07-15).

Targeted index reconciliation after a manual rename/move/delete: the CLI resolves the
owning disk from config, then delegates to the scoped refresh, which touches only the
given paths (rescan if they exist, removal from the index if they are gone).
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path
from unittest.mock import patch

from personalscraper.dispatch.post_maintenance import ScopedRefreshReport
from tests.commands._e2e_helpers import make_synthetic_db, make_test_config_with_db, run_cli, seed_disk

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"
_PATCH_MAINT = "personalscraper.dispatch.post_maintenance.run_post_dispatch_maintenance"
_PATCH_SCOPED = "personalscraper.dispatch.post_maintenance.run_scoped_refresh"


def test_help_exits_zero(test_config) -> None:
    """--help exits 0 and shows the command."""
    result = run_cli(["library-refresh-path", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-refresh-path" in result.output


def test_refresh_hands_the_given_paths_to_the_scoped_refresh(tmp_path, test_config) -> None:
    """The given paths reach the scoped refresh; the disk-wide maintenance is NOT run."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    disk = cfg.disks[0]
    target = Path(disk.path) / "series" / "Show (2020)"
    target.mkdir(parents=True)

    with (
        patch(_PATCH_LOAD_CONFIG, return_value=cfg),
        patch(_PATCH_MAINT) as maint,
        patch(_PATCH_SCOPED, return_value=ScopedRefreshReport()) as scoped,
    ):
        result = run_cli(["library-refresh-path", str(target)])

    assert result.exit_code == 0, result.output
    scoped.assert_called_once()
    args, kwargs = scoped.call_args
    assert args[1] == disk.id
    assert args[2] == [target]
    assert kwargs["dry_run"] is False
    maint.assert_not_called()


def _library(tmp_path: Path, test_config):
    """A migrated DB, a config whose first disk is rooted in ``tmp_path`` and its disk row."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    disk = cfg.disks[0]
    mount = Path(disk.path)
    mount.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    seed_disk(conn, disk.id, mount)
    conn.close()
    return cfg, mount, db_path


def _show(mount: Path, name: str, episodes: list[str]) -> Path:
    season = mount / "series" / name / "Season 01"
    season.mkdir(parents=True, exist_ok=True)
    for ep in episodes:
        (season / ep).write_bytes(b"x" * 2048)
    return mount / "series" / name


def _dump(db_path: Path) -> list[str]:
    """The whole database as SQL statements: equal dumps mean nothing was written."""
    conn = sqlite3.connect(db_path)
    try:
        return list(conn.iterdump())
    finally:
        conn.close()


def _snapshot(db_path: Path, like: str) -> list[tuple]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT p.rel_path, p.dir_mtime_ns, mf.filename, mf.size_bytes, mf.scan_generation, mf.deleted_at "
            "FROM media_file mf JOIN path p ON p.id = mf.path_id WHERE p.rel_path LIKE ? ORDER BY 1, 3",
            (like,),
        ).fetchall()
    finally:
        conn.close()


def test_e2e_refresh_leaves_a_second_show_on_the_same_disk_untouched(tmp_path, test_config) -> None:
    """Defect: the refresh re-indexed the whole disk. Now only the given show changes."""
    cfg, mount, db_path = _library(tmp_path, test_config)
    show_a = _show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    show_b = _show(mount, "Show B (2021)", ["Show.B.S01E01.mkv"])
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        assert run_cli(["library-refresh-path", str(show_a), str(show_b)]).exit_code == 0
        b_before = _snapshot(db_path, "series/Show B%")
        (show_a / "Season 01" / "Show.A.S01E02.mkv").write_bytes(b"y" * 4096)
        (show_b / "Season 01" / "Show.B.S01E02.mkv").write_bytes(b"y" * 4096)
        result = run_cli(["library-refresh-path", str(show_a)])

    assert result.exit_code == 0, result.output
    assert [r[2] for r in _snapshot(db_path, "series/Show A%")] == ["Show.A.S01E01.mkv", "Show.A.S01E02.mkv"]
    assert _snapshot(db_path, "series/Show B%") == b_before


def test_e2e_refresh_removes_a_deleted_path_from_the_index(tmp_path, test_config) -> None:
    """Defect: a deleted path was refused (exit 2). Now it leaves the index, exit 0."""
    cfg, mount, db_path = _library(tmp_path, test_config)
    show_a = _show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    show_b = _show(mount, "Show B (2021)", ["Show.B.S01E01.mkv"])
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        assert run_cli(["library-refresh-path", str(show_a), str(show_b)]).exit_code == 0
        b_before = _snapshot(db_path, "series/Show B%")
        shutil.rmtree(show_a)
        result = run_cli(["library-refresh-path", str(show_a)])

    assert result.exit_code == 0, result.output
    assert all(r[5] is not None for r in _snapshot(db_path, "series/Show A%"))
    assert _snapshot(db_path, "series/Show B%") == b_before


def test_e2e_dry_run_removes_nothing(tmp_path, test_config) -> None:
    """--dry-run on a deleted path reports it and leaves the index as it was."""
    cfg, mount, db_path = _library(tmp_path, test_config)
    show_a = _show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        assert run_cli(["library-refresh-path", str(show_a)]).exit_code == 0
        before = _snapshot(db_path, "%")
        shutil.rmtree(show_a)
        result = run_cli(["library-refresh-path", str(show_a), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "DRY-RUN" in result.output
    assert _snapshot(db_path, "%") == before


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


def test_e2e_stopped_walk_exits_1_and_writes_nothing(tmp_path, test_config) -> None:
    """A walk stopped by a shutdown request is reported (exit 1), not committed as a success."""
    cfg, mount, db_path = _library(tmp_path, test_config)
    show_a = _show(mount, "Show A (2020)", ["Show.A.S01E01.mkv"])
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        assert run_cli(["library-refresh-path", str(show_a)]).exit_code == 0
        (show_a / "Season 01" / "Show.A.S01E02.mkv").write_bytes(b"y" * 4096)
        before = _dump(db_path)
        with patch("personalscraper.indexer.scanner._shutdown.is_shutdown_requested", return_value=True):
            result = run_cli(["library-refresh-path", str(show_a)])

    assert result.exit_code == 1, result.output
    assert "did not finish" in " ".join(result.output.split())
    assert _dump(db_path) == before

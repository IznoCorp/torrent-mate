"""E2E tests for ``personalscraper library-ghost-audit`` — CLI-level harness.

Exercises the NTFS-via-macFUSE ghost dirent audit against synthetic
mounted disks.  Read-only command — never mutates the filesystem or DB.
"""

from __future__ import annotations

import re
from unittest.mock import patch

from personalscraper.conf.models.disks import DiskConfig
from tests.commands._e2e_helpers import (
    assert_no_python_traceback,
    make_synthetic_db,
    make_test_config_with_db,
    run_cli,
)

_PATCH_LOAD_CONFIG = "personalscraper.conf.loader.load_config"


def _clean(output: str) -> str:
    """Strip Rich ANSI escape codes for plain-text assertions."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def _make_disk_config(disk_id: str, path) -> DiskConfig:
    """Create a minimal DiskConfig with a single builtin category."""
    from personalscraper.conf import ids as CID

    return DiskConfig(id=disk_id, path=path, categories=[CID.MOVIES])


# ── 1. Smoke ───────────────────────────────────────────────────────────────────


def test_ghost_audit_help_exits_zero() -> None:
    """``library-ghost-audit --help`` exits 0."""
    result = run_cli(["library-ghost-audit", "--help"])
    assert result.exit_code == 0, result.output
    assert "library-ghost-audit" in result.output


# ── 2. Realistic scenarios ────────────────────────────────────────────────────


def test_ghost_audit_no_disks_exits_clean(tmp_path, test_config) -> None:
    """Config with zero disks → 'All disks clean' message, exit 0."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    cfg = cfg.model_copy(update={"disks": []})

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-ghost-audit"])

    assert result.exit_code == 0, result.output
    clean = _clean(result.output)
    assert "no ghost dirents" in clean, f"Expected 'no ghost dirents' for zero disks, got: {clean}"


def test_ghost_audit_clean_disk_exits_clean(tmp_path, test_config) -> None:
    """Mounted disk with only real files → per-disk 'clean' + global clean."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    disk_dir = tmp_path / "cleandisk"
    disk_dir.mkdir()
    (disk_dir / "real_file.mkv").write_text("test content")

    cfg = cfg.model_copy(update={"disks": [_make_disk_config("cleandisk", disk_dir)]})

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-ghost-audit"])

    assert result.exit_code == 0, result.output
    clean = _clean(result.output)
    assert "cleandisk" in clean, f"Disk label missing: {clean}"
    assert "clean" in clean, f"Expected 'clean' for clean disk: {clean}"


def test_ghost_audit_disk_filter_restricts_scope(tmp_path, test_config) -> None:
    """``--disk`` flag restricts audit to the specified disk only."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    dir_a = tmp_path / "diska"
    dir_a.mkdir()
    (dir_a / "f.mkv").write_text("a")
    dir_b = tmp_path / "diskb"
    dir_b.mkdir()
    (dir_b / "f.mkv").write_text("b")

    cfg = cfg.model_copy(
        update={
            "disks": [
                _make_disk_config("diska", dir_a),
                _make_disk_config("diskb", dir_b),
            ]
        }
    )

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-ghost-audit", "--disk", "diska"])

    assert result.exit_code == 0, result.output
    clean = _clean(result.output)
    assert "diska" in clean, f"Filtered disk 'diska' should appear: {clean}"
    assert "diskb" not in clean, f"Unfiltered disk 'diskb' must not appear: {clean}"


def test_ghost_audit_skips_unmounted_disk(tmp_path, test_config) -> None:
    """Disk whose path does not exist → 'not mounted, skipped'."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)

    nonexistent = tmp_path / "nonexistent_disk"
    # Do NOT create the directory.

    cfg = cfg.model_copy(update={"disks": [_make_disk_config("ghostdisk", nonexistent)]})

    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-ghost-audit"])

    assert result.exit_code == 0, result.output
    clean = _clean(result.output)
    assert "not mounted, skipped" in clean, f"Expected 'not mounted, skipped' for nonexistent path: {clean}"
    assert "ghostdisk" in clean, f"Disk label should appear: {clean}"


# ── 3. Errors ──


def test_ghost_audit_invalid_arg_exits_nonzero() -> None:
    """Unknown flag → non-zero exit, no Python traceback."""
    result = run_cli(["library-ghost-audit", "--not-a-real-flag-xyz123"])
    assert result.exit_code != 0
    assert_no_python_traceback(result)


def test_ghost_audit_config_absent_exits_gracefully(monkeypatch) -> None:
    """load_config raises ConfigNotFoundError → friendly error, no traceback."""
    from personalscraper.conf.loader import ConfigNotFoundError

    def _raise(*_a, **_kw):
        raise ConfigNotFoundError("no config found")

    monkeypatch.setattr("personalscraper.conf.loader.load_config", _raise)
    result = run_cli(["library-ghost-audit"])
    assert result.exit_code != 0
    assert "error" in result.output.lower() or "config" in result.output.lower()
    assert_no_python_traceback(result)


# ── 6. Output ──


def test_ghost_audit_output_no_traceback(tmp_path, test_config) -> None:
    """Output is Rich-formatted, never a Python traceback."""
    db_path = make_synthetic_db(tmp_path)
    cfg = make_test_config_with_db(test_config, db_path)
    cfg = cfg.model_copy(update={"disks": []})
    with patch(_PATCH_LOAD_CONFIG, return_value=cfg):
        result = run_cli(["library-ghost-audit"])
    assert result.exit_code == 0
    assert_no_python_traceback(result)
    assert "no ghost dirents" in _clean(result.output)


def test_ghost_audit_error_exits_nonzero(monkeypatch) -> None:
    """Config error → non-zero exit code."""
    from personalscraper.conf.loader import ConfigNotFoundError

    def _raise(*_a, **_kw):
        raise ConfigNotFoundError("no config found")

    monkeypatch.setattr("personalscraper.conf.loader.load_config", _raise)
    result = run_cli(["library-ghost-audit"])
    assert result.exit_code != 0


# ── 7. Events ──

# N/A: ``library-ghost-audit`` is a read-only diagnostic command.  It opens no
# database connection (uses ``os.walk`` directly against storage disks) and
# creates no EventBus.  Output is Rich console text via ``console.print``.
# No domain event is published.

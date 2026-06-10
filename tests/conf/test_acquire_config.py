"""Tests for AcquireConfig WAL-safety validator and Config-level derivation."""

from __future__ import annotations

from pathlib import Path

import pytest

from personalscraper.conf.models.acquire import AcquireConfig


def test_acquire_config_defaults_to_none() -> None:
    """db_path defaults to None."""
    cfg = AcquireConfig()
    assert cfg.db_path is None


def test_acquire_config_absolute_path_accepted(tmp_path: Path) -> None:
    """An absolute path on a safe filesystem is accepted."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    assert cfg.db_path == tmp_path / "acquire.db"


def test_acquire_config_rejects_ntfs_macfuse_path(monkeypatch) -> None:
    """A path on ntfs_macfuse must be rejected (WAL unsafe)."""
    from personalscraper.core.sqlite._fs_probe import MountInfo

    mock_info = MountInfo(
        mount_point="/Volumes/ext",
        fs_type="ntfs_macfuse",
        raw_fs_type="ufsd_ntfs",
        flags=frozenset(),
    )
    monkeypatch.setattr(
        "personalscraper.core.sqlite._fs_probe.probe_mount",
        lambda path: mock_info,
    )
    with pytest.raises(ValueError, match="WAL"):
        AcquireConfig(db_path=Path("/Volumes/ext/acquire.db"))


def test_acquire_config_extra_fields_forbidden() -> None:
    """_StrictModel extra='forbid' rejects unknown fields."""
    with pytest.raises(Exception):
        AcquireConfig(unknown_field=True)  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Config-level derivation tests (sub-phase 2.3)
# ---------------------------------------------------------------------------


def test_config_derives_acquire_db_path_from_data_dir() -> None:
    """Config._resolve_derived_paths sets acquire.db_path from paths.data_dir."""
    from pathlib import Path

    from personalscraper.conf.loader import load_config_dir

    _REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    EXAMPLE_DIR = _REPO_ROOT / "config.example"

    config = load_config_dir(EXAMPLE_DIR)
    expected = config.paths.data_dir / "acquire.db"
    assert config.acquire.db_path == expected


def test_config_respects_explicit_acquire_db_path(test_config) -> None:
    """Config._resolve_derived_paths does NOT override an explicit acquire.db_path."""
    from pathlib import Path

    explicit_path = Path("/tmp/explicit_acquire.db")
    cfg_with_explicit = test_config.model_copy(update={"acquire": AcquireConfig(db_path=explicit_path)})
    assert cfg_with_explicit.acquire.db_path == explicit_path

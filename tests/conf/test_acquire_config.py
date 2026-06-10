"""Tests for AcquireConfig WAL-safety validator."""

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

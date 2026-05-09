"""Tests for the disk scanner module."""

from pathlib import Path

from personalscraper.conf.models.disks import DiskConfig
from personalscraper.dispatch.disk_scanner import (
    DiskStatus,
    get_disk_configs,
    get_disk_status,
)

# ---------------------------------------------------------------------------
# get_disk_configs
# ---------------------------------------------------------------------------


class TestGetDiskConfigs:
    """Tests for get_disk_configs(config)."""

    def test_returns_config_disks(self, test_config) -> None:
        """Should return the same DiskConfig objects as config.disks."""
        result = get_disk_configs(test_config)
        assert result == list(test_config.disks)

    def test_count_matches_disks(self, test_config) -> None:
        """Number of returned configs matches number of disks in config."""
        result = get_disk_configs(test_config)
        assert len(result) == len(test_config.disks)

    def test_returns_pydantic_disk_configs(self, test_config) -> None:
        """Returned objects are Pydantic DiskConfig instances."""
        result = get_disk_configs(test_config)
        for dc in result:
            assert isinstance(dc, DiskConfig)
            assert hasattr(dc, "id")
            assert hasattr(dc, "path")
            assert hasattr(dc, "categories")


# ---------------------------------------------------------------------------
# get_disk_status
# ---------------------------------------------------------------------------


class TestGetDiskStatus:
    """Tests for get_disk_status."""

    def test_unmounted_disk_returns_false(self, tmp_path: Path) -> None:
        """Non-existent path → is_mounted=False, free_space_gb=0."""
        dc = DiskConfig(id="disk_a", path=tmp_path / "nonexistent", categories=["movies"])
        status = get_disk_status(dc)
        assert status.is_mounted is False
        assert status.free_space_gb == 0.0

    def test_mounted_disk_returns_true(self, tmp_path: Path) -> None:
        """Existing path → is_mounted=True, free_space_gb > 0."""
        dc = DiskConfig(id="disk_a", path=tmp_path, categories=["movies"])
        status = get_disk_status(dc)
        assert status.is_mounted is True
        assert status.free_space_gb > 0.0

    def test_returns_disk_status_instance(self, tmp_path: Path) -> None:
        """get_disk_status returns a DiskStatus dataclass."""
        dc = DiskConfig(id="disk_a", path=tmp_path, categories=["movies"])
        status = get_disk_status(dc)
        assert isinstance(status, DiskStatus)
        assert status.config is dc

    def test_disk_usage_oserror_treated_as_unmounted(self, tmp_path: Path) -> None:
        """When shutil.disk_usage raises OSError, disk is treated as unmounted."""
        from unittest.mock import patch

        dc = DiskConfig(id="disk_a", path=tmp_path, categories=["movies"])
        with patch("shutil.disk_usage", side_effect=OSError("permission denied")):
            status = get_disk_status(dc)
        assert status.is_mounted is False
        assert status.free_space_gb == 0.0

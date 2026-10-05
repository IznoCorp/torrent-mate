"""Tests for the disk scanner module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

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

    @pytest.mark.real_mount_check
    def test_folder_on_root_filesystem_is_not_mounted(self, tmp_path: Path) -> None:
        """A folder that exists on the system disk is not a mounted disk (B-687).

        The only mount point is ``/``: the disk's volume was never mounted, yet its
        folder exists on the system disk.

        Design: docs/production/storage.md#mounted-means-a-mounted-volume
        Contract: A disk whose folder exists but whose volume is not mounted
        (only ``/`` is a mount point above it) reports ``is_mounted`` False.
        """
        folder = tmp_path / "Volumes" / "Disk9" / "medias"
        folder.mkdir(parents=True)
        dc = DiskConfig(id="disk_a", path=folder, categories=["movies"])
        with patch("personalscraper.core.sqlite._fs_probe._is_mount_root", side_effect=lambda p: p == "/"):
            status = get_disk_status(dc)
        assert status.is_mounted is False
        assert status.free_space_gb == 0.0

    @pytest.mark.real_mount_check
    def test_tmp_folder_is_not_mounted_on_real_mount_table(self, tmp_path: Path) -> None:
        """With the real mount reading, a folder on the root device is not mounted.

        Design: docs/production/storage.md#mounted-means-a-mounted-volume
        Contract: Reading the real mount table, a folder on the root device
        is not a mounted disk.
        """
        if os.stat(tmp_path).st_dev != os.stat("/").st_dev:
            pytest.skip("tmp_path is not on the root device here (tmpfs or a separate volume)")
        dc = DiskConfig(id="disk_a", path=tmp_path, categories=["movies"])
        assert get_disk_status(dc).is_mounted is False

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
        dc = DiskConfig(id="disk_a", path=tmp_path, categories=["movies"])
        with patch("shutil.disk_usage", side_effect=OSError("permission denied")):
            status = get_disk_status(dc)
        assert status.is_mounted is False
        assert status.free_space_gb == 0.0


# ---------------------------------------------------------------------------
# sandbox mount-point guard
# ---------------------------------------------------------------------------


class TestSandboxMarker:
    """Under a sandbox environment a disk root without that environment's marker reads as not mounted."""

    def _dc(self, path: Path) -> DiskConfig:
        return DiskConfig(id="disk_p", path=path, categories=["movies"])

    def test_unmarked_root_is_not_mounted_under_staging(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A mounted but unmarked preprod root reports ``is_mounted`` False and no free space."""
        monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
        with (
            patch("personalscraper.dispatch.disk_scanner._volume_is_mounted", return_value=True),
            patch("personalscraper.conf.sandbox_guard.is_mounted", return_value=True),
        ):
            status = get_disk_status(self._dc(tmp_path))
        assert status.is_mounted is False
        assert status.free_space_gb == 0.0

    def test_marked_root_is_mounted_under_staging(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The same root with its marker reads as mounted."""
        monkeypatch.setenv("PERSONALSCRAPER_ENV", "staging")
        (tmp_path / ".tm-preprod-root").write_text("", encoding="utf-8")
        with (
            patch("personalscraper.dispatch.disk_scanner._volume_is_mounted", return_value=True),
            patch("personalscraper.conf.sandbox_guard.is_mounted", return_value=True),
        ):
            assert get_disk_status(self._dc(tmp_path)).is_mounted is True

    def test_unset_environment_ignores_the_marker(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without ``PERSONALSCRAPER_ENV`` an unmarked mounted root is mounted, as before."""
        monkeypatch.delenv("PERSONALSCRAPER_ENV", raising=False)
        with patch("personalscraper.dispatch.disk_scanner._volume_is_mounted", return_value=True):
            assert get_disk_status(self._dc(tmp_path)).is_mounted is True

    def test_unmarked_root_is_not_mounted_under_dev(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Under dev a mounted root without ``.tm-dev-root`` reads as not mounted, even with preprod's marker."""
        monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
        (tmp_path / ".tm-preprod-root").write_text("", encoding="utf-8")
        with (
            patch("personalscraper.dispatch.disk_scanner._volume_is_mounted", return_value=True),
            patch("personalscraper.conf.sandbox_guard.is_mounted", return_value=True),
        ):
            status = get_disk_status(self._dc(tmp_path))
        assert status.is_mounted is False
        assert status.free_space_gb == 0.0

    def test_dev_marked_root_is_mounted_under_dev(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The same root with the dev marker reads as mounted under dev."""
        monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
        (tmp_path / ".tm-dev-root").write_text("", encoding="utf-8")
        with (
            patch("personalscraper.dispatch.disk_scanner._volume_is_mounted", return_value=True),
            patch("personalscraper.conf.sandbox_guard.is_mounted", return_value=True),
        ):
            assert get_disk_status(self._dc(tmp_path)).is_mounted is True

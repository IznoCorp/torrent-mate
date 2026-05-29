"""Tests for DiskConfig.fs_type field and Dispatcher override-beats-autodetect.

Covers Phase 4 of the multi-filesystem feature:

- ``DiskConfig.fs_type`` optional override field (AC-13).
- ``Dispatcher._resolve_disk_capability`` honouring the override before
  falling back to auto-detection via ``probe_mount``.
- ``IndexerConfig.db_path`` capability-aware validator accepting a legitimate
  APFS volume mounted under ``/Volumes/`` (the case the former blunt
  ``/Volumes/`` prefix check wrongly rejected).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.conf.models.disks import DiskConfig
from personalscraper.indexer._fs_capability import APFS, NTFS_MACFUSE


class TestDiskConfigFsType:
    """AC-13: DiskConfig accepts an optional fs_type override."""

    def test_fs_type_none_by_default(self) -> None:
        """An omitted fs_type defaults to None (auto-detection at runtime)."""
        d = DiskConfig(id="x", path=Path("/tmp"), categories=["movies"])
        assert d.fs_type is None

    def test_fs_type_apfs_override(self) -> None:
        """An explicit 'apfs' override is preserved on the model."""
        d = DiskConfig(id="x", path=Path("/tmp"), categories=["movies"], fs_type="apfs")
        assert d.fs_type == "apfs"

    def test_fs_type_ntfs_macfuse_override(self) -> None:
        """An explicit 'ntfs_macfuse' override is preserved on the model."""
        d = DiskConfig(id="x", path=Path("/tmp"), categories=["movies"], fs_type="ntfs_macfuse")
        assert d.fs_type == "ntfs_macfuse"

    def test_fs_type_hfsplus_override(self) -> None:
        """An explicit 'hfsplus' override is preserved on the model."""
        d = DiskConfig(id="x", path=Path("/tmp"), categories=["movies"], fs_type="hfsplus")
        assert d.fs_type == "hfsplus"


class TestDispatcherCapabilityOverride:
    """Override beats autodetect: when fs_type is set, FsProbe is not used."""

    def test_override_beats_autodetect(self) -> None:
        """When DiskConfig.fs_type='apfs', capability is APFS regardless of probe."""
        from personalscraper.dispatch.dispatcher import _resolve_disk_capability

        disk = DiskConfig(
            id="raid",
            path=Path("/Volumes/AppleRAID"),
            categories=["movies"],
            fs_type="apfs",
        )

        # Even if probe_mount would say "unknown", the override wins and the
        # probe is never invoked.
        with patch("personalscraper.dispatch.dispatcher.probe_mount") as mock_probe:
            mock_probe.return_value = None  # probe would say "unknown"
            cap = _resolve_disk_capability(disk)

        assert cap == APFS
        mock_probe.assert_not_called()  # override skips the probe entirely

    def test_autodetect_used_when_no_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When fs_type is None, the FsProbe result is used."""
        import personalscraper.dispatch.dispatcher as mod
        from personalscraper.indexer._fs_probe import MountInfo

        fake_info = MountInfo(
            mount_point="/Volumes/Disk1",
            fs_type="ntfs_macfuse",
            raw_fs_type="ufsd_ntfs",
            flags=frozenset({"local", "noatime"}),
        )
        monkeypatch.setattr(mod, "probe_mount", lambda _: fake_info)

        disk = DiskConfig(id="disk1", path=Path("/Volumes/Disk1"), categories=["movies"])
        cap = mod._resolve_disk_capability(disk)
        assert cap == NTFS_MACFUSE

    def test_unrecognised_override_falls_back_to_ntfs_safe(self) -> None:
        """An unrecognised override value falls back to the NTFS-safe capability."""
        from personalscraper.dispatch.dispatcher import _resolve_disk_capability

        disk = DiskConfig(
            id="paragon",
            path=Path("/Volumes/Paragon"),
            categories=["movies"],
            fs_type="some_unknown_driver_token",
        )
        cap = _resolve_disk_capability(disk)
        # capability_for falls back to UNKNOWN, which equals NTFS_MACFUSE.
        assert cap == NTFS_MACFUSE


class TestIndexerConfigDbPathValidator:
    """The db_path validator accepts APFS-under-/Volumes, rejects NTFS."""

    def test_apfs_under_volumes_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A legitimate APFS DB path at /Volumes/Data/library.db must be accepted."""
        from personalscraper.indexer._fs_probe import MountInfo

        apfs_info = MountInfo(
            mount_point="/Volumes/Data",
            fs_type="apfs",
            raw_fs_type="apfs",
            flags=frozenset(),
        )

        # Patch probe_mount to return an APFS MountInfo whose mount point is the
        # real external volume /Volumes/Data, mirroring a genuine APFS volume.
        monkeypatch.setattr(
            "personalscraper.indexer._fs_probe.probe_mount",
            lambda p: apfs_info if "/Volumes/Data" in p else None,
        )

        from personalscraper.conf.models.indexer import IndexerConfig

        # Must not raise.
        cfg = IndexerConfig(db_path=Path("/Volumes/Data/library.db"))
        assert cfg.db_path == Path("/Volumes/Data/library.db")

    def test_ntfs_macfuse_under_volumes_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A detected NTFS-macFUSE DB path under /Volumes/ must be rejected."""
        from pydantic import ValidationError

        from personalscraper.indexer._fs_probe import MountInfo

        ntfs_info = MountInfo(
            mount_point="/Volumes/Disk1",
            fs_type="ntfs_macfuse",
            raw_fs_type="ufsd_ntfs",
            flags=frozenset({"local", "noatime"}),
        )
        monkeypatch.setattr(
            "personalscraper.indexer._fs_probe.probe_mount",
            lambda p: ntfs_info if "/Volumes/Disk1" in p else None,
        )

        from personalscraper.conf.models.indexer import IndexerConfig

        with pytest.raises(ValidationError, match="WAL-unsafe"):
            IndexerConfig(db_path=Path("/Volumes/Disk1/library.db"))

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
from pydantic import ValidationError

from personalscraper.conf.models.disks import DiskConfig
from personalscraper.indexer._fs_capability import APFS, NTFS_MACFUSE

pytestmark = pytest.mark.multifs


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

    @pytest.mark.parametrize(
        "fs_type",
        ["ntfs_macfuse", "apfs", "hfsplus", "exfat", "ext4", "unknown"],
    )
    def test_every_canonical_key_accepted(self, fs_type: str) -> None:
        """All six canonical fs-type keys are valid Literal values (FIX-1)."""
        d = DiskConfig(id="x", path=Path("/tmp"), categories=["movies"], fs_type=fs_type)
        assert d.fs_type == fs_type

    @pytest.mark.parametrize(
        "bad_value",
        ["ntfs", "APFS", "apfs ", "some_unknown_driver_token", "ntfs-macfuse"],
    )
    def test_typo_fs_type_raises_validation_error(self, bad_value: str) -> None:
        """A non-canonical fs_type fails loud at config load (FIX-1).

        Pins the fail-loud contract: the Literal rejects typos like ``"ntfs"``,
        wrong casing (``"APFS"``), trailing whitespace (``"apfs "``), or any
        unrecognised driver token, instead of silently degrading to the
        NTFS-safe ``"unknown"`` capability. This enforces the docstring's
        "Must be one of the canonical keys" contract at construction time.
        """
        with pytest.raises(ValidationError):
            DiskConfig(id="x", path=Path("/tmp"), categories=["movies"], fs_type=bad_value)


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
        # probe is never invoked.  The single real call site is the lazy import
        # inside ``resolve_capability`` (``_fs_probe.probe_mount``); when an
        # override is set ``resolve_capability`` returns before that import, so
        # ``assert_not_called`` still holds after the consistency refactor.
        with patch("personalscraper.core.sqlite._fs_probe.probe_mount") as mock_probe:
            mock_probe.return_value = None  # probe would say "unknown"
            cap = _resolve_disk_capability(disk)

        assert cap == APFS
        mock_probe.assert_not_called()  # override skips the probe entirely

    def test_autodetect_used_when_no_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When fs_type is None, the FsProbe result is used."""
        import personalscraper.dispatch.dispatcher as mod
        from personalscraper.core.sqlite._fs_probe import MountInfo

        fake_info = MountInfo(
            mount_point="/Volumes/Disk1",
            fs_type="ntfs_macfuse",
            raw_fs_type="ufsd_ntfs",
            flags=frozenset({"local", "noatime"}),
        )
        # The single real call site is the lazy import inside
        # ``resolve_capability`` — patch ``_fs_probe.probe_mount`` (not the
        # dispatcher namespace, which no longer imports the symbol).
        monkeypatch.setattr("personalscraper.core.sqlite._fs_probe.probe_mount", lambda _: fake_info)

        disk = DiskConfig(id="disk1", path=Path("/Volumes/Disk1"), categories=["movies"])
        cap = mod._resolve_disk_capability(disk)
        assert cap == NTFS_MACFUSE

    def test_unrecognised_override_rejected_at_config_load(self) -> None:
        """FIX-1: an unrecognised DiskConfig.fs_type fails loud at construction.

        Previously this token silently constructed a ``DiskConfig`` whose
        ``_resolve_disk_capability`` degraded to the NTFS-safe ``UNKNOWN``
        capability. With the ``Literal`` field it now raises a
        ``ValidationError`` at config load — a typo can no longer reach the
        resolver. The resolver-level fallback (``capability_for(...) ==
        UNKNOWN``) is unchanged and is covered directly below.
        """
        with pytest.raises(ValidationError):
            DiskConfig(
                id="paragon",
                path=Path("/Volumes/Paragon"),
                categories=["movies"],
                fs_type="some_unknown_driver_token",
            )

    def test_resolver_fallback_for_unrecognised_token_unchanged(self) -> None:
        """The resolver keeps its NTFS-safe fallback as defense-in-depth (FIX-1).

        The ``DiskConfig`` Literal blocks bad tokens at config load, but the
        ``resolve_capability`` resolver still falls back to the NTFS-safe
        ``UNKNOWN`` capability for any non-config path that reaches it with an
        unrecognised token — this behaviour is intentionally left intact.
        """
        from personalscraper.indexer._fs_capability import resolve_capability

        cap = resolve_capability("/Volumes/Paragon", "some_unknown_driver_token")
        # capability_for falls back to UNKNOWN, which equals NTFS_MACFUSE.
        assert cap == NTFS_MACFUSE


class TestIndexerConfigDbPathValidator:
    """The db_path validator accepts APFS-under-/Volumes, rejects NTFS."""

    def test_apfs_under_volumes_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A legitimate APFS DB path at /Volumes/Data/library.db must be accepted."""
        from personalscraper.core.sqlite._fs_probe import MountInfo

        apfs_info = MountInfo(
            mount_point="/Volumes/Data",
            fs_type="apfs",
            raw_fs_type="apfs",
            flags=frozenset(),
        )

        # Patch probe_mount to return an APFS MountInfo whose mount point is the
        # real external volume /Volumes/Data, mirroring a genuine APFS volume.
        monkeypatch.setattr(
            "personalscraper.core.sqlite._fs_probe.probe_mount",
            lambda p: apfs_info if "/Volumes/Data" in p else None,
        )

        from personalscraper.conf.models.indexer import IndexerConfig

        # Must not raise.
        cfg = IndexerConfig(db_path=Path("/Volumes/Data/library.db"))
        assert cfg.db_path == Path("/Volumes/Data/library.db")

    def test_ntfs_macfuse_under_volumes_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A detected NTFS-macFUSE DB path under /Volumes/ must be rejected."""
        from pydantic import ValidationError

        from personalscraper.core.sqlite._fs_probe import MountInfo

        ntfs_info = MountInfo(
            mount_point="/Volumes/Disk1",
            fs_type="ntfs_macfuse",
            raw_fs_type="ufsd_ntfs",
            flags=frozenset({"local", "noatime"}),
        )
        monkeypatch.setattr(
            "personalscraper.core.sqlite._fs_probe.probe_mount",
            lambda p: ntfs_info if "/Volumes/Disk1" in p else None,
        )

        from personalscraper.conf.models.indexer import IndexerConfig

        with pytest.raises(ValidationError, match="WAL-unsafe"):
            IndexerConfig(db_path=Path("/Volumes/Disk1/library.db"))

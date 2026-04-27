"""Tests for personalscraper.indexer.merkle.

Covers:
- ``compute_merkle_root`` — determinism, order-independence, distinct-input sensitivity, empty input.
- ``bootstrap_disk_identity`` — sentinel write, diskutil missing, no VolumeUUID.
- ``verify_disk_mounted`` — UNMOUNTED, NO_SENTINEL, MOUNTED_WRONG_DISK, MOUNTED_AND_VERIFIED.
- ``guard_disk_mounted`` — each state transition (raises or returns None).
"""

from __future__ import annotations

import plistlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.indexer.merkle import (
    SENTINEL_FILENAME,
    BootstrapError,
    DiskMismatchError,
    DiskMountStatus,
    DiskUnmountedError,
    FileFingerprint,
    bootstrap_disk_identity,
    compute_merkle_root,
    guard_disk_mounted,
    verify_disk_mounted,
)
from personalscraper.indexer.schema import DiskRow

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_disk(mount_path: str | None = "/Volumes/TestDisk", uuid: str = "AAAA-BBBB") -> DiskRow:
    """Return a minimal :class:`DiskRow` for testing."""
    return DiskRow(
        id=1,
        uuid=uuid,
        label="TestDisk",
        mount_path=mount_path,
        last_seen_at=None,
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )


def _make_fps() -> list[FileFingerprint]:
    """Return a deterministic list of 5 :class:`FileFingerprint` objects."""
    return [
        FileFingerprint(path_id=1, size=100, mtime_ns=1_000_000, oshash="aabbccdd00112233"),
        FileFingerprint(path_id=2, size=200, mtime_ns=2_000_000, oshash="bbccdd0011223344"),
        FileFingerprint(path_id=3, size=300, mtime_ns=3_000_000, oshash="ccdd001122334455"),
        FileFingerprint(path_id=4, size=400, mtime_ns=4_000_000, oshash="dd00112233445566"),
        FileFingerprint(path_id=5, size=500, mtime_ns=5_000_000, oshash="0011223344556677"),
    ]


def _plist_bytes(uuid: str) -> bytes:
    """Encode a diskutil-style plist containing *uuid* as ``VolumeUUID``."""
    data = {"VolumeUUID": uuid}
    return plistlib.dumps(data)


# ---------------------------------------------------------------------------
# compute_merkle_root — determinism and correctness
# ---------------------------------------------------------------------------


class TestComputeMerkleRoot:
    """Tests for :func:`compute_merkle_root`."""

    def test_merkle_determinism_same_files_same_order(self) -> None:
        """Same files, same order → identical root computed twice."""
        fps = _make_fps()
        root1 = compute_merkle_root(fps)
        root2 = compute_merkle_root(fps)
        assert root1 == root2

    def test_merkle_determinism_same_files_different_order(self) -> None:
        """Same files shuffled → same root because sort by path_id is applied."""
        fps = _make_fps()
        shuffled = list(reversed(fps))
        assert compute_merkle_root(fps) == compute_merkle_root(shuffled)

    def test_merkle_distinct_files_distinct_root(self) -> None:
        """Changing one field in one fingerprint must produce a different root."""
        fps = _make_fps()
        modified_fps = [
            FileFingerprint(
                path_id=fps[2].path_id,
                size=fps[2].size + 1,  # one byte different
                mtime_ns=fps[2].mtime_ns,
                oshash=fps[2].oshash,
            )
            if i == 2
            else fp
            for i, fp in enumerate(fps)
        ]
        assert compute_merkle_root(fps) != compute_merkle_root(modified_fps)

    def test_merkle_empty_input_returns_hash_of_empty(self) -> None:
        """Empty iterable returns a valid 16-char hex string."""
        root = compute_merkle_root([])
        assert isinstance(root, str)
        assert len(root) == 16
        # Must be valid hex
        int(root, 16)

    def test_merkle_root_is_16_chars(self) -> None:
        """Non-empty input also returns exactly 16 chars."""
        root = compute_merkle_root(_make_fps())
        assert len(root) == 16


# ---------------------------------------------------------------------------
# bootstrap_disk_identity
# ---------------------------------------------------------------------------


class TestBootstrapDiskIdentity:
    """Tests for :func:`bootstrap_disk_identity`."""

    def test_sentinel_write_on_success(self, tmp_path: Path) -> None:
        """bootstrap_disk_identity writes sentinel file and returns UUID."""
        expected_uuid = "12345678-ABCD-EFGH-IJKL-000000000001"
        plist_output = _plist_bytes(expected_uuid).decode("utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = plist_output
        mock_result.stderr = ""

        with patch("personalscraper.indexer.merkle.subprocess.run", return_value=mock_result):
            returned_uuid = bootstrap_disk_identity(tmp_path)

        assert returned_uuid == expected_uuid
        sentinel = (tmp_path / SENTINEL_FILENAME).read_text(encoding="utf-8")
        assert sentinel == expected_uuid

    def test_bootstrap_error_when_diskutil_missing(self, tmp_path: Path) -> None:
        """FileNotFoundError from subprocess.run → BootstrapError."""
        with patch(
            "personalscraper.indexer.merkle.subprocess.run",
            side_effect=FileNotFoundError,
        ):
            with pytest.raises(BootstrapError, match="diskutil not available"):
                bootstrap_disk_identity(tmp_path)

    def test_bootstrap_error_when_diskutil_returns_nonzero(self, tmp_path: Path) -> None:
        """Non-zero return code from diskutil → BootstrapError."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "No such disk"

        with patch("personalscraper.indexer.merkle.subprocess.run", return_value=mock_result):
            with pytest.raises(BootstrapError, match="diskutil failed"):
                bootstrap_disk_identity(tmp_path)

    def test_bootstrap_error_when_no_volumeuuid(self, tmp_path: Path) -> None:
        """Plist without VolumeUUID → BootstrapError."""
        plist_without_uuid = plistlib.dumps({"SomeOtherKey": "value"}).decode("utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = plist_without_uuid
        mock_result.stderr = ""

        with patch("personalscraper.indexer.merkle.subprocess.run", return_value=mock_result):
            with pytest.raises(BootstrapError, match="no VolumeUUID"):
                bootstrap_disk_identity(tmp_path)


# ---------------------------------------------------------------------------
# verify_disk_mounted
# ---------------------------------------------------------------------------


class TestVerifyDiskMounted:
    """Tests for :func:`verify_disk_mounted`."""

    def test_verify_disk_mounted_unmounted_when_no_mount_path(self) -> None:
        """mount_path is None → UNMOUNTED."""
        disk = _make_disk(mount_path=None)
        with patch("os.path.ismount", return_value=False):
            status = verify_disk_mounted(disk)
        assert status is DiskMountStatus.UNMOUNTED

    def test_verify_disk_mounted_unmounted(self) -> None:
        """os.path.ismount returns False → UNMOUNTED."""
        disk = _make_disk()
        with patch("os.path.ismount", return_value=False):
            status = verify_disk_mounted(disk)
        assert status is DiskMountStatus.UNMOUNTED

    def test_verify_disk_mounted_no_sentinel(self, tmp_path: Path) -> None:
        """Sentinel file missing → NO_SENTINEL."""
        disk = _make_disk(mount_path=str(tmp_path))
        # No sentinel file written — it simply doesn't exist.
        with patch("os.path.ismount", return_value=True):
            status = verify_disk_mounted(disk)
        assert status is DiskMountStatus.NO_SENTINEL

    def test_verify_disk_mounted_wrong_disk(self, tmp_path: Path) -> None:
        """Sentinel UUID differs from disk.uuid → MOUNTED_WRONG_DISK."""
        disk = _make_disk(mount_path=str(tmp_path), uuid="CORRECT-UUID")
        (tmp_path / SENTINEL_FILENAME).write_text("WRONG-UUID", encoding="utf-8")
        with patch("os.path.ismount", return_value=True):
            status = verify_disk_mounted(disk)
        assert status is DiskMountStatus.MOUNTED_WRONG_DISK

    def test_sentinel_write_and_read(self, tmp_path: Path) -> None:
        """bootstrap_disk_identity writes sentinel; verify_disk_mounted reads it → MOUNTED_AND_VERIFIED."""
        expected_uuid = "SENTINEL-TEST-UUID"
        plist_output = _plist_bytes(expected_uuid).decode("utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = plist_output
        mock_result.stderr = ""

        with patch("personalscraper.indexer.merkle.subprocess.run", return_value=mock_result):
            bootstrap_disk_identity(tmp_path)

        disk = _make_disk(mount_path=str(tmp_path), uuid=expected_uuid)
        with patch("os.path.ismount", return_value=True):
            status = verify_disk_mounted(disk)
        assert status is DiskMountStatus.MOUNTED_AND_VERIFIED


# ---------------------------------------------------------------------------
# guard_disk_mounted
# ---------------------------------------------------------------------------


class TestGuardDiskMounted:
    """Tests for :func:`guard_disk_mounted`."""

    def test_guard_disk_mounted_unmounted_raises(self) -> None:
        """UNMOUNTED → DiskUnmountedError."""
        disk = _make_disk()
        with patch("os.path.ismount", return_value=False):
            with pytest.raises(DiskUnmountedError):
                guard_disk_mounted(disk)

    def test_guard_disk_mounted_wrong_disk_raises(self, tmp_path: Path) -> None:
        """MOUNTED_WRONG_DISK → DiskMismatchError."""
        disk = _make_disk(mount_path=str(tmp_path), uuid="CORRECT-UUID")
        (tmp_path / SENTINEL_FILENAME).write_text("WRONG-UUID", encoding="utf-8")
        with patch("os.path.ismount", return_value=True):
            with pytest.raises(DiskMismatchError):
                guard_disk_mounted(disk)

    def test_guard_disk_mounted_verified_returns_none(self, tmp_path: Path) -> None:
        """MOUNTED_AND_VERIFIED → returns None (no exception)."""
        expected_uuid = "GUARD-HAPPY-UUID"
        (tmp_path / SENTINEL_FILENAME).write_text(expected_uuid, encoding="utf-8")
        disk = _make_disk(mount_path=str(tmp_path), uuid=expected_uuid)
        with patch("os.path.ismount", return_value=True):
            result = guard_disk_mounted(disk)
        assert result is None

    def test_guard_no_sentinel_bootstraps_and_returns_none(self, tmp_path: Path) -> None:
        """NO_SENTINEL with matching bootstrapped UUID → returns None after re-creating sentinel."""
        expected_uuid = "BOOTSTRAP-UUID"
        plist_output = _plist_bytes(expected_uuid).decode("utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = plist_output
        mock_result.stderr = ""

        disk = _make_disk(mount_path=str(tmp_path), uuid=expected_uuid)
        with patch("os.path.ismount", return_value=True):
            with patch("personalscraper.indexer.merkle.subprocess.run", return_value=mock_result):
                result = guard_disk_mounted(disk)
        assert result is None
        # Sentinel must now exist.
        assert (tmp_path / SENTINEL_FILENAME).read_text(encoding="utf-8") == expected_uuid

    def test_guard_no_sentinel_bootstrap_uuid_mismatch_raises(self, tmp_path: Path) -> None:
        """NO_SENTINEL where bootstrapped UUID != disk.uuid → DiskMismatchError."""
        registered_uuid = "REGISTERED-UUID"
        actual_uuid = "DIFFERENT-UUID"
        plist_output = _plist_bytes(actual_uuid).decode("utf-8")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = plist_output
        mock_result.stderr = ""

        disk = _make_disk(mount_path=str(tmp_path), uuid=registered_uuid)
        with patch("os.path.ismount", return_value=True):
            with patch("personalscraper.indexer.merkle.subprocess.run", return_value=mock_result):
                with pytest.raises(DiskMismatchError):
                    guard_disk_mounted(disk)

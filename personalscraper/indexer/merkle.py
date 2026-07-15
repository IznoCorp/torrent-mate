"""Merkle root computation and disk-sentinel guard for the media indexer.

Provides:
- :class:`FileFingerprint` — lightweight record used to build a Merkle root.
- :func:`compute_merkle_root` — deterministic xxh3_64 hash over a set of files.
- :func:`compute_merkle_delta` — ratio of fresh files whose tier-1 fingerprint differs from stored.
- :class:`DiskMountStatus` — enum classifying a disk's mount state.
- :func:`_resolve_volume_root` — walk ancestors until a real OS mount point is found.
- :func:`bootstrap_disk_identity` — write a ``.personalscraper-disk-id`` sentinel to a disk.
- :func:`verify_disk_mounted` — classify a disk's mount state without side effects.
- :func:`guard_disk_mounted` — raise on any non-verified mount state; bootstrap on NO_SENTINEL.

Custom exceptions:
- :class:`BootstrapError` — diskutil unavailable or returned no VolumeUUID.
- :class:`DiskUnmountedError` — disk is not mounted.
- :class:`DiskMismatchError` — sentinel UUID does not match the registered disk UUID.
- :class:`DiskBulkChangeDetected` — Merkle delta exceeds the configured freeze threshold.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import xxhash

from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("indexer.merkle")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Filename of the per-disk identity sentinel written by :func:`bootstrap_disk_identity`.
SENTINEL_FILENAME: str = ".personalscraper-disk-id"


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class BootstrapError(RuntimeError):
    """Raised when disk identity bootstrap fails.

    Args:
        message: Human-readable description of the failure.
    """


class DiskUnmountedError(RuntimeError):
    """Raised when a disk is not currently mounted.

    Args:
        uuid: UUID of the disk that is not mounted.
    """


class DiskMismatchError(RuntimeError):
    """Raised when the sentinel UUID does not match the registered disk UUID.

    Args:
        uuid: UUID of the disk as registered in the database.
        expected: UUID that was expected (same as ``uuid`` in most cases).
        found: UUID found in the sentinel file, or ``None`` if not applicable.
    """

    def __init__(self, uuid: str, expected: str | None = None, found: str | None = None) -> None:
        """Initialize with disk UUID plus optional expected/found pair."""
        self.uuid = uuid
        self.expected = expected
        self.found = found
        detail = f" (expected={expected!r}, found={found!r})" if expected or found else ""
        super().__init__(f"Disk UUID mismatch for disk {uuid!r}{detail}")


class DiskBulkChangeDetected(RuntimeError):
    """Raised when the Merkle delta exceeds the configured freeze threshold.

    This typically indicates a bulk restore or disk swap rather than organic
    file-level drift, and scanning is halted to avoid recording stale state.

    Attributes:
        delta: Fraction of fresh files whose tier-1 fingerprint differs from
            stored, in the range ``[0.0, 1.0]``.
        disk_uuid: UUID of the disk that triggered the freeze.
    """

    def __init__(self, delta: float, disk_uuid: str) -> None:
        """Initialize with delta ratio and disk UUID.

        Args:
            delta: Fraction of changed files (0.0–1.0).
            disk_uuid: UUID of the affected disk.
        """
        self.delta = delta
        self.disk_uuid = disk_uuid
        super().__init__(f"Disk {disk_uuid!r} bulk change detected: {delta:.0%} files changed")


# ---------------------------------------------------------------------------
# DiskMountStatus
# ---------------------------------------------------------------------------


class DiskMountStatus(str, Enum):
    """Classification of a disk's mount state.

    Members:
        MOUNTED_AND_VERIFIED: Disk is mounted and its sentinel UUID matches the registered UUID.
        MOUNTED_WRONG_DISK: Disk is mounted but the sentinel UUID differs from the registered UUID.
        UNMOUNTED: The mount path is absent or ``os.path.ismount`` returns ``False``.
        NO_SENTINEL: Disk appears mounted but the sentinel file is absent or unreadable.
    """

    MOUNTED_AND_VERIFIED = "MOUNTED_AND_VERIFIED"
    MOUNTED_WRONG_DISK = "MOUNTED_WRONG_DISK"
    UNMOUNTED = "UNMOUNTED"
    NO_SENTINEL = "NO_SENTINEL"


# ---------------------------------------------------------------------------
# FileFingerprint
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileFingerprint:
    """Lightweight per-file record used to build a Merkle root.

    Args:
        path_id: Primary key of the ``path`` row in the indexer database.
        size: File size in bytes (``st_size``).
        mtime_ns: File modification time in nanoseconds (``st_mtime_ns``).
        oshash: 16-character lowercase hex OpenSubtitles hash.
    """

    path_id: int
    size: int
    mtime_ns: int
    oshash: str


# ---------------------------------------------------------------------------
# Merkle root
# ---------------------------------------------------------------------------


def compute_merkle_root(files: Iterable[FileFingerprint]) -> str:
    r"""Compute a deterministic xxh3_64 hash over a collection of file fingerprints.

    Files are sorted by the full fingerprint tuple ``(path_id, size, mtime_ns,
    oshash)`` before hashing so the result is independent of iteration order
    even when several files share a ``path_id`` (the schema's ``path`` row
    refers to a directory, so a directory with N files yields N fingerprints
    with the same ``path_id`` — DEV #11). Each file contributes one UTF-8
    line of the form ``"{path_id}|{size}|{mtime_ns}|{oshash}\n"``. An empty
    input returns the hash of zero bytes (still a valid 16-char hex string).

    Args:
        files: Iterable of :class:`FileFingerprint` objects.  May be empty.

    Returns:
        A 16-character lowercase hex string (xxh3_64 digest).
    """
    sorted_files = sorted(files, key=lambda f: (f.path_id, f.size, f.mtime_ns, f.oshash))
    joined = b"".join(f"{f.path_id}|{f.size}|{f.mtime_ns}|{f.oshash}\n".encode("utf-8") for f in sorted_files)
    return xxhash.xxh3_64(joined).hexdigest()


def compute_merkle_delta(
    stored_files: Iterable[FileFingerprint],
    fresh_files: Iterable[FileFingerprint],
) -> float:
    """Compute the fraction of fresh files whose tier-1 fingerprint differs from stored.

    ``path_id`` refers to a *directory* row, so a directory with N files yields
    N fingerprints sharing the same ``path_id`` (DEV #11).  The lookup therefore
    keys on ``(path_id, oshash)`` — the fresh sample reuses the stored ``oshash``
    (:func:`~personalscraper.indexer.scanner._walker._sample_fresh_fingerprints`
    never recomputes it), so the pair identifies one file on both sides.  Keying
    on ``path_id`` alone would keep a single fingerprint per directory and count
    every sibling file as changed (82–86% spurious delta on a real TV library —
    2026-07-15 freeze incident).

    A file is considered "different" if its ``(path_id, oshash)`` pair does not
    appear in the stored set at all (new path — may indicate a bulk restore with
    re-indexed paths), or if ``size`` or ``mtime_ns`` differ from the stored
    entry for the same pair.

    Args:
        stored_files: Iterable of :class:`FileFingerprint` objects from the
            indexer database (previous scan state).  May be empty.
        fresh_files: Iterable of :class:`FileFingerprint` objects freshly
            sampled from the filesystem.  May be empty.

    Returns:
        A float in ``[0.0, 1.0]`` representing the fraction of fresh files
        that differ from stored.  Returns ``0.0`` when *fresh_files* is empty.
    """
    # Build a lookup of stored fingerprints by (path_id, oshash) for O(1)
    # comparison — one entry per FILE, not per directory.
    stored_map: dict[tuple[int, str], FileFingerprint] = {(fp.path_id, fp.oshash): fp for fp in stored_files}

    differs_count = 0
    total_fresh_count = 0

    for fresh in fresh_files:
        total_fresh_count += 1
        stored = stored_map.get((fresh.path_id, fresh.oshash))
        if stored is None:
            # File not found in stored set — counts as different.
            differs_count += 1
        elif fresh.size != stored.size or fresh.mtime_ns != stored.mtime_ns:
            # A tier-1 stat field differs — counts as different.
            differs_count += 1

    if total_fresh_count == 0:
        return 0.0

    return differs_count / total_fresh_count


# ---------------------------------------------------------------------------
# Volume root resolution
# ---------------------------------------------------------------------------


def _resolve_volume_root(p: Path) -> Path:
    """Walk up the ancestor chain until a real OS mount point is found.

    ``os.path.ismount`` returns ``True`` for actual volume mount roots (e.g.
    ``/Volumes/Disk1``) but ``False`` for subdirectories inside a volume (e.g.
    ``/Volumes/Disk1/medias``).  When ``Config.disks[].path`` points to a
    subdirectory of a volume (the common case when a disk is shared), this
    helper resolves the underlying mount root so that ``diskutil`` and sentinel
    operations target the correct path.

    Args:
        p: Absolute path to start the search from (typically ``DiskConfig.path``
            or ``DiskRow.mount_path``).

    Returns:
        The nearest ancestor (inclusive) that satisfies ``os.path.ismount``.
        Falls back to ``p`` itself when the filesystem root is reached without
        finding a mount point (degenerate case — should not occur in practice).
    """
    candidate = p.resolve()
    while True:
        if os.path.ismount(str(candidate)):
            return candidate
        parent = candidate.parent
        if parent == candidate:
            # Reached filesystem root without finding a mount point — return p as-is.
            return p.resolve()
        candidate = parent


# ---------------------------------------------------------------------------
# Disk identity bootstrap
# ---------------------------------------------------------------------------


def bootstrap_disk_identity(mount_path: Path) -> str:
    """Write a UUID sentinel to the volume root of a disk and return the UUID.

    Resolves the actual OS mount root from ``mount_path`` (which may be a
    subdirectory, e.g. ``/Volumes/Disk1/medias``) using
    :func:`_resolve_volume_root`, then calls
    ``diskutil info -plist <volume_root>`` to retrieve the ``VolumeUUID``
    assigned by macOS.  The sentinel file is written at
    ``<volume_root>/<SENTINEL_FILENAME>`` so it is per-volume, not per-subdir.

    Args:
        mount_path: Absolute path to the disk's configured path.  May be the
            mount root itself or a subdirectory of it.

    Returns:
        The ``VolumeUUID`` string extracted from diskutil output.

    Raises:
        BootstrapError: If ``diskutil`` is not on ``PATH``, returns a non-zero
            exit code, or the plist does not contain a ``VolumeUUID``.
    """
    # Resolve to the actual OS mount root so diskutil receives a valid path.
    volume_root = _resolve_volume_root(mount_path)

    try:
        result = subprocess.run(
            ["diskutil", "info", "-plist", str(volume_root)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        raise BootstrapError("diskutil not available on this system")

    if result.returncode != 0:
        # stderr is often empty for diskutil failures; try parsing the plist
        # ErrorMessage key for a more informative message.
        error_detail: str = result.stderr.strip()
        if not error_detail and result.stdout:
            try:
                err_plist: dict[str, object] = plistlib.loads(result.stdout.encode("utf-8"))
                raw_msg = err_plist.get("ErrorMessage", "")
                error_detail = str(raw_msg) if raw_msg else ""
            except Exception:  # noqa: BLE001 — best-effort plist parse
                pass
        raise BootstrapError(f"diskutil failed: {error_detail}")

    plist_data: dict[str, object] = plistlib.loads(result.stdout.encode("utf-8"))
    raw_uuid = plist_data.get("VolumeUUID", "")
    volume_uuid: str = str(raw_uuid) if raw_uuid else ""
    if not volume_uuid:
        raise BootstrapError("diskutil returned no VolumeUUID")

    # Write sentinel at the volume root, not at the configured subdir,
    # so it is tied to the volume identity rather than a specific subdir path.
    sentinel_path = volume_root / SENTINEL_FILENAME
    sentinel_path.write_text(volume_uuid, encoding="utf-8")

    log.info(
        "indexer.disk.bootstrapped",
        disk_uuid=volume_uuid,
        mount_path=str(mount_path),
        volume_root=str(volume_root),
    )
    return volume_uuid


# ---------------------------------------------------------------------------
# Disk mount verification
# ---------------------------------------------------------------------------


def verify_disk_mounted(disk: DiskRow) -> DiskMountStatus:
    """Classify the mount state of a disk without performing any side effects.

    Resolves the actual OS mount root from ``disk.mount_path`` (which may be a
    subdirectory, e.g. ``/Volumes/Disk1/medias``) via :func:`_resolve_volume_root`,
    then checks ``os.path.ismount`` against that root.  The sentinel file is read
    from ``<volume_root>/<SENTINEL_FILENAME>`` (not from the configured subdir),
    mirroring the placement chosen by :func:`bootstrap_disk_identity`.

    Does **not** bootstrap a missing sentinel — that decision belongs to the
    caller (:func:`guard_disk_mounted`).

    Args:
        disk: :class:`~personalscraper.indexer.schema.DiskRow` describing the
            disk to verify.  ``disk.mount_path`` may be ``None``.

    Returns:
        A :class:`DiskMountStatus` value classifying the current state.
    """
    if disk.mount_path is None:
        return DiskMountStatus.UNMOUNTED

    # Resolve to the actual OS mount root: a subdir like /Volumes/Disk1/medias
    # would return False from os.path.ismount, masking a live volume.
    volume_root = _resolve_volume_root(Path(disk.mount_path))
    if not os.path.ismount(str(volume_root)):
        return DiskMountStatus.UNMOUNTED

    # Read sentinel from the volume root, where bootstrap_disk_identity wrote it.
    sentinel_path = volume_root / SENTINEL_FILENAME
    try:
        sentinel_content = sentinel_path.read_text(encoding="utf-8").strip()
    except OSError:
        # File missing or unreadable — treat as NO_SENTINEL.
        return DiskMountStatus.NO_SENTINEL

    if sentinel_content == disk.uuid:
        return DiskMountStatus.MOUNTED_AND_VERIFIED

    return DiskMountStatus.MOUNTED_WRONG_DISK


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------


def guard_disk_mounted(disk: DiskRow) -> None:
    """Raise if a disk is not mounted and verified; bootstrap a missing sentinel.

    Decision table:

    * ``UNMOUNTED`` → raises :class:`DiskUnmountedError`.
    * ``MOUNTED_AND_VERIFIED`` → returns ``None`` (happy path).
    * ``NO_SENTINEL`` → calls :func:`bootstrap_disk_identity`.  If the returned
      UUID matches ``disk.uuid``, sentinel is re-created and returns ``None``.
      Otherwise raises :class:`DiskMismatchError`.
    * ``MOUNTED_WRONG_DISK`` → raises :class:`DiskMismatchError`.

    Args:
        disk: :class:`~personalscraper.indexer.schema.DiskRow` to guard.

    Raises:
        DiskUnmountedError: The disk is not mounted.
        DiskMismatchError: A disk is mounted at ``disk.mount_path`` but its
            sentinel UUID does not match ``disk.uuid``.
    """
    status = verify_disk_mounted(disk)

    if status is DiskMountStatus.UNMOUNTED:
        raise DiskUnmountedError(disk.uuid)

    if status is DiskMountStatus.MOUNTED_AND_VERIFIED:
        return None

    if status is DiskMountStatus.NO_SENTINEL:
        # mount_path is guaranteed non-None here because UNMOUNTED was already excluded.
        assert disk.mount_path is not None  # narrowing for mypy
        bootstrapped_uuid = bootstrap_disk_identity(Path(disk.mount_path))
        if bootstrapped_uuid == disk.uuid:
            return None
        raise DiskMismatchError(disk.uuid, expected=disk.uuid, found=bootstrapped_uuid)

    # MOUNTED_WRONG_DISK — read sentinel from volume root for the mismatch detail.
    assert disk.mount_path is not None  # narrowing for mypy (UNMOUNTED already excluded)
    wrong_root = _resolve_volume_root(Path(disk.mount_path))
    sentinel_path = wrong_root / SENTINEL_FILENAME
    try:
        found_uuid = sentinel_path.read_text(encoding="utf-8").strip()
    except OSError:
        found_uuid = "<unreadable>"
    raise DiskMismatchError(disk.uuid, expected=disk.uuid, found=found_uuid)

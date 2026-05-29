"""Low-level transfer primitives for dispatch operations.

All functions are standalone (no Dispatcher dependency). Extracted from
``dispatcher.py`` during the module split so that ``_movie.py`` and
``_tv.py`` can call them directly.

Functions:
    force_rmtree: Remove a directory tree, handling macOS permission errors.
    rsync: Execute rsync for cross-filesystem transfer.
    rsync_merge: Execute rsync with backup for merge operations.
    restore_merge_backup: Restore overwritten files from merge backup.
    verify_transfer: Verify file sizes match after transfer.
    has_ntfs_illegal_names: Check for NTFS-illegal characters in filenames.
    dir_size_gb: Calculate total size of a directory in GB.
    dir_stats: Return (size_bytes, max_mtime_ns) for all files.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability
from personalscraper.logger import get_logger
from personalscraper.text_utils import _NTFS_ILLEGAL

log = get_logger("dispatcher.transfer")


def _build_rsync_cmd(
    source: Path,
    dest: Path,
    capability: FilesystemCapability,
    *,
    delete: bool = False,
    backup_dir: Path | None = None,
) -> list[str]:
    """Build the rsync argv from a :class:`FilesystemCapability`.

    Single source of truth for both :func:`rsync` and :func:`rsync_merge` —
    replaces the two previously hardcoded literal flag lists.  The capability
    provides the full rsync flag prefix; the ``"rsync"`` binary name and the
    source/dest paths are added here.

    Argv layout (matches the legacy ordering byte-for-byte for ``ntfs_macfuse``)::

        ["rsync", *capability.rsync_flags, (--delete?),
         (--backup, --backup-dir=<dir>?), f"{source}/", str(dest)]

    Args:
        source: Source directory.
        dest: Destination directory.
        capability: Filesystem capability for the destination volume.
        delete: When True, append ``--delete`` (used by :func:`rsync`).
        backup_dir: When set, append ``--backup --backup-dir=<path>`` (used by
            :func:`rsync_merge`).

    Returns:
        Complete rsync argv list (including the leading ``"rsync"`` binary name).
    """
    cmd = ["rsync", *capability.rsync_flags]
    if delete:
        cmd.append("--delete")
    if backup_dir is not None:
        cmd.append("--backup")
        cmd.append(f"--backup-dir={backup_dir}")
    cmd.extend([f"{source}/", str(dest)])
    return cmd


def force_rmtree(path: Path) -> None:
    """Remove a directory tree, handling macOS permission errors.

    Uses an onerror handler that adds owner rwx permissions before
    retrying deletion. Handles .actors and other macOS-protected dirs.
    Raises OSError if the directory could not be fully removed.

    Args:
        path: Directory to remove.

    Raises:
        OSError: If files remain after all retry attempts.
    """
    errors: list[tuple[str, OSError]] = []

    def _on_error(func: Callable[..., Any], fpath: str, exc: Any) -> None:
        """Add owner rwx permissions and retry deletion.

        Args:
            func: The function that raised the exception (os.remove, etc.).
            fpath: Path of the file/dir that could not be removed.
            exc: Exception info -- tuple (type, value, tb) for onerror,
                or BaseException for onexc (Python 3.12+).
        """
        try:
            os.chmod(fpath, stat.S_IRWXU)
            func(fpath)
        except OSError as e:
            errors.append((fpath, e))

    # Python 3.12 uses onexc; earlier versions use onerror.
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_on_error)
    else:
        shutil.rmtree(path, onerror=_on_error)

    if errors and path.exists():
        for fpath, err in errors[:5]:
            log.warning("rmtree_partial_failure", path=fpath, error=str(err))
        raise OSError(f"force_rmtree incomplete for {path}: {len(errors)} file(s) could not be removed")


def rsync(
    source: Path,
    dest: Path,
    delete: bool = False,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> bool:
    """Execute rsync for cross-filesystem transfer.

    The rsync flag prefix is provided by *capability*.  For the default
    ``NTFS_MACFUSE`` capability the flags are byte-identical to the legacy
    hardcoded list (``-a --no-perms --no-owner --no-group --no-times
    --omit-dir-times --inplace --partial --exclude=.DS_Store --exclude=._*``).
    The rationale for each NTFS flag is documented on
    :data:`personalscraper.indexer._fs_capability.NTFS_MACFUSE` and in
    ``audit/13-ntfs-cache-pressure.md``; ``--checksum`` is intentionally
    omitted (the size+mtime heuristic is correct for an immutable library).

    Args:
        source: Source path (trailing / added for contents).
        dest: Destination path.
        delete: If True, delete extraneous files in dest.
        capability: Filesystem capability for the destination volume.
            Defaults to ``NTFS_MACFUSE`` (byte-identical to the legacy
            hardcoded flags) so every existing caller that does not pass a
            capability is unaffected.

    Returns:
        True if rsync succeeded (returncode 0).
    """
    cmd = _build_rsync_cmd(source, dest, capability, delete=delete)

    log.info("rsync_start", source=source.name, dest=str(dest))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            log.error("rsync_failed", returncode=proc.returncode, stderr=proc.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("rsync_timeout", source=source.name)
        return False


def rsync_merge(
    source: Path,
    dest: Path,
    backup_dir: Path,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> bool:
    """Execute rsync with backup for merge operations.

    Backs up any overwritten files to backup_dir so they can
    be restored on failure.  The rsync flag prefix is provided by
    *capability* (same flags as :func:`rsync`); ``--backup`` /
    ``--backup-dir`` are appended by :func:`_build_rsync_cmd`.  Note that
    ``--inplace`` is compatible with ``--backup``: rsync still writes the
    backup copy to ``backup_dir`` before overwriting the destination in place.

    Args:
        source: Source directory.
        dest: Destination directory.
        backup_dir: Directory to store backups of overwritten files.
        capability: Filesystem capability for the destination volume.
            Defaults to ``NTFS_MACFUSE`` (byte-identical to the legacy flags).

    Returns:
        True if rsync succeeded.
    """
    cmd = _build_rsync_cmd(source, dest, capability, backup_dir=backup_dir)

    log.info("rsync_merge_start", source=source.name, dest=str(dest), backup=str(backup_dir))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            log.error("rsync_merge_failed", returncode=proc.returncode, stderr=proc.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        log.error("rsync_merge_timeout", source=source.name)
        return False


def restore_merge_backup(dest: Path, backup_dir: Path) -> int:
    """Restore overwritten files from merge backup.

    Copies files from backup_dir back to their original locations
    within dest, then removes the backup directory. Continues
    restoring remaining files even if one file fails.

    Args:
        dest: Destination directory to restore into.
        backup_dir: Backup directory with original files.

    Returns:
        Number of files restored (0 if backup_dir doesn't exist).
    """
    if not backup_dir.exists():
        return 0

    restored = 0
    failed = 0
    for backup_file in backup_dir.rglob("*"):
        if not backup_file.is_file():
            continue
        rel = backup_file.relative_to(backup_dir)
        original = dest / rel
        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup_file, original)
            restored += 1
            log.info("backup_file_restored", rel=str(rel))
        except OSError as e:
            failed += 1
            log.error("backup_file_restore_failed", rel=str(rel), error=str(e))

    if failed:
        log.error("merge_backup_restore_partial", restored=restored, failed=failed)
    else:
        # All files restored -- safe to remove backup
        try:
            force_rmtree(backup_dir)
        except OSError as e:
            log.warning("backup_dir_cleanup_failed", path=str(backup_dir), error=str(e))

    return restored


def verify_transfer(source: Path, dest: Path) -> bool:
    """Verify file sizes match after transfer.

    Args:
        source: Source directory.
        dest: Destination directory.

    Returns:
        True if all file sizes match.
    """
    for src_file in source.rglob("*"):
        try:
            if not src_file.is_file():
                continue
        except OSError:
            continue  # Broken symlink or NTFS metadata
        rel = src_file.relative_to(source)
        dst_file = dest / rel
        if not dst_file.exists():
            log.warning("verify_missing_file", rel=str(rel))
            return False
        try:
            if src_file.stat().st_size != dst_file.stat().st_size:
                log.warning("verify_size_mismatch", rel=str(rel))
                return False
        except OSError as exc:
            log.warning("verify_stat_failed", rel=str(rel), error=str(exc))
    return True


def has_ntfs_illegal_names(
    directory: Path,
    pattern: re.Pattern[str] | None = _NTFS_ILLEGAL,
) -> bool:
    r"""Check if any file in directory has filesystem-illegal characters.

    Scans recursively for filenames matching *pattern*.  Used as a pre-check
    before rsync to filesystems with naming restrictions.

    Args:
        directory: Directory to scan.
        pattern: Compiled regex for illegal characters.  Defaults to the NTFS
            illegal-character set (``<>:"/\|?*``) so every existing caller is
            unaffected.  Pass ``None`` to skip the check entirely (POSIX
            filesystems with no naming restrictions, e.g. APFS/HFS+).

    Returns:
        True if any file has illegal characters (always False when *pattern*
        is ``None``).
    """
    if pattern is None:
        return False
    illegal = [f for f in directory.rglob("*") if f.is_file() and pattern.search(f.name)]
    for f in illegal:
        log.warning("ntfs_illegal_filename", path=str(f))
    return len(illegal) > 0


def dir_size_gb(directory: Path) -> float:
    """Calculate total size of a directory in GB.

    Args:
        directory: Directory to measure.

    Returns:
        Size in GB.
    """
    total = 0
    for f in directory.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass  # Broken symlinks, NTFS metadata permission errors
    return total / (1024**3)


def dir_stats(directory: Path) -> tuple[int, int]:
    """Return ``(size_bytes, max_mtime_ns)`` for all files in *directory*.

    Args:
        directory: Directory to scan.

    Returns:
        Tuple of total size in bytes and the highest ``st_mtime_ns`` found.
    """
    total_size = 0
    max_mtime = 0
    for f in directory.rglob("*"):
        try:
            if f.is_file():
                st = f.stat()
                total_size += st.st_size
                if st.st_mtime_ns > max_mtime:
                    max_mtime = st.st_mtime_ns
        except OSError:
            pass
    return total_size, max_mtime

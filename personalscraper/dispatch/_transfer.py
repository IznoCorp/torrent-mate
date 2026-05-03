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
import shutil
import stat
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from personalscraper.logger import get_logger
from personalscraper.text_utils import _NTFS_ILLEGAL

log = get_logger("dispatcher.transfer")


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


def rsync(source: Path, dest: Path, delete: bool = False) -> bool:
    """Execute rsync for cross-filesystem transfer.

    Args:
        source: Source path (trailing / added for contents).
        dest: Destination path.
        delete: If True, delete extraneous files in dest.

    Returns:
        True if rsync succeeded (returncode 0).
    """
    # -a minus -pgo: NTFS via macFUSE doesn't support Unix permissions
    # Exclude macOS metadata files -- .DS_Store and ._* AppleDouble files
    # cause rsync errors on NTFS targets which don't support them.
    cmd = [
        "rsync",
        "-a",
        "--no-perms",
        "--no-owner",
        "--no-group",
        "--partial",
        "--checksum",
        "--exclude=.DS_Store",
        "--exclude=._*",
    ]
    if delete:
        cmd.append("--delete")
    cmd.extend([f"{source}/", str(dest)])

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
) -> bool:
    """Execute rsync with backup for merge operations.

    Backs up any overwritten files to backup_dir so they can
    be restored on failure.

    Args:
        source: Source directory.
        dest: Destination directory.
        backup_dir: Directory to store backups of overwritten files.

    Returns:
        True if rsync succeeded.
    """
    # Exclude macOS metadata files -- same rationale as rsync()
    cmd = [
        "rsync",
        "-a",
        "--no-perms",
        "--no-owner",
        "--no-group",
        "--partial",
        "--checksum",
        "--exclude=.DS_Store",
        "--exclude=._*",
        "--backup",
        f"--backup-dir={backup_dir}",
        f"{source}/",
        str(dest),
    ]

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


def has_ntfs_illegal_names(directory: Path) -> bool:
    r"""Check if any file in directory has NTFS-illegal characters.

    Scans recursively for filenames containing <>:"/\|?*.
    Used as a pre-check before rsync to NTFS disks.

    Args:
        directory: Directory to scan.

    Returns:
        True if any file has illegal characters.
    """
    illegal = [f for f in directory.rglob("*") if f.is_file() and _NTFS_ILLEGAL.search(f.name)]
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

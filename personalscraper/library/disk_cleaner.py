"""Library disk cleaner — remove .actors/, empty dirs, junk files.

Dry-run by default. Requires --apply to actually delete.
Handles NTFS deletion failures gracefully (per-item error, continues).
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.dispatch.disk_scanner import DiskConfig

logger = logging.getLogger(__name__)

_JUNK_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


@dataclass
class CleanResult:
    """Result of a library cleanup operation.

    Attributes:
        dry_run: Whether this was a dry-run (no actual deletions).
        deleted_count: Number of items deleted (or would-be-deleted in dry-run).
        error_count: Number of deletion failures (NTFS errors, etc.).
        freed_bytes: Approximate bytes freed (or would be freed).
        details: Per-item details (path + action).
        errors: Per-item error details (path + error message).
    """

    dry_run: bool = True
    deleted_count: int = 0
    error_count: int = 0
    freed_bytes: int = 0
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _dir_size(path: Path) -> int:
    """Calculate total byte size of a directory recursively."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    continue
    except OSError as exc:
        logger.warning("Cannot measure directory size %s: %s", path, exc)
    return total


def _delete_dir(path: Path, result: CleanResult, dry_run: bool, label: str) -> None:
    """Delete a directory, handling NTFS errors gracefully.

    Args:
        path: Directory to delete.
        result: CleanResult to update.
        dry_run: If True, only count without deleting.
        label: Human label for logging (e.g. ".actors", "empty dir").
    """
    size = _dir_size(path)
    if dry_run:
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"[DRY-RUN] Would delete {label}: {path} ({size} bytes)")
        return

    try:
        shutil.rmtree(path)
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"Deleted {label}: {path} ({size} bytes)")
        logger.info("Deleted %s: %s", label, path)
    except OSError as exc:
        result.error_count += 1
        result.errors.append(f"Failed to delete {label}: {path} — {exc}")
        logger.warning("NTFS deletion failed for %s: %s — %s", label, path, exc)


def _delete_file(path: Path, result: CleanResult, dry_run: bool, label: str) -> None:
    """Delete a single file, handling errors gracefully.

    Args:
        path: File to delete.
        result: CleanResult to update.
        dry_run: If True, only count without deleting.
        label: Human label for logging.
    """
    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    if dry_run:
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"[DRY-RUN] Would delete {label}: {path}")
        return

    try:
        path.unlink()
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"Deleted {label}: {path}")
    except OSError as exc:
        result.error_count += 1
        result.errors.append(f"Failed to delete {label}: {path} — {exc}")
        logger.warning("Deletion failed for %s: %s — %s", label, path, exc)


def _is_effectively_empty(directory: Path) -> bool:
    """Check if a directory is empty or contains only junk files."""
    try:
        for item in directory.iterdir():
            if item.name not in _JUNK_FILES and not item.name.startswith("._"):
                return False
        return True
    except OSError:
        return False


def clean_library(
    disk_configs: list[DiskConfig],
    apply: bool = False,
    only: str | None = None,
    disk_filter: str | None = None,
    category_filter: str | None = None,
) -> CleanResult:
    """Clean the media library across storage disks.

    Dry-run by default — set apply=True to actually delete.

    Args:
        disk_configs: List of DiskConfig objects from Settings.
        apply: If True, actually delete files. If False, only report.
        only: Filter cleanup type: "actors", "empty", "junk", "release", or None (all).
        disk_filter: Only clean this disk. None = all.
        category_filter: Only clean this category. None = all.

    Returns:
        CleanResult with counts and details.
    """
    result = CleanResult(dry_run=not apply)

    clean_actors = only in (None, "actors")
    clean_empty = only in (None, "empty")
    clean_junk = only in (None, "junk")
    clean_release = only in (None, "release")

    for config in disk_configs:
        if disk_filter and config.name != disk_filter:
            continue
        if not config.path.exists():
            logger.warning("Disk not mounted: %s (%s)", config.name, config.path)
            continue

        for category_dir in sorted(config.path.iterdir()):
            if not category_dir.is_dir():
                continue
            if category_dir.name not in config.categories:
                continue
            if category_filter and category_dir.name != category_filter:
                continue

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                _clean_media_dir(
                    media_dir, result, not apply,
                    clean_actors, clean_empty, clean_junk, clean_release,
                )

    return result


def _clean_media_dir(
    media_dir: Path,
    result: CleanResult,
    dry_run: bool,
    clean_actors: bool,
    clean_empty: bool,
    clean_junk: bool,
    clean_release: bool,
) -> None:
    """Clean a single media directory.

    Args:
        media_dir: Path to media directory.
        result: CleanResult to update.
        dry_run: If True, only count.
        clean_actors: Whether to remove .actors/.
        clean_empty: Whether to remove empty dirs.
        clean_junk: Whether to remove junk files.
        clean_release: Whether to remove release-group artifacts.
    """
    try:
        entries = list(media_dir.iterdir())
    except OSError as exc:
        result.error_count += 1
        result.errors.append(f"Cannot list directory: {media_dir} — {exc}")
        logger.warning("Cannot list directory %s: %s", media_dir, exc)
        return

    for item in entries:
        name = item.name

        # .actors directory
        if clean_actors and name == ".actors" and item.is_dir():
            _delete_dir(item, result, dry_run, ".actors")
            continue

        # Junk files (including macOS resource forks "._*")
        if clean_junk and (name in _JUNK_FILES or name.startswith("._")) and item.is_file():
            _delete_file(item, result, dry_run, "junk file")
            continue

        # Empty directories and release-group artifacts
        if item.is_dir() and _is_effectively_empty(item):
            # Detect release-group style names (contain dots + group suffix)
            is_release = "." in name and any(
                c.isupper() for c in name.split(".")[-1] if c.isalpha()
            )
            if clean_release and is_release:
                _delete_dir(item, result, dry_run, "release artifact")
            elif clean_empty:
                _delete_dir(item, result, dry_run, "empty dir")

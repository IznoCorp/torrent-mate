"""Sanitize filenames for NTFS compatibility and remove macOS metadata.

Renames files/directories containing NTFS-illegal characters,
removes .DS_Store and ._ resource fork files. Processes directories
bottom-up to handle nested renames correctly.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.text_utils import sanitize_filename

logger = logging.getLogger(__name__)

_FILENAME_ILLEGAL_CHARS = set('<>:"/\\|?*')


@dataclass
class SanitizeResult:
    """Result of sanitizing a single file or directory."""

    path: Path
    action: str  # "renamed", "deleted_duplicate", "deleted_ds_store",
    #              "deleted_resource_fork", "skipped"
    old_name: str | None = None
    new_name: str | None = None


def _has_illegal_chars(name: str) -> bool:
    """Check if a filename contains NTFS-illegal characters.

    Args:
        name: Filename or directory name to check.

    Returns:
        True if name contains at least one NTFS-illegal character.
    """
    return any(c in _FILENAME_ILLEGAL_CHARS for c in name)


def sanitize_files(
    settings: Settings,
    dry_run: bool = False,
) -> list[SanitizeResult]:
    """Sanitize all filenames in staging categories.

    Processes 001-MOVIES/ and 002-TVSHOWS/ recursively.
    Renames NTFS-illegal characters, removes .DS_Store and ._ files.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, log actions without modifying filesystem.

    Returns:
        List of SanitizeResult for each action taken.
    """
    results: list[SanitizeResult] = []
    staging = Path(getattr(settings, "staging_dir", "."))

    for dir_name in (settings.movies_dir_name, settings.tvshows_dir_name):
        cat_dir = staging / dir_name
        if not cat_dir.exists():
            continue
        results.extend(_sanitize_directory(cat_dir, dry_run))

    return results


def _sanitize_directory(root: Path, dry_run: bool) -> list[SanitizeResult]:
    """Sanitize all files and dirs under root, bottom-up.

    Files are processed first (deleting .DS_Store, ._*, renaming illegal
    names). Directories are then processed deepest-first so that a parent
    directory rename does not invalidate already-computed child paths.

    Args:
        root: Directory to scan.
        dry_run: Preview mode — report but do not modify filesystem.

    Returns:
        List of SanitizeResult for each action taken or planned.
    """
    results: list[SanitizeResult] = []

    all_files = []
    all_dirs = []
    for item in root.rglob("*"):
        if item.is_file():
            all_files.append(item)
        elif item.is_dir():
            all_dirs.append(item)

    # Sort dirs by depth descending (deepest first) for bottom-up rename
    all_dirs.sort(key=lambda p: len(p.parts), reverse=True)

    # 1. Process files
    for f in all_files:
        if f.name == ".DS_Store":
            if not dry_run:
                try:
                    f.unlink()
                except OSError as exc:
                    logger.warning("Cannot delete %s: %s", f.name, exc)
                    results.append(SanitizeResult(path=f, action="error", old_name=f.name))
                    continue
            results.append(SanitizeResult(path=f, action="deleted_ds_store", old_name=f.name))
            continue

        if f.name.startswith("._"):
            if not dry_run:
                try:
                    f.unlink()
                except OSError as exc:
                    logger.warning("Cannot delete %s: %s", f.name, exc)
                    results.append(SanitizeResult(path=f, action="error", old_name=f.name))
                    continue
            results.append(SanitizeResult(path=f, action="deleted_resource_fork", old_name=f.name))
            continue

        if _has_illegal_chars(f.name):
            sanitized = sanitize_filename(f.name)
            target = f.parent / sanitized
            if target.exists():
                # Sanitized name already present — legacy file is the duplicate
                if not dry_run:
                    try:
                        f.unlink()
                    except OSError as exc:
                        logger.warning("Cannot delete duplicate %s: %s", f.name, exc)
                        results.append(
                            SanitizeResult(
                                path=f,
                                action="error",
                                old_name=f.name,
                                new_name=sanitized,
                            )
                        )
                        continue
                results.append(
                    SanitizeResult(
                        path=f,
                        action="deleted_duplicate",
                        old_name=f.name,
                        new_name=sanitized,
                    )
                )
            else:
                if not dry_run:
                    try:
                        f.rename(target)
                    except OSError as exc:
                        logger.warning("Cannot rename %s: %s", f.name, exc)
                        results.append(
                            SanitizeResult(
                                path=f,
                                action="error",
                                old_name=f.name,
                                new_name=sanitized,
                            )
                        )
                        continue
                results.append(
                    SanitizeResult(
                        path=f,
                        action="renamed",
                        old_name=f.name,
                        new_name=sanitized,
                    )
                )

    # 2. Process directories (bottom-up so child renames don't orphan parents)
    for d in all_dirs:
        # Path may no longer exist if a parent was already renamed
        if not d.exists():
            continue
        if _has_illegal_chars(d.name):
            sanitized = sanitize_filename(d.name)
            target = d.parent / sanitized
            if target.exists():
                logger.warning("Cannot rename dir %s → %s: target exists", d.name, sanitized)
            else:
                if not dry_run:
                    try:
                        d.rename(target)
                    except OSError as exc:
                        logger.warning("Cannot rename dir %s: %s", d.name, exc)
                results.append(
                    SanitizeResult(
                        path=d,
                        action="renamed",
                        old_name=d.name,
                        new_name=sanitized,
                    )
                )

    return results

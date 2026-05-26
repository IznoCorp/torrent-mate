"""Sanitize filenames for NTFS compatibility and remove macOS metadata.

Renames files/directories containing NTFS-illegal characters,
removes .DS_Store and ._ resource fork files. Processes directories
bottom-up to handle nested renames correctly.
"""

from dataclasses import dataclass
from pathlib import Path

from personalscraper._fs_utils import is_apple_double
from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.logger import get_logger
from personalscraper.sorter.file_type import FileType
from personalscraper.text_utils import sanitize_filename

log = get_logger("enforce.sanitizer")

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
    config: Config,
    dry_run: bool = False,
) -> list[SanitizeResult]:
    """Sanitize all filenames in staging categories.

    Processes {movies_dir}/ and {tvshows_dir}/ recursively.
    Renames NTFS-illegal characters, removes .DS_Store and ._ files.

    Args:
        settings: Pipeline configuration (reserved for future use).
        config: Application config used to resolve staging_dir and category folder names.
        dry_run: If True, log actions without modifying filesystem.

    Returns:
        List of SanitizeResult for each action taken.
    """
    results: list[SanitizeResult] = []
    staging = config.paths.staging_dir

    for dir_name in (
        folder_name(find_by_file_type(config, FileType.MOVIE)),
        folder_name(find_by_file_type(config, FileType.TVSHOW)),
    ):
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
                    log.warning("enforce_sanitize_delete_failed", name=f.name, exc_info=True, error=str(exc))
                    results.append(SanitizeResult(path=f, action="error", old_name=f.name))
                    continue
            results.append(SanitizeResult(path=f, action="deleted_ds_store", old_name=f.name))
            continue

        if is_apple_double(f.name):
            if not dry_run:
                try:
                    f.unlink()
                except OSError as exc:
                    log.warning("enforce_sanitize_delete_failed", name=f.name, exc_info=True, error=str(exc))
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
                        log.warning(
                            "enforce_sanitize_delete_duplicate_failed",
                            name=f.name,
                            exc_info=True,
                            error=str(exc),
                        )
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
                        log.warning("enforce_sanitize_rename_failed", name=f.name, exc_info=True, error=str(exc))
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
                log.warning("enforce_sanitize_dir_target_exists", name=d.name, sanitized=sanitized)
            else:
                if not dry_run:
                    try:
                        d.rename(target)
                    except OSError as exc:
                        log.warning("enforce_sanitize_dir_rename_failed", name=d.name, exc_info=True, error=str(exc))
                results.append(
                    SanitizeResult(
                        path=d,
                        action="renamed",
                        old_name=d.name,
                        new_name=sanitized,
                    )
                )

    return results

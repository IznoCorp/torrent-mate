"""Extracted scraper service module."""

from __future__ import annotations

import re
from pathlib import Path

from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

log = get_logger("scraper")

_TVDB_LANG_MAP: dict[str, str] = {
    "fr": "fra",
    "en": "eng",
    "es": "spa",
    "de": "deu",
    "it": "ita",
    "ja": "jpn",
    "ko": "kor",
    "pt": "por",
    "ru": "rus",
    "zh": "zho",
    "ar": "ara",
    "nl": "nld",
}

_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2} - .+\.\w+$")
_EPISODE_FALLBACK_RE = re.compile(r"^S\d{2}E0*(\d+) - Episode 0*\1\.\w+$", re.IGNORECASE)


def _merge_dirs(source: Path, target: Path) -> tuple[int, int]:
    """Merge contents of source directory into target, then remove source.

    Files in source that already exist in target are replaced
    (source always wins). Subdirectories are merged recursively.
    Per-item errors are logged and skipped — the merge continues
    with remaining items. Source is only removed if fully emptied.

    Args:
        source: Directory to merge from (removed only if fully emptied).
        target: Directory to merge into (must exist).

    Returns:
        Tuple of (moved_count, failed_count).
    """
    import shutil as _shutil

    moved = 0
    failed = 0
    for item in source.iterdir():
        dest = target / item.name
        try:
            if item.is_dir() and dest.is_dir():
                # Recursive merge for subdirectories (e.g. Saison 01/)
                sub_moved, sub_failed = _merge_dirs(item, dest)
                moved += sub_moved
                failed += sub_failed
            else:
                # Move file/dir, replacing if exists
                if dest.exists():
                    if dest.is_dir():
                        _shutil.rmtree(dest)
                    else:
                        dest.unlink()
                _shutil.move(str(item), str(dest))
                moved += 1
        except (OSError, _shutil.Error) as exc:
            failed += 1
            log.warning("merge_item_failed", item=item.name, dest=str(dest), error=str(exc))
    # Remove empty source after merge — preserve if items remain
    try:
        if source.exists() and not any(source.iterdir()):
            source.rmdir()
    except OSError as exc:
        log.warning("merge_source_rmdir_failed", source=source.name, error=str(exc))
    if failed:
        log.warning(
            "merge_partial",
            source=source.name,
            target=target.name,
            moved=moved,
            failed=failed,
        )
    return moved, failed


def _rename_dir_case_safe(source: Path, target: Path) -> Path:
    """Rename a directory, handling case-only renames on case-insensitive filesystems."""
    if target.exists():
        try:
            if source.samefile(target):
                tmp = source.with_name(f"{source.name}.case-rename-tmp")
                suffix = 1
                while tmp.exists():
                    tmp = source.with_name(f"{source.name}.case-rename-tmp-{suffix}")
                    suffix += 1
                source.rename(tmp)
                tmp.rename(target)
                return target
        except OSError:
            pass
    source.rename(target)
    return target


def _cleanup_stale_files(directory: Path, old_prefix: str, new_prefix: str) -> int:
    """Remove stale files with old title prefix when sanitized versions exist.

    After a folder rename (e.g., stripping ':'), old artwork/NFO files
    may remain alongside the new sanitized versions. This function removes
    the old duplicates only when a corresponding new file exists.

    Args:
        directory: Directory to scan for stale files.
        old_prefix: The old title prefix (e.g., "Title : Subtitle").
        new_prefix: The new sanitized prefix (e.g., "Title Subtitle").

    Returns:
        Number of stale files removed.
    """
    if old_prefix == new_prefix:
        return 0

    removed = 0
    for f in list(directory.iterdir()):
        if not f.is_file() or not f.name.startswith(old_prefix):
            continue
        # Build the expected sanitized equivalent
        new_name = new_prefix + f.name[len(old_prefix) :]
        if (directory / new_name).exists():
            try:
                f.unlink()
                log.info("stale_file_removed", filename=f.name)
                removed += 1
            except OSError as exc:
                log.warning("stale_file_remove_failed", filename=f.name, error=str(exc))
    return removed


def _cleanup_empty_release_dirs(show_dir: Path) -> int:
    """Remove release-group subdirectories with no video files.

    After episodes are moved to Saison XX/ directories, the original
    release-group subdirectories (e.g., Show.S01E01.1080p.WEB-GROUP/)
    may be left empty or contain only residual NFOs. This function
    removes them if they have no video files (recursively).

    Skips hidden directories (.actors/) and season directories (Saison XX/).

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        Number of directories removed.
    """
    import shutil

    removed = 0
    for subdir in list(show_dir.iterdir()):
        if not subdir.is_dir():
            continue
        if subdir.name.startswith("."):
            continue
        if SEASON_DIR_RE.match(subdir.name):
            continue
        # Check if subdir has any video files (recursively)
        has_video = any(f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS for f in subdir.rglob("*"))
        if has_video:
            continue
        non_video_files = [f.name for f in subdir.rglob("*") if f.is_file()]
        if non_video_files:
            log.warning("release_dir_residual_files", directory=subdir.name, files=non_video_files)
        try:
            shutil.rmtree(subdir)
            log.info("release_dir_removed", directory=subdir.name)
            removed += 1
        except OSError as exc:
            log.warning("release_dir_remove_failed", directory=subdir.name, error=str(exc))
    return removed

"""Extracted scraper service module."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.core.media_types import VIDEO_EXTENSIONS, is_archive_filename, is_sample_path
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE

if TYPE_CHECKING:
    from personalscraper.scraper._shared import ScrapeResult

log = get_logger("scraper")

_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2}(?:-E\d{2,})? - .+\.\w+$")
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

    # Same-directory guard: on a case-insensitive filesystem (macOS APFS) a
    # case-only rename target ALIASES the source (``Flow (2024)`` vs
    # ``FLOW (2024)`` are the same directory), so "merging" would walk the
    # source items, see each dest as "already existing" (it IS the source
    # item), unlink it — destroying the only copy — then rmdir the emptied
    # source. Callers must use ``_rename_dir_case_safe`` for that case; this
    # guard makes the mistake harmless instead of data-destroying.
    try:
        if source.samefile(target):
            log.warning("merge_dirs_same_directory_skipped", source=str(source), target=str(target))
            return 0, 0
    except OSError:
        pass  # target does not exist / not statable → a real merge, proceed.

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


def apply_canonical_dir_rename(
    current: Path,
    canonical_name: str,
    *,
    dry_run: bool,
    result: "ScrapeResult",
) -> Path:
    """Rename a media directory to its canonical name (case-safe, NFC-aware).

    The ONE folder rename/merge/case-safe block shared by the movie and TV
    write-back (SCRAPER-04), folded out of the two hand-synchronised copies in
    ``movie_service`` / ``tv_service_write``. Compares ``current.name`` against
    *canonical_name* under NFC normalisation (macOS stores filenames in NFD,
    Python strings are typically NFC — a naive compare treats them as different
    and triggers a rename-into-self merge that empties the folder), then applies
    one of:

    * **no change** — names already match → returns *current* unchanged.
    * **dry-run** — logs the intended action and returns *current*.
    * **target absent** — a plain case-safe rename.
    * **target present, same dir** — a case-only rename on a case-insensitive
      filesystem (``Flow (2024)`` vs ``FLOW (2024)`` alias the same inode) →
      two-step case-safe rename, NEVER a merge (a merge would walk the source,
      see each dest as "already existing", unlink it against itself and destroy
      the only copy of the video).
    * **target present, distinct dir** — merge *current* into it (source wins),
      recording a warning on partial failure.

    On an :class:`OSError` the message is recorded on ``result.error`` and
    *current* is returned unchanged — the caller MUST check ``result.error`` and
    abort. On a successful move ``result.media_path`` is set to the new path.

    Args:
        current: The media directory as it currently exists on disk.
        canonical_name: The desired canonical folder name (already sanitised).
        dry_run: When True, only log the intended action (no filesystem change).
        result: The :class:`ScrapeResult` to update (``media_path`` on success,
            ``error`` on OS failure, ``warnings`` on partial merge).

    Returns:
        The resulting directory path — the new path on a successful rename/merge,
        else *current* (no-op, dry-run, or error).
    """
    if unicodedata.normalize("NFC", current.name) == unicodedata.normalize("NFC", canonical_name):
        return current

    new_path = current.parent / canonical_name
    if dry_run:
        action = "merge into" if new_path.exists() else "rename"
        log.info("media_folder_would_rename", action=action, source=current.name, dest=canonical_name)
        return current

    try:
        if new_path.exists():
            # Case-only rename trap (macOS case-insensitive FS): the target
            # ALIASES the source, so merging would unlink each item against
            # itself. Same-dir → two-step case-safe rename, never a merge.
            try:
                is_same_dir = current.samefile(new_path)
            except OSError:
                is_same_dir = False
            if is_same_dir:
                _rename_dir_case_safe(current, new_path)
                log.info("media_folder_renamed", source=current.name, dest=canonical_name)
            else:
                moved, merge_failed = _merge_dirs(current, new_path)
                log.info("media_folder_merged", source=current.name, dest=canonical_name, items=moved)
                if merge_failed:
                    result.warnings.append(f"Partial merge: {merge_failed} item(s) failed")
        else:
            _rename_dir_case_safe(current, new_path)
            log.info("media_folder_renamed", source=current.name, dest=canonical_name)
    except OSError as exc:
        result.error = f"Rename/merge failed: {exc}"
        log.error("media_folder_rename_failed", source=current.name, dest=canonical_name, error=str(exc))
        return current

    result.media_path = new_path
    return new_path


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
        files = [f for f in subdir.rglob("*") if f.is_file()]
        # Keep the subdir if it still holds a REAL (non-sample) video — sample
        # clips no longer count as content (DEV #1) so a sample-only leftover
        # release dir is removed here.
        has_real_video = any(f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS and not is_sample_path(f) for f in files)
        if has_real_video:
            continue
        # Preserve a subdir that still holds un-extracted archives: extraction
        # failed (or never ran), and deleting it would destroy the only copy of
        # the real content. The no_archive_files verify check blocks dispatch so
        # the operator can extract it manually (DEV #1 safety net).
        if any(is_archive_filename(f.name) for f in files):
            log.warning("release_dir_archive_retained", directory=subdir.name, files=[f.name for f in files])
            continue
        non_video_files = [f.name for f in files]
        if non_video_files:
            log.warning("release_dir_residual_files", directory=subdir.name, files=non_video_files)
        try:
            shutil.rmtree(subdir)
            log.info("release_dir_removed", directory=subdir.name)
            removed += 1
        except OSError as exc:
            log.warning("release_dir_remove_failed", directory=subdir.name, error=str(exc))
    return removed

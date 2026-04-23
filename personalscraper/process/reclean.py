"""Re-clean folder names in category directories.

Detects folder names still containing release-group tokens
(screen_size, video_codec, release_group, etc.) and re-cleans
them via NameCleaner (guessit). Handles target-exists by merging.
When a ``Config`` is supplied, the rename is also propagated to
every configured disk so that staging and storage stay aligned
and the next dispatch treats the item as a merge rather than a
new (duplicate) folder.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.models import StepReport
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.text_utils import sanitize_filename

if TYPE_CHECKING:
    from personalscraper.conf.models import Config

logger = logging.getLogger(__name__)


def _propagate_rename_to_disks(
    config: "Config",
    old_name: str,
    new_name: str,
    dry_run: bool,
) -> list[str]:
    """Rename matching folders on every configured disk from old_name to new_name.

    When reclean renames a folder in staging, the same folder sitting on a
    storage disk (from a previous dispatch) must follow — otherwise the next
    dispatch looks up ``new_name`` on disks, fails to find it, treats the
    staging item as NEW, and creates a duplicate folder next to the old one,
    fragmenting the show/movie across two directories.

    For each disk in ``config.disks``:
      * iterate category subdirectories (skipping unmounted disks)
      * if ``category / old_name`` exists, rename it to ``category / new_name``
      * if the target already exists (merge case), skip and log a warning —
        reclean does not merge across disks, that is dispatch's job

    Args:
        config: Loaded Config with disk layout.
        old_name: Previous folder name (as it still exists on disks).
        new_name: New folder name (matching the just-renamed staging folder).
        dry_run: If True, log intended actions without performing them.

    Returns:
        List of human-readable strings describing the disks and categories
        that were touched (for inclusion in the StepReport details).
    """
    touched: list[str] = []
    for disk in config.disks:
        if not disk.path.exists():
            continue
        try:
            category_dirs = [p for p in disk.path.iterdir() if p.is_dir()]
        except OSError as exc:
            logger.warning("Cannot scan disk %s for rename propagation: %s", disk.id, exc)
            continue
        for cat_dir in category_dirs:
            src = cat_dir / old_name
            if not src.is_dir():
                continue
            dst = cat_dir / new_name
            if dst.exists():
                logger.warning(
                    "Cannot rename on %s:%s — target '%s' already exists (dispatch will merge)",
                    disk.id,
                    cat_dir.name,
                    new_name,
                )
                touched.append(f"{disk.id}:{cat_dir.name} target exists (skipped)")
                continue
            if dry_run:
                logger.info(
                    "[DRY-RUN] Would rename on %s:%s: %s → %s",
                    disk.id,
                    cat_dir.name,
                    old_name,
                    new_name,
                )
                touched.append(f"{disk.id}:{cat_dir.name} (dry-run)")
                continue
            try:
                src.rename(dst)
                logger.info(
                    "Propagated reclean rename on %s:%s: %s → %s",
                    disk.id,
                    cat_dir.name,
                    old_name,
                    new_name,
                )
                touched.append(f"{disk.id}:{cat_dir.name}")
            except OSError as exc:
                logger.warning(
                    "Failed to propagate rename on %s:%s: %s",
                    disk.id,
                    cat_dir.name,
                    exc,
                )
                touched.append(f"{disk.id}:{cat_dir.name} failed: {exc}")
    return touched


# guessit keys that indicate a folder name is still "polluted"
# with release artifacts (not a clean media title)
_POLLUTION_KEYS = frozenset(
    {
        "screen_size",
        "video_codec",
        "release_group",
        "source",
        "audio_codec",
        "video_profile",
        "streaming_service",
    }
)


def _has_polluted_folders(category_dir: Path) -> bool:
    """Check if any folder in category_dir has a polluted name.

    Quick scan that returns True as soon as the first polluted
    folder is found. Used for fast-skip in the clean phase.

    Args:
        category_dir: Path to {movies_dir}/ or {tvshows_dir}/.

    Returns:
        True if at least one folder has release tokens in its name.
    """
    if not category_dir.exists():
        return False
    for folder in category_dir.iterdir():
        if not folder.is_dir() or folder.name.startswith("."):
            continue
        if is_title_polluted(folder.name):
            return True
    return False


def is_title_polluted(title: str) -> bool:
    """Check if a folder title contains release group tokens.

    Uses guessit to parse the title and detect non-title tokens
    such as screen_size, video_codec, release_group, source, etc.
    Clean titles like "Scream 7" or "2001 A Space Odyssey" only
    contain title/year tokens and are not flagged.

    Args:
        title: Extracted title from folder name.

    Returns:
        True if title contains release tokens.
    """
    import guessit

    parsed = guessit.guessit(title)
    return bool(_POLLUTION_KEYS & set(parsed.keys()))


def _format_clean_name(title: str, year: int | None) -> str:
    """Format a clean folder name as 'Title (Year)' or 'Title'.

    Args:
        title: Cleaned media title.
        year: Detected year, if any.

    Returns:
        Formatted folder name.
    """
    if year:
        return f"{title} ({year})"
    return title


def reclean_folders(
    category_dir: Path,
    dry_run: bool = False,
    config: "Config | None" = None,
) -> StepReport:
    """Re-clean folder names in a category directory.

    Scans all folders in category_dir. For each folder whose name
    is polluted (contains release tokens), re-cleans via NameCleaner
    and renames to "Title (Year)" format.

    If the target name already exists, merges the polluted folder
    into the existing one via _merge_dirs.

    When ``config`` is provided, each successful staging rename is
    propagated to every configured disk so dispatch can still match
    the item by its (new) folder name. Without propagation, a reclean
    turns the next dispatch into a "new" move and fragments the show.

    Args:
        category_dir: Path to {movies_dir}/ or {tvshows_dir}/.
        dry_run: If True, log without renaming.
        config: Loaded Config. When provided, staging renames are
            propagated to the configured disks. When ``None``, only
            the staging folder is renamed (used by unit tests that do
            not need disk propagation).

    Returns:
        StepReport with success (re-cleaned), skip (already clean),
        error (failed) counts.
    """
    from personalscraper.scraper.scraper import _merge_dirs

    report = StepReport(name="reclean")
    if not category_dir.exists():
        return report

    cleaner = NameCleaner()

    for folder in sorted(category_dir.iterdir()):
        if not folder.is_dir() or folder.name.startswith("."):
            continue

        if not is_title_polluted(folder.name):
            report.skip_count += 1
            continue

        # Re-clean via guessit
        title = cleaner.clean(folder.name)
        year = cleaner.extract_year(folder.name)
        clean_name = sanitize_filename(_format_clean_name(title, year))

        if clean_name == folder.name:
            report.skip_count += 1
            continue

        target = category_dir / clean_name

        if dry_run:
            action = "merge into" if target.exists() else "rename"
            logger.info("[DRY-RUN] Would %s: %s → %s", action, folder.name, clean_name)
            report.success_count += 1
            report.details.append(f"[DRY-RUN] {folder.name} → {clean_name}")
            if config is not None and not target.exists():
                touched = _propagate_rename_to_disks(config, folder.name, clean_name, dry_run=True)
                if touched:
                    report.details.append(f"  [DRY-RUN] disk-propagate: {', '.join(touched)}")
            continue

        try:
            if target.exists():
                moved, merge_failed = _merge_dirs(folder, target)
                logger.info("Reclean+merge: %s → %s (%d items)", folder.name, clean_name, moved)
                report.details.append(f"{folder.name} → {clean_name} (merged {moved} items)")
                if merge_failed:
                    report.warnings.append(f"{folder.name}: {merge_failed} item(s) failed during merge")
            else:
                old_name = folder.name
                folder.rename(target)
                logger.info("Reclean: %s → %s", old_name, clean_name)
                report.details.append(f"{old_name} → {clean_name}")
                if config is not None:
                    touched = _propagate_rename_to_disks(config, old_name, clean_name, dry_run=False)
                    if touched:
                        report.details.append(f"  disk-propagate: {', '.join(touched)}")
            report.success_count += 1
        except OSError as exc:
            logger.warning("Reclean failed for %s: %s", folder.name, exc)
            report.error_count += 1
            report.warnings.append(f"{folder.name}: {exc}")
        except Exception as exc:
            logger.error("Unexpected error recleaning %s: %s", folder.name, exc, exc_info=True)
            report.error_count += 1
            report.warnings.append(f"{folder.name}: unexpected error: {exc}")

    return report

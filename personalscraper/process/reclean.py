"""Re-clean folder names in category directories.

Detects folder names still containing release-group tokens
(screen_size, video_codec, release_group, etc.) and re-cleans
them via NameCleaner (guessit). Handles target-exists by merging.
"""

import logging
from pathlib import Path

from personalscraper.models import StepReport
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.text_utils import sanitize_filename

logger = logging.getLogger(__name__)

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
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.

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
) -> StepReport:
    """Re-clean folder names in a category directory.

    Scans all folders in category_dir. For each folder whose name
    is polluted (contains release tokens), re-cleans via NameCleaner
    and renames to "Title (Year)" format.

    If the target name already exists, merges the polluted folder
    into the existing one via _merge_dirs.

    Args:
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.
        dry_run: If True, log without renaming.

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
            continue

        try:
            if target.exists():
                moved, merge_failed = _merge_dirs(folder, target)
                logger.info("Reclean+merge: %s → %s (%d items)", folder.name, clean_name, moved)
                report.details.append(f"{folder.name} → {clean_name} (merged {moved} items)")
                if merge_failed:
                    report.warnings.append(f"{folder.name}: {merge_failed} item(s) failed during merge")
            else:
                folder.rename(target)
                logger.info("Reclean: %s → %s", folder.name, clean_name)
                report.details.append(f"{folder.name} → {clean_name}")
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

"""Sort step entry point — run_sort() function.

Coordinates NameCleaner and Sorter to sort all items from the ingest
directory (097-TEMP/) into categorized subdirectories under the staging
root. Returns a StepReport for the pipeline.
The lock is managed by the CLI caller, not by this module.

staging_dir and ingest_dir come from Config.paths. Functions accept an
explicit ``staging_dir`` parameter; Settings.ingest_dir (a method) is
called with the staging_dir value.
"""

import logging
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.models import StepReport
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.sorter import Sorter

logger = logging.getLogger(__name__)


def run_sort(settings: Settings, staging_dir: Path, dry_run: bool = False) -> StepReport:
    """Sort all items from the ingest directory into type subdirectories.

    Instantiates NameCleaner and Sorter, processes the ingest directory
    (097-TEMP/) and sorts items into category subdirectories (001-MOVIES/,
    002-TVSHOWS/, etc.) under the staging root.

    Fast-skip: returns immediately if 097-TEMP has no items to sort.

    Args:
        settings: Pipeline settings (ingest_dir_name, thresholds).
        staging_dir: Absolute path to the staging area (from Config.paths).
        dry_run: If True, simulate moves without actually moving.

    Returns:
        StepReport with counts and per-item details.
    """
    ingest_dir = settings.ingest_dir(staging_dir)

    # Fast-skip: nothing to sort
    if not _has_unsorted_items(ingest_dir):
        logger.info("Sort fast-skip: 097-TEMP is empty")
        return StepReport(name="sort")

    cleaner = NameCleaner()
    sorter = Sorter(cleaner=cleaner, dry_run=dry_run)

    # Sort processes ingest_dir (097-TEMP/) → categorized dirs at staging root
    results = sorter.process(ingest_dir, dest_root=staging_dir)

    report = StepReport(name="sort")
    for r in results:
        if r.status == "moved":
            report.success_count += 1
            report.details.append(f"{r.source.name} -> {r.destination}")
        elif r.status == "dry-run":
            report.success_count += 1
            report.details.append(f"[DRY-RUN] {r.source.name} -> {r.destination}")
        elif r.status == "skipped":
            report.skip_count += 1
            if r.message:
                report.warnings.append(f"{r.source.name}: {r.message}")
        elif r.status == "error":
            report.error_count += 1
            report.warnings.append(f"ERROR {r.source.name}: {r.message}")

    logger.info(
        "Sort complete: %d moved, %d skipped, %d errors",
        report.success_count,
        report.skip_count,
        report.error_count,
    )
    return report


def _has_unsorted_items(ingest_dir: Path) -> bool:
    """Check if the ingest directory contains non-hidden items to sort.

    Used for fast-skip: if nothing to sort, skip the entire phase.

    Args:
        ingest_dir: Resolved path to the ingest directory (097-TEMP/).

    Returns:
        True if there are items to sort.
    """
    if not ingest_dir.exists():
        return False
    return any(not item.name.startswith(".") for item in ingest_dir.iterdir())


def assert_temp_empty(settings: Settings, staging_dir: Path) -> list[str]:
    """Check that the ingest directory is empty after sort.

    Ignores hidden files (.gitkeep, .DS_Store, etc.) since these
    are not unsorted media.

    Args:
        settings: Pipeline settings (provides ingest_dir_name).
        staging_dir: Absolute path to the staging area (from Config.paths).

    Returns:
        List of remaining file/dir names. Empty list means gate passes.
    """
    ingest_dir = settings.ingest_dir(staging_dir)
    if not ingest_dir.exists():
        return []
    remaining = [item.name for item in ingest_dir.iterdir() if not item.name.startswith(".")]
    if remaining:
        logger.warning(
            "097-TEMP not empty after sort: %d items remain",
            len(remaining),
        )
    return remaining

"""Sort step entry point — run_sort() function.

Coordinates NameCleaner and Sorter to sort all items from the ingest
directory (097-TEMP/) into categorized subdirectories under the staging
root. Returns a StepReport for the pipeline.
The lock is managed by the CLI caller, not by this module.
"""

import logging

from personalscraper.config import Settings
from personalscraper.models import StepReport
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.sorter import Sorter

logger = logging.getLogger(__name__)


def run_sort(settings: Settings, dry_run: bool = False) -> StepReport:
    """Sort all items from the ingest directory into type subdirectories.

    Instantiates NameCleaner and Sorter, processes the ingest directory
    (097-TEMP/) and sorts items into category subdirectories (001-MOVIES/,
    002-TVSHOWS/, etc.) under the staging root.

    Args:
        settings: Pipeline configuration (ingest_dir and staging_dir).
        dry_run: If True, simulate moves without actually moving.

    Returns:
        StepReport with counts and per-item details.
    """
    cleaner = NameCleaner()
    sorter = Sorter(cleaner=cleaner, dry_run=dry_run)

    # Sort processes ingest_dir (097-TEMP/) → categorized dirs at staging root
    results = sorter.process(settings.ingest_dir, dest_root=settings.staging_dir)

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

"""Sort step entry point — run_sort() function.

Coordinates NameCleaner and Sorter to sort all items at the staging root
into categorized subdirectories. Returns a StepReport for the pipeline.
The lock is managed by the CLI caller, not by this module.
"""

import logging

from personalscraper.config import Settings
from personalscraper.models import StepReport
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.sorter import Sorter

logger = logging.getLogger(__name__)


def run_sort(settings: Settings, dry_run: bool = False) -> StepReport:
    """Sort all items at the staging root into type subdirectories.

    Instantiates NameCleaner and Sorter, processes the staging directory,
    and converts the list of SortResult into a StepReport.

    Args:
        settings: Pipeline settings (staging_dir path).
        dry_run: If True, simulate moves without actually moving.

    Returns:
        StepReport with counts and per-item details.
    """
    cleaner = NameCleaner()
    sorter = Sorter(cleaner=cleaner, dry_run=dry_run)

    results = sorter.process(settings.staging_dir)

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

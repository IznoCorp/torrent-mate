"""Process phase entry point — run_process() and sub-step functions.

Coordinates reclean, dedup, scrape, and cleanup across all category
directories. Returns 3 StepReports for the pipeline:
clean (reclean+dedup), scrape, cleanup.

Each sub-step can be called independently for error isolation.
"""

import logging

from personalscraper.config import Settings
from personalscraper.models import StepReport

logger = logging.getLogger(__name__)


def run_clean(settings: Settings, dry_run: bool = False) -> StepReport:
    """Run reclean + dedup on all category directories.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without modifying files.

    Returns:
        StepReport with combined reclean + dedup counts.
    """
    from personalscraper.process.dedup import dedup_folders
    from personalscraper.process.reclean import reclean_folders

    movies_dir = settings.staging_dir / settings.movies_dir_name
    tvshows_dir = settings.staging_dir / settings.tvshows_dir_name

    clean_report = StepReport(name="clean")

    for category_dir in (movies_dir, tvshows_dir):
        reclean_report = reclean_folders(category_dir, dry_run=dry_run)
        clean_report.success_count += reclean_report.success_count
        clean_report.skip_count += reclean_report.skip_count
        clean_report.error_count += reclean_report.error_count
        clean_report.details.extend(reclean_report.details)
        clean_report.warnings.extend(reclean_report.warnings)

        dedup_merged, dedup_failed = dedup_folders(category_dir, dry_run=dry_run)
        if dedup_merged:
            clean_report.success_count += dedup_merged
            clean_report.details.append(
                f"Dedup: {dedup_merged} duplicates merged in {category_dir.name}"
            )
        if dedup_failed:
            clean_report.error_count += dedup_failed
            clean_report.warnings.append(
                f"Dedup: {dedup_failed} merge(s) failed in {category_dir.name}"
            )

    logger.info(
        "Clean phase: %d re-cleaned/deduped, %d skipped, %d errors",
        clean_report.success_count,
        clean_report.skip_count,
        clean_report.error_count,
    )
    return clean_report


def run_cleanup(settings: Settings, dry_run: bool = False) -> StepReport:
    """Run empty directory cleanup on all category directories.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without deleting.

    Returns:
        StepReport with cleanup counts.
    """
    from personalscraper.process.cleanup import cleanup_empty_dirs

    movies_dir = settings.staging_dir / settings.movies_dir_name
    tvshows_dir = settings.staging_dir / settings.tvshows_dir_name

    cleanup_report = StepReport(name="cleanup")

    for category_dir in (movies_dir, tvshows_dir):
        cat_report = cleanup_empty_dirs(category_dir, dry_run=dry_run)
        cleanup_report.success_count += cat_report.success_count
        cleanup_report.details.extend(cat_report.details)

    logger.info("Cleanup phase: %d empty dirs removed", cleanup_report.success_count)
    return cleanup_report


def run_process(
    settings: Settings,
    dry_run: bool = False,
    interactive: bool = False,
) -> tuple[StepReport, StepReport, StepReport]:
    """Run Phase 3: reclean + dedup + scrape + cleanup.

    Each sub-step is isolated so that a crash in one does not prevent
    the others from running (same isolation as Pipeline._run_step).

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without modifying files.
        interactive: If True, prompt for ambiguous scrape matches.

    Returns:
        Tuple of (clean_report, scrape_report, cleanup_report).
    """
    from personalscraper.scraper.run import run_scrape

    # Error isolation: each sub-step runs independently
    try:
        clean_report = run_clean(settings, dry_run=dry_run)
    except Exception as exc:
        logger.exception("Clean sub-step failed fatally")
        clean_report = StepReport(
            name="clean", error_count=1,
            details=[f"Fatal: {type(exc).__name__}: {exc}"],
        )

    try:
        scrape_report = run_scrape(settings, dry_run=dry_run, interactive=interactive)
    except Exception as exc:
        logger.exception("Scrape sub-step failed fatally")
        scrape_report = StepReport(
            name="scrape", error_count=1,
            details=[f"Fatal: {type(exc).__name__}: {exc}"],
        )

    try:
        cleanup_report = run_cleanup(settings, dry_run=dry_run)
    except Exception as exc:
        logger.exception("Cleanup sub-step failed fatally")
        cleanup_report = StepReport(
            name="cleanup", error_count=1,
            details=[f"Fatal: {type(exc).__name__}: {exc}"],
        )

    return clean_report, scrape_report, cleanup_report

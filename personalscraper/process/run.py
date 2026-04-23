"""Process phase entry point — run_process() and sub-step functions.

Coordinates reclean, dedup, scrape, and cleanup across all category
directories. Returns 3 StepReports for the pipeline:
clean (reclean+dedup), scrape, cleanup.

Each sub-step can be called independently for error isolation.
"""

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.sorter.file_type import FileType

log = get_logger("process.run")


def run_clean(settings: Settings, config: Config, dry_run: bool = False) -> StepReport:
    """Run reclean + dedup on all category directories.

    Skips reclean when no polluted folder names are found.
    Dedup always runs (lightweight fuzzy comparison).

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without modifying files.
        config: Loaded Config for staging dir name resolution.
            Derives movie/tvshow dir names from staging_dirs.

    Returns:
        StepReport with combined reclean + dedup counts.
    """
    from personalscraper.process.dedup import dedup_folders
    from personalscraper.process.reclean import _has_polluted_folders, reclean_folders

    staging = config.paths.staging_dir
    movies_dir = staging / folder_name(find_by_file_type(config, FileType.MOVIE))
    tvshows_dir = staging / folder_name(find_by_file_type(config, FileType.TVSHOW))

    has_polluted = _has_polluted_folders(movies_dir) or _has_polluted_folders(tvshows_dir)

    clean_report = StepReport(name="clean")

    for category_dir in (movies_dir, tvshows_dir):
        # Only run reclean if polluted folders exist
        if has_polluted:
            reclean_report = reclean_folders(category_dir, dry_run=dry_run, config=config)
            clean_report.success_count += reclean_report.success_count
            clean_report.skip_count += reclean_report.skip_count
            clean_report.error_count += reclean_report.error_count
            clean_report.details.extend(reclean_report.details)
            clean_report.warnings.extend(reclean_report.warnings)

        # Always run dedup (lightweight fuzzy comparison)
        dedup_merged, dedup_failed = dedup_folders(category_dir, dry_run=dry_run, fuzzy_config=config.fuzzy_match)
        if dedup_merged:
            clean_report.success_count += dedup_merged
            clean_report.details.append(f"Dedup: {dedup_merged} duplicates merged in {category_dir.name}")
        if dedup_failed:
            clean_report.error_count += dedup_failed
            clean_report.warnings.append(f"Dedup: {dedup_failed} merge(s) failed in {category_dir.name}")

    log.info(
        "process_clean_complete",
        recleaned=clean_report.success_count,
        skipped=clean_report.skip_count,
        errors=clean_report.error_count,
    )
    return clean_report


def run_cleanup(settings: Settings, config: Config, dry_run: bool = False) -> StepReport:
    """Run empty directory cleanup on all category directories.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without deleting.
        config: Loaded Config for staging dir name resolution.
            Derives movie/tvshow dir names from staging_dirs.

    Returns:
        StepReport with cleanup counts.
    """
    from personalscraper.process.cleanup import cleanup_empty_dirs

    staging = config.paths.staging_dir
    movies_dir = staging / folder_name(find_by_file_type(config, FileType.MOVIE))
    tvshows_dir = staging / folder_name(find_by_file_type(config, FileType.TVSHOW))

    cleanup_report = StepReport(name="cleanup")

    for category_dir in (movies_dir, tvshows_dir):
        cat_report = cleanup_empty_dirs(category_dir, dry_run=dry_run)
        cleanup_report.success_count += cat_report.success_count
        cleanup_report.details.extend(cat_report.details)

    log.info("process_cleanup_complete", removed=cleanup_report.success_count)
    return cleanup_report


def run_process(
    settings: Settings,
    config: Config,
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
        config: Loaded Config passed through to run_clean and run_cleanup
            for staging dir name resolution.

    Returns:
        Tuple of (clean_report, scrape_report, cleanup_report).
    """
    from personalscraper.scraper.run import run_scrape

    # Error isolation: each sub-step runs independently
    try:
        clean_report = run_clean(settings, dry_run=dry_run, config=config)
    except Exception as exc:
        log.exception("process_clean_fatal", exc_info=exc)
        clean_report = StepReport(
            name="clean",
            error_count=1,
            details=[f"Fatal: {type(exc).__name__}: {exc}"],
        )

    try:
        scrape_report = run_scrape(settings, config=config, dry_run=dry_run, interactive=interactive)
    except Exception as exc:
        log.exception("process_scrape_fatal", exc_info=exc)
        scrape_report = StepReport(
            name="scrape",
            error_count=1,
            details=[f"Fatal: {type(exc).__name__}: {exc}"],
        )

    try:
        cleanup_report = run_cleanup(settings, dry_run=dry_run, config=config)
    except Exception as exc:
        log.exception("process_cleanup_fatal", exc_info=exc)
        cleanup_report = StepReport(
            name="cleanup",
            error_count=1,
            details=[f"Fatal: {type(exc).__name__}: {exc}"],
        )

    return clean_report, scrape_report, cleanup_report

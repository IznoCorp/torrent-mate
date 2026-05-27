"""Process phase entry point — run_process() and sub-step functions.

Coordinates reclean, dedup, scrape, and cleanup across all category
directories. Returns 3 StepReports for the pipeline:
clean (reclean+dedup), scrape, cleanup.

Each sub-step can be called independently for error isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.sorter.file_type import FileType

if TYPE_CHECKING:
    from personalscraper.api.metadata.registry import ProviderRegistry

log = get_logger("process.run")


def _revert_unmatched_recleans(
    category_dirs: list[Path],
    unmatched_names: set[str],
    rename_map: dict[str, str],
    dry_run: bool = False,
) -> int:
    """Revert reclean renames whose scrape produced no confident match.

    When reclean renames a polluted folder (e.g.
    ``Les.secrets.du.Prince.Andrew.2023.S01.…`` → ``Les secrets du Prince
    Andrew S01 (2023)``) but the scraper subsequently fails to match the
    resulting clean name, the folder is left in a half-processed state:
    canonical outer name, raw torrent subdir still nested inside, no NFO
    or artwork.  This function reverts such folders to their original
    torrent name so a manual ``rescrape`` or future pipeline run can
    re-attempt the match from the original filename.

    Only folders that are both in ``rename_map`` (were renamed by reclean)
    AND appear in ``unmatched_names`` (scraper returned ``skipped_low_confidence``)
    are reverted.  Folders that were successfully scraped or skipped for other
    reasons are left untouched.

    Args:
        category_dirs: List of category root paths (movies, tvshows staging
            directories).  Used to resolve the absolute path of each renamed
            folder.
        unmatched_names: Set of folder names for which the scraper returned
            ``skipped_low_confidence``.  Derived from the scrape StepReport
            details by the caller.
        rename_map: Mapping of ``new_name → old_name`` populated by
            ``reclean_folders``.  Keys are the clean names that replaced the
            original torrent folder names.
        dry_run: If True, log intended reversions without performing them.

    Returns:
        Number of folders reverted (or that would be reverted in dry-run).
    """
    if not rename_map:
        return 0

    if not unmatched_names:
        return 0

    # Build a lookup from category dir path → path object for all category dirs.
    reverted = 0
    for category_dir in category_dirs:
        if not category_dir.exists():
            continue
        for new_name, old_name in rename_map.items():
            if new_name not in unmatched_names:
                continue
            current = category_dir / new_name
            if not current.exists():
                # Already renamed by scraper (e.g. folder was moved) — skip.
                continue
            original = category_dir / old_name
            if dry_run:
                log.warning(
                    "process.clean.skipped_unmatched",
                    folder=new_name,
                    reverted_to=old_name,
                    dry_run=True,
                )
                reverted += 1
                continue
            try:
                if original.exists():
                    # Edge case: original name reappeared (parallel run?) — skip.
                    log.warning(
                        "process.clean.revert_target_exists",
                        folder=new_name,
                        original=old_name,
                    )
                    continue
                current.rename(original)
                log.warning(
                    "process.clean.skipped_unmatched",
                    folder=new_name,
                    reverted_to=old_name,
                )
                reverted += 1
            except OSError as exc:
                log.warning(
                    "process.clean.revert_failed",
                    folder=new_name,
                    original=old_name,
                    error=str(exc),
                )
    return reverted


def run_clean(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
    *,
    event_bus: EventBus,
) -> StepReport:
    """Run reclean + dedup on all category directories.

    Skips reclean when no polluted folder names are found.
    Dedup always runs (lightweight fuzzy comparison).

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without modifying files.
        config: Loaded Config for staging dir name resolution.
            Derives movie/tvshow dir names from staging_dirs.
        event_bus: Required in-process EventBus. Each per-item
        lifecycle transition emits an ``ItemProgressed`` event on the bus.

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
        event_bus.emit(ItemProgressed(step="clean", item=str(category_dir.name), status="started"))
        # Only run reclean if polluted folders exist
        if has_polluted:
            reclean_report = reclean_folders(category_dir, dry_run=dry_run, config=config)
            clean_report.success_count += reclean_report.success_count
            clean_report.skip_count += reclean_report.skip_count
            clean_report.error_count += reclean_report.error_count
            clean_report.details.extend(reclean_report.details)
            clean_report.warnings.extend(reclean_report.warnings)
            # Accumulate rename maps so run_process can revert unmatched recleans.
            clean_report.renames.update(reclean_report.renames)

        # Always run dedup (lightweight fuzzy comparison)
        dedup_merged, dedup_failed = dedup_folders(category_dir, dry_run=dry_run, fuzzy_config=config.fuzzy_match)
        if dedup_merged:
            clean_report.success_count += dedup_merged
            clean_report.details.append(f"Dedup: {dedup_merged} duplicates merged in {category_dir.name}")
        if dedup_failed:
            clean_report.error_count += dedup_failed
            clean_report.warnings.append(f"Dedup: {dedup_failed} merge(s) failed in {category_dir.name}")

        if clean_report.error_count > 0:
            cat_status = "error"
        elif clean_report.success_count > 0:
            cat_status = "cleaned"
        else:
            cat_status = "skipped"
        event_bus.emit(ItemProgressed(step="clean", item=str(category_dir.name), status=cat_status))

    log.info(
        "process_clean_complete",
        recleaned=clean_report.success_count,
        skipped=clean_report.skip_count,
        errors=clean_report.error_count,
    )
    return clean_report


def run_cleanup(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
    *,
    event_bus: EventBus,
) -> StepReport:
    """Run empty directory cleanup on all category directories.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without deleting.
        config: Loaded Config for staging dir name resolution.
            Derives movie/tvshow dir names from staging_dirs.
        event_bus: Required in-process EventBus. Each per-item
        lifecycle transition emits an ``ItemProgressed`` event on the bus.

    Returns:
        StepReport with cleanup counts.
    """
    from personalscraper.process.cleanup import cleanup_empty_dirs

    staging = config.paths.staging_dir
    movies_dir = staging / folder_name(find_by_file_type(config, FileType.MOVIE))
    tvshows_dir = staging / folder_name(find_by_file_type(config, FileType.TVSHOW))

    cleanup_report = StepReport(name="cleanup")

    for category_dir in (movies_dir, tvshows_dir):
        event_bus.emit(ItemProgressed(step="cleanup", item=str(category_dir.name), status="started"))
        cat_report = cleanup_empty_dirs(category_dir, dry_run=dry_run)
        cleanup_report.success_count += cat_report.success_count
        cleanup_report.details.extend(cat_report.details)
        # Emit "skipped" when no empty dirs were found in this category, "removed" otherwise.
        # Aligns with plan phase-07 §7.1 (DESIGN.md §9: removed / skipped).
        terminal_status = "removed" if cat_report.success_count > 0 else "skipped"
        event_bus.emit(
            ItemProgressed(
                step="cleanup",
                item=str(category_dir.name),
                status=terminal_status,
                details={"removed": cat_report.success_count},
            )
        )

    log.info("process_cleanup_complete", removed=cleanup_report.success_count)
    return cleanup_report


def run_process(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
    interactive: bool = False,
    *,
    event_bus: EventBus,
    registry: "ProviderRegistry",
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
        event_bus: Required in-process EventBus. Each per-item
            lifecycle transition emits an ``ItemProgressed`` event on the bus.
        registry: Required :class:`ProviderRegistry` from the pipeline boot
            sequence. Owns provider instantiation for the scrape sub-step
            (DESIGN §6.1).

    Returns:
        Tuple of (clean_report, scrape_report, cleanup_report).
    """
    from personalscraper.scraper.run import run_scrape

    # Error isolation: each sub-step runs independently
    try:
        clean_report = run_clean(settings, dry_run=dry_run, config=config, event_bus=event_bus)
    except Exception as exc:
        log.exception("process_clean_fatal", error=str(exc))
        clean_report = StepReport(
            name="clean",
            error_count=1,
            details=[f"Fatal: {type(exc).__name__}: {exc}"],
        )

    try:
        scrape_report = run_scrape(
            settings,
            config=config,
            dry_run=dry_run,
            interactive=interactive,
            event_bus=event_bus,
            registry=registry,
        )
    except Exception as exc:
        log.exception("process_scrape_fatal", error=str(exc))
        scrape_report = StepReport(
            name="scrape",
            error_count=1,
            details=[f"Fatal: {type(exc).__name__}: {exc}"],
        )

    # Revert reclean renames for folders the scraper could not match so that
    # they keep their original torrent name and remain rescrape-eligible.
    if clean_report.renames:
        staging = config.paths.staging_dir
        movies_dir = staging / folder_name(find_by_file_type(config, FileType.MOVIE))
        tvshows_dir = staging / folder_name(find_by_file_type(config, FileType.TVSHOW))
        # Read the typed unmatched_paths field directly (no detail-string parsing).
        unmatched_names: set[str] = set(scrape_report.unmatched_paths)
        _revert_unmatched_recleans(
            category_dirs=[movies_dir, tvshows_dir],
            unmatched_names=unmatched_names,
            rename_map=clean_report.renames,
            dry_run=dry_run,
        )

    try:
        cleanup_report = run_cleanup(settings, dry_run=dry_run, config=config, event_bus=event_bus)
    except Exception as exc:
        log.exception("process_cleanup_fatal", error=str(exc))
        cleanup_report = StepReport(
            name="cleanup",
            error_count=1,
            details=[f"Fatal: {type(exc).__name__}: {exc}"],
        )

    return clean_report, scrape_report, cleanup_report

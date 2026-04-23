"""Sort step entry point — run_sort() function.

Coordinates NameCleaner and Sorter to sort all items from the ingest
directory ({ingest_dir}/) into categorized subdirectories under the staging
root. Returns a StepReport for the pipeline.
The lock is managed by the CLI caller, not by this module.

staging_dir and ingest_dir come from Config.paths. Functions accept an
explicit ``staging_dir`` parameter; when config is provided, ingest_dir is
resolved via staging_path(config, find_ingest_dir(config)).
"""

from pathlib import Path

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_ingest_dir, staging_path
from personalscraper.config import Settings
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.sorter.cleaner import NameCleaner
from personalscraper.sorter.sorter import Sorter

log = get_logger("sorter.run")


def run_sort(settings: Settings, staging_dir: Path, config: Config, dry_run: bool = False) -> StepReport:
    """Sort all items from the ingest directory into type subdirectories.

    Instantiates NameCleaner and Sorter, processes the ingest directory
    (e.g. {ingest_dir}/) and sorts items into category subdirectories
    ({movies_dir}/, {tvshows_dir}/, etc.) under the staging root.

    Fast-skip: returns immediately if the ingest dir has no items to sort.

    Args:
        settings: Pipeline settings (retained for API compatibility; thresholds).
        staging_dir: Absolute path to the staging area (from Config.paths).
        config: Loaded Config instance (required) for staging_dirs and path resolution.
        dry_run: If True, simulate moves without actually moving.

    Returns:
        StepReport with counts and per-item details.
    """
    ingest_dir = staging_path(config, find_ingest_dir(config))

    # Fast-skip: nothing to sort
    if not _has_unsorted_items(ingest_dir):
        log.info("sort_fast_skip", ingest_dir=str(ingest_dir))
        return StepReport(name="sort")

    cleaner = NameCleaner()
    sorter = Sorter(config=config, cleaner=cleaner, dry_run=dry_run)

    # Sort processes ingest_dir ({ingest_dir}/) → categorized dirs at staging root
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

    log.info(
        "sort_complete",
        moved=report.success_count,
        skipped=report.skip_count,
        errors=report.error_count,
    )
    return report


def _has_unsorted_items(ingest_dir: Path) -> bool:
    """Check if the ingest directory contains non-hidden items to sort.

    Used for fast-skip: if nothing to sort, skip the entire phase.

    Args:
        ingest_dir: Resolved path to the ingest directory ({ingest_dir}/).

    Returns:
        True if there are items to sort.
    """
    if not ingest_dir.exists():
        return False
    return any(not item.name.startswith(".") for item in ingest_dir.iterdir())


def assert_temp_empty(settings: Settings, staging_dir: Path, config: Config) -> list[str]:
    """Check that the ingest directory is empty after sort.

    Ignores hidden files (.gitkeep, .DS_Store, etc.) since these
    are not unsorted media.

    Args:
        settings: Pipeline settings (retained for API compatibility; no longer used for path resolution).
        staging_dir: Absolute path to the staging area (from Config.paths).
        config: Loaded Config instance (required) for ingest_dir resolution.

    Returns:
        List of remaining file/dir names. Empty list means gate passes.
    """
    ingest_dir = staging_path(config, find_ingest_dir(config))
    if not ingest_dir.exists():
        return []
    remaining = [item.name for item in ingest_dir.iterdir() if not item.name.startswith(".")]
    if remaining:
        log.warning(
            "sort_ingest_not_empty",
            remaining_count=len(remaining),
        )
    return remaining

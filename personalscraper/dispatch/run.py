"""Dispatch step runner: entry point for the dispatch pipeline step.

Instantiates the Dispatcher and MediaIndex, processes verified items,
and converts DispatchResult to StepReport. In standalone mode (no
verified list provided), runs verify first to obtain dispatchable items.

staging_dir is passed explicitly from Config.paths; Settings no longer
carries disk paths.
"""

import shutil
from pathlib import Path

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.dispatch.dispatcher import Dispatcher, DispatchResult
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.sorter.file_type import FileType
from personalscraper.verify.verifier import VerifyResult

log = get_logger("dispatch_run")


def _cleanup_staging_orphans(settings: Settings, config: Config, staging_dir: Path) -> int:
    """Remove orphaned dispatch temp dirs from staging categories.

    Cleans up _tmp_dispatch_* directories and .merge_backup/
    subdirectories that were left behind by interrupted dispatches.

    Args:
        settings: Pipeline configuration (provides dir name attributes).
        config: Application config for category-based dir name resolution.
        staging_dir: Absolute path to the staging area (from Config.paths).

    Returns:
        Number of orphan directories removed.
    """
    cleaned = 0
    staging = staging_dir
    for dir_name in (
        folder_name(find_by_file_type(config, FileType.MOVIE)),
        folder_name(find_by_file_type(config, FileType.TVSHOW)),
    ):
        cat_dir = staging / dir_name
        if not cat_dir.exists():
            continue
        for item in cat_dir.iterdir():
            if not item.is_dir():
                continue
            # Clean _tmp_dispatch_* orphans
            if item.name.startswith("_tmp_dispatch_"):
                try:
                    shutil.rmtree(item)
                    log.warning("staging_orphan_cleaned", name=item.name)
                    cleaned += 1
                except OSError as exc:
                    log.warning("staging_orphan_cleanup_failed", name=item.name, error=str(exc))
            # Clean .merge_backup/ inside media dirs
            backup = item / ".merge_backup"
            if backup.exists() and backup.is_dir():
                try:
                    shutil.rmtree(backup)
                    log.warning("staging_backup_cleaned", media=item.name, backup=backup.name)
                    cleaned += 1
                except OSError as exc:
                    log.warning("staging_backup_cleanup_failed", path=str(backup), error=str(exc))
    return cleaned


def run_dispatch(
    settings: Settings,
    config: "Config",
    dry_run: bool = False,
    verified: list[VerifyResult] | None = None,
) -> StepReport:
    """Run the dispatch pipeline step.

    Args:
        settings: Pipeline configuration (thresholds, API keys).
        config: Config with disk layout and paths.
        dry_run: If True, preview without transferring files.
        verified: Verified items from the verify step (pipeline mode).
            If None, runs verify first to obtain dispatchable items.

    Returns:
        StepReport with dispatch counts and details.
    """
    staging_dir = config.paths.staging_dir
    index_path = config.paths.data_dir / "media_index.json"

    # Clean orphaned temp dirs from staging area
    cleaned = 0
    if not dry_run:
        cleaned = _cleanup_staging_orphans(settings, config, staging_dir)

    index = MediaIndex(index_path)
    index.load()

    # Log index freshness at entry so dry-run reviews know whether the plan
    # is computed against a fresh or cached index.
    index_source = "cache" if index.count > 0 else "empty"
    log.info("dispatch_index_state", entries=index.count, source=index_source, path=str(index_path))

    # Rebuild index if empty (first run or corrupted) to detect existing media
    # on all 4 disks. Without this, all items are treated as "new" and sent
    # to the disk with most free space, ignoring existing series/movies.
    # The rebuild is persisted even on dry-run because the index is a cache
    # of disk reality, not pipeline output — skipping persistence would make
    # every dry-run redo the scan (observed waste: ~2044 entries per call).
    if index.count == 0:
        from personalscraper.dispatch.disk_scanner import get_disk_configs

        disk_configs = get_disk_configs(config)
        count = index.rebuild(disk_configs, categories=config.categories)
        log.info("index_rebuilt_on_empty", entries=count)
        index.save()

    dispatcher = Dispatcher(config=config, settings=settings, index=index, dry_run=dry_run)

    if verified is None:
        # Standalone mode: run verify first to get dispatchable items
        from personalscraper.verify.run import run_verify

        _, verified = run_verify(settings, config, dry_run=dry_run)

    results = dispatcher.process(verified=verified)

    # Save updated index
    if not dry_run:
        index.save()

    report = _to_step_report(results)
    if cleaned:
        report.details.insert(0, f"Cleaned {cleaned} staging orphan(s)")
    return report


def _to_step_report(results: list[DispatchResult]) -> StepReport:
    """Convert DispatchResult list to StepReport.

    Args:
        results: List of dispatch results.

    Returns:
        StepReport with aggregated counts.
    """
    success = 0
    skipped = 0
    errors = 0
    warnings: list[str] = []
    details: list[str] = []

    # Action tags use a leading "action=" prefix (not "[action]") because
    # Rich console.print() would silently swallow bracketed tokens as markup.
    for r in results:
        name = r.source.name
        if r.action in ("replaced", "merged", "moved"):
            success += 1
            details.append(f"action={r.action:<8} {name} → {r.disk}")
        elif r.action == "skipped":
            skipped += 1
            details.append(f"action=skipped  {name}: {r.reason}")
            if r.reason:
                warnings.append(f"{name}: {r.reason}")
        elif r.action == "error":
            errors += 1
            details.append(f"action=error    {name}: {r.reason}")
            warnings.append(f"{name}: {r.reason or 'unknown error'}")

    return StepReport(
        name="dispatch",
        success_count=success,
        skip_count=skipped,
        error_count=errors,
        warnings=warnings,
        details=details,
    )

"""Dispatch step runner: entry point for the dispatch pipeline step.

Instantiates the Dispatcher and MediaIndex, processes verified items,
and converts DispatchResult to StepReport. In standalone mode (no
verified list provided), runs verify first to obtain dispatchable items.
"""

import logging
import shutil

from personalscraper.config import Settings
from personalscraper.dispatch.dispatcher import Dispatcher, DispatchResult
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.models import StepReport
from personalscraper.verify.verifier import VerifyResult

logger = logging.getLogger(__name__)


def _cleanup_staging_orphans(settings: Settings) -> int:
    """Remove orphaned dispatch temp dirs from staging categories.

    Cleans up _tmp_dispatch_* directories and .merge_backup/
    subdirectories that were left behind by interrupted dispatches.

    Args:
        settings: Pipeline configuration.

    Returns:
        Number of orphan directories removed.
    """
    cleaned = 0
    staging = settings.staging_dir
    for dir_name in (settings.movies_dir_name, settings.tvshows_dir_name):
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
                    logger.warning("Cleaned staging orphan: %s", item.name)
                    cleaned += 1
                except OSError as exc:
                    logger.warning("Failed to clean orphan %s: %s", item.name, exc)
            # Clean .merge_backup/ inside media dirs
            backup = item / ".merge_backup"
            if backup.exists() and backup.is_dir():
                try:
                    shutil.rmtree(backup)
                    logger.warning("Cleaned merge backup: %s/%s", item.name, backup.name)
                    cleaned += 1
                except OSError as exc:
                    logger.warning("Failed to clean backup %s: %s", backup, exc)
    return cleaned


def run_dispatch(
    settings: Settings,
    dry_run: bool = False,
    verified: list[VerifyResult] | None = None,
) -> StepReport:
    """Run the dispatch pipeline step.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without transferring files.
        verified: Verified items from V4 (pipeline mode).
            If None, runs verify first to obtain dispatchable items.

    Returns:
        StepReport with dispatch counts and details.
    """
    # Clean orphaned temp dirs from staging area
    cleaned = 0
    if not dry_run:
        cleaned = _cleanup_staging_orphans(settings)

    index = MediaIndex()
    index.load()

    dispatcher = Dispatcher(settings=settings, index=index, dry_run=dry_run)

    if verified is None:
        # Standalone mode: run verify first to get dispatchable items
        from personalscraper.verify.run import run_verify

        _, verified = run_verify(settings, dry_run=dry_run)
        verified = [vr for vr in verified if vr.category]

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

    for r in results:
        name = r.source.name
        if r.action in ("replaced", "merged", "moved"):
            success += 1
            details.append(f"[{r.action}] {name} → {r.disk}")
        elif r.action == "skipped":
            skipped += 1
            details.append(f"[skipped] {name}: {r.reason}")
            if r.reason:
                warnings.append(f"{name}: {r.reason}")
        elif r.action == "error":
            errors += 1
            details.append(f"[error] {name}: {r.reason}")
            warnings.append(f"{name}: {r.reason or 'unknown error'}")

    return StepReport(
        name="dispatch",
        success_count=success,
        skip_count=skipped,
        error_count=errors,
        warnings=warnings,
        details=details,
    )

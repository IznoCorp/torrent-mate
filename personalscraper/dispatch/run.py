"""Dispatch step runner: entry point for the dispatch pipeline step.

Instantiates the Dispatcher and MediaIndex, processes verified items
or scans the staging directory, and converts DispatchResult to StepReport.
"""

import logging
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.dispatch.dispatcher import Dispatcher, DispatchResult
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.models import StepReport
from personalscraper.verify.verifier import VerifyResult

logger = logging.getLogger(__name__)


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
            If None, runs in standalone mode scanning staging dir.

    Returns:
        StepReport with dispatch counts and details.
    """
    index = MediaIndex()
    index.load()

    dispatcher = Dispatcher(settings=settings, index=index, dry_run=dry_run)

    if verified is not None:
        results = dispatcher.process(verified=verified)
    else:
        results = dispatcher.process(staging_dir=Path(settings.staging_dir))

    # Save updated index
    if not dry_run:
        index.save()

    return _to_step_report(results)


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

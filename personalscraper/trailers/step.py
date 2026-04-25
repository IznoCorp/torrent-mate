"""Pipeline step: trailer discovery and download for staged media.

Runs after the ``verify`` step and before ``dispatch``. Non-blocking:
failures produce ``status='partial'`` and dispatch proceeds. Uses structlog
(the project-wide logger) — not the stdlib ``logging``.

Public entry point:
``run_trailers(config, staging_dir, verified, skip_trailers=False) -> StepReport``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from personalscraper.logger import get_logger
from personalscraper.models import StepReport

logger = get_logger(__name__)


def run_trailers(
    config: Any,
    staging_dir: Path,
    verified: list[Any],
    skip_trailers: bool = False,
) -> StepReport:
    """Run the trailers pipeline step for all staged media items.

    Scans ``staging_dir`` for media without trailers, discovers YouTube URLs
    via TMDB/YouTube, downloads via yt-dlp, and places files next to media.
    Non-blocking: failures log a warning and dispatch continues.

    Args:
        config: Loaded pipeline Config.
        staging_dir: Path to the staging area (where sorted media lives).
        verified: List of items that passed the previous ``verify`` step. Items
            absent from this list are skipped (they failed verify already).
        skip_trailers: If True, return a skipped StepReport immediately.

    Returns:
        StepReport with name="trailers", status in
        {success, partial, skipped, error}, and counts dict.
    """
    # Skipped gate -- honour the explicit flag and the config toggle
    if skip_trailers or not config.trailers.enabled:
        logger.info(
            "trailers_step_skipped",
            enabled=config.trailers.enabled,
            skip_flag=skip_trailers,
        )
        return StepReport(name="trailers", status="skipped")

    # Deferred imports: avoids circular dependencies between this step entry-point
    # and the orchestrator / state modules (which import from this module's siblings).
    from personalscraper.trailers.orchestrator import TrailersOrchestrator  # noqa: PLC0415
    from personalscraper.trailers.state import TrailerStateLocked  # noqa: PLC0415

    try:
        orchestrator = TrailersOrchestrator(config=config, staging_dir=staging_dir)
        counts = orchestrator.run()
        failed_items = orchestrator.failed_items

        success_count = counts.get("downloaded", 0)
        skip_count = counts.get("already_present", 0) + counts.get("skipped_by_state", 0)
        error_count = counts.get("error", 0) + counts.get("bot_detected", 0)

        # Partial: some items succeeded but at least one failed or was bot-detected.
        # Success: all items processed cleanly (errors=0 and no failed_items list).
        if error_count > 0 or failed_items:
            step_status = "partial"
        else:
            step_status = "success"

        report = StepReport(
            name="trailers",
            success_count=success_count,
            skip_count=skip_count,
            error_count=error_count,
            status=step_status,
            counts=counts,
            failed_items=failed_items,
        )
        logger.info(
            "trailers_step_complete",
            step_status=step_status,
            downloaded=success_count,
            skipped=skip_count,
            errors=error_count,
        )
        return report

    except TrailerStateLocked as exc:
        # Another process is holding the state-file lock — surfaced as a clean
        # error rather than a deadlock.  The pipeline logs and continues to
        # dispatch (non-blocking by default).
        logger.error(
            "trailers_state_locked",
            lock_path=str(exc.lock_path),
            holder_pid=exc.holder_pid,
        )
        return StepReport(name="trailers", error_count=1, status="error")

    except Exception as exc:  # noqa: BLE001 — last-resort guard so the pipeline can dispatch
        logger.exception(
            "trailers_step_crashed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return StepReport(name="trailers", error_count=1, status="error")

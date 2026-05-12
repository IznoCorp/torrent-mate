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
from personalscraper.pipeline_observer import PipelineObserver, StepEvent, notify_progress

logger = get_logger(__name__)


def run_trailers(
    config: Any,
    staging_dir: Path,
    verified: list[Any],
    skip_trailers: bool = False,
    observers: tuple[PipelineObserver, ...] = (),
) -> StepReport:
    """Run the trailers pipeline step for all staged media items.

    Scans ``staging_dir`` for media without trailers, discovers YouTube URLs
    via TMDB/YouTube, downloads via yt-dlp, and places files using the per-type
    Plex placement convention (see ``trailers.placement``).
    Non-blocking: failures log a warning and dispatch continues.

    Args:
        config: Loaded pipeline Config.
        staging_dir: Path to the staging area (where sorted media lives).
        verified: List of items that passed the previous ``verify`` step. Items
            absent from this list are skipped (they failed verify already).
        skip_trailers: If True, return a skipped StepReport immediately.
        observers: Tuple of pipeline observers for progress and lifecycle notifications.

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
        notify_progress(
            observers,
            StepEvent(
                step="trailers",
                item="<step>",
                status="skipped",
                details={
                    "reason": "skip_flag" if skip_trailers else "disabled_by_config",
                },
            ),
        )
        return StepReport(name="trailers", status="skipped")

    # Deferred imports: avoids circular dependencies between this step entry-point
    # and the orchestrator / state modules (which import from this module's siblings).
    from personalscraper.trailers.orchestrator import TrailersOrchestrator  # noqa: PLC0415
    from personalscraper.trailers.state import TrailerStateLocked  # noqa: PLC0415

    try:
        orchestrator = TrailersOrchestrator(config=config, staging_dir=staging_dir)

        # Build the items list to pass to the orchestrator.
        #
        # When `verified` is non-empty (pipeline step invocation), restrict the
        # orchestrator to paths that were confirmed clean by the verify step.  We
        # perform a fresh scan and filter by allowed paths so ScanItem objects
        # carry the full metadata (title, year, tmdb_id) the orchestrator needs —
        # the VerifyResult items in `verified` do not carry that payload.
        #
        # When `verified` is empty or None (CLI-direct invocation, unit tests),
        # pass items=None so the orchestrator falls back to its own staging scan.
        orchestrator_items: list[Any] | None
        if verified:
            allowed_paths: set[Path] = {
                Path(item.path) for item in verified if getattr(item, "status", None) in ("success", "pass")
            }
            # scan_staging returns ScanItems whose .path matches staging entries;
            # filter to only those whose path is in the allowed set.
            all_scan_items = orchestrator._scanner.scan_staging(staging_dir, config)
            orchestrator_items = [si for si in all_scan_items if si.path in allowed_paths]
            logger.debug(
                "trailers_step_filtered_items",
                verified_count=len(verified),
                allowed_paths=len(allowed_paths),
                filtered_count=len(orchestrator_items),
            )
        else:
            # No verified list — let the orchestrator scan staging itself.
            orchestrator_items = None

        # Emit progress events for each item being processed.
        if orchestrator_items:
            for item in orchestrator_items:
                item_path = getattr(item, "path", None)
                item_name = str(item_path.name) if item_path else str(item)
                notify_progress(
                    observers,
                    StepEvent(step="trailers", item=item_name, status="started"),
                )

        counts = orchestrator.run(items=orchestrator_items)
        failed_items = orchestrator.failed_items
        item_results = orchestrator.item_results

        success_count = counts.get("downloaded", 0)
        skip_count = counts.get("already_present", 0) + counts.get("skipped_by_state", 0)
        error_count = counts.get("error", 0) + counts.get("bot_detected", 0)

        # Emit per-item completion events from orchestrator results
        for item_path, status, reason in item_results:
            notify_progress(
                observers,
                StepEvent(
                    step="trailers",
                    item=item_path,
                    status=status,
                    details={"reason": reason or ""},
                ),
            )

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
            failed_items=failed_items,  # type: ignore[arg-type]  # coerced via StepReport.__post_init__
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
        notify_progress(
            observers,
            StepEvent(
                step="trailers",
                item="<step>",
                status="failed",
                details={"reason": "state_locked", "holder_pid": str(exc.holder_pid or "")},
            ),
        )
        return StepReport(name="trailers", error_count=1, status="error")

    except OSError as exc:
        # Ops-transient filesystem error (disk full, read-only fs, NFS stale
        # handle) raised by TrailerStateStore._save().  Distinguished from logic
        # bugs (covered by the generic catch below) so operators can tell from
        # the event name that the root cause is infrastructure, not a code defect.
        logger.error(
            "trailers_state_write_failed",
            errno=exc.errno,
            path=str(exc.filename) if exc.filename else None,
            error=exc.strerror,
            exc_info=True,
        )
        notify_progress(
            observers,
            StepEvent(
                step="trailers",
                item="<step>",
                status="failed",
                details={"reason": "state_write_failed", "error": exc.strerror or ""},
            ),
        )
        return StepReport(
            name="trailers",
            error_count=1,
            status="error",
            details=[f"state write failed: {exc.strerror}"],
        )

    except Exception as exc:  # noqa: BLE001 — last-resort guard so the pipeline can dispatch
        logger.exception(
            "trailers_step_crashed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        notify_progress(
            observers,
            StepEvent(
                step="trailers",
                item="<step>",
                status="failed",
                details={"reason": "crashed", "error_type": type(exc).__name__},
            ),
        )
        return StepReport(name="trailers", error_count=1, status="error")

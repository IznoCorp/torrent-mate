"""Enforce step runner: entry point for the enforce pipeline step.

Executes three sub-components in order:
1. file_sanitizer — NTFS filenames, .DS_Store, resource forks
2. structure_validator — NFO count, artwork, season structure
3. coherence_checker — genre, IDs, sort↔process consistency

Each component works on the state left by the previous one.
"""

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus
from personalscraper.enforce.coherence_checker import check_coherence
from personalscraper.enforce.file_sanitizer import sanitize_files
from personalscraper.enforce.structure_validator import validate_structure
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.pipeline_events import ItemProgressed

log = get_logger("enforce.run")


def run_enforce(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
    only: frozenset[str] | None = None,
    *,
    event_bus: EventBus,
) -> StepReport:
    """Run the enforce pipeline step.

    Executes sanitize → structure → coherence in order.

    Emits structlog ``enforce_start`` / ``enforce_complete`` events bracketing
    the step; per-component ``enforce_sanitize_filename``, ``enforce_structure_ok``,
    ``enforce_coherence_ok`` events fire inside the loops.

    Args:
        settings: Pipeline configuration.
        config: Config passed to the coherence checker for classifier rules.
        dry_run: If True, preview without modifying filesystem.
        only: Optional allow-set of check names restricting the coherence
            sub-component to the named STAGING-stage checks. ``None`` (default)
            runs every check — byte-identical to the pre-filter behavior. The
            sanitize and structure sub-components are unaffected (they are not
            registry-driven).
        event_bus: Required in-process EventBus. Each per-item
        lifecycle transition emits an ``ItemProgressed`` event on the bus.

    Returns:
        StepReport with enforce counts and details.
    """
    log.info("enforce_start", dry_run=dry_run)

    # Each sub-component emits its per-item ``started`` events (F8, real
    # lifecycle) as it works; the terminal transitions + counters are recorded
    # below from the returned results.
    sanitize_results = sanitize_files(settings, config, dry_run, bus=event_bus)
    structure_results = validate_structure(settings, config, dry_run, bus=event_bus)
    coherence_results = check_coherence(settings, config, dry_run, only, bus=event_bus)

    success = 0
    warnings_list: list[str] = []
    details: list[str] = []

    # Sanitize actions (``started`` already emitted by ``sanitize_files``, F8)
    for sanitize_result in sanitize_results:
        if sanitize_result.action not in ("skipped",):
            success += 1
            details.append(
                f"[sanitize:{sanitize_result.action}] {sanitize_result.old_name}"
                + (f" → {sanitize_result.new_name}" if sanitize_result.new_name else "")
            )
            event_bus.emit(
                ItemProgressed(
                    step="enforce",
                    item=sanitize_result.old_name or "",
                    status="fixed",
                    details={
                        "action": sanitize_result.action,
                        "new_name": sanitize_result.new_name or "",
                    },
                )
            )
            log.info(
                "enforce_sanitize_action",
                action=sanitize_result.action,
                old_name=sanitize_result.old_name,
                new_name=sanitize_result.new_name,
            )
            if sanitize_result.action in ("renamed", "deleted_duplicate"):
                log.info(
                    "enforce_sanitize_filename",
                    action=sanitize_result.action,
                    old_name=sanitize_result.old_name,
                    new_name=sanitize_result.new_name,
                )
        else:
            event_bus.emit(ItemProgressed(step="enforce", item=sanitize_result.old_name or "", status="skipped"))

    # Structure fixes (``started`` already emitted by ``validate_structure``, F8)
    for structure_result in structure_results:
        item_name = structure_result.path.name
        if structure_result.action == "repaired":
            success += 1
            for fix in structure_result.fixes:
                details.append(f"[structure:fix] {item_name}: {fix}")
                log.info("enforce_structure_fix", item=item_name, fix=fix)
            event_bus.emit(
                ItemProgressed(step="enforce", item=item_name, status="fixed", details={"component": "structure"})
            )
        else:
            event_bus.emit(
                ItemProgressed(
                    step="enforce",
                    item=item_name,
                    status="skipped",
                    details={"component": "structure", "action": structure_result.action},
                )
            )
            log.info("enforce_structure_ok", item=item_name)
        for w in structure_result.warnings:
            warnings_list.append(f"{item_name}: {w}")
            log.warning("enforce_structure_warning", item=item_name, warning=w)

    # Coherence warnings (``started`` already emitted by ``check_coherence``, F8)
    for coherence_result in coherence_results:
        item_name = coherence_result.path.name
        if coherence_result.warnings:
            event_bus.emit(
                ItemProgressed(
                    step="enforce",
                    item=item_name,
                    status="fixed",
                    details={"component": "coherence", "warning_count": len(coherence_result.warnings)},
                )
            )
        else:
            event_bus.emit(
                ItemProgressed(step="enforce", item=item_name, status="skipped", details={"component": "coherence"})
            )
            log.info("enforce_coherence_ok", item=item_name)
        for w in coherence_result.warnings:
            warnings_list.append(f"[coherence] {item_name}: {w}")
            log.warning("enforce_coherence_warning", item=item_name, warning=w)

    skip_count = sum(1 for sr in sanitize_results if sr.action == "skipped") + sum(
        1 for sr in structure_results if sr.action == "validated"
    )

    error_count = sum(1 for sr in sanitize_results if sr.action == "error") + sum(
        1 for sr in structure_results if sr.action == "error"
    )

    log.info(
        "enforce_complete",
        success=success,
        skip=skip_count,
        error=error_count,
        warnings=len(warnings_list),
    )

    return StepReport(
        name="enforce",
        success_count=success,
        skip_count=skip_count,
        error_count=error_count,
        warnings=warnings_list,
        details=details,
    )

"""Enforce step runner: entry point for the enforce pipeline step.

Executes three sub-components in order:
1. file_sanitizer — NTFS filenames, .DS_Store, resource forks
2. structure_validator — NFO count, artwork, season structure
3. coherence_checker — genre, IDs, sort↔process consistency

Each component works on the state left by the previous one.
"""

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.enforce.coherence_checker import check_coherence
from personalscraper.enforce.file_sanitizer import sanitize_files
from personalscraper.enforce.structure_validator import validate_structure
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.pipeline_observer import PipelineObserver

log = get_logger("enforce.run")


def run_enforce(settings: Settings, config: Config, dry_run: bool = False, *, observers: tuple[PipelineObserver, ...] = ()) -> StepReport:
    """Run the enforce pipeline step.

    Executes sanitize → structure → coherence in order.

    Args:
        settings: Pipeline configuration.
        config: Config passed to the coherence checker for classifier rules.
        dry_run: If True, preview without modifying filesystem.

    Returns:
        StepReport with enforce counts and details.
    """
    sanitize_results = sanitize_files(settings, config, dry_run)
    structure_results = validate_structure(settings, config, dry_run)
    coherence_results = check_coherence(settings, config, dry_run)

    success = 0
    warnings_list: list[str] = []
    details: list[str] = []

    # Sanitize actions
    for sanitize_result in sanitize_results:
        if sanitize_result.action not in ("skipped",):
            success += 1
            details.append(
                f"[sanitize:{sanitize_result.action}] {sanitize_result.old_name}"
                + (f" → {sanitize_result.new_name}" if sanitize_result.new_name else "")
            )
            log.info(
                "enforce_sanitize_action",
                action=sanitize_result.action,
                old_name=sanitize_result.old_name,
                new_name=sanitize_result.new_name,
            )

    # Structure fixes
    for structure_result in structure_results:
        if structure_result.action == "repaired":
            success += 1
            for fix in structure_result.fixes:
                details.append(f"[structure:fix] {structure_result.path.name}: {fix}")
                log.info(
                    "enforce_structure_fix",
                    item=structure_result.path.name,
                    fix=fix,
                )
        for w in structure_result.warnings:
            warnings_list.append(f"{structure_result.path.name}: {w}")
            log.warning(
                "enforce_structure_warning",
                item=structure_result.path.name,
                warning=w,
            )

    # Coherence warnings
    for coherence_result in coherence_results:
        for w in coherence_result.warnings:
            warnings_list.append(f"[coherence] {coherence_result.path.name}: {w}")
            log.warning(
                "enforce_coherence_warning",
                item=coherence_result.path.name,
                warning=w,
            )

    skip_count = sum(1 for sr in sanitize_results if sr.action == "skipped") + sum(
        1 for sr in structure_results if sr.action == "validated"
    )

    error_count = sum(1 for sr in sanitize_results if sr.action == "error") + sum(
        1 for sr in structure_results if sr.action == "error"
    )

    return StepReport(
        name="enforce",
        success_count=success,
        skip_count=skip_count,
        error_count=error_count,
        warnings=warnings_list,
        details=details,
    )

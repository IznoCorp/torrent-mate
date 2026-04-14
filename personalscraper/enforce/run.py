"""Enforce step runner: entry point for the enforce pipeline step.

Executes three sub-components in order:
1. file_sanitizer — NTFS filenames, .DS_Store, resource forks
2. structure_validator — NFO count, artwork, season structure
3. coherence_checker — genre, IDs, sort↔process consistency

Each component works on the state left by the previous one.
"""

import logging

from personalscraper.config import Settings
from personalscraper.enforce.coherence_checker import check_coherence
from personalscraper.enforce.file_sanitizer import sanitize_files
from personalscraper.enforce.structure_validator import validate_structure
from personalscraper.models import StepReport

logger = logging.getLogger(__name__)


def run_enforce(settings: Settings, dry_run: bool = False) -> StepReport:
    """Run the enforce pipeline step.

    Executes sanitize → structure → coherence in order.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without modifying filesystem.

    Returns:
        StepReport with enforce counts and details.
    """
    sanitize_results = sanitize_files(settings, dry_run)
    structure_results = validate_structure(settings, dry_run)
    coherence_results = check_coherence(settings, dry_run)

    success = 0
    warnings_list: list[str] = []
    details: list[str] = []

    # Sanitize actions
    for r in sanitize_results:
        if r.action not in ("skipped",):
            success += 1
            details.append(
                f"[sanitize:{r.action}] {r.old_name}"
                + (f" → {r.new_name}" if r.new_name else "")
            )

    # Structure fixes
    for r in structure_results:
        if r.action == "repaired":
            success += 1
            for fix in r.fixes:
                details.append(f"[structure:fix] {r.path.name}: {fix}")
        for w in r.warnings:
            warnings_list.append(f"{r.path.name}: {w}")

    # Coherence warnings
    for r in coherence_results:
        for w in r.warnings:
            warnings_list.append(f"[coherence] {r.path.name}: {w}")

    skip_count = sum(1 for r in sanitize_results if r.action == "skipped") + sum(
        1 for r in structure_results if r.action == "validated"
    )

    return StepReport(
        name="enforce",
        success_count=success,
        skip_count=skip_count,
        error_count=0,
        warnings=warnings_list,
        details=details,
    )

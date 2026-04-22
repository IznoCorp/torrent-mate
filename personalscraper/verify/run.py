"""Verify step runner: entry point for the verify pipeline step.

Instantiates the Verifier, processes movies and TV shows, and
converts VerifyResult lists to StepReport.
"""

import logging
from pathlib import Path

from personalscraper.conf.models import Config
from personalscraper.config import Settings
from personalscraper.models import StepReport
from personalscraper.naming_patterns import PATTERNS
from personalscraper.verify.verifier import Verifier, VerifyResult

logger = logging.getLogger(__name__)


def _has_items_to_verify(settings: Settings) -> bool:
    """Check if any media folders exist in category directories.

    Used for fast-skip: if no media folders exist, the entire
    verify phase is skipped.

    Args:
        settings: Pipeline configuration.

    Returns:
        True if at least one media folder exists.
    """
    staging = Path(getattr(settings, "staging_dir", "."))
    for dir_name in (settings.movies_dir_name, settings.tvshows_dir_name):
        cat_dir = staging / dir_name
        if not cat_dir.exists():
            continue
        for item in cat_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                return True
    return False


def run_verify(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
    fix: bool = True,
    movies_only: bool = False,
    tvshows_only: bool = False,
) -> tuple[StepReport, list[VerifyResult]]:
    """Run the verify pipeline step.

    Args:
        settings: Pipeline configuration.
        config: Config passed to the Verifier for classifier-backed
            category resolution.
        dry_run: If True, preview without modifying files.
        fix: If True, attempt automatic corrections.
        movies_only: Process only 001-MOVIES/.
        tvshows_only: Process only 002-TVSHOWS/.

    Returns:
        Tuple of (StepReport, dispatchable VerifyResult list).
    """
    # Fast-skip: no media folders to verify
    if not _has_items_to_verify(settings):
        logger.info("Verify fast-skip: no media folders found")
        return StepReport(name="verify"), []

    verifier = Verifier(
        settings=settings,
        patterns=PATTERNS,
        config=config,
        dry_run=dry_run,
        fix=fix,
    )

    all_results: list[VerifyResult] = []
    staging = Path(getattr(settings, "staging_dir", "."))

    if not tvshows_only:
        movies_dir = staging / settings.movies_dir_name
        if movies_dir.exists():
            all_results.extend(verifier.verify_all_movies(movies_dir))

    if not movies_only:
        tvshows_dir = staging / settings.tvshows_dir_name
        if tvshows_dir.exists():
            all_results.extend(verifier.verify_all_tvshows(tvshows_dir))

    dispatchable = Verifier.get_dispatchable(all_results)
    report = _to_step_report(all_results)

    return report, dispatchable


def _to_step_report(results: list[VerifyResult]) -> StepReport:
    """Convert VerifyResult list to StepReport.

    Args:
        results: List of verify results.

    Returns:
        StepReport with aggregated counts.
    """
    valid = sum(1 for r in results if r.status == "valid")
    fixed = sum(1 for r in results if r.status == "fixed")
    blocked = sum(1 for r in results if r.status == "blocked")
    warnings: list[str] = []
    details: list[str] = []

    for r in results:
        name = r.media_path.name
        cat = f" [{r.category}]" if r.category else ""
        if r.status == "valid":
            details.append(f"[valid] {name}{cat}")
        elif r.status == "fixed":
            fixes = ", ".join(r.fixes_applied)
            details.append(f"[fixed] {name}{cat} — {fixes}")
        elif r.status == "blocked":
            errs = "; ".join(r.errors)
            details.append(f"[blocked] {name} — {errs}")
            warnings.append(f"{name}: {errs}")

    return StepReport(
        name="verify",
        success_count=valid + fixed,
        skip_count=0,
        error_count=blocked,
        warnings=warnings,
        details=details,
    )

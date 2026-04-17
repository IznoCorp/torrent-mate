"""Library validator — check NFO, artwork, naming, structure conformity.

Wraps existing verify/checker.py checks for use on storage disks.
Distinction with enforce: enforce = staging (A TRIER/), validate = library (Disk1-4).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from personalscraper.genre_mapper import GenreMapper
from personalscraper.library.models import (
    LibraryValidationResult,
    ValidationItem,
)
from personalscraper.library.scanner import _SERIES_CATEGORIES, _parse_title_year
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checker import CheckResult, MediaChecker, Severity

logger = logging.getLogger(__name__)


def _classify_results(
    checks: list[CheckResult],
) -> tuple[list[str], list[str]]:
    """Split check results into errors and warnings.

    Args:
        checks: List of CheckResult from MediaChecker.

    Returns:
        Tuple of (error names, warning names) for failed checks.
    """
    errors = [c.name for c in checks if not c.passed and c.severity == Severity.ERROR]
    warnings = [c.name for c in checks if not c.passed and c.severity == Severity.WARNING]
    return errors, warnings


def validate_library(
    disk_configs: list,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    level: str = "full",
) -> LibraryValidationResult:
    """Validate all library items on storage disks.

    Args:
        disk_configs: List of DiskConfig objects.
        disk_filter: Only validate this disk. None = all.
        category_filter: Only validate this category. None = all.
        level: "quick" (NFO + poster only) or "full" (all checks).

    Returns:
        LibraryValidationResult with per-item validation status.
    """
    checker = MediaChecker(NamingPatterns(), GenreMapper())
    items: list[ValidationItem] = []
    valid_count = 0
    blocked_count = 0
    start = datetime.now(tz=timezone.utc).isoformat()

    for config in disk_configs:
        if disk_filter and config.name != disk_filter:
            continue
        if not config.path.exists():
            continue

        for category_dir in sorted(config.path.iterdir()):
            if not category_dir.is_dir():
                continue
            if category_dir.name not in config.categories:
                continue
            if category_filter and category_dir.name != category_filter:
                continue

            is_series = category_dir.name in _SERIES_CATEGORIES

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue

                title, year = _parse_title_year(media_dir.name)

                try:
                    if is_series:
                        checks = checker.check_tvshow(media_dir)
                    else:
                        checks = checker.check_movie(media_dir)
                except Exception as exc:
                    logger.warning("Error checking %s: %s", media_dir, exc)
                    items.append(ValidationItem(
                        path=str(media_dir), disk=config.name,
                        category=category_dir.name,
                        media_type="tvshow" if is_series else "movie",
                        title=title, year=year, status="blocked",
                        errors=[f"os_error: {exc}"],
                    ))
                    blocked_count += 1
                    continue

                errors, warnings = _classify_results(checks)

                if errors:
                    status = "blocked"
                    blocked_count += 1
                else:
                    status = "valid"
                    valid_count += 1

                items.append(ValidationItem(
                    path=str(media_dir), disk=config.name,
                    category=category_dir.name,
                    media_type="tvshow" if is_series else "movie",
                    title=title, year=year, status=status,
                    errors=errors, warnings=warnings,
                ))

    return LibraryValidationResult(
        validated_at=start,
        disk_filter=disk_filter,
        category_filter=category_filter,
        total_items=len(items),
        valid_count=valid_count,
        fixed_count=0,
        blocked_count=blocked_count,
        items=items,
    )

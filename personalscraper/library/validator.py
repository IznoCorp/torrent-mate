"""Library validator — check NFO, artwork, naming, structure conformity.

Wraps existing verify/checker.py checks for use on storage disks.
Supports --fix mode for local corrections (empty dirs, NTFS names, dir naming).
Distinction with enforce: enforce = staging (``paths.staging_dir``), validate = library (configured storage disks).

``validate_library`` accepts a ``Config`` object and resolves folder names
from ``config.category(id).folder_name``. TV detection uses ``TV_CATEGORY_IDS``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.conf.models import Config

from personalscraper.conf.ids import TV_CATEGORY_IDS
from personalscraper.library.models import (
    LibraryValidationResult,
    ValidationItem,
)
from personalscraper.library.scanner import parse_title_year
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.text_utils import sanitize_filename
from personalscraper.verify.checker import CheckResult, MediaChecker, Severity
from personalscraper.verify.fixer import MediaFixer

log = get_logger("library.validator")


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


def _fix_empty_dirs(media_dir: Path, dry_run: bool) -> list[str]:
    """Remove empty subdirectories from a media directory.

    Args:
        media_dir: Path to media directory.
        dry_run: If True, only report without deleting.

    Returns:
        List of fix descriptions.
    """
    fixes = []
    try:
        for subdir in list(media_dir.iterdir()):
            if subdir.is_dir() and not any(subdir.iterdir()):
                if not dry_run:
                    try:
                        subdir.rmdir()
                    except OSError as exc:
                        log.warning(
                            "library_validate_remove_empty_dir_failed",
                            subdir=str(subdir),
                            exc_info=True,
                            error=str(exc),
                        )
                        continue
                prefix = "[DRY-RUN] Would remove" if dry_run else "Removed"
                fixes.append(f"{prefix} empty dir: {subdir.name}")
    except OSError as exc:
        log.warning("library_validate_list_error", media_dir=str(media_dir), exc_info=True, error=str(exc))
    return fixes


def _fix_ntfs_names(media_dir: Path, dry_run: bool) -> list[str]:
    """Rename files with NTFS-illegal characters.

    Args:
        media_dir: Path to media directory.
        dry_run: If True, only report without renaming.

    Returns:
        List of fix descriptions.
    """
    fixes = []
    try:
        for item in media_dir.rglob("*"):
            if item.is_file():
                safe_name = sanitize_filename(item.name)
                if safe_name != item.name:
                    if not dry_run:
                        try:
                            item.rename(item.parent / safe_name)
                        except OSError as exc:
                            log.warning(
                                "library_validate_ntfs_rename_failed",
                                item=str(item),
                                exc_info=True,
                                error=str(exc),
                            )
                            continue
                    prefix = "[DRY-RUN] Would rename" if dry_run else "Renamed"
                    fixes.append(f"{prefix}: {item.name} → {safe_name}")
    except OSError as exc:
        log.warning("library_validate_ntfs_list_error", media_dir=str(media_dir), exc_info=True, error=str(exc))
    return fixes


def validate_library(
    config: Config,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    fix: bool = False,
    apply: bool = False,
) -> LibraryValidationResult:
    """Validate all library items on storage disks.

    Iterates ``config.disks``, resolves folder names from
    ``config.category(id).folder_name``, and validates media directories.
    TV detection uses ``TV_CATEGORY_IDS`` from ``conf/ids``.

    Args:
        config: Config with disk and category definitions.
        disk_filter: Only validate this disk (by disk.id). None = all.
        category_filter: Only validate this category_id. None = all.
        fix: If True, attempt to fix locally fixable issues.
        apply: If True (with fix), actually execute fixes. False = dry-run.

    Returns:
        LibraryValidationResult with per-item validation status.
    """
    patterns = NamingPatterns()
    checker = MediaChecker(patterns, config)
    fixer = MediaFixer(patterns, dry_run=not apply) if fix else None
    items: list[ValidationItem] = []
    valid_count = 0
    fixed_count = 0
    issues_count = 0
    start = datetime.now(tz=timezone.utc).isoformat()

    for disk in config.disks:
        if disk_filter and disk.id != disk_filter:
            continue
        if not disk.path.exists():
            log.warning("library_validate_disk_not_mounted", disk=disk.id, path=str(disk.path))
            continue

        for category_id in disk.categories:
            if category_filter and category_id != category_filter:
                continue

            # Resolve physical folder name from config
            cat_cfg = config.category(category_id)
            category_dir = disk.path / cat_cfg.folder_name
            if not category_dir.is_dir():
                log.debug("library_validate_category_not_found", category_dir=str(category_dir), disk=disk.id)
                continue

            is_series = category_id in TV_CATEGORY_IDS

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue

                title, year = parse_title_year(media_dir.name)

                try:
                    if is_series:
                        checks = checker.check_tvshow(media_dir)
                    else:
                        checks = checker.check_movie(media_dir)
                except OSError as exc:
                    log.warning("library_validate_fs_error", media_dir=str(media_dir), exc_info=True, error=str(exc))
                    items.append(
                        ValidationItem(
                            path=str(media_dir),
                            disk=disk.id,
                            category=category_id,
                            media_type="tvshow" if is_series else "movie",
                            title=title,
                            year=year,
                            status="issues",
                            errors=[f"os_error: {exc}"],
                        )
                    )
                    issues_count += 1
                    continue

                errors, warnings = _classify_results(checks)
                fixes_applied: list[str] = []
                fixed_error_names: set[str] = set()

                # --- Apply fixes if requested ---
                if fix and errors:
                    # Fix 1: dir_naming via MediaFixer (rename from NFO title+year)
                    if "dir_naming" in errors and fixer:
                        fixable_checks = [c for c in checks if not c.passed and c.fixable]
                        if fixable_checks:
                            if is_series:
                                actions = fixer.fix_tvshow(media_dir, fixable_checks)
                            else:
                                actions = fixer.fix_movie(media_dir, fixable_checks)
                            for a in actions:
                                fixes_applied.append(a.description)
                                fixed_error_names.add("dir_naming")
                                # Update media_dir if renamed
                                if a.new_path and apply:
                                    media_dir = a.new_path

                    # Fix 2: Empty subdirectories
                    if "no_empty_dirs" in errors:
                        empty_fixes = _fix_empty_dirs(media_dir, dry_run=not apply)
                        fixes_applied.extend(empty_fixes)
                        if empty_fixes:
                            fixed_error_names.add("no_empty_dirs")

                    # Fix 3: NTFS-unsafe filenames
                    if "ntfs_safe_names" in errors:
                        ntfs_fixes = _fix_ntfs_names(media_dir, dry_run=not apply)
                        fixes_applied.extend(ntfs_fixes)
                        if ntfs_fixes:
                            fixed_error_names.add("ntfs_safe_names")

                # Determine final status
                remaining_errors = [e for e in errors if e not in fixed_error_names]
                if fixes_applied and not remaining_errors:
                    status = "fixed"
                    fixed_count += 1
                elif not remaining_errors:
                    status = "valid"
                    valid_count += 1
                else:
                    status = "issues"
                    issues_count += 1

                items.append(
                    ValidationItem(
                        path=str(media_dir),
                        disk=disk.id,
                        category=category_id,
                        media_type="tvshow" if is_series else "movie",
                        title=title,
                        year=year,
                        status=status,
                        errors=remaining_errors,
                        warnings=warnings,
                        fixes_applied=fixes_applied,
                    )
                )

    return LibraryValidationResult(
        validated_at=start,
        disk_filter=disk_filter,
        category_filter=category_filter,
        total_items=len(items),
        valid_count=valid_count,
        fixed_count=fixed_count,
        issues_count=issues_count,
        items=items,
    )

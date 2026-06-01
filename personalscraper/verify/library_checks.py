"""Library media-item validation checks — standalone verify module.

Wraps :class:`verify.checker.MediaChecker` and :class:`verify.fixer.MediaFixer`
to produce per-item validation results. Kept standalone (NOT inlined into
``checker.py``) to respect the 1000-LOC hard ceiling on that module and to
enable future registration in the Check plugin system.

Checks NFO, artwork, naming, structure conformity on storage disks.
Supports --fix mode for local corrections (empty dirs, NTFS names, dir naming).
Distinction with enforce: enforce = staging (``paths.staging_dir``),
validate = library (configured storage disks).

``validate_library`` accepts a ``Config`` object and resolves folder names
from ``config.category(id).folder_name``. TV detection uses ``TV_CATEGORY_IDS``.

Dataclasses ``ValidationItem`` and ``LibraryValidationResult`` live here
(DESIGN §4.6 — verify is the producer/consumer).

Moved from the legacy library validator module during lib-fold Phase 5.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config

from personalscraper.conf.ids import TV_CATEGORY_IDS
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.nfo_utils import parse_title_year
from personalscraper.text_utils import sanitize_filename
from personalscraper.verify.checker import CheckResult, MediaChecker, Severity
from personalscraper.verify.fixer import MediaFixer

log = get_logger("library.validator")


# --- Validation models ---

_VALID_VALIDATION_STATUSES = {"valid", "fixed", "issues"}


@dataclass
class ValidationItem:
    """Validation result for a single library item.

    Attributes:
        path: Absolute path to media directory (str for JSON).
        disk: Disk name.
        category: Category name.
        media_type: "movie" or "tvshow".
        title: Media title.
        year: Release year.
        status: "valid", "fixed", or "issues" (has quality problems).
        errors: List of error check names that failed.
        warnings: List of warning check names that failed.
        fixes_applied: List of fixes that were applied (if --fix --apply).
    """

    path: str
    disk: str
    category: str
    media_type: str
    title: str
    year: int | None
    status: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    fixes_applied: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Enforce status/errors/fixes_applied consistency."""
        if self.status not in _VALID_VALIDATION_STATUSES:
            raise ValueError(f"status must be one of {_VALID_VALIDATION_STATUSES}, got '{self.status}'")
        if self.status == "fixed" and not self.fixes_applied:
            raise ValueError("status='fixed' requires non-empty fixes_applied")
        if self.status == "valid" and (self.errors or self.fixes_applied):
            raise ValueError("status='valid' must have empty errors and fixes_applied")
        if self.status == "issues" and not (self.errors or self.warnings):
            raise ValueError("status='issues' requires non-empty errors or warnings")


@dataclass
class LibraryValidationResult:
    """Top-level container for library_validation.json."""

    validated_at: str
    disk_filter: str | None
    category_filter: str | None
    total_items: int
    valid_count: int
    fixed_count: int
    issues_count: int
    items: list[ValidationItem] = field(default_factory=list)


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


def validate_from_index(
    conn: sqlite3.Connection,
    disk_filter: str | None = None,
    category_filter: str | None = None,
) -> LibraryValidationResult:
    """Cheap validate path that reads NFO + artwork status from the indexer DB.

    Skips every filesystem walk: each ``media_item`` row already carries
    ``nfo_status`` (from the enrich pass NFO presence check) and
    ``artwork_json`` (from the enrich pass artwork inventory). This mode
    surfaces missing / invalid NFO and missing poster + landscape, and
    nothing else.

    Trade-offs vs :func:`validate_library` (the FS-direct path):

    - **Misses structural issues** — ``no_empty_dirs``, ``ntfs_safe_names``,
      ``dir_naming``, ``video_present``, ``not_sample``, ``streamdetails``,
      ``season_structure``, ``season_posters`` checks all need the actual
      filesystem and are not run here.
    - **Stale data risk** — if files moved on disk since the last enrich
      pass, the index still reports the old state. Run
      ``library-index --mode enrich`` first to refresh.
    - **No ``--fix`` support** — fixes act on the filesystem; a fast
      pre-screen has no business mutating disks.

    Use as a quick health check between full validates, or to drive
    follow-up scoping for ``library-rescrape``.

    Args:
        conn: Open SQLite connection on the indexer DB.
        disk_filter: Restrict to items on a specific disk (matches
            ``item_attribute.dispatch_disk``).
        category_filter: Restrict to a single ``media_item.category_id``.

    Returns:
        :class:`LibraryValidationResult` populated from the index.
    """
    start = datetime.now(tz=timezone.utc).isoformat()
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT mi.id, mi.kind, mi.title, mi.year, mi.category_id,
               mi.nfo_status, mi.artwork_json,
               ia_disk.value AS disk_label,
               ia_path.value AS dispatch_path
          FROM media_item mi
     LEFT JOIN item_attribute ia_disk
            ON ia_disk.item_id = mi.id AND ia_disk.key = 'dispatch_disk'
     LEFT JOIN item_attribute ia_path
            ON ia_path.item_id = mi.id AND ia_path.key = 'dispatch_path'
      ORDER BY mi.title_sort, mi.id
        """
    ).fetchall()

    items: list[ValidationItem] = []
    valid_count = 0
    issues_count = 0

    for row in rows:
        if disk_filter is not None and row["disk_label"] != disk_filter:
            continue
        if category_filter is not None and row["category_id"] != category_filter:
            continue

        media_type = "tvshow" if row["kind"] == "show" else "movie"

        errors: list[str] = []
        warnings: list[str] = []

        nfo_status = row["nfo_status"]
        if nfo_status == "missing":
            errors.append("nfo_present")
        elif nfo_status == "invalid":
            errors.append("nfo_valid")
        # nfo_status=='valid' or NULL (item never enriched) → no NFO finding;
        # NULL is not flagged because we cannot distinguish "not yet enriched"
        # from "no NFO" without re-walking the filesystem.

        artwork_raw = row["artwork_json"]
        if artwork_raw:
            try:
                artwork = json.loads(artwork_raw)
            except (TypeError, ValueError):
                artwork = {}
            if not artwork.get("poster"):
                errors.append("poster_present")
            if media_type == "movie" and not artwork.get("landscape"):
                warnings.append("artwork_landscape")

        if errors or warnings:
            status = "issues"
            issues_count += 1
        else:
            status = "valid"
            valid_count += 1

        items.append(
            ValidationItem(
                path=str(row["dispatch_path"] or ""),
                disk=str(row["disk_label"] or ""),
                category=row["category_id"],
                media_type=media_type,
                title=row["title"],
                year=row["year"],
                status=status,
                errors=errors,
                warnings=warnings,
            )
        )

    conn.row_factory = None

    return LibraryValidationResult(
        validated_at=start,
        disk_filter=disk_filter,
        category_filter=category_filter,
        total_items=len(items),
        valid_count=valid_count,
        fixed_count=0,
        issues_count=issues_count,
        items=items,
    )


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

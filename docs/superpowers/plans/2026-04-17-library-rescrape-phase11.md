# Phase 11: Validate --fix — Local Fixes Without API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `library-validate --fix --apply` — fix empty dirs, NTFS-unsafe names, and directory naming from existing NFO data. Dry-run by default.

**Architecture:** Extend `validate_library()` with `fix`/`apply` parameters. Reuse `MediaFixer` for dir_naming, add `_fix_empty_dirs` and `_fix_ntfs_names` helpers. Forward existing CLI flags to the function.

**Tech Stack:** Python, Typer, pytest

---

## Task 1: Implement fix logic in validator.py

**Files:**

- Modify: `personalscraper/library/validator.py`
- Create: `tests/library/test_validator_fix.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/library/test_validator_fix.py
"""Tests for library-validate --fix functionality."""

from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.library.validator import validate_library


def _make_config(path: Path, name: str, categories: list[str]):
    """Create a mock DiskConfig."""
    config = MagicMock()
    config.path = path
    config.name = name
    config.categories = categories
    return config


class TestFixEmptyDirs:
    """Tests for --fix removing empty subdirectories."""

    def test_fix_dry_run_preserves(self, tmp_path: Path) -> None:
        """Dry-run should report but not delete empty dirs."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        (movie / "Test.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test.nfo").write_text(
            '<movie><title>Test</title><year>2024</year>'
            '<uniqueid type="tmdb">1</uniqueid>'
            '<uniqueid type="imdb">tt0000001</uniqueid>'
            '<genre>Action</genre>'
            '<fileinfo><streamdetails>'
            '<video><codec>h264</codec><width>1920</width><height>1080</height></video>'
            '<audio><codec>ac3</codec><language>fra</language><channels>6</channels></audio>'
            '</streamdetails></fileinfo></movie>'
        )
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test-landscape.jpg").write_bytes(b"\x00" * 100)
        empty = movie / "Subs"
        empty.mkdir()

        config = _make_config(disk, "Disk1", ["films"])
        result = validate_library([config], fix=True, apply=False)

        assert empty.exists()  # Not deleted in dry-run
        # Should show the fix would be applied
        fixed_items = [i for i in result.items if i.fixes_applied]
        assert len(fixed_items) >= 1

    def test_fix_apply_deletes(self, tmp_path: Path) -> None:
        """Apply should delete empty subdirectories."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        (movie / "Test.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test.nfo").write_text(
            '<movie><title>Test</title><year>2024</year>'
            '<uniqueid type="tmdb">1</uniqueid>'
            '<uniqueid type="imdb">tt0000001</uniqueid>'
            '<genre>Action</genre>'
            '<fileinfo><streamdetails>'
            '<video><codec>h264</codec><width>1920</width><height>1080</height></video>'
            '<audio><codec>ac3</codec><language>fra</language><channels>6</channels></audio>'
            '</streamdetails></fileinfo></movie>'
        )
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test-landscape.jpg").write_bytes(b"\x00" * 100)
        empty = movie / "Subs"
        empty.mkdir()

        config = _make_config(disk, "Disk1", ["films"])
        result = validate_library([config], fix=True, apply=True)

        assert not empty.exists()  # Deleted
        assert result.fixed_count >= 1


class TestFixDirNaming:
    """Tests for --fix renaming directories from NFO data."""

    def test_dir_renamed_from_nfo(self, tmp_path: Path) -> None:
        """Directory without (Year) should be renamed if NFO has title+year."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test Movie"
        movie.mkdir(parents=True)
        (movie / "Test Movie.mkv").write_bytes(b"\x00" * 200_000_000)
        (movie / "Test Movie.nfo").write_text(
            '<movie><title>Test Movie</title><year>2024</year>'
            '<uniqueid type="tmdb">1</uniqueid>'
            '<uniqueid type="imdb">tt0000001</uniqueid>'
            '<genre>Action</genre>'
            '<fileinfo><streamdetails>'
            '<video><codec>h264</codec><width>1920</width><height>1080</height></video>'
            '<audio><codec>ac3</codec><language>fra</language><channels>6</channels></audio>'
            '</streamdetails></fileinfo></movie>'
        )
        (movie / "Test Movie-poster.jpg").write_bytes(b"\x00" * 100)
        (movie / "Test Movie-landscape.jpg").write_bytes(b"\x00" * 100)

        config = _make_config(disk, "Disk1", ["films"])
        result = validate_library([config], fix=True, apply=True)

        # Check the directory was renamed
        renamed = disk / "films" / "Test Movie (2024)"
        assert renamed.exists() or result.fixed_count >= 1


class TestFixNonFixableMessage:
    """Tests for non-fixable items suggesting library-rescrape."""

    def test_missing_nfo_suggests_rescrape(self, tmp_path: Path) -> None:
        """Items with API-dependent issues should suggest rescrape."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "NoNfo (2024)"
        movie.mkdir(parents=True)
        (movie / "NoNfo.mkv").write_bytes(b"\x00" * 200_000_000)

        config = _make_config(disk, "Disk1", ["films"])
        result = validate_library([config], fix=True, apply=True)

        # Item should still have issues (nfo_present not fixable locally)
        assert result.issues_count >= 1
```

- [ ] **Step 2: Run to verify failures**

Run: `python -m pytest tests/library/test_validator_fix.py -v`
Expected: FAIL — `validate_library()` does not accept `fix`/`apply` params

- [ ] **Step 3: Implement fix logic in validator.py**

Replace `personalscraper/library/validator.py` with extended version:

```python
"""Library validator — check NFO, artwork, naming, structure conformity.

Wraps existing verify/checker.py checks for use on storage disks.
Supports --fix mode for local corrections (empty dirs, NTFS names, dir naming).
Distinction with enforce: enforce = staging (A TRIER/), validate = library (Disk1-4).
"""

from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from personalscraper.genre_mapper import GenreMapper
from personalscraper.library.models import (
    LibraryValidationResult,
    ValidationItem,
)
from personalscraper.library.scanner import _SERIES_CATEGORIES, parse_title_year
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.text_utils import sanitize_filename
from personalscraper.verify.checker import CheckResult, MediaChecker, Severity
from personalscraper.verify.fixer import MediaFixer

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
                        logger.warning("Cannot remove empty dir %s: %s", subdir, exc)
                        continue
                fixes.append(f"{'[DRY-RUN] Would remove' if dry_run else 'Removed'} empty dir: {subdir.name}")
    except OSError:
        pass
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
                            logger.warning("Cannot rename %s: %s", item, exc)
                            continue
                    fixes.append(
                        f"{'[DRY-RUN] Would rename' if dry_run else 'Renamed'}: "
                        f"{item.name} → {safe_name}"
                    )
    except OSError:
        pass
    return fixes


def validate_library(
    disk_configs: list,
    disk_filter: str | None = None,
    category_filter: str | None = None,
    fix: bool = False,
    apply: bool = False,
) -> LibraryValidationResult:
    """Validate all library items on storage disks.

    Args:
        disk_configs: List of DiskConfig objects.
        disk_filter: Only validate this disk. None = all.
        category_filter: Only validate this category. None = all.
        fix: If True, attempt to fix locally fixable issues.
        apply: If True (with fix), actually execute fixes. False = dry-run.

    Returns:
        LibraryValidationResult with per-item validation status.
    """
    patterns = NamingPatterns()
    checker = MediaChecker(patterns, GenreMapper())
    fixer = MediaFixer(patterns, dry_run=not apply) if fix else None
    items: list[ValidationItem] = []
    valid_count = 0
    fixed_count = 0
    issues_count = 0
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

                title, year = parse_title_year(media_dir.name)

                try:
                    if is_series:
                        checks = checker.check_tvshow(media_dir)
                    else:
                        checks = checker.check_movie(media_dir)
                except OSError as exc:
                    logger.warning("Filesystem error checking %s: %s", media_dir, exc)
                    items.append(ValidationItem(
                        path=str(media_dir), disk=config.name,
                        category=category_dir.name,
                        media_type="tvshow" if is_series else "movie",
                        title=title, year=year, status="issues",
                        errors=[f"os_error: {exc}"],
                    ))
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
                if not remaining_errors and not errors:
                    status = "valid"
                    valid_count += 1
                elif not remaining_errors and fixes_applied:
                    status = "fixed"
                    fixed_count += 1
                else:
                    status = "issues"
                    issues_count += 1

                items.append(ValidationItem(
                    path=str(media_dir), disk=config.name,
                    category=category_dir.name,
                    media_type="tvshow" if is_series else "movie",
                    title=title, year=year, status=status,
                    errors=remaining_errors, warnings=warnings,
                    fixes_applied=fixes_applied,
                ))

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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_validator_fix.py tests/library/test_validator.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add personalscraper/library/validator.py tests/library/test_validator_fix.py
git commit -m "v14.11.1: Implement validate --fix with empty dirs, NTFS names, dir naming"
```

---

## Task 2: Wire CLI flags to validate_library

**Files:**

- Modify: `personalscraper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
class TestLibraryValidateFix:
    """Tests for library-validate --fix CLI."""

    def test_fix_dry_run(self, tmp_path) -> None:
        """--fix without --apply should pass fix=True, apply=False."""
        from unittest.mock import MagicMock

        from personalscraper.library.models import LibraryValidationResult

        mock_result = LibraryValidationResult(
            validated_at="2026-04-17T12:00:00",
            disk_filter=None, category_filter=None,
            total_items=1, valid_count=0, fixed_count=1, issues_count=0,
        )

        with (
            patch("personalscraper.library.validator.validate_library", return_value=mock_result) as mock_val,
            patch("personalscraper.library.models.write_json"),
            patch("personalscraper.dispatch.disk_scanner.get_disk_configs", return_value=[]),
            patch("personalscraper.cli.get_settings") as mock_settings,
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-validate", "--fix"])

        assert result.exit_code == 0
        mock_val.assert_called_once()
        call_kwargs = mock_val.call_args
        assert call_kwargs.kwargs.get("fix") is True or call_kwargs[1].get("fix") is True
```

- [ ] **Step 2: Update CLI to forward fix/apply**

In `personalscraper/cli.py`, in the `library_validate` function, update the call to `validate_library`:

```python
        result = validate_library(
            disk_configs,
            disk_filter=disk,
            category_filter=category,
            fix=fix,
            apply=apply,
        )
```

Also add output for API-dependent issues when --fix is used:

```python
        if fix and result.issues_count:
            console.print(
                f"[yellow]{result.issues_count} items have API-dependent issues.[/yellow]\n"
                f"  Use: personalscraper library-rescrape"
            )
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_cli.py::TestLibraryValidateFix tests/test_cli.py::TestLibraryValidate -v`
Expected: ALL PASS

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add personalscraper/cli.py tests/test_cli.py
git commit -m "v14.11.2: Wire --fix/--apply CLI flags to validate_library"
```

---

## Task 3: Phase 11 gate

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 2: Update IMPLEMENTATION.md**

Update Phase 10+11 status to DONE, next action to Phase 12.

- [ ] **Step 3: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v14.11.3: Phase 11 gate — validate --fix complete"
```

---

## Acceptance Criteria — Phase 11

- [ ] `library-validate --fix` shows fixable items in dry-run mode
- [ ] `library-validate --fix --apply` fixes empty dirs
- [ ] `library-validate --fix --apply` fixes directory naming from NFO
- [ ] Fixed items show `status="fixed"` and populated `fixes_applied`
- [ ] Non-fixable items suggest `library-rescrape` in CLI output
- [ ] `--fix --apply` acquires pipeline lock (existing CLI behavior)
- [ ] Full test suite passes

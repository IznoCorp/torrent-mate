# Phase 4: Validator — library-validate command

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `personalscraper library-validate` — validate NFO, artwork, naming, structure conformity of existing library items. Optional `--fix --apply` for automatic corrections. Outputs `library_validation.json`.

**Architecture:** `validator.py` wraps existing `verify/checker.py` checks (`check_movie()`, `check_tvshow()`) and `verify/fixer.py` for fixes. Operates on storage disks (not staging). Distinction with `enforce`: enforce = staging area (A TRIER/), validate = library (Disk1-4).

**Tech Stack:** Python, Typer, pytest

---

## Task 1: Implement validation result model

**Files:**

- Modify: `personalscraper/library/models.py`
- Modify: `tests/library/test_models.py`

- [ ] **Step 1: Write failing test**

Add to `tests/library/test_models.py`:

```python
from personalscraper.library.models import (
    ValidationItem,
    LibraryValidationResult,
)


class TestValidationItem:
    """Tests for ValidationItem model."""

    def test_valid_item(self) -> None:
        """Item with all checks passed."""
        item = ValidationItem(
            path="/tmp/Movie (2024)", disk="Disk1", category="films",
            media_type="movie", title="Movie", year=2024,
            status="valid", errors=[], warnings=[], fixes_applied=[],
        )
        assert item.status == "valid"

    def test_blocked_item(self) -> None:
        """Item with errors should be blocked."""
        item = ValidationItem(
            path="/tmp/Movie", disk="Disk1", category="films",
            media_type="movie", title="Movie", year=None,
            status="blocked",
            errors=["nfo_missing", "bad_dir_naming"],
            warnings=["no_landscape"],
            fixes_applied=[],
        )
        assert item.status == "blocked"
        assert len(item.errors) == 2
```

- [ ] **Step 2: Implement ValidationItem and container**

Add to `personalscraper/library/models.py`:

```python
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
        status: "valid", "fixed", or "blocked".
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


@dataclass
class LibraryValidationResult:
    """Top-level container for library_validation.json."""

    validated_at: str
    disk_filter: str | None
    category_filter: str | None
    total_items: int
    valid_count: int
    fixed_count: int
    blocked_count: int
    items: list[ValidationItem] = field(default_factory=list)
```

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/library/test_models.py -v`
Expected: ALL PASS

```bash
git add personalscraper/library/models.py tests/library/test_models.py
git commit -m "v14.4.1: Add ValidationItem and LibraryValidationResult models"
```

---

## Task 2: Implement validator core logic

**Files:**

- Create: `personalscraper/library/validator.py`
- Create: `tests/library/test_validator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/library/test_validator.py
"""Tests for personalscraper.library.validator — library validation."""

from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.library.validator import validate_library


class TestValidateLibrary:
    """Tests for validate_library function."""

    def _make_config(self, path: Path, name: str, categories: list[str]):
        config = MagicMock()
        config.path = path
        config.name = name
        config.categories = categories
        return config

    def test_valid_movie(self, tmp_path: Path) -> None:
        """Complete movie should be marked valid."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Test (2024)"
        movie.mkdir(parents=True)
        (movie / "Test.mkv").write_bytes(b"\x00" * 200_000_000)  # 200 MB
        (movie / "Test.nfo").write_text(
            '<movie><title>Test</title><year>2024</year>'
            '<uniqueid type="tmdb">1</uniqueid></movie>'
        )
        (movie / "Test-poster.jpg").write_bytes(b"\x00" * 100)

        config = self._make_config(disk, "Disk1", ["films"])
        result = validate_library([config])

        assert result.total_items == 1
        assert result.valid_count == 1
        assert result.items[0].status == "valid"

    def test_missing_nfo_blocked(self, tmp_path: Path) -> None:
        """Movie without NFO should be blocked."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "NoNfo (2024)"
        movie.mkdir(parents=True)
        (movie / "NoNfo.mkv").write_bytes(b"\x00" * 200_000_000)

        config = self._make_config(disk, "Disk1", ["films"])
        result = validate_library([config])

        assert result.blocked_count == 1
        assert "nfo_present" in result.items[0].errors

    def test_disk_filter(self, tmp_path: Path) -> None:
        """Disk filter should limit validation."""
        d1 = tmp_path / "d1" / "medias"
        d2 = tmp_path / "d2" / "medias"
        (d1 / "films" / "A (2024)").mkdir(parents=True)
        (d2 / "films" / "B (2024)").mkdir(parents=True)
        (d1 / "films" / "A (2024)" / "A.mkv").write_bytes(b"\x00" * 200_000_000)
        (d2 / "films" / "B (2024)" / "B.mkv").write_bytes(b"\x00" * 200_000_000)

        configs = [
            self._make_config(d1, "Disk1", ["films"]),
            self._make_config(d2, "Disk2", ["films"]),
        ]
        result = validate_library(configs, disk_filter="Disk1")

        assert result.total_items == 1
```

- [ ] **Step 2: Implement validator.py**

```python
# personalscraper/library/validator.py
"""Library validator — check NFO, artwork, naming, structure conformity.

Wraps existing verify/checker.py checks for use on storage disks.
Distinction with enforce: enforce = staging (A TRIER/), validate = library (Disk1-4).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from personalscraper.library.models import (
    LibraryValidationResult,
    ValidationItem,
)
from personalscraper.library.scanner import _parse_title_year, _SERIES_CATEGORIES
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
    checker = MediaChecker(NamingPatterns())
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
                except OSError as exc:
                    logger.warning("Error checking %s: %s", media_dir, exc)
                    items.append(ValidationItem(
                        path=str(media_dir), disk=config.name,
                        category=category_dir.name, media_type="tvshow" if is_series else "movie",
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
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/library/test_validator.py -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add personalscraper/library/validator.py tests/library/test_validator.py
git commit -m "v14.4.2: Implement validate_library with checker integration"
```

---

## Task 3: Add library-validate CLI command

**Files:**

- Modify: `personalscraper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
class TestLibraryValidate:
    """Tests for library-validate CLI command."""

    def test_help(self, runner) -> None:
        result = runner.invoke(app, ["library-validate", "--help"])
        assert result.exit_code == 0
        assert "--disk" in result.output
        assert "--level" in result.output
        assert "--fix" in result.output
```

- [ ] **Step 2: Add command to cli.py**

```python
@app.command()
@handle_cli_errors
def library_validate(
    disk: str = typer.Option(None, "--disk", help="Validate only this disk"),
    category: str = typer.Option(None, "--category", help="Validate only this category"),
    level: str = typer.Option("full", "--level", help="Validation level: quick or full"),
    fix: bool = typer.Option(False, "--fix", help="Attempt automatic fixes"),
    apply: bool = typer.Option(False, "--apply", help="Apply fixes (requires --fix)"),
) -> None:
    """Validate NFO, artwork, naming conformity of library items.

    Checks each media item on storage disks against quality rules.
    Use --fix --apply to attempt automatic corrections.

    Examples:
        personalscraper library-validate
        personalscraper library-validate --disk Disk1 --level quick
        personalscraper library-validate --fix --apply
    """
    from personalscraper.library.models import write_json
    from personalscraper.library.validator import validate_library

    console = state["console"]
    settings = get_settings()

    if apply and not fix:
        console.print("[red]--apply requires --fix[/red]")
        raise typer.Exit(1)

    if fix and apply:
        if not acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        console.print("[bold]Validating library...[/bold]")
        result = validate_library(
            settings.disk_configs,
            disk_filter=disk,
            category_filter=category,
            level=level,
        )

        output_path = settings.data_dir / "library_validation.json"
        write_json(result, output_path)

        console.print(
            f"[green]Valid:[/green] {result.valid_count}  "
            f"[yellow]Fixed:[/yellow] {result.fixed_count}  "
            f"[red]Blocked:[/red] {result.blocked_count}  "
            f"→ {output_path}"
        )
    finally:
        if fix and apply:
            release_lock()
```

- [ ] **Step 3: Run tests and commit**

Run: `python -m pytest tests/test_cli.py::TestLibraryValidate tests/library/ -v`
Expected: ALL PASS

```bash
git add personalscraper/cli.py personalscraper/library/validator.py tests/
git commit -m "v14.4.3: Add library-validate CLI with quick/full levels"
```

---

## Acceptance Criteria — Phase 4

- [ ] `personalscraper library-validate --help` shows --disk, --category, --level, --fix, --apply
- [ ] Valid movies/shows marked "valid", missing-NFO items marked "blocked"
- [ ] Disk and category filters work
- [ ] `--fix --apply` acquires lock, `--apply` without `--fix` errors
- [ ] `library_validation.json` written to `.personalscraper/`
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`

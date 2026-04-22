# Phase 3: Disk Cleaner — library-clean command

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `personalscraper library-clean` — remove .actors/, empty dirs, junk files, release-group artifacts. Dry-run by default, `--apply` to execute. NTFS-safe error handling.

**Architecture:** `disk_cleaner.py` iterates storage disks, identifies cleanup targets, reports or deletes. Acquires pipeline lock when `--apply` is used.

**Tech Stack:** Python, Typer, shutil, pytest

---

## Task 1: Implement cleaner core logic

**Files:**

- Create: `personalscraper/library/disk_cleaner.py`
- Create: `tests/library/test_disk_cleaner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/library/test_disk_cleaner.py
"""Tests for personalscraper.library.disk_cleaner — library cleanup."""

from pathlib import Path

from personalscraper.library.disk_cleaner import (
    CleanResult,
    clean_library,
)


class TestCleanActors:
    """Tests for .actors/ directory removal."""

    def test_actors_removed_on_apply(self, tmp_path: Path) -> None:
        """--apply should delete .actors/ directories."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        actors = movie / ".actors"
        actors.mkdir(parents=True)
        (actors / "Actor.jpg").write_bytes(b"\x00" * 100)

        config = _make_config(disk, "Disk1", ["films"])
        result = clean_library([config], apply=True, only="actors")

        assert not actors.exists()
        assert result.deleted_count > 0

    def test_actors_kept_on_dry_run(self, tmp_path: Path) -> None:
        """Dry-run should NOT delete .actors/ directories."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        actors = movie / ".actors"
        actors.mkdir(parents=True)
        (actors / "Actor.jpg").write_bytes(b"\x00" * 100)

        config = _make_config(disk, "Disk1", ["films"])
        result = clean_library([config], apply=False, only="actors")

        assert actors.exists()
        assert result.deleted_count > 0  # counted but not deleted
        assert result.dry_run is True

    def test_ntfs_error_continues(self, tmp_path: Path, monkeypatch) -> None:
        """NTFS deletion failure should log error and continue."""
        import shutil
        disk = tmp_path / "medias"
        movie1 = disk / "films" / "Movie1 (2024)" / ".actors"
        movie2 = disk / "films" / "Movie2 (2024)" / ".actors"
        movie1.mkdir(parents=True)
        movie2.mkdir(parents=True)
        (movie1 / "a.jpg").write_bytes(b"\x00")
        (movie2 / "b.jpg").write_bytes(b"\x00")

        call_count = 0
        original_rmtree = shutil.rmtree

        def flaky_rmtree(path, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("NTFS permission denied")
            original_rmtree(path, *args, **kwargs)

        monkeypatch.setattr(shutil, "rmtree", flaky_rmtree)

        config = _make_config(disk, "Disk1", ["films"])
        result = clean_library([config], apply=True, only="actors")

        # First deletion failed, second succeeded
        assert result.error_count == 1
        assert result.deleted_count == 1


class TestCleanEmpty:
    """Tests for empty directory removal."""

    def test_empty_dirs_removed(self, tmp_path: Path) -> None:
        """Empty directories should be removed on apply."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.mkv").write_bytes(b"\x00" * 1000)
        empty = movie / "Subs"
        empty.mkdir()

        config = _make_config(disk, "Disk1", ["films"])
        result = clean_library([config], apply=True, only="empty")

        assert not empty.exists()
        assert movie.exists()  # parent not deleted

    def test_release_group_empty_dirs_removed(self, tmp_path: Path) -> None:
        """Empty release-group artifact directories should be removed."""
        disk = tmp_path / "medias"
        show = disk / "series" / "Show (2024)"
        show.mkdir(parents=True)
        (show / "tvshow.nfo").write_text("<tvshow/>")
        artifact = show / "Show.S01E01.1080p.WEB-DL.H264-GROUP"
        artifact.mkdir()  # empty

        config = _make_config(disk, "Disk1", ["series"])
        result = clean_library([config], apply=True, only="release")

        assert not artifact.exists()


class TestCleanJunk:
    """Tests for junk file removal."""

    def test_ds_store_removed(self, tmp_path: Path) -> None:
        """.DS_Store should be removed on apply."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.mkv").write_bytes(b"\x00" * 1000)
        ds = movie / ".DS_Store"
        ds.write_bytes(b"\x00")

        config = _make_config(disk, "Disk1", ["films"])
        result = clean_library([config], apply=True, only="junk")

        assert not ds.exists()
        assert result.deleted_count == 1

    def test_thumbs_db_and_desktop_ini(self, tmp_path: Path) -> None:
        """Thumbs.db and desktop.ini should be removed."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.mkv").write_bytes(b"\x00")
        (movie / "Thumbs.db").write_bytes(b"\x00")
        (movie / "desktop.ini").write_text("[ViewState]")

        config = _make_config(disk, "Disk1", ["films"])
        result = clean_library([config], apply=True, only="junk")

        assert not (movie / "Thumbs.db").exists()
        assert not (movie / "desktop.ini").exists()
        assert result.deleted_count == 2


class TestCleanAll:
    """Tests for full cleanup (no --only filter)."""

    def test_all_targets_cleaned(self, tmp_path: Path) -> None:
        """Without --only, all cleanup targets should be processed."""
        disk = tmp_path / "medias"
        movie = disk / "films" / "Movie (2024)"
        movie.mkdir(parents=True)
        (movie / "movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / ".actors").mkdir()
        (movie / ".actors" / "a.jpg").write_bytes(b"\x00")
        (movie / ".DS_Store").write_bytes(b"\x00")
        (movie / "empty_dir").mkdir()

        config = _make_config(disk, "Disk1", ["films"])
        result = clean_library([config], apply=True, only=None)

        assert not (movie / ".actors").exists()
        assert not (movie / ".DS_Store").exists()
        assert not (movie / "empty_dir").exists()
        assert result.deleted_count == 3

    def test_disk_filter(self, tmp_path: Path) -> None:
        """Disk filter should limit cleanup to one disk."""
        disk1 = tmp_path / "d1" / "medias"
        disk2 = tmp_path / "d2" / "medias"
        m1 = disk1 / "films" / "M1 (2024)"
        m2 = disk2 / "films" / "M2 (2024)"
        m1.mkdir(parents=True)
        m2.mkdir(parents=True)
        (m1 / ".actors").mkdir()
        (m2 / ".actors").mkdir()

        configs = [
            _make_config(disk1, "Disk1", ["films"]),
            _make_config(disk2, "Disk2", ["films"]),
        ]
        result = clean_library(configs, apply=True, only="actors", disk_filter="Disk1")

        assert not (m1 / ".actors").exists()
        assert (m2 / ".actors").exists()  # untouched


def _make_config(path: Path, name: str, categories: list[str]):
    """Create a mock DiskConfig."""
    from unittest.mock import MagicMock
    config = MagicMock()
    config.path = path
    config.name = name
    config.categories = categories
    return config
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/library/test_disk_cleaner.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement disk_cleaner.py**

```python
# personalscraper/library/disk_cleaner.py
"""Library disk cleaner — remove .actors/, empty dirs, junk files.

Dry-run by default. Requires --apply to actually delete.
Handles NTFS deletion failures gracefully (per-item error, continues).
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_JUNK_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})


@dataclass
class CleanResult:
    """Result of a library cleanup operation.

    Attributes:
        dry_run: Whether this was a dry-run (no actual deletions).
        deleted_count: Number of items deleted (or would-be-deleted in dry-run).
        error_count: Number of deletion failures (NTFS errors, etc.).
        freed_bytes: Approximate bytes freed (or would be freed).
        details: Per-item details (path + action).
        errors: Per-item error details (path + error message).
    """

    dry_run: bool = True
    deleted_count: int = 0
    error_count: int = 0
    freed_bytes: int = 0
    details: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _dir_size(path: Path) -> int:
    """Calculate total byte size of a directory recursively."""
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return total


def _delete_dir(path: Path, result: CleanResult, dry_run: bool, label: str) -> None:
    """Delete a directory, handling NTFS errors gracefully.

    Args:
        path: Directory to delete.
        result: CleanResult to update.
        dry_run: If True, only count without deleting.
        label: Human label for logging (e.g. ".actors", "empty dir").
    """
    size = _dir_size(path)
    if dry_run:
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"[DRY-RUN] Would delete {label}: {path} ({size} bytes)")
        return

    try:
        shutil.rmtree(path)
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"Deleted {label}: {path} ({size} bytes)")
        logger.info("Deleted %s: %s", label, path)
    except OSError as exc:
        result.error_count += 1
        result.errors.append(f"Failed to delete {label}: {path} — {exc}")
        logger.warning("NTFS deletion failed for %s: %s — %s", label, path, exc)


def _delete_file(path: Path, result: CleanResult, dry_run: bool, label: str) -> None:
    """Delete a single file, handling errors gracefully.

    Args:
        path: File to delete.
        result: CleanResult to update.
        dry_run: If True, only count without deleting.
        label: Human label for logging.
    """
    try:
        size = path.stat().st_size
    except OSError:
        size = 0

    if dry_run:
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"[DRY-RUN] Would delete {label}: {path}")
        return

    try:
        path.unlink()
        result.deleted_count += 1
        result.freed_bytes += size
        result.details.append(f"Deleted {label}: {path}")
    except OSError as exc:
        result.error_count += 1
        result.errors.append(f"Failed to delete {label}: {path} — {exc}")
        logger.warning("Deletion failed for %s: %s — %s", label, path, exc)


def _is_effectively_empty(directory: Path) -> bool:
    """Check if a directory is empty or contains only junk files."""
    try:
        for item in directory.iterdir():
            if item.name not in _JUNK_FILES:
                return False
        return True
    except OSError:
        return False


def clean_library(
    disk_configs: list,
    apply: bool = False,
    only: str | None = None,
    disk_filter: str | None = None,
    category_filter: str | None = None,
) -> CleanResult:
    """Clean the media library across storage disks.

    Dry-run by default — set apply=True to actually delete.

    Args:
        disk_configs: List of DiskConfig objects from Settings.
        apply: If True, actually delete files. If False, only report.
        only: Filter cleanup type: "actors", "empty", "junk", "release", or None (all).
        disk_filter: Only clean this disk. None = all.
        category_filter: Only clean this category. None = all.

    Returns:
        CleanResult with counts and details.
    """
    result = CleanResult(dry_run=not apply)

    clean_actors = only in (None, "actors")
    clean_empty = only in (None, "empty")
    clean_junk = only in (None, "junk")
    clean_release = only in (None, "release")

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

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                _clean_media_dir(
                    media_dir, result, not apply,
                    clean_actors, clean_empty, clean_junk, clean_release,
                )

    return result


def _clean_media_dir(
    media_dir: Path,
    result: CleanResult,
    dry_run: bool,
    clean_actors: bool,
    clean_empty: bool,
    clean_junk: bool,
    clean_release: bool,
) -> None:
    """Clean a single media directory.

    Args:
        media_dir: Path to media directory.
        result: CleanResult to update.
        dry_run: If True, only count.
        clean_actors: Whether to remove .actors/.
        clean_empty: Whether to remove empty dirs.
        clean_junk: Whether to remove junk files.
        clean_release: Whether to remove release-group artifacts.
    """
    try:
        entries = list(media_dir.iterdir())
    except OSError:
        return

    for item in entries:
        name = item.name

        # .actors directory
        if clean_actors and name == ".actors" and item.is_dir():
            _delete_dir(item, result, dry_run, ".actors")
            continue

        # Junk files
        if clean_junk and name in _JUNK_FILES and item.is_file():
            _delete_file(item, result, dry_run, "junk file")
            continue

        # Empty directories and release-group artifacts
        if item.is_dir() and _is_effectively_empty(item):
            # Detect release-group style names (contain dots + group suffix)
            is_release = "." in name and any(
                c.isupper() for c in name.split(".")[-1] if c.isalpha()
            )
            if clean_release and is_release:
                _delete_dir(item, result, dry_run, "release artifact")
            elif clean_empty and not is_release:
                _delete_dir(item, result, dry_run, "empty dir")
            elif clean_empty and is_release:
                # --only empty also catches release artifacts
                _delete_dir(item, result, dry_run, "empty dir")

    # Also check subdirs recursively (e.g. empty Saison dirs)
    try:
        for subdir in media_dir.iterdir():
            if subdir.is_dir() and subdir.name != ".actors":
                for nested in subdir.iterdir():
                    if (
                        nested.is_dir()
                        and _is_effectively_empty(nested)
                        and clean_empty
                    ):
                        _delete_dir(nested, result, dry_run, "empty nested dir")
    except OSError:
        pass
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_disk_cleaner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add personalscraper/library/disk_cleaner.py tests/library/test_disk_cleaner.py
git commit -m "v14.3.1: Implement disk_cleaner with NTFS error handling"
```

---

## Task 2: Add library-clean CLI command

**Files:**

- Modify: `personalscraper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
class TestLibraryClean:
    """Tests for library-clean CLI command."""

    def test_help(self, runner) -> None:
        """library-clean --help should display usage."""
        result = runner.invoke(app, ["library-clean", "--help"])
        assert result.exit_code == 0
        assert "--apply" in result.output
        assert "--only" in result.output
        assert "--disk" in result.output

    def test_dry_run_by_default(self, runner, monkeypatch) -> None:
        """library-clean without --apply should be dry-run."""
        from unittest.mock import patch, MagicMock
        from personalscraper.library.disk_cleaner import CleanResult

        mock_result = CleanResult(dry_run=True, deleted_count=5, freed_bytes=1024)

        with (
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.library.disk_cleaner.clean_library", return_value=mock_result),
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-clean"])

        assert result.exit_code == 0
        assert "DRY-RUN" in result.output or "dry" in result.output.lower()

    def test_apply_acquires_lock(self, runner, monkeypatch) -> None:
        """library-clean --apply should acquire pipeline lock."""
        from unittest.mock import patch, MagicMock
        from personalscraper.library.disk_cleaner import CleanResult

        mock_result = CleanResult(dry_run=False, deleted_count=0)

        with (
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.library.disk_cleaner.clean_library", return_value=mock_result),
            patch("personalscraper.cli.acquire_lock", return_value=True) as mock_lock,
            patch("personalscraper.cli.release_lock"),
        ):
            settings = MagicMock()
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-clean", "--apply"])

        mock_lock.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::TestLibraryClean -v`
Expected: FAIL — command not registered

- [ ] **Step 3: Add library-clean command to cli.py**

Add to `personalscraper/cli.py`:

```python
@app.command()
@handle_cli_errors
def library_clean(
    apply: bool = typer.Option(False, "--apply", help="Actually delete (default: dry-run)"),
    only: str = typer.Option(None, "--only", help="Only clean: actors, empty, junk, release"),
    disk: str = typer.Option(None, "--disk", help="Clean only this disk (Disk1-4)"),
    category: str = typer.Option(None, "--category", help="Clean only this category"),
) -> None:
    """Remove .actors/, empty dirs, junk files from storage disks.

    Dry-run by default — shows what would be deleted without deleting.
    Use --apply to actually execute deletions.
    Use --only to target specific cleanup types.

    Examples:
        personalscraper library-clean                     # Dry-run everything
        personalscraper library-clean --apply             # Delete everything
        personalscraper library-clean --apply --only actors  # Only .actors/
        personalscraper library-clean --disk Disk1        # Only Disk1
    """
    from personalscraper.dispatch.disk_scanner import get_disk_configs
    from personalscraper.library.disk_cleaner import clean_library

    console = state["console"]
    settings = get_settings()
    disk_configs = get_disk_configs(settings)

    # Acquire lock only when applying changes
    if apply:
        if not acquire_lock():
            console.print("[red]Another instance is running. Exiting.[/red]")
            raise typer.Exit(1)

    try:
        mode = "[bold red]APPLY[/bold red]" if apply else "[bold yellow]DRY-RUN[/bold yellow]"
        console.print(f"[bold]Cleaning library ({mode})...[/bold]")

        result = clean_library(
            disk_configs,
            apply=apply,
            only=only,
            disk_filter=disk,
            category_filter=category,
        )

        if result.dry_run:
            console.print(
                f"[yellow]DRY-RUN:[/yellow] Would delete {result.deleted_count} items "
                f"({result.freed_bytes / 1024 / 1024:.1f} MB)"
            )
        else:
            console.print(
                f"[green]Deleted:[/green] {result.deleted_count} items "
                f"({result.freed_bytes / 1024 / 1024:.1f} MB freed)"
            )
            if result.error_count:
                console.print(
                    f"[red]Errors:[/red] {result.error_count} deletions failed (NTFS)"
                )
                for err in result.errors:
                    console.print(f"  {err}")
    finally:
        if apply:
            release_lock()
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_cli.py::TestLibraryClean -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/cli.py tests/test_cli.py
git commit -m "v14.3.2: Add library-clean CLI command with dry-run/apply/lock"
```

---

## Acceptance Criteria — Phase 3

Before moving to Phase 4, verify:

- [ ] `personalscraper library-clean --help` shows --apply, --only, --disk, --category
- [ ] Dry-run by default: no files deleted without --apply
- [ ] `--apply` acquires pipeline lock
- [ ] `.actors/`, empty dirs, junk files, release artifacts all cleaned
- [ ] NTFS deletion errors are caught per-item, reported, and don't crash the command
- [ ] Disk and category filters work
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`

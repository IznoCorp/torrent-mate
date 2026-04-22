# Phase 1: sanitize_filename cohérent (bugs #3,4,5,9,10,13,16)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Ensure all generated filenames are NTFS-safe. Clean stale files after folder rename. Apply sanitize_filename in reclean.

**Architecture:** New `_cleanup_stale_files()` in scraper.py + sanitize_filename in reclean.py.

**Tech Stack:** Python, pytest

---

## Task 1: Write reproducer test for stale artwork files after rename

**Files:**

- Modify: `tests/scraper/test_scraper.py`

- [ ] **Step 1: Write failing test**

Add to `tests/scraper/test_scraper.py`:

```python
class TestCleanupStaleFiles:
    """Tests for _cleanup_stale_files after folder rename."""

    def test_old_artwork_with_colon_removed_after_rename(self, tmp_path: Path) -> None:
        """Old artwork files with ':' should be deleted when sanitized versions exist."""
        movie_dir = tmp_path / "Title Subtitle (2025)"
        movie_dir.mkdir()

        # Old files (from previous scrape, with colon)
        (movie_dir / "Title : Subtitle-poster.jpg").write_bytes(b"old_poster")
        (movie_dir / "Title : Subtitle-landscape.jpg").write_bytes(b"old_landscape")
        (movie_dir / "Title : Subtitle.nfo").write_bytes(b"old_nfo")

        # New files (from current scrape, sanitized)
        (movie_dir / "Title Subtitle-poster.jpg").write_bytes(b"new_poster")
        (movie_dir / "Title Subtitle-landscape.jpg").write_bytes(b"new_landscape")
        (movie_dir / "Title Subtitle.nfo").write_bytes(b"new_nfo")

        # Video file (should NOT be touched)
        (movie_dir / "Title Subtitle.mkv").write_bytes(b"video")

        from personalscraper.scraper.scraper import _cleanup_stale_files
        _cleanup_stale_files(movie_dir, "Title : Subtitle", "Title Subtitle")

        # Old files should be gone
        assert not (movie_dir / "Title : Subtitle-poster.jpg").exists()
        assert not (movie_dir / "Title : Subtitle-landscape.jpg").exists()
        assert not (movie_dir / "Title : Subtitle.nfo").exists()

        # New files should remain
        assert (movie_dir / "Title Subtitle-poster.jpg").exists()
        assert (movie_dir / "Title Subtitle-landscape.jpg").exists()
        assert (movie_dir / "Title Subtitle.nfo").exists()

        # Video untouched
        assert (movie_dir / "Title Subtitle.mkv").exists()

    def test_no_deletion_when_no_sanitized_duplicate(self, tmp_path: Path) -> None:
        """Old files should NOT be deleted if no sanitized equivalent exists."""
        movie_dir = tmp_path / "Title Subtitle (2025)"
        movie_dir.mkdir()

        # Only old file, no new equivalent
        (movie_dir / "Title : Subtitle-poster.jpg").write_bytes(b"old_poster")

        from personalscraper.scraper.scraper import _cleanup_stale_files
        _cleanup_stale_files(movie_dir, "Title : Subtitle", "Title Subtitle")

        # Should NOT be deleted (no replacement exists)
        assert (movie_dir / "Title : Subtitle-poster.jpg").exists()

    def test_no_crash_on_empty_directory(self, tmp_path: Path) -> None:
        """Should handle empty directories without error."""
        movie_dir = tmp_path / "Empty (2025)"
        movie_dir.mkdir()

        from personalscraper.scraper.scraper import _cleanup_stale_files
        _cleanup_stale_files(movie_dir, "Old Name", "New Name")  # No crash
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/scraper/test_scraper.py::TestCleanupStaleFiles -v`
Expected: FAIL — `ImportError: cannot import name '_cleanup_stale_files'`

- [ ] **Step 3: Commit**

```bash
git add tests/scraper/test_scraper.py
git commit -m "v12.1.1: Add failing tests for stale artwork cleanup after rename"
```

## Task 2: Implement \_cleanup_stale_files

**Files:**

- Modify: `personalscraper/scraper/scraper.py`

- [ ] **Step 1: Add \_cleanup_stale_files function**

Add after `_find_video_file()` (around line 212) in `personalscraper/scraper/scraper.py`:

```python
def _cleanup_stale_files(directory: Path, old_prefix: str, new_prefix: str) -> int:
    """Remove stale files with old title prefix when sanitized versions exist.

    After a folder rename (e.g., stripping ':'), old artwork/NFO files
    may remain alongside the new sanitized versions. This function removes
    the old duplicates only when a corresponding new file exists.

    Args:
        directory: Directory to scan for stale files.
        old_prefix: The old title prefix (e.g., "Title : Subtitle").
        new_prefix: The new sanitized prefix (e.g., "Title Subtitle").

    Returns:
        Number of stale files removed.
    """
    if old_prefix == new_prefix:
        return 0

    removed = 0
    for f in list(directory.iterdir()):
        if not f.is_file() or not f.name.startswith(old_prefix):
            continue
        # Build the expected sanitized equivalent
        new_name = new_prefix + f.name[len(old_prefix):]
        if (directory / new_name).exists():
            try:
                f.unlink()
                logger.info("Cleaned stale file: %s", f.name)
                removed += 1
            except OSError as exc:
                logger.warning("Cannot remove stale file %s: %s", f.name, exc)
    return removed
```

- [ ] **Step 2: Call \_cleanup_stale_files after movie rename**

In `scrape_movie()`, after `movie_dir = new_path` (line 534), add:

```python
                    movie_dir = new_path
                    result.media_path = new_path
                    # Clean stale artwork/NFO from before rename
                    old_name = movie_dir.name  # This is already new_path.name
                    _cleanup_stale_files(movie_dir, title, resolved_title)
```

Wait — the old title is in `movie_dir.name` BEFORE rename (the original `title` variable). The new title is `resolved_title` which gets sanitized via `clean_name`. Let me be more precise:

Before the rename block (line 519), save the old prefix:

```python
        old_dir_name = movie_dir.name  # Save before potential rename
        if movie_dir.name != clean_name:
            ...
                    movie_dir = new_path
                    result.media_path = new_path
                    _cleanup_stale_files(movie_dir, old_dir_name, clean_name)
```

The key: `old_dir_name` is the folder name BEFORE rename (may contain `:`), `clean_name` is the sanitized name AFTER rename.

- [ ] **Step 3: Call \_cleanup_stale_files after tvshow rename**

In `scrape_tvshow()`, same pattern around line 776:

```python
        old_dir_name = show_dir.name
        if show_dir.name != canonical:
            ...
                    show_dir = new_dir
                    _cleanup_stale_files(show_dir, old_dir_name, canonical)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/scraper/test_scraper.py::TestCleanupStaleFiles -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass, 0 failures

- [ ] **Step 6: Commit**

```bash
git add personalscraper/scraper/scraper.py
git commit -m "v12.1.2: Add _cleanup_stale_files and call after movie/tvshow rename"
```

## Task 3: Write reproducer test for reclean sanitize_filename

**Files:**

- Modify: `tests/process/test_reclean.py`

- [ ] **Step 1: Write failing test**

```python
def test_reclean_removes_colon_from_folder_name(tmp_path: Path) -> None:
    """Reclean should sanitize folder names — colons must be stripped."""
    category_dir = tmp_path / "001-MOVIES"
    category_dir.mkdir()

    # Create a folder with colon (as guessit might produce from French TMDB title)
    dirty = category_dir / "Title : Subtitle.2025.1080p.BluRay"
    dirty.mkdir()
    (dirty / "video.mkv").write_bytes(b"\x00" * 1000)

    from personalscraper.process.reclean import reclean_category
    from personalscraper.models import StepReport

    report = StepReport(name="reclean")
    reclean_category(category_dir, dry_run=False, report=report)

    # The colon should be gone from the resulting folder name
    result_dirs = [d.name for d in category_dir.iterdir() if d.is_dir()]
    for name in result_dirs:
        assert ":" not in name, f"Colon found in folder name: {name}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/process/test_reclean.py::test_reclean_removes_colon_from_folder_name -v`
Expected: FAIL — folder name still contains `:`

- [ ] **Step 3: Commit**

```bash
git add tests/process/test_reclean.py
git commit -m "v12.1.3: Add failing test for reclean colon sanitization"
```

## Task 4: Apply sanitize_filename in reclean.py

**Files:**

- Modify: `personalscraper/process/reclean.py:126`

- [ ] **Step 1: Add import and apply sanitize_filename**

Add import at the top of `reclean.py`:

```python
from personalscraper.text_utils import sanitize_filename
```

Change line 126 from:

```python
        clean_name = _format_clean_name(title, year)
```

To:

```python
        clean_name = sanitize_filename(_format_clean_name(title, year))
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/process/test_reclean.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add personalscraper/process/reclean.py
git commit -m "v12.1.4: Apply sanitize_filename in reclean _format_clean_name"
```

## Task 5: Update IMPLEMENTATION.md

- [ ] **Step 1: Add V12 section, mark Phase 1 complete**
- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v12.1.5: Update IMPLEMENTATION.md — Phase 1 complete"
```

# Phase 5: Verify/Dispatch NTFS-safe (bugs #18, #19)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Block items with NTFS-illegal characters at verify stage. Pre-scan in dispatch as safety net.

**Architecture:** New `ntfs_safe_names` check in checker.py. New `_has_ntfs_illegal_names()` guard in dispatcher.py.

**Tech Stack:** Python, pytest

---

## Task 1: Write reproducer tests for verify NTFS check

**Files:**

- Modify: `tests/verify/test_checker.py`

- [ ] **Step 1: Write failing tests**

```python
class TestNtfsSafeNames:
    """Tests for NTFS-illegal character detection in verify checker."""

    def test_colon_in_artwork_fails_check(self, tmp_path: Path) -> None:
        """Artwork file with ':' should fail ntfs_safe_names check."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        (movie_dir / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie_dir / "Movie.nfo").write_text("<movie><title>Movie</title></movie>")
        (movie_dir / "Movie-poster.jpg").write_bytes(b"poster")
        # This file has illegal ':' character
        (movie_dir / "Movie : Special-landscape.jpg").write_bytes(b"bad")

        from personalscraper.verify.checker import MediaChecker
        checker = MediaChecker()
        results = checker.check_movie(movie_dir)

        ntfs_check = next((r for r in results if r.name == "ntfs_safe_names"), None)
        assert ntfs_check is not None, "ntfs_safe_names check should exist"
        assert ntfs_check.passed is False
        assert ":" in ntfs_check.message

    def test_clean_names_pass_check(self, tmp_path: Path) -> None:
        """Files with NTFS-safe names should pass the check."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        (movie_dir / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie_dir / "Movie.nfo").write_text("<movie><title>Movie</title></movie>")
        (movie_dir / "Movie-poster.jpg").write_bytes(b"poster")

        from personalscraper.verify.checker import MediaChecker
        checker = MediaChecker()
        results = checker.check_movie(movie_dir)

        ntfs_check = next((r for r in results if r.name == "ntfs_safe_names"), None)
        assert ntfs_check is not None
        assert ntfs_check.passed is True

    def test_tvshow_with_colon_in_nfo_fails(self, tmp_path: Path) -> None:
        """TV show with ':' in a filename should also fail."""
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text("<tvshow><title>Show</title></tvshow>")
        (show_dir / "poster.jpg").write_bytes(b"poster")
        season_dir = show_dir / "Saison 01"
        season_dir.mkdir()
        (season_dir / "S01E01 - Title.mkv").write_bytes(b"\x00" * 1000)
        # Illegal file
        (season_dir / "S01E01 : Title.nfo").write_bytes(b"bad_nfo")

        from personalscraper.verify.checker import MediaChecker
        checker = MediaChecker()
        results = checker.check_tvshow(show_dir)

        ntfs_check = next((r for r in results if r.name == "ntfs_safe_names"), None)
        assert ntfs_check is not None
        assert ntfs_check.passed is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/verify/test_checker.py::TestNtfsSafeNames -v`
Expected: FAIL — no `ntfs_safe_names` check exists

- [ ] **Step 3: Commit**

```bash
git add tests/verify/test_checker.py
git commit -m "v12.5.1: Add failing tests for NTFS-safe filename check in verify"
```

## Task 2: Implement ntfs_safe_names check in checker.py

**Files:**

- Modify: `personalscraper/verify/checker.py`

- [ ] **Step 1: Add import**

At the top of `checker.py`, add:

```python
from personalscraper.text_utils import _FILENAME_ILLEGAL
```

- [ ] **Step 2: Add \_check_ntfs_safe_names method**

Add a helper method to `MediaChecker`:

```python
    def _check_ntfs_safe_names(self, media_dir: Path) -> CheckResult:
        """Check all filenames for NTFS-illegal characters.

        Scans recursively for files containing <>:"/\\|?* in their names.
        These characters cause rsync failures on NTFS storage disks.

        Args:
            media_dir: Directory to scan.

        Returns:
            CheckResult with list of offending filenames if any.
        """
        illegal_files = []
        for f in media_dir.rglob("*"):
            if f.is_file() and _FILENAME_ILLEGAL.search(f.name):
                illegal_files.append(f.name)

        if illegal_files:
            sample = ", ".join(illegal_files[:3])
            suffix = f" (+{len(illegal_files) - 3} more)" if len(illegal_files) > 3 else ""
            message = f"NTFS-illegal filenames: {sample}{suffix}"
        else:
            message = ""

        return CheckResult(
            name="ntfs_safe_names",
            passed=len(illegal_files) == 0,
            severity=Severity.ERROR,
            message=message,
            fixable=True,
        )
```

- [ ] **Step 3: Call in check_movie and check_tvshow**

In `check_movie()`, before the `return results` (after the `category` check block), add:

```python
        # ntfs_safe_names
        results.append(self._check_ntfs_safe_names(movie_dir))
```

In `check_tvshow()`, same pattern — add before `return results`:

```python
        # ntfs_safe_names
        results.append(self._check_ntfs_safe_names(show_dir))
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/verify/test_checker.py::TestNtfsSafeNames -v`
Expected: PASS

- [ ] **Step 5: Run full verify tests**

Run: `python -m pytest tests/verify/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/verify/checker.py
git commit -m "v12.5.2: Add ntfs_safe_names check to verify — blocks files with illegal chars"
```

## Task 3: Write reproducer test for dispatch NTFS pre-scan

**Files:**

- Modify: `tests/dispatch/test_dispatcher.py`

- [ ] **Step 1: Write failing test**

```python
class TestNtfsPreScan:
    """Tests for NTFS-illegal filename pre-scan before rsync."""

    def test_item_with_colon_skipped(self, tmp_path: Path) -> None:
        """Dispatch should skip items with NTFS-illegal filenames."""
        from personalscraper.dispatch.dispatcher import Dispatcher

        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        (movie_dir / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie_dir / "Movie : Subtitle-poster.jpg").write_bytes(b"bad")

        result = Dispatcher._has_ntfs_illegal_names(movie_dir)

        assert result is True

    def test_clean_item_passes(self, tmp_path: Path) -> None:
        """Items with clean filenames should pass the pre-scan."""
        from personalscraper.dispatch.dispatcher import Dispatcher

        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        (movie_dir / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie_dir / "Movie-poster.jpg").write_bytes(b"ok")

        result = Dispatcher._has_ntfs_illegal_names(movie_dir)

        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/dispatch/test_dispatcher.py::TestNtfsPreScan -v`
Expected: FAIL — `AttributeError: type object 'Dispatcher' has no attribute '_has_ntfs_illegal_names'`

- [ ] **Step 3: Commit**

```bash
git add tests/dispatch/test_dispatcher.py
git commit -m "v12.5.3: Add failing tests for dispatch NTFS pre-scan"
```

## Task 4: Implement \_has_ntfs_illegal_names in dispatcher.py

**Files:**

- Modify: `personalscraper/dispatch/dispatcher.py`

- [ ] **Step 1: Add import**

```python
from personalscraper.text_utils import _FILENAME_ILLEGAL
```

- [ ] **Step 2: Add \_has_ntfs_illegal_names static method**

Add to `Dispatcher` class:

```python
    @staticmethod
    def _has_ntfs_illegal_names(directory: Path) -> bool:
        """Check if any file in directory has NTFS-illegal characters.

        Scans recursively for filenames containing <>:"/\\|?*.
        Used as a pre-check before rsync to NTFS disks.

        Args:
            directory: Directory to scan.

        Returns:
            True if any file has illegal characters.
        """
        for f in directory.rglob("*"):
            if f.is_file() and _FILENAME_ILLEGAL.search(f.name):
                logger.warning("NTFS-illegal filename: %s", f)
                return True
        return False
```

- [ ] **Step 3: Add pre-scan call in dispatch_movie and dispatch_tvshow**

In `dispatch_movie()`, before the rsync/replace/move operation, add:

```python
        # Pre-scan for NTFS-illegal filenames
        if self._has_ntfs_illegal_names(movie_dir):
            result.error = (
                f"NTFS-illegal filenames in {movie_dir.name}. "
                "Run 'personalscraper process' to sanitize."
            )
            logger.error("dispatch_ntfs_illegal", source=str(movie_dir))
            return result
```

Same pattern in `dispatch_tvshow()`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/dispatch/test_dispatcher.py::TestNtfsPreScan -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/dispatch/dispatcher.py
git commit -m "v12.5.4: Add NTFS pre-scan in dispatch — skip items with illegal filenames"
```

## Task 5: Update IMPLEMENTATION.md

- [ ] **Step 1: Mark Phase 5 complete**
- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v12.5.5: Update IMPLEMENTATION.md — Phase 5 complete"
```

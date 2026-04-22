# Phase 2: Restructuration épisodes (bugs #6, #7, #8)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Make `_find_video_file()` recursive and clean empty release-group subdirectories after episode rename.

**Architecture:** Rewrite `_find_video_file()` to use `rglob` + pick largest. Add empty-dir cleanup after `rename_episodes()`.

**Tech Stack:** Python, pytest

---

## Task 1: Write reproducer test for \_find_video_file with nested structure

**Files:**

- Modify: `tests/scraper/test_scraper.py`

- [ ] **Step 1: Write failing test**

```python
class TestFindVideoFileNested:
    """Tests for _find_video_file with nested torrent structures."""

    def test_finds_mkv_in_subdirectory(self, tmp_path: Path) -> None:
        """Video file in a release-group subdirectory should be found."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        release_dir = movie_dir / "Movie.2025.1080p.BluRay.x264-GROUP"
        release_dir.mkdir()
        video = release_dir / "Movie.2025.1080p.BluRay.x264-GROUP.mkv"
        video.write_bytes(b"\x00" * 1000)

        from personalscraper.scraper.scraper import _find_video_file
        result = _find_video_file(movie_dir)

        assert result is not None
        assert result == video

    def test_picks_largest_when_multiple_videos(self, tmp_path: Path) -> None:
        """When multiple video files exist, pick the largest (main feature)."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        sample = movie_dir / "Sample.mkv"
        sample.write_bytes(b"\x00" * 100)
        main = movie_dir / "sub" / "Movie.mkv"
        main.parent.mkdir()
        main.write_bytes(b"\x00" * 10000)

        from personalscraper.scraper.scraper import _find_video_file
        result = _find_video_file(movie_dir)

        assert result == main

    def test_finds_video_in_deeply_nested_dir(self, tmp_path: Path) -> None:
        """Video in a 2-level deep structure should still be found."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        deep = movie_dir / "Release" / "Subs"
        deep.mkdir(parents=True)
        video = movie_dir / "Release" / "Movie.mkv"
        video.write_bytes(b"\x00" * 1000)

        from personalscraper.scraper.scraper import _find_video_file
        result = _find_video_file(movie_dir)

        assert result == video
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/scraper/test_scraper.py::TestFindVideoFileNested -v`
Expected: FAIL — current `_find_video_file` uses `iterdir()` and doesn't find nested files.

- [ ] **Step 3: Commit**

```bash
git add tests/scraper/test_scraper.py
git commit -m "v12.2.1: Add failing tests for _find_video_file with nested torrent structures"
```

## Task 2: Rewrite \_find_video_file to be recursive

**Files:**

- Modify: `personalscraper/scraper/scraper.py:199-211`

- [ ] **Step 1: Replace \_find_video_file**

Replace the current function (lines 199-211):

```python
def _find_video_file(directory: Path) -> Path | None:
    """Find the main video file in a directory tree.

    Searches recursively for video files. When multiple are found,
    returns the largest one (main feature, not sample/extra).
    Skips hidden files and .actors/ directories.

    Args:
        directory: Root directory to search.

    Returns:
        Path to the largest video file, or None if no video found.
    """
    candidates = [
        f for f in directory.rglob("*")
        if f.is_file()
        and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        and not f.name.startswith(".")
        and ".actors" not in f.parts
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.stat().st_size)
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/scraper/test_scraper.py::TestFindVideoFileNested tests/scraper/test_scraper.py::TestFindVideoFile -v`
Expected: ALL pass (new + existing tests)

- [ ] **Step 3: Commit**

```bash
git add personalscraper/scraper/scraper.py
git commit -m "v12.2.2: Make _find_video_file recursive — finds nested torrent video files"
```

## Task 3: Write reproducer test for empty release-group dir cleanup

**Files:**

- Modify: `tests/scraper/test_scraper.py`

- [ ] **Step 1: Write failing test**

```python
class TestCleanupEmptyReleaseDirs:
    """Tests for empty release-group directory cleanup after episode rename."""

    def test_empty_release_dirs_removed(self, tmp_path: Path) -> None:
        """Empty release-group subdirectories should be removed after rename."""
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()

        # Simulate post-rename state: episodes moved to Saison 01/,
        # but empty release-group dirs remain
        (show_dir / "Saison 01").mkdir()
        (show_dir / "Saison 01" / "S01E01 - Title.mkv").write_bytes(b"ep1")

        # Empty release-group dirs (should be removed)
        (show_dir / "Show.S01E01.1080p.WEB-GROUP").mkdir()
        (show_dir / "Show.S01E02.1080p.WEB-GROUP").mkdir()

        # Non-empty dir (should NOT be removed)
        leftover = show_dir / "Show.S01E03.1080p.WEB-GROUP"
        leftover.mkdir()
        (leftover / "S01E03.mkv").write_bytes(b"ep3")

        # .actors dir (should NOT be removed even if empty)
        (show_dir / ".actors").mkdir()

        from personalscraper.scraper.scraper import _cleanup_empty_release_dirs
        removed = _cleanup_empty_release_dirs(show_dir)

        assert removed == 2
        assert not (show_dir / "Show.S01E01.1080p.WEB-GROUP").exists()
        assert not (show_dir / "Show.S01E02.1080p.WEB-GROUP").exists()
        assert (show_dir / "Show.S01E03.1080p.WEB-GROUP").exists()  # Non-empty
        assert (show_dir / ".actors").exists()  # Hidden dir
        assert (show_dir / "Saison 01").exists()  # Season dir
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/scraper/test_scraper.py::TestCleanupEmptyReleaseDirs -v`
Expected: FAIL — `ImportError: cannot import name '_cleanup_empty_release_dirs'`

- [ ] **Step 3: Commit**

```bash
git add tests/scraper/test_scraper.py
git commit -m "v12.2.3: Add failing test for empty release-group dir cleanup"
```

## Task 4: Implement \_cleanup_empty_release_dirs and integrate

**Files:**

- Modify: `personalscraper/scraper/scraper.py`

- [ ] **Step 1: Add \_cleanup_empty_release_dirs function**

Add after `_cleanup_stale_files()` in scraper.py:

```python
def _cleanup_empty_release_dirs(show_dir: Path) -> int:
    """Remove empty release-group subdirectories from a TV show folder.

    After episodes are moved to Saison XX/ directories, the original
    release-group subdirectories (e.g., Show.S01E01.1080p.WEB-GROUP/)
    may be left empty. This function removes them.

    Skips hidden directories (.actors/) and season directories (Saison XX/).

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        Number of empty directories removed.
    """
    removed = 0
    for subdir in list(show_dir.iterdir()):
        if not subdir.is_dir():
            continue
        if subdir.name.startswith("."):
            continue
        if re.match(r"^Saison \d+$", subdir.name):
            continue
        try:
            if not any(subdir.iterdir()):
                subdir.rmdir()
                logger.info("Removed empty release dir: %s", subdir.name)
                removed += 1
        except OSError:
            pass
    return removed
```

- [ ] **Step 2: Call after rename_episodes in scrape_tvshow**

In `scrape_tvshow()`, after the `rename_episodes()` call block (around line 840-850), add:

```python
            # Clean empty release-group subdirectories
            _cleanup_empty_release_dirs(show_dir)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/scraper/test_scraper.py::TestCleanupEmptyReleaseDirs -v`
Expected: PASS

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add personalscraper/scraper/scraper.py
git commit -m "v12.2.4: Add _cleanup_empty_release_dirs after episode rename"
```

## Task 5: Update IMPLEMENTATION.md

- [ ] **Step 1: Mark Phase 2 complete**
- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v12.2.5: Update IMPLEMENTATION.md — Phase 2 complete"
```

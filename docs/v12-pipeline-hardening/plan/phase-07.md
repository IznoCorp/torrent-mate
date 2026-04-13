# Phase 7: Améliorations mineures (bugs #21, #22)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Fix overly strict Saison regex + add desktop.ini to junk files.

**Architecture:** Two small targeted fixes with reproducer tests.

**Tech Stack:** Python, pytest

---

## Task 1: Write reproducer test for Saison regex

**Files:**

- Modify: `tests/scraper/test_scraper.py`

- [ ] **Step 1: Write failing test**

```python
class TestSaisonRegex:
    """Tests for Saison directory regex matching."""

    def test_single_digit_saison_excluded_from_rglob(self, tmp_path: Path) -> None:
        """Files in 'Saison 1' (single digit) should be excluded from episode re-processing."""
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()

        # Already-organized episode in single-digit season dir
        saison = show_dir / "Saison 1"
        saison.mkdir()
        episode = saison / "S01E01 - Pilot.mkv"
        episode.write_bytes(b"\x00" * 1000)

        # This should NOT pick up the episode (it's already in a Saison dir)
        import re
        from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

        video_files = [
            f for f in show_dir.rglob("*")
            if f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and not re.match(r"^Saison \d+$", f.parent.name)
        ]

        assert len(video_files) == 0, (
            f"Episode in 'Saison 1' should be excluded but was found: {video_files}"
        )

    def test_three_digit_saison_excluded(self, tmp_path: Path) -> None:
        """Files in 'Saison 100' (three digits) should also be excluded."""
        show_dir = tmp_path / "Anime (2020)"
        show_dir.mkdir()

        saison = show_dir / "Saison 100"
        saison.mkdir()
        episode = saison / "S100E01 - Title.mkv"
        episode.write_bytes(b"\x00" * 1000)

        import re
        from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

        video_files = [
            f for f in show_dir.rglob("*")
            if f.is_file()
            and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
            and not re.match(r"^Saison \d+$", f.parent.name)
        ]

        assert len(video_files) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/scraper/test_scraper.py::TestSaisonRegex -v`
Expected: FAIL — current regex `r"^Saison \d{2}$"` doesn't match `Saison 1` or `Saison 100`

- [ ] **Step 3: Commit**

```bash
git add tests/scraper/test_scraper.py
git commit -m "v12.7.1: Add failing tests for Saison regex with 1 and 3+ digits"
```

## Task 2: Fix Saison regex in scraper.py

**Files:**

- Modify: `personalscraper/scraper/scraper.py:815`

- [ ] **Step 1: Change regex**

Change line 815 from:

```python
            and not re.match(r"^Saison \d{2}$", f.parent.name)
```

To:

```python
            and not re.match(r"^Saison \d+$", f.parent.name)
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/scraper/test_scraper.py::TestSaisonRegex -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add personalscraper/scraper/scraper.py
git commit -m "v12.7.2: Fix Saison regex — accept any digit count (1, 01, 100)"
```

## Task 3: Write reproducer test for desktop.ini junk

**Files:**

- Modify: `tests/process/test_cleanup.py`

- [ ] **Step 1: Write failing test**

```python
def test_desktop_ini_treated_as_junk(tmp_path: Path) -> None:
    """Directory containing only desktop.ini should be treated as empty."""
    category_dir = tmp_path / "001-MOVIES"
    category_dir.mkdir()

    junk_dir = category_dir / "Empty Movie (2025)"
    junk_dir.mkdir()
    (junk_dir / "desktop.ini").write_text("[ViewState]\nMode=4\n")

    from personalscraper.process.cleanup import _is_effectively_empty

    assert _is_effectively_empty(junk_dir) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/process/test_cleanup.py::test_desktop_ini_treated_as_junk -v`
Expected: FAIL — `desktop.ini` is not in `_JUNK_FILES`

- [ ] **Step 3: Commit**

```bash
git add tests/process/test_cleanup.py
git commit -m "v12.7.3: Add failing test for desktop.ini as junk file"
```

## Task 4: Add desktop.ini to \_JUNK_FILES

**Files:**

- Modify: `personalscraper/process/cleanup.py:16`

- [ ] **Step 1: Update \_JUNK_FILES**

Change line 16 from:

```python
_JUNK_FILES = {".DS_Store", "Thumbs.db"}
```

To:

```python
_JUNK_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/process/test_cleanup.py -v`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add personalscraper/process/cleanup.py
git commit -m "v12.7.4: Add desktop.ini to junk files for NTFS compatibility"
```

## Task 5: Update IMPLEMENTATION.md

- [ ] **Step 1: Mark Phase 7 complete**
- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v12.7.5: Update IMPLEMENTATION.md — Phase 7 complete"
```

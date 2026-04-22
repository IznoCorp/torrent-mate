# Phase 3: Remove Dead `TMDBClient.select_best_image`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Delete the dead `TMDBClient.select_best_image()` method and its tests. The identical function in `artwork.py` is the single source of truth.

**Architecture:** Pure deletion — no refactoring, no new code. Remove the dead method and its 7 test cases.

**Tech Stack:** Python, pytest

---

## Task 1: Remove dead method from TMDBClient

**Files:**

- Modify: `personalscraper/scraper/tmdb_client.py:397-430`

- [ ] **Step 1: Delete `select_best_image` method**

Remove the entire `select_best_image` method from `TMDBClient` (lines 397-430 in `personalscraper/scraper/tmdb_client.py`):

```python
# DELETE THIS ENTIRE METHOD (lines 397-430):
    def select_best_image(self, images: list[dict], image_type: str) -> str | None:
        """Select the best image by language priority and vote average.
        ...
        """
        if not images:
            return None

        # Language priority mapping (lower = better)
        lang_priority: dict[str | None, int] = {"fr": 0, "en": 1}

        def sort_key(img: dict) -> tuple:
            lang: str | None = img.get("iso_639_1")
            priority = lang_priority.get(lang, 2)  # None/other → 2
            vote = img.get("vote_average", 0.0)
            return (priority, -vote)  # Lower priority first, higher vote first

        sorted_images = sorted(images, key=sort_key)
        return sorted_images[0].get("file_path")
```

- [ ] **Step 2: Verify no other code references the removed method**

Run: `grep -rn "select_best_image" personalscraper/ --include="*.py" | grep -v artwork | grep -v __pycache__`

Expected: No matches from `tmdb_client.py` (the method is gone). Only `artwork.py` references should remain.

- [ ] **Step 3: Commit**

```bash
git add personalscraper/scraper/tmdb_client.py
git commit -m "v11.3.1: Remove dead TMDBClient.select_best_image method"
```

## Task 2: Remove dead tests

**Files:**

- Modify: `tests/scraper/test_tmdb_client.py`

- [ ] **Step 1: Delete the `TestImageSelection` class tests for `select_best_image`**

Remove the 7 test methods that test `TMDBClient.select_best_image()` from `tests/scraper/test_tmdb_client.py`. These are in the `TestImageSelection` class (around lines 606-671):

```python
# DELETE THESE 7 TESTS:
    def test_select_best_image_prefers_french(self, client: TMDBClient) -> None:
    def test_select_best_image_english_over_null(self, client: TMDBClient) -> None:
    def test_select_best_image_vote_tiebreaker(self, client: TMDBClient) -> None:
    def test_select_best_image_null_language(self, client: TMDBClient) -> None:
    def test_select_best_image_empty_list(self, client: TMDBClient) -> None:
    def test_select_best_image_full_priority(self, client: TMDBClient) -> None:
    def test_select_best_image_unknown_language(self, client: TMDBClient) -> None:
```

If `TestImageSelection` only contains these tests and `test_get_image_url`, rename the class to `TestGetImageUrl` or keep it as-is with just the remaining test.

- [ ] **Step 2: Run artwork tests to confirm the canonical select_best_image is still tested**

Run: `python -m pytest tests/scraper/test_artwork.py::TestSelectBestImage -v`

Expected: PASS — all 6 tests for `artwork.select_best_image()` pass (these are the canonical tests).

- [ ] **Step 3: Run full scraper test suite**

Run: `python -m pytest tests/scraper/ -v`

Expected: All tests pass. Count should be ~7 lower than before (removed dead tests).

- [ ] **Step 4: Run full test suite for regressions**

Run: `python -m pytest tests/ -x -q`

Expected: ~987+ passed (7 fewer than before), 0 failed

- [ ] **Step 5: Commit**

```bash
git add tests/scraper/test_tmdb_client.py
git commit -m "v11.3.2: Remove dead tests for TMDBClient.select_best_image"
```

## Task 3: Update IMPLEMENTATION.md

- [ ] **Step 1: Update V11 Phase 3 entry**

Mark Phase 3 as complete in `docs/IMPLEMENTATION.md`.

- [ ] **Step 2: Commit**

```bash
git add -f docs/IMPLEMENTATION.md
git commit -m "v11.3.3: Update IMPLEMENTATION.md — Phase 3 complete"
```

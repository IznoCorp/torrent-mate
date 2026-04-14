# V13 PIPELINE CORRECTNESS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the pipeline truly idempotent — every re-run detects and corrects problems instead of skipping them. Fix all 24 bugs from the 2026-04-14 pipeline run. Add ENFORCE step between PROCESS and VERIFY.

**Architecture:** Two-layer defense: PROCESS repairs what it can (episodes, NFO residues) by replacing blind fast-skip with validate-and-repair. New ENFORCE step sanitizes filenames, validates structure, checks cross-step coherence. VERIFY becomes read-only gate. Pipeline goes from 7 to 8 StepReports.

**Tech Stack:** Python 3.11, pytest, personalscraper existing modules (text_utils, naming_patterns, genre_mapper, scraper, verify). No new external dependencies.

**Design spec:** `docs/v13-pipeline-correctness/DESIGN.md`

---

## File Structure

### New files

| File                                             | Responsibility                                          |
| ------------------------------------------------ | ------------------------------------------------------- |
| `personalscraper/enforce/__init__.py`            | Package init                                            |
| `personalscraper/enforce/file_sanitizer.py`      | Rename NTFS-illegal chars, delete .DS*Store/.*\*        |
| `personalscraper/enforce/structure_validator.py` | Validate/fix NFO count, artwork dupes, season structure |
| `personalscraper/enforce/coherence_checker.py`   | Cross-step coherence (genre, IDs, sort↔process)         |
| `personalscraper/enforce/run.py`                 | Orchestrator — sanitize → structure → coherence         |
| `tests/enforce/__init__.py`                      | Test package init                                       |
| `tests/enforce/test_file_sanitizer.py`           | Tests for file_sanitizer                                |
| `tests/enforce/test_structure_validator.py`      | Tests for structure_validator                           |
| `tests/enforce/test_coherence_checker.py`        | Tests for coherence_checker                             |
| `tests/enforce/test_run_enforce.py`              | Tests for orchestrator                                  |
| `tests/enforce/test_idempotence.py`              | Idempotence fixture tests (run 1 fixes, run 2 no-op)    |

### Modified files

| File                                     | Changes                                                                                                        |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `personalscraper/scraper/run.py`         | Add `_needs_repair()`, modify `run_scrape()` fast-skip to combine `_has_unscraped_items()` + `_needs_repair()` |
| `personalscraper/scraper/scraper.py`     | Add `_repair_movie_dir()`, `_repair_tvshow_dir()`, modify fast-skip in `scrape_movie()`/`scrape_tvshow()`      |
| `personalscraper/pipeline.py`            | Add ENFORCE step, update step count 7→8, update docstrings                                                     |
| `personalscraper/cli.py`                 | Add `enforce` command, deprecate `verify --fix`, update `run` docstring                                        |
| `personalscraper/models.py`              | Add enforce icon to `to_html()`, update `StepReport.name` docstring                                            |
| `personalscraper/genre_mapper.py`        | Add French TMDB genre variants to `_REALITY_NAMES` ("emission", "divertissement", "jeu televise")              |
| `personalscraper/dispatch/dispatcher.py` | Add `--exclude=.DS_Store --exclude=._*` to rsync                                                               |
| `personalscraper/verify/run.py`          | Accept `fix=False` from pipeline mode                                                                          |
| `CLAUDE.md`                              | Update pipeline docs, add V13, add enforce/                                                                    |

---

## Phases

| Phase | Tasks | Focus                              |
| ----- | ----- | ---------------------------------- |
| 0     | 1     | Audit V0-V12                       |
| 1     | 2-5   | Scraper repair (fast-skip refonte) |
| 2     | 6-9   | ENFORCE step                       |
| 3     | 10-12 | Integration + fixes ponctuels      |
| 4     | 13-14 | E2E idempotence tests              |
| 5     | 15    | Rapport V14+ + CLAUDE.md           |

---

## Phase 0 — Audit

### Task 1: Audit V0-V12 promises vs implementation

**Files:**

- Create: `docs/v13-pipeline-correctness/AUDIT-V0-V12.md`

This task is a research/documentation task, not a code task. Use an Explore agent to read
each version's design docs and grep the codebase for implementation status.

- [ ] **Step 1: Read all brainstorming/design docs**

For each version V0 through V12, read:

- `docs/vX-*/BRAINSTORMING.md`
- `docs/vX-*/DESIGN.md`
- `docs/vX-*/plan/INDEX.md`

Extract every feature that was promised/designed.

- [ ] **Step 2: Verify each feature in code**

For each feature: grep the codebase to check if the function/class exists, is tested, and
is called in the pipeline flow. Classify as OK | BUG | MISSING.

- [ ] **Step 3: Write the audit report**

Write `docs/v13-pipeline-correctness/AUDIT-V0-V12.md` with a table per version showing
features, their code location, test status, and flow integration.

- [ ] **Step 4: Triage findings**

Separate BUG findings into V13 scope vs V14+ backlog. Add any new V13-scope bugs to the
task list.

- [ ] **Step 5: Commit**

```bash
git add -f docs/v13-pipeline-correctness/AUDIT-V0-V12.md
git commit -m "v13.0.1: Audit V0-V12 — promises vs implementation report"
```

---

## Phase 1 — Scraper Repair

### Task 2: `_needs_repair()` and `_should_skip_scrape()` in scraper/run.py

**Files:**

- Modify: `personalscraper/scraper/run.py`
- Test: `tests/scraper/test_run_scrape.py`

- [ ] **Step 1: Write failing tests for `_needs_repair()`**

```python
# tests/scraper/test_run_scrape.py — add these tests
from personalscraper.scraper.run import _needs_repair


def test_needs_repair_false_when_clean(tmp_path):
    """Clean show dir (episodes in Saison XX/, no residuals) → False."""
    show_dir = tmp_path / "002-TVSHOWS" / "The Boys (2019)"
    show_dir.mkdir(parents=True)
    (show_dir / "tvshow.nfo").write_text("<tvshow><title>The Boys</title></tvshow>")
    s01 = show_dir / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - Episode.mkv").write_bytes(b"\x00")
    assert _needs_repair(tmp_path / "002-TVSHOWS") is False


def test_needs_repair_true_raw_torrent_dir(tmp_path):
    """Episode in raw torrent subdir → True."""
    show_dir = tmp_path / "002-TVSHOWS" / "The Boys (2019)"
    show_dir.mkdir(parents=True)
    (show_dir / "tvshow.nfo").write_text("<tvshow><title>The Boys</title></tvshow>")
    raw = show_dir / "The.Boys.S05E01.MULTi"
    raw.mkdir()
    (raw / "S05E01.mkv").write_bytes(b"\x00")
    assert _needs_repair(tmp_path / "002-TVSHOWS") is True


def test_needs_repair_true_duplicate_nfo(tmp_path):
    """Movie with 2 NFOs → True."""
    movie_dir = tmp_path / "001-MOVIES" / "Scream 7 (2026)"
    movie_dir.mkdir(parents=True)
    (movie_dir / "Scream 7.nfo").write_text("<movie><title>Scream 7</title></movie>")
    (movie_dir / "Scream.7.2026.MULTI.nfo").write_text("<movie/>")
    (movie_dir / "Scream 7.mkv").write_bytes(b"\x00")
    assert _needs_repair(tmp_path / "001-MOVIES") is True


def test_needs_repair_true_root_mkv_with_season(tmp_path):
    """MKV at root when Saison XX/ exists → True."""
    show_dir = tmp_path / "002-TVSHOWS" / "Show (2025)"
    show_dir.mkdir(parents=True)
    (show_dir / "tvshow.nfo").write_text("<tvshow/>")
    s02 = show_dir / "Saison 02"
    s02.mkdir()
    (s02 / "S02E01 - Ep.mkv").write_bytes(b"\x00")
    (show_dir / "Show.S02E01.mkv").write_bytes(b"\x00")  # duplicate at root
    assert _needs_repair(tmp_path / "002-TVSHOWS") is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/scraper/test_run_scrape.py -k "needs_repair" -v
```

Expected: FAIL (function not found).

- [ ] **Step 3: Implement `_needs_repair()`**

```python
# personalscraper/scraper/run.py — add imports at top of module (alongside existing ones)
# Add: import re, from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

import re

from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

_SEASON_DIR_RE = re.compile(r"^Saison \d+$")


def _needs_repair(category_dir: Path) -> bool:
    """Check if any item in category needs repair beyond NFO/artwork.

    Quick filesystem-only check (no API calls). Returns True if any
    item has unorganized episodes, residual NFOs, or root-level MKV
    duplicates.

    Args:
        category_dir: Path to 001-MOVIES/ or 002-TVSHOWS/.

    Returns:
        True if at least one item needs repair.
    """
    if not category_dir.exists():
        return False

    is_movies = "MOVIE" in category_dir.name.upper()

    for folder in category_dir.iterdir():
        if not folder.is_dir() or folder.name.startswith("."):
            continue

        if is_movies:
            # Multiple NFOs in a movie dir = residual
            nfo_count = sum(1 for f in folder.iterdir() if f.suffix.lower() == ".nfo")
            if nfo_count > 1:
                return True
        else:
            # TV show checks
            has_season_dirs = any(
                d.is_dir() and _SEASON_DIR_RE.match(d.name)
                for d in folder.iterdir()
            )

            for item in folder.iterdir():
                # Video at root when seasons exist = duplicate
                if (
                    has_season_dirs
                    and item.is_file()
                    and item.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
                ):
                    return True

                # Raw torrent subdir with videos = unorganized episodes
                if (
                    item.is_dir()
                    and not item.name.startswith(".")
                    and not _SEASON_DIR_RE.match(item.name)
                ):
                    for sub in item.rglob("*"):
                        if sub.is_file() and sub.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS:
                            return True

            # NFO residuals at root (anything besides tvshow.nfo)
            root_nfos = [
                f for f in folder.iterdir()
                if f.is_file() and f.suffix.lower() == ".nfo" and f.name != "tvshow.nfo"
            ]
            if root_nfos:
                return True

    return False
```

- [ ] **Step 4: Modify `run_scrape()` to use combined skip logic**

Replace the fast-skip in `run_scrape()`:

```python
# personalscraper/scraper/run.py — modify run_scrape()
# BEFORE:
#   if not _has_unscraped_items(settings):
#       logger.info("Scrape fast-skip: all NFOs valid and artwork present")
#       return StepReport(name="scrape")

# AFTER:
    if not _has_unscraped_items(settings) and not _needs_repair(
        settings.staging_dir / settings.movies_dir_name
    ) and not _needs_repair(
        settings.staging_dir / settings.tvshows_dir_name
    ):
        logger.info("Scrape fast-skip: all NFOs valid, artwork present, no repairs needed")
        return StepReport(name="scrape")
```

- [ ] **Step 5: Run all tests**

```bash
python -m pytest tests/scraper/test_run_scrape.py -v
```

Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add personalscraper/scraper/run.py tests/scraper/test_run_scrape.py
git commit -m "v13.1.1: Add _needs_repair() — disable scraper fast-skip when repairs needed"
```

---

### Task 3: `_repair_movie_dir()` in scraper.py

**Files:**

- Modify: `personalscraper/scraper/scraper.py`
- Test: `tests/scraper/test_scraper.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/scraper/test_scraper.py — add these tests

def test_repair_movie_dir_removes_residual_nfos(tmp_path, scraper):
    """Movie with 2 NFOs: keep the correct one, delete residual."""
    movie_dir = tmp_path / "Avatar De feu et de cendres (2025)"
    movie_dir.mkdir()
    good_nfo = movie_dir / "Avatar De feu et de cendres.nfo"
    good_nfo.write_text('<movie><title>Avatar</title><uniqueid type="tmdb">83533</uniqueid></movie>')
    bad_nfo = movie_dir / "Avatar de feu et de cendres 7 1 neostark (2025).nfo"
    bad_nfo.write_text("<movie/>")
    (movie_dir / "Avatar De feu et de cendres.mkv").write_bytes(b"\x00")

    repaired = scraper._repair_movie_dir(movie_dir, "Avatar De feu et de cendres")
    assert repaired is True
    assert good_nfo.exists()
    assert not bad_nfo.exists()


def test_repair_movie_dir_noop_when_clean(tmp_path, scraper):
    """Movie with exactly 1 NFO → no repair needed."""
    movie_dir = tmp_path / "Scream 7 (2026)"
    movie_dir.mkdir()
    (movie_dir / "Scream 7.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie_dir / "Scream 7.mkv").write_bytes(b"\x00")
    (movie_dir / "Scream 7-poster.jpg").write_bytes(b"\x00")

    repaired = scraper._repair_movie_dir(movie_dir, "Scream 7")
    assert repaired is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/scraper/test_scraper.py -k "repair_movie" -v
```

- [ ] **Step 3: Implement `_repair_movie_dir()`**

Add to `Scraper` class in `personalscraper/scraper/scraper.py`:

```python
def _repair_movie_dir(self, movie_dir: Path, title: str) -> bool:
    """Repair a movie directory with valid NFO.

    Removes residual NFOs (keeps only {sanitized_title}.nfo).
    Does not re-scrape or re-match.

    Args:
        movie_dir: Path to the movie directory.
        title: Parsed movie title from folder name.

    Returns:
        True if any repair was applied.
    """
    repaired = False
    expected_nfo = sanitize_filename(title) + ".nfo"

    for nfo in movie_dir.glob("*.nfo"):
        if nfo.name != expected_nfo:
            if not self.dry_run:
                try:
                    nfo.unlink()
                    logger.info("Repair: removed residual NFO %s", nfo.name)
                    repaired = True
                except OSError as exc:
                    logger.warning("Repair: cannot delete %s: %s", nfo.name, exc)
            else:
                logger.info("[DRY RUN] Would remove residual NFO %s", nfo.name)
                repaired = True

    return repaired
```

- [ ] **Step 4: Modify `scrape_movie()` fast-skip to call `_repair_movie_dir()`**

In `scrape_movie()`, after the existing artwork recovery block:

```python
# BEFORE (line ~552):
#   if result.action != "artwork_recovered":
#       result.action = "skipped_already_done"
#   logger.info("NFO valid, %s: %s", result.action, movie_dir.name)
#   return result

# AFTER:
        # Repair pass: remove residual NFOs
        repaired = self._repair_movie_dir(movie_dir, title)
        if repaired and result.action != "artwork_recovered":
            result.action = "repaired"
        elif result.action != "artwork_recovered":
            result.action = "skipped_already_done"
        logger.info("NFO valid, %s: %s", result.action, movie_dir.name)
        return result
```

- [ ] **Step 5: Run all scraper tests**

```bash
python -m pytest tests/scraper/ -v
```

Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add personalscraper/scraper/scraper.py tests/scraper/test_scraper.py
git commit -m "v13.1.2: Add _repair_movie_dir() — remove residual NFOs on re-run"
```

---

### Task 4: `_repair_tvshow_dir()` in scraper.py

**Files:**

- Modify: `personalscraper/scraper/scraper.py`
- Test: `tests/scraper/test_scraper.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/scraper/test_scraper.py — add these tests

def test_repair_tvshow_dir_removes_root_nfo_residuals(tmp_path, scraper):
    """tvshow.nfo is kept, other .nfo at root are removed."""
    show_dir = tmp_path / "Show (2025)"
    show_dir.mkdir()
    tvshow_nfo = show_dir / "tvshow.nfo"
    tvshow_nfo.write_text('<tvshow><uniqueid type="tmdb">123</uniqueid></tvshow>')
    residual = show_dir / "random.nfo"
    residual.write_text("<movie/>")

    repaired = scraper._repair_tvshow_dir(show_dir)
    assert repaired is True
    assert tvshow_nfo.exists()
    assert not residual.exists()


def test_repair_tvshow_dir_removes_root_mkv_duplicates(tmp_path, scraper):
    """MKV at root matching SxxExx in Saison XX/ → deleted."""
    show_dir = tmp_path / "Show (2025)"
    show_dir.mkdir()
    (show_dir / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
    s02 = show_dir / "Saison 02"
    s02.mkdir()
    (s02 / "S02E01 - Episode Title.mkv").write_bytes(b"\x00" * 100)
    # Root duplicate
    root_dup = show_dir / "Show.S02E01.1080p.mkv"
    root_dup.write_bytes(b"\x00" * 50)

    repaired = scraper._repair_tvshow_dir(show_dir)
    assert repaired is True
    assert not root_dup.exists()
    assert (s02 / "S02E01 - Episode Title.mkv").exists()


def test_repair_tvshow_dir_noop_when_clean(tmp_path, scraper):
    """Clean show dir → no repair."""
    show_dir = tmp_path / "Show (2025)"
    show_dir.mkdir()
    (show_dir / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
    (show_dir / "poster.jpg").write_bytes(b"\x00")
    s01 = show_dir / "Saison 01"
    s01.mkdir()
    (s01 / "S01E01 - Ep.mkv").write_bytes(b"\x00")

    repaired = scraper._repair_tvshow_dir(show_dir)
    assert repaired is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/scraper/test_scraper.py -k "repair_tvshow" -v
```

- [ ] **Step 3: Implement `_repair_tvshow_dir()`**

Add to `Scraper` class in `personalscraper/scraper/scraper.py`:

```python
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)

def _repair_tvshow_dir(self, show_dir: Path) -> bool:
    """Repair a TV show directory with valid NFO.

    1. Remove residual NFOs at root (keep only tvshow.nfo).
    2. Remove root MKV duplicates (same SxxExx in Saison XX/).
    3. Organize unstructured episodes into Saison XX/ (if TMDB ID available).

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        True if any repair was applied.
    """
    repaired = False

    # 1. Remove residual NFOs at root (keep tvshow.nfo)
    for nfo in show_dir.glob("*.nfo"):
        if nfo.name != "tvshow.nfo":
            if not self.dry_run:
                try:
                    nfo.unlink()
                    logger.info("Repair: removed residual NFO %s in %s", nfo.name, show_dir.name)
                    repaired = True
                except OSError as exc:
                    logger.warning("Repair: cannot delete %s: %s", nfo.name, exc)
            else:
                logger.info("[DRY RUN] Would remove residual NFO %s", nfo.name)
                repaired = True

    # 2. Collect organized episodes (SxxExx → path)
    organized: set[tuple[int, int]] = set()
    for season_dir in show_dir.iterdir():
        if season_dir.is_dir() and re.match(r"^Saison \d+$", season_dir.name):
            for f in season_dir.iterdir():
                if f.is_file():
                    m = _SXXEXX_RE.search(f.stem)
                    if m:
                        organized.add((int(m.group(1)), int(m.group(2))))

    # 3. Remove root MKV duplicates that match organized episodes
    if organized:
        for f in list(show_dir.iterdir()):
            if not f.is_file() or f.suffix.lstrip(".").lower() not in VIDEO_EXTENSIONS:
                continue
            m = _SXXEXX_RE.search(f.stem)
            if m and (int(m.group(1)), int(m.group(2))) in organized:
                if not self.dry_run:
                    try:
                        f.unlink()
                        logger.info(
                            "Repair: removed root duplicate %s (in Saison already)",
                            f.name,
                        )
                        repaired = True
                    except OSError as exc:
                        logger.warning("Repair: cannot delete %s: %s", f.name, exc)
                else:
                    logger.info("[DRY RUN] Would remove root duplicate %s", f.name)
                    repaired = True

    # 4. Organize unstructured episodes (from raw torrent dirs)
    # Find videos NOT in Saison XX/ dirs
    unorganized = sorted(
        f for f in show_dir.rglob("*")
        if f.is_file()
        and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        and not re.match(r"^Saison \d+$", f.parent.name)
        and f.parent != show_dir  # root files already handled above
        and ".actors" not in str(f)
    )

    if unorganized:
        nfo_path = show_dir / "tvshow.nfo"
        tmdb_id = self._extract_tmdb_id_from_nfo(nfo_path)
        if tmdb_id:
            try:
                show_data = self._tmdb.get_tv(tmdb_id)
                api_episodes: dict[tuple[int, int], str] = {}
                for season in show_data.get("seasons", []):
                    s_num = season.get("season_number", 0)
                    if s_num == 0:
                        continue
                    try:
                        s_detail = self._tmdb.get_tv_season(tmdb_id, s_num)
                        for ep in s_detail.get("episodes", []):
                            e_num = ep.get("episode_number", 0)
                            api_episodes[(s_num, e_num)] = ep.get("name", f"Episode {e_num}")
                    except Exception as e:
                        logger.warning("Repair: failed to get season %d: %s", s_num, e)

                if api_episodes:
                    from personalscraper.scraper.episode_manager import (
                        create_season_dirs,
                        match_episode_files,
                        rename_episodes,
                    )
                    ep_list = [{"season_number": s, "episode_number": e} for s, e in api_episodes]
                    create_season_dirs(show_dir, ep_list, self.patterns, self.dry_run)
                    matched = match_episode_files(unorganized, api_episodes)
                    if matched:
                        count = rename_episodes(matched, show_dir, self.patterns, self.dry_run)
                        if count > 0:
                            repaired = True
                            logger.info(
                                "Repair: organized %d episodes in %s", count, show_dir.name,
                            )
                        # Generate episode NFOs for newly organized episodes
                        self._generate_episode_nfos(matched, show_dir, show_data)

                    # Clean empty release-group subdirs
                    if not self.dry_run:
                        try:
                            _cleanup_empty_release_dirs(show_dir)
                        except OSError as exc:
                            logger.warning(
                                "Repair: failed to clean empty dirs in %s: %s",
                                show_dir.name, exc,
                            )
            except Exception as e:
                logger.warning(
                    "Repair: failed to organize episodes in %s: %s", show_dir.name, e,
                )
        else:
            logger.warning(
                "Repair: cannot organize episodes in %s — no TMDB ID in NFO",
                show_dir.name,
            )

    return repaired
```

- [ ] **Step 4: Modify `scrape_tvshow()` fast-skip to call `_repair_tvshow_dir()`**

In `scrape_tvshow()`, after the existing artwork recovery block:

```python
# BEFORE:
#   if result.action != "artwork_recovered":
#       result.action = "skipped_already_done"
#   logger.info("NFO valid, %s: %s", result.action, show_dir.name)
#   return result

# AFTER:
        # Repair pass
        repaired = self._repair_tvshow_dir(show_dir)
        if repaired and result.action != "artwork_recovered":
            result.action = "repaired"
        elif result.action != "artwork_recovered":
            result.action = "skipped_already_done"
        logger.info("NFO valid, %s: %s", result.action, show_dir.name)
        return result
```

- [ ] **Step 5: Update `_to_step_report()` in `scraper/run.py` to handle "repaired" action**

```python
# In _to_step_report() in scraper/run.py, add after "artwork_recovered":
        elif r.action == "repaired":
            success += 1
            details.append(f"[repaired] {name}")
```

- [ ] **Step 6: Run all scraper tests**

```bash
python -m pytest tests/scraper/ -v
```

Expected: ALL PASS.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/scraper/scraper.py personalscraper/scraper/run.py tests/scraper/test_scraper.py
git commit -m "v13.1.3: Add _repair_tvshow_dir() — organize episodes, remove duplicates on re-run"
```

---

### Task 5: Run full test suite for Phase 1

- [ ] **Step 1: Run ALL tests**

```bash
python -m pytest tests/ -x -q
```

Expected: ALL PASS with zero regressions.

- [ ] **Step 2: Commit if any test fixes needed**

---

## Phase 2 — ENFORCE Step

### Task 6: `file_sanitizer.py`

**Files:**

- Create: `personalscraper/enforce/__init__.py`
- Create: `personalscraper/enforce/file_sanitizer.py`
- Create: `tests/enforce/__init__.py`
- Create: `tests/enforce/test_file_sanitizer.py`

- [ ] **Step 1: Create package init files**

```python
# personalscraper/enforce/__init__.py
"""ENFORCE pipeline step — validate and correct staging media conventions."""

# tests/enforce/__init__.py
```

- [ ] **Step 2: Write failing tests**

```python
# tests/enforce/test_file_sanitizer.py

import pytest
from pathlib import Path
from personalscraper.enforce.file_sanitizer import sanitize_files, SanitizeResult


@pytest.fixture
def settings(tmp_path):
    """Minimal settings pointing to tmp_path as staging."""
    from unittest.mock import MagicMock
    s = MagicMock()
    s.staging_dir = tmp_path
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    return s


def test_renames_colon_file(tmp_path, settings):
    """File with : in name → renamed to sanitized version."""
    movies = tmp_path / "001-MOVIES" / "Avatar (2025)"
    movies.mkdir(parents=True)
    colon_file = movies / "Avatar : De feu-poster.jpg"
    colon_file.write_bytes(b"\x00")

    results = sanitize_files(settings, dry_run=False)
    renamed = [r for r in results if r.action == "renamed"]
    assert len(renamed) == 1
    assert renamed[0].old_name == "Avatar : De feu-poster.jpg"
    assert not colon_file.exists()
    assert (movies / "Avatar De feu-poster.jpg").exists()  # single space (sanitize collapses)


def test_deletes_duplicate_when_sanitized_exists(tmp_path, settings):
    """Legacy file with : deleted when sanitized version already exists."""
    movies = tmp_path / "001-MOVIES" / "Avatar (2025)"
    movies.mkdir(parents=True)
    (movies / "Avatar De feu-poster.jpg").write_bytes(b"good")  # sanitized = single space
    (movies / "Avatar : De feu-poster.jpg").write_bytes(b"legacy")

    results = sanitize_files(settings, dry_run=False)
    deleted = [r for r in results if r.action == "deleted_duplicate"]
    assert len(deleted) == 1
    assert not (movies / "Avatar : De feu-poster.jpg").exists()
    assert (movies / "Avatar De feu-poster.jpg").read_bytes() == b"good"


def test_renames_directory_with_colon(tmp_path, settings):
    """Directory with : in name → renamed."""
    movies = tmp_path / "001-MOVIES"
    movies.mkdir(parents=True)
    bad_dir = movies / "Spirale : L'Héritage de Saw (2021)"
    bad_dir.mkdir()
    (bad_dir / "movie.nfo").write_text("<movie/>")

    results = sanitize_files(settings, dry_run=False)
    renamed_dirs = [r for r in results if r.action == "renamed" and "Spirale" in (r.old_name or "")]
    assert len(renamed_dirs) == 1
    assert (movies / "Spirale L'Héritage de Saw (2021)").exists()  # single space


def test_deletes_ds_store(tmp_path, settings):
    """All .DS_Store files are removed recursively."""
    movies = tmp_path / "001-MOVIES" / "Film (2025)"
    movies.mkdir(parents=True)
    (movies / ".DS_Store").write_bytes(b"\x00")
    actors = movies / ".actors"
    actors.mkdir()
    (actors / ".DS_Store").write_bytes(b"\x00")

    results = sanitize_files(settings, dry_run=False)
    ds = [r for r in results if r.action == "deleted_ds_store"]
    assert len(ds) == 2


def test_deletes_resource_forks(tmp_path, settings):
    """._* resource fork files are removed."""
    movies = tmp_path / "001-MOVIES" / "Film (2025)"
    movies.mkdir(parents=True)
    (movies / "._Film.mkv").write_bytes(b"\x00")

    results = sanitize_files(settings, dry_run=False)
    deleted = [r for r in results if r.action == "deleted_resource_fork"]
    assert len(deleted) == 1


def test_dry_run_no_changes(tmp_path, settings):
    """Dry run: report actions but don't modify filesystem."""
    movies = tmp_path / "001-MOVIES" / "Film (2025)"
    movies.mkdir(parents=True)
    colon_file = movies / "Film : Title-poster.jpg"
    colon_file.write_bytes(b"\x00")

    results = sanitize_files(settings, dry_run=True)
    assert len(results) > 0
    assert colon_file.exists()  # NOT modified


def test_idempotent_second_run(tmp_path, settings):
    """Second run after sanitization → 0 actions."""
    movies = tmp_path / "001-MOVIES" / "Film (2025)"
    movies.mkdir(parents=True)
    (movies / "Film : Title-poster.jpg").write_bytes(b"\x00")

    sanitize_files(settings, dry_run=False)  # Run 1: fix
    results2 = sanitize_files(settings, dry_run=False)  # Run 2: no-op
    actions = [r for r in results2 if r.action != "skipped"]
    assert len(actions) == 0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python -m pytest tests/enforce/test_file_sanitizer.py -v
```

- [ ] **Step 4: Implement `file_sanitizer.py`**

```python
# personalscraper/enforce/file_sanitizer.py
"""Sanitize filenames for NTFS compatibility and remove macOS metadata.

Renames files/directories containing NTFS-illegal characters,
removes .DS_Store and ._ resource fork files. Processes directories
bottom-up to handle nested renames correctly.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.text_utils import sanitize_filename

logger = logging.getLogger(__name__)

_FILENAME_ILLEGAL_CHARS = set('<>:"/\\|?*')


@dataclass
class SanitizeResult:
    """Result of sanitizing a single file or directory."""

    path: Path
    action: str  # "renamed", "deleted_duplicate", "deleted_ds_store",
    #              "deleted_resource_fork", "skipped"
    old_name: str | None = None
    new_name: str | None = None


def _has_illegal_chars(name: str) -> bool:
    """Check if a filename contains NTFS-illegal characters."""
    return any(c in _FILENAME_ILLEGAL_CHARS for c in name)


def sanitize_files(
    settings: Settings, dry_run: bool = False,
) -> list[SanitizeResult]:
    """Sanitize all filenames in staging categories.

    Processes 001-MOVIES/ and 002-TVSHOWS/ recursively.
    Renames NTFS-illegal characters, removes .DS_Store and ._ files.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, log actions without modifying filesystem.

    Returns:
        List of SanitizeResult for each action taken.
    """
    results: list[SanitizeResult] = []
    staging = settings.staging_dir

    for dir_name in (settings.movies_dir_name, settings.tvshows_dir_name):
        cat_dir = staging / dir_name
        if not cat_dir.exists():
            continue
        results.extend(_sanitize_directory(cat_dir, dry_run))

    return results


def _sanitize_directory(
    root: Path, dry_run: bool,
) -> list[SanitizeResult]:
    """Sanitize all files and dirs under root.

    Processes bottom-up (deepest files first) so that directory
    renames don't invalidate paths of already-processed children.

    Args:
        root: Directory to scan.
        dry_run: Preview mode.

    Returns:
        List of actions taken.
    """
    results: list[SanitizeResult] = []

    # Collect all paths bottom-up (files first, then dirs deepest-first)
    all_files = []
    all_dirs = []
    for item in root.rglob("*"):
        if item.is_file():
            all_files.append(item)
        elif item.is_dir():
            all_dirs.append(item)

    # Sort dirs by depth descending (deepest first) for safe renaming
    all_dirs.sort(key=lambda p: len(p.parts), reverse=True)

    # 1. Process files
    for f in all_files:
        # Delete .DS_Store
        if f.name == ".DS_Store":
            if not dry_run:
                try:
                    f.unlink()
                except OSError:
                    pass
            results.append(SanitizeResult(
                path=f, action="deleted_ds_store", old_name=f.name,
            ))
            continue

        # Delete ._ resource forks
        if f.name.startswith("._"):
            if not dry_run:
                try:
                    f.unlink()
                except OSError:
                    pass
            results.append(SanitizeResult(
                path=f, action="deleted_resource_fork", old_name=f.name,
            ))
            continue

        # Rename NTFS-illegal filenames
        if _has_illegal_chars(f.name):
            sanitized = sanitize_filename(f.name)
            target = f.parent / sanitized
            if target.exists():
                # Sanitized version already exists → delete legacy
                if not dry_run:
                    try:
                        f.unlink()
                    except OSError as exc:
                        logger.warning("Cannot delete duplicate %s: %s", f.name, exc)
                results.append(SanitizeResult(
                    path=f, action="deleted_duplicate",
                    old_name=f.name, new_name=sanitized,
                ))
            else:
                # Rename to sanitized
                if not dry_run:
                    try:
                        f.rename(target)
                    except OSError as exc:
                        logger.warning("Cannot rename %s: %s", f.name, exc)
                results.append(SanitizeResult(
                    path=f, action="renamed",
                    old_name=f.name, new_name=sanitized,
                ))

    # 2. Process directories (bottom-up)
    for d in all_dirs:
        if not d.exists():  # may have been moved by parent rename
            continue
        if _has_illegal_chars(d.name):
            sanitized = sanitize_filename(d.name)
            target = d.parent / sanitized
            if target.exists():
                logger.warning(
                    "Cannot rename dir %s → %s: target exists", d.name, sanitized,
                )
            else:
                if not dry_run:
                    try:
                        d.rename(target)
                    except OSError as exc:
                        logger.warning("Cannot rename dir %s: %s", d.name, exc)
                results.append(SanitizeResult(
                    path=d, action="renamed",
                    old_name=d.name, new_name=sanitized,
                ))

    return results
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/enforce/test_file_sanitizer.py -v
```

Expected: ALL PASS.

- [ ] **Step 6: Commit**

```bash
git add personalscraper/enforce/__init__.py personalscraper/enforce/file_sanitizer.py \
       tests/enforce/__init__.py tests/enforce/test_file_sanitizer.py
git commit -m "v13.2.1: Add file_sanitizer — rename NTFS-illegal chars, remove .DS_Store"
```

---

### Task 7: `structure_validator.py`

**Files:**

- Create: `personalscraper/enforce/structure_validator.py`
- Create: `tests/enforce/test_structure_validator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/enforce/test_structure_validator.py

import pytest
from pathlib import Path
from personalscraper.enforce.structure_validator import validate_structure, StructureResult


@pytest.fixture
def settings(tmp_path):
    from unittest.mock import MagicMock
    s = MagicMock()
    s.staging_dir = tmp_path
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    return s


def test_movie_extra_nfo_removed(tmp_path, settings):
    """Movie with 2 NFOs: residual removed, correct kept."""
    movie = tmp_path / "001-MOVIES" / "Scream 7 (2026)"
    movie.mkdir(parents=True)
    good = movie / "Scream 7.nfo"
    good.write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    bad = movie / "Scream.7.2026.MULTI.nfo"
    bad.write_text("<movie/>")
    (movie / "Scream 7.mkv").write_bytes(b"\x00")

    results = validate_structure(settings, dry_run=False)
    repaired = [r for r in results if r.action == "repaired"]
    assert len(repaired) == 1
    assert good.exists()
    assert not bad.exists()


def test_movie_duplicate_artwork_legacy_removed(tmp_path, settings):
    """Artwork with same type but different names: keep sanitized, delete legacy."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film-poster.jpg").write_bytes(b"good")
    (movie / "Film-poster (1).jpg").write_bytes(b"dup")  # duplicate poster

    results = validate_structure(settings, dry_run=False)
    repaired = [r for r in results if r.action == "repaired"]
    assert len(repaired) == 1
    assert not (movie / "Film-poster (1).jpg").exists()


def test_tvshow_empty_torrent_subdir_removed(tmp_path, settings):
    """Empty torrent subdirectory removed."""
    show = tmp_path / "002-TVSHOWS" / "Show (2025)"
    show.mkdir(parents=True)
    (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
    empty_dir = show / "Show.S01E01.MULTi.1080p"
    empty_dir.mkdir()  # empty torrent dir (episodes already moved)

    results = validate_structure(settings, dry_run=False)
    assert not empty_dir.exists()


def test_clean_movie_no_action(tmp_path, settings):
    """Clean movie → validated, no fixes."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film-poster.jpg").write_bytes(b"\x00")
    (movie / "Film-landscape.jpg").write_bytes(b"\x00")

    results = validate_structure(settings, dry_run=False)
    validated = [r for r in results if r.action == "validated"]
    assert len(validated) == 1


def test_idempotent_second_run(tmp_path, settings):
    """Run 2 after fixes → no more repairs."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
    (movie / "Film.mkv").write_bytes(b"\x00")
    (movie / "Film.MULTI.nfo").write_text("<movie/>")

    validate_structure(settings, dry_run=False)  # Run 1: fix
    results2 = validate_structure(settings, dry_run=False)  # Run 2
    repaired = [r for r in results2 if r.action == "repaired"]
    assert len(repaired) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/enforce/test_structure_validator.py -v
```

- [ ] **Step 3: Implement `structure_validator.py`**

```python
# personalscraper/enforce/structure_validator.py
"""Validate and fix directory structure for staging media items.

Checks NFO count, artwork duplicates, season structure, and torrent
residuals. Fixes what can be fixed, reports what can't.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.config import Settings
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS
from personalscraper.text_utils import sanitize_filename

logger = logging.getLogger(__name__)

_SEASON_DIR_RE = re.compile(r"^Saison \d+$")
# Artwork type suffixes used in NamingPatterns
_ARTWORK_SUFFIXES = {
    "-poster", "-fanart", "-banner", "-landscape",
    "-clearlogo", "-clearart", "-discart", "-thumb",
}


@dataclass
class StructureResult:
    """Result of validating/fixing structure for one media item."""

    path: Path
    media_type: str  # "movie" or "tvshow"
    action: str  # "validated", "repaired", "error"
    fixes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_structure(
    settings: Settings, dry_run: bool = False,
) -> list[StructureResult]:
    """Validate and fix directory structure for all staging items.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, log actions without modifying filesystem.

    Returns:
        List of StructureResult for each media item.
    """
    results: list[StructureResult] = []
    staging = settings.staging_dir

    movies_dir = staging / settings.movies_dir_name
    if movies_dir.exists():
        for folder in sorted(movies_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                results.append(_validate_movie(folder, dry_run))

    tvshows_dir = staging / settings.tvshows_dir_name
    if tvshows_dir.exists():
        for folder in sorted(tvshows_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                results.append(_validate_tvshow(folder, dry_run))

    return results


def _validate_movie(movie_dir: Path, dry_run: bool) -> StructureResult:
    """Validate a single movie directory."""
    result = StructureResult(path=movie_dir, media_type="movie", action="validated")

    # Extract expected title from folder name (strip year)
    title = re.sub(r"\s*\(\d{4}\)\s*$", "", movie_dir.name).strip()
    expected_nfo = sanitize_filename(title) + ".nfo"

    # Check NFO count — remove extras
    nfos = list(movie_dir.glob("*.nfo"))
    for nfo in nfos:
        if nfo.name != expected_nfo:
            if not dry_run:
                try:
                    nfo.unlink()
                except OSError as exc:
                    logger.warning("Cannot delete extra NFO %s: %s", nfo.name, exc)
                    continue
            result.fixes.append(f"Removed extra NFO: {nfo.name}")

    # Check artwork duplicates — same type, different names
    artwork_by_type: dict[str, list[Path]] = {}
    for f in movie_dir.iterdir():
        if not f.is_file():
            continue
        for suffix in _ARTWORK_SUFFIXES:
            if suffix in f.stem:
                artwork_by_type.setdefault(suffix, []).append(f)
                break

    for art_type, files in artwork_by_type.items():
        if len(files) > 1:
            # Keep the one with the expected sanitized name
            expected_stem = sanitize_filename(title) + art_type
            keep = None
            for f in files:
                if f.stem == expected_stem:
                    keep = f
                    break
            if keep is None:
                keep = files[0]  # fallback: keep first
            for f in files:
                if f != keep:
                    if not dry_run:
                        try:
                            f.unlink()
                        except OSError:
                            continue
                    result.fixes.append(f"Removed duplicate artwork: {f.name}")

    if result.fixes:
        result.action = "repaired"
    return result


def _validate_tvshow(show_dir: Path, dry_run: bool) -> StructureResult:
    """Validate a single TV show directory."""
    result = StructureResult(path=show_dir, media_type="tvshow", action="validated")

    # Remove empty non-season subdirs (leftover torrent dirs)
    for subdir in list(show_dir.iterdir()):
        if (
            subdir.is_dir()
            and not subdir.name.startswith(".")
            and not _SEASON_DIR_RE.match(subdir.name)
        ):
            # Check if empty (no files recursively)
            has_files = any(subdir.rglob("*"))
            if not has_files:
                if not dry_run:
                    try:
                        subdir.rmdir()
                    except OSError:
                        continue
                result.fixes.append(f"Removed empty torrent dir: {subdir.name}")

    # Check for missing tvshow.nfo
    if not (show_dir / "tvshow.nfo").exists():
        result.warnings.append("Missing tvshow.nfo")

    if result.fixes:
        result.action = "repaired"
    return result
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/enforce/test_structure_validator.py -v
```

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/enforce/structure_validator.py tests/enforce/test_structure_validator.py
git commit -m "v13.2.2: Add structure_validator — enforce NFO/artwork/season conventions"
```

---

### Task 8: `coherence_checker.py`

**Files:**

- Create: `personalscraper/enforce/coherence_checker.py`
- Create: `tests/enforce/test_coherence_checker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/enforce/test_coherence_checker.py

import pytest
from pathlib import Path
from personalscraper.enforce.coherence_checker import check_coherence, CoherenceResult


@pytest.fixture
def settings(tmp_path):
    from unittest.mock import MagicMock
    s = MagicMock()
    s.staging_dir = tmp_path
    s.movies_dir_name = "001-MOVIES"
    s.tvshows_dir_name = "002-TVSHOWS"
    return s


def test_tvshow_in_movies_warns(tmp_path, settings):
    """tvshow.nfo in 001-MOVIES → warning."""
    movie = tmp_path / "001-MOVIES" / "Fake Show (2026)"
    movie.mkdir(parents=True)
    (movie / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')

    results = check_coherence(settings, dry_run=False)
    warns = [w for r in results for w in r.warnings if "wrong category" in w.lower()]
    assert len(warns) >= 1


def test_nfo_missing_both_ids_warns(tmp_path, settings):
    """NFO without TMDB or IMDB ID → warning."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text("<movie><title>Film</title></movie>")

    results = check_coherence(settings, dry_run=False)
    warns = [w for r in results for w in r.warnings if "missing" in w.lower() and "id" in w.lower()]
    assert len(warns) >= 1


def test_clean_items_no_warnings(tmp_path, settings):
    """Properly structured items → no warnings."""
    movie = tmp_path / "001-MOVIES" / "Film (2025)"
    movie.mkdir(parents=True)
    (movie / "Film.nfo").write_text(
        '<movie><uniqueid type="tmdb">123</uniqueid>'
        '<uniqueid type="imdb">tt123</uniqueid></movie>'
    )

    results = check_coherence(settings, dry_run=False)
    warns = [w for r in results for w in r.warnings]
    assert len(warns) == 0


def test_genre_emission_in_series_warns(tmp_path, settings):
    """NFO with genre 'Émission' in 002-TVSHOWS → warning about emissions category."""
    show = tmp_path / "002-TVSHOWS" / "Show (2026)"
    show.mkdir(parents=True)
    (show / "tvshow.nfo").write_text(
        '<tvshow><genre>Émission</genre>'
        '<uniqueid type="tmdb">312697</uniqueid></tvshow>'
    )

    results = check_coherence(settings, dry_run=False)
    warns = [w for r in results for w in r.warnings if "emission" in w.lower()]
    assert len(warns) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/enforce/test_coherence_checker.py -v
```

- [ ] **Step 3: Implement `coherence_checker.py`**

```python
# personalscraper/enforce/coherence_checker.py
"""Cross-step coherence checker for staging media.

Read-only checker that parses NFOs, verifies genre_mapper consistency,
and checks sort↔process coherence. Produces warnings, never modifies
the filesystem.
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class CoherenceResult:
    """Result of coherence check for one media item."""

    path: Path
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_coherence(
    settings: Settings, dry_run: bool = False,
) -> list[CoherenceResult]:
    """Check cross-step coherence for all staging items.

    Args:
        settings: Pipeline configuration.
        dry_run: No effect (coherence check is read-only).

    Returns:
        List of CoherenceResult for each media item.
    """
    results: list[CoherenceResult] = []
    staging = settings.staging_dir

    movies_dir = staging / settings.movies_dir_name
    if movies_dir.exists():
        for folder in sorted(movies_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                results.append(_check_movie(folder))

    tvshows_dir = staging / settings.tvshows_dir_name
    if tvshows_dir.exists():
        for folder in sorted(tvshows_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                results.append(_check_tvshow(folder))

    return results


def _check_movie(movie_dir: Path) -> CoherenceResult:
    """Check coherence for a movie directory."""
    result = CoherenceResult(path=movie_dir)

    # Sort↔Process: movie dir should NOT have tvshow.nfo
    if (movie_dir / "tvshow.nfo").exists():
        result.warnings.append(
            f"Wrong category: {movie_dir.name} has tvshow.nfo but is in MOVIES"
        )
    result.checks.append("sort_process_coherence")

    # Find movie NFO and check IDs
    nfos = list(movie_dir.glob("*.nfo"))
    if nfos:
        _check_nfo_ids(nfos[0], result)

    return result


def _check_tvshow(show_dir: Path) -> CoherenceResult:
    """Check coherence for a TV show directory."""
    result = CoherenceResult(path=show_dir)

    # Sort↔Process: tvshow dir should have tvshow.nfo, not just {Title}.nfo
    nfo_path = show_dir / "tvshow.nfo"
    if not nfo_path.exists():
        movie_nfos = [f for f in show_dir.glob("*.nfo") if f.name != "tvshow.nfo"]
        if movie_nfos:
            result.warnings.append(
                f"Wrong category: {show_dir.name} has movie NFO but is in TVSHOWS"
            )
    else:
        _check_nfo_ids(nfo_path, result)
        _check_genre_coherence(nfo_path, result)

    result.checks.append("sort_process_coherence")
    return result


def _check_nfo_ids(nfo_path: Path, result: CoherenceResult) -> None:
    """Check that NFO has at least one valid ID (TMDB or IMDB)."""
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314
    except (ET.ParseError, OSError):
        result.warnings.append(f"Cannot parse NFO: {nfo_path.name}")
        return

    has_tmdb = False
    has_imdb = False
    for uid in root.findall("uniqueid"):
        uid_type = uid.get("type", "")
        if uid_type == "tmdb" and uid.text and uid.text.strip():
            has_tmdb = True
        elif uid_type == "imdb" and uid.text and uid.text.strip():
            has_imdb = True

    if not has_tmdb and not has_imdb:
        result.warnings.append(f"Missing IDs: no TMDB or IMDB in {nfo_path.name}")

    result.checks.append("nfo_ids")


def _check_genre_coherence(nfo_path: Path, result: CoherenceResult) -> None:
    """Check if genre suggests a different category (e.g., emissions vs series)."""
    try:
        from personalscraper.genre_mapper import GenreMapper

        mapper = GenreMapper()
        category = mapper.categorize_from_nfo(nfo_path, media_type="tvshow")
        if category and category == "emissions":
            result.warnings.append(
                f"Genre suggests 'emissions' not 'series' for {result.path.name} "
                f"— consider moving to emissions category"
            )
    except Exception as exc:
        logger.debug("Genre check failed for %s: %s", nfo_path.name, exc)

    result.checks.append("genre_coherence")
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/enforce/test_coherence_checker.py -v
```

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/enforce/coherence_checker.py tests/enforce/test_coherence_checker.py
git commit -m "v13.2.3: Add coherence_checker — cross-step genre/ID/sort consistency"
```

---

### Task 9: `enforce/run.py` orchestrator

**Files:**

- Create: `personalscraper/enforce/run.py`
- Create: `tests/enforce/test_run_enforce.py`

- [ ] **Step 1: Write failing tests**

Test the orchestrator calls sanitize → structure → coherence in order
and produces a valid StepReport.

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement `run.py`**

```python
# personalscraper/enforce/run.py
"""Enforce step runner: entry point for the enforce pipeline step.

Executes three sub-components in order:
1. file_sanitizer — NTFS filenames, .DS_Store, resource forks
2. structure_validator — NFO count, artwork, season structure
3. coherence_checker — genre, IDs, sort↔process consistency

Each component works on the state left by the previous one.
"""

import logging

from personalscraper.config import Settings
from personalscraper.enforce.coherence_checker import check_coherence
from personalscraper.enforce.file_sanitizer import sanitize_files
from personalscraper.enforce.structure_validator import validate_structure
from personalscraper.models import StepReport

logger = logging.getLogger(__name__)


def run_enforce(
    settings: Settings,
    dry_run: bool = False,
) -> StepReport:
    """Run the enforce pipeline step.

    Args:
        settings: Pipeline configuration.
        dry_run: If True, preview without modifying filesystem.

    Returns:
        StepReport with enforce counts and details.
    """
    sanitize_results = sanitize_files(settings, dry_run)
    structure_results = validate_structure(settings, dry_run)
    coherence_results = check_coherence(settings, dry_run)

    # Build StepReport
    success = 0
    warnings_list: list[str] = []
    details: list[str] = []

    # Count sanitize actions
    sanitize_actions = [r for r in sanitize_results if r.action != "skipped"]
    success += len(sanitize_actions)
    for r in sanitize_actions:
        details.append(f"[sanitize:{r.action}] {r.old_name} → {r.new_name or 'deleted'}")

    # Count structure fixes
    for r in structure_results:
        if r.action == "repaired":
            success += 1
            for fix in r.fixes:
                details.append(f"[structure:fix] {r.path.name}: {fix}")
        if r.warnings:
            for w in r.warnings:
                warnings_list.append(f"{r.path.name}: {w}")

    # Count coherence warnings
    for r in coherence_results:
        for w in r.warnings:
            warnings_list.append(f"[coherence] {r.path.name}: {w}")

    skip_count = (
        len([r for r in sanitize_results if r.action == "skipped"])
        + len([r for r in structure_results if r.action == "validated"])
    )

    return StepReport(
        name="enforce",
        success_count=success,
        skip_count=skip_count,
        error_count=0,
        warnings=warnings_list,
        details=details,
    )
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/enforce/ -v
```

- [ ] **Step 5: Commit**

```bash
git add personalscraper/enforce/run.py tests/enforce/test_run_enforce.py
git commit -m "v13.2.4: Add enforce orchestrator — sanitize → structure → coherence"
```

---

## Phase 3 — Integration + Fixes

### Task 10: Pipeline integration (7→8 steps)

**Files:**

- Modify: `personalscraper/pipeline.py`
- Modify: `personalscraper/models.py`
- Modify: `personalscraper/cli.py`

- [ ] **Step 1: Add ENFORCE to `pipeline.py`**

In `Pipeline.run()`, between `_run_process_phase()` and verify:

```python
        # Phase 4: ENFORCE (validate and correct conventions)
        from personalscraper.enforce.run import run_enforce

        self._run_step(
            "enforce",
            lambda: run_enforce(self.settings, dry_run=self.dry_run),
            report,
        )
```

Update `_step_icon()`:

```python
        icons = {
            "ingest": "[cyan]1/8[/cyan]",
            "sort": "[cyan]2/8[/cyan]",
            "clean": "[cyan]3/8[/cyan]",
            "scrape": "[cyan]4/8[/cyan]",
            "cleanup": "[cyan]5/8[/cyan]",
            "enforce": "[cyan]6/8[/cyan]",
            "verify": "[cyan]7/8[/cyan]",
            "dispatch": "[cyan]8/8[/cyan]",
        }
```

Update module docstring and class docstring: "5 phases producing 7 StepReports" → "6 phases producing 8 StepReports".
Also update in `Pipeline.run()` docstring: "7 StepReports" → "8 StepReports".
Also update in `cli.py`: comment "# 7-step sequential flow" → "8-step", "# 7 steps" → "8 steps" (lines 317, 333).

- [ ] **Step 2: Add enforce icon to `models.py`**

In `PipelineReport.to_html()` `step_icons` dict:

```python
            "enforce": "\U0001f527",   # 🔧
```

Update `StepReport.name` docstring to include "enforce".

- [ ] **Step 3: Add `enforce` CLI command and update `verify` in `cli.py`**

```python
@app.command()
@handle_cli_errors
def enforce(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without modifying"),
) -> None:
    """Enforce staging conventions: sanitize filenames, validate structure, check coherence."""
    from personalscraper.enforce.run import run_enforce

    console = state["console"]
    if not acquire_lock():
        console.print("[red]Another instance is running. Exiting.[/red]")
        raise typer.Exit(1)
    try:
        settings = get_settings()
        report = run_enforce(settings, dry_run=dry_run)
        console.print(
            f"Enforce: {report.success_count} fixed, "
            f"{report.skip_count} OK, {report.error_count} errors"
        )
    finally:
        release_lock()
```

Modify verify in pipeline to pass `fix=False`:

```python
    # In Pipeline._run_verify():
    def _run_verify(self) -> tuple[StepReport, list]:
        from personalscraper.verify.run import run_verify
        return run_verify(self.settings, dry_run=self.dry_run, fix=False)
```

- [ ] **Step 4: Run pipeline tests**

```bash
python -m pytest tests/test_pipeline.py tests/test_pipeline_integration.py tests/test_cli.py -v
```

- [ ] **Step 5: Commit**

```bash
git add personalscraper/pipeline.py personalscraper/models.py personalscraper/cli.py
git commit -m "v13.3.1: Integrate ENFORCE step — pipeline 7→8 steps, enforce CLI command"
```

---

### Task 11: Genre mapper fix (#12) + dispatch .DS_Store (#1)

**Files:**

- Modify: `personalscraper/genre_mapper.py`
- Modify: `personalscraper/dispatch/dispatcher.py`
- Test: `tests/verify/test_genre_mapper.py`

- [ ] **Step 1: Write failing test for genre mapper**

Root cause: TMDB returns genres in French (`language="fr-FR"` in tmdb_client.py).
The NFO contains `<genre>Émission</genre>` (not "Reality"). `_normalize("Émission")`
strips accents → `"emission"`, but "emission" is NOT in `_REALITY_NAMES`.
The English `"reality"` IS in `_REALITY_NAMES` but TMDB never returns it in fr-FR locale.

```python
# tests/verify/test_genre_mapper.py — add tests
from personalscraper.genre_mapper import GenreMapper


def test_categorize_from_nfo_french_emission_is_emissions(tmp_path):
    """NFO with French TMDB genre 'Émission' → emissions, not series."""
    nfo = tmp_path / "tvshow.nfo"
    nfo.write_text(
        '<tvshow><genre>Émission</genre>'
        '<uniqueid type="tmdb">312697</uniqueid></tvshow>'
    )
    mapper = GenreMapper()
    result = mapper.categorize_from_nfo(nfo, media_type="tvshow")
    assert result == "emissions"


def test_categorize_tvshow_french_divertissement(tmp_path):
    """French genre 'Divertissement' → emissions."""
    mapper = GenreMapper()
    result = mapper.categorize_tvshow(["Divertissement"])
    assert result == "emissions"
```

- [ ] **Step 2: Fix `_REALITY_NAMES` in `genre_mapper.py`**

The fix: add French TMDB genre variants returned by `language="fr-FR"`.
The existing `"reality"` and `"realite"` cover English and accented French,
but TMDB fr-FR returns different genre names entirely.

Look at the `_REALITY_NAMES` attribute on the `GenreMapper` class (it's a set attribute,
not a frozenset). Add the French variants:

```python
# In GenreMapper.__init__() or wherever _REALITY_NAMES is defined:
# Add these French TMDB genre name variants:
"emission",        # TMDB fr-FR: "Émission" → normalized "emission"
"divertissement",  # TMDB fr-FR: entertainment/variety
"jeu televise",    # TMDB fr-FR: game show
```

Keep `"reality"`, `"realite"`, `"talk show"`, `"talk"`, `"news"` as they already are.

- [ ] **Step 3: Add rsync exclude for .DS_Store in `dispatcher.py`**

Find the rsync command construction and add excludes:

```python
# In _build_rsync_cmd() or wherever rsync args are built:
# Add to the rsync args list:
"--exclude=.DS_Store", "--exclude=._*",
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/verify/test_genre_mapper.py tests/dispatch/ -v
```

- [ ] **Step 5: Commit**

```bash
git add personalscraper/genre_mapper.py personalscraper/dispatch/dispatcher.py \
       tests/verify/test_genre_mapper.py
git commit -m "v13.3.2: Fix genre mapper Reality→emissions, rsync exclude .DS_Store"
```

---

### Task 12: Update CLAUDE.md + verify run.py deprecation

**Files:**

- Modify: `CLAUDE.md`
- Modify: `personalscraper/verify/run.py`

- [ ] **Step 1: Update CLAUDE.md**

Update pipeline diagram, directory structure (add enforce/), versions table (add V13),
commands section (add `personalscraper enforce`), step count references.

- [ ] **Step 2: Add deprecation warning for verify `--fix` in pipeline mode**

In `run_verify()`, if `fix=False` is passed, that's the pipeline path (no warning needed).
In CLI standalone with `--fix`, add a warning:

```python
# cli.py verify command, after settings:
if fix:
    import warnings
    warnings.warn(
        "verify --fix is deprecated. Use 'personalscraper enforce' instead.",
        DeprecationWarning,
        stacklevel=1,
    )
    console.print("[yellow]Warning: --fix is deprecated. Use 'personalscraper enforce' instead.[/yellow]")
```

- [ ] **Step 3: Commit**

```bash
git add -f CLAUDE.md personalscraper/verify/run.py personalscraper/cli.py
git commit -m "v13.3.3: Update CLAUDE.md for V13, deprecate verify --fix"
```

---

## Phase 4 — E2E Idempotence Tests

### Task 13: Idempotence fixture tests + E2E real tests

**Files:**

- Create: `tests/enforce/test_idempotence.py`
- Modify: `pyproject.toml` (add `e2e_idempotence` marker)

- [ ] **Step 1: Register `e2e_idempotence` marker**

In `pyproject.toml`, add to `[tool.pytest.ini_options]` markers list:

```toml
"e2e_idempotence: E2E idempotence tests on real staging data (manual only)",
```

- [ ] **Step 2: Write idempotence fixture tests**

Each test: setup fixture → run ENFORCE → assert fixed → run again → assert no-op.
Cover all 9 fixture types from the design. Each test is self-contained with its
own tmp_path fixture setup.

- [ ] **Step 3: Write E2E real idempotence tests**

```python
# tests/enforce/test_idempotence.py — add at end of file

import pytest
from personalscraper.config import Settings
from personalscraper.enforce.run import run_enforce


@pytest.mark.e2e_idempotence
class TestRealStagingIdempotence:
    """Run enforce on actual staging data. Manual only."""

    def test_enforce_detects_and_fixes(self):
        """First run should fix known issues from staging."""
        settings = Settings()
        report = run_enforce(settings, dry_run=False)
        # At least some actions should be taken on real staging
        print(f"Run 1: {report.success_count} fixed, {report.skip_count} OK")
        print(f"Details: {report.details}")

    def test_enforce_second_run_noop(self):
        """Second run should change nothing (idempotent)."""
        settings = Settings()
        report = run_enforce(settings, dry_run=False)
        assert report.success_count == 0, (
            f"Expected no-op on second run, got {report.success_count} fixes: "
            f"{report.details}"
        )
```

- [ ] **Step 4: Run fixture tests (NOT e2e_idempotence)**

```bash
python -m pytest tests/enforce/test_idempotence.py -v -m "not e2e_idempotence"
```

- [ ] **Step 5: Commit**

```bash
git add tests/enforce/test_idempotence.py pyproject.toml
git commit -m "v13.4.1: E2E idempotence tests — fixtures + real staging with marker"
```

---

### Task 14: Full regression suite

- [ ] **Step 1: Run ALL tests**

```bash
python -m pytest tests/ -x -q
```

Expected: ALL PASS.

- [ ] **Step 2: Run with coverage**

```bash
python -m pytest tests/ --cov=personalscraper --cov-report=term-missing -q
```

Verify enforce/ module has >80% coverage.

- [ ] **Step 3: Commit any fixes**

---

## Phase 5 — Report + Finalize

### Task 15: V14+ backlog + final commit

**Files:**

- Create: `docs/v13-pipeline-correctness/BACKLOG-V14.md`

- [ ] **Step 1: Write backlog from audit findings**

Document features classified as MISSING in the Phase 0 audit that are out of scope
for V13. Include the complete removal of verify `--fix` (deprecated in V13).

- [ ] **Step 2: Update `docs/IMPLEMENTATION.md`**

Mark V13 as DONE with links to design, plan, and audit docs.

- [ ] **Step 3: Final commit**

```bash
git add -f docs/v13-pipeline-correctness/BACKLOG-V14.md docs/IMPLEMENTATION.md
git commit -m "v13.5.1: V14+ backlog report, update IMPLEMENTATION.md — V13 complete"
```

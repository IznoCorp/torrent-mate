# match-guard — Phase 2: Episode-Filename Fallback for Degenerate Show Titles (Unit 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When the folder title parsed by `_parse_folder_name` is empty or is a pure season token (matches `^\s*S\d+(E\d+)?$`), re-derive the show title from the first episode file via guessit/NameCleaner, strip the `SxxEyy` token, and use that recovered title for the provider query — so `" S03"` folders containing `"The Orville - S3E01.mkv"` files correctly query `"The Orville"`.

**Architecture:** Add a `is_degenerate_title(title)` predicate in `personalscraper/scraper/classifier.py` (near `_parse_folder_name`). Add a `_recover_title_from_episodes(show_dir)` helper in `personalscraper/scraper/tv_service.py` that lists video files, picks the first, runs `NameCleaner.clean()`, strips the `SxxEyy` suffix token, and returns the recovered title or `None`. Call both from `TvServiceMixin.scrape_tvshow` immediately after line 110 (`title, year = _parse_folder_name(show_dir.name)`).

**Tech Stack:** Python 3.12, `personalscraper.sorter.cleaner.NameCleaner` (wraps guessit), `personalscraper.core.media_types.VIDEO_EXTENSIONS`, `re`, pytest.

---

## File map

- Modify: `personalscraper/scraper/classifier.py` — add `is_degenerate_title(title: str) -> bool` helper (near line 78, after `_FOLDER_PATTERN`)
- Modify: `personalscraper/scraper/tv_service.py` — add `_recover_title_from_episodes(show_dir: Path) -> str | None` helper function (module-level, before `TvServiceMixin`), call it from `scrape_tvshow` after line 110
- Test: `tests/scraper/test_confidence_match_guard.py` — extend with AC-2 and AC-6 tests (same file used in Phase 1)
- Test: `tests/scraper/test_classifier_match_guard.py` — new file covering `is_degenerate_title` unit tests (AC-6)

---

## Task 1: Write failing tests for `is_degenerate_title` (AC-6)

**Files:**

- Create: `tests/scraper/test_classifier_match_guard.py`

- [ ] **Step 1.1: Create the test file**

```python
"""Unit tests for is_degenerate_title — AC-6 of the match-guard feature.

AC-6: is_degenerate_title returns True for ' S03'/'S3'/'S01E01',
      False for 'FROM'/'The Hack'/'Among'/'Top Chef France'/'S.W.A.T.'/'Sense8'.
"""

import pytest

from personalscraper.scraper.classifier import is_degenerate_title


class TestIsDegenerateTitle:
    """Tests for the degenerate-title predicate (AC-6)."""

    @pytest.mark.parametrize(
        "title",
        [
            " S03",       # Orville case — leading space + season token
            "S03",        # no leading space
            "S3",         # single-digit season
            "S01E01",     # season + episode token
            "S12E99",     # large numbers
            "  S02  ",    # extra whitespace
        ],
    )
    def test_degenerate_titles_return_true(self, title: str) -> None:
        """Pure season/episode tokens must be recognised as degenerate."""
        assert is_degenerate_title(title) is True, (
            f"Expected is_degenerate_title({title!r}) to be True"
        )

    @pytest.mark.parametrize(
        "title",
        [
            "FROM",             # short but legit — single word, no Sxx pattern
            "The Hack",         # short legit title
            "Among",            # guessit-stripped remainder — still not a season token
            "Top Chef France",  # multiword legit
            "S.W.A.T.",         # starts with S but has dots — not a season token
            "Sense8",           # starts with S, has digit, but not Sxx form
            "S Club 7",         # starts with S, has digit, but not Sxx form
            "S-Town",           # starts with S but not Sxx form
            "S4C",              # channel name — not Sxx form
            "Station 19",       # legit show title with digits
        ],
    )
    def test_legit_titles_return_false(self, title: str) -> None:
        """Legit show titles must NOT be classified as degenerate."""
        assert is_degenerate_title(title) is False, (
            f"Expected is_degenerate_title({title!r}) to be False "
            f"(would wrongly trigger fallback and break this legit title)"
        )
```

- [ ] **Step 1.2: Run to confirm tests FAIL (function not yet defined)**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_classifier_match_guard.py -v 2>&1 | tail -15
```

Expected: ImportError or AttributeError — `is_degenerate_title` does not exist yet.

---

## Task 2: Implement `is_degenerate_title` in `classifier.py`

**Files:**

- Modify: `personalscraper/scraper/classifier.py`

- [ ] **Step 2.1: Read the top of classifier.py to see the existing regex block**

Read `personalscraper/scraper/classifier.py` lines 70-80 (the `_FOLDER_PATTERN` and `_SXXEXX_RE` definitions near line 72-73).

- [ ] **Step 2.2: Add `_DEGENERATE_TITLE_RE` and `is_degenerate_title` after the existing regexes**

Insert after line 75 (after `_EPISODE_FALLBACK_RE`), before `_parse_folder_name`:

```python
# Matches folder titles that are pure season or season+episode tokens with
# no show name — e.g. " S03", "S3", "S01E01". These trigger the episode-
# filename fallback in tv_service so the real show title can be recovered.
# Anchored with optional surrounding whitespace; must NOT match legit titles
# like "S.W.A.T.", "Sense8", "S Club 7", "S-Town" (verified in tests).
_DEGENERATE_TITLE_RE = re.compile(r"^\s*S\d+(E\d+)?\s*$", re.IGNORECASE)


def is_degenerate_title(title: str) -> bool:
    """Return True when ``title`` is a bare season/episode token with no show name.

    A degenerate title is one that matches ``^\s*S\d+(E\d+)?\s*$`` — for
    example `` S03``, ``S3``, ``S01E01``.  Such titles arise when the sort
    step could not parse the torrent name (e.g. a torrent named ``Saison 3``
    with no show title), leaving only the season token in the folder name.

    Legit titles that start with ``S`` followed by digits but are NOT season
    tokens — ``S.W.A.T.``, ``Sense8``, ``S Club 7``, ``S-Town``, ``S4C`` —
    do not match this pattern and correctly return False.

    Args:
        title: Show title as parsed from the staging folder name.

    Returns:
        True if the title is a degenerate season/episode token.
    """
    return bool(_DEGENERATE_TITLE_RE.match(title))
```

- [ ] **Step 2.3: Run the AC-6 tests — all must PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_classifier_match_guard.py -v 2>&1 | tail -20
```

Expected: 16 PASSes (6 degenerate True + 10 legit False).

- [ ] **Step 2.4: Commit the classifier change**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/scraper/classifier.py tests/scraper/test_classifier_match_guard.py && git commit -m "$(cat <<'EOF'
feat(match-guard): add is_degenerate_title predicate for season-token folders

Adds _DEGENERATE_TITLE_RE and is_degenerate_title() to classifier.py.
Regex ^\s*S\d+(E\d+)?\s*$ matches ' S03'/'S3'/'S01E01' but NOT
'S.W.A.T.'/'Sense8'/'S Club 7'/'S-Town'/'S4C' (verified in 16 tests).
EOF
)"
```

---

## Task 3: Write the failing AC-2 integration test (episode-filename fallback)

**Files:**

- Modify: `tests/scraper/test_confidence_match_guard.py` (extend, do not replace)

- [ ] **Step 3.1: Append the AC-2 test class to `tests/scraper/test_confidence_match_guard.py`**

Add at the end of the existing file:

```python
# ---------------------------------------------------------------------------
# AC-2 — Orville recovery: degenerate folder → episode-filename fallback
# ---------------------------------------------------------------------------


class TestAC2OrvilleRecovery:
    """AC-2: a season-token folder with Orville episode files recovers 'The Orville'."""

    def test_recover_title_from_episode_files(self, tmp_path: Path) -> None:
        """_recover_title_from_episodes returns 'The Orville' from episode filenames."""
        from pathlib import Path  # noqa: PLC0415 (re-imported for clarity in added block)

        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / " S03"
        show_dir.mkdir()
        # Create representative episode files matching the real torrent layout
        (show_dir / "The Orville - S3E01 - Some Episode.mkv").touch()
        (show_dir / "The Orville - S3E02 - Another Episode.mkv").touch()

        recovered = _recover_title_from_episodes(show_dir)
        assert recovered == "The Orville", (
            f"Expected 'The Orville', got {recovered!r}. "
            "NameCleaner.clean() on the first episode file should extract 'The Orville'."
        )

    def test_recover_title_strips_season_token(self, tmp_path: Path) -> None:
        """Recovered title must not contain 'S3'/'S03' residue."""
        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / "S03"
        show_dir.mkdir()
        (show_dir / "The Orville - S3E01.mkv").touch()

        recovered = _recover_title_from_episodes(show_dir)
        assert recovered is not None
        import re  # noqa: PLC0415
        assert not re.search(r"\bS\d+\b", recovered, re.IGNORECASE), (
            f"Recovered title still contains season token: {recovered!r}"
        )

    def test_no_episode_files_returns_none(self, tmp_path: Path) -> None:
        """Empty show dir with no video files returns None (no recovery possible)."""
        from personalscraper.scraper.tv_service import _recover_title_from_episodes

        show_dir = tmp_path / "S03"
        show_dir.mkdir()
        (show_dir / "subtitles.srt").touch()  # not a video file

        recovered = _recover_title_from_episodes(show_dir)
        assert recovered is None, (
            f"Expected None when no video files present, got {recovered!r}"
        )
```

Also add `from pathlib import Path` to the imports block at the top of the file (after the existing imports).

- [ ] **Step 3.2: Run to confirm AC-2 tests FAIL**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py::TestAC2OrvilleRecovery -v 2>&1 | tail -15
```

Expected: ImportError — `_recover_title_from_episodes` does not exist yet.

---

## Task 4: Implement `_recover_title_from_episodes` and wire into `scrape_tvshow`

**Files:**

- Modify: `personalscraper/scraper/tv_service.py`

- [ ] **Step 4.1: Read the imports block and the `scrape_tvshow` opening lines**

Read `personalscraper/scraper/tv_service.py` lines 1-55 (imports) and lines 101-115 (`scrape_tvshow` start, where `_parse_folder_name` is called on line 110).

- [ ] **Step 4.2: Add `_recover_title_from_episodes` module-level helper**

Insert after the `log = get_logger("scraper")` line (line 52) and before `_safe_get_rating` (line 55), adding the `re` import at the top of the file (it is already imported in classifier.py; add it to tv_service.py imports block if not already present):

Check first: `import re` — add it to the top-of-file import block if missing. Then insert:

```python
# Season/episode token pattern used to strip the SxxEyy suffix from a
# guessit-extracted episode title so only the show name remains.
_SEASON_TOKEN_RE = re.compile(r"\s*-?\s*S\d+(?:E\d+)*.*$", re.IGNORECASE)


def _recover_title_from_episodes(show_dir: Path) -> str | None:
    """Recover the show title from episode filenames when the folder name is degenerate.

    When a staging folder is named with only a season token (e.g. `` S03``),
    ``_parse_folder_name`` returns that token as the title. This function
    inspects the episode files inside ``show_dir``, picks the first video
    file, runs ``NameCleaner.clean()`` on its stem, and strips the trailing
    season/episode token so only the show title remains.

    Args:
        show_dir: Path to the TV show staging directory.

    Returns:
        Recovered show title string, or None if no video files are found or
        the recovery produces an empty / token-only string.
    """
    video_files = sorted(
        f for f in show_dir.iterdir()
        if f.is_file() and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
    )
    if not video_files:
        return None

    first = video_files[0]
    try:
        from personalscraper.sorter.cleaner import NameCleaner  # noqa: PLC0415

        cleaner = NameCleaner()
        raw_title = cleaner.clean(first.stem)
    except Exception:  # pragma: no cover — guard against unexpected guessit failures
        return None

    if not raw_title:
        return None

    # Strip trailing SxxEyy and everything after it (episode number, title)
    recovered = _SEASON_TOKEN_RE.sub("", raw_title).strip(" -").strip()
    return recovered if recovered else None
```

- [ ] **Step 4.3: Wire into `scrape_tvshow` after `_parse_folder_name` call**

In `TvServiceMixin.scrape_tvshow`, after line 110 (`title, year = _parse_folder_name(show_dir.name)`) and before line 111 (`if year is None:`), insert:

```python
        # Episode-filename fallback: if the folder title is a bare season/episode
        # token (e.g. " S03"), re-derive the show title from the first episode
        # file so the provider query uses the real title ("The Orville") instead
        # of the degenerate token.  is_degenerate_title is imported inline to
        # avoid a circular import with classifier.
        from personalscraper.scraper.classifier import is_degenerate_title  # noqa: PLC0415

        if is_degenerate_title(title):
            recovered = _recover_title_from_episodes(show_dir)
            if recovered:
                log.info(
                    "show_title_recovered_from_episodes",
                    degenerate_title=title,
                    recovered_title=recovered,
                    show_dir=str(show_dir),
                )
                title = recovered
```

The resulting block in `scrape_tvshow` (lines 110-113 after edit):

```python
        title, year = _parse_folder_name(show_dir.name)
        from personalscraper.scraper.classifier import is_degenerate_title  # noqa: PLC0415

        if is_degenerate_title(title):
            recovered = _recover_title_from_episodes(show_dir)
            if recovered:
                log.info(
                    "show_title_recovered_from_episodes",
                    degenerate_title=title,
                    recovered_title=recovered,
                    show_dir=str(show_dir),
                )
                title = recovered
        if year is None:
            year = _infer_year_from_child_names(show_dir, title)
```

- [ ] **Step 4.4: Add `import re` to tv_service.py imports if missing**

Check: `command rg -n "^import re" /Users/izno/dev/PersonnalScaper/personalscraper/scraper/tv_service.py --type py`

If missing, add `import re` after `import unicodedata` (line 5) in the stdlib imports block.

- [ ] **Step 4.5: Run the AC-2 tests — all 3 must PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py::TestAC2OrvilleRecovery -v 2>&1 | tail -15
```

Expected: 3 PASSes.

- [ ] **Step 4.6: Run the full match-guard test suite**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/test_confidence_match_guard.py tests/scraper/test_classifier_match_guard.py -v 2>&1 | tail -25
```

Expected: all PASS.

- [ ] **Step 4.7: Run the existing scraper test suite to catch regressions**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m pytest tests/scraper/ -v --tb=short 2>&1 | tail -30
```

Expected: 0 failed, 0 errors. If any test references `scrape_tvshow` or `_parse_folder_name` and now fails, investigate before committing.

- [ ] **Step 4.8: Quick ruff + mypy pass on changed files**

```bash
cd /Users/izno/dev/PersonnalScaper && command python -m ruff check personalscraper/scraper/tv_service.py personalscraper/scraper/classifier.py tests/scraper/test_confidence_match_guard.py && command python -m mypy personalscraper/scraper/tv_service.py personalscraper/scraper/classifier.py --ignore-missing-imports 2>&1 | tail -15
```

Expected: no errors.

- [ ] **Step 4.9: Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/scraper/tv_service.py tests/scraper/test_confidence_match_guard.py && git commit -m "$(cat <<'EOF'
feat(match-guard): episode-filename fallback for degenerate show titles

Adds _recover_title_from_episodes() to tv_service.py: when the folder
title is a bare season token (is_degenerate_title), pick the first video
file, run NameCleaner.clean() on its stem, strip the SxxEyy suffix, and
use the recovered show title for the provider query.

Effect: ' S03' folder + 'The Orville - S3E01.mkv' → queries 'The Orville'.
Tests: AC-2 (recovery), AC-6 (predicate scoping) all green.
EOF
)"
```

---

## Mutation-proof note

The AC-2 tests are mutation-proof because:

- `test_recover_title_from_episode_files` asserts the exact string `"The Orville"`. Removing the `_SEASON_TOKEN_RE.sub` strip causes the test to fail (recovered would contain `"S3E01 - Some Episode"` residue).
- `test_no_episode_files_returns_none` asserts `None`. Returning a default empty string instead would break it.
- The AC-6 tests check both directions of the predicate. Inverting the regex or widening it to match `S.W.A.T.` would break the False-expected cases.

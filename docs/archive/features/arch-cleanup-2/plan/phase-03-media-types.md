# Phase 3 — media_types promotion

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> or `superpowers:executing-plans` to implement this phase step-by-step.

**Goal:** Promote `VIDEO_EXTENSIONS`, `FileType`, and `is_trailer_filename` out of
`sorter/file_type.py` into a new `core/media_types.py`. Rewrite all 23 non-`sorter`
import lines across 10 subpackages to import from `core.media_types`. Drop the
re-export from `sorter/file_type.py` so `sorter` is no longer an undeclared
utility dependency of the whole system.

**Architecture:** Create `core/media_types.py` as the new canonical home. Update
`sorter/file_type.py` to import its own constants from `core.media_types` (downward
dependency — fine). Rewrite 23 call sites. No re-export from `sorter` at end of phase.

**Tech Stack:** Python stdlib (`enum`, `re`); pytest; `rg` with `-t py`.

---

## Gate (pre-conditions from previous phases)

Phase 3 is independently completable (no shared state with Phase 1 or 2). If prior
phases were completed, their gates must have passed:

```bash
make check   # must exit 0
```

---

## Files

| Action | Path                                                  |
| ------ | ----------------------------------------------------- |
| Create | `personalscraper/core/media_types.py`                 |
| Modify | `personalscraper/sorter/file_type.py`                 |
| Modify | `personalscraper/scraper/run.py`                      |
| Modify | `personalscraper/scraper/movie_service.py`            |
| Modify | `personalscraper/scraper/tv_service.py`               |
| Modify | `personalscraper/scraper/rename_service.py`           |
| Modify | `personalscraper/scraper/existing_validator.py`       |
| Modify | `personalscraper/scraper/existing_validator_drift.py` |
| Modify | `personalscraper/scraper/_shared.py`                  |
| Modify | `personalscraper/enforce/structure_validator.py`      |
| Modify | `personalscraper/enforce/coherence_checker.py`        |
| Modify | `personalscraper/enforce/file_sanitizer.py`           |
| Modify | `personalscraper/library/analyzer.py`                 |
| Modify | `personalscraper/library/rescraper.py`                |
| Modify | `personalscraper/library/scanner.py`                  |
| Modify | `personalscraper/conf/staging.py`                     |
| Modify | `personalscraper/conf/models/staging.py`              |
| Modify | `personalscraper/indexer/scanner/_modes/backfill.py`  |
| Modify | `personalscraper/indexer/scanner/_modes/enrich.py`    |
| Modify | `personalscraper/verify/checker.py`                   |
| Modify | `personalscraper/verify/run.py`                       |
| Modify | `personalscraper/dispatch/run.py`                     |
| Modify | `personalscraper/ingest/ingest.py`                    |
| Modify | `personalscraper/process/run.py`                      |
| Modify | `personalscraper/trailers/scanner.py`                 |

---

## Sub-phase 3.1 — Create `core/media_types.py`

### Task 1: Confirm which symbols from `sorter/file_type.py` are used outside `sorter/`

- [ ] **Step 3.1.1: Audit external sorter/file_type.py imports**

```bash
rg -t py "from personalscraper.sorter.file_type import\|from personalscraper.sorter import file_type" \
    personalscraper/ | rg -v 'personalscraper/sorter/'
# Note which symbols each file imports (VIDEO_EXTENSIONS, FileType,
# is_trailer_filename, AUDIO_EXTENSIONS, EBOOK_EXTENSIONS, or other).
```

Also check whether `AUDIO_EXTENSIONS` or `EBOOK_EXTENSIONS` are used outside `sorter/`:

```bash
rg -t py "AUDIO_EXTENSIONS\|EBOOK_EXTENSIONS" personalscraper/ | rg -v 'personalscraper/sorter/'
# If any results: include those symbols in core/media_types.py.
# If no results: only move VIDEO_EXTENSIONS, FileType, is_trailer_filename.
```

### Task 2: Write the failing identity test

- [ ] **Step 3.1.2: Write the regression/identity test**

Add a new test file `tests/unit/core/test_media_types.py`:

```python
"""Regression / identity tests for core.media_types (arch-cleanup-2 Phase 3).

Invariants:
- VIDEO_EXTENSIONS in core.media_types is a frozenset containing 'mkv'.
- FileType enum is importable from core.media_types.
- is_trailer_filename is callable and returns bool.
- The VIDEO_EXTENSIONS object is identical (same frozenset) whether imported
  from core.media_types or from sorter.file_type (identity, not just equality).
  This guards against accidental duplication that would allow them to diverge.
"""

from __future__ import annotations

from personalscraper.core.media_types import (
    VIDEO_EXTENSIONS,
    FileType,
    is_trailer_filename,
)


def test_video_extensions_is_frozenset_with_mkv() -> None:
    """VIDEO_EXTENSIONS is a frozenset and contains the canonical 'mkv' extension."""
    assert isinstance(VIDEO_EXTENSIONS, frozenset)
    assert "mkv" in VIDEO_EXTENSIONS


def test_file_type_enum_has_expected_members() -> None:
    """FileType enum is importable and has the canonical members."""
    assert hasattr(FileType, "MOVIE")
    assert hasattr(FileType, "TVSHOW")
    assert FileType.MOVIE.value == "movie"
    assert FileType.TVSHOW.value == "tvshow"


def test_is_trailer_filename_returns_bool() -> None:
    """is_trailer_filename is callable and returns a bool for a known trailer name."""
    result = is_trailer_filename("The.Movie-trailer.mkv")
    assert isinstance(result, bool)
    assert result is True  # stem ends with "-trailer"


def test_is_trailer_filename_non_trailer() -> None:
    """is_trailer_filename returns False for a normal video filename."""
    assert is_trailer_filename("The.Movie.mkv") is False


def test_video_extensions_same_object_as_sorter() -> None:
    """After Phase 3, sorter.file_type.VIDEO_EXTENSIONS IS core.media_types.VIDEO_EXTENSIONS.

    Guards against accidental duplication — the two names must resolve to the
    exact same frozenset object (sorter re-imports from core.media_types).
    """
    from personalscraper.sorter.file_type import VIDEO_EXTENSIONS as sorter_ve

    assert sorter_ve is VIDEO_EXTENSIONS, (
        "sorter.file_type.VIDEO_EXTENSIONS and core.media_types.VIDEO_EXTENSIONS "
        "are different objects — sorter/file_type.py must import from core.media_types, "
        "not re-define the set."
    )
```

- [ ] **Step 3.1.3: Run the test — expect failures**

```bash
python -m pytest tests/unit/core/test_media_types.py -v
# EXPECT: FAILED — core.media_types does not exist yet
```

### Task 3: Create `core/media_types.py`

- [ ] **Step 3.1.4: Create `personalscraper/core/media_types.py`**

Exact content (all values verified against `sorter/file_type.py` @ HEAD `1c4636eb`).
Note: `is_trailer_filename` implementation differs from `sorter` — the sorter version
checks `stem.endswith("-trailer")` (Plex flat-file convention). The predicate here
is the same implementation, copied verbatim.

```python
"""Shared media-type constants and filename predicates.

Promotes the canonical file-extension sets and ``FileType`` enum out of
``sorter/`` into the lowest-layer ``core/`` package so any subpackage
can import them without taking a dependency on the sorter pipeline step
(arch-cleanup-2 Phase 3).

The detection *functions* (``detect_file_type``, ``detect_dir_type``) remain
in ``sorter/file_type.py`` because they contain sorter-specific pipeline
heuristics. This module holds only the shared *constants* and the
cross-package filename predicate ``is_trailer_filename``.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Extension sets
# ---------------------------------------------------------------------------

# Video extensions handled by the pipeline (matches CLAUDE.md list + extras from FileMate)
VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        "avi",
        "mkv",
        "mp4",
        "mpg",
        "mpeg",
        "mov",
        "wmv",
        "flv",
        "webm",
        "m4v",
        "ts",
        "m2ts",
        "mts",
        "3gp",
        "vob",
        "ogv",
        "rmvb",
    }
)

AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {
        "mp3",
        "wav",
        "flac",
        "ogg",
        "m4a",
        "wma",
        "aac",
        "ac3",
        "dts",
        "mka",
        "opus",
        "m4b",
        "m4r",
    }
)

EBOOK_EXTENSIONS: frozenset[str] = frozenset(
    {
        "pdf",
        "epub",
        "mobi",
        "azw",
        "azw3",
        "djvu",
        "cbz",
        "cbr",
        "fb2",
        "lit",
    }
)


# ---------------------------------------------------------------------------
# FileType enum
# ---------------------------------------------------------------------------


class FileType(Enum):
    """Media type categories matching staging subdirectories.

    Attributes:
        MOVIE: Films — sorted to the movies staging dir.
        TVSHOW: TV series — sorted to the tvshows staging dir.
        EBOOK: Ebooks — sorted to the ebooks staging dir.
        AUDIO: Audiobooks/music — sorted to the audio staging dir.
        APP: Applications — sorted to the apps staging dir.
        OTHER: Unrecognized type.
    """

    MOVIE = "movie"
    TVSHOW = "tvshow"
    EBOOK = "ebook"
    AUDIO = "audio"
    APP = "app"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Shared filename predicate
# ---------------------------------------------------------------------------


def is_trailer_filename(name: str) -> bool:
    """Check if a filename is a flat Plex movie trailer (filename-only check).

    Movies place their trailer FLAT at the movie root following the Plex Local
    Media Assets convention: ``{media_name}-trailer.{ext}``. This predicate
    lets dedup logic exempt that trailer from duplicate-video detection so a
    movie with its trailer is not wrongly flagged as holding two feature videos.

    The match is purely on the filename stem: it is ``True`` only when the stem
    ends with the ``-trailer`` suffix (case-insensitive). A movie literally
    named "The Trailer" has stem "The Trailer" (no hyphen) and is NOT matched.

    Args:
        name: Filename (basename only; any directory part is ignored).

    Returns:
        ``True`` if the filename stem ends with ``-trailer`` (case-insensitive).
    """
    return Path(name).stem.casefold().endswith("-trailer")
```

- [ ] **Step 3.1.6: Run the identity test — expect passing**

```bash
python -m pytest tests/unit/core/test_media_types.py::test_video_extensions_is_frozenset_with_mkv \
    tests/unit/core/test_media_types.py::test_file_type_enum_has_expected_members \
    tests/unit/core/test_media_types.py::test_is_trailer_filename_returns_bool \
    tests/unit/core/test_media_types.py::test_is_trailer_filename_non_trailer -v
# EXPECT: 4 passed
# (test_video_extensions_same_object_as_sorter will still fail — sorter not updated yet)
```

- [ ] **Step 3.1.7: Commit (core/media_types.py + identity test)**

```bash
git add personalscraper/core/media_types.py tests/unit/core/test_media_types.py
git commit -m "feat(arch-cleanup-2): create core/media_types.py with VIDEO_EXTENSIONS, FileType, is_trailer_filename"
```

---

## Sub-phase 3.2 — Rewrite `sorter/file_type.py`

### Task 4: Update `sorter/file_type.py` to import from `core.media_types`

- [ ] **Step 3.2.1: Update `personalscraper/sorter/file_type.py`**

Replace the definitions of `VIDEO_EXTENSIONS`, `AUDIO_EXTENSIONS`, `EBOOK_EXTENSIONS`,
`FileType`, and `is_trailer_filename` with imports from `core.media_types`. Keep
`detect_file_type`, `detect_dir_type`, and any private helpers (`_has_tvshow_markers`,
`_extension_of`, etc.) — those are sorter-internal pipeline logic.

At the top of `sorter/file_type.py`, replace the definitions with:

```python
# Shared constants and predicate are canonical in core.media_types.
# Imported here so sorter-internal detection functions can use them,
# and so any legacy `from personalscraper.sorter.file_type import …`
# call sites still resolve during the transition window (arch-cleanup-2 Phase 3).
# The re-export is intentional and will be dropped once all 23 call sites
# are rewritten to import from core.media_types directly (end of this phase).
from personalscraper.core.media_types import (
    AUDIO_EXTENSIONS,
    EBOOK_EXTENSIONS,
    VIDEO_EXTENSIONS,
    FileType,
    is_trailer_filename,
)
```

Remove the original definitions of those five symbols from the file body.

- [ ] **Step 3.2.2: Run the object-identity test — expect passing**

```bash
python -m pytest tests/unit/core/test_media_types.py::test_video_extensions_same_object_as_sorter -v
# EXPECT: passed (same object because sorter now re-imports from core)
```

- [ ] **Step 3.2.3: Quick smoke**

```bash
python -c "from personalscraper.sorter.file_type import VIDEO_EXTENSIONS, FileType, is_trailer_filename; print('ok')"
# EXPECT: ok
```

- [ ] **Step 3.2.4: Commit**

```bash
git add personalscraper/sorter/file_type.py
git commit -m "refactor(arch-cleanup-2): sorter/file_type.py imports shared symbols from core.media_types"
```

---

## Sub-phase 3.3 — Rewrite the 23 non-`sorter` import lines

### Task 5: Rewrite all 23 import lines across 10 subpackages

For each file below, find the line that imports from `personalscraper.sorter.file_type`
and change it to import from `personalscraper.core.media_types` instead. Import only
the symbols that file actually uses.

- [ ] **Step 3.3.1: scraper/ (7 files)**

```bash
# Confirm current imports before editing:
rg -t py "from personalscraper.sorter.file_type import" personalscraper/scraper/
```

For each of `run.py`, `movie_service.py`, `tv_service.py`, `rename_service.py`,
`existing_validator.py`, `existing_validator_drift.py`, `_shared.py`:

```python
# Before (example):
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS, FileType

# After:
from personalscraper.core.media_types import VIDEO_EXTENSIONS, FileType
```

- [ ] **Step 3.3.2: enforce/ (3 files)**

```bash
rg -t py "from personalscraper.sorter.file_type import" personalscraper/enforce/
```

Update `structure_validator.py`, `coherence_checker.py`, `file_sanitizer.py`.

- [ ] **Step 3.3.3: library/ (3 files)**

```bash
rg -t py "from personalscraper.sorter.file_type import" personalscraper/library/
```

Update `analyzer.py`, `rescraper.py`, `scanner.py`.

- [ ] **Step 3.3.4: conf/ (2 files)**

```bash
rg -t py "from personalscraper.sorter.file_type import" personalscraper/conf/
```

Update `staging.py`, `models/staging.py`.

- [ ] **Step 3.3.5: indexer/ (2 files)**

```bash
rg -t py "from personalscraper.sorter.file_type import" personalscraper/indexer/
```

Update `scanner/_modes/backfill.py`, `scanner/_modes/enrich.py`.

- [ ] **Step 3.3.6: verify/ (2 files)**

```bash
rg -t py "from personalscraper.sorter.file_type import" personalscraper/verify/
```

Update `checker.py`, `run.py`.

- [ ] **Step 3.3.7: dispatch/, ingest/, process/, trailers/ (1 file each)**

```bash
rg -t py "from personalscraper.sorter.file_type import" \
    personalscraper/dispatch/ personalscraper/ingest/ \
    personalscraper/process/ personalscraper/trailers/
```

Update `dispatch/run.py`, `ingest/ingest.py`, `process/run.py`, `trailers/scanner.py`.

- [ ] **Step 3.3.8: Verify zero remaining non-sorter imports**

```bash
rg -t py "from personalscraper.sorter.file_type import" personalscraper/ | rg -v 'personalscraper/sorter/'
# EXPECT: no output (exit 1)
```

- [ ] **Step 3.3.9: Run full test suite**

```bash
make test
# EXPECT: all passed, 0 errors
```

- [ ] **Step 3.3.10: Commit**

```bash
git add personalscraper/scraper/ personalscraper/enforce/ personalscraper/library/ \
        personalscraper/conf/ personalscraper/indexer/ personalscraper/verify/ \
        personalscraper/dispatch/ personalscraper/ingest/ personalscraper/process/ \
        personalscraper/trailers/
git commit -m "refactor(arch-cleanup-2): rewrite 23 non-sorter imports to use core.media_types"
```

---

## Sub-phase 3.4 — Drop re-export from `sorter/file_type.py`

### Task 6: Remove the transitional re-export and run final checks

- [ ] **Step 3.4.1: Drop the re-export from `sorter/file_type.py`**

Remove the `from personalscraper.core.media_types import …` re-export block added in
Step 3.2.1 (the transitional block that exported the shared symbols for legacy callers).
Keep only the imports that `sorter/file_type.py` needs _internally_ for
`detect_file_type` and `detect_dir_type`:

```python
# Keep only what the detection functions need internally:
from personalscraper.core.media_types import VIDEO_EXTENSIONS, FileType, is_trailer_filename
# (or whichever symbols detect_file_type / detect_dir_type actually use)
```

Do NOT add `__all__` or any re-export — `sorter/file_type.py` should only export its own
detection functions (`detect_file_type`, `detect_dir_type`).

- [ ] **Step 3.4.2: Verify zero non-sorter imports of sorter.file_type for shared symbols**

```bash
rg -t py "from personalscraper.sorter.file_type import" personalscraper/ | rg -v 'personalscraper/sorter/'
# EXPECT: no output (exit 1)

rg -t py "from personalscraper.sorter.file_type import" tests/
# Note any test imports — update them in the next step if found.
```

- [ ] **Step 3.4.3: Update test fixtures/mocks that import from sorter.file_type**

```bash
rg -t py "sorter.file_type\|sorter\.file_type" tests/
```

For each match, update the import to `core.media_types` if it imports a shared constant
or `FileType`/`is_trailer_filename`. Leave imports of `detect_file_type`/`detect_dir_type`
unchanged (those stay in `sorter`).

- [ ] **Step 3.4.4: Run all tests**

```bash
make test
# EXPECT: all passed, 0 errors
```

- [ ] **Step 3.4.5: Commit**

```bash
git add personalscraper/sorter/file_type.py tests/
git commit -m "refactor(arch-cleanup-2): drop sorter.file_type re-export; sorter is now a pure pipeline step"
```

---

## Phase Gate

```bash
make lint && make test && make check
# EXPECT: exit 0 for all three

rg -t py "from personalscraper.sorter.file_type import" personalscraper/ | rg -v 'personalscraper/sorter/'
# EXPECT: no output (exit 1)

python3 scripts/check-module-size.py
# EXPECT: exit 0; only two WARN lines (scraper/movie_service.py, library/scanner.py)
```

---

## Acceptance Criteria (Phase 3 subset)

```bash
# ACC-11 — sorter.file_type no longer imported outside sorter/
rg -t py 'from personalscraper.sorter.file_type import' personalscraper/ | rg -v 'personalscraper/sorter/'
# EXPECT: no output, exit 1

# ACC-12 — media_types is the new home and VIDEO_EXTENSIONS is correct
python -c "
from personalscraper.core.media_types import VIDEO_EXTENSIONS, FileType, is_trailer_filename
assert isinstance(VIDEO_EXTENSIONS, frozenset) and 'mkv' in VIDEO_EXTENSIONS
print('ok')
"
# EXPECT: exit 0; stdout: ok

# ACC-14 — module-size guardrail unchanged
python3 scripts/check-module-size.py
# EXPECT: exit 0; exactly two WARN lines (movie_service.py, library/scanner.py)

# ACC-17 — smoke import
python -c "import personalscraper; print('ok')"
# EXPECT: exit 0; stdout: ok
```

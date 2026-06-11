# Phase 03 — Hard-Filters (`acquire/_filters.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `acquire/_filters.py` with resolution-ordinal hard-filter (fail-open on
None-resolution) and anchored title-language audio filter. Fix the `TrackerResult.audio`
docstring (it describes codec, not language — the docstring is wrong). Tests cover the
`\b` boundary guard against false-matches like `MULTILINGUAL` and `ConVOSTed`.

**Architecture:** `_filters.py` is a pure predicate module — no I/O, no DB access, no
ranking. It takes a list of `TrackerResult` + a `QualityProfile` and returns survivors.
The `audio` docstring fix in `_base.py` is a one-line correction.

**Tech Stack:** Python 3.12, `re`, `acquire/desired.py` (`Resolution`, `QualityProfile`),
`api/tracker/_base.py` (`TrackerResult`).

---

## Gate (start of phase)

Previous phase produced:

- `acquire/desired.py` with `Resolution`, `QualityProfile`
- `acquire/_dedup.py` with `dedup()`, `SearchOutcome`
- `api/tracker/_registry.py` with `search_candidates()` + `transports()`

---

## File Map

- **Create:** `personalscraper/acquire/_filters.py`
- **Modify:** `personalscraper/api/tracker/_base.py` — fix `audio` field docstring
- **Test:** `tests/acquire/test_filters.py`

---

## Task 1: Fix the `TrackerResult.audio` docstring

The `audio` field docstring currently says "Audio language/track info (VFF, VFQ, TrueHD...)"
— this is wrong; the field is **codec-only** (DTS, AAC, TrueHD). Language markers come from
the title. The hard-filter design depends on this invariant being documented accurately.

**Files:**

- Modify: `personalscraper/api/tracker/_base.py`

- [ ] **Step 1: Read the current docstring**

Open `personalscraper/api/tracker/_base.py` and locate the `audio` attribute in the
`TrackerResult` docstring (around line 82). Verify it reads:
`audio: Audio language/track info (VFF, VFQ, TrueHD...).`

- [ ] **Step 2: Fix the docstring**

Change the `audio` attribute line in `TrackerResult`'s class docstring from:

```
        audio: Audio language/track info (VFF, VFQ, TrueHD...).
```

to:

```
        audio: Audio codec info (DTS, AAC, TrueHD, AC3, ...).
            NOTE: this field is codec-only — it never contains language
            markers (VF/VOSTFR/VO). Language detection for the audio
            hard-filter must parse ``result.title`` instead.
```

- [ ] **Step 3: Commit the docstring fix**

```bash
git add personalscraper/api/tracker/_base.py
git commit -m "fix(grab-core): correct TrackerResult.audio docstring — codec-only, not language"
```

---

## Task 2: Resolution hard-filter with fail-open None

**Files:**

- Create: `personalscraper/acquire/_filters.py`
- Test: `tests/acquire/test_filters.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/acquire/test_filters.py
"""Tests for the hard-filter stage (acquire/_filters.py).

Non-vacuous: covers fail-open None-resolution, resolution floor enforcement,
audio regex anchoring (\b guard), and profile no-op when defaults are permissive.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from personalscraper.acquire._filters import apply_hard_filters
from personalscraper.acquire.desired import QualityProfile, Resolution
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api._units import ByteSize


def _result(
    title: str,
    resolution: str | None = None,
    audio: str | None = None,
    seeders: int = 10,
) -> TrackerResult:
    return TrackerResult(
        provider="lacale",
        tracker_id="t1",
        title=title,
        size=ByteSize(1_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution=resolution,
        audio=audio,
    )


# --- Resolution filter ---

def test_resolution_floor_drops_below_minimum() -> None:
    profile = QualityProfile(min_resolution=Resolution.R1080P)
    results = [
        _result("Movie 720p", resolution="720p"),
        _result("Movie 1080p", resolution="1080p"),
        _result("Movie 2160p", resolution="2160p"),
    ]
    survivors = apply_hard_filters(results, profile)
    resolutions = [r.resolution for r in survivors]
    assert "720p" not in resolutions
    assert "1080p" in resolutions
    assert "2160p" in resolutions


def test_resolution_none_fails_open() -> None:
    """LOAD-BEARING: None-resolution (REMUX, COMPLETE.BLURAY) must pass the filter."""
    profile = QualityProfile(min_resolution=Resolution.R1080P)
    results = [
        _result("Movie.COMPLETE.BLURAY.DTS-GRP", resolution=None),
        _result("Movie.REMUX.DTS-GRP", resolution=None),
        _result("Movie.720p", resolution="720p"),
    ]
    survivors = apply_hard_filters(results, profile)
    # None-resolution passes, 720p is dropped
    assert all(r.resolution is None for r in survivors)
    assert len(survivors) == 2


def test_resolution_filter_noop_when_profile_min_is_none() -> None:
    """Permissive default: min_resolution=None → filter is a no-op."""
    profile = QualityProfile()  # min_resolution=None
    results = [
        _result("Movie 480p", resolution="480p"),
        _result("Movie 720p", resolution="720p"),
        _result("Movie REMUX", resolution=None),
    ]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 3


def test_resolution_4k_uhd_aliases_pass_2160_floor() -> None:
    profile = QualityProfile(min_resolution=Resolution.R2160P)
    results = [
        _result("Movie 4K HDR", resolution="4k"),
        _result("Movie UHD BluRay", resolution="uhd"),
        _result("Movie 2160p", resolution="2160p"),
        _result("Movie 1080p", resolution="1080p"),
    ]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 3  # 4k, uhd, 2160p pass; 1080p dropped
```

- [ ] **Step 2: Run to verify fails**

```bash
cd /Users/izno/dev/PersonnalScaper
python -m pytest tests/acquire/test_filters.py::test_resolution_floor_drops_below_minimum -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create `_filters.py` with resolution filter**

```python
# personalscraper/acquire/_filters.py
"""Hard-filter stage for the grab orchestrator (RP5b).

Eliminatory filters applied BEFORE dedup so a merge never drops the only
profile-passing variant.  Two filters are active at RP5b:

1. **Resolution floor** — drops results below ``profile.min_resolution``.
   None-resolution = FAIL-OPEN (passes) by default: unparseable resolution
   tokens (REMUX, COMPLETE.BLURAY, WEB-DL pack) are often the best source
   and are soft-scored by ``rank()`` later.

2. **Audio language filter** — parses language markers from ``result.title``
   (NOT ``result.audio`` which is codec-only — see TrackerResult.audio
   docstring). Uses anchored regex to prevent false-matches like
   ``MULTILINGUAL`` matching ``MULTI`` or ``ConVOSTed`` matching ``VOSTFR``.

Import direction: ``acquire/desired.py`` + ``api/tracker/_base.py`` + stdlib.
Never imports sorter, cleaner, or indexer.
"""

from __future__ import annotations

import re

from personalscraper.acquire.desired import QualityProfile, Resolution
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.logger import get_logger

log = get_logger("acquire.filters")

# Map raw resolution tokens from TrackerResult.resolution to Resolution tiers.
# Tokens not in this map produce None → fail-open (passes the filter).
_RESOLUTION_TOKEN_MAP: dict[str, Resolution] = {
    "480p": Resolution.R480P,
    "720p": Resolution.R720P,
    "1080p": Resolution.R1080P,
    "2160p": Resolution.R2160P,
    "4k": Resolution.R2160P,
    "uhd": Resolution.R2160P,
}

# Anchored audio language regex: \b prevents MULTILINGUAL from matching MULTI
# and ConVOSTed from matching VOSTFR.  re.IGNORECASE handles mixed-case titles.
_AUDIO_LANG_RE = re.compile(
    r"\b(VFF|VFQ|VFI|VF2|VOF|TRUEFRENCH|MULTI|VOSTFR|VOST|VO)\b",
    re.IGNORECASE,
)

# Normalise matched raw markers to the three canonical tier names used
# in QualityProfile.required_audio.
_AUDIO_NORM: dict[str, str] = {
    "vff": "VF",
    "vfq": "VF",
    "vfi": "VF",
    "vf2": "VF",
    "vof": "VF",
    "truefrench": "VF",
    "multi": "VF",   # MULTI always includes a French track
    "vostfr": "VOSTFR",
    "vost": "VOSTFR",
    "vo": "VO",
}


def _parse_resolution(token: str | None) -> Resolution | None:
    """Map a raw resolution token to a :class:`Resolution` tier.

    Args:
        token: Raw ``TrackerResult.resolution`` string (e.g. ``"1080p"``,
            ``"4k"``, ``"uhd"``), or ``None``.

    Returns:
        Matching :class:`Resolution` tier, or ``None`` if unrecognised.
    """
    if not token:
        return None
    return _RESOLUTION_TOKEN_MAP.get(token.lower())


def _parse_audio_languages(title: str) -> frozenset[str]:
    """Extract canonical language tier markers from a torrent title.

    Parses ``result.title`` (NOT ``result.audio`` — codec-only field) with
    the anchored ``_AUDIO_LANG_RE`` to avoid false-matches.

    Args:
        title: Raw torrent title from :class:`TrackerResult`.

    Returns:
        Set of canonical tier strings (``{"VF"}``, ``{"VOSTFR"}``,
        ``{"VF", "VO"}``, …), or empty set if no marker found.
    """
    found: set[str] = set()
    for m in _AUDIO_LANG_RE.finditer(title):
        canonical = _AUDIO_NORM.get(m.group(0).lower())
        if canonical:
            found.add(canonical)
    return frozenset(found)


def _passes_resolution(result: TrackerResult, profile: QualityProfile) -> bool:
    """Return True if *result* meets the profile's resolution floor.

    Args:
        result: Candidate torrent result.
        profile: Active quality profile.

    Returns:
        ``True`` when the result should survive the resolution filter.
    """
    if profile.min_resolution is None:
        # Permissive default: no floor configured — filter is a no-op.
        return True
    parsed = _parse_resolution(result.resolution)
    if parsed is None:
        # Unrecognised resolution token: FAIL-OPEN (passes).
        # REMUX / COMPLETE.BLURAY / WEB-DL packs often omit a resolution tag
        # and are typically the best available source; rank() soft-scores them.
        return True
    return parsed >= profile.min_resolution


def _passes_audio(result: TrackerResult, profile: QualityProfile) -> bool:
    """Return True if *result* contains at least one required audio language.

    Args:
        result: Candidate torrent result.
        profile: Active quality profile.

    Returns:
        ``True`` when the result should survive the audio filter.
    """
    if not profile.required_audio:
        # Permissive default: no audio requirement — filter is a no-op.
        return True
    found = _parse_audio_languages(result.title)
    return bool(found & profile.required_audio)


def apply_hard_filters(
    results: list[TrackerResult],
    profile: QualityProfile,
) -> list[TrackerResult]:
    """Apply eliminatory hard-filters; return surviving results.

    Filters applied in order:
    1. Resolution floor (fail-open on unrecognised tokens).
    2. Audio language (parsed from title with anchored regex).

    A result must pass **both** filters to survive.  An empty survivor list
    signals ``all_filtered`` → ``WantedAbandoned`` in the orchestrator.

    Args:
        results: Candidate results from the search stage.
        profile: Effective quality profile for this grab attempt.

    Returns:
        Filtered list (may be empty).
    """
    survivors = []
    for r in results:
        if not _passes_resolution(r, profile):
            log.debug(
                "acquire.filter.resolution_dropped",
                title=r.title,
                resolution=r.resolution,
                min_resolution=profile.min_resolution,
            )
            continue
        if not _passes_audio(r, profile):
            log.debug(
                "acquire.filter.audio_dropped",
                title=r.title,
                required=sorted(profile.required_audio),
            )
            continue
        survivors.append(r)
    return survivors


__all__ = ["apply_hard_filters"]
```

- [ ] **Step 4: Run resolution tests**

```bash
python -m pytest tests/acquire/test_filters.py -k "resolution" -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/_filters.py tests/acquire/test_filters.py
git commit -m "feat(grab-core): resolution hard-filter with fail-open None-resolution"
```

---

## Task 3: Audio language filter + `\b` false-match guard (load-bearing)

**Files:**

- Modify: `tests/acquire/test_filters.py` (add audio tests)

The `_filters.py` code from Task 2 already includes the audio filter. These tests
validate the implementation — especially the `\b` guard.

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/acquire/test_filters.py

# --- Audio language filter ---

def test_audio_filter_noop_when_required_audio_empty() -> None:
    """Permissive default: required_audio=frozenset() → no-op."""
    profile = QualityProfile()  # required_audio=frozenset()
    results = [
        _result("Movie 2020 VO 1080p"),
        _result("Movie 2020 1080p"),  # no language marker
        _result("Movie 2020 VOSTFR 1080p"),
    ]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 3


def test_audio_filter_drops_no_marker_title_when_vf_required() -> None:
    """Title with no language marker is dropped when VF is required."""
    profile = QualityProfile(required_audio=frozenset({"VF"}))
    results = [
        _result("Movie 2020 MULTi VFF 1080p BluRay"),  # VFF → VF
        _result("Movie 2020 1080p BluRay"),             # no marker → dropped
        _result("Movie 2020 TRUEFRENCH 1080p"),          # TRUEFRENCH → VF
    ]
    survivors = apply_hard_filters(results, profile)
    titles = [r.title for r in survivors]
    assert "Movie 2020 1080p BluRay" not in titles
    assert len(survivors) == 2


def test_audio_filter_multi_title_passes_vf_requirement() -> None:
    """MULTi title passes when VF required (MULTi always includes French)."""
    profile = QualityProfile(required_audio=frozenset({"VF"}))
    results = [_result("Inception 2010 MULTi VFF 2160p BluRay x265 DTS 5.1 - QTZ")]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 1


def test_audio_filter_passes_audio_dts_title_multi() -> None:
    """LOAD-BEARING (DESIGN §11-h): result.audio='DTS' with MULTi title passes VF filter."""
    profile = QualityProfile(required_audio=frozenset({"VF"}))
    # audio field is 'DTS' (codec-only) — language comes from title 'MULTi'
    result = _result("Movie 2020 MULTi 1080p BluRay", audio="DTS")
    survivors = apply_hard_filters([result], profile)
    assert len(survivors) == 1, "MULTi title must pass VF filter regardless of audio='DTS'"


def test_audio_filter_vostfr_kept_when_vostfr_required() -> None:
    profile = QualityProfile(required_audio=frozenset({"VOSTFR"}))
    results = [
        _result("Movie 2020 VOSTFR 1080p"),
        _result("Movie 2020 VF 1080p"),   # VF but VOSTFR required
    ]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 1
    assert "VOSTFR" in survivors[0].title


# --- \b boundary guard (LOAD-BEARING) ---

def test_audio_regex_boundary_multilingual_does_not_match() -> None:
    """LOAD-BEARING (DESIGN §11-i): MULTILINGUAL must NOT match the MULTI pattern."""
    from personalscraper.acquire._filters import _parse_audio_languages
    langs = _parse_audio_languages("Movie 2020 MULTILINGUAL 1080p BluRay")
    assert "VF" not in langs, "MULTILINGUAL must not trigger the MULTI→VF match"


def test_audio_regex_boundary_convostfr_does_not_match() -> None:
    """LOAD-BEARING (DESIGN §11-i): ConVOSTed must NOT match the VOSTFR pattern."""
    from personalscraper.acquire._filters import _parse_audio_languages
    langs = _parse_audio_languages("Movie 2020 ConVOSTed 1080p BluRay")
    assert "VOSTFR" not in langs, "ConVOSTed must not trigger the VOSTFR match"


def test_audio_regex_vostfr_exact_match_works() -> None:
    """VOSTFR (standalone word) still matches correctly after \b guard."""
    from personalscraper.acquire._filters import _parse_audio_languages
    langs = _parse_audio_languages("Inception.2010.VOSTFR.1080p.BluRay.x265")
    assert "VOSTFR" in langs
```

- [ ] **Step 2: Run all filter tests**

```bash
python -m pytest tests/acquire/test_filters.py -v
```

Expected: All 13 tests PASSED.

- [ ] **Step 3: Lint + size check**

```bash
python -m ruff check personalscraper/acquire/_filters.py tests/acquire/test_filters.py
python -m mypy personalscraper/acquire/_filters.py
python scripts/check-module-size.py personalscraper/acquire/_filters.py
```

Expected: zero errors; under 200 LOC.

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -10
```

Expected: passing summary, no regressions.

- [ ] **Step 5: Commit phase gate**

```bash
git add personalscraper/acquire/_filters.py tests/acquire/test_filters.py
git commit -m "feat(grab-core): audio hard-filter + \\b boundary guard + phase 03 gate"
```

---

## Drift notes (phase-3 execution, 2026-06-11)

- **Task 1-3 merged into single commit** (cap 2 allowed): the docstring fix + filter
  module + tests ship together as one phase-3 gate commit — per the plan's own "one
  phase, one gate" rhythm.
- **`_parse_resolution` uses `Resolution.from_token`** instead of a manual
  `_RESOLUTION_TOKEN_MAP` dict (plan §Task 2 Step 3). `from_token` already maps
  4k/uhd/2160p/1080p/720p/480p → the correct tier and returns `UNKNOWN` for
  unrecognised tokens, matching the fail-open design.
- **Extra tests beyond the plan's 13**: `test_resolution_unrecognised_fails_open_by_default`
  (UNKOWN→PASS), `test_resolution_unrecognised_fails_when_require_known_resolution`
  (UNKOWN→FAIL with opt-in), `test_audio_filter_vf_required_drops_vo_only_title`
  (VO→dropped when VF required), `test_audio_regex_boundary_convost_does_not_match`
  (ConVOSTed→no VOST match either), `test_audio_regex_multi_exact_match_works`
  (MULTi standalone→works). Total: 17 tests (plan minimum 13).
- **`_base.py` docstring commit is separate** (fix type, not feat) — total 2 commits
  for the phase.

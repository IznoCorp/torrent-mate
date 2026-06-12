# Phase 01 — RP3a Vocabulary (`acquire/desired.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `Resolution` IntEnum, `QualityProfile`, and `SourceCriteria` frozen dataclasses
with JSON codecs and a precedence round-trip test — all in `acquire/desired.py` (NOT `store.py`).

**Architecture:** Pure stdlib/core-only VOs. Permissive defaults (min_resolution=None,
required_audio=frozenset()). JSON helpers mirror the style of `store.py`'s `_media_ref_to_json`.

**Tech Stack:** Python 3.12, `enum.IntEnum`, frozen `kw_only=True` dataclasses, `json` stdlib.

---

## Gate (start of phase)

Previous phase: none — this is phase 1.
Precondition: `acquire/domain.py` exists (ships `WantedItem`, `FollowedSeries`).
`store.py` is at 684 LOC — new codec helpers go in `desired.py` to protect that budget.

---

## File Map

- **Create:** `personalscraper/acquire/desired.py`
- **Test:** `tests/acquire/test_desired.py`

---

## Task 1: Create `desired.py` with `Resolution` IntEnum

**Files:**

- Create: `personalscraper/acquire/desired.py`
- Test: `tests/acquire/test_desired.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/acquire/test_desired.py
"""Tests for acquire/desired.py — Resolution, QualityProfile, SourceCriteria."""
from __future__ import annotations

from personalscraper.acquire.desired import Resolution


def test_resolution_ordering_numeric() -> None:
    assert Resolution.R480P < Resolution.R720P < Resolution.R1080P
    assert Resolution.R2160P > Resolution.R1080P


def test_resolution_4k_uhd_2160p_fold() -> None:
    """4k / uhd / 2160p must all map to the same ordinal tier."""
    assert Resolution.R4K == Resolution.R2160P
    assert Resolution.R4K == Resolution.RUHD
    assert Resolution.R2160P == Resolution.RUHD
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/izno/dev/PersonnalScaper
python -m pytest tests/acquire/test_desired.py -v 2>&1 | tail -20
```

Expected: `ModuleNotFoundError` or `ImportError` — `desired.py` does not exist yet.

- [ ] **Step 3: Write `Resolution` in `desired.py`**

```python
# personalscraper/acquire/desired.py
"""Typed RP3a vocabulary — Resolution, QualityProfile, SourceCriteria.

Frozen, core+stdlib-pure value objects.  JSON codec helpers live here
(mirrors the style of ``store.py``'s ``_media_ref_to_json``) so the
684-LOC ``store.py`` budget is protected.

Import direction: stdlib only — never api/, indexer/, scraper/, or triage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import IntEnum


class Resolution(IntEnum):
    """Ordered resolution tiers.

    ``>=`` comparisons are numeric — never string-compare resolution tokens.
    ``R4K`` / ``RUHD`` / ``R2160P`` all fold to the same ordinal (2160)
    so any of the three names in a result title ranks identically.
    """

    R480P = 480
    R720P = 720
    R1080P = 1080
    R2160P = 2160
    # Aliases — same ordinal value as R2160P
    R4K = 2160
    RUHD = 2160
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/acquire/test_desired.py::test_resolution_ordering_numeric \
    tests/acquire/test_desired.py::test_resolution_4k_uhd_2160p_fold -v
```

Expected: 2 PASSED.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/desired.py tests/acquire/test_desired.py
git commit -m "feat(grab-core): add Resolution IntEnum to acquire/desired.py"
```

---

## Task 2: Add `QualityProfile` with permissive defaults

**Files:**

- Modify: `personalscraper/acquire/desired.py`
- Modify: `tests/acquire/test_desired.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/acquire/test_desired.py
from personalscraper.acquire.desired import QualityProfile


def test_quality_profile_permissive_defaults() -> None:
    """Default profile: no resolution floor, no audio requirement."""
    p = QualityProfile()
    assert p.min_resolution is None
    assert p.required_audio == frozenset()
    assert p.allowed_codecs == frozenset()
    assert p.min_size is None
    assert p.max_size is None


def test_quality_profile_explicit_floor() -> None:
    p = QualityProfile(min_resolution=Resolution.R1080P, required_audio=frozenset({"VF", "VOSTFR"}))
    assert p.min_resolution == Resolution.R1080P
    assert "VF" in p.required_audio
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/acquire/test_desired.py::test_quality_profile_permissive_defaults -v
```

Expected: `ImportError` — `QualityProfile` not defined yet.

- [ ] **Step 3: Add `QualityProfile` to `desired.py`**

```python
@dataclass(frozen=True, kw_only=True)
class QualityProfile:
    """Per-series quality policy decoded from ``FollowedSeries.quality_profile_json``.

    All defaults are **permissive**: ``min_resolution=None`` means no floor
    (hard-filter stage is a no-op); ``required_audio=frozenset()`` means any
    language passes.  A French-only or ≥1080p policy is an explicit per-profile
    opt-in set by Follow D4 — not a global default.

    Attributes:
        min_resolution: Minimum acceptable resolution tier, or ``None`` (no
            floor — fail-open, passes all resolutions including None-resolution
            REMUX/BluRay sources that the ranking engine soft-scores).
        required_audio: Set of required audio language markers
            (``{"VF", "VOSTFR", "VO"}`` tiers).  Empty = no language filter.
        allowed_codecs: Optional codec allow-list (empty = allow all).
        min_size: Minimum file size in bytes, or ``None`` (no lower bound).
        max_size: Maximum file size in bytes, or ``None`` (no upper bound).
    """

    min_resolution: Resolution | None = None
    required_audio: frozenset[str] = field(default_factory=frozenset)
    allowed_codecs: frozenset[str] = field(default_factory=frozenset)
    min_size: int | None = None
    max_size: int | None = None
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/acquire/test_desired.py -v
```

Expected: All passing so far (4 tests).

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/desired.py tests/acquire/test_desired.py
git commit -m "feat(grab-core): add QualityProfile with permissive defaults"
```

---

## Task 3: Add `SourceCriteria` (decode-only at RP5b)

**Files:**

- Modify: `personalscraper/acquire/desired.py`
- Modify: `tests/acquire/test_desired.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/acquire/test_desired.py
from personalscraper.acquire.desired import SourceCriteria


def test_source_criteria_defaults_all_none() -> None:
    """SourceCriteria is decode-only at RP5b: no live producer until Follow D4."""
    c = SourceCriteria()
    assert c.preferred_resolution is None
    assert c.required_audio == frozenset()
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/acquire/test_desired.py::test_source_criteria_defaults_all_none -v
```

Expected: `ImportError`.

- [ ] **Step 3: Add `SourceCriteria` to `desired.py`**

```python
@dataclass(frozen=True, kw_only=True)
class SourceCriteria:
    """Per-item source overrides decoded from ``WantedItem.criteria_json``.

    **Decode-only at RP5b** — no live producer until Follow D4.  The
    effective-profile precedence (series default ← item override) ships as
    a round-trip unit test, but is not an exercised live path yet.

    Attributes:
        preferred_resolution: Item-level resolution preference override, or
            ``None`` (inherit from ``QualityProfile``).
        required_audio: Item-level audio requirement override.  Empty =
            inherit from ``QualityProfile``.
    """

    preferred_resolution: Resolution | None = None
    required_audio: frozenset[str] = field(default_factory=frozenset)
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/acquire/test_desired.py -v
```

Expected: 5 PASSED.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/desired.py tests/acquire/test_desired.py
git commit -m "feat(grab-core): add SourceCriteria (decode-only RP5b)"
```

---

## Task 4: JSON codecs for `QualityProfile` and `SourceCriteria`

**Files:**

- Modify: `personalscraper/acquire/desired.py`
- Modify: `tests/acquire/test_desired.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/acquire/test_desired.py
from personalscraper.acquire.desired import (
    quality_profile_to_json,
    quality_profile_from_json,
    source_criteria_to_json,
    source_criteria_from_json,
)


def test_quality_profile_json_roundtrip_permissive() -> None:
    p = QualityProfile()
    assert quality_profile_from_json(quality_profile_to_json(p)) == p


def test_quality_profile_json_roundtrip_explicit() -> None:
    p = QualityProfile(
        min_resolution=Resolution.R1080P,
        required_audio=frozenset({"VF", "VOSTFR"}),
    )
    restored = quality_profile_from_json(quality_profile_to_json(p))
    assert restored.min_resolution == Resolution.R1080P
    assert restored.required_audio == frozenset({"VF", "VOSTFR"})


def test_source_criteria_json_roundtrip() -> None:
    c = SourceCriteria(
        preferred_resolution=Resolution.R720P,
        required_audio=frozenset({"VO"}),
    )
    assert source_criteria_from_json(source_criteria_to_json(c)) == c


def test_source_criteria_json_roundtrip_empty() -> None:
    c = SourceCriteria()
    assert source_criteria_from_json(source_criteria_to_json(c)) == c
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/acquire/test_desired.py::test_quality_profile_json_roundtrip_permissive -v
```

Expected: `ImportError`.

- [ ] **Step 3: Add codec helpers to `desired.py`**

```python
# --- JSON helpers (mirrors _media_ref_to_json style in store.py) ---

def quality_profile_to_json(p: QualityProfile) -> str:
    """Serialize a :class:`QualityProfile` to a compact JSON string.

    Args:
        p: The profile to serialize.

    Returns:
        JSON string suitable for storage in ``quality_profile_json`` column.
    """
    return json.dumps({
        "min_resolution": p.min_resolution.value if p.min_resolution is not None else None,
        "required_audio": sorted(p.required_audio),
        "allowed_codecs": sorted(p.allowed_codecs),
        "min_size": p.min_size,
        "max_size": p.max_size,
    })


def quality_profile_from_json(blob: str) -> QualityProfile:
    """Deserialize a :class:`QualityProfile` from its JSON string.

    Args:
        blob: JSON string produced by :func:`quality_profile_to_json`.

    Returns:
        The reconstructed :class:`QualityProfile`.
    """
    data = json.loads(blob)
    min_res_val = data.get("min_resolution")
    return QualityProfile(
        min_resolution=Resolution(min_res_val) if min_res_val is not None else None,
        required_audio=frozenset(data.get("required_audio", [])),
        allowed_codecs=frozenset(data.get("allowed_codecs", [])),
        min_size=data.get("min_size"),
        max_size=data.get("max_size"),
    )


def source_criteria_to_json(c: SourceCriteria) -> str:
    """Serialize a :class:`SourceCriteria` to a compact JSON string.

    Args:
        c: The criteria to serialize.

    Returns:
        JSON string suitable for storage in ``criteria_json`` column.
    """
    return json.dumps({
        "preferred_resolution": c.preferred_resolution.value if c.preferred_resolution is not None else None,
        "required_audio": sorted(c.required_audio),
    })


def source_criteria_from_json(blob: str) -> SourceCriteria:
    """Deserialize a :class:`SourceCriteria` from its JSON string.

    Args:
        blob: JSON string produced by :func:`source_criteria_to_json`.

    Returns:
        The reconstructed :class:`SourceCriteria`.
    """
    data = json.loads(blob)
    pref_res_val = data.get("preferred_resolution")
    return SourceCriteria(
        preferred_resolution=Resolution(pref_res_val) if pref_res_val is not None else None,
        required_audio=frozenset(data.get("required_audio", [])),
    )
```

Also add to `__all__` at bottom of `desired.py`:

```python
__all__ = [
    "QualityProfile",
    "Resolution",
    "SourceCriteria",
    "quality_profile_from_json",
    "quality_profile_to_json",
    "source_criteria_from_json",
    "source_criteria_to_json",
]
```

- [ ] **Step 4: Run all tests**

```bash
python -m pytest tests/acquire/test_desired.py -v
```

Expected: 9 PASSED (all tasks 1–4 tests).

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/desired.py tests/acquire/test_desired.py
git commit -m "feat(grab-core): add JSON codecs for QualityProfile and SourceCriteria"
```

---

## Task 5: Effective-profile precedence round-trip test

This test proves the SourceCriteria override logic (series default ← item override),
which is **decode-only at RP5b** — the helper `effective_quality` ships here but has no
live caller until Follow D4.

**Files:**

- Modify: `personalscraper/acquire/desired.py`
- Modify: `tests/acquire/test_desired.py`

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/acquire/test_desired.py
from personalscraper.acquire.desired import effective_quality


def test_effective_quality_series_default_when_no_override() -> None:
    series_profile = QualityProfile(min_resolution=Resolution.R1080P)
    item_criteria = SourceCriteria()  # no override
    result = effective_quality(series_profile, item_criteria)
    assert result.min_resolution == Resolution.R1080P


def test_effective_quality_item_overrides_resolution() -> None:
    series_profile = QualityProfile(min_resolution=Resolution.R1080P)
    item_criteria = SourceCriteria(preferred_resolution=Resolution.R720P)
    result = effective_quality(series_profile, item_criteria)
    # item preferred_resolution overrides series min_resolution
    assert result.min_resolution == Resolution.R720P


def test_effective_quality_item_overrides_audio() -> None:
    series_profile = QualityProfile(required_audio=frozenset({"VF"}))
    item_criteria = SourceCriteria(required_audio=frozenset({"VO"}))
    result = effective_quality(series_profile, item_criteria)
    assert result.required_audio == frozenset({"VO"})


def test_effective_quality_series_audio_preserved_when_no_item_override() -> None:
    series_profile = QualityProfile(required_audio=frozenset({"VF", "VOSTFR"}))
    item_criteria = SourceCriteria()  # empty = no override
    result = effective_quality(series_profile, item_criteria)
    assert result.required_audio == frozenset({"VF", "VOSTFR"})
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/acquire/test_desired.py::test_effective_quality_series_default_when_no_override -v
```

Expected: `ImportError`.

- [ ] **Step 3: Add `effective_quality` to `desired.py`**

```python
def effective_quality(series: QualityProfile, item: SourceCriteria) -> QualityProfile:
    """Merge series-level profile with per-item criteria (item overrides series).

    **RP5b: decode-only** — no live producer until Follow D4.  This helper is
    shipped so the precedence is tested, not speculative.

    Item fields override series fields only when explicitly set (non-None /
    non-empty): a ``SourceCriteria()`` with all defaults leaves the series
    profile unchanged.

    Args:
        series: Series-level :class:`QualityProfile` (from
            ``FollowedSeries.quality_profile_json``).
        item: Per-item :class:`SourceCriteria` override (from
            ``WantedItem.criteria_json``).

    Returns:
        Effective :class:`QualityProfile` to use for the grab attempt.
    """
    min_res = (
        item.preferred_resolution
        if item.preferred_resolution is not None
        else series.min_resolution
    )
    audio = item.required_audio if item.required_audio else series.required_audio
    return QualityProfile(
        min_resolution=min_res,
        required_audio=audio,
        allowed_codecs=series.allowed_codecs,
        min_size=series.min_size,
        max_size=series.max_size,
    )
```

Add `"effective_quality"` to `__all__`.

- [ ] **Step 4: Run full test file**

```bash
python -m pytest tests/acquire/test_desired.py -v
```

Expected: 13 PASSED.

- [ ] **Step 5: Smoke-test import**

```bash
python -c "from personalscraper.acquire.desired import Resolution, QualityProfile, SourceCriteria, effective_quality; print('OK')"
```

Expected: `OK`.

- [ ] **Step 6: Run make lint on the new file**

```bash
cd /Users/izno/dev/PersonnalScaper
python -m ruff check personalscraper/acquire/desired.py tests/acquire/test_desired.py
python -m mypy personalscraper/acquire/desired.py
python scripts/check-module-size.py personalscraper/acquire/desired.py
```

Expected: zero errors; module well under 200 LOC.

- [ ] **Step 7: Commit phase gate**

```bash
git add personalscraper/acquire/desired.py tests/acquire/test_desired.py
git commit -m "feat(grab-core): effective_quality precedence + phase 01 gate"
```

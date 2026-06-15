# Phase 1 — Cadence module + config + codec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add the pure `acquire/cadence.py` (VOs + predicates), `CadenceConfig` on `AcquireConfig`, the two `acquire.json5` config files, and four codec functions in `acquire/desired.py`. Tests: design criteria 1-3.

**Architecture:** `cadence.py` imports `core`/stdlib only — enforced by the layering test. Config in `conf/models/acquire.py` (Pydantic). Codecs in `desired.py` (alongside the existing quality_profile_json pattern).

**Tech Stack:** Python 3.11+, `dataclasses`, `pydantic`, `json`, `pytest`, `make test`

---

## Gate

_This is Phase 1 — no previous phase gate required._

---

## Sub-phase 1.1 — Create `acquire/cadence.py` with VOs + predicates

**Files:**

- Create: `personalscraper/acquire/cadence.py`
- Create: `tests/acquire/test_cadence.py`

### Task 1: Write failing predicate tests first (TDD)

- [ ] **Step 1: Create `tests/acquire/test_cadence.py` with boundary tests**

```python
"""Tests for acquire/cadence.py — Hot/Warm/Cold tier + cutoff predicates."""
from __future__ import annotations

import pytest

# Canonical cadence for tests: Hot <72h/2h, Warm <14d/1d, Cold <30d/7d, cutoff=30d
HOT_S = 2 * 3600
WARM_S = 24 * 3600
COLD_S = 7 * 24 * 3600
HOT_MAX = 72 * 3600
WARM_MAX = 14 * 24 * 3600
COLD_MAX = 30 * 24 * 3600
NOW = 1_000_000


def _canon():
    from personalscraper.acquire.cadence import Cadence, CadenceTier
    return Cadence(
        tiers=(
            CadenceTier(max_age_s=HOT_MAX, interval_s=HOT_S),
            CadenceTier(max_age_s=WARM_MAX, interval_s=WARM_S),
            CadenceTier(max_age_s=COLD_MAX, interval_s=COLD_S),
        ),
        cutoff_s=COLD_MAX,
    )


def test_is_due_hot_first_search():
    """age=0, last_search_at=None → due immediately (Hot tier)."""
    from personalscraper.acquire.cadence import is_due_by_cadence
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=NOW, last_search_at=None) is True


def test_is_due_hot_too_soon():
    """age=1h, last_search_at=30min ago → NOT due (Hot interval=2h)."""
    from personalscraper.acquire.cadence import is_due_by_cadence
    enqueued = NOW - 3600
    last = NOW - 1800
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is False


def test_is_due_hot_warm_boundary_minus1s():
    """age=72h-1s → still Hot tier, interval=2h."""
    from personalscraper.acquire.cadence import is_due_by_cadence
    enqueued = NOW - (HOT_MAX - 1)
    last = NOW - HOT_S - 1  # just past interval → due
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_warm_boundary_plus1s():
    """age=72h+1s → Warm tier, interval=1d."""
    from personalscraper.acquire.cadence import is_due_by_cadence
    enqueued = NOW - (HOT_MAX + 1)
    last = NOW - WARM_S - 1  # just past 1d interval → due
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_warm_cold_boundary_minus1s():
    """age=14d-1s → still Warm, interval=1d."""
    from personalscraper.acquire.cadence import is_due_by_cadence
    enqueued = NOW - (WARM_MAX - 1)
    last = NOW - WARM_S - 1
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_cold_boundary_plus1s():
    """age=14d+1s → Cold tier, interval=7d."""
    from personalscraper.acquire.cadence import is_due_by_cadence
    enqueued = NOW - (WARM_MAX + 1)
    last = NOW - COLD_S - 1
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is True


def test_is_due_cold_too_soon():
    """age=15d, last_search_at=3d ago → NOT due (Cold interval=7d)."""
    from personalscraper.acquire.cadence import is_due_by_cadence
    enqueued = NOW - (15 * 24 * 3600)
    last = NOW - (3 * 24 * 3600)
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=last) is False


def test_is_past_cutoff_false_before():
    """age=30d-1s → NOT past cutoff."""
    from personalscraper.acquire.cadence import is_past_cutoff
    assert is_past_cutoff(_canon(), now=NOW, enqueued_at=NOW - (COLD_MAX - 1)) is False


def test_is_past_cutoff_true_at():
    """age=30d exactly → past cutoff."""
    from personalscraper.acquire.cadence import is_past_cutoff
    assert is_past_cutoff(_canon(), now=NOW, enqueued_at=NOW - COLD_MAX) is True


def test_is_past_cutoff_true_after():
    """age=30d+1s → past cutoff."""
    from personalscraper.acquire.cadence import is_past_cutoff
    assert is_past_cutoff(_canon(), now=NOW, enqueued_at=NOW - (COLD_MAX + 1)) is True


def test_is_due_returns_false_past_cutoff():
    """is_due_by_cadence returns False when past cutoff (don't search, abandon)."""
    from personalscraper.acquire.cadence import is_due_by_cadence
    enqueued = NOW - (COLD_MAX + 1)
    assert is_due_by_cadence(_canon(), now=NOW, enqueued_at=enqueued, last_search_at=None) is False
```

- [ ] **Step 2: Confirm tests FAIL (module missing)**

```bash
pytest tests/acquire/test_cadence.py -v 2>&1 | head -15
```

Expected: `ModuleNotFoundError` — `personalscraper.acquire.cadence` does not exist.

### Task 2: Create `personalscraper/acquire/cadence.py`

- [ ] **Step 3: Create the module**

```python
"""Pure cadence value objects and predicates for the acquisition lobe (D2).

Defines the Hot/Warm/Cold backoff tiers and cutoff policy. Entirely pure:
imports ``core``/stdlib only — never ``scraper``, ``indexer``, ``store``, or
the event bus.

Logging: this module has no side-effects; callers log.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CadenceTier:
    """One tier in the Hot/Warm/Cold backoff ladder.

    Attributes:
        max_age_s: Upper bound (exclusive) of ages that fall in this tier,
            in seconds. Tiers must be ordered by max_age_s ascending.
        interval_s: Minimum gap between two searches while in this tier,
            in seconds.
    """

    max_age_s: int
    interval_s: int


@dataclass(frozen=True)
class Cadence:
    """Complete cadence policy for a wanted item.

    Attributes:
        tiers: Ordered tuple of :class:`CadenceTier` (ascending max_age_s).
            Covers Hot, Warm, Cold in the canonical policy.
        cutoff_s: Age in seconds at or after which the item is abandoned
            (``is_past_cutoff`` returns True; ``is_due_by_cadence`` returns False).
    """

    tiers: tuple[CadenceTier, ...]
    cutoff_s: int


def is_due_by_cadence(
    cadence: Cadence,
    *,
    now: int,
    enqueued_at: int,
    last_search_at: int | None,
) -> bool:
    """Return True iff the item should be (re)searched at ``now``.

    A never-searched item (``last_search_at is None``) is due immediately
    while inside the cadence window. Returns False when past cutoff, when no
    tier matches (age >= all tier max_age_s but below cutoff — treated as
    not-due), or when last_search_at is too recent for the current tier's
    interval.

    Args:
        cadence: The effective cadence policy for this item.
        now: Current unix epoch seconds (injected — no hidden clock).
        enqueued_at: Unix epoch seconds when the item was enqueued (age origin).
        last_search_at: Unix epoch seconds of the last search attempt, or None
            if never searched (None → due now while within the window).

    Returns:
        True iff the item is due for a (re)search.
    """
    if is_past_cutoff(cadence, now=now, enqueued_at=enqueued_at):
        return False

    age = now - enqueued_at
    # Select the first tier whose max_age_s > age (i.e. age < max_age_s).
    tier: CadenceTier | None = next((t for t in cadence.tiers if age < t.max_age_s), None)
    if tier is None:
        # age is between last tier max_age_s and cutoff_s — treat as not-due.
        return False

    if last_search_at is None:
        # Never searched → due now (within the window).
        return True

    return (now - last_search_at) >= tier.interval_s


def is_past_cutoff(cadence: Cadence, *, now: int, enqueued_at: int) -> bool:
    """Return True iff the item's age has reached or exceeded the cutoff.

    Args:
        cadence: The effective cadence policy.
        now: Current unix epoch seconds.
        enqueued_at: Unix epoch seconds when the item was enqueued.

    Returns:
        True iff (now - enqueued_at) >= cadence.cutoff_s.
    """
    return (now - enqueued_at) >= cadence.cutoff_s


__all__ = ["Cadence", "CadenceTier", "is_due_by_cadence", "is_past_cutoff"]
```

- [ ] **Step 4: Run predicate tests — all must PASS**

```bash
pytest tests/acquire/test_cadence.py -v
```

Expected: `11 passed`, `0 failed`.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/cadence.py tests/acquire/test_cadence.py
git commit -m "feat(follow-detect): add Cadence/CadenceTier VOs + is_due_by_cadence/is_past_cutoff"
```

---

## Sub-phase 1.2 — `CadenceConfig` on `AcquireConfig` + config files

**Files:**

- Modify: `personalscraper/conf/models/acquire.py`
- Modify: `config/acquire.json5`
- Modify: `config.example/acquire.json5`

### Task 3: Add `CadenceConfig` to `conf/models/acquire.py`

- [ ] **Step 1: Read the current `AcquireConfig` to locate the insert point**

```bash
grep -n "class AcquireConfig\|db_path\|__all__" personalscraper/conf/models/acquire.py --type py
```

- [ ] **Step 2: Add `CadenceTierConfig` + `CadenceConfig` before `AcquireConfig`, then add `cadence` field**

Add to imports at top of `conf/models/acquire.py` (after existing imports):

```python
from typing import List
```

Add before `class AcquireConfig`:

```python
def _default_tiers() -> "list[CadenceTierConfig]":
    """Return the canonical Hot/Warm/Cold tier defaults (DESIGN §3 frozen decision)."""
    return [
        CadenceTierConfig(max_age_hours=72, interval_minutes=120),   # Hot
        CadenceTierConfig(max_age_hours=336, interval_minutes=1440), # Warm (14d)
        CadenceTierConfig(max_age_hours=720, interval_minutes=10080), # Cold (30d)
    ]


class CadenceTierConfig(_StrictModel):
    """Config for one Hot/Warm/Cold tier.

    Attributes:
        max_age_hours: Upper age bound (exclusive) for this tier, in hours.
        interval_minutes: Minimum gap between searches in this tier, in minutes.
    """

    max_age_hours: int
    interval_minutes: int


class CadenceConfig(_StrictModel):
    """Global cadence policy config for the acquisition lobe.

    Attributes:
        tiers: Ordered list of :class:`CadenceTierConfig` (ascending max_age_hours).
            Defaults to the canonical Hot/Warm/Cold policy (DESIGN §3).
        cutoff_days: Age in days at which a wanted item is abandoned. Must exceed
            the last tier's max_age_hours / 24. Default: 30.
    """

    tiers: list[CadenceTierConfig] = Field(default_factory=_default_tiers)
    cutoff_days: int = 30
```

Modify `AcquireConfig` to add the `cadence` field after `db_path`:

```python
    cadence: CadenceConfig = Field(default_factory=CadenceConfig)
```

Update `__all__`:

```python
__all__ = ["AcquireConfig", "CadenceConfig", "CadenceTierConfig"]
```

- [ ] **Step 3: Smoke-test the config model**

```bash
python -c "
from personalscraper.conf.models.acquire import CadenceConfig, AcquireConfig
cfg = AcquireConfig()
print('tiers:', len(cfg.cadence.tiers))
print('cutoff_days:', cfg.cadence.cutoff_days)
"
```

Expected:

```
tiers: 3
cutoff_days: 30
```

- [ ] **Step 4: Add `cadence` block to `config/acquire.json5` and `config.example/acquire.json5`**

In both files, add inside the top-level object (alongside `db_path`):

```json5
cadence: {
  // Hot/Warm/Cold backoff — DESIGN §3 frozen policy (D2).
  tiers: [
    { max_age_hours: 72,  interval_minutes: 120  },  // Hot  — 0–72h,  re-search every 2h
    { max_age_hours: 336, interval_minutes: 1440 },  // Warm — 3–14d,  re-search every 1d
    { max_age_hours: 720, interval_minutes: 10080 }, // Cold — 14–30d, re-search every 7d
  ],
  cutoff_days: 30,
},
```

- [ ] **Step 5: Add config tests to `tests/acquire/test_cadence.py`**

Append to `tests/acquire/test_cadence.py`:

```python
def test_cadence_config_default_reproduces_hot_warm_cold():
    """CadenceConfig() must reproduce the DESIGN §3 frozen policy."""
    from personalscraper.conf.models.acquire import CadenceConfig
    cfg = CadenceConfig()
    assert len(cfg.tiers) == 3
    assert cfg.tiers[0].max_age_hours == 72
    assert cfg.tiers[0].interval_minutes == 120
    assert cfg.tiers[1].max_age_hours == 336
    assert cfg.tiers[1].interval_minutes == 1440
    assert cfg.tiers[2].max_age_hours == 720
    assert cfg.tiers[2].interval_minutes == 10080
    assert cfg.cutoff_days == 30


def test_acquire_config_has_cadence_field():
    """AcquireConfig() has a cadence field defaulting to CadenceConfig()."""
    from personalscraper.conf.models.acquire import AcquireConfig, CadenceConfig
    cfg = AcquireConfig()
    assert isinstance(cfg.cadence, CadenceConfig)
```

- [ ] **Step 6: Run config tests**

```bash
pytest tests/acquire/test_cadence.py -v -k "config"
```

Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/conf/models/acquire.py config/acquire.json5 config.example/acquire.json5 tests/acquire/test_cadence.py
git commit -m "feat(follow-detect): add CadenceConfig to AcquireConfig + acquire.json5 blocks"
```

---

## Sub-phase 1.3 — Codec functions in `acquire/desired.py`

**Files:**

- Modify: `personalscraper/acquire/desired.py`

### Task 4: Add cadence codec functions

- [ ] **Step 1: Add `json` import if not present and add codecs before `__all__`**

`json` is already imported in `desired.py`. Add after `source_criteria_from_json`:

```python
def cadence_to_json(cadence: "Cadence") -> str:
    """Serialize a :class:`~personalscraper.acquire.cadence.Cadence` to JSON.

    Args:
        cadence: The cadence to serialize.

    Returns:
        Compact JSON string for storage in ``FollowedSeries.cadence_json``.
    """
    from personalscraper.acquire.cadence import Cadence  # noqa: PLC0415 — avoid top-level cycle risk
    return json.dumps(
        {
            "tiers": [{"max_age_s": t.max_age_s, "interval_s": t.interval_s} for t in cadence.tiers],
            "cutoff_s": cadence.cutoff_s,
        }
    )


def cadence_from_json(blob: str | None) -> "Cadence | None":
    """Deserialize a :class:`~personalscraper.acquire.cadence.Cadence` from JSON.

    A ``None`` blob means "use the global default" — callers must supply the
    fallback via :func:`effective_cadence`.

    Args:
        blob: JSON string produced by :func:`cadence_to_json`, or ``None``.

    Returns:
        The reconstructed :class:`Cadence`, or ``None`` if blob is ``None``.
    """
    if blob is None:
        return None
    from personalscraper.acquire.cadence import Cadence, CadenceTier  # noqa: PLC0415
    data = json.loads(blob)
    return Cadence(
        tiers=tuple(CadenceTier(max_age_s=t["max_age_s"], interval_s=t["interval_s"]) for t in data["tiers"]),
        cutoff_s=data["cutoff_s"],
    )


def cadence_from_config(cfg: "CadenceConfig") -> "Cadence":
    """Convert a :class:`~personalscraper.conf.models.acquire.CadenceConfig` to a :class:`Cadence` VO.

    Unit bridge: hours/minutes/days (config) → seconds (VO).

    Args:
        cfg: Pydantic config model loaded from ``config/acquire.json5``.

    Returns:
        A :class:`Cadence` with all durations in seconds.
    """
    from personalscraper.acquire.cadence import Cadence, CadenceTier  # noqa: PLC0415
    return Cadence(
        tiers=tuple(
            CadenceTier(
                max_age_s=t.max_age_hours * 3600,
                interval_s=t.interval_minutes * 60,
            )
            for t in cfg.tiers
        ),
        cutoff_s=cfg.cutoff_days * 24 * 3600,
    )


def effective_cadence(series_override: "Cadence | None", global_default: "Cadence") -> "Cadence":
    """Return the effective cadence: series override if present, else global default.

    Precedence is whole-object (no field-by-field merge): the per-series
    ``cadence_json`` encodes a complete :class:`Cadence`. An absent
    (``None``) override means "use the global default verbatim".

    Args:
        series_override: Per-series cadence decoded from
            ``FollowedSeries.cadence_json``, or ``None``.
        global_default: Cadence built from ``config.acquire.cadence``.

    Returns:
        The effective :class:`Cadence` to use.
    """
    return series_override if series_override is not None else global_default
```

Add a `TYPE_CHECKING` guard at the top of `desired.py` if not already present:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from personalscraper.acquire.cadence import Cadence
    from personalscraper.conf.models.acquire import CadenceConfig
```

Update `__all__` in `desired.py` to append:

```python
    "cadence_from_config",
    "cadence_from_json",
    "cadence_to_json",
    "effective_cadence",
```

- [ ] **Step 2: Append codec + effective_cadence tests to `tests/acquire/test_cadence.py`**

```python
def test_cadence_round_trip_json():
    """cadence_to_json → cadence_from_json round-trips all fields."""
    from personalscraper.acquire.cadence import Cadence, CadenceTier
    from personalscraper.acquire.desired import cadence_from_json, cadence_to_json
    c = Cadence(tiers=(CadenceTier(max_age_s=100, interval_s=10),), cutoff_s=200)
    assert cadence_from_json(cadence_to_json(c)) == c


def test_cadence_from_json_none_returns_none():
    """cadence_from_json(None) returns None (use global default)."""
    from personalscraper.acquire.desired import cadence_from_json
    assert cadence_from_json(None) is None


def test_cadence_from_config_converts_units():
    """cadence_from_config converts hours/minutes/days → seconds correctly."""
    from personalscraper.conf.models.acquire import CadenceConfig, CadenceTierConfig
    from personalscraper.acquire.desired import cadence_from_config
    cfg = CadenceConfig(tiers=[CadenceTierConfig(max_age_hours=1, interval_minutes=30)], cutoff_days=2)
    c = cadence_from_config(cfg)
    assert c.tiers[0].max_age_s == 3600
    assert c.tiers[0].interval_s == 1800
    assert c.cutoff_s == 2 * 24 * 3600


def test_effective_cadence_series_wins():
    """effective_cadence returns series override when not None."""
    from personalscraper.acquire.cadence import Cadence, CadenceTier
    from personalscraper.acquire.desired import effective_cadence
    override = Cadence(tiers=(CadenceTier(max_age_s=10, interval_s=1),), cutoff_s=20)
    default = Cadence(tiers=(CadenceTier(max_age_s=999, interval_s=999),), cutoff_s=999)
    assert effective_cadence(override, default) is override


def test_effective_cadence_none_returns_default():
    """effective_cadence(None, default) returns default verbatim."""
    from personalscraper.acquire.cadence import Cadence, CadenceTier
    from personalscraper.acquire.desired import effective_cadence
    default = Cadence(tiers=(CadenceTier(max_age_s=999, interval_s=999),), cutoff_s=999)
    assert effective_cadence(None, default) is default
```

- [ ] **Step 3: Run codec tests**

```bash
pytest tests/acquire/test_cadence.py -v
```

Expected: all tests pass (predicate + config + codec), `0 failed`.

- [ ] **Step 4: Commit**

```bash
git add personalscraper/acquire/desired.py tests/acquire/test_cadence.py
git commit -m "feat(follow-detect): add cadence codecs + effective_cadence to desired.py"
```

---

## Phase 1 Gate

- [ ] **Run `make check`** — must exit 0.
- [ ] **Smoke test:** `python -c "import personalscraper"` — must print nothing and exit 0.
- [ ] **Layering check:** `rg "indexer|scraper|store|event_bus" --type py personalscraper/acquire/cadence.py` — must return no matches (exit 1).

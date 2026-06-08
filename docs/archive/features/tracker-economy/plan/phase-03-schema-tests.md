# Phase 3 — Economy schema unit tests

## Gate

**Requires Phase 2:**
`python -c "from personalscraper.conf.models.api_config import TrackerEconomyConfig, TrackerProviderConfig; print('ok')"` → `ok`

---

## Goal

Cover `TrackerEconomyConfig` and `TrackerProviderConfig.economy` with unit tests: valid policy, ratio ordering rejection, negative-value rejection, extra-field rejection, defaults, and economy-from-dict round-trip.

## Files

- **Create:** `tests/unit/test_tracker_economy_schema.py`

---

## Tasks

### Task 3.1 — Create `test_tracker_economy_schema.py`

- [ ] **Create** `tests/unit/test_tracker_economy_schema.py`:

```python
"""Unit tests for TrackerEconomyConfig + TrackerProviderConfig.economy.

Design: tracker-economy §Components.1 — schema validation rules.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from personalscraper.conf.models.api_config import TrackerEconomyConfig, TrackerProviderConfig


class TestTrackerEconomyConfig:
    """TrackerEconomyConfig Pydantic validation rules."""

    def test_valid_policy_stores_seconds(self) -> None:
        """Humanized duration strings are stored as integer seconds."""
        cfg = TrackerEconomyConfig(
            target_ratio=2.0, min_ratio=1.0,
            min_seed_time="72h", hit_and_run_grace="48h",  # type: ignore[arg-type]
        )
        assert cfg.min_seed_time == 259_200    # 72 * 3600
        assert cfg.hit_and_run_grace == 172_800  # 48 * 3600

    def test_bare_int_duration_passes_through(self) -> None:
        """A bare int is accepted as already-seconds."""
        assert TrackerEconomyConfig(target_ratio=1.5, min_seed_time=3600).min_seed_time == 3_600

    def test_target_ratio_below_min_ratio_rejected(self) -> None:
        """target_ratio < min_ratio raises ValidationError."""
        with pytest.raises(ValidationError, match="target_ratio"):
            TrackerEconomyConfig(target_ratio=0.5, min_ratio=1.0, min_seed_time=0)

    def test_negative_target_ratio_rejected(self) -> None:
        """Negative target_ratio raises ValidationError."""
        with pytest.raises(ValidationError, match="target_ratio must be >= 0"):
            TrackerEconomyConfig(target_ratio=-1.0, min_seed_time=0)

    def test_negative_min_ratio_rejected(self) -> None:
        """Negative min_ratio raises ValidationError."""
        with pytest.raises(ValidationError, match="min_ratio must be >= 0"):
            TrackerEconomyConfig(target_ratio=1.0, min_ratio=-0.1, min_seed_time=0)

    def test_extra_field_rejected(self) -> None:
        """_StrictModel forbids extra fields."""
        with pytest.raises(ValidationError):
            TrackerEconomyConfig(target_ratio=1.0, min_seed_time=0, unknown="oops")  # type: ignore[call-arg]

    def test_defaults(self) -> None:
        """min_ratio defaults to 1.0; hit_and_run_grace defaults to 0."""
        cfg = TrackerEconomyConfig(target_ratio=2.0, min_seed_time=0)
        assert cfg.min_ratio == 1.0
        assert cfg.hit_and_run_grace == 0

    def test_malformed_duration_rejected(self) -> None:
        """Malformed duration string raises ValidationError."""
        with pytest.raises(ValidationError):
            TrackerEconomyConfig(target_ratio=1.0, min_seed_time="bad")  # type: ignore[arg-type]


class TestTrackerProviderConfigEconomy:
    """TrackerProviderConfig.economy optional field behaviour."""

    def test_economy_none_by_default(self) -> None:
        """economy is None when not provided (activation-only mode)."""
        assert TrackerProviderConfig(enabled=True).economy is None

    def test_economy_attached_directly(self) -> None:
        """economy can be set to a TrackerEconomyConfig instance."""
        cfg = TrackerProviderConfig(
            enabled=True,
            economy=TrackerEconomyConfig(target_ratio=2.0, min_seed_time="72h"),  # type: ignore[arg-type]
        )
        assert cfg.economy is not None
        assert cfg.economy.min_seed_time == 259_200

    def test_economy_from_nested_dict(self) -> None:
        """model_validate with a nested economy dict coerces durations."""
        cfg = TrackerProviderConfig.model_validate({
            "enabled": True,
            "economy": {"target_ratio": 2.0, "min_seed_time": "72h", "hit_and_run_grace": "0h"},
        })
        assert cfg.economy is not None
        assert cfg.economy.min_seed_time == 259_200
```

- [ ] **Run:** `pytest tests/unit/test_tracker_economy_schema.py -v` → `11 passed`

---

### Task 3.2 — Commit

```bash
git add tests/unit/test_tracker_economy_schema.py
git commit -m "test(tracker-economy): TrackerEconomyConfig schema unit tests"
```

---

## Gate exit checklist

- [ ] `pytest tests/unit/test_tracker_economy_schema.py` → 11 passed, 0 failed
- [ ] Commit SHA recorded

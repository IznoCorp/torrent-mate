# Phase 1 — Duration parser (`_duration.py`) + unit tests

## Gate

This is the first phase. No prior phase dependency.

**Pre-flight:** `python -c "from personalscraper.conf.models.api_config import TrackerProviderConfig; print('ok')"` → `ok`

---

## Goal

Create `personalscraper/conf/models/_duration.py` with `parse_duration()` and cover it with unit tests. This is a prerequisite for Phase 2's `field_validator` on `TrackerEconomyConfig`.

---

## Files

- **Create:** `personalscraper/conf/models/_duration.py`
- **Create:** `tests/unit/test_duration.py`

---

## Tasks

### Task 1.1 — Create `_duration.py`

- [ ] **Create** `personalscraper/conf/models/_duration.py`:

```python
"""Humanized-duration parser for config models.

Converts strings like ``"72h"`` / ``"3d"`` to integer seconds at config-load
time. Used as a Pydantic field_validator on TrackerEconomyConfig seed-time fields.

Design: tracker-economy §Components.2.
"""
from __future__ import annotations

_UNIT_SECONDS: dict[str, int] = {"s": 1, "m": 60, "h": 3_600, "d": 86_400, "w": 604_800}


def parse_duration(value: str | int) -> int:
    """Parse humanized duration string or bare int to seconds.

    Args:
        value: ``"<int><unit>"`` (unit in s/m/h/d/w) or bare int (already seconds).

    Returns:
        Integer seconds.

    Raises:
        ValueError: Unknown unit, non-integer magnitude, or empty string.
    """
    if isinstance(value, int):
        return value
    raw = str(value).strip()
    if not raw:
        raise ValueError("duration string must not be empty")
    unit = raw[-1].lower()
    if unit not in _UNIT_SECONDS:
        raise ValueError(f"unknown duration unit {raw[-1]!r} in {raw!r}; valid: {', '.join(_UNIT_SECONDS)}")
    try:
        magnitude = int(raw[:-1])
    except ValueError:
        raise ValueError(f"non-integer magnitude {raw[:-1]!r} in duration {raw!r}") from None
    return magnitude * _UNIT_SECONDS[unit]


__all__ = ["parse_duration"]
```

- [ ] **Verify:** `python -c "from personalscraper.conf.models._duration import parse_duration; print(parse_duration('72h'))"` → `259200`

---

### Task 1.2 — Write and run `test_duration.py`

- [ ] **Create** `tests/unit/test_duration.py`:

```python
"""Tests for parse_duration() — tracker-economy §Components.2."""
from __future__ import annotations
import pytest
from personalscraper.conf.models._duration import parse_duration


class TestParseDuration:
    def test_seconds_unit(self) -> None:
        assert parse_duration("90s") == 90

    def test_minutes_unit(self) -> None:
        assert parse_duration("90m") == 5_400

    def test_hours_unit(self) -> None:
        assert parse_duration("72h") == 259_200

    def test_days_unit(self) -> None:
        assert parse_duration("3d") == 259_200

    def test_weeks_unit(self) -> None:
        assert parse_duration("2w") == 1_209_600

    def test_bare_int(self) -> None:
        assert parse_duration(3600) == 3_600

    def test_zero_value(self) -> None:
        assert parse_duration("0h") == 0

    def test_unit_case_insensitive(self) -> None:
        assert parse_duration("24H") == 86_400

    def test_malformed_no_unit(self) -> None:
        with pytest.raises(ValueError, match="unknown duration unit"):
            parse_duration("3600")

    def test_malformed_non_integer_magnitude(self) -> None:
        with pytest.raises(ValueError, match="non-integer magnitude"):
            parse_duration("1.5h")

    def test_malformed_unknown_unit(self) -> None:
        with pytest.raises(ValueError, match="unknown duration unit"):
            parse_duration("3x")

    def test_empty_string(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            parse_duration("")
```

- [ ] **Run:** `pytest tests/unit/test_duration.py -v` → `12 passed`

---

### Task 1.3 — Commit

```bash
git add personalscraper/conf/models/_duration.py tests/unit/test_duration.py
git commit -m "feat(tracker-economy): parse_duration helper + unit tests"
```

---

## Gate exit checklist

- [ ] `parse_duration('72h')` prints `259200` → exit 0
- [ ] `pytest tests/unit/test_duration.py` → 12 passed, 0 failed
- [ ] Commit SHA recorded

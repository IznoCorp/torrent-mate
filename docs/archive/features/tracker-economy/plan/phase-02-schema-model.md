# Phase 2 — Economy schema model

## Gate

**Requires Phase 1:**
`python -c "from personalscraper.conf.models._duration import parse_duration; print(parse_duration('72h'))"` → `259200`

---

## Goal

Add `TrackerEconomyConfig` to `api_config.py` and attach it optionally to `TrackerProviderConfig`.

## Files

- **Modify:** `personalscraper/conf/models/api_config.py`

---

## Tasks

### Task 2.1 — Modify `api_config.py`

- [ ] Extend pydantic import to include `field_validator` (file already has `Field, model_validator`):
      `from pydantic import Field, field_validator, model_validator`

- [ ] Add after the `_ranking` imports block:
      `from personalscraper.conf.models._duration import parse_duration`

- [ ] **Insert before `class TrackerProviderConfig`** (in the `# Tracker config (DESIGN S8.4)` section):

```python
class TrackerEconomyConfig(_StrictModel):
    """Per-tracker seeding economy. Data-carrier for Ratio C1 + Seed-Safety O2 (Vague 5).

    Attributes:
        target_ratio: Ratio Ratio-C1 loops toward. Must be >= min_ratio.
        min_ratio: Deletion floor for O2. Default 1.0.
        min_seed_time: Minimum seed time in seconds. Accepts humanized string (e.g. "72h").
        hit_and_run_grace: Grace seconds after download before H&R counting. Default 0.
    """

    target_ratio: float
    min_ratio: float = 1.0
    min_seed_time: int
    hit_and_run_grace: int = 0

    @field_validator("min_seed_time", "hit_and_run_grace", mode="before")
    @classmethod
    def _parse_duration_field(cls, v: object) -> int:
        """Coerce humanized duration string to integer seconds.

        Args:
            v: Raw config value — humanized string or bare int.

        Returns:
            Integer seconds.
        """
        return parse_duration(v)  # type: ignore[arg-type]

    @model_validator(mode="after")
    def _validate_ratio_ordering(self) -> "TrackerEconomyConfig":
        """Enforce target_ratio >= min_ratio and all values >= 0.

        Returns:
            Self after validation.

        Raises:
            ValueError: If target_ratio < min_ratio or any field is negative.
        """
        if self.target_ratio < self.min_ratio:
            raise ValueError(f"target_ratio ({self.target_ratio}) must be >= min_ratio ({self.min_ratio})")
        for name in ("target_ratio", "min_ratio", "min_seed_time", "hit_and_run_grace"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0, got {getattr(self, name)}")
        return self
```

- [ ] **Replace `TrackerProviderConfig` body** (add `economy`, keep `enabled`):

```python
class TrackerProviderConfig(_StrictModel):
    """Per-tracker toggle in tracker.json5.

    Attributes:
        enabled: Whether this tracker is active.
        economy: Optional seeding economy policy. None = activation-only mode.
    """

    enabled: bool = False
    economy: TrackerEconomyConfig | None = None
```

- [ ] Add `"TrackerEconomyConfig"` to `__all__`.

- [ ] Verify:
      `python -c "from personalscraper.conf.models.api_config import TrackerEconomyConfig, TrackerProviderConfig; print('ok')"` → `ok`

---

### Task 2.2 — Commit

```bash
git add personalscraper/conf/models/api_config.py
git commit -m "feat(tracker-economy): TrackerEconomyConfig schema + TrackerProviderConfig.economy field"
```

---

## Gate exit checklist

- [ ] `python -c "from personalscraper.conf.models.api_config import TrackerEconomyConfig, TrackerProviderConfig"` → exit 0
- [ ] Commit SHA recorded

# Phase 3 — Cross-seed + watch configuration

## Gate

- **Requires Phase 2**: `QBitClient` has `inject()` / `list_files()` / `properties()` ready — the config phase unlocks consumption of RP10b by future phases.
- **Requires nothing from Phase 1 directly** (the config doesn't import `_layout`), but Phase 1 should be done first per the dependency order in INDEX.md.
- **Produces for Phase 4**: `TrackerProviderConfig.cross_seed` field, `CrossSeedConfig` + `WatchConfig` models importable, both `config/` and `config.example/` overlays updated.

## Overview

Add `cross_seed: bool` to `TrackerProviderConfig` (RP2 family, per-tracker opt-in). Add new top-level config blocks `cross_seed` and `watch` in a new `personalscraper/conf/models/watch_seed.py`. Wire them into the config loader. Update **both** `config/` and `config.example/` (anti-drift rule). No tracker-override merge logic — each tracker JSON5 gets a `cross_seed` field directly.

### Sub-phases (4 commits)

| #   | Commit                                                              | Scope            |
| --- | ------------------------------------------------------------------- | ---------------- |
| 3.1 | `feat(watch-seed): add cross_seed field to TrackerProviderConfig`   | Model + overlays |
| 3.2 | `feat(watch-seed): add CrossSeedConfig and WatchConfig models`      | Config models    |
| 3.3 | `feat(watch-seed): wire watch_seed config into the app config tree` | Wiring           |
| 3.4 | `test(watch-seed): add config validation and overlay tests`         | Tests            |

## Sub-phase 3.1 — cross_seed field on TrackerProviderConfig

**Files:**

- Modify: `personalscraper/conf/models/api_config.py` (`TrackerProviderConfig`)
- Modify: `config/tracker.json5` + `config.example/tracker.json5`

Add the field to the existing pydantic model:

```python
class TrackerProviderConfig(_StrictModel):
    """Per-tracker toggle in tracker.json5.

    Attributes:
        enabled: Whether this tracker is active.
        economy: Optional seeding economy policy.
        cross_seed: Allow this tracker to receive cross-seed injections.
            Defaults to False — trackers must opt in (D9).
        enrich_seeders: ...
        enrich_seeders_top_k: ...
    """

    enabled: bool = False
    economy: TrackerEconomyConfig | None = None
    cross_seed: bool = False    # <-- NEW (D9: opt-in gate)
    enrich_seeders: bool = False
    enrich_seeders_top_k: int = 10
```

Update BOTH tracker.json5 files to include `cross_seed: false` in each provider block (after `enabled: false`):

```json5
lacale: {
    enabled: false,
    cross_seed: false,
    // economy: { ... }
},
c411: {
    enabled: false,
    cross_seed: false,
    // economy: { ... }
},
torr9: {
    enabled: false,
    cross_seed: false,
    // economy: { ... }
},
```

## Sub-phase 3.2 — CrossSeedConfig + WatchConfig models

**Files:**

- Create: `personalscraper/conf/models/watch_seed.py`

```python
"""Watch + cross-seed configuration models (watch-seed feature).

See docs/features/watch-seed/DESIGN.md §Config.
"""

from pydantic import Field

from personalscraper.conf.models._base import _StrictModel


class WatchConfig(_StrictModel):
    """Watcher daemon configuration.

    Attributes:
        enabled: Global kill-switch for the watcher daemon. When False,
            ``personalscraper watch`` exits immediately.
        poll_interval_s: Seconds between poll cycles (default 60).
        debounce_s: Quiet window after a pipeline trigger — new completions
            do not fire another run during this window (default 900 = 15 min).
        safety_net_hours: If no successful pipeline run for this many hours,
            fire a safety-net run regardless of debounce (default 24).
    """

    enabled: bool = False
    poll_interval_s: int = Field(default=60, ge=10, le=3600)
    debounce_s: int = Field(default=900, ge=60, le=86400)
    safety_net_hours: int = Field(default=24, ge=1, le=168)


class CrossSeedConfig(_StrictModel):
    """Cross-seeding engine configuration.

    Attributes:
        enabled: Global kill-switch. When False, all cross-seed activity
            (per-completion + sweep) is disabled.
        max_searches_per_day: Daily quota for search operations (back-catalog
            sweep). Per-completion searches are NOT counted against this quota
            (they are targeted, one hash = one search).
        min_delay_between_searches_s: Minimum seconds between two search
            operations (throttle).
        exclude_recent_search_days: Skip torrents whose info_hash was already
            searched within this many days.
    """

    enabled: bool = False
    max_searches_per_day: int = Field(default=250, ge=1)
    min_delay_between_searches_s: int = Field(default=30, ge=5)
    exclude_recent_search_days: int = Field(default=3, ge=1)
```

## Sub-phase 3.3 — wire into app config tree

**Files:**

- Modify: `personalscraper/conf/models/config.py` (or wherever the `AppConfig` root model lives)
- Modify: `config/config.json5` + `config.example/config.json5` (add `cross_seed` and `watch` blocks)

Add to the root `AppConfig` model:

```python
from personalscraper.conf.models.watch_seed import CrossSeedConfig, WatchConfig

class AppConfig(_StrictModel):
    # ... existing fields ...
    cross_seed: CrossSeedConfig = Field(default_factory=CrossSeedConfig)
    watch: WatchConfig = Field(default_factory=WatchConfig)
```

Add the new blocks to BOTH `config/config.json5` and `config.example/config.json5` (anti-drift):

```json5
// ... existing blocks ...
, cross_seed: {
    enabled: false,
    // max_searches_per_day: 250,
    // min_delay_between_searches_s: 30,
    // exclude_recent_search_days: 3,
}
, watch: {
    enabled: false,
    // poll_interval_s: 60,
    // debounce_s: 900,
    // safety_net_hours: 24,
}
```

## Sub-phase 3.4 — config validation + overlay tests

**Files:**

- Create: `tests/unit/conf/test_watch_seed_config.py`

Tests:

- `test_tracker_provider_cross_seed_defaults_false` — `TrackerProviderConfig().cross_seed` is `False` (ACC-4).
- `test_cross_seed_config_defaults` — `CrossSeedConfig()` has correct defaults.
- `test_watch_config_defaults` — `WatchConfig()` has correct defaults.
- `test_poll_interval_below_min_rejected` — `WatchConfig(poll_interval_s=5)` raises `ValidationError`.
- `test_max_searches_invalid_rejected` — `CrossSeedConfig(max_searches_per_day=0)` raises `ValidationError`.
- `test_config_json5_has_cross_seed_blocks` — grep both `config/` and `config.example/` master files for `cross_seed` and `watch` keys (verify anti-drift).

## Gate check (before advancing to Phase 4)

- [ ] `make lint` — 0 errors.
- [ ] `python -c "from personalscraper.conf.models.api_config import TrackerProviderConfig; print(TrackerProviderConfig().cross_seed)"` → `False` (ACC-4).
- [ ] `grep -c 'cross_seed' config/tracker.json5 config.example/tracker.json5` — each ≥ 3 (one per provider).
- [ ] `python -m pytest tests/unit/conf/test_watch_seed_config.py -q` — all pass.
- [ ] `python -c "import personalscraper"` — smoke test (config modules load clean).

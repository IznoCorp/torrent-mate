# Phase 4 — CrossSeedService: X1 core + X2 sweep

## Gate

- **Requires Phase 1**: `TorrentLayout` + `parse_torrent_layout()` + `structural_match()` importable.
- **Requires Phase 2**: `TorrentInjector` protocol + `QBitClient.inject()` / `list_files()` / `properties()` + `TorrentItem.save_path` / `completion_on` ready.
- **Requires Phase 3**: `TrackerProviderConfig.cross_seed` field + `CrossSeedConfig` available in `AppContext.config`.
- **Produces for Phase 5**: `CrossSeedService` class importable from `acquire/cross_seed.py` with `check(info_hash)` + `sweep()` methods, and `acquire.db` sub-stores for search history + quota counter.

## Overview

Build `CrossSeedService` in `acquire/` — a thin orchestrator consuming RP10a+RP10b + existing ports (`TrackerRegistry.search_candidates`, `resolve_source`/`fetch_torrent_source`, `SEED_PURE` tag, `SeedObligation` + `SeedSubStore.add`). Injected via `_build_app_context` with **one handle** (RP5c discipline). Depends only downward on `api/` ports + `acquire.db`. X1: per-completion `check(info_hash)`. X2: back-catalog `sweep()` with throttle/quota/exclude-recent.

### Sub-phases (5 commits)

| #   | Commit                                                                   | Scope     |
| --- | ------------------------------------------------------------------------ | --------- |
| 4.1 | `feat(watch-seed): add cross-seed sub-stores to acquire.db`              | DB schema |
| 4.2 | `feat(watch-seed): implement CrossSeedService.check() — X1 core`         | X1        |
| 4.3 | `feat(watch-seed): implement CrossSeedService.sweep() — X2 back-catalog` | X2        |
| 4.4 | `feat(watch-seed): wire CrossSeedService into the acquire context`       | Wiring    |
| 4.5 | `test(watch-seed): add unit + integration tests for CrossSeedService`    | Tests     |

## Sub-phase 4.1 — cross-seed sub-stores in acquire.db

**Files:**

- Modify: `personalscraper/acquire/store.py` (add `_CrossSeedStore` or extend existing)
- Modify: `personalscraper/acquire/domain.py` (add dataclasses if needed)

Two tiny tables in the existing `acquire.db` (lazy-open + BEGIN IMMEDIATE discipline, per the composition-root rule):

```sql
CREATE TABLE IF NOT EXISTS cross_seed_history (
    source_hash TEXT NOT NULL,
    tracker TEXT NOT NULL,
    searched_at REAL NOT NULL,  -- Unix timestamp (float)
    PRIMARY KEY (source_hash, tracker)
);

CREATE TABLE IF NOT EXISTS cross_seed_quota (
    date TEXT NOT NULL,         -- 'YYYY-MM-DD'
    count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (date)
);
```

Add store methods:

```python
def record_search(self, source_hash: str, tracker: str) -> None:
    """Record a cross-seed search attempt."""

def was_searched_recently(self, source_hash: str, tracker: str, days: int) -> bool:
    """True if source_hash+tracker pair was searched within *days*."""

def daily_searches_remaining(self, max_per_day: int) -> int:
    """Return remaining quota for today (max_per_day - today's count)."""

def increment_daily_count(self) -> None:
    """Increment today's search count. UNSAFE outside a transaction."""
```

## Sub-phase 4.2 — CrossSeedService.check() (X1 core)

**Files:**

- Create: `personalscraper/acquire/cross_seed.py`

```python
"""Cross-seeding engine — thin orchestration over RP10a+b + existing ports.

This module lives in ``acquire/`` per DESIGN §Architecture: it depends
downward on ``api/`` ports + ``acquire.db``, never importing triage packages.
"""

from __future__ import annotations

from personalscraper.logger import get_logger

logger = get_logger(__name__)

# For type hints only — the concrete types are passed at construction
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.api.torrent._contracts import TorrentLister, TorrentInjector
    from personalscraper.conf.models.api_config import TrackerProviderConfig
    from personalscraper.acquire.store import AcquireStore


class CrossSeedService:
    """Orchestrates cross-seed matching + injection for completed torrents.

    One instance per process lifetime, built in :func:`_build_app_context`.
    Depends on *ports* (protocols), not concrete tracker/transport
    implementations — inject fakes for testing.
    """

    def __init__(
        self,
        registry: TrackerRegistry,
        lister: TorrentLister,
        injector: TorrentInjector,
        controller: TorrentController,
        tagger: TorrentTagger,
        store: AcquireStore,
        config,  # AppConfig — typed loosely to avoid circular imports
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._registry = registry
        self._lister = lister
        self._injector = injector
        self._controller = controller
        self._tagger = tagger
        self._store = store
        self._config = config
        self._clock = clock
        self._sleep = sleep

    def check(self, info_hash: str) -> CrossSeedResult:
        """Per-completion cross-seed for a single torrent (X1 — D3).

        Steps:
        1. Read source layout via :meth:`TorrentInjector.list_files` +
           :meth:`TorrentInjector.properties` → build local ``TorrentLayout``.
        2. Skip if tagged ``SEED_PURE`` or v2/hybrid.
        3. Build query from the release name (D7: strongest signal).
        4. ``search_candidates(name, media_type)`` — managed trackers,
           origin excluded, ``cross_seed=true`` gate (D5, D9).
        5. For each candidate: fetch .torrent → parse → structural_match.
        6. On match → inject (paused, recheck) → poll → if 100%: resume +
           tag SEED_PURE + write SeedObligation (D10).
        7. Record search in history.
        """
        ...
```

Flow exactly as DESIGN §"Cross-seed engine flow". `CrossSeedResult` is a small dataclass: `injected: list[str]` (hashes), `rejected: list[tuple[str, str, str]]` (hash, tracker, reason), `skipped: bool` (SEED_PURE or v2/hybrid).

The method calls are synchronous — no asyncio. The `injector.inject()` → poll loop reuses `TorrentStateInspector` (already available) to check state after recheck.

## Sub-phase 4.3 — CrossSeedService.sweep() (X2 back-catalog)

**Files:**

- Modify: `personalscraper/acquire/cross_seed.py` (add `sweep()` method)

```python
def sweep(self) -> SweepResult:
    """Throttled back-catalog sweep (X2 — D6).

    Iterates ALL completed torrents (via :meth:`TorrentLister.get_completed`),
    skipping SEED_PURE-tagged ones.  For each:
    - Check daily quota (``max_searches_per_day``).
    - Check exclude-recent (``exclude_recent_search_days`` — skip if
      recently searched).
    - Honor ``min_delay_between_searches_s`` via ``time.sleep()``.
    - Call ``self.check(info_hash)`` for each eligible torrent.

    Stops early when quota is exhausted.

    Returns:
        SweepResult with counts: checked, injected, quota_exhausted.
    """
    ...
```

`SweepResult` dataclass: `checked: int`, `injected: int`, `quota_exhausted: bool`.

## Sub-phase 4.4 — wire CrossSeedService into the acquire context

**Files:**

- Modify: `personalscraper/acquire/context.py` (add `cross_seed` field to `AcquireContext`)
- Modify: `personalscraper/acquire/_factory.py` (`build_acquire_context` — the RP5c one-handle seam)

Build `CrossSeedService` inside `build_acquire_context` (RP5c discipline — NOT `_build_app_context` directly) after the `TrackerRegistry` and store are available, mirroring the `GrabCore` conditional pattern. The service is built ONLY when the `torrent_client` satisfies ALL four required capabilities (`TorrentLister`, `TorrentInjector`, `TorrentController`, `TorrentTagger`). Transmission clients lack `TorrentInjector` → `cross_seed` stays `None` (logged at debug).

```python
# In build_acquire_context, after building grab:
cross_seed: CrossSeedService | None = None
if torrent_client is not None:
    from personalscraper.api.torrent._contracts import (
        TorrentController, TorrentInjector, TorrentLister, TorrentTagger,
    )
    if (
        isinstance(torrent_client, TorrentLister)
        and isinstance(torrent_client, TorrentInjector)
        and isinstance(torrent_client, TorrentController)
        and isinstance(torrent_client, TorrentTagger)
    ):
        from personalscraper.acquire.cross_seed import CrossSeedService
        cross_seed = CrossSeedService(
            registry=tracker_registry,
            lister=torrent_client,
            injector=torrent_client,
            controller=torrent_client,
            tagger=torrent_client,
            store=store,
            config=config,
        )
```

The same `torrent_client` instance satisfies all four protocol roles (QBitClient composes all of them).

## Sub-phase 4.5 — tests

**Files:**

- Create: `tests/integration/acquire/test_cross_seed_service.py` (ACC-6)

Tests with faked registry + transport + torrent client:

- `test_check_injects_on_match_and_tags_and_writes_obligation` — happy path: 1 match → inject → 100% verified → SEED_PURE tag + SeedObligation (ACC-6).
- `test_check_recheck_fails_removes_without_obligation` — inject → recheck → not 100% → remove injection, no obligation (ACC-6).
- `test_check_idempotent_rerun` — same hash called twice → second call returns `skipped=True` (recently searched).
- `test_check_origin_tracker_excluded` — a candidate from the same tracker as the source is not included.
- `test_check_seed_pure_skipped` — SEED_PURE-tagged torrent → `skipped=True`.
- `test_check_v2_hybrid_skipped` — `meta_version=2` → `skipped=True`.
- `test_check_cross_seed_disabled_tracker_excluded` — tracker with `cross_seed: false` is not queried.
- `test_sweep_quota_exhausted_stops` — `max_searches_per_day=2` → after 2 searches, sweep exits with `quota_exhausted=True`.
- `test_sweep_exclude_recent_respected` — hash searched < 3 days ago → skipped.
- `test_sweep_delay_respected` — timing test: `min_delay_between_searches_s=0.1` → 2 searches take ≥ 0.2 s total.

## Gate check (before advancing to Phase 5)

- [ ] `make lint` — 0 errors.
- [ ] `python -m pytest tests/integration/acquire/test_cross_seed_service.py -q` — all pass (ACC-6).
- [ ] `personalscraper/acquire/cross_seed.py` ≤ 800 LOC (soft).
- [ ] `acquire/` does not import from `commands/` or `pipeline/` — verified by `tests/architecture/test_layering.py`.

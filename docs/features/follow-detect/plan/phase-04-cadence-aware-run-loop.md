# Phase 4 — Cadence-aware run loop

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Insert cutoff + cadence checks BEFORE `claim_for_search` in `AcquisitionService._process_item` (`service.py:233-298`). Emit `WantedAbandoned(reason='cutoff_reached')` at cutoff. Build a `followed_id → FollowedSeries` map once per `run()` call. Retire `_STALE_THRESHOLD_S` as the cadence decision (it stays as the stale-recovery window). Tests: design criterion 7.

**Architecture:** `_process_item` receives `cadence: Cadence` as a new parameter (computed once per item in `run()` via `effective_cadence`). The stale-searching re-promotion at line 260-261 is unchanged; the two new checks sit between the re-promotion and `claim_for_search`. `RunSummary` semantics: not-due → `skipped`; cutoff → `abandoned`.

**Tech Stack:** Python 3.11+, `sqlite3`, `pytest`, `unittest.mock`, `make test`

---

## Gate

Phase 3 must be complete:

- [ ] `personalscraper/commands/follow.py` exports `follow_detect`.
- [ ] `pytest tests/commands/test_follow_detect.py` passes with 0 failures.

---

## Sub-phase 4.1 — Modify `AcquisitionService`

**Files:**

- Modify: `personalscraper/acquire/service.py`
- Create: `tests/acquire/test_service_cadence.py`

### Task 1: Write failing cadence-aware loop tests first (TDD)

> **PLAN-DRIFT (corrected during 4.1):** the service computes
> `now = int(time.time())` (service.py), so tests pin the clock by patching
> `personalscraper.acquire.service.time.time` — NOT the builtin `int` (patching
> `int` would also corrupt the `now - _STALE_THRESHOLD_S` arithmetic). This
> follows the existing `test_service.py` §11d precedent. `FollowedSeries` is not
> referenced in the cadence test module (the store stub returns `None` for
> `follow.get`), so it is not imported there.

- [ ] **Step 1: Create `tests/acquire/test_service_cadence.py`**

```python
"""Tests for cadence-aware AcquisitionService._process_item (criterion 7)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from personalscraper.acquire.cadence import Cadence, CadenceTier
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import WantedAbandoned
from personalscraper.acquire.service import AcquisitionService
from personalscraper.core.identity import MediaRef

NOW = 2_000_000
ENQUEUED_RECENT = NOW - 3600         # 1h ago → Hot tier
ENQUEUED_CUTOFF = NOW - (30 * 24 * 3600)  # exactly 30d → past cutoff


def _canon_cadence() -> Cadence:
    return Cadence(
        tiers=(
            CadenceTier(max_age_s=72 * 3600, interval_s=2 * 3600),    # Hot
            CadenceTier(max_age_s=14 * 24 * 3600, interval_s=86400),  # Warm
            CadenceTier(max_age_s=30 * 24 * 3600, interval_s=7 * 86400),  # Cold
        ),
        cutoff_s=30 * 24 * 3600,
    )


def _pending_item(enqueued_at: int, last_search_at: int | None = None, followed_id: int = 1) -> WantedItem:
    return WantedItem(
        id=10,
        media_ref=MediaRef(tvdb_id=99),
        kind="episode",
        status="pending",
        enqueued_at=enqueued_at,
        followed_id=followed_id,
        season=1,
        episode=1,
        last_search_at=last_search_at,
        attempts=0,
    )


def _make_config():
    """Return a minimal config stub with the canonical cadence (Hot/Warm/Cold/30d)."""
    from personalscraper.conf.models.acquire import AcquireConfig
    config = MagicMock()
    config.acquire = AcquireConfig()  # default cadence — Hot/Warm/Cold/30d
    return config


def _make_service(pending: list[WantedItem], stale: list[WantedItem] | None = None):
    """Build a minimal AcquisitionService with a stubbed store, orchestrator, bus, config."""
    store = MagicMock()
    store.wanted.list_pending.return_value = pending
    store.wanted.list_stale_searching.return_value = stale or []
    store.wanted.claim_for_search.return_value = True
    store.wanted.get.return_value = pending[0] if pending else None
    store.follow.get.return_value = None  # no FollowedSeries override → global cadence

    orchestrator = MagicMock()
    orchestrator.grab.return_value = MagicMock(disposition="success", info_hash="abc123")

    bus = MagicMock()
    config = _make_config()

    svc = AcquisitionService(store=store, orchestrator=orchestrator, event_bus=bus, config=config)
    return svc, store, orchestrator, bus


def test_not_due_item_is_skipped_no_claim():
    """A not-yet-due item (last_search_at 30min ago, Hot interval=2h) → skipped, no claim."""
    item = _pending_item(enqueued_at=ENQUEUED_RECENT, last_search_at=NOW - 1800)
    svc, store, orchestrator, bus = _make_service([item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_search.assert_not_called()
    orchestrator.grab.assert_not_called()
    assert summary.skipped == 1
    assert summary.grabbed == 0


def test_due_item_proceeds_to_claim():
    """A due item (last_search_at=None, Hot tier) → claim called, grab proceeds."""
    item = _pending_item(enqueued_at=ENQUEUED_RECENT, last_search_at=None)
    svc, store, orchestrator, bus = _make_service([item])
    store.wanted.get.return_value = WantedItem(
        id=10, media_ref=MediaRef(tvdb_id=99), kind="episode", status="searching",
        enqueued_at=ENQUEUED_RECENT, followed_id=1, season=1, episode=1, attempts=1,
    )

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_search.assert_called_once()
    assert summary.grabbed == 1


def test_cutoff_item_abandoned_no_claim():
    """Past-cutoff item → set_status('abandoned') called, WantedAbandoned emitted, no claim."""
    item = _pending_item(enqueued_at=ENQUEUED_CUTOFF, last_search_at=None)
    svc, store, orchestrator, bus = _make_service([item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        summary = svc.run()

    store.wanted.claim_for_search.assert_not_called()
    store.wanted.set_status.assert_called_once_with(10, "abandoned")
    bus.emit.assert_called_once()
    emitted = bus.emit.call_args[0][0]
    assert isinstance(emitted, WantedAbandoned)
    assert emitted.reason == "cutoff_reached"
    assert summary.abandoned == 1


def test_cutoff_abandoned_before_grab():
    """Cutoff abandon happens BEFORE any grab attempt — orchestrator.grab not called."""
    item = _pending_item(enqueued_at=ENQUEUED_CUTOFF)
    svc, store, orchestrator, bus = _make_service([item])

    with patch("personalscraper.acquire.service.time.time", return_value=NOW):
        svc.run()

    orchestrator.grab.assert_not_called()
```

- [ ] **Step 2: Confirm tests FAIL (checks not yet inserted)**

```bash
pytest tests/acquire/test_service_cadence.py -v 2>&1 | head -20
```

Expected: failures — the cutoff/cadence checks do not exist yet.

### Task 2: Modify `AcquisitionService` in `service.py`

- [ ] **Step 3: Read `service.py:1-75` to locate imports and `_STALE_THRESHOLD_S`**

```bash
grep -n "^from\|^import\|_STALE_THRESHOLD_S\|FollowedSeries\|store\.follow" personalscraper/acquire/service.py --type py | head -30
```

- [ ] **Step 4: Add required imports to `service.py`**

Add after existing imports (near the top, alongside `WantedItem` etc.):

```python
from personalscraper.acquire.cadence import Cadence, is_due_by_cadence, is_past_cutoff
from personalscraper.acquire.desired import cadence_from_config, cadence_from_json, effective_cadence
from personalscraper.acquire.domain import FollowedSeries
```

- [ ] **Step 5: Modify `run()` to build a `followed_id → FollowedSeries` map and pass `cadence` to `_process_item`**

In `run()` (currently `service.py:151`), after building `queue` and before the `for item in queue` loop, add:

```python
        # Build cadence resolution map once per run (DESIGN §7).
        # Items with followed_id=None fall back to the global default.
        global_cadence = cadence_from_config(self._config.acquire.cadence)
        follow_map: dict[int, FollowedSeries] = {}
        for item in queue:
            if item.followed_id is not None and item.followed_id not in follow_map:
                fs = self._store.follow.get(item.followed_id)
                if fs is not None:
                    follow_map[item.followed_id] = fs
```

Also update the `_process_item` call inside the loop from:

```python
                outcome_tag = self._process_item(item, now)
```

to:

```python
                fs = follow_map.get(item.followed_id) if item.followed_id is not None else None
                cadence = effective_cadence(
                    cadence_from_json(fs.cadence_json) if fs is not None else None,
                    global_cadence,
                )
                outcome_tag = self._process_item(item, now, cadence=cadence)
```

**Note:** `self._config` must be injected. Update `__init__` to accept `config` parameter:

```python
    def __init__(
        self,
        *,
        store: AcquireStore,
        orchestrator: GrabOrchestrator,
        event_bus: EventBus,
        config: "Config",
    ) -> None:
        """Initialise the service with injected narrow deps.

        Args:
            store: Acquire store.
            orchestrator: Single-item grab chain.
            event_bus: In-process event bus for emitting WantedAbandoned events.
            config: Full application config (used to read cadence policy).
        """
        self._store = store
        self._orchestrator = orchestrator
        self._event_bus = event_bus
        self._config = config
```

Add `Config` to imports using a `TYPE_CHECKING` guard (matching the `_factory.py` pattern):

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
```

- [ ] **Step 6: Modify `_process_item` to accept `cadence` and insert the two checks**

Change signature from:

```python
    def _process_item(self, item: WantedItem, now: int) -> _ItemOutcome:
```

to:

```python
    def _process_item(self, item: WantedItem, now: int, *, cadence: Cadence) -> _ItemOutcome:
```

After the stale re-promote block (currently around line 260-261) and BEFORE `won = self._store.wanted.claim_for_search(...)`, insert:

```python
        # --- CUTOFF CHECK (DESIGN §7) ---
        # Emit-after-persist: set_status first, then emit, symmetrical to
        # the attempts-cap abandon at service.py:357.
        if is_past_cutoff(cadence, now=now, enqueued_at=item.enqueued_at):
            self._store.wanted.set_status(wanted_id, "abandoned")
            self._event_bus.emit(WantedAbandoned(media_ref=item.media_ref, reason="cutoff_reached"))
            log.info("acquire.service.cutoff_abandoned", wanted_id=wanted_id)
            return "abandoned"

        # --- CADENCE CHECK (DESIGN §7) ---
        # A not-yet-due item stays 'pending' and is re-listed next run.
        # No claim, no attempts increment.
        if not is_due_by_cadence(cadence, now=now, enqueued_at=item.enqueued_at, last_search_at=item.last_search_at):
            log.debug("acquire.service.cadence_not_due", wanted_id=wanted_id)
            return "skipped"
```

- [ ] **Step 7: Update `_process_item` docstring to document the new `cadence` param**

Add to `Args:` section:

```
            cadence: Effective cadence policy for this item (resolved in :meth:`run`).
```

- [ ] **Step 8: Find and update any construction sites of `AcquisitionService` to pass `config`**

```bash
rg --type py "AcquisitionService\(" personalscraper/
```

Single prod site: `personalscraper/acquire/_factory.py:138`, inside
`build_acquire_context(config, ...)` — pass `config=config` (the factory already
holds the typed `Config` in scope). No other prod call sites exist.

**PLAN-DRIFT — test call sites + clock-pin regression fix (added during 4.1):**
The 5 `AcquisitionService(...)` sites in `tests/acquire/test_service.py` (one in
the `_service` helper + 4 direct) must also pass `config=`. A shared `_config()`
helper returns `MagicMock()` whose `.acquire` is a real `AcquireConfig()` so
`cadence_from_config(config.acquire.cadence)` reads the canonical default cadence.

Critically, every existing `_pending_item` uses `enqueued_at=1_700_000_000`; with
a real ~2026 `now` the new 30d cutoff gate would ABANDON all of them, breaking the
grab/retry/stale tests. Fix: an `autouse` fixture in `test_service.py` patches
`personalscraper.acquire.service.time.time` to `_PINNED_NOW = 1_700_003_600`
(enqueued_at + 1h → Hot tier, well within cutoff), so fresh rows
(`last_search_at=None`) are due immediately. Two clock-sensitive tests are
adjusted: `test_attempts_cap_abandons_item` stamps its claim/reset cycles at
`_PINNED_NOW - 7200` (one Hot interval back, so the row is due on the service run);
`test_section_11d_crash_window...`'s run-2 clock becomes `_PINNED_NOW + 7200 + 10`
(stale AND due again, still < cutoff) instead of `time.time() + _STALE_THRESHOLD_S + 10`.
The now-unused `_STALE_THRESHOLD_S` import in the test module is dropped (ruff `--fix`).

- [ ] **Step 9: Run cadence-aware loop tests — all must PASS**

```bash
pytest tests/acquire/test_service_cadence.py -v
```

Expected: `4 passed`, `0 failed`.

- [ ] **Step 10: Commit**

```bash
git add personalscraper/acquire/service.py tests/acquire/test_service_cadence.py
git commit -m "feat(follow-detect): cadence-aware _process_item — cutoff abandon + cadence gating"
```

---

## Phase 4 Gate

- [ ] **Run `make check`** — must exit 0 (covers lint + all tests + module-size).
- [ ] **Smoke test:** `python -c "import personalscraper"` — must exit 0.
- [ ] **Residual grep:** `rg "_STALE_THRESHOLD_S" --type py personalscraper/acquire/service.py` — must still find the constant (it is kept as a stale-recovery window, NOT removed).

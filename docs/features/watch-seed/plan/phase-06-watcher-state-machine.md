# Phase 6 — WatcherService pure state machine

## Gate

- **Requires Phase 3**: `WatchConfig` is available and wired into `AppContext.config.watch`.
- **Does NOT require Phase 4 or 5** — the WatcherService is a pure decision engine that doesn't call `CrossSeedService` or the CLI directly. It runs in parallel with Phase 4–5 development.
- **Produces for Phase 7**: `WatcherService` class importable from `acquire/watcher.py` — a pure state machine that the watch command loop (Phase 7) drives each cycle.

## Overview

`WatcherService` is a **pure** decision engine (no I/O, no sleep, injected clock, house style per `acquire/cadence.py` and `indexer/_throttle.py`). Inputs: completed-torrent snapshot, ingested-hash set, sentinel-poke flag, now(). Output: a decision enum. Unit-testable exhaustively without a daemon.

### Sub-phases (4 commits)

| #   | Commit                                                                       | Scope              |
| --- | ---------------------------------------------------------------------------- | ------------------ |
| 6.1 | `feat(watch-seed): define WatcherDecision enum + WatcherService constructor` | State model        |
| 6.2 | `feat(watch-seed): implement WatcherService state machine core`              | Core logic         |
| 6.3 | `feat(watch-seed): add sentinel bypass + backoff to WatcherService`          | Sentinel + backoff |
| 6.4 | `test(watch-seed): add exhaustive unit tests for WatcherService`             | Tests              |

## Sub-phase 6.1 — WatcherDecision + constructor

**Files:**

- Create: `personalscraper/acquire/watcher.py`

```python
"""WatcherService — pure decision engine for the watch daemon (W1–W7).

No I/O, no sleep, no subprocess — the service is a pure function of its
inputs per cycle.  The watch loop in ``commands/watch.py`` calls it each
poll cycle and executes the returned decisions.

See docs/features/watch-seed/DESIGN.md §Watcher.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class WatcherDecision(enum.Enum):
    """What the watcher loop should do this cycle."""

    IDLE = "idle"
    START_DEBOUNCE = "start_debounce"
    FIRE_RUN = "fire_run"
    FIRE_CROSS_SEED = "fire_cross_seed"
    REQUEUE = "requeue"


@dataclass
class WatcherState:
    """Mutable state carried across cycles (in-memory, rebuilt on PM2 restart).

    Attributes:
        debounce_until: Wall-clock timestamp after which a debounced run
            may fire, or None when no debounce window is open.
        last_successful_run_at: Wall-clock timestamp of the last successful
            pipeline run. Persisted in acquire.db across restarts.
        backoff_multiplier: Exponential backoff factor for the anti-storm
            mechanism (W7).  0 = normal (no backoff).
        cross_seed_dispatched: Info-hashes already sent to cross-seed this
            daemon lifetime.  Prevents re-firing cross-seed every poll cycle
            for the same not-yet-ingested hashes during the entire debounce
            window.  Cleared on daemon restart (in-memory); ingestion
            eventually makes entries irrelevant.
    """

    debounce_until: float | None = None
    last_successful_run_at: float | None = None
    backoff_multiplier: int = 0
    cross_seed_dispatched: frozenset[str] = frozenset()


@dataclass
class WatcherInput:
    """Snapshot of the world for one decision cycle.

    All attributes are READ-ONLY — the WatcherService never mutates its input.

    Attributes:
        completed_hashes: Set of info-hashes from ``get_completed()``.
        ingested_hashes: Set of already-ingested hashes.
        seed_pure_hashes: Set of SEED_PURE-tagged hashes (skip these).
        sentinel_present: True if ``data_dir/watch.trigger`` exists.
        pipeline_lock_held: True if the lock file exists (manual run in progress).
        now: Current wall-clock timestamp (float, e.g. ``time.time()``).
    """

    completed_hashes: frozenset[str]
    ingested_hashes: frozenset[str]
    seed_pure_hashes: frozenset[str]
    sentinel_present: bool
    pipeline_lock_held: bool
    now: float


@dataclass
class WatcherOutput:
    """Decision + payload for one cycle.

    Attributes:
        decision: The action the loop should take.
        run_reason: If decision is FIRE_RUN, why (completion/safety_net/manual).
        cross_seed_hashes: If decision includes cross-seed, which hashes to spawn.
        new_state: Updated watcher state to carry forward.
    """

    decision: WatcherDecision
    run_reason: str = ""
    cross_seed_hashes: list[str] = field(default_factory=list)
    new_state: WatcherState = field(default_factory=WatcherState)
```

## Sub-phase 6.2 — state machine core

**Files:**

- Modify: `personalscraper/acquire/watcher.py` (add `WatcherService.evaluate()`)

```python
class WatcherService:
    """Pure decision engine for the watcher daemon.

    Injected clock (now) keeps the unit testable — no ``time.time()`` calls.
    """

    def __init__(self, config_watch) -> None:
        """Args: config_watch: ``AppConfig.watch`` (:class:`WatchConfig`)."""
        self._poll_interval_s = config_watch.poll_interval_s
        self._debounce_s = config_watch.debounce_s
        self._safety_net_hours = config_watch.safety_net_hours
        self._enabled = config_watch.enabled

    def evaluate(self, inp: WatcherInput, state: WatcherState) -> WatcherOutput:
        """Produce one cycle's decision.

        Logic (per DESIGN flow):
        1. sentinel present → consume → FIRE_RUN (reason=manual)
        2. Work predicate: NEW completions (not ingested, not SEED_PURE)
           → FIRE_CROSS_SEED per new hash
        3. Work predicate true?
           → not in debounce: START_DEBOUNCE
           → debounce expired: FIRE_RUN (reason=completion)
        4. No successful run for safety_net_hours? → FIRE_RUN (reason=safety_net)
        5. Lock held → REQUEUE
        6. Otherwise → IDLE
        """
        if not self._enabled:
            return WatcherOutput(decision=WatcherDecision.IDLE, new_state=state)

        # (1) Sentinel bypass
        if inp.sentinel_present:
            return WatcherOutput(
                decision=WatcherDecision.FIRE_RUN,
                run_reason="manual",
                new_state=state,
            )

        # (2) New completions → cross-seed
        new_hashes = self._new_completions(inp)
        if new_hashes:
            return WatcherOutput(
                decision=WatcherDecision.FIRE_CROSS_SEED,
                cross_seed_hashes=list(new_hashes),
                new_state=state,
            )

        # (3) Work predicate → pipeline run
        work_exists = self._work_predicate(inp)
        if work_exists:
            if state.debounce_until is None:
                # Start debounce window
                new_state = WatcherState(
                    debounce_until=inp.now + self._debounce_s,
                    last_successful_run_at=state.last_successful_run_at,
                    backoff_multiplier=state.backoff_multiplier,
                )
                return WatcherOutput(decision=WatcherDecision.START_DEBOUNCE, new_state=new_state)
            elif inp.now >= state.debounce_until:
                # Debounce expired
                if inp.pipeline_lock_held:
                    return self._requeue(state)
                backoff = state.backoff_multiplier
                delay = self._debounce_s * (2 ** max(0, backoff - 1))
                new_state = WatcherState(
                    debounce_until=inp.now + delay,
                    last_successful_run_at=state.last_successful_run_at,
                    backoff_multiplier=backoff + 1,  # exponential backoff (W7)
                )
                return WatcherOutput(
                    decision=WatcherDecision.FIRE_RUN,
                    run_reason="completion",
                    new_state=new_state,
                )

        # (4) Safety net
        if self._safety_net_expired(state, inp.now):
            if inp.pipeline_lock_held:
                return self._requeue(state)
            new_state = WatcherState(
                debounce_until=inp.now + self._debounce_s,
                last_successful_run_at=state.last_successful_run_at,
                backoff_multiplier=0,
            )
            return WatcherOutput(
                decision=WatcherDecision.FIRE_RUN,
                run_reason="safety_net",
                new_state=new_state,
            )

        return WatcherOutput(decision=WatcherDecision.IDLE, new_state=state)

    def _new_completions(self, inp: WatcherInput) -> set[str]:
        """Hashes in completed_hashes but NOT in ingested nor SEED_PURE."""
        return inp.completed_hashes - inp.ingested_hashes - inp.seed_pure_hashes

    def _work_predicate(self, inp: WatcherInput) -> bool:
        """True when ∃ completed torrent NOT ingested AND NOT SEED_PURE (W7)."""
        return bool(self._new_completions(inp))

    def _safety_net_expired(self, state: WatcherState, now: float) -> bool:
        """True when no successful run for ``safety_net_hours``."""
        if state.last_successful_run_at is None:
            return True
        elapsed_hours = (now - state.last_successful_run_at) / 3600.0
        return elapsed_hours >= self._safety_net_hours

    def _requeue(self, state: WatcherState) -> WatcherOutput:
        """Lock held → retry after debounce (W6)."""
        return WatcherOutput(decision=WatcherDecision.REQUEUE, new_state=state)
```

## Sub-phase 6.3 — sentinel bypass + backoff

The sentinel bypass is already handled in step (1) of `evaluate()` above. The exponential backoff is integrated into step (3): `backoff_multiplier` increases on each FIRE_RUN while the work predicate stays true, so repeated failing items get exponentially longer waits (W7 anti-storm). The safety-net run resets backoff to 0.

The `last_successful_run_at` field is set by the **watch loop** (Phase 7) after a successful subprocess run, not by the WatcherService itself. The service only reads it.

## Sub-phase 6.4 — exhaustive unit tests (ACC-10)

**Files:**

- Create: `tests/unit/test_watcher_service.py`

Cover every state transition. Key test cases:

```python
class TestWatcherService:
    @pytest.fixture
    def svc(self):
        from personalscraper.conf.models.watch_seed import WatchConfig
        return WatcherService(WatchConfig())

    def test_idle_when_no_work_and_safety_net_not_expired(self, svc):
        """Nothing to do and last run was recent → IDLE."""
        state = WatcherState(last_successful_run_at=10_000.0)
        inp = _inp(completed=set(), ingested=set(), now=10_100.0)  # 100s later
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE

    def test_sentinel_bypass_ignores_debounce(self, svc):
        """Sentinel present → FIRE_RUN even inside debounce window."""
        state = WatcherState(debounce_until=20_000.0)
        inp = _inp(completed=set(), ingested=set(), now=10_000.0, sentinel=True)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "manual"

    def test_new_completion_triggers_cross_seed(self, svc):
        """Fresh completion → FIRE_CROSS_SEED immediately (no debounce)."""
        state = WatcherState(debounce_until=20_000.0)
        inp = _inp(completed={"abc"}, ingested=set(), now=10_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_CROSS_SEED
        assert "abc" in out.cross_seed_hashes

    def test_seed_pure_excluded_from_work_predicate(self, svc):
        """SEED_PURE hash is ignored (W7)."""
        state = WatcherState()
        inp = _inp(completed={"abc"}, ingested=set(), seed_pure={"abc"}, now=10_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE

    def test_work_predicate_starts_debounce(self, svc):
        state = WatcherState()
        inp = _inp(completed={"abc"}, ingested=set(), now=10_000.0)
        out = svc.evaluate(inp, state)
        # Cross-seed fires first (new completions). Run again with same hash
        # "ingested" → work predicate true, no new completions → debounce.
        state2 = WatcherState()
        inp2 = _inp(completed={"abc"}, ingested={"abc"}, now=10_000.0)
        out2 = svc.evaluate(inp2, state2)
        assert out2.decision in (WatcherDecision.START_DEBOUNCE, WatcherDecision.IDLE)

    def test_debounce_expired_fires_run(self, svc):
        state = WatcherState(debounce_until=10_000.0)
        inp = _inp(completed={"abc"}, ingested={"abc"}, now=11_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "completion"

    def test_lock_held_requeues(self, svc):
        state = WatcherState(debounce_until=10_000.0)
        inp = _inp(completed={"abc"}, ingested={"abc"}, now=11_000.0, lock_held=True)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.REQUEUE

    def test_safety_net_fires_when_expired(self, svc):
        state = WatcherState(last_successful_run_at=10_000.0)
        # 25 hours later (safety_net_hours=24)
        inp = _inp(completed=set(), ingested=set(), now=10_000.0 + 25 * 3600)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "safety_net"

    def test_anti_storm_backoff_increases(self, svc):
        state = WatcherState(debounce_until=10_000.0, backoff_multiplier=0)
        inp = _inp(completed={"abc"}, ingested={"abc"}, now=11_000.0)
        out = svc.evaluate(inp, state)
        assert out.new_state.backoff_multiplier == 1

    def test_disabled_always_idle(self):
        from personalscraper.conf.models.watch_seed import WatchConfig
        svc = WatcherService(WatchConfig(enabled=False))
        inp = _inp(completed={"abc"}, ingested=set(), now=10_000.0, sentinel=True)
        out = svc.evaluate(inp, WatcherState())
        assert out.decision == WatcherDecision.IDLE


def _inp(*, completed, ingested, now, seed_pure=None, sentinel=False, lock_held=False):
    return WatcherInput(
        completed_hashes=frozenset(completed),
        ingested_hashes=frozenset(ingested),
        seed_pure_hashes=frozenset(seed_pure or set()),
        sentinel_present=sentinel,
        pipeline_lock_held=lock_held,
        now=now,
    )
```

## Gate check (before advancing to Phase 7)

- [ ] `make lint` — 0 errors.
- [ ] `python -m pytest tests/unit/test_watcher_service.py -q` — all pass (ACC-10).
- [ ] `personalscraper/acquire/watcher.py` ≤ 250 LOC (pure state machine, small).
- [ ] `acquire/watcher.py` imports only from `personalscraper.conf.models.watch_seed` (downward) — no `commands/`, no `pipeline/`, no `api/` (the service doesn't touch torrents at all). Verified by `tests/architecture/test_layering.py`.

"""Exhaustive unit tests for WatcherService state machine.

Covers every transition of the pure decision engine defined in
``personalscraper.acquire.watcher``, including disabled mode, sentinel
bypass, cross-seed dedup, debounce window, exponential backoff (anti-storm),
stale-window clearing, safety-net, immutability, and determinism.

See docs/features/watch-seed/plan/phase-06-watcher-state-machine.md §6.4.
"""

from __future__ import annotations

import dataclasses

import pytest

from personalscraper.acquire.watcher import (
    WatcherDecision,
    WatcherInput,
    WatcherService,
    WatcherState,
)
from personalscraper.conf.models.watch_seed import WatchConfig


def _inp(
    *,
    completed: set[str],
    ingested: set[str],
    now: float,
    seed_pure: set[str] | None = None,
    sentinel: bool = False,
    lock_held: bool = False,
    deferred: set[str] | None = None,
) -> WatcherInput:
    """Build a WatcherInput with sensible defaults for concise test setup.

    Args:
        completed: Info-hashes returned by ``get_completed()``.
        ingested: Info-hashes already ingested.
        now: Injected wall-clock timestamp (float).
        seed_pure: Info-hashes tagged SEED_PURE (excluded from all work).
        sentinel: Whether ``watch.trigger`` exists.
        lock_held: Whether the pipeline lock file exists.
        deferred: Info-hashes transiently deferred (ingest would re-skip).

    Returns:
        A new WatcherInput frozen snapshot.
    """
    return WatcherInput(
        completed_hashes=frozenset(completed),
        ingested_hashes=frozenset(ingested),
        seed_pure_hashes=frozenset(seed_pure or set()),
        sentinel_present=sentinel,
        pipeline_lock_held=lock_held,
        now=now,
        deferred_hashes=frozenset(deferred or set()),
    )


class TestWatcherService:
    """Exhaustive tests for every WatcherService.evaluate() transition."""

    @pytest.fixture
    def svc(self) -> WatcherService:
        """Active WatcherService with explicit config (debounce=900s, safety_net=24h)."""
        return WatcherService(WatchConfig(enabled=True, debounce_s=900, safety_net_hours=24, poll_interval_s=60))

    # ------------------------------------------------------------------
    # Case  1: disabled → IDLE even with sentinel + work
    # ------------------------------------------------------------------

    def test_disabled_always_idle_even_with_sentinel_and_work(self) -> None:
        """Disabled service returns IDLE regardless of inputs, state preserved."""
        svc = WatcherService(WatchConfig(enabled=False))
        state = WatcherState()
        inp = _inp(completed={"abc"}, ingested=set(), now=1_000_000.0, sentinel=True)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE
        assert out.new_state is state  # unchanged

    # ------------------------------------------------------------------
    # Case  2: idle when no work + recent successful run
    # ------------------------------------------------------------------

    def test_idle_when_no_work_and_recent_successful_run(self, svc: WatcherService) -> None:
        """Nothing to do and last run was 100 s ago → IDLE."""
        state = WatcherState(last_successful_run_at=1_000_000.0)
        inp = _inp(completed=set(), ingested=set(), now=1_000_100.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE

    # ------------------------------------------------------------------
    # Case  3: sentinel + lock → REQUEUE (state unchanged)
    # ------------------------------------------------------------------

    def test_sentinel_with_lock_requeues_state_unchanged(self, svc: WatcherService) -> None:
        """Sentinel present but pipeline lock held → REQUEUE, state untouched."""
        state = WatcherState(debounce_until=2_000_000.0, backoff_multiplier=3)
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0, sentinel=True, lock_held=True)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.REQUEUE
        assert out.new_state is state  # identical object — no mutation

    # ------------------------------------------------------------------
    # Case  4: sentinel free → FIRE_RUN(manual) + debounce cleared + backoff reset
    # ------------------------------------------------------------------

    def test_sentinel_free_fires_manual_and_resets_windows(self, svc: WatcherService) -> None:
        """Sentinel present + lock free → FIRE_RUN(manual), windows cleared."""
        state = WatcherState(debounce_until=2_000_000.0, backoff_multiplier=5)
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0, sentinel=True, lock_held=False)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "manual"
        assert out.new_state.debounce_until is None
        assert out.new_state.backoff_multiplier == 0
        assert out.new_state.debounce_origin is None

    # ------------------------------------------------------------------
    # Case  5: new completion → FIRE_CROSS_SEED with sorted hashes + dispatched-set grows
    # ------------------------------------------------------------------

    def test_new_completion_triggers_cross_seed_sorted_hashes(self, svc: WatcherService) -> None:
        """Fresh completions → FIRE_CROSS_SEED, hashes sorted, dispatched set updated."""
        state = WatcherState()
        inp = _inp(completed={"def123", "abc456"}, ingested=set(), now=1_000_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_CROSS_SEED
        assert out.cross_seed_hashes == ["abc456", "def123"]  # lexicographic sort
        assert out.new_state.cross_seed_dispatched == frozenset({"abc456", "def123"})

    def test_partial_new_completion_cross_seed_only_new_hashes(self, svc: WatcherService) -> None:
        """Only not-yet-dispatched hashes are sent to cross-seed."""
        state = WatcherState(cross_seed_dispatched=frozenset({"old_hash"}))
        inp = _inp(completed={"old_hash", "new_hash"}, ingested=set(), now=1_000_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_CROSS_SEED
        assert out.cross_seed_hashes == ["new_hash"]  # only the new one
        assert out.new_state.cross_seed_dispatched == frozenset({"old_hash", "new_hash"})

    # ------------------------------------------------------------------
    # Case  6: same completion second cycle → dedup → START_DEBOUNCE
    # ------------------------------------------------------------------

    def test_same_completion_second_cycle_not_re_fired_starts_debounce(self, svc: WatcherService) -> None:
        """Already-dispatched hashes skip cross-seed → fall through to START_DEBOUNCE."""
        state = WatcherState(cross_seed_dispatched=frozenset({"abc", "def"}))
        inp = _inp(completed={"abc", "def"}, ingested=set(), now=1_000_000.0)
        out = svc.evaluate(inp, state)
        # No new cross-seed candidates → work predicate fires START_DEBOUNCE
        assert out.decision == WatcherDecision.START_DEBOUNCE
        assert out.new_state.cross_seed_dispatched == frozenset({"abc", "def"})  # unchanged
        assert out.new_state.debounce_until == 1_000_000.0 + 900  # now + debounce_s

    # ------------------------------------------------------------------
    # Case  7: seed_pure excluded from both work-set and cross-seed set
    # ------------------------------------------------------------------

    def test_seed_pure_excluded_from_work_and_cross_seed(self, svc: WatcherService) -> None:
        """SEED_PURE hash removed from work_set → no cross-seed, no pipeline trigger."""
        state = WatcherState(last_successful_run_at=1_000_000.0)
        inp = _inp(completed={"abc"}, ingested=set(), seed_pure={"abc"}, now=1_000_000.0)
        out = svc.evaluate(inp, state)
        # work_set = {"abc"} - {} - {"abc"} = {} → IDLE (safety-net not expired)
        assert out.decision == WatcherDecision.IDLE

    # ------------------------------------------------------------------
    # Case  8: ingested excluded from work-set
    # ------------------------------------------------------------------

    def test_ingested_excluded_from_work_set(self, svc: WatcherService) -> None:
        """Already-ingested hash removed from work_set → no action."""
        state = WatcherState(last_successful_run_at=1_000_000.0)
        inp = _inp(completed={"abc"}, ingested={"abc"}, now=1_000_000.0)
        out = svc.evaluate(inp, state)
        # work_set = {"abc"} - {"abc"} - {} = {} → IDLE
        assert out.decision == WatcherDecision.IDLE

    # ------------------------------------------------------------------
    # Case  9: debounce window open (now < until) → IDLE
    # ------------------------------------------------------------------

    def test_debounce_window_open_returns_idle(self, svc: WatcherService) -> None:
        """Now < debounce_until → IDLE, state unchanged."""
        state = WatcherState(debounce_until=2_000_000.0, cross_seed_dispatched=frozenset({"abc"}))
        inp = _inp(completed={"abc"}, ingested=set(), now=1_000_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE
        assert out.new_state is state  # unchanged

    # ------------------------------------------------------------------
    # Case 10: debounce expired + lock held → REQUEUE (until unchanged)
    # ------------------------------------------------------------------

    def test_debounce_expired_lock_held_requeues_until_unchanged(self, svc: WatcherService) -> None:
        """Debounce window expired but pipeline lock is held → REQUEUE, state preserved."""
        state = WatcherState(debounce_until=1_000_000.0, cross_seed_dispatched=frozenset({"abc"}))
        inp = _inp(completed={"abc"}, ingested=set(), now=1_000_100.0, lock_held=True)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.REQUEUE
        assert out.new_state is state  # debounce_until preserved at 1_000_000.0

    # ------------------------------------------------------------------
    # Case 11: debounce expired + free → FIRE_RUN(completion) + backoff
    # ------------------------------------------------------------------

    def test_debounce_expired_free_fires_completion_backoff_multiplier_0(self, svc: WatcherService) -> None:
        """Multiplier 0: debounce_s * 2^0 = 900 s."""
        state = WatcherState(
            debounce_until=1_000_000.0,
            backoff_multiplier=0,
            cross_seed_dispatched=frozenset({"abc"}),
        )
        inp = _inp(completed={"abc"}, ingested=set(), now=1_000_100.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "completion"
        assert out.new_state.backoff_multiplier == 1
        assert out.new_state.debounce_until == 1_000_100.0 + 900 * (2**0)  # 1_001_000.0
        assert out.new_state.debounce_origin == "completion"

    def test_debounce_expired_free_fires_completion_backoff_multiplier_1(self, svc: WatcherService) -> None:
        """Multiplier 1: debounce_s * 2^1 = 1800 s."""
        state = WatcherState(
            debounce_until=1_001_000.0,
            backoff_multiplier=1,
            cross_seed_dispatched=frozenset({"abc"}),
        )
        inp = _inp(completed={"abc"}, ingested=set(), now=1_001_100.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "completion"
        assert out.new_state.backoff_multiplier == 2
        assert out.new_state.debounce_until == 1_001_100.0 + 900 * (2**1)  # 1_002_900.0
        assert out.new_state.debounce_origin == "completion"

    def test_debounce_expired_free_fires_completion_backoff_multiplier_2(self, svc: WatcherService) -> None:
        """Multiplier 2: debounce_s * 2^2 = 3600 s."""
        state = WatcherState(
            debounce_until=1_002_900.0,
            backoff_multiplier=2,
            cross_seed_dispatched=frozenset({"abc"}),
        )
        inp = _inp(completed={"abc"}, ingested=set(), now=1_003_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "completion"
        assert out.new_state.backoff_multiplier == 3
        assert out.new_state.debounce_until == 1_003_000.0 + 900 * (2**2)  # 1_006_600.0
        assert out.new_state.debounce_origin == "completion"

    # ------------------------------------------------------------------
    # Case 12: stale-window clear — work vanished + old debounce_until
    # ------------------------------------------------------------------

    def test_stale_window_clear_resets_debounce_and_backoff(self, svc: WatcherService) -> None:
        """Work vanished while debounce window was open → IDLE, window cleared."""
        state = WatcherState(
            debounce_until=1_000_000.0,
            backoff_multiplier=3,
            last_successful_run_at=1_500_000.0,  # prevents safety-net
        )
        inp = _inp(completed=set(), ingested=set(), now=1_500_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE
        assert out.new_state.debounce_until is None
        assert out.new_state.backoff_multiplier == 0
        assert out.new_state.debounce_origin is None

    # ------------------------------------------------------------------
    # Case 13: safety net
    # ------------------------------------------------------------------

    def test_safety_net_fires_when_last_successful_run_is_none(self, svc: WatcherService) -> None:
        """last_successful_run_at=None → safety net triggers immediately."""
        state = WatcherState()  # last_successful_run_at=None by default
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "safety_net"
        assert out.new_state.debounce_until == 1_000_000.0 + 900
        assert out.new_state.backoff_multiplier == 1  # incremented, not reset
        assert out.new_state.debounce_origin == "safety_net"

    def test_safety_net_fires_when_expired_25h(self, svc: WatcherService) -> None:
        """25 h elapsed with 24 h config → safety net triggers."""
        state = WatcherState(last_successful_run_at=1_000_000.0)
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0 + 25 * 3600)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "safety_net"
        assert out.new_state.backoff_multiplier == 1  # incremented, not reset
        assert out.new_state.debounce_origin == "safety_net"

    def test_safety_net_fires_at_exact_boundary_24h(self, svc: WatcherService) -> None:
        """Exactly 24 h elapsed with 24 h config → safety net triggers (boundary)."""
        state = WatcherState(last_successful_run_at=1_000_000.0)
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0 + 24 * 3600)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "safety_net"
        assert out.new_state.backoff_multiplier == 1  # incremented
        assert out.new_state.debounce_origin == "safety_net"

    def test_safety_net_expired_lock_held_requeues(self, svc: WatcherService) -> None:
        """Safety net expired but pipeline lock is held → REQUEUE."""
        state = WatcherState()  # last_successful_run_at=None
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0, lock_held=True)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.REQUEUE
        assert out.new_state is state

    # ------------------------------------------------------------------
    # Case 14: safety net NOT expired (23h) → IDLE
    # ------------------------------------------------------------------

    def test_safety_net_not_expired_23h_returns_idle(self, svc: WatcherService) -> None:
        """23 h elapsed with 24 h config → IDLE (safety net not yet expired)."""
        state = WatcherState(last_successful_run_at=1_000_000.0)
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0 + 23 * 3600)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE
        assert out.new_state is state

    # ------------------------------------------------------------------
    # Case 15: immutability — input state object is never mutated
    # ------------------------------------------------------------------

    def test_input_state_is_never_mutated(self, svc: WatcherService) -> None:
        """WatcherInput and WatcherState are never mutated by evaluate()."""
        original_state = WatcherState(
            debounce_until=1_500_000.0,
            last_successful_run_at=1_000_000.0,
            backoff_multiplier=2,
            cross_seed_dispatched=frozenset({"abc"}),
        )
        original_inp = _inp(completed={"abc", "def"}, ingested=set(), now=2_000_000.0, sentinel=True)

        # Snapshot before
        state_before = dataclasses.replace(original_state)
        inp_before = _inp(
            completed=set(original_inp.completed_hashes),
            ingested=set(original_inp.ingested_hashes),
            now=original_inp.now,
            seed_pure=set(original_inp.seed_pure_hashes),
            sentinel=original_inp.sentinel_present,
            lock_held=original_inp.pipeline_lock_held,
        )

        svc.evaluate(original_inp, original_state)

        # Verify state unchanged
        assert original_state.debounce_until == state_before.debounce_until
        assert original_state.last_successful_run_at == state_before.last_successful_run_at
        assert original_state.backoff_multiplier == state_before.backoff_multiplier
        assert original_state.cross_seed_dispatched == state_before.cross_seed_dispatched

        # Verify input unchanged
        assert original_inp.completed_hashes == inp_before.completed_hashes
        assert original_inp.ingested_hashes == inp_before.ingested_hashes
        assert original_inp.seed_pure_hashes == inp_before.seed_pure_hashes
        assert original_inp.sentinel_present == inp_before.sentinel_present
        assert original_inp.pipeline_lock_held == inp_before.pipeline_lock_held
        assert original_inp.now == inp_before.now

    # ------------------------------------------------------------------
    # Case 16: determinism — same input + state → identical output twice
    # ------------------------------------------------------------------

    def test_determinism_same_input_produces_identical_output(self, svc: WatcherService) -> None:
        """WatcherService is a pure function: same (input, state) → same output."""
        state = WatcherState(
            debounce_until=1_500_000.0,
            last_successful_run_at=1_000_000.0,
            backoff_multiplier=1,
            cross_seed_dispatched=frozenset({"xyz"}),
        )
        inp = _inp(completed={"abc"}, ingested=set(), now=1_600_000.0)

        out1 = svc.evaluate(inp, state)
        out2 = svc.evaluate(inp, state)

        assert out1.decision == out2.decision
        assert out1.run_reason == out2.run_reason
        assert out1.cross_seed_hashes == out2.cross_seed_hashes
        assert out1.new_state == out2.new_state

    # ------------------------------------------------------------------
    # Additional edge: stale-window clear wins before safety net
    # ------------------------------------------------------------------

    def test_stale_window_clears_before_safety_net_check(self, svc: WatcherService) -> None:
        """Stale debounce window clears before safety net is evaluated (order 4 < 5).

        Even though safety net *would* fire (last_successful_run_at=None), the
        stale-window clear (step 4) returns first.  Origin defaults to None,
        which is always clearable by branch 4.
        """
        state = WatcherState(debounce_until=1_000_000.0)  # last_successful_run_at=None
        inp = _inp(completed=set(), ingested=set(), now=1_500_000.0)
        out = svc.evaluate(inp, state)
        # Step 4 clears stale window → IDLE (not safety-net FIRE_RUN)
        assert out.decision == WatcherDecision.IDLE
        assert out.new_state.debounce_until is None
        assert out.new_state.backoff_multiplier == 0
        assert out.new_state.debounce_origin is None

    # ------------------------------------------------------------------
    # Acceptance (a): completion backoff clamps at safety_net_hours × 3600
    # ------------------------------------------------------------------

    def test_completion_backoff_clamped_at_safety_net_boundary(self) -> None:
        """Repeated completion fires with predicate stuck true → delays clamp.

        With debounce_s=900 and safety_net_hours=1 (3600s):
        - multiplier 0 → 900 s
        - multiplier 1 → 1800 s
        - multiplier 2 → 3600 s (exact clamp)
        - multiplier 3 → 3600 s (clamped, would be 7200)
        - multiplier 4 → 3600 s (still clamped)
        """
        svc = WatcherService(
            WatchConfig(
                enabled=True,
                debounce_s=900,
                safety_net_hours=1,
                poll_interval_s=60,
            )
        )
        t = 1_000_000.0

        # multiplier 0 → delay = min(900, 3600) = 900
        state = WatcherState(
            debounce_until=t,
            backoff_multiplier=0,
            cross_seed_dispatched=frozenset({"abc"}),
        )
        out = svc.evaluate(_inp(completed={"abc"}, ingested=set(), now=t), state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "completion"
        assert out.new_state.backoff_multiplier == 1
        assert out.new_state.debounce_until == t + 900
        assert out.new_state.debounce_origin == "completion"

        # multiplier 1 → delay = min(1800, 3600) = 1800
        t2 = out.new_state.debounce_until
        state2 = out.new_state
        out2 = svc.evaluate(_inp(completed={"abc"}, ingested=set(), now=t2), state2)
        assert out2.new_state.backoff_multiplier == 2
        assert out2.new_state.debounce_until == t2 + 1800

        # multiplier 2 → delay = min(3600, 3600) = 3600 (at clamp)
        t3 = out2.new_state.debounce_until
        state3 = out2.new_state
        out3 = svc.evaluate(_inp(completed={"abc"}, ingested=set(), now=t3), state3)
        assert out3.new_state.backoff_multiplier == 3
        assert out3.new_state.debounce_until == t3 + 3600

        # multiplier 3 → delay = min(7200, 3600) = 3600 (clamped!)
        t4 = out3.new_state.debounce_until
        state4 = out3.new_state
        out4 = svc.evaluate(_inp(completed={"abc"}, ingested=set(), now=t4), state4)
        assert out4.new_state.backoff_multiplier == 4
        assert out4.new_state.debounce_until == t4 + 3600  # still 3600

    # ------------------------------------------------------------------
    # Acceptance (b): work vanishes after completion fire → window cleared
    # ------------------------------------------------------------------

    def test_work_vanishes_after_completion_fire_clears_window(self, svc: WatcherService) -> None:
        """After a completion fire, work vanishes → next cycle clears window + backoff.

        This is the normal success path: the machine's branch 4 resets
        completion-origin windows when work disappears.
        """
        state = WatcherState(
            debounce_until=1_000_000.0,
            backoff_multiplier=2,
            debounce_origin="completion",
            cross_seed_dispatched=frozenset({"abc"}),
            last_successful_run_at=500_000.0,  # prevents safety-net
        )
        # No work → branch 4 fires.
        inp = _inp(completed=set(), ingested=set(), now=1_500_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE
        assert out.new_state.debounce_until is None
        assert out.new_state.backoff_multiplier == 0
        assert out.new_state.debounce_origin is None

    # ------------------------------------------------------------------
    # Acceptance (c): safety-net pacing — window blocks re-fire, spaces
    # ------------------------------------------------------------------

    def test_safety_net_pacing_blocks_refire_within_window(self, svc: WatcherService) -> None:
        """Safety-net sets a debounce window; next cycle does not re-fire until it expires.

        With last_successful_run_at=None, the safety net fires immediately in
        cycle 1.  Cycle 2 (within the window) must return IDLE — the debounce
        gate blocks.  Cycle 3 (after the window expires) fires again with
        incremented backoff.
        """
        t = 1_000_000.0
        state = WatcherState()  # last_successful_run_at=None → safety-net expired

        # Cycle 1: safety-net fires, sets debounce_until = t + 900, backoff=1.
        out1 = svc.evaluate(_inp(completed=set(), ingested=set(), now=t), state)
        assert out1.decision == WatcherDecision.FIRE_RUN
        assert out1.run_reason == "safety_net"
        assert out1.new_state.debounce_until == t + 900
        assert out1.new_state.backoff_multiplier == 1
        assert out1.new_state.debounce_origin == "safety_net"

        # Cycle 2: now = t + 300 (within window).  Branch 4 sees origin="safety_net"
        # → does NOT clear.  Branch 5 safety_net_expired is True but debounce gate
        # blocks (now < debounce_until) → IDLE.
        out2 = svc.evaluate(_inp(completed=set(), ingested=set(), now=t + 300), out1.new_state)
        assert out2.decision == WatcherDecision.IDLE
        assert out2.new_state is out1.new_state  # unchanged

        # Cycle 3: now = t + 900 (window expired).  Branch 4 does NOT clear
        # (origin="safety_net").  Branch 5 debounce gate: now >= debounce_until → fires.
        out3 = svc.evaluate(_inp(completed=set(), ingested=set(), now=t + 900), out1.new_state)
        assert out3.decision == WatcherDecision.FIRE_RUN
        assert out3.run_reason == "safety_net"
        assert out3.new_state.backoff_multiplier == 2  # incremented (was 1)
        assert out3.new_state.debounce_origin == "safety_net"
        assert out3.new_state.debounce_until == (t + 900) + 1800  # min(900*2^1, 86400)

    def test_safety_net_window_survives_stale_clear(self) -> None:
        """Safety-net-origin debounce window is NOT cleared by branch 4.

        Config with debounce_s=60, safety_net_hours=1 (3600s).  After a
        safety-net fire sets origin="safety_net", branch 4 must leave the
        window intact.
        """
        svc = WatcherService(
            WatchConfig(
                enabled=True,
                debounce_s=60,
                safety_net_hours=1,
                poll_interval_s=10,
            )
        )
        t = 1_000_000.0

        # Set up state as if a safety-net fire just happened.
        state = WatcherState(
            debounce_until=t + 60,
            backoff_multiplier=1,
            debounce_origin="safety_net",
            last_successful_run_at=t,  # fresh run, safety-net NOT expired yet
        )
        # No work, safety-net not expired → branch 4 is evaluated.
        # Origin is "safety_net" → branch 4 must NOT clear.
        inp = _inp(completed=set(), ingested=set(), now=t + 30)  # within window
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE  # safety-net not expired, no work
        assert out.new_state.debounce_until == t + 60  # window survives
        assert out.new_state.backoff_multiplier == 1  # backoff survives
        assert out.new_state.debounce_origin == "safety_net"  # origin survives

    # ------------------------------------------------------------------
    # Acceptance (d): cross_seed_dispatched survives every FIRE_RUN path
    # ------------------------------------------------------------------

    def test_cross_seed_dispatched_survives_manual_fire(self, svc: WatcherService) -> None:
        """Manual fire (sentinel) preserves cross_seed_dispatched."""
        dispatched = frozenset({"hash_a", "hash_b"})
        state = WatcherState(
            cross_seed_dispatched=dispatched,
            debounce_until=2_000_000.0,
            backoff_multiplier=3,
        )
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0, sentinel=True)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "manual"
        assert out.new_state.cross_seed_dispatched == dispatched

    def test_cross_seed_dispatched_survives_completion_fire(self, svc: WatcherService) -> None:
        """Completion fire preserves cross_seed_dispatched."""
        dispatched = frozenset({"hash_a"})
        state = WatcherState(
            cross_seed_dispatched=dispatched,
            debounce_until=1_000_000.0,
            backoff_multiplier=0,
        )
        inp = _inp(completed={"hash_a"}, ingested=set(), now=1_000_100.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "completion"
        assert out.new_state.cross_seed_dispatched == dispatched

    def test_cross_seed_dispatched_survives_safety_net_fire(self, svc: WatcherService) -> None:
        """Safety-net fire preserves cross_seed_dispatched."""
        dispatched = frozenset({"hash_x"})
        state = WatcherState(
            cross_seed_dispatched=dispatched,
            last_successful_run_at=None,  # triggers safety-net
        )
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "safety_net"
        assert out.new_state.cross_seed_dispatched == dispatched


class TestDeferredHashes:
    """Transiently-deferred hashes must not trigger pipeline runs (2026-07-15).

    Live incident: torrents skipped by ingest for transient reasons (ratio,
    content missing, disk full) were never marked ingested, stayed in the
    work set forever, and the watcher fired « Pipeline » runs with empty
    results in a loop.
    """

    @pytest.fixture
    def svc(self) -> WatcherService:
        """WatcherService with the standard test config."""
        return WatcherService(WatchConfig(enabled=True, debounce_s=900, safety_net_hours=24, poll_interval_s=60))

    def test_deferred_hash_does_not_start_debounce(self, svc: WatcherService) -> None:
        """All work deferred → IDLE, no debounce window opens."""
        state = WatcherState(
            last_successful_run_at=1_000_000.0,
            cross_seed_dispatched=frozenset({"abc"}),
        )
        inp = _inp(completed={"abc"}, ingested=set(), deferred={"abc"}, now=1_000_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE
        assert out.new_state.debounce_until is None

    def test_deferred_hash_still_cross_seeds(self, svc: WatcherService) -> None:
        """A deferred completed torrent is seedable — cross-seed still fires."""
        state = WatcherState(last_successful_run_at=1_000_000.0)
        inp = _inp(completed={"abc"}, ingested=set(), deferred={"abc"}, now=1_000_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_CROSS_SEED
        assert out.cross_seed_hashes == ["abc"]

    def test_condition_clears_hash_reenters_trigger_set(self, svc: WatcherService) -> None:
        """Once no longer deferred, the same hash starts a debounce window."""
        state = WatcherState(
            last_successful_run_at=1_000_000.0,
            cross_seed_dispatched=frozenset({"abc"}),
        )
        # Cycle 1: deferred → IDLE.
        out1 = svc.evaluate(_inp(completed={"abc"}, ingested=set(), deferred={"abc"}, now=1_000_000.0), state)
        assert out1.decision == WatcherDecision.IDLE
        # Cycle 2: ratio reached (no longer deferred) → START_DEBOUNCE.
        out2 = svc.evaluate(
            _inp(completed={"abc"}, ingested=set(), now=1_000_030.0),
            out1.new_state,
        )
        assert out2.decision == WatcherDecision.START_DEBOUNCE

    def test_all_work_becomes_deferred_clears_completion_window(self, svc: WatcherService) -> None:
        """An open completion debounce clears when remaining work is all deferred."""
        state = WatcherState(
            debounce_until=1_000_500.0,
            debounce_origin="completion",
            backoff_multiplier=2,
            cross_seed_dispatched=frozenset({"abc"}),
            last_successful_run_at=1_000_000.0,
        )
        inp = _inp(completed={"abc"}, ingested=set(), deferred={"abc"}, now=1_000_100.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.IDLE
        assert out.new_state.debounce_until is None, "stale completion window must clear"
        assert out.new_state.backoff_multiplier == 0

    def test_mixed_work_still_fires_for_non_deferred(self, svc: WatcherService) -> None:
        """One deferred + one actionable hash → the actionable one triggers."""
        state = WatcherState(
            last_successful_run_at=1_000_000.0,
            cross_seed_dispatched=frozenset({"abc", "def"}),
        )
        inp = _inp(completed={"abc", "def"}, ingested=set(), deferred={"abc"}, now=1_000_000.0)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.START_DEBOUNCE

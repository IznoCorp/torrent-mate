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
) -> WatcherInput:
    """Build a WatcherInput with sensible defaults for concise test setup.

    Args:
        completed: Info-hashes returned by ``get_completed()``.
        ingested: Info-hashes already ingested.
        now: Injected wall-clock timestamp (float).
        seed_pure: Info-hashes tagged SEED_PURE (excluded from all work).
        sentinel: Whether ``watch.trigger`` exists.
        lock_held: Whether the pipeline lock file exists.

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
        assert out.new_state.backoff_multiplier == 0

    def test_safety_net_fires_when_expired_25h(self, svc: WatcherService) -> None:
        """25 h elapsed with 24 h config → safety net triggers."""
        state = WatcherState(last_successful_run_at=1_000_000.0)
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0 + 25 * 3600)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "safety_net"
        assert out.new_state.backoff_multiplier == 0  # backoff reset on safety-net run

    def test_safety_net_fires_at_exact_boundary_24h(self, svc: WatcherService) -> None:
        """Exactly 24 h elapsed with 24 h config → safety net triggers (boundary)."""
        state = WatcherState(last_successful_run_at=1_000_000.0)
        inp = _inp(completed=set(), ingested=set(), now=1_000_000.0 + 24 * 3600)
        out = svc.evaluate(inp, state)
        assert out.decision == WatcherDecision.FIRE_RUN
        assert out.run_reason == "safety_net"

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
        stale-window clear (step 4) returns first.
        """
        state = WatcherState(debounce_until=1_000_000.0)  # last_successful_run_at=None
        inp = _inp(completed=set(), ingested=set(), now=1_500_000.0)
        out = svc.evaluate(inp, state)
        # Step 4 clears stale window → IDLE (not safety-net FIRE_RUN)
        assert out.decision == WatcherDecision.IDLE
        assert out.new_state.debounce_until is None
        assert out.new_state.backoff_multiplier == 0

"""Tests for the pure anti-loop guard in :mod:`kanbanmate.core.antiloop`.

Covers the target-keyed dedup guard (first move allowed, immediate repeat to the
same target blocked, expiry after the TTL) and the per-ticket rate limit.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import get_origin, get_type_hints

from kanbanmate.core.antiloop import (
    AntiLoopConfig,
    AntiLoopState,
    forget,
    is_blocked,
    record_move,
)


class TestTargetKeyedGuard:
    """The target-keyed dedup guard."""

    def test_first_move_allowed(self) -> None:
        """A move on a fresh, empty state is never blocked."""
        state = AntiLoopState()
        assert is_blocked(state, "ticket-1", "InProgress", now=0.0) is False

    def test_immediate_repeat_to_same_target_blocked(self) -> None:
        """A repeat move to the same target within the TTL is blocked."""
        state = record_move(AntiLoopState(), "ticket-1", "InProgress", now=100.0)
        assert is_blocked(state, "ticket-1", "InProgress", now=101.0) is True

    def test_repeat_to_different_target_allowed(self) -> None:
        """The guard is keyed on the target column, not just the ticket."""
        state = record_move(AntiLoopState(), "ticket-1", "InProgress", now=100.0)
        assert is_blocked(state, "ticket-1", "Review", now=101.0) is False

    def test_repeat_for_different_ticket_allowed(self) -> None:
        """The guard is keyed on the ticket too: another ticket is unaffected."""
        state = record_move(AntiLoopState(), "ticket-1", "InProgress", now=100.0)
        assert is_blocked(state, "ticket-2", "InProgress", now=101.0) is False

    def test_move_allowed_again_after_ttl_expires(self) -> None:
        """Past the recency TTL, the same target is permitted again."""
        cfg = AntiLoopConfig(recent_ttl=600.0)
        state = record_move(AntiLoopState(), "ticket-1", "InProgress", now=100.0)
        # 100 + 600 = 700 is exactly the TTL boundary; just past it is allowed.
        assert is_blocked(state, "ticket-1", "InProgress", now=701.0, config=cfg) is False


class TestRateLimit:
    """The per-ticket rate limit."""

    def test_blocks_once_limit_reached(self) -> None:
        """Reaching the rate limit within the window blocks further moves."""
        cfg = AntiLoopConfig(rate_limit=3, rate_window=3600.0, recent_ttl=0.0)
        state = AntiLoopState()
        # Three distinct targets so the dedup guard never trips; only the rate
        # limit can block here.
        for index in range(3):
            state = record_move(state, "ticket-1", f"col-{index}", now=float(index))
        assert is_blocked(state, "ticket-1", "col-new", now=3.0, config=cfg) is True

    def test_below_limit_allowed(self) -> None:
        """Below the rate limit, moves are permitted."""
        cfg = AntiLoopConfig(rate_limit=3, rate_window=3600.0, recent_ttl=0.0)
        state = AntiLoopState()
        for index in range(2):
            state = record_move(state, "ticket-1", f"col-{index}", now=float(index))
        assert is_blocked(state, "ticket-1", "col-new", now=2.0, config=cfg) is False

    def test_stale_moves_fall_out_of_window(self) -> None:
        """Moves older than the rate window no longer count toward the limit."""
        cfg = AntiLoopConfig(rate_limit=2, rate_window=3600.0, recent_ttl=0.0)
        state = AntiLoopState()
        state = record_move(state, "ticket-1", "col-0", now=0.0)
        state = record_move(state, "ticket-1", "col-1", now=10.0)
        # Far in the future: both recorded moves are outside the 3600 s window.
        assert is_blocked(state, "ticket-1", "col-new", now=100_000.0, config=cfg) is False


class TestRecordMove:
    """Immutability and bookkeeping of :func:`record_move`."""

    def test_returns_new_state_leaving_input_untouched(self) -> None:
        """Recording a move does not mutate the input state."""
        original = AntiLoopState()
        updated = record_move(original, "ticket-1", "InProgress", now=5.0)
        assert original.recent_targets == {}
        assert original.move_times == {}
        assert updated.recent_targets == {("ticket-1", "InProgress"): 5.0}
        assert updated.move_times == {"ticket-1": (5.0,)}

    def test_accumulates_move_times(self) -> None:
        """Successive moves accumulate their timestamps per ticket."""
        state = AntiLoopState()
        state = record_move(state, "ticket-1", "col-0", now=1.0)
        state = record_move(state, "ticket-1", "col-1", now=2.0)
        assert state.move_times["ticket-1"] == (1.0, 2.0)


class TestImmutability:
    """The immutability guarantee is enforced at the type boundary."""

    def test_field_types_are_mapping_not_dict(self) -> None:
        """The field type annotations must use Mapping, not dict.

        With ``@dataclass(frozen=True)`` + ``dict`` fields, ``frozen`` only
        blocks *attribute rebinding* (``state.x = ...``) — the dict values are
        freely mutable in place (``state.recent_targets[k] = v`` succeeds
        silently).  Changing the type annotations to ``Mapping`` means mypy will
        reject any ``__setitem__`` on the fields at static-analysis time,
        enforcing the documented "input state left untouched" contract.

        This test guards against a regression to ``dict`` in the annotations.
        """
        hints = get_type_hints(AntiLoopState)
        assert get_origin(hints["recent_targets"]) is Mapping, (
            f"recent_targets must be typed as Mapping, got {hints['recent_targets']}"
        )
        assert get_origin(hints["move_times"]) is Mapping, (
            f"move_times must be typed as Mapping, got {hints['move_times']}"
        )

    def test_record_move_returns_fresh_state_input_untouched(self) -> None:
        """``record_move`` must still return a new state leaving the input unchanged."""
        original = AntiLoopState()
        updated = record_move(original, "ticket-A", "InProgress", now=42.0)
        # Input untouched
        assert len(original.recent_targets) == 0
        assert len(original.move_times) == 0
        # Output carries the new record
        assert updated.recent_targets[("ticket-A", "InProgress")] == 42.0
        assert updated.move_times["ticket-A"] == (42.0,)
        # Structural independence: mutating a dict extracted from the new state
        # must not propagate back to the original.
        assert original is not updated


class TestBookkeepingFlag:
    """The #19 rollback-aware ``bookkeeping`` flag on :func:`record_move`."""

    def test_bookkeeping_move_sets_recency_marker(self) -> None:
        """A bookkeeping move STILL records the ``(ticket, target)`` recency marker.

        The dedup baseline is set so a later identical-target check reads "already handled,
        do not re-trigger" (the rollback bounce is not re-fired)."""
        state = record_move(AntiLoopState(), "ticket-1", "Backlog", now=100.0, bookkeeping=True)
        assert state.recent_targets[("ticket-1", "Backlog")] == 100.0
        # The recency guard still blocks an immediate repeat to the same target.
        assert is_blocked(state, "ticket-1", "Backlog", now=101.0) is True

    def test_bookkeeping_move_excluded_from_rate_limit_counter(self) -> None:
        """A ``bookkeeping=True`` move does NOT feed the per-ticket rate-limit counter (#19).

        A legitimate rollback must not eat into the runaway-loop budget — only genuine
        auto-loop moves count (the PoC counted auto/bot moves only)."""
        state = record_move(AntiLoopState(), "ticket-1", "Backlog", now=0.0, bookkeeping=True)
        # No rate-limit timestamp was appended for this ticket.
        assert "ticket-1" not in state.move_times

    def test_bookkeeping_moves_never_trip_the_rate_limit(self) -> None:
        """Many bookkeeping moves to DISTINCT targets never trip the rate limit (#19).

        Each bookkeeping move is excluded from the counter, so even past the cap the rate
        limit cannot fire on a fresh (un-recorded) target."""
        cfg = AntiLoopConfig(rate_limit=2, rate_window=3600.0, recent_ttl=0.0)
        state = AntiLoopState()
        for index in range(5):
            state = record_move(
                state, "ticket-1", f"col-{index}", now=float(index), bookkeeping=True
            )
        # recent_ttl=0 disables the dedup guard, so only the rate limit could block — and it
        # cannot, because no bookkeeping move was counted.
        assert is_blocked(state, "ticket-1", "col-new", now=5.0, config=cfg) is False

    def test_default_move_still_feeds_the_counter(self) -> None:
        """A default (``bookkeeping=False``) move still feeds the rate-limit counter."""
        state = record_move(AntiLoopState(), "ticket-1", "Backlog", now=7.0)
        assert state.move_times["ticket-1"] == (7.0,)

    def test_bookkeeping_recency_ttl_holds(self) -> None:
        """The 600s recency TTL applies to a bookkeeping marker like any other (#19)."""
        cfg = AntiLoopConfig(recent_ttl=600.0)
        state = record_move(AntiLoopState(), "ticket-1", "Backlog", now=100.0, bookkeeping=True)
        # Within the TTL → still "recent" (do-not-re-trigger).
        assert is_blocked(state, "ticket-1", "Backlog", now=500.0, config=cfg) is True
        # Past the TTL boundary → the marker no longer blocks.
        assert is_blocked(state, "ticket-1", "Backlog", now=701.0, config=cfg) is False

    def test_restart_wipes_the_net(self) -> None:
        """A fresh (empty) :class:`AntiLoopState` carries no markers — a restart wipes the net.

        The in-memory net is documented (DESIGN §6) to be lost on restart; the diff-baseline
        re-sync is the intended backstop. A bookkeeping rollback recorded in one 'session' is
        gone after the daemon restarts with a default state."""
        recorded = record_move(AntiLoopState(), "ticket-1", "Backlog", now=100.0, bookkeeping=True)
        assert ("ticket-1", "Backlog") in recorded.recent_targets
        # Simulate a daemon restart: a brand-new default state.
        after_restart = AntiLoopState()
        assert after_restart.recent_targets == {}
        assert after_restart.move_times == {}
        assert is_blocked(after_restart, "ticket-1", "Backlog", now=101.0) is False


class TestForget:
    """The #22 pure teardown reset :func:`forget`."""

    def test_drops_all_entries_for_the_ticket(self) -> None:
        """``forget`` removes every recency marker AND the rate-limit history for a ticket."""
        state = AntiLoopState()
        state = record_move(state, "ticket-1", "InProgress", now=1.0)
        state = record_move(state, "ticket-1", "Review", now=2.0)
        state = record_move(state, "ticket-2", "InProgress", now=3.0)

        result = forget(state, "ticket-1")

        # ticket-1's entries are gone from both indices.
        assert ("ticket-1", "InProgress") not in result.recent_targets
        assert ("ticket-1", "Review") not in result.recent_targets
        assert "ticket-1" not in result.move_times
        # ticket-2 is untouched.
        assert ("ticket-2", "InProgress") in result.recent_targets
        assert "ticket-2" in result.move_times

    def test_no_stale_timestamps_survive(self) -> None:
        """After forget, the dropped ticket is no longer blocked by its old markers."""
        state = record_move(AntiLoopState(), "ticket-1", "InProgress", now=100.0)
        assert is_blocked(state, "ticket-1", "InProgress", now=101.0) is True
        result = forget(state, "ticket-1")
        # The stale marker is gone → an identical move is no longer deduped.
        assert is_blocked(result, "ticket-1", "InProgress", now=101.0) is False

    def test_is_pure_input_untouched(self) -> None:
        """``forget`` does not mutate the input state (the core is immutable)."""
        state = record_move(AntiLoopState(), "ticket-1", "InProgress", now=1.0)
        _ = forget(state, "ticket-1")
        assert ("ticket-1", "InProgress") in state.recent_targets
        assert "ticket-1" in state.move_times

    def test_unknown_ticket_is_clean_noop(self) -> None:
        """Forgetting a ticket with no recorded entries is a clean no-op."""
        state = record_move(AntiLoopState(), "ticket-1", "InProgress", now=1.0)
        result = forget(state, "ticket-absent")
        assert result.recent_targets == state.recent_targets
        assert result.move_times == state.move_times

"""WatcherService — pure decision engine for the watch daemon (W1–W7).

No I/O, no sleep, no subprocess — the service is a pure function of its
inputs per cycle.  The watch loop drives it each poll cycle.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass, field

from personalscraper.conf.models.watch_seed import WatchConfig


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


class WatcherService:
    """Pure decision engine for the watcher daemon.

    Injected clock (now) keeps the service unit-testable — no ``time.time()``
    calls.  The watch loop builds a :class:`WatcherInput` snapshot each cycle
    and executes the returned :class:`WatcherOutput`.
    """

    def __init__(self, config_watch: WatchConfig) -> None:
        """Initialise from watch config.

        Args:
            config_watch: ``AppConfig.watch`` (:class:`WatchConfig`).
        """
        self._poll_interval_s: int = config_watch.poll_interval_s
        self._debounce_s: int = config_watch.debounce_s
        self._safety_net_hours: int = config_watch.safety_net_hours
        self._enabled: bool = config_watch.enabled

    def evaluate(self, inp: WatcherInput, state: WatcherState) -> WatcherOutput:
        """Produce one cycle's decision (see DESIGN §Watcher for the full flow).

        Pure: no I/O, no ``time.time()``, no logging.  Returns fresh
        :class:`WatcherState` instances via :func:`dataclasses.replace`;
        never mutates *inp* or *state*.

        The watch loop (Phase 7) must reset ``backoff_multiplier=0`` and
        ``debounce_until=None`` after a successful ``FIRE_RUN`` that makes
        the work predicate go false (storm-is-over signal).

        Args:
            inp: Snapshot of the world for this cycle.
            state: Watcher state carried forward from the previous cycle.

        Returns:
            WatcherOutput with the decision for this cycle and updated state.
        """
        if not self._enabled:
            return WatcherOutput(decision=WatcherDecision.IDLE, new_state=state)

        # 1. Sentinel present — manual poke bypasses all windows.
        if inp.sentinel_present:
            if inp.pipeline_lock_held:
                return self._requeue(state)
            new_state = dataclasses.replace(
                state,
                debounce_until=None,
                backoff_multiplier=0,
            )
            return WatcherOutput(
                decision=WatcherDecision.FIRE_RUN,
                run_reason="manual",
                new_state=new_state,
            )
        # 2. Cross-seed: new completions not yet dispatched this daemon lifetime.
        work_set = inp.completed_hashes - inp.ingested_hashes - inp.seed_pure_hashes
        cross_seed_new = work_set - state.cross_seed_dispatched
        if cross_seed_new:
            new_state = dataclasses.replace(
                state,
                cross_seed_dispatched=state.cross_seed_dispatched | cross_seed_new,
            )
            return WatcherOutput(
                decision=WatcherDecision.FIRE_CROSS_SEED,
                cross_seed_hashes=sorted(cross_seed_new),
                new_state=new_state,
            )
        # 3. Work predicate: items exist that need a pipeline run.
        if work_set:
            if state.debounce_until is None:
                # 3a. Start a fresh debounce window.
                new_state = dataclasses.replace(
                    state,
                    debounce_until=inp.now + self._debounce_s,
                )
                return WatcherOutput(
                    decision=WatcherDecision.START_DEBOUNCE,
                    new_state=new_state,
                )
            elif inp.now >= state.debounce_until:
                # 3b. Debounce window expired — fire a pipeline run.
                if inp.pipeline_lock_held:
                    return self._requeue(state)
                multiplier = state.backoff_multiplier
                new_debounce = inp.now + self._debounce_s * (2**multiplier)
                new_state = dataclasses.replace(
                    state,
                    debounce_until=new_debounce,
                    backoff_multiplier=multiplier + 1,
                )
                return WatcherOutput(
                    decision=WatcherDecision.FIRE_RUN,
                    run_reason="completion",
                    new_state=new_state,
                )
            else:
                # 3c. Still within the debounce window — wait.
                return WatcherOutput(
                    decision=WatcherDecision.IDLE,
                    new_state=state,
                )
        # 4. Stale-window clear: work vanished while debounce window was open.
        if state.debounce_until is not None:
            new_state = dataclasses.replace(
                state,
                debounce_until=None,
                backoff_multiplier=0,
            )
            return WatcherOutput(
                decision=WatcherDecision.IDLE,
                new_state=new_state,
            )
        # 5. Safety-net: no successful run for too long.
        if self._safety_net_expired(state, inp.now):
            if inp.pipeline_lock_held:
                return self._requeue(state)
            new_state = dataclasses.replace(
                state,
                debounce_until=inp.now + self._debounce_s,
                backoff_multiplier=0,
            )
            return WatcherOutput(
                decision=WatcherDecision.FIRE_RUN,
                run_reason="safety_net",
                new_state=new_state,
            )
        # 6. Nothing to do.
        return WatcherOutput(decision=WatcherDecision.IDLE, new_state=state)

    def _safety_net_expired(self, state: WatcherState, now: float) -> bool:
        """True when no successful run for ``safety_net_hours``.

        Args:
            state: Current watcher state.
            now: Current injected-clock timestamp.

        Returns:
            True if a safety-net run is due.
        """
        if state.last_successful_run_at is None:
            return True
        elapsed_hours = (now - state.last_successful_run_at) / 3600.0
        return elapsed_hours >= self._safety_net_hours

    def _requeue(self, state: WatcherState) -> WatcherOutput:
        """Lock held → REQUEUE, state unchanged (W6)."""
        return WatcherOutput(decision=WatcherDecision.REQUEUE, new_state=state)


__all__ = [
    "WatcherDecision",
    "WatcherInput",
    "WatcherOutput",
    "WatcherService",
    "WatcherState",
]

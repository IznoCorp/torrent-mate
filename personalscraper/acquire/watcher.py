"""WatcherService — pure decision engine for the watch daemon (W1–W7).

No I/O, no sleep, no subprocess — the service is a pure function of its
inputs per cycle.  The watch loop in ``commands/watch.py`` calls it each
poll cycle and executes the returned decisions.

See docs/features/watch-seed/DESIGN.md §Watcher.
"""

from __future__ import annotations

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
    calls.  The watch loop in ``commands/watch.py`` is the sole caller; it
    builds a :class:`WatcherInput` snapshot each cycle and executes the
    returned :class:`WatcherOutput`.

    Attributes:
        _poll_interval_s: Seconds between poll cycles (from WatchConfig).
        _debounce_s: Quiet window in seconds after a pipeline trigger (from WatchConfig).
        _safety_net_hours: Max hours without a successful run before forcing one (from WatchConfig).
        _enabled: Global kill-switch — when False, every cycle returns IDLE (from WatchConfig).
    """

    def __init__(self, config_watch: WatchConfig) -> None:
        """Initialise the decision engine from the watch configuration.

        Args:
            config_watch: ``AppConfig.watch`` — the resolved :class:`WatchConfig`
                for the current daemon invocation.
        """
        self._poll_interval_s: int = config_watch.poll_interval_s
        self._debounce_s: int = config_watch.debounce_s
        self._safety_net_hours: int = config_watch.safety_net_hours
        self._enabled: bool = config_watch.enabled


__all__ = [
    "WatcherDecision",
    "WatcherInput",
    "WatcherOutput",
    "WatcherService",
    "WatcherState",
]

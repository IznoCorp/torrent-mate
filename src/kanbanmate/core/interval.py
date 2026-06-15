"""Poll-interval strategy (DESIGN §3.3 ``interval.py``).

By default the daemon polls the board on a **fixed 10 s cadence** — the idle
back-off is disabled so a card move is detected within ~10 s no matter how long
the board has been quiet (the geometric back-off lengthened the reprise to up to
5 min, which the operator deemed too slow). The default :class:`IntervalConfig`
sets ``idle_max == base == 10.0``, which clamps :func:`next_sleep` to a flat
``10.0`` for *any* idle duration. GraphQL rate-limit cost at 10 s is negligible
(~7 %/h of the 5000 pt/h budget).

The geometric back-off curve is still implemented and is **opt-in**: it engages
only when an operator explicitly configures ``idle_max > base`` (e.g.
``IntervalConfig(base=15, idle_max=300, backoff=2)``). With the shipped default it
is a no-op.

The strategy is a pure function of *time only*: given the timestamp of the last
observed activity and the current time, it returns how long the daemon should
sleep before the next poll.  No clock or I/O is read inside the core — ``now`` is
supplied by the imperative shell.

Curve (opt-in only): the sleep starts at :attr:`IntervalConfig.base` while
activity is recent and grows geometrically by :attr:`IntervalConfig.backoff` for
every ``base``-long idle stretch, clamped at :attr:`IntervalConfig.idle_max`. When
``idle_max == base`` (the default) the curve degenerates to a flat ``base``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Default cadence: a FIXED 10 s poll. ``idle_max == base`` makes ``next_sleep``
# return a flat ``base`` for any idle (the back-off never lengthens the cadence).
_DEFAULT_BASE = 10.0  # seconds: the fixed poll cadence (no idle lengthening)
_DEFAULT_IDLE_MAX = 10.0  # seconds: == base ⇒ idle back-off disabled by default
# Kept > 1 so ``math.log(idle_max / base, backoff)`` never divides by zero (with
# ``idle_max == base`` this is ``log(1, backoff) == 0`` ⇒ max_exponent 0 ⇒ flat).
# Only relevant when an operator opts into back-off via ``idle_max > base``.
_DEFAULT_BACKOFF = 2.0  # geometric growth factor per idle stretch (opt-in only)


@dataclass(frozen=True)
class IntervalConfig:
    """Tunables for the poll interval.

    The shipped default is a **fixed 10 s cadence**: ``base == idle_max == 10.0``,
    so :func:`next_sleep` returns a flat ``10.0`` for any idle and the geometric
    back-off never engages. The back-off is **opt-in** — an operator gets it back
    only by explicitly constructing an :class:`IntervalConfig` with
    ``idle_max > base`` (e.g. ``IntervalConfig(base=15, idle_max=300, backoff=2)``).

    Attributes:
        base: The minimum sleep, in seconds, used while activity is recent. Also
            the unit length of an "idle stretch" used to scale the back-off. With
            the default config this is the *constant* poll cadence.
        idle_max: The maximum sleep, in seconds, the interval backs off toward
            when the board has been idle for a long time. Defaults to ``base``,
            which disables the back-off (a fixed cadence). Set ``> base`` to opt
            into the geometric idle back-off.
        backoff: The geometric growth factor applied per elapsed ``base``-long
            idle stretch. Must be greater than 1 for the interval to grow. Has no
            effect when ``idle_max == base`` (the default fixed cadence).
    """

    base: float = _DEFAULT_BASE
    idle_max: float = _DEFAULT_IDLE_MAX
    backoff: float = _DEFAULT_BACKOFF


def next_sleep(
    last_activity_ts: float,
    now: float,
    cfg: IntervalConfig | None = None,
) -> float:
    """Return how long to sleep before the next poll, given recent activity.

    While the board is active (idle time below one ``base`` stretch) the function
    returns :attr:`IntervalConfig.base`.  As idle time grows it backs off
    geometrically by :attr:`IntervalConfig.backoff` per ``base``-long stretch,
    clamped at :attr:`IntervalConfig.idle_max`.  The function is pure and
    non-decreasing in the idle duration.

    With the **default** config (``idle_max == base == 10.0``) the back-off
    degenerates to a constant: the function returns a flat ``10.0`` for any idle,
    giving the fixed 10 s cadence. The geometric back-off only engages when an
    operator opts in with an explicit ``idle_max > base``.

    Args:
        last_activity_ts: Timestamp (wall-clock / POSIX seconds) of the last
            observed board activity.
        now: The current timestamp (wall-clock / POSIX seconds), supplied by
            the caller.
        cfg: Optional tunables; defaults to :class:`IntervalConfig`.

    Returns:
        The sleep duration in seconds, in the closed range
        ``[cfg.base, cfg.idle_max]``.
    """
    config = cfg or IntervalConfig()

    # A clock skew (or first tick) can yield a negative idle; treat as "active".
    idle = max(0.0, now - last_activity_ts)

    # Within the first base stretch the board counts as active: stay tight.
    if idle < config.base:
        return config.base

    # Number of whole idle stretches elapsed beyond the first active one.
    stretches = int(idle // config.base)

    # Cap the exponent: once the candidate would reach idle_max the result is
    # clamped anyway, so computing larger powers is wasted work — and an
    # uncapped ``backoff ** stretches`` overflows for very large idle times.
    # ``ceil(log_backoff(idle_max / base))`` is the smallest exponent at which
    # ``base * backoff**exp >= idle_max``.
    max_exponent = math.ceil(math.log(config.idle_max / config.base, config.backoff))
    capped = min(stretches, max(max_exponent, 0))
    candidate = config.base * (config.backoff**capped)

    # Clamp to the idle ceiling so the cadence never exceeds idle_max.
    return min(candidate, config.idle_max)

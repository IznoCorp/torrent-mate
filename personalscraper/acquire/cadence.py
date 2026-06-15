"""Pure cadence value objects and predicates for the acquisition lobe (D2).

Defines the Hot/Warm/Cold backoff tiers and cutoff policy. Entirely pure:
imports ``core``/stdlib only — never ``scraper``, ``indexer``, ``store``, or
the event bus.

Logging: this module has no side-effects; callers log.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CadenceTier:
    """One tier in the Hot/Warm/Cold backoff ladder.

    Attributes:
        max_age_s: Upper bound (exclusive) of ages that fall in this tier,
            in seconds. Tiers must be ordered by max_age_s ascending.
        interval_s: Minimum gap between two searches while in this tier,
            in seconds.
    """

    max_age_s: int
    interval_s: int


@dataclass(frozen=True)
class Cadence:
    """Complete cadence policy for a wanted item.

    Attributes:
        tiers: Ordered tuple of :class:`CadenceTier` (ascending max_age_s).
            Covers Hot, Warm, Cold in the canonical policy.
        cutoff_s: Age in seconds at or after which the item is abandoned
            (``is_past_cutoff`` returns True; ``is_due_by_cadence`` returns False).
    """

    tiers: tuple[CadenceTier, ...]
    cutoff_s: int


def is_due_by_cadence(
    cadence: Cadence,
    *,
    now: int,
    enqueued_at: int,
    last_search_at: int | None,
) -> bool:
    """Return True iff the item should be (re)searched at ``now``.

    A never-searched item (``last_search_at is None``) is due immediately
    while inside the cadence window — that is the whole point of a fresh
    enqueue. Returns False when past cutoff, when no tier matches (age >= all
    tier max_age_s but below cutoff — treated as not-due), or when
    ``last_search_at`` is too recent for the current tier's interval.

    Args:
        cadence: The effective cadence policy for this item.
        now: Current unix epoch seconds (injected — no hidden clock).
        enqueued_at: Unix epoch seconds when the item was enqueued (age origin).
        last_search_at: Unix epoch seconds of the last search attempt, or None
            if never searched (None → due now while within the window).

    Returns:
        True iff the item is due for a (re)search.
    """
    if is_past_cutoff(cadence, now=now, enqueued_at=enqueued_at):
        return False

    age = now - enqueued_at
    # Select the first tier whose max_age_s > age (i.e. age < max_age_s).
    tier: CadenceTier | None = next((t for t in cadence.tiers if age < t.max_age_s), None)
    if tier is None:
        # age is between last tier max_age_s and cutoff_s — treat as not-due.
        return False

    if last_search_at is None:
        # Never searched → due now (within the window).
        return True

    return (now - last_search_at) >= tier.interval_s


def is_past_cutoff(cadence: Cadence, *, now: int, enqueued_at: int) -> bool:
    """Return True iff the item's age has reached or exceeded the cutoff.

    Args:
        cadence: The effective cadence policy.
        now: Current unix epoch seconds.
        enqueued_at: Unix epoch seconds when the item was enqueued.

    Returns:
        True iff (now - enqueued_at) >= cadence.cutoff_s.
    """
    return (now - enqueued_at) >= cadence.cutoff_s


__all__ = ["Cadence", "CadenceTier", "is_due_by_cadence", "is_past_cutoff"]

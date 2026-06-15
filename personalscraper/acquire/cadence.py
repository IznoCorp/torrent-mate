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

    def __post_init__(self) -> None:
        """Validate the tier invariants once at construction time.

        Leaf-level guard making an illegal tier unrepresentable on its own,
        independent of any enclosing :class:`Cadence`. Fires before
        ``Cadence.__post_init__`` when a bad tier is nested in a Cadence (the
        tuple is built — hence each tier constructed — before the Cadence body
        runs), so the resulting ``ValueError`` names the offending tier field.

        Raises:
            ValueError: if ``max_age_s`` or ``interval_s`` is non-positive.
        """
        if self.max_age_s <= 0:
            raise ValueError(f"CadenceTier.max_age_s must be positive, got {self.max_age_s}")
        if self.interval_s <= 0:
            raise ValueError(f"CadenceTier.interval_s must be positive, got {self.interval_s}")


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

    def __post_init__(self) -> None:
        """Validate the cadence invariants once at construction time.

        Makes illegal states unrepresentable: every construction path
        (``cadence_from_config``, ``cadence_from_json``, direct) is
        self-validating, mirroring the ``CadenceConfig`` validator at the VO
        level. Runs once at build — the predicates stay branch-free.

        Raises:
            ValueError: if ``tiers`` is empty; any tier has a non-positive
                ``max_age_s`` or ``interval_s``; ``tiers`` are not strictly
                increasing by ``max_age_s``; or ``cutoff_s`` is below the last
                tier's ``max_age_s``.
        """
        if not self.tiers:
            raise ValueError("Cadence.tiers must not be empty")

        prev_max: int | None = None
        for tier in self.tiers:
            if tier.max_age_s <= 0:
                raise ValueError(f"CadenceTier.max_age_s must be positive, got {tier.max_age_s}")
            if tier.interval_s <= 0:
                raise ValueError(f"CadenceTier.interval_s must be positive, got {tier.interval_s}")
            if prev_max is not None and tier.max_age_s <= prev_max:
                raise ValueError(
                    f"Cadence.tiers must be strictly increasing by max_age_s, got {tier.max_age_s} after {prev_max}"
                )
            prev_max = tier.max_age_s

        if self.cutoff_s < self.tiers[-1].max_age_s:
            raise ValueError(
                "Cadence.cutoff_s must be >= the last tier's max_age_s, "
                f"got cutoff_s={self.cutoff_s} < {self.tiers[-1].max_age_s}"
            )


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
    enqueue. Returns False when past cutoff or when ``last_search_at`` is too
    recent for the current tier's interval. When no tier matches (age >= all
    tier max_age_s but below cutoff), the item keeps searching at the last
    (slowest/Cold) tier's interval rather than freezing — it is abandoned only
    once ``is_past_cutoff`` fires.

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
    # When age is beyond the last tier (age >= tiers[-1].max_age_s) but still
    # before cutoff, fall back to the last (slowest/Cold) tier and keep
    # searching at that cadence until is_past_cutoff fires. This prevents the
    # dead-band freeze that occurred when cutoff_s > tiers[-1].max_age_s (the
    # validator allows cutoff >= last tier, so that gap is reachable).
    tier: CadenceTier = next((t for t in cadence.tiers if age < t.max_age_s), cadence.tiers[-1])

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

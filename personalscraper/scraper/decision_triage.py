"""Shared decision-triage logic for the scrape-arbiter three-tier trigger.

Extracted from movie_service.py and tv_service.py to stay under the
module-size ceiling (1000 non-blank LOC). Both services shared identical
LOW_CONFIDENCE / HIGH_CONFIDENCE / AMBIGUITY_DELTA branching; this module
consolidates the pure classification and result-mutation helpers so the
two callers differ only in log event names.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.scraper.confidence import AMBIGUITY_DELTA, HIGH_CONFIDENCE, LOW_CONFIDENCE

if TYPE_CHECKING:
    from personalscraper.scraper._shared import ScrapeResult
    from personalscraper.scraper.confidence import MatchResult
    from personalscraper.scraper.decision_candidate import DecisionCandidate


def classify_decision_trigger(
    match: MatchResult | None,
    candidates: list[DecisionCandidate] | None = None,
) -> str | None:
    """Classify the decision trigger for a match result (scrape-arbiter DESIGN §4).

    Pure function — no side effects, no logging. The caller is responsible
    for emitting the appropriate log event.

    Three tiers:

    - ``"below_threshold"``: ``match`` is ``None`` or its confidence is
      below ``LOW_CONFIDENCE``. The item is skipped for auto-scrape but
      additively enqueued in the decision queue.
    - ``"mid_band"``: confidence is between ``LOW_CONFIDENCE`` (inclusive)
      and ``HIGH_CONFIDENCE`` (exclusive). Replaces the historical
      auto-accept — the item enters the decision queue for operator review
      (DESIGN §2 decision 2).
    - ``"ambiguous"``: confidence is >= ``HIGH_CONFIDENCE`` but the top two
      candidates are both >= ``LOW_CONFIDENCE`` and within
      ``AMBIGUITY_DELTA``. The auto-accepted match is ambiguous and
      enqueued for operator review.
    - ``None``: clean match — proceed with auto-scrape.

    Args:
        match: The best :class:`MatchResult` from the provider chain, or
            ``None`` if no provider returned a match.
        candidates: Top-N scored :class:`DecisionCandidate` list from the
            detailed match. Used for ambiguity detection. May be ``None``
            or empty.

    Returns:
        The trigger reason string, or ``None`` for a clean match.
    """
    if match is None or match.confidence < LOW_CONFIDENCE:
        return "below_threshold"
    if match.confidence < HIGH_CONFIDENCE:
        return "mid_band"
    if candidates and len(candidates) > 1:
        if candidates[1].score >= LOW_CONFIDENCE and candidates[0].score - candidates[1].score < AMBIGUITY_DELTA:
            return "ambiguous"
    return None


def apply_decision_to_result(
    result: ScrapeResult,
    match: MatchResult | None,
    candidates: list[DecisionCandidate] | None,
    trigger: str,
) -> None:
    """Apply a classified decision trigger to a :class:`ScrapeResult`.

    Mutates ``result`` in place:

    - ``"below_threshold"``: sets ``action="skipped_low_confidence"``,
      ``decision_candidates``, and ``decision_trigger``. Does **not** set
      ``result.match`` (the match is below threshold).
    - ``"mid_band"`` / ``"ambiguous"``: sets ``result.match``,
      ``action="queued_for_decision"``, ``decision_candidates``, and
      ``decision_trigger``.

    Args:
        result: The :class:`ScrapeResult` to mutate.
        match: The best :class:`MatchResult` (or ``None``, for
            ``below_threshold``).
        candidates: Top-N scored candidates for the decision queue. When
            falsy, ``result.decision_candidates`` is left unchanged.
        trigger: The trigger reason from :func:`classify_decision_trigger`.
    """
    if trigger == "below_threshold":
        result.action = "skipped_low_confidence"
    else:
        result.action = "queued_for_decision"
        result.match = match
    if candidates:
        result.decision_candidates = candidates
    result.decision_trigger = trigger

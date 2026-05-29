"""Ranking models re-export and engine for tracker results.

Implements DESIGN §6.3 / §8.5: the runtime ``rank()`` engine that scores
TrackerResult instances. The Pydantic config models (RankingCriterion,
ThresholdEntry, RankingBonuses, RankingConfig) now live in their config-layer
home ``personalscraper.conf.models._ranking`` (arch-cleanup-2 Phase 2,
Option A) and are re-exported below so runtime callers of
``personalscraper.api.tracker._ranking`` keep working unchanged. ByteSize-aware
threshold parsing lets config authors write ``at: "1GB"`` and get the integer
byte value at validation time.
"""

from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult

# Re-export Ranking* config models from their canonical config-layer home
# (arch-cleanup-2 Phase 2, Option A). Runtime callers of
# personalscraper.api.tracker._ranking keep working unchanged.
from personalscraper.conf.models._ranking import (  # noqa: F401
    RankingBonuses,
    RankingConfig,
    RankingCriterion,
    ThresholdEntry,
)


def rank(
    results: list[TrackerResult],
    ranking: RankingConfig,
) -> list[tuple[TrackerResult, int]]:
    """Score tracker results, apply bonuses, drop sub-min-seeders, sort desc.

    For each result:
      - Skip if ``seeders < ranking.min_seeders``.
      - For each criterion, look up the field on the result. If ``values``
        is set (categorical), score = values.get(str(value), 0). Otherwise
        if ``thresholds`` is set (numeric):
          - ``prefer = "higher"`` (default and ``None``): score = highest
            ``score`` of any threshold whose ``at`` is ≤ the numeric value
            (i.e. higher-is-better — bigger torrents score more).
          - ``prefer = "lower"``: score = highest ``score`` of any threshold
            whose ``at`` is ≥ the numeric value (i.e. lower-is-better — for
            criteria like episode-size where smaller is preferable).
        ByteSize values use ``.bytes``; other numerics are coerced via ``int()``.
      - Multiply by ``weight`` and add to total.
      - Add ``bonuses.freeleech`` / ``bonuses.silverleech`` if applicable.
    Returns a list of ``(result, score)`` sorted by score descending; ties
    keep input order (Python's sort is stable).

    Args:
        results: Tracker results to score.
        ranking: Ranking configuration.

    Returns:
        Sorted list of (result, score) pairs, highest score first.
    """
    scored: list[tuple[TrackerResult, int]] = []
    for r in results:
        if r.seeders < ranking.min_seeders:
            continue
        total = 0
        for c in ranking.criteria:
            v = getattr(r, c.field, None)
            if v is None:
                continue
            pts = 0
            if c.values is not None:
                pts = c.values.get(str(v), 0)
            elif c.thresholds:
                numeric = v.bytes if isinstance(v, ByteSize) else int(v)
                if c.prefer == "lower":
                    applicable = [t for t in c.thresholds if numeric <= t.at]
                else:
                    applicable = [t for t in c.thresholds if numeric >= t.at]
                pts = max((t.score for t in applicable), default=0)
            total += int(pts * c.weight)
        if r.is_freeleech:
            total += ranking.bonuses.freeleech
        if r.is_silverleech:
            total += ranking.bonuses.silverleech
        scored.append((r, total))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored

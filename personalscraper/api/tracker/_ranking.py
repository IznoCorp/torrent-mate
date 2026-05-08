"""Ranking models and engine for tracker results.

Implements DESIGN §6.3 / §8.5: RankingCriterion, ThresholdEntry, RankingBonuses,
RankingConfig (Pydantic models consumed by config validation) and the runtime
``rank()`` engine that scores TrackerResult instances. ByteSize-aware threshold
parsing lets config authors write ``at: "1GB"`` and get the integer byte value
at validation time.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult


class ThresholdEntry(BaseModel):
    """A size-or-count threshold with a score value.

    Attributes:
        at: Threshold value — int, float, or human-readable string like "1GB".
        score: Score awarded when the field meets this threshold.
    """

    at: int
    score: int

    @field_validator("at", mode="before")
    @classmethod
    def _parse_at(cls, v: object) -> int:
        if isinstance(v, str):
            return ByteSize.parse(v).bytes
        if isinstance(v, ByteSize):
            return v.bytes
        return int(v)  # type: ignore[call-overload,no-any-return]


class RankingCriterion(BaseModel):
    """A single ranking criterion for scoring tracker results.

    Attributes:
        field: The field to score (e.g. "resolution", "seeders", "size").
        weight: Multiplier applied to this criterion's score.
        values: Map of field value → score (for categorical fields).
        thresholds: Ordered thresholds for numeric fields.
        prefer: For threshold-based fields, whether higher or lower is better.
    """

    field: str
    weight: float = 1.0
    values: dict[str, int] | None = None
    thresholds: list[ThresholdEntry] | None = None
    prefer: Literal["higher", "lower"] | None = None


class RankingBonuses(BaseModel):
    """Bonus points for torrent properties.

    Attributes:
        freeleech: Bonus points for freeleech torrents.
        silverleech: Bonus points for silverleech (partial freeleech) torrents.
    """

    freeleech: int = 10
    silverleech: int = 5


class RankingConfig(BaseModel):
    """Full ranking configuration consumed by the ranking engine.

    Attributes:
        criteria: Ordered list of RankingCriterion to evaluate.
        bonuses: Bonus point configuration.
        min_seeders: Minimum seeders required for a result to be considered.
    """

    criteria: list[RankingCriterion] = Field(default_factory=list)
    bonuses: RankingBonuses = Field(default_factory=RankingBonuses)
    min_seeders: int = 1


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

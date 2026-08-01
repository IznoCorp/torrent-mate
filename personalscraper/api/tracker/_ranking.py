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
from personalscraper.conf.models._ranking import (
    RankingBonuses as RankingBonuses,
)
from personalscraper.conf.models._ranking import (
    RankingConfig as RankingConfig,
)
from personalscraper.conf.models._ranking import (
    RankingCriterion as RankingCriterion,
)
from personalscraper.conf.models._ranking import (
    ThresholdEntry as ThresholdEntry,
)


def rank(
    results: list[TrackerResult],
    ranking: RankingConfig,
    *,
    exclude_hashes: frozenset[str] = frozenset(),
    media_kind: str | None = None,
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

    When ``media_kind`` is set and ``ranking.size_thresholds_by_type`` has a
    non-empty entry for that kind, the ``size`` criterion uses those per-type
    thresholds instead of its own ``thresholds`` (the criterion's ``prefer``
    still applies).  When ``media_kind`` is ``None`` (default) or the kind has
    no by-type entry, the criterion's own thresholds are used — byte-identical
    to the current behaviour.

    Returns a list of ``(result, score)`` sorted by score descending; ties
    keep input order (Python's sort is stable).

    Args:
        results: Tracker results to score.
        ranking: Ranking configuration.
        exclude_hashes: Lowercase info-hashes to drop before scoring — releases
            already grabbed-and-failed for this item (reswitch #342). Empty by
            default, so the ordinary grab is unchanged.
        media_kind: The wanted item's kind (``"movie"`` or ``"episode"``) when
            the grab context knows it, so per-type size thresholds can be applied.
            ``None`` (default) keeps the current byte-identical behaviour.

    Returns:
        Sorted list of (result, score) pairs, highest score first.
    """
    # Pre-casefold each categorical criterion's value map ONCE. A release token
    # carries the title's own casing (``dts-hd`` / ``TRUEHD`` / ``X265``), while
    # only ``language`` is normalized at parse time — so a case-sensitive lookup
    # silently scored 0 for a differently-cased token (e.g. a ``dts-hd`` release
    # under an ``audio: {"DTS-HD": …}`` criterion). Matching on the casefolded key
    # makes the score depend on the token's meaning, not its capitalization.
    cf_values: list[dict[str, int] | None] = [
        {k.casefold(): val for k, val in c.values.items()} if c.values is not None else None for c in ranking.criteria
    ]
    scored: list[tuple[TrackerResult, int]] = []
    for r in results:
        if r.seeders < ranking.min_seeders:
            continue
        # reswitch #342: never re-pick a release already grabbed-and-failed for
        # this item (dead swarm / broken). The exclusion set is lowercase hex;
        # compare case-insensitively so a differently-cased hash still matches.
        if r.info_hash is not None and r.info_hash.lower() in exclude_hashes:
            continue
        total = 0
        for c, cf in zip(ranking.criteria, cf_values, strict=True):
            v = getattr(r, c.field, None)
            if v is None:
                continue
            pts = 0
            if cf is not None:
                pts = cf.get(str(v).casefold(), 0)
            elif c.thresholds:
                # Per-media-type size thresholds override the generic size
                # criterion's thresholds when the grab context knows the wanted
                # kind (#376). The criterion's ``prefer`` still applies.
                thresholds = c.thresholds
                if c.field == "size" and media_kind is not None and ranking.size_thresholds_by_type is not None:
                    by_type = ranking.size_thresholds_by_type.get(media_kind)
                    if by_type:
                        thresholds = by_type
                numeric = v.bytes if isinstance(v, ByteSize) else int(v)
                if c.prefer == "lower":
                    applicable = [t for t in thresholds if numeric <= t.at]
                else:
                    applicable = [t for t in thresholds if numeric >= t.at]
                pts = max((t.score for t in applicable), default=0)
            total += int(pts * c.weight)
        if r.is_freeleech:
            total += ranking.bonuses.freeleech
        if r.is_silverleech:
            total += ranking.bonuses.silverleech
        scored.append((r, total))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored

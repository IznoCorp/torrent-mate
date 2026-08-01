"""Ranking config models — config-layer home (arch-cleanup-2 Phase 2, Option A).

These Pydantic models are parsed from config files (``api_config.json5``
``ranking`` section). They live here in ``conf/`` because they are
configuration-layer objects, not API-transport objects.

``personalscraper.api.tracker._ranking`` re-exports them for backward
compatibility with existing runtime consumers of the tracker package.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Intentional, documented upward dependency: this config model parses byte-size
# strings (e.g. "1GB") at validation time and reuses the canonical ByteSize
# parser from api/_units (arch-cleanup-2 Phase 2 plan, Option A).
from personalscraper.api._units import ByteSize  # layering: allow

#: Valid keys for ``size_thresholds_by_type`` — "season" is forward-provisioned
#: for season-kind wanted items that will land with the whole-season feature.
_VALID_SIZE_THRESHOLD_KINDS: frozenset[str] = frozenset({"movie", "season", "episode"})


class ThresholdEntry(BaseModel):
    """A size-or-count threshold with a score value.

    Attributes:
        at: Threshold value — int, float, or human-readable string like ``"1GB"``.
        score: Score awarded when the field meets this threshold.
    """

    at: int
    score: int

    @field_validator("at", mode="before")
    @classmethod
    def _parse_at(cls, v: object) -> int:
        """Coerce string byte-size values (e.g. ``'1GB'``) to integer bytes.

        Args:
            v: Raw value from config (str, ByteSize, or int-like).

        Returns:
            Integer byte count.
        """
        if isinstance(v, str):
            return ByteSize.parse(v).bytes
        if isinstance(v, ByteSize):
            return v.bytes
        return int(v)  # type: ignore[call-overload,no-any-return]


class RankingCriterion(BaseModel):
    """A single ranking criterion for scoring tracker results.

    Attributes:
        field: The field to score (e.g. ``"resolution"``, ``"seeders"``).
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
        criteria: Ordered list of :class:`RankingCriterion` to evaluate.
        bonuses: Bonus point configuration.
        min_seeders: Minimum seeders required for a result to be considered.
        size_thresholds_by_type: Optional per-media-type size thresholds that
            override the generic ``size`` criterion's ``thresholds`` when the
            grab context knows the wanted item's kind.  Valid keys are
            ``"movie"``, ``"episode"``, and ``"season"`` (forward-provisioned
            for season-kind wanted items that will land with the whole-season
            feature).  Empty lists are allowed (no override for that kind).
            When ``None`` (default) or when a kind has no entry (or an empty
            list), ``rank()`` falls back to the criterion's own ``thresholds``
            — byte-identical to the current behavior.
    """

    criteria: list[RankingCriterion] = Field(default_factory=list)
    bonuses: RankingBonuses = Field(default_factory=RankingBonuses)
    min_seeders: int = 1
    size_thresholds_by_type: dict[str, list[ThresholdEntry]] | None = None

    @field_validator("size_thresholds_by_type")
    @classmethod
    def _validate_size_thresholds_by_type(
        cls, v: dict[str, list[ThresholdEntry]] | None
    ) -> dict[str, list[ThresholdEntry]] | None:
        """Reject unknown keys in ``size_thresholds_by_type``.

        Args:
            v: The raw value from config, or ``None``.

        Returns:
            The value unchanged if valid.

        Raises:
            ValueError: If any key is not one of ``{"movie", "season", "episode"}``.
        """
        if v is None:
            return v
        unknown = set(v.keys()) - _VALID_SIZE_THRESHOLD_KINDS
        if unknown:
            raise ValueError(
                f"Unknown key(s) in size_thresholds_by_type: {sorted(unknown)}. "
                f"Valid keys are: {sorted(_VALID_SIZE_THRESHOLD_KINDS)}"
            )
        return v

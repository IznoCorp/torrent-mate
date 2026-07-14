"""Typed RP3a vocabulary — Resolution, QualityProfile, SourceCriteria.

Frozen, core+stdlib-pure value objects.  JSON codec helpers live here
(mirrors the style of ``store.py``'s ``_media_ref_to_json``) so
``store.py`` stays under the 1000-LOC module ceiling.

Import direction: stdlib only — never api/, indexer/, scraper/, or triage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.cadence import Cadence
    from personalscraper.conf.models.acquire import CadenceConfig

log = get_logger("acquire.desired")


class Resolution(IntEnum):
    """Ordered resolution tiers.

    ``>=`` comparisons are numeric — never string-compare resolution tokens.
    ``R4K`` / ``RUHD`` / ``R2160P`` all fold to the same ordinal (2160)
    so any of the three names in a result title ranks identically.
    """

    UNKNOWN = 0
    R480P = 480
    R720P = 720
    R1080P = 1080
    R2160P = 2160
    # Aliases — same ordinal value as R2160P
    R4K = 2160
    RUHD = 2160

    @classmethod
    def from_token(cls, s: str | None) -> Resolution:
        """Parse a lowercase resolution token into an ordered tier.

        Folds ``4k`` / ``uhd`` / ``2160p`` → ``R2160P`` (via the most
        specific alias) so all 2160-class tokens rank identically.

        Args:
            s: Lowercase token from a tracker result title
                (e.g. ``"2160p"``, ``"1080p"``, ``"720p"``, ``"480p"``,
                ``"4k"``, ``"uhd"``).  ``None`` or unrecognised tokens
                return ``UNKNOWN``.

        Returns:
            The matching :class:`Resolution` tier.
        """
        if s is None:
            return cls.UNKNOWN
        token = s.strip().lower()
        if token in ("2160p",):
            return cls.R2160P
        if token in ("1080p",):
            return cls.R1080P
        if token in ("720p",):
            return cls.R720P
        if token in ("480p",):
            return cls.R480P
        if token in ("4k",):
            return cls.R4K
        if token in ("uhd",):
            return cls.RUHD
        return cls.UNKNOWN


@dataclass(frozen=True, kw_only=True)
class QualityProfile:
    """Per-series quality policy decoded from ``FollowedSeries.quality_profile_json``.

    Quality/language defaults are **permissive**: ``min_resolution=None`` means
    no floor (hard-filter stage is a no-op); ``required_audio=frozenset()`` means
    any language passes.  A French-only or ≥1080p policy is an explicit
    per-profile opt-in set by Follow D4 — not a global default.

    The one deliberately non-permissive default is ``exclude_3d=True``: a
    stereoscopic-3D encode (Side-By-Side / Over-Under) is **unwatchable** on a
    normal 2D setup — dropping it is a correctness floor, not a taste preference,
    so it defaults on.  An operator with a 3D rig opts back in per-series by
    storing ``exclude_3d=False``.

    Attributes:
        min_resolution: Minimum acceptable resolution tier, or ``None`` (no
            floor — fail-open, passes all resolutions including None-resolution
            REMUX/BluRay sources that the ranking engine soft-scores).
        required_audio: Set of required audio language markers
            (``{"VF", "VOSTFR", "VO"}`` tiers).  Empty = no language filter.
        allowed_codecs: Optional codec allow-list (empty = allow all).
        min_size: Minimum file size in bytes, or ``None`` (no lower bound).
        max_size: Maximum file size in bytes, or ``None`` (no upper bound).
        require_known_resolution: When ``True``, fail-closed on unparseable
            resolution.  Default ``False`` (fail-open) — an unparseable
            resolution is usually a naming-style gap (REMUX/COMPLETE.BLURAY)
            that the ranking engine soft-scores.
        exclude_3d: When ``True`` (default), drop stereoscopic-3D releases
            (``3D``, ``Full-SBS``, ``Half-SBS``, ``Over-Under`` tokens) — they
            are unwatchable on a 2D setup. Set ``False`` for a 3D-capable rig.
    """

    min_resolution: Resolution | None = None
    required_audio: frozenset[str] = field(default_factory=frozenset)
    allowed_codecs: frozenset[str] = field(default_factory=frozenset)
    min_size: int | None = None
    max_size: int | None = None
    require_known_resolution: bool = False
    exclude_3d: bool = True


@dataclass(frozen=True, kw_only=True)
class SourceCriteria:
    """Per-item source overrides decoded from ``WantedItem.criteria_json``.

    **Decode-only at RP5b** — no live producer until Follow D4.  The
    effective-profile precedence (series default ← item override) ships as
    a round-trip unit test, but is not an exercised live path yet.

    Attributes:
        preferred_resolution: Item-level resolution preference override, or
            ``None`` (inherit from ``QualityProfile``).
        required_audio: Item-level audio requirement override.  Empty =
            inherit from ``QualityProfile``.
    """

    preferred_resolution: Resolution | None = None
    required_audio: frozenset[str] = field(default_factory=frozenset)


# ---------------------------------------------------------------------------
# JSON helpers (mirrors _media_ref_to_json style in store.py)
# ---------------------------------------------------------------------------


def quality_profile_to_json(p: QualityProfile) -> str:
    """Serialize a :class:`QualityProfile` to a compact JSON string.

    Args:
        p: The profile to serialize.

    Returns:
        JSON string suitable for storage in ``quality_profile_json`` column.
    """
    return json.dumps(
        {
            "min_resolution": p.min_resolution.value if p.min_resolution is not None else None,
            "required_audio": sorted(p.required_audio),
            "allowed_codecs": sorted(p.allowed_codecs),
            "min_size": p.min_size,
            "max_size": p.max_size,
            "require_known_resolution": p.require_known_resolution,
            "exclude_3d": p.exclude_3d,
        }
    )


def quality_profile_from_json(blob: str | None) -> QualityProfile:
    """Deserialize a :class:`QualityProfile` from its JSON string.

    A ``None`` or empty blob decodes to the **permissive default**
    profile (no floor, no language filter) — this is load-bearing:
    a NULL column means "no policy configured yet".

    Args:
        blob: JSON string produced by :func:`quality_profile_to_json`,
            or ``None`` for a null database column.

    Returns:
        The reconstructed :class:`QualityProfile`.
    """
    if blob is None:
        return QualityProfile()
    data = json.loads(blob)
    min_res_val = data.get("min_resolution")
    return QualityProfile(
        min_resolution=Resolution(min_res_val) if min_res_val is not None else None,
        required_audio=frozenset(data.get("required_audio", [])),
        allowed_codecs=frozenset(data.get("allowed_codecs", [])),
        min_size=data.get("min_size"),
        max_size=data.get("max_size"),
        require_known_resolution=bool(data.get("require_known_resolution", False)),
        # Absent key → True: a profile stored before the 3D filter existed still
        # gets the (correctness-floor) exclusion.
        exclude_3d=bool(data.get("exclude_3d", True)),
    )


def source_criteria_to_json(c: SourceCriteria) -> str:
    """Serialize a :class:`SourceCriteria` to a compact JSON string.

    Args:
        c: The criteria to serialize.

    Returns:
        JSON string suitable for storage in ``criteria_json`` column.
    """
    return json.dumps(
        {
            "preferred_resolution": c.preferred_resolution.value if c.preferred_resolution is not None else None,
            "required_audio": sorted(c.required_audio),
        }
    )


def source_criteria_from_json(blob: str | None) -> SourceCriteria:
    """Deserialize a :class:`SourceCriteria` from its JSON string.

    A ``None`` or empty blob decodes to the default (all-None) criteria.

    Args:
        blob: JSON string produced by :func:`source_criteria_to_json`,
            or ``None`` for a null database column.

    Returns:
        The reconstructed :class:`SourceCriteria`.
    """
    if blob is None:
        return SourceCriteria()
    data = json.loads(blob)
    pref_res_val = data.get("preferred_resolution")
    return SourceCriteria(
        preferred_resolution=Resolution(pref_res_val) if pref_res_val is not None else None,
        required_audio=frozenset(data.get("required_audio", [])),
    )


def cadence_to_json(cadence: Cadence) -> str:
    """Serialize a :class:`~personalscraper.acquire.cadence.Cadence` to JSON.

    Args:
        cadence: The cadence to serialize.

    Returns:
        Compact JSON string for storage in ``FollowedSeries.cadence_json``.
    """
    return json.dumps(
        {
            "tiers": [{"max_age_s": t.max_age_s, "interval_s": t.interval_s} for t in cadence.tiers],
            "cutoff_s": cadence.cutoff_s,
        }
    )


def cadence_from_json(blob: str | None) -> Cadence | None:
    """Deserialize a :class:`~personalscraper.acquire.cadence.Cadence` from JSON.

    A ``None`` blob means "use the global default" — callers must supply the
    fallback via :func:`effective_cadence`.

    Fail-soft on a malformed or semantically-invalid blob: a parse error,
    missing key, wrong type, or a value that violates a :class:`Cadence`
    invariant (caught from ``__post_init__``'s ``ValueError``) is logged at
    ``warning`` and decodes to ``None`` — the caller then falls back to the
    global default via :func:`effective_cadence`, so a corrupt
    ``cadence_json`` column never crashes a poll.

    Args:
        blob: JSON string produced by :func:`cadence_to_json`, or ``None``.

    Returns:
        The reconstructed :class:`Cadence`, ``None`` if blob is ``None``, or
        ``None`` if the blob is malformed or semantically invalid.
    """
    if blob is None:
        return None
    from personalscraper.acquire.cadence import Cadence, CadenceTier  # noqa: PLC0415

    try:
        data = json.loads(blob)
        return Cadence(
            tiers=tuple(CadenceTier(max_age_s=t["max_age_s"], interval_s=t["interval_s"]) for t in data["tiers"]),
            cutoff_s=data["cutoff_s"],
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        # Corrupt cadence_json must never crash a poll: fail-soft to the global
        # default. __post_init__ raises ValueError for semantically-invalid
        # blobs (empty tiers, negative durations, cutoff < last tier) — caught here.
        log.warning("acquire.cadence.bad_cadence_json", error=str(exc))
        return None


def cadence_from_config(cfg: CadenceConfig) -> Cadence:
    """Convert a :class:`~personalscraper.conf.models.acquire.CadenceConfig` to a :class:`Cadence` VO.

    Unit bridge: hours/minutes/days (config) → seconds (VO).

    Args:
        cfg: Pydantic config model loaded from ``config/acquire.json5``.

    Returns:
        A :class:`Cadence` with all durations in seconds.
    """
    from personalscraper.acquire.cadence import Cadence, CadenceTier  # noqa: PLC0415

    return Cadence(
        tiers=tuple(
            CadenceTier(
                max_age_s=t.max_age_hours * 3600,
                interval_s=t.interval_minutes * 60,
            )
            for t in cfg.tiers
        ),
        cutoff_s=cfg.cutoff_days * 24 * 3600,
    )


def effective_cadence(series_override: Cadence | None, global_default: Cadence) -> Cadence:
    """Return the effective cadence: series override if present, else global default.

    Precedence is whole-object (no field-by-field merge): the per-series
    ``cadence_json`` encodes a complete :class:`Cadence`. An absent
    (``None``) override means "use the global default verbatim".

    Args:
        series_override: Per-series cadence decoded from
            ``FollowedSeries.cadence_json``, or ``None``.
        global_default: Cadence built from ``config.acquire.cadence``.

    Returns:
        The effective :class:`Cadence` to use.
    """
    return series_override if series_override is not None else global_default


def effective_quality(series: QualityProfile, item: SourceCriteria) -> QualityProfile:
    """Merge series-level profile with per-item criteria (item overrides series).

    **RP5b: decode-only** — no live producer until Follow D4.  This helper is
    shipped so the precedence is tested, not speculative.

    Item fields override series fields only when explicitly set (non-None /
    non-empty): a ``SourceCriteria()`` with all defaults leaves the series
    profile unchanged.

    Args:
        series: Series-level :class:`QualityProfile` (from
            ``FollowedSeries.quality_profile_json``).
        item: Per-item :class:`SourceCriteria` override (from
            ``WantedItem.criteria_json``).

    Returns:
        Effective :class:`QualityProfile` to use for the grab attempt.
    """
    min_res = item.preferred_resolution if item.preferred_resolution is not None else series.min_resolution
    audio = item.required_audio if item.required_audio else series.required_audio
    return QualityProfile(
        min_resolution=min_res,
        required_audio=audio,
        allowed_codecs=series.allowed_codecs,
        min_size=series.min_size,
        max_size=series.max_size,
        require_known_resolution=series.require_known_resolution,
        exclude_3d=series.exclude_3d,
    )


__all__ = [
    "QualityProfile",
    "Resolution",
    "SourceCriteria",
    "cadence_from_config",
    "cadence_from_json",
    "cadence_to_json",
    "effective_cadence",
    "effective_quality",
    "quality_profile_from_json",
    "quality_profile_to_json",
    "source_criteria_from_json",
    "source_criteria_to_json",
]

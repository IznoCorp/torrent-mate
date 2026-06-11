"""Tests for acquire/desired.py — Resolution, QualityProfile, SourceCriteria."""

from __future__ import annotations

from personalscraper.acquire.desired import (
    QualityProfile,
    Resolution,
    SourceCriteria,
    effective_quality,
    quality_profile_from_json,
    quality_profile_to_json,
    source_criteria_from_json,
    source_criteria_to_json,
)

# ---------------------------------------------------------------------------
# Task 1 — Resolution
# ---------------------------------------------------------------------------


def test_resolution_ordering_numeric() -> None:
    """Resolution tiers are ordered so ``>=`` is numeric, never string compare."""
    assert Resolution.R480P < Resolution.R720P < Resolution.R1080P
    assert Resolution.R2160P > Resolution.R1080P


def test_resolution_4k_uhd_2160p_fold() -> None:
    """4k / uhd / 2160p must all map to the same ordinal tier."""
    assert Resolution.R4K == Resolution.R2160P
    assert Resolution.R4K == Resolution.RUHD
    assert Resolution.R2160P == Resolution.RUHD


def test_resolution_from_token_known() -> None:
    """from_token maps lowercase resolution tokens to correct tiers."""
    assert Resolution.from_token("2160p") == Resolution.R2160P
    assert Resolution.from_token("1080p") == Resolution.R1080P
    assert Resolution.from_token("720p") == Resolution.R720P
    assert Resolution.from_token("480p") == Resolution.R480P


def test_resolution_from_token_aliases() -> None:
    """from_token folds 4k and uhd to the 2160 tier."""
    r4k = Resolution.from_token("4k")
    ruhd = Resolution.from_token("uhd")
    r2160 = Resolution.from_token("2160p")
    # All three tokens share the same ordinal (2160), so they compare equal.
    assert r4k == ruhd == r2160


def test_resolution_from_token_none_unknown() -> None:
    """None → UNKNOWN."""
    assert Resolution.from_token(None) == Resolution.UNKNOWN


def test_resolution_from_token_garbage_unknown() -> None:
    """Unrecognised tokens → UNKNOWN."""
    assert Resolution.from_token("garbage") == Resolution.UNKNOWN
    assert Resolution.from_token("") == Resolution.UNKNOWN
    assert Resolution.from_token("8k") == Resolution.UNKNOWN


def test_resolution_unknown_is_floor() -> None:
    """UNKNOWN (0) is below all real tiers."""
    assert Resolution.UNKNOWN < Resolution.R480P
    assert Resolution.UNKNOWN < Resolution.R720P
    assert Resolution.UNKNOWN < Resolution.R1080P
    assert Resolution.UNKNOWN < Resolution.R2160P


# ---------------------------------------------------------------------------
# Task 2 — QualityProfile
# ---------------------------------------------------------------------------


def test_quality_profile_permissive_defaults() -> None:
    """Default profile: no resolution floor, no audio requirement."""
    p = QualityProfile()
    assert p.min_resolution is None
    assert p.required_audio == frozenset()
    assert p.allowed_codecs == frozenset()
    assert p.min_size is None
    assert p.max_size is None
    assert p.require_known_resolution is False


def test_quality_profile_explicit_floor() -> None:
    """Explicit min_resolution and required_audio are stored correctly."""
    p = QualityProfile(
        min_resolution=Resolution.R1080P,
        required_audio=frozenset({"VF", "VOSTFR"}),
    )
    assert p.min_resolution == Resolution.R1080P
    assert "VF" in p.required_audio


# ---------------------------------------------------------------------------
# Task 3 — SourceCriteria
# ---------------------------------------------------------------------------


def test_source_criteria_defaults_all_none() -> None:
    """SourceCriteria is decode-only at RP5b: no live producer until Follow D4."""
    c = SourceCriteria()
    assert c.preferred_resolution is None
    assert c.required_audio == frozenset()


# ---------------------------------------------------------------------------
# Task 4 — JSON codecs
# ---------------------------------------------------------------------------


def test_quality_profile_json_roundtrip_permissive() -> None:
    """Default QualityProfile round-trips through JSON unchanged."""
    p = QualityProfile()
    assert quality_profile_from_json(quality_profile_to_json(p)) == p


def test_quality_profile_json_roundtrip_explicit() -> None:
    """Explicit profile with min_resolution + required_audio round-trips correctly."""
    p = QualityProfile(
        min_resolution=Resolution.R1080P,
        required_audio=frozenset({"VF", "VOSTFR"}),
    )
    restored = quality_profile_from_json(quality_profile_to_json(p))
    assert restored.min_resolution == Resolution.R1080P
    assert restored.required_audio == frozenset({"VF", "VOSTFR"})


def test_source_criteria_json_roundtrip() -> None:
    """SourceCriteria with explicit fields round-trips through JSON."""
    c = SourceCriteria(
        preferred_resolution=Resolution.R720P,
        required_audio=frozenset({"VO"}),
    )
    assert source_criteria_from_json(source_criteria_to_json(c)) == c


def test_source_criteria_json_roundtrip_empty() -> None:
    """Default (empty) SourceCriteria round-trips through JSON unchanged."""
    c = SourceCriteria()
    assert source_criteria_from_json(source_criteria_to_json(c)) == c


def test_quality_profile_null_column_default() -> None:
    """A NULL column decodes to the permissive default profile (load-bearing)."""
    p = quality_profile_from_json(None)
    assert p.min_resolution is None
    assert p.required_audio == frozenset()
    assert p.allowed_codecs == frozenset()
    assert p.min_size is None
    assert p.max_size is None
    assert p.require_known_resolution is False


def test_source_criteria_null_column_default() -> None:
    """A NULL criteria_json decodes to the all-default SourceCriteria."""
    c = source_criteria_from_json(None)
    assert c.preferred_resolution is None
    assert c.required_audio == frozenset()


def test_quality_profile_json_roundtrip_require_known_resolution() -> None:
    """require_known_resolution=True round-trips correctly."""
    p = QualityProfile(require_known_resolution=True, min_resolution=Resolution.R1080P)
    restored = quality_profile_from_json(quality_profile_to_json(p))
    assert restored.require_known_resolution is True
    assert restored.min_resolution == Resolution.R1080P


# ---------------------------------------------------------------------------
# Task 5 — effective_quality precedence
# ---------------------------------------------------------------------------


def test_effective_quality_series_default_when_no_override() -> None:
    """Series profile is preserved when item has no overrides."""
    series_profile = QualityProfile(min_resolution=Resolution.R1080P)
    item_criteria = SourceCriteria()  # no override
    result = effective_quality(series_profile, item_criteria)
    assert result.min_resolution == Resolution.R1080P


def test_effective_quality_item_overrides_resolution() -> None:
    """Item preferred_resolution overrides series min_resolution."""
    series_profile = QualityProfile(min_resolution=Resolution.R1080P)
    item_criteria = SourceCriteria(preferred_resolution=Resolution.R720P)
    result = effective_quality(series_profile, item_criteria)
    # item preferred_resolution overrides series min_resolution
    assert result.min_resolution == Resolution.R720P


def test_effective_quality_item_overrides_audio() -> None:
    """Item required_audio overrides series required_audio."""
    series_profile = QualityProfile(required_audio=frozenset({"VF"}))
    item_criteria = SourceCriteria(required_audio=frozenset({"VO"}))
    result = effective_quality(series_profile, item_criteria)
    assert result.required_audio == frozenset({"VO"})


def test_effective_quality_series_audio_preserved_when_no_item_override() -> None:
    """Series audio is preserved when item has no audio override."""
    series_profile = QualityProfile(required_audio=frozenset({"VF", "VOSTFR"}))
    item_criteria = SourceCriteria()  # empty = no override
    result = effective_quality(series_profile, item_criteria)
    assert result.required_audio == frozenset({"VF", "VOSTFR"})


def test_effective_quality_series_nonne_fields_preserved() -> None:
    """Item overrides ONLY resolution + audio; other fields stay from series."""
    series_profile = QualityProfile(
        min_resolution=Resolution.R1080P,
        allowed_codecs=frozenset({"x264", "x265"}),
        min_size=100_000_000,
        max_size=10_000_000_000,
        require_known_resolution=True,
    )
    item_criteria = SourceCriteria(preferred_resolution=Resolution.R2160P)
    result = effective_quality(series_profile, item_criteria)
    assert result.min_resolution == Resolution.R2160P  # overridden
    assert result.allowed_codecs == frozenset({"x264", "x265"})  # preserved
    assert result.min_size == 100_000_000  # preserved
    assert result.max_size == 10_000_000_000  # preserved
    assert result.require_known_resolution is True  # preserved


def test_effective_quality_empty_item_no_op() -> None:
    """A fully-default SourceCriteria leaves the series profile unchanged."""
    series_profile = QualityProfile(
        min_resolution=Resolution.R720P,
        required_audio=frozenset({"VOSTFR"}),
        require_known_resolution=True,
    )
    result = effective_quality(series_profile, SourceCriteria())
    assert result == series_profile

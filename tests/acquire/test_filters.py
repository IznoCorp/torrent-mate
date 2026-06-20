r"""Tests for the hard-filter stage (acquire/_filters.py).

Non-vacuous: covers fail-open None-resolution, resolution floor enforcement,
audio regex anchoring (\b guard), and profile no-op when defaults are permissive.
"""

from __future__ import annotations

from personalscraper.acquire._filters import apply_hard_filters
from personalscraper.acquire.desired import QualityProfile, Resolution
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.core.identity import MediaRef


def _result(
    title: str,
    resolution: str | None = None,
    audio: str | None = None,
    seeders: int = 10,
    tmdb_id: int | None = None,
) -> TrackerResult:
    return TrackerResult(
        provider="lacale",
        tracker_id="t1",
        title=title,
        size=ByteSize(1_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution=resolution,
        audio=audio,
        tmdb_id=tmdb_id,
    )


# ---------------------------------------------------------------------------
# Resolution filter
# ---------------------------------------------------------------------------


def test_resolution_floor_drops_below_minimum() -> None:
    """Resolution below min_resolution is dropped; at-or-above passes."""
    profile = QualityProfile(min_resolution=Resolution.R1080P)
    results = [
        _result("Movie 720p", resolution="720p"),
        _result("Movie 1080p", resolution="1080p"),
        _result("Movie 2160p", resolution="2160p"),
    ]
    survivors = apply_hard_filters(results, profile)
    resolutions = [r.resolution for r in survivors]
    assert "720p" not in resolutions
    assert "1080p" in resolutions
    assert "2160p" in resolutions


def test_resolution_none_fails_open() -> None:
    """LOAD-BEARING: None-resolution (REMUX, COMPLETE.BLURAY) must pass the filter."""
    profile = QualityProfile(min_resolution=Resolution.R1080P)
    results = [
        _result("Movie.COMPLETE.BLURAY.DTS-GRP", resolution=None),
        _result("Movie.REMUX.DTS-GRP", resolution=None),
        _result("Movie.720p", resolution="720p"),
    ]
    survivors = apply_hard_filters(results, profile)
    # None-resolution passes, 720p is dropped
    assert all(r.resolution is None for r in survivors)
    assert len(survivors) == 2


def test_resolution_unrecognised_fails_open_by_default() -> None:
    """LOAD-BEARING: unparseable resolution (WEB-DL, REMUX token) PASSES by default."""
    profile = QualityProfile(min_resolution=Resolution.R1080P)
    results = [
        _result("Movie.2010.WEB-DL.GRP", resolution="web-dl"),
        _result("Movie.2010.x264-GRP", resolution="x264"),
    ]
    survivors = apply_hard_filters(results, profile)
    # UNKNOWN resolution tokens pass (fail-open)
    assert len(survivors) == 2


def test_resolution_unrecognised_fails_when_require_known_resolution() -> None:
    """require_known_resolution=True → UNKNOWN-resolution is DROPPED (opt-in fail-closed)."""
    profile = QualityProfile(
        min_resolution=Resolution.R1080P,
        require_known_resolution=True,
    )
    results = [
        _result("Movie.2010.REMUX.DTS-GRP", resolution="remux"),
        _result("Movie.2010.1080p.BluRay", resolution="1080p"),
    ]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 1
    assert survivors[0].resolution == "1080p"


def test_require_known_resolution_drops_absent_field() -> None:
    """require_known_resolution=True → None-resolution is DROPPED (absent field, not UNKNOWN)."""
    profile_strict = QualityProfile(
        min_resolution=Resolution.R1080P,
        require_known_resolution=True,
    )
    profile_default = QualityProfile(
        min_resolution=Resolution.R1080P,
        require_known_resolution=False,
    )
    none_result = _result("Movie.COMPLETE.BLURAY.NoResTag-GRP", resolution=None)
    known_result = _result("Movie.1080p.BluRay", resolution="1080p")

    # require_known_resolution=True: None-resolution is dropped (fail-closed).
    survivors_strict = apply_hard_filters([none_result, known_result], profile_strict)
    assert len(survivors_strict) == 1
    assert survivors_strict[0].resolution == "1080p"

    # require_known_resolution=False (default): None-resolution passes (fail-open).
    survivors_default = apply_hard_filters([none_result], profile_default)
    assert len(survivors_default) == 1, "None-resolution must pass when require_known_resolution=False"


def test_resolution_filter_noop_when_profile_min_is_none() -> None:
    """Permissive default: min_resolution=None → filter is a no-op."""
    profile = QualityProfile()  # min_resolution=None
    results = [
        _result("Movie 480p", resolution="480p"),
        _result("Movie 720p", resolution="720p"),
        _result("Movie REMUX", resolution=None),
    ]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 3


def test_resolution_4k_uhd_aliases_pass_2160_floor() -> None:
    """4k and uhd tokens are aliased to 2160p tier."""
    profile = QualityProfile(min_resolution=Resolution.R2160P)
    results = [
        _result("Movie 4K HDR", resolution="4k"),
        _result("Movie UHD BluRay", resolution="uhd"),
        _result("Movie 2160p", resolution="2160p"),
        _result("Movie 1080p", resolution="1080p"),
    ]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 3  # 4k, uhd, 2160p pass; 1080p dropped


# ---------------------------------------------------------------------------
# Audio language filter
# ---------------------------------------------------------------------------


def test_audio_filter_noop_when_required_audio_empty() -> None:
    """Permissive default: required_audio=frozenset() → no-op."""
    profile = QualityProfile()  # required_audio=frozenset()
    results = [
        _result("Movie 2020 VO 1080p"),
        _result("Movie 2020 1080p"),  # no language marker
        _result("Movie 2020 VOSTFR 1080p"),
    ]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 3


def test_audio_filter_drops_no_marker_title_when_vf_required() -> None:
    """Title with no language marker is dropped when VF is required."""
    profile = QualityProfile(required_audio=frozenset({"VF"}))
    results = [
        _result("Movie 2020 MULTi VFF 1080p BluRay"),  # VFF → VF
        _result("Movie 2020 1080p BluRay"),  # no marker → dropped
        _result("Movie 2020 TRUEFRENCH 1080p"),  # TRUEFRENCH → VF
    ]
    survivors = apply_hard_filters(results, profile)
    titles = [r.title for r in survivors]
    assert "Movie 2020 1080p BluRay" not in titles
    assert len(survivors) == 2


def test_audio_filter_multi_title_passes_vf_requirement() -> None:
    """MULTi title passes when VF required (MULTi always includes French)."""
    profile = QualityProfile(required_audio=frozenset({"VF"}))
    results = [_result("Inception 2010 MULTi VFF 2160p BluRay x265 DTS 5.1 - QTZ")]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 1


def test_audio_filter_passes_audio_dts_title_multi() -> None:
    """LOAD-BEARING (DESIGN §11-h): result.audio='DTS' with MULTi title passes VF filter."""
    profile = QualityProfile(required_audio=frozenset({"VF"}))
    # audio field is 'DTS' (codec-only) — language comes from title 'MULTi'
    result = _result("Movie 2020 MULTi 1080p BluRay", audio="DTS")
    survivors = apply_hard_filters([result], profile)
    assert len(survivors) == 1, "MULTi title must pass VF filter regardless of audio='DTS'"


def test_audio_filter_vostfr_kept_when_vostfr_required() -> None:
    """VOSTFR-title passes when required_audio={VOSTFR}; VF-title is dropped."""
    profile = QualityProfile(required_audio=frozenset({"VOSTFR"}))
    results = [
        _result("Movie 2020 VOSTFR 1080p"),
        _result("Movie 2020 VF 1080p"),  # VF but VOSTFR required
    ]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 1
    assert "VOSTFR" in survivors[0].title


def test_audio_filter_vf_required_drops_vo_only_title() -> None:
    """Title with VO only is dropped when VF is required."""
    profile = QualityProfile(required_audio=frozenset({"VF"}))
    results = [_result("Movie 2020 VO 1080p")]
    survivors = apply_hard_filters(results, profile)
    assert len(survivors) == 0


# ---------------------------------------------------------------------------
# \\b boundary guard (LOAD-BEARING)
# ---------------------------------------------------------------------------


def test_audio_regex_boundary_multilingual_does_not_match() -> None:
    """LOAD-BEARING (DESIGN §11-i): MULTILINGUAL must NOT match the MULTI pattern."""
    from personalscraper.acquire._filters import _parse_audio_languages

    langs = _parse_audio_languages("Movie 2020 MULTILINGUAL 1080p BluRay")
    assert "VF" not in langs, "MULTILINGUAL must not trigger the MULTI→VF match"


def test_audio_regex_boundary_convostfr_does_not_match() -> None:
    """LOAD-BEARING (DESIGN §11-i): ConVOSTed must NOT match the VOSTFR pattern."""
    from personalscraper.acquire._filters import _parse_audio_languages

    langs = _parse_audio_languages("Movie 2020 ConVOSTed 1080p BluRay")
    assert "VOSTFR" not in langs, "ConVOSTed must not trigger the VOSTFR match"


def test_audio_regex_boundary_convost_does_not_match() -> None:
    """ConVOSTed must NOT match the VOST pattern."""
    from personalscraper.acquire._filters import _parse_audio_languages

    langs = _parse_audio_languages("Movie 2020 ConVOSTed 1080p BluRay")
    assert "VOSTFR" not in langs, "ConVOSTed must not trigger the VOST match"


def test_audio_regex_vostfr_exact_match_works() -> None:
    r"""VOSTFR (standalone word) still matches correctly after \b guard."""
    from personalscraper.acquire._filters import _parse_audio_languages

    langs = _parse_audio_languages("Inception.2010.VOSTFR.1080p.BluRay.x265")
    assert "VOSTFR" in langs


def test_audio_regex_multi_exact_match_works() -> None:
    r"""MULTI (standalone word) matches correctly after \b guard."""
    from personalscraper.acquire._filters import _parse_audio_languages

    langs = _parse_audio_languages("Inception.2010.MULTi.1080p.BluRay.x265")
    assert "VF" in langs


# ---------------------------------------------------------------------------
# TMDB identity filter (wires torr9's tmdb_id into matching)
# ---------------------------------------------------------------------------


class TestTmdbIdentityFilter:
    """The identity filter drops a result whose tmdb_id contradicts the wanted item.

    Engages ONLY when BOTH the result and the wanted media_ref carry a tmdb_id;
    otherwise the result passes (can't disambiguate). The permissive default
    QualityProfile means resolution/audio are no-ops here, isolating the
    identity behaviour.
    """

    def test_mismatched_tmdb_is_dropped(self) -> None:
        """Result tmdb_id != wanted tmdb_id (both set) → DROPPED (wrong remake)."""
        profile = QualityProfile()  # permissive: isolates the identity filter
        wanted = MediaRef(tmdb_id=2021)
        results = [_result("Dune 1984", tmdb_id=1984)]
        survivors = apply_hard_filters(results, profile, wanted)
        assert survivors == []

    def test_matching_tmdb_is_kept(self) -> None:
        """Result tmdb_id == wanted tmdb_id → KEPT (passes resolution/audio)."""
        profile = QualityProfile()
        wanted = MediaRef(tmdb_id=2021)
        results = [_result("Dune 2021", tmdb_id=2021)]
        survivors = apply_hard_filters(results, profile, wanted)
        assert len(survivors) == 1
        assert survivors[0].tmdb_id == 2021

    def test_result_tmdb_none_is_kept(self) -> None:
        """Result tmdb_id None (lacale/c411) + wanted tmdb set → KEPT (no disambiguation)."""
        profile = QualityProfile()
        wanted = MediaRef(tmdb_id=2021)
        results = [_result("Dune 2021", tmdb_id=None)]
        survivors = apply_hard_filters(results, profile, wanted)
        assert len(survivors) == 1

    def test_wanted_tmdb_none_is_kept(self) -> None:
        """Wanted tmdb_id None (tvdb-only item) + result tmdb set → KEPT (no disambiguation)."""
        profile = QualityProfile()
        wanted = MediaRef(tvdb_id=12345)  # tmdb_id defaults to None
        results = [_result("Dune 2021", tmdb_id=2021)]
        survivors = apply_hard_filters(results, profile, wanted)
        assert len(survivors) == 1

    def test_media_ref_none_is_kept(self) -> None:
        """media_ref None (default, e.g. manual grab) → KEPT (existing behaviour unchanged)."""
        profile = QualityProfile()
        results = [_result("Dune 2021", tmdb_id=2021)]
        survivors = apply_hard_filters(results, profile)
        assert len(survivors) == 1

    def test_mismatch_drops_only_the_wrong_version(self) -> None:
        """Mixed batch: the contradicting tmdb_id is dropped, the matching one survives."""
        profile = QualityProfile()
        wanted = MediaRef(tmdb_id=2021)
        results = [
            _result("Dune 1984", tmdb_id=1984),
            _result("Dune 2021", tmdb_id=2021),
            _result("Dune (no tmdb)", tmdb_id=None),
        ]
        survivors = apply_hard_filters(results, profile, wanted)
        survivor_titles = [r.title for r in survivors]
        assert "Dune 1984" not in survivor_titles
        assert "Dune 2021" in survivor_titles
        assert "Dune (no tmdb)" in survivor_titles

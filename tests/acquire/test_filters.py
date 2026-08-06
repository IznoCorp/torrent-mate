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
        provider="c411",
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


# ---------------------------------------------------------------------------
# Stereoscopic-3D exclusion (on by default)
# ---------------------------------------------------------------------------


def test_3d_sbs_dropped_by_default_flat_kept() -> None:
    """Regression (« Le Robot sauvage » recovery grabbed a 3D Full-SBS encode).

    The default profile prefers 1080p x265 correctly, but had NO 3D penalty, so
    a Side-By-Side 3D release — unwatchable on a 2D setup — outranked and won.
    With the default ``exclude_3d`` the 3D variant is dropped and the flat one
    survives.  Red on the pre-fix code (both survived).
    """
    profile = QualityProfile()  # exclude_3d defaults True
    flat = _result("The.Wild.Robot.2024.MULTI.VF2.1080p.WEBRip.x265-NS243")
    threed = _result("The.Wild.Robot.2024.3D.Full-SBS.MULTI.VF2.1080p.10bit.WEBRip.EAC3.x265-NS243")
    survivors = apply_hard_filters([flat, threed], profile)
    titles = [r.title for r in survivors]
    assert flat.title in titles
    assert threed.title not in titles


def test_3d_variants_all_dropped() -> None:
    """Every stereoscopic marker (3D / Full-SBS / Half-SBS / HSBS / Over-Under) is dropped."""
    profile = QualityProfile()
    threed = [
        _result("Film.2024.3D.1080p.x265"),
        _result("Film.2024.Full-SBS.1080p.x265"),
        _result("Film.2024.Half-SBS.1080p.x265"),
        _result("Film.2024.HSBS.1080p.x265"),
        _result("Film.2024.Over-Under.1080p.x265"),
    ]
    survivors = apply_hard_filters(threed, profile)
    assert survivors == []


def test_3d_kept_when_exclude_disabled() -> None:
    """A 3D-capable rig opts back in: exclude_3d=False lets SBS releases through."""
    profile = QualityProfile(exclude_3d=False)
    threed = _result("Film.2024.3D.Full-SBS.1080p.x265")
    survivors = apply_hard_filters([threed], profile)
    assert survivors == [threed]


def test_non_3d_titles_never_false_matched() -> None:
    """Flat titles (incl. x265/HEVC/SBS-broadcaster edge tokens) are never dropped as 3D."""
    profile = QualityProfile()
    flat = [
        _result("Film.2024.1080p.BluRay.x265-GRP"),  # x265 must not trip the H-SBS branch
        _result("Film.2024.1080p.HEVC.HDR-GRP"),
        _result("Show.S01E01.1080p.SBS.WEB-DL"),  # bare SBS (broadcaster) is intentionally allowed
    ]
    survivors = apply_hard_filters(flat, profile)
    assert len(survivors) == 3


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
# TMDB identity filter (wires a tracker result's tmdb_id into matching)
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
        """Result tmdb_id None (c411/tr4ker) + wanted tmdb set → KEPT (no disambiguation)."""
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


class TestTmdbIdentityFilterEndToEndFromATracker:
    """The identity filter is fed by a REAL tracker parse, not a hand-built result.

    The filter was dormant between the removal of the tracker that used to set
    ``tmdb_id`` and the Torznab client mapping the ``tmdbid`` attr: every result
    carried ``None``, so the anti-remake guard could never engage. These tests
    close that loop — the result comes out of ``TorznabClient._parse_item`` and
    goes straight into ``apply_hard_filters``.
    """

    @staticmethod
    def _tracker_results(*tmdbids: str | None) -> list[TrackerResult]:
        """Parse a Torznab RSS document into results, one per given ``tmdbid``.

        Args:
            tmdbids: One value per item; ``None`` omits the attr entirely.

        Returns:
            The parsed :class:`TrackerResult` list, in document order.
        """
        from unittest.mock import MagicMock  # noqa: PLC0415

        from personalscraper.api.tracker.c411 import C411Client  # noqa: PLC0415

        items = []
        for index, tmdbid in enumerate(tmdbids):
            attrs = [{"@name": "seeders", "@value": "10"}]
            if tmdbid is not None:
                attrs.append({"@name": "tmdbid", "@value": tmdbid})
            items.append(
                {
                    "title": f"Dune.{index}.1080p.BluRay.x265-GRP",
                    "guid": f"hash{index}",
                    "size": "1000",
                    "torznab:attr": attrs,
                }
            )
        client = C411Client(MagicMock())
        client._transport.get.return_value = {"rss": {"channel": {"item": items}}}
        return client.search("Dune")

    def test_tracker_parsed_mismatch_is_dropped_again(self) -> None:
        """A tracker result whose parsed tmdb_id contradicts the wanted item is DROPPED."""
        results = self._tracker_results("1984")
        assert results[0].tmdb_id == 1984  # the parse actually produced the id

        survivors = apply_hard_filters(results, QualityProfile(), MediaRef(tmdb_id=2021))

        assert survivors == []

    def test_tracker_parsed_match_survives(self) -> None:
        """A tracker result whose parsed tmdb_id matches the wanted item SURVIVES."""
        survivors = apply_hard_filters(self._tracker_results("2021"), QualityProfile(), MediaRef(tmdb_id=2021))

        assert len(survivors) == 1

    def test_tracker_result_without_the_attr_still_passes(self) -> None:
        """No ``tmdbid`` attr → None → the filter stays a no-op (never a wrong drop)."""
        results = self._tracker_results(None)
        assert results[0].tmdb_id is None

        survivors = apply_hard_filters(results, QualityProfile(), MediaRef(tmdb_id=2021))

        assert len(survivors) == 1

    def test_mixed_tracker_batch_keeps_only_the_right_version(self) -> None:
        """Wrong remake dropped, right one and id-less one kept — all from one parse."""
        results = self._tracker_results("1984", "2021", None)

        survivors = apply_hard_filters(results, QualityProfile(), MediaRef(tmdb_id=2021))

        assert [r.tmdb_id for r in survivors] == [2021, None]


# ---------------------------------------------------------------------------
# Video-category filter (Spider-Man soundtrack regression)
# ---------------------------------------------------------------------------


class TestVideoCategoryFilter:
    r"""Regression: a FLAC soundtrack must never satisfy a video wanted item.

    Live incident 2026-08-05 20:35:58 — wanted #95 "Spider-Man : Brand New Day"
    (movie, tmdb 969681) grabbed the Michael Giacchino SOUNDTRACK album. The
    title guard passed (rapidfuzz token_set_ratio 96 — an artist prefix costs
    nothing) and the year matched (2026), while the resolution filter fails open
    on a release that carries no resolution. Nothing in the chain ever asked
    whether the release was VIDEO at all.

    The trackers had said so all along, in the one field that is authoritative
    tracker metadata rather than a title heuristic: the Newznab category. Both
    live results were tagged Audio.
    """

    #: The two results the live search actually returned, provider-agnostic:
    #: the filter keys on the Newznab class, not on which tracker sent it.
    SOUNDTRACKS = [
        ("c411", "3010", "Michael.Giacchino.Spider-Man.Brand.New.Day.2026.FLAC.[16bit.44.1kHz]-SDB"),
        (
            "tr4ker",
            "3000",
            "Michael.Giacchino.Spider-Man.Brand.New.Day.Original.Motion.Picture."
            "Soundtrack.24BIT.44.1KHZ.WEB.FLAC.2026.TEAM-EICHBAUM",
        ),
    ]

    @staticmethod
    def _categorised(provider: str, category: str | None, title: str) -> TrackerResult:
        """Build a result carrying a Newznab category, as every Torznab tracker does."""
        return TrackerResult(
            provider=provider,
            tracker_id="t1",
            title=title,
            size=ByteSize(700_000_000),
            seeders=10,
            leechers=0,
            resolution=None,
            category=category,
        )

    def test_live_soundtracks_are_dropped_for_every_tracker(self) -> None:
        """Both real Audio-category results are dropped, whichever tracker sent them."""
        results = [self._categorised(*row) for row in self.SOUNDTRACKS]

        survivors = apply_hard_filters(results, QualityProfile())

        assert survivors == []

    def test_video_categories_survive(self) -> None:
        """Movies (2xxx) AND TV (5xxx) survive — C411 files both under « Films & Vidéos ».

        LOAD-BEARING: a movie search on C411 legitimately returns 5xxx subcats
        (5000 « Série TV », 5070 « Animation Série ») because they sit under the
        2000 parent. Narrowing a movie wanted to 2xxx would drop real releases.
        """
        results = [
            self._categorised("c411", "2030", "Spider-Man Brand New Day 2026 1080p WEB-DL"),
            self._categorised("c411", "2060", "Some Animated Movie 2026 1080p"),
            self._categorised("c411", "5000", "Some Show S01E01 1080p"),
            self._categorised("c411", "5070", "Some Anime S01E01 1080p"),
        ]

        survivors = apply_hard_filters(results, QualityProfile())

        assert [r.category for r in survivors] == ["2030", "2060", "5000", "5070"]

    def test_other_non_video_classes_are_dropped(self) -> None:
        """Console (1xxx), PC (4xxx) and Books (7xxx) can never satisfy a video wanted.

        Every ``wanted.kind`` is movie/episode/season, so the acquisition lobe
        never wants a game, an application or an ebook.
        """
        results = [
            self._categorised("c411", "1000", "Marvels.Spider-Man.2.v1.526.0.FRENCH-Mephisto"),
            self._categorised("c411", "4000", "Some.App.v1.2-GRP"),
            self._categorised("c411", "7000", "Some.Ebook.epub"),
        ]

        survivors = apply_hard_filters(results, QualityProfile())

        assert survivors == []

    def test_missing_category_fails_open(self) -> None:
        """LOAD-BEARING: no category → keep.

        A tracker that publishes none must not have its whole result set
        silently wiped.
        """
        results = [self._categorised("other", None, "Spider-Man Brand New Day 2026 1080p")]

        survivors = apply_hard_filters(results, QualityProfile())

        assert len(survivors) == 1

    def test_non_numeric_category_fails_open(self) -> None:
        """A slug-based dialect ('films') is not a Newznab class — keep, never guess."""
        results = [self._categorised("other", "films", "Spider-Man Brand New Day 2026 1080p")]

        survivors = apply_hard_filters(results, QualityProfile())

        assert len(survivors) == 1


# ---------------------------------------------------------------------------
# Adult-content filter (XXX)
# ---------------------------------------------------------------------------


class TestAdultFilter:
    """An adult release must never satisfy a movie/TV wanted item.

    Live incident 2026-08-06: the wanted film « The Odyssey » (TMDB 1368337) was
    satisfied by an adult release. The tracker probe of the very same query shows
    why nothing stopped it — the class-6 result was the ONLY survivor:

        cat=2000  classe=2  The.Odyssey.Making.Of.2026...-BYOR
        cat=2070  classe=2  The.Odyssey.Making.Of.2026.DOC...-BYOR
        cat=6010  classe=6  [Cosplayground].The.Odyssey.Part.1.2026...-ONYXA   <-- grabbed
        cat=7000  classe=7  PACK.5183.BANDES.DESSINEES...-DDD                  (dropped, class 7)
        cat=3010  classe=3  Ludwig.Goransson.The.Odyssey.2026.FLAC...-SDB      (dropped, class 3)
    """

    #: The exact release that was grabbed, with the category the tracker really
    #: published for it (verified live against c411/tr4ker on 2026-08-06).
    LIVE_ADULT = ("tr4ker", "6010", "[Cosplayground].The.Odyssey.Part.1.2026.VO.720p.AVC.AAC.2.0-ONYXA")

    @staticmethod
    def _categorised(provider: str, category: str | None, title: str) -> TrackerResult:
        return TrackerResult(
            provider=provider,
            tracker_id="t1",
            title=title,
            size=ByteSize(700_000_000),
            seeders=10,
            leechers=0,
            resolution=None,
            category=category,
        )

    def test_live_adult_release_is_dropped(self) -> None:
        """REGRESSION: the exact release grabbed on 2026-08-06 must not survive."""
        provider, category, title = self.LIVE_ADULT
        results = [self._categorised(provider, category, title)]

        survivors = apply_hard_filters(results, QualityProfile())

        assert survivors == []

    def test_adult_class_dropped_for_every_tracker(self) -> None:
        """Any class-6 category is dropped, whichever tracker published it."""
        results = [
            self._categorised("c411", "6010", "Some.Adult.Release.2026.1080p"),
            self._categorised("tr4ker", "6000", "Another.Adult.Release.2026.1080p"),
            self._categorised("c411", "6070", "Third.Adult.Release.2026.1080p"),
        ]

        survivors = apply_hard_filters(results, QualityProfile())

        assert survivors == []

    def test_movie_class_still_passes(self) -> None:
        """The guard must not touch legitimate video classes."""
        results = [self._categorised("c411", "2000", "The.Odyssey.2026.MULTi.1080p.WEB-BYOR")]

        survivors = apply_hard_filters(results, QualityProfile())

        assert len(survivors) == 1

    def test_adult_title_marker_dropped_when_category_lies(self) -> None:
        """Defense in depth: an explicit adult marker is dropped even under class 2.

        A tracker that mis-files an adult release under Movies would otherwise
        walk straight through the category rule.
        """
        results = [
            self._categorised("c411", "2000", "Some.Movie.A.XXX.Parody.2026.1080p"),
            self._categorised("c411", "2000", "Some.Movie.2026.PORN.1080p"),
            self._categorised("c411", None, "Some.Movie.2026.HENTAI.1080p"),
        ]

        survivors = apply_hard_filters(results, QualityProfile())

        assert survivors == []

    def test_xxx_alone_does_not_drop_the_2002_film(self) -> None:
        """LOAD-BEARING: « xXx » (2002) is a mainstream film, not an adult release.

        A bare ``XXX`` token is deliberately NOT an adult marker — the title guard
        keys on unambiguous words only. The category rule remains the authority.
        """
        results = [
            self._categorised("c411", "2000", "xXx.2002.MULTi.1080p.BluRay.x264-GRP"),
            self._categorised("c411", "2000", "xXx.Return.of.Xander.Cage.2017.MULTi.1080p-GRP"),
        ]

        survivors = apply_hard_filters(results, QualityProfile())

        assert len(survivors) == 2

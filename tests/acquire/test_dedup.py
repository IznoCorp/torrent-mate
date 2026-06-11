"""Non-vacuous tests for the cross-tracker dedup engine + search_candidates seam.

The ``-QTZ`` golden is LOAD-BEARING (DESIGN §4 / §11): it uses the *real*
divergent-title release pairs from ``docs/reference/_samples/`` and asserts the
engine genuinely MERGES them. A normalizer that fails to merge the real pairs is
the failure mode this file is designed to catch — assertions check survivor
identity and group count, never just "no exception".

Ground-truth sample provenance (verified against the fixtures):

- ``docs/reference/_samples/lacale/search-inception.json``
- ``docs/reference/_samples/c411/search-inception.xml``

Cross-tracker pair #1 (AAC, EXACT same size 4677887384, divergent info_hash):
    lacale "Inception (2010) MULTi VFF 2160p 10bit 4KLight HDR BluRay x265 HE-AAC 5.1 - QTZ"
           info_hash=41fa1a36… seeders=101
    c411   "Inception.2010.MULTI.VFF.2160p.BluRay.HDR10.AAC.5.1.x265-QTZ"
           info_hash=0450af2b… seeders=110
    → MUST merge (re-pack → divergent hash → caught by the fuzzy key).

Cross-tracker pair #2 (DTS, ~0.6 % size diff — exercises the tolerance window):
    lacale "Inception (2010) MULTi VFF 2160p 10bit 4KLight HDR BluRay x265 DTS 5.1 - QTZ"
           size=7352098468 info_hash=5a3b9563… seeders=175
    c411   "Inception.2010.MULTi.VFF.2160p.BluRay.4KLight.HDR.10bit.DTS.5.1.x265-QTZ"
           size=7396633907 info_hash=b08b70d0… seeders=141
    → MUST merge (diff 0.6 % < 2 % tolerance).

AAC (~4.68 GB) vs DTS (~7.35 GB) → MUST stay distinct (57 % size diff + audio).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.acquire._dedup import (
    SearchOutcome,
    dedup,
    normalize_title_core,
)
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry


def _make_registry(trackers: dict, priority: list[str]) -> TrackerRegistry:
    """Build a TrackerRegistry over mock clients with a default ranking.

    ``search_candidates`` never calls ``rank()``, so the ranking config is inert
    here — a default :class:`RankingConfig` is enough to construct the registry.
    """
    ranking = RankingConfig(min_seeders=0)
    return TrackerRegistry(trackers=trackers, priority=priority, ranking=ranking)


def _make_result(
    provider: str,
    title: str,
    size: int,
    info_hash: str | None = None,
    seeders: int = 10,
    resolution: str | None = None,
    is_freeleech: bool = False,
    is_silverleech: bool = False,
) -> TrackerResult:
    """Construct a TrackerResult with the fields the dedup engine reads."""
    return TrackerResult(
        provider=provider,
        tracker_id="t1",
        title=title,
        size=ByteSize(size),
        seeders=seeders,
        leechers=0,
        info_hash=info_hash,
        resolution=resolution,
        is_freeleech=is_freeleech,
        is_silverleech=is_silverleech,
    )


# ---------------------------------------------------------------------------
# Real -QTZ sample objects (verified against the fixtures, real seeder counts)
# ---------------------------------------------------------------------------

_QTZ_AAC_LACALE = _make_result(
    "lacale",
    "Inception (2010) MULTi VFF 2160p 10bit 4KLight HDR BluRay x265 HE-AAC 5.1 - QTZ",
    4677887384,
    info_hash="41fa1a3678fc8100ecb29e020264015d9d781642",
    seeders=101,
    resolution="2160p",
)
_QTZ_AAC_C411 = _make_result(
    "c411",
    "Inception.2010.MULTI.VFF.2160p.BluRay.HDR10.AAC.5.1.x265-QTZ",
    4677887384,
    info_hash="0450af2b81eb8885befb1f2a92e33f72a8d9e93e",
    seeders=110,
    resolution="2160p",
)
_QTZ_DTS_LACALE = _make_result(
    "lacale",
    "Inception (2010) MULTi VFF 2160p 10bit 4KLight HDR BluRay x265 DTS 5.1 - QTZ",
    7352098468,
    info_hash="5a3b9563fe21c5a11b8feeb40c2c7f46a1a8b1a6",
    seeders=175,
    resolution="2160p",
)
_QTZ_DTS_C411 = _make_result(
    "c411",
    "Inception.2010.MULTi.VFF.2160p.BluRay.4KLight.HDR.10bit.DTS.5.1.x265-QTZ",
    7396633907,
    info_hash="b08b70d0855318efa71aeccce0ae42b3e4493113",
    seeders=141,
    resolution="2160p",
)


# ---------------------------------------------------------------------------
# Task 1: SearchOutcome + search_candidates seam
# ---------------------------------------------------------------------------


def test_search_candidates_happy_path() -> None:
    """A single healthy tracker → SearchOutcome with its results, 0 errored."""
    result = _make_result("lacale", "Inception 2010", 1_000_000)
    mock_client = MagicMock()
    mock_client.search.return_value = [result]
    registry = _make_registry({"lacale": mock_client}, ["lacale"])

    outcome = registry.search_candidates("Inception", MediaType.MOVIE, 2010)

    assert isinstance(outcome, SearchOutcome)
    assert outcome.results == [result]
    assert outcome.trackers_queried == 1
    assert outcome.trackers_errored == 0
    assert not outcome.all_errored


def test_search_candidates_merges_two_trackers_unranked() -> None:
    """Results from both trackers are concatenated in priority order, un-ranked."""
    r_lacale = _make_result("lacale", "Inception 2010 lacale", 1_000_000, seeders=5)
    r_c411 = _make_result("c411", "Inception 2010 c411", 2_000_000, seeders=500)
    lacale = MagicMock()
    lacale.search.return_value = [r_lacale]
    c411 = MagicMock()
    c411.search.return_value = [r_c411]
    registry = _make_registry({"lacale": lacale, "c411": c411}, ["lacale", "c411"])

    outcome = registry.search_candidates("Inception", MediaType.MOVIE, 2010)

    # Un-ranked: lacale (priority 0, fewer seeders) appears before c411.
    assert outcome.results == [r_lacale, r_c411]
    assert outcome.trackers_queried == 2
    assert outcome.trackers_errored == 0


def test_search_candidates_tracker_error_increments_errored() -> None:
    """An ApiError from one tracker is swallowed but counted; results survive."""
    mock_client = MagicMock()
    mock_client.search.side_effect = ApiError(provider="lacale", http_status=500, message="down")
    registry = _make_registry({"lacale": mock_client}, ["lacale"])

    outcome = registry.search_candidates("Inception", MediaType.MOVIE, None)

    assert outcome.trackers_queried == 1
    assert outcome.trackers_errored == 1
    assert outcome.results == []


def test_search_candidates_all_errored_flag() -> None:
    """Every queried tracker errored → all_errored is True (retryable outage)."""
    mock_client = MagicMock()
    mock_client.search.side_effect = ApiError(provider="lacale", http_status=503, message="down")
    registry = _make_registry({"lacale": mock_client}, ["lacale"])

    outcome = registry.search_candidates("Inception", MediaType.MOVIE, None)

    assert outcome.all_errored


def test_search_outcome_empty_is_not_all_errored() -> None:
    """An empty registry queried nothing → all_errored stays False (not an outage)."""
    outcome = SearchOutcome()
    assert outcome.trackers_queried == 0
    assert not outcome.all_errored


# ---------------------------------------------------------------------------
# Task 2: token-set title normalizer
# ---------------------------------------------------------------------------


def test_normalize_strips_noise_tokens_real_qtz_dts_pair() -> None:
    """The real DTS -QTZ pair (divergent punctuation/order) → identical core."""
    a = normalize_title_core(_QTZ_DTS_LACALE.title)
    b = normalize_title_core(_QTZ_DTS_C411.title)
    assert a == b, f"Expected same core for the DTS -QTZ pair, got {sorted(a)!r} vs {sorted(b)!r}"


def test_normalize_strips_noise_tokens_real_qtz_aac_pair() -> None:
    """The real AAC -QTZ pair (HE-AAC vs AAC, HDR10 vs HDR) → identical core."""
    a = normalize_title_core(_QTZ_AAC_LACALE.title)
    b = normalize_title_core(_QTZ_AAC_C411.title)
    assert a == b, f"Expected same core for the AAC -QTZ pair, got {sorted(a)!r} vs {sorted(b)!r}"


def test_normalize_aac_core_differs_from_dts_core() -> None:
    """AAC and DTS variants have distinct cores — the audio token discriminates."""
    aac = normalize_title_core(_QTZ_AAC_LACALE.title)
    dts = normalize_title_core(_QTZ_DTS_LACALE.title)
    assert aac != dts


def test_normalize_preserves_vf_vostfr_as_distinct() -> None:
    """VF and VOSTFR produce different cores — language markers are preserved."""
    vf = normalize_title_core("Inception.2010.MULTi.VFF.2160p.BluRay.x265-QTZ")
    vostfr = normalize_title_core("Inception.2010.VOSTFR.2160p.BluRay.x265-QTZ")
    assert vf != vostfr


def test_normalize_codec_alias_he_aac_to_aac() -> None:
    """HE-AAC is aliased to AAC for normalization purposes."""
    a = normalize_title_core("Movie.2020.AAC.5.1.x265-GRP")
    b = normalize_title_core("Movie.2020.HE-AAC.5.1.x265-GRP")
    assert a == b


def test_normalize_order_independent() -> None:
    """Token-SET comparison: word-order differences collapse to the same core."""
    a = normalize_title_core("Movie.2020.1080p.BluRay.x264-GRP")
    b = normalize_title_core("Movie BluRay 2020 1080p x264 GRP")
    assert a == b


# ---------------------------------------------------------------------------
# Task 3: dedup — info_hash primary + fuzzy fallback + best-provenance
#         The LOAD-BEARING -QTZ golden lives here.
# ---------------------------------------------------------------------------


def test_dedup_same_info_hash_within_tracker_collapses() -> None:
    """PRIMARY key: identical info_hash → one survivor (within-tracker re-announce)."""
    r1 = _make_result("lacale", "Movie 2020", 1_000_000, info_hash="AAAA", seeders=5)
    r2 = _make_result("lacale", "Movie 2020 repack", 1_000_000, info_hash="aaaa", seeders=99)
    survivors = dedup([r1, r2])
    assert len(survivors) == 1
    # Hash key is case-insensitive ("AAAA" == "aaaa") and best-provenance keeps r2.
    assert survivors[0].seeders == 99


def test_dedup_qtz_aac_pair_merges_exact_size() -> None:
    """LOAD-BEARING: the real AAC -QTZ pair (divergent hash, EXACT size) merges to 1."""
    survivors = dedup([_QTZ_AAC_LACALE, _QTZ_AAC_C411])
    assert len(survivors) == 1, "AAC -QTZ cross-tracker pair must merge into 1 survivor, got " + str(
        [(r.provider, r.title[:48]) for r in survivors]
    )
    # Best provenance: c411 has more seeders (110 > 101).
    assert survivors[0].provider == "c411"
    assert survivors[0].seeders == 110


def test_dedup_qtz_dts_pair_merges_via_size_tolerance() -> None:
    """LOAD-BEARING: the real DTS -QTZ pair (~0.6 % size diff) merges via the 2 % window."""
    survivors = dedup([_QTZ_DTS_LACALE, _QTZ_DTS_C411])
    assert len(survivors) == 1, (
        "DTS -QTZ cross-tracker pair must merge into 1 survivor (size within tolerance), got "
        + str([(r.provider, r.size.bytes) for r in survivors])
    )
    # Best provenance: lacale has more seeders (175 > 141).
    assert survivors[0].provider == "lacale"
    assert survivors[0].seeders == 175


def test_dedup_all_four_qtz_items_collapse_to_exactly_two_groups() -> None:
    """LOAD-BEARING GOLDEN: the 4 real -QTZ items → exactly 2 groups (AAC, DTS).

    NOT 1 (proves AAC ≠ DTS: 57 % size diff + different audio token), and
    NOT 4 (proves the cross-tracker merge genuinely fires on divergent titles).
    """
    survivors = dedup([_QTZ_AAC_LACALE, _QTZ_AAC_C411, _QTZ_DTS_LACALE, _QTZ_DTS_C411])
    assert len(survivors) == 2, "Expected exactly 2 groups (AAC + DTS), got " + str(
        [(r.provider, r.size.bytes, r.title[:40]) for r in survivors]
    )
    sizes = sorted(r.size.bytes for r in survivors)
    # One ~4.68 GB AAC representative and one ~7.35 GB DTS representative.
    assert sizes == [4677887384, 7352098468]
    providers = {r.size.bytes: r.provider for r in survivors}
    assert providers[4677887384] == "c411"  # AAC: c411 wins on seeders
    assert providers[7352098468] == "lacale"  # DTS: lacale wins on seeders


def test_dedup_vf_vs_vostfr_same_size_stays_distinct() -> None:
    """Language preservation: a VF cut and a VOSTFR cut never merge, even at equal size."""
    vff = _make_result(
        "lacale",
        "Inception 2010 MULTi VFF 2160p BluRay x265 QTZ",
        7_000_000_000,
        resolution="2160p",
    )
    vostfr = _make_result(
        "c411",
        "Inception 2010 VOSTFR 2160p BluRay x265 QTZ",
        7_000_000_000,
        resolution="2160p",
    )
    survivors = dedup([vff, vostfr])
    assert len(survivors) == 2, "VFF and VOSTFR must remain distinct"


def test_dedup_no_info_hash_uses_fuzzy_key() -> None:
    """Two hash-less results with matching fuzzy key + size → deduplicated."""
    r1 = _make_result("lacale", "Movie 2020 1080p BluRay x265 GRP", 2_000_000_000)
    r2 = _make_result("c411", "Movie.2020.1080p.BluRay.x265-GRP", 2_010_000_000)  # ~0.5 % diff
    survivors = dedup([r1, r2])
    assert len(survivors) == 1


def test_dedup_size_beyond_tolerance_stays_distinct() -> None:
    """Same title core but sizes 57 % apart (AAC vs DTS sizes) → 2 distinct survivors.

    Sanity that the size-tolerance window is real and not a vacuous always-merge:
    identical core tokens but a large size gap must NOT collapse.
    """
    small = _make_result(
        "lacale",
        "Movie 2020 MULTi VFF 2160p BluRay x265 GRP",
        4_677_887_384,
        resolution="2160p",
    )
    large = _make_result(
        "c411",
        "Movie 2020 MULTi VFF 2160p BluRay x265 GRP",
        7_352_098_468,
        resolution="2160p",
    )
    survivors = dedup([small, large])
    assert len(survivors) == 2


def test_dedup_best_provenance_freeleech_beats_seeders() -> None:
    """Provenance priority: freeleech outranks a higher seeder count."""
    free = _make_result(
        "lacale",
        "Movie 2020 MULTi VFF 2160p BluRay x265 GRP",
        2_000_000_000,
        seeders=1,
        resolution="2160p",
        is_freeleech=True,
    )
    busy = _make_result(
        "c411",
        "Movie 2020 MULTi VFF 2160p BluRay x265 GRP",
        2_000_000_000,
        seeders=900,
        resolution="2160p",
    )
    survivors = dedup([free, busy])
    assert len(survivors) == 1
    assert survivors[0].is_freeleech
    assert survivors[0].provider == "lacale"

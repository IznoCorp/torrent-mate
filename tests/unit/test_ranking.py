"""Tests for the tracker ranking engine — rank()."""

from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import (
    RankingBonuses,
    RankingConfig,
    RankingCriterion,
    ThresholdEntry,
    rank,
)


def _result(
    *,
    title: str = "T",
    seeders: int = 10,
    size: int = 1_000_000_000,
    resolution: str | None = None,
    is_freeleech: bool = False,
    is_silverleech: bool = False,
) -> TrackerResult:
    """Build a minimal TrackerResult with sensible defaults."""
    return TrackerResult(
        provider="test",
        tracker_id="t1",
        title=title,
        size=ByteSize.parse(size),
        seeders=seeders,
        leechers=0,
        resolution=resolution,
        is_freeleech=is_freeleech,
        is_silverleech=is_silverleech,
    )


class TestRankCategorical:
    """Categorical scoring via the `values` map."""

    def test_resolution_match_applies_weight(self) -> None:
        """resolution: {'2160p': 20} with weight=2 gives 40 points."""
        results = [_result(resolution="2160p")]
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(field="resolution", weight=2.0, values={"2160p": 20, "1080p": 15}),
            ],
        )
        scored = rank(results, cfg)
        assert scored[0][1] == 40

    def test_unknown_value_scores_zero(self) -> None:
        """Unmapped categorical value yields 0 points for that criterion."""
        results = [_result(resolution="240p")]
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(field="resolution", values={"2160p": 20}),
            ],
        )
        assert rank(results, cfg)[0][1] == 0


class TestRankThresholds:
    """Numeric threshold scoring via the `thresholds` ladder."""

    def test_seeders_thresholds_pick_highest_applicable(self) -> None:
        """seeders=50 with rungs at 0/5/20/100 picks the 20-rung score."""
        results = [_result(seeders=50)]
        cfg = RankingConfig(
            min_seeders=0,
            criteria=[
                RankingCriterion(
                    field="seeders",
                    thresholds=[
                        ThresholdEntry(at=0, score=0),
                        ThresholdEntry(at=5, score=2),
                        ThresholdEntry(at=20, score=5),
                        ThresholdEntry(at=100, score=10),
                    ],
                ),
            ],
        )
        assert rank(results, cfg)[0][1] == 5

    def test_size_threshold_matches_bytesize(self) -> None:
        """size=5GB with rungs at 1GB/5GB picks the 5GB-rung score."""
        results = [_result(size=5_000_000_000, seeders=10)]
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(
                    field="size",
                    thresholds=[
                        ThresholdEntry(at="1GB", score=5),  # type: ignore[arg-type]
                        ThresholdEntry(at="5GB", score=10),  # type: ignore[arg-type]
                    ],
                ),
            ],
        )
        assert rank(results, cfg)[0][1] == 10

    def test_prefer_lower_inverts_threshold_direction(self) -> None:
        """`prefer="lower"` makes smaller-is-better — 700MB ranks higher than 7GB."""
        small = _result(size=700_000_000, seeders=10)
        large = _result(size=7_000_000_000, seeders=10)
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(
                    field="size",
                    prefer="lower",
                    thresholds=[
                        ThresholdEntry(at="1GB", score=10),  # type: ignore[arg-type]
                        ThresholdEntry(at="3GB", score=5),  # type: ignore[arg-type]
                    ],
                ),
            ],
            min_seeders=0,
        )
        scored = rank([large, small], cfg)
        # Smaller result wins, with the lowest threshold score (10).
        assert scored[0][0] is small
        assert scored[0][1] == 10
        # 7GB is above the highest "lower" threshold (3GB) → 0 points.
        assert scored[1][0] is large
        assert scored[1][1] == 0

    def test_prefer_higher_default_unchanged(self) -> None:
        """`prefer="higher"` (and the default `None`) keeps the existing semantics."""
        small = _result(size=500_000_000, seeders=10)
        large = _result(size=10_000_000_000, seeders=10)
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(
                    field="size",
                    prefer="higher",
                    thresholds=[
                        ThresholdEntry(at="1GB", score=5),  # type: ignore[arg-type]
                        ThresholdEntry(at="5GB", score=10),  # type: ignore[arg-type]
                    ],
                ),
            ],
            min_seeders=0,
        )
        scored = rank([small, large], cfg)
        assert scored[0][0] is large
        assert scored[0][1] == 10
        # 500MB below 1GB → no threshold applies → 0 points.
        assert scored[1][0] is small
        assert scored[1][1] == 0


class TestRankFilters:
    """min_seeders cutoff."""

    def test_min_seeders_drops_sub_threshold(self) -> None:
        """Seeders < min_seeders → result excluded from output."""
        results = [_result(seeders=0), _result(seeders=10)]
        cfg = RankingConfig(min_seeders=1)
        scored = rank(results, cfg)
        assert len(scored) == 1
        assert scored[0][0].seeders == 10


class TestRankBonuses:
    """freeleech / silverleech bonus addition."""

    def test_freeleech_bonus_added(self) -> None:
        """is_freeleech adds bonuses.freeleech to total."""
        results = [_result(is_freeleech=True)]
        cfg = RankingConfig(bonuses=RankingBonuses(freeleech=10, silverleech=5))
        assert rank(results, cfg)[0][1] == 10

    def test_silverleech_bonus_added(self) -> None:
        """is_silverleech adds bonuses.silverleech to total."""
        results = [_result(is_silverleech=True)]
        cfg = RankingConfig(bonuses=RankingBonuses(freeleech=10, silverleech=5))
        assert rank(results, cfg)[0][1] == 5

    def test_both_bonuses_additive(self) -> None:
        """Both flags set → sum of both bonuses."""
        results = [_result(is_freeleech=True, is_silverleech=True)]
        cfg = RankingConfig(bonuses=RankingBonuses(freeleech=10, silverleech=5))
        assert rank(results, cfg)[0][1] == 15


class TestRankSortStability:
    """Sort order: descending score; stable for ties."""

    def test_highest_score_first(self) -> None:
        """Higher score sorts before lower score."""
        a = _result(title="A", resolution="1080p")
        b = _result(title="B", resolution="2160p")
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(field="resolution", values={"2160p": 20, "1080p": 15}),
            ],
        )
        scored = rank([a, b], cfg)
        assert scored[0][0].title == "B"
        assert scored[1][0].title == "A"

    def test_stable_for_ties(self) -> None:
        """Ties preserve input order (Python's sort is stable)."""
        a = _result(title="A", resolution="1080p")
        b = _result(title="B", resolution="1080p")
        c = _result(title="C", resolution="1080p")
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(field="resolution", values={"1080p": 15}),
            ],
        )
        scored = rank([a, b, c], cfg)
        assert [r[0].title for r in scored] == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# Per-media-type size thresholds (#376)
# ---------------------------------------------------------------------------


_MOVIE_TIERS: list[ThresholdEntry] = [
    ThresholdEntry(at=0, score=0),
    ThresholdEntry(at="4GB", score=5),  # type: ignore[arg-type]
    ThresholdEntry(at="15GB", score=10),  # type: ignore[arg-type]
]
_EPISODE_TIERS: list[ThresholdEntry] = [
    ThresholdEntry(at=0, score=0),
    ThresholdEntry(at="500MB", score=5),  # type: ignore[arg-type]
    ThresholdEntry(at="2GB", score=10),  # type: ignore[arg-type]
]
_GENERIC_SIZE_CRITERION = RankingCriterion(
    field="size",
    prefer="higher",
    thresholds=[
        ThresholdEntry(at=0, score=0),
        ThresholdEntry(at="1GB", score=5),  # type: ignore[arg-type]
        ThresholdEntry(at="5GB", score=10),  # type: ignore[arg-type]
    ],
)


class TestRankMediaKind:
    """media_kind parameter for per-type size thresholds."""

    def test_media_kind_none_is_byte_identical(self) -> None:
        """media_kind=None produces the same scores as today (golden pin)."""
        cfg = RankingConfig(criteria=[_GENERIC_SIZE_CRITERION], min_seeders=0)
        r = _result(size=5_000_000_000)
        # With media_kind=None
        scored_none = rank([r], cfg, media_kind=None)
        # Without media_kind (default)
        scored_default = rank([r], cfg)
        assert scored_none[0][1] == scored_default[0][1] == 10

    def test_movie_kind_uses_movie_tiers(self) -> None:
        """A 6GB movie: generic tiers give 10pts (≥5GB), movie tiers give 5pts (≥4GB but <15GB)."""
        cfg = RankingConfig(
            criteria=[_GENERIC_SIZE_CRITERION],
            min_seeders=0,
            size_thresholds_by_type={"movie": _MOVIE_TIERS},
        )
        r = _result(size=6_000_000_000)
        # Generic: ≥5GB → 10. Movie: ≥4GB but <15GB → 5.
        assert rank([r], cfg)[0][1] == 10  # no override
        assert rank([r], cfg, media_kind="movie")[0][1] == 5

    def test_episode_kind_uses_episode_tiers(self) -> None:
        """A 600MB episode: generic tiers give 0 (below 1GB), episode tiers give 5 (≥500MB)."""
        cfg = RankingConfig(
            criteria=[_GENERIC_SIZE_CRITERION],
            min_seeders=0,
            size_thresholds_by_type={"episode": _EPISODE_TIERS},
        )
        r = _result(size=600_000_000)
        assert rank([r], cfg)[0][1] == 0  # generic: below 1GB → 0
        assert rank([r], cfg, media_kind="episode")[0][1] == 5

    def test_kind_set_but_no_entry_falls_back_to_generic(self) -> None:
        """When media_kind='episode' but no episode entry exists, use generic thresholds."""
        cfg = RankingConfig(
            criteria=[_GENERIC_SIZE_CRITERION],
            min_seeders=0,
            size_thresholds_by_type={"movie": _MOVIE_TIERS},
        )
        r = _result(size=5_000_000_000)
        # 'episode' has no by-type entry → falls back to generic
        assert rank([r], cfg, media_kind="episode")[0][1] == 10

    def test_empty_list_entry_falls_back_to_generic(self) -> None:
        """An empty list for a kind → fall back to generic thresholds."""
        cfg = RankingConfig(
            criteria=[_GENERIC_SIZE_CRITERION],
            min_seeders=0,
            size_thresholds_by_type={"movie": []},
        )
        r = _result(size=5_000_000_000)
        # Empty list → fall back to generic
        assert rank([r], cfg, media_kind="movie")[0][1] == 10

    def test_prefer_lower_still_applies_with_by_type(self) -> None:
        """The criterion's prefer='lower' still applies with per-type thresholds."""
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(
                    field="size",
                    prefer="lower",
                    thresholds=[
                        ThresholdEntry(at="1GB", score=10),  # type: ignore[arg-type]
                        ThresholdEntry(at="3GB", score=5),  # type: ignore[arg-type]
                    ],
                ),
            ],
            min_seeders=0,
            size_thresholds_by_type={
                "movie": [
                    ThresholdEntry(at="2GB", score=10),  # type: ignore[arg-type]
                    ThresholdEntry(at="8GB", score=5),  # type: ignore[arg-type]
                ],
            },
        )
        small = _result(size=1_500_000_000)
        large = _result(size=10_000_000_000)
        # prefer="lower": smaller is better. movie tier: <2GB → 10, >8GB → 0.
        scored = rank([large, small], cfg, media_kind="movie")
        assert scored[0][0] is small
        assert scored[0][1] == 10
        assert scored[1][1] == 0

    def test_non_size_criterion_unaffected(self) -> None:
        """media_kind only affects the 'size' field; other criteria are unchanged."""
        cfg = RankingConfig(
            criteria=[
                RankingCriterion(field="seeders", thresholds=[ThresholdEntry(at=1, score=20)]),
                _GENERIC_SIZE_CRITERION,
            ],
            min_seeders=0,
            size_thresholds_by_type={"movie": _MOVIE_TIERS},
        )
        r = _result(size=6_000_000_000, seeders=10)
        # seeders: 20pts + size: with movie tiers: 5pts = 25
        assert rank([r], cfg, media_kind="movie")[0][1] == 25
        # seeders: 20pts + size: generic: 10pts = 30
        assert rank([r], cfg)[0][1] == 30

    def test_media_kind_ignored_when_no_size_thresholds_by_type(self) -> None:
        """When size_thresholds_by_type is None, media_kind is a no-op."""
        cfg = RankingConfig(criteria=[_GENERIC_SIZE_CRITERION], min_seeders=0)
        r = _result(size=6_000_000_000)
        assert rank([r], cfg, media_kind="movie")[0][1] == 10
        assert rank([r], cfg, media_kind="episode")[0][1] == 10

    def test_exclude_hashes_and_media_kind_compose(self) -> None:
        """exclude_hashes and media_kind both work when passed together."""
        cfg = RankingConfig(
            criteria=[_GENERIC_SIZE_CRITERION],
            min_seeders=0,
            size_thresholds_by_type={"movie": _MOVIE_TIERS},
        )
        excluded = _result(size=15_000_000_000)
        # Give it an info_hash so it can be excluded.
        excluded = TrackerResult(
            provider="test",
            tracker_id="t1",
            title="excluded",
            size=ByteSize.parse(15_000_000_000),
            seeders=10,
            leechers=0,
            info_hash="deadbeef",
        )
        kept = _result(size=6_000_000_000)
        scored = rank(
            [excluded, kept],
            cfg,
            exclude_hashes=frozenset({"deadbeef"}),
            media_kind="movie",
        )
        assert len(scored) == 1
        assert scored[0][0] is kept
        # 6GB vs movie tiers: ≥4GB → 5
        assert scored[0][1] == 5

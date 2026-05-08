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

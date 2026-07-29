"""reswitch Phase 1 — seeders strengthened in the ranking score.

The operator asked that « le nombre de seeder doit influer sur le score d'une
release pour favoriser les releases les plus seedées ». Seeders already fed the
score (weight 1); this phase strengthens the seeder criterion (weight 2 + finer
thresholds) so a well-seeded release beats a poorly-seeded one at equal quality
and outweighs a single codec-tier difference — without a code change (the engine
is config-driven).

Two guards:
  * behaviour — ``rank()`` with the tuned criterion orders as intended;
  * config pin — the TRACKED template ``config.example/ranking.json5`` actually
    carries the strengthened weight/thresholds (else the "feature" never ships).
"""

from __future__ import annotations

from pathlib import Path

import json5

from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import (
    RankingConfig,
    RankingCriterion,
    ThresholdEntry,
    rank,
)

# The tuned seeder criterion (mirrors the config.example edit in this phase).
_SEEDERS = RankingCriterion(
    field="seeders",
    weight=2,
    prefer="higher",
    thresholds=[
        ThresholdEntry(at=0, score=0),
        ThresholdEntry(at=1, score=3),
        ThresholdEntry(at=5, score=8),
        ThresholdEntry(at=20, score=14),
        ThresholdEntry(at=50, score=18),
        ThresholdEntry(at=100, score=22),
    ],
)
# Codec criterion straight from the template (x265 > x264).
_CODEC = RankingCriterion(
    field="codec", weight=3, values={"x265": 10, "HEVC": 10, "x264": 5}
)
_RESOLUTION = RankingCriterion(
    field="resolution", weight=4, values={"2160p": 20, "1080p": 15, "720p": 10}
)
_TUNED = RankingConfig(
    criteria=[_RESOLUTION, _CODEC, _SEEDERS], min_seeders=1
)


def _result(*, seeders: int, codec: str = "x265", resolution: str = "1080p", tid: str = "t") -> TrackerResult:
    """A TrackerResult differing only on the fields under test."""
    return TrackerResult(
        provider="test",
        tracker_id=tid,
        title=f"Show S03E09 {resolution} {codec}",
        size=ByteSize(4_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution=resolution,
        codec=codec,
        info_hash=tid * 3,
        download_url=f"https://test/{tid}",
    )


def test_at_equal_quality_the_better_seeded_release_wins() -> None:
    """Same resolution+codec ⇒ the higher-seed release ranks strictly first."""
    low = _result(seeders=2, tid="a")
    high = _result(seeders=100, tid="b")
    ranked = rank([low, high], _TUNED)
    assert ranked[0][0] is high, f"expected the 100-seed release first; got {ranked}"
    assert ranked[0][1] > ranked[1][1]


def test_seeders_outweigh_a_codec_tier_at_equal_resolution() -> None:
    """A well-seeded x264 1080p beats a barely-seeded x265 1080p (operator intent).

    codec delta = 3*(10-5) = 15; seeder delta (2→100) = 2*(22-3) = 38 > 15.
    """
    seeded_x264 = _result(seeders=100, codec="x264", tid="a")
    starved_x265 = _result(seeders=2, codec="x265", tid="b")
    ranked = rank([starved_x265, seeded_x264], _TUNED)
    assert ranked[0][0] is seeded_x264, f"seeders must outweigh a codec tier; got {ranked}"


def test_zero_seed_release_is_dropped_by_min_seeders() -> None:
    """A 0-seed (dead) release never survives ranking (min_seeders floor)."""
    dead = _result(seeders=0, tid="a")
    alive = _result(seeders=10, tid="b")
    ranked = rank([dead, alive], _TUNED)
    assert [r for r, _ in ranked] == [alive]


def test_tracked_template_carries_the_strengthened_seeder_weight() -> None:
    """Config pin: config.example/ranking.json5 must ship weight 2 + tuned thresholds.

    Without this the behaviour above is only aspirational — the shipped default
    would still be weight 1.
    """
    example = Path(__file__).parents[2] / "config.example" / "ranking.json5"
    data = json5.loads(example.read_text(encoding="utf-8"))
    criteria = data["ranking"]["criteria"]
    seeders = next(c for c in criteria if c["field"] == "seeders")
    assert seeders["weight"] == 2, "seeder weight must be strengthened to 2"
    thresholds = {t["at"]: t["score"] for t in seeders["thresholds"]}
    # The tuned curve rewards high seed counts more steeply than the old 0/5/20/100.
    assert thresholds.get(100) == 22
    assert thresholds.get(50) == 18
    assert thresholds.get(1) == 3
    assert data["ranking"]["min_seeders"] == 1

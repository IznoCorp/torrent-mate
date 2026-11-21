"""K3 P10 — the ratio standing: where a tracker's ratio stands against its own economy.

``RatioStanding.classify`` is the one derivation (DESIGN § 2.10): ``under_floor`` below the
economy's ``min_ratio``, ``under_target`` below its ``target_ratio``, ``comfortable`` from there up,
``None`` when the tracker declares no economy or no ratio was ever observed. The orchestrator fills
``TrackerResult.tracker_ratio_state`` from it before ``rank()``; with no resolver wired (prod today,
nobody writes ``ratio_state`` until K5) every state stays ``None`` and no score moves (O-8 A).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import RatioState, WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.acquire.standing import RatioStanding
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig, RankingCriterion, ThresholdEntry
from personalscraper.conf.models.acquire import AcquireConfig, BandwidthConfig
from personalscraper.conf.models.api_config import TrackerEconomyConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.core.units import ByteSize

_ECONOMY = TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time="72h")


def _wanted() -> WantedItem:
    """Build a movie WantedItem the search chain accepts."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=11111),
        kind="movie",
        status="searching",
        enqueued_at=1_700_000_000,
        attempts=1,
    )


def _candidate(provider: str, seeders: int, *, group: str = "GRP") -> TrackerResult:
    """Build one takeable result of *provider*.

    Args:
        provider: The tracker's name.
        seeders: Its seeders.
        group: The release group; two results of one release (same group) are the dedup's to merge,
            so a test that needs two survivors names two groups.

    Returns:
        The result.
    """
    return TrackerResult(
        provider=provider,
        tracker_id=f"{provider}-1",
        title=f"Movie 2010 MULTi 1080p BluRay x265-{group}",
        size=ByteSize(5_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution="1080p",
        info_hash=provider.encode().hex().ljust(40, "0")[:40],
        download_url=f"https://{provider}.test/torrent/1",
    )


def _orchestrator(
    candidates: list[TrackerResult],
    ranking: RankingConfig,
    *,
    resolver: object | None = None,
) -> GrabOrchestrator:
    """Build an orchestrator whose tracker search yields *candidates*.

    Args:
        candidates: What the fake registry returns.
        ranking: The ranking configuration.
        resolver: The ``tracker_ratio_state_resolver`` to wire, or ``None`` to leave it unset
            (every caller before K3 P10).

    Returns:
        The orchestrator.
    """
    registry = MagicMock()
    registry.search_candidates.return_value = SearchOutcome(
        results=candidates,
        trackers_queried=len(candidates),
        trackers_errored=0,
    )
    extra: dict[str, object] = {} if resolver is None else {"tracker_ratio_state_resolver": resolver}
    return GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=None,
        event_bus=EventBus(),
        ranking=ranking,
        bandwidth=BandwidthConfig(),
        **extra,  # type: ignore[arg-type]
    )


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        A :class:`ConcreteAcquireStore`.
    """
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


class TestClassify:
    """Each threshold of ``RatioStanding.classify``."""

    def test_below_the_floor_is_under_floor(self) -> None:
        """An observed ratio under ``min_ratio`` is ``under_floor``."""
        assert RatioStanding.classify(0.5, _ECONOMY) == "under_floor"

    def test_at_the_floor_is_under_target(self) -> None:
        """The floor itself is not under it: ``observed == min_ratio`` is ``under_target``."""
        assert RatioStanding.classify(1.0, _ECONOMY) == "under_target"

    def test_between_floor_and_target_is_under_target(self) -> None:
        """Above the floor and below the target is ``under_target``."""
        assert RatioStanding.classify(1.99, _ECONOMY) == "under_target"

    def test_at_the_target_is_comfortable(self) -> None:
        """The target itself is reached: ``observed == target_ratio`` is ``comfortable``."""
        assert RatioStanding.classify(2.0, _ECONOMY) == "comfortable"

    def test_above_the_target_is_comfortable(self) -> None:
        """Above the target is ``comfortable``."""
        assert RatioStanding.classify(5.17, _ECONOMY) == "comfortable"

    def test_an_infinite_ratio_is_comfortable(self) -> None:
        """A tracker reports ``inf`` for an account that never downloaded: nothing owed."""
        assert RatioStanding.classify(math.inf, _ECONOMY) == "comfortable"

    def test_a_zero_floor_never_reads_under_floor(self) -> None:
        """With ``min_ratio = 0`` no observed ratio is below the floor."""
        economy = TrackerEconomyConfig(target_ratio=1.0, min_ratio=0.0, min_seed_time="1h")
        assert RatioStanding.classify(0.0, economy) == "under_target"

    def test_no_economy_is_none(self) -> None:
        """A tracker with no economy block has no policy: ``None`` whatever the ratio."""
        assert RatioStanding.classify(0.1, None) is None

    def test_no_observed_ratio_is_none(self) -> None:
        """No ratio ever observed: ``None``, never a guess."""
        assert RatioStanding.classify(None, _ECONOMY) is None

    def test_a_nan_ratio_is_none(self) -> None:
        """A NaN ratio is no observation: it compares false to everything, so it is ``None``."""
        assert RatioStanding.classify(math.nan, _ECONOMY) is None


class TestOf:
    """``RatioStanding.of(tracker)``: the store's ratio read through the tracker's economy."""

    @staticmethod
    def _state(tracker: str, ratio: float) -> RatioState:
        """Build a ``ratio_state`` row."""
        return RatioState(
            tracker_name=tracker,
            observed_ratio=ratio,
            accumulated_seed_time_s=0,
            hnr_count=0,
            updated_at=1_700_000_000,
        )

    def test_reads_the_stored_ratio_against_the_economy(self, store: ConcreteAcquireStore) -> None:
        """A stored ratio under the tracker's floor reads ``under_floor``."""
        store.ratio.upsert(self._state("c411", 0.4))

        standing = RatioStanding(store.ratio, {"c411": _ECONOMY})

        assert standing.of("c411") == "under_floor"

    def test_a_tracker_without_economy_is_none(self, store: ConcreteAcquireStore) -> None:
        """A stored ratio but no economy block for the tracker: ``None``."""
        store.ratio.upsert(self._state("tr4ker", 5.0))

        assert RatioStanding(store.ratio, {"c411": _ECONOMY}).of("tr4ker") is None

    def test_a_tracker_without_observed_ratio_is_none(self, store: ConcreteAcquireStore) -> None:
        """An economy but no ``ratio_state`` row (nobody writes one until K5): ``None``."""
        assert RatioStanding(store.ratio, {"c411": _ECONOMY}).of("c411") is None


class TestOrchestratorFill:
    """The orchestrator fills ``tracker_ratio_state`` before ``rank()``."""

    _RANKING = RankingConfig(
        criteria=[
            RankingCriterion(
                field="tracker_ratio_state",
                values={"under_floor": -50, "under_target": 0, "comfortable": 10},
            )
        ],
        min_seeders=0,
    )

    def test_the_state_reaches_the_ranking(self) -> None:
        """A criterion on the state lifts the comfortable tracker's release over the starved one's."""
        states = {"c411": "under_floor", "tr4ker": "comfortable"}
        orch = _orchestrator(
            [_candidate("c411", 99, group="AAA"), _candidate("tr4ker", 1, group="BBB")],
            self._RANKING,
            resolver=states.get,
        )

        verdict = orch.search(_wanted(), QualityProfile())

        assert verdict.chosen is not None
        assert verdict.chosen.provider == "tr4ker"
        assert verdict.chosen.tracker_ratio_state == "comfortable"

    def test_a_resolver_miss_leaves_the_state_none(self) -> None:
        """A tracker the resolver does not know stays ``None`` and scores 0 on that criterion."""
        orch = _orchestrator([_candidate("c411", 5)], self._RANKING, resolver={}.get)

        verdict = orch.search(_wanted(), QualityProfile())

        assert verdict.chosen is not None
        assert verdict.chosen.tracker_ratio_state is None

    def test_no_resolver_changes_nothing(self) -> None:
        """Unwired (every caller before P10): the field stays ``None`` and the order is the seeders'."""
        ranking = RankingConfig(
            criteria=[RankingCriterion(field="seeders", thresholds=[ThresholdEntry(at=1, score=10)])],
            min_seeders=0,
        )
        orch = _orchestrator([_candidate("c411", 5, group="AAA"), _candidate("tr4ker", 9, group="BBB")], ranking)

        verdict = orch.search(_wanted(), QualityProfile())

        assert verdict.chosen is not None
        assert verdict.chosen.tracker_ratio_state is None

    def test_a_ranking_without_the_criterion_never_asks_the_resolver(self) -> None:
        """No criterion names the field: the store behind the resolver is not read, nothing is copied."""
        asked: list[str] = []

        def resolver(tracker: str) -> str | None:
            asked.append(tracker)
            return "comfortable"

        ranking = RankingConfig(criteria=[RankingCriterion(field="resolution", values={"1080p": 5})], min_seeders=0)
        orch = _orchestrator([_candidate("c411", 5)], ranking, resolver=resolver)

        verdict = orch.search(_wanted(), QualityProfile())

        assert asked == []
        assert verdict.chosen is not None
        assert verdict.chosen.tracker_ratio_state is None

    def test_the_resolver_is_asked_once_per_tracker(self) -> None:
        """Two results of one tracker cost one standing read."""
        asked: list[str] = []

        def resolver(tracker: str) -> str | None:
            asked.append(tracker)
            return "under_target"

        first = _candidate("c411", 5)
        second = replace(
            first, tracker_id="c411-2", title=first.title.replace("GRP", "ZZZ"), info_hash="c" * 40, seeders=6
        )
        orch = _orchestrator([first, second], self._RANKING, resolver=resolver)

        orch.search(_wanted(), QualityProfile())

        assert asked == ["c411"]

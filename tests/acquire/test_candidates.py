"""The search pass persists the candidates of a concluded search (K3 P9b, DESIGN O-7 = A).

A concluded search replaces the wanted row's whole candidate set: the ranked survivors, the best
twenty, each numbered by :class:`~personalscraper.acquire.numbering.ReleaseNumbering`. A search
that did not conclude (an outage, ``found`` NULL) leaves the previous set as it was. The ranking
and the release the grab takes are not touched: the search verdict only carries what it ranked.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.desired import QualityProfile
from personalscraper.acquire.domain import FollowedSeries, WantedCandidate, WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator, SearchVerdict
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.conf.models.acquire import AcquireConfig, BandwidthConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.core.units import ByteSize

_ENQUEUED_AT = 1_700_000_000
_PINNED_NOW = _ENQUEUED_AT + 3600
_REF = MediaRef(tvdb_id=99)


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _pin_service_clock() -> Iterator[None]:
    """Pin ``service.time.time`` so the fixture rows stay due and ``searched_at`` is known."""
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        yield


def _result(title: str, *, info_hash: str, seeders: int = 50, provider: str = "c411") -> TrackerResult:
    """Build a tracker result carrying the facts a candidate keeps.

    Args:
        title: The release's title.
        info_hash: Its info-hash.
        seeders: Its seeders.
        provider: The tracker that offered it.

    Returns:
        The result.
    """
    return TrackerResult(
        provider=provider,
        tracker_id=f"t-{info_hash}",
        title=title,
        size=ByteSize(5_000_000_000),
        seeders=seeders,
        leechers=0,
        source="WEB",
        resolution="1080p",
        language="MULTI",
        info_hash=info_hash,
        download_url=f"https://{provider}.test/torrent/{info_hash}",
    )


def _available(*ranked: tuple[TrackerResult, int]) -> SearchVerdict:
    """Build an ``available`` verdict over ranked ``(result, score)`` pairs.

    Args:
        *ranked: The ranked pairs, best first.

    Returns:
        The verdict, its ``chosen`` the first result.
    """
    return SearchVerdict(
        disposition="available",
        outcome="available",
        found=len(ranked),
        chosen=ranked[0][0] if ranked else None,
        ranked=tuple(ranked),
    )


def _follow(store: ConcreteAcquireStore) -> int:
    """Return the rowid of the show's follow, adding it on first use (``add`` merges a repeat).

    Args:
        store: The acquire store.

    Returns:
        The follow's rowid.
    """
    return store.follow.add(FollowedSeries(media_ref=_REF, title="Severance", added_at=1))


def _add(store: ConcreteAcquireStore, *, kind: str, season: int | None = None, episode: int | None = None) -> int:
    """Insert a pending wanted row of a followed show.

    Args:
        store: The acquire store.
        kind: ``"episode"`` or ``"season"``.
        season: The season number.
        episode: The episode number.

    Returns:
        The row's rowid.
    """
    fid = _follow(store)
    return store.wanted.add(
        WantedItem(
            media_ref=_REF,
            kind=kind,  # type: ignore[arg-type]
            status="pending",
            enqueued_at=_ENQUEUED_AT,
            followed_id=fid,
            season=season,
            episode=episode,
        )
    )


def _seed_aired(store: ConcreteAcquireStore, season: int, count: int) -> None:
    """Seed the aired-episode cache with *count* episodes of *season*.

    Args:
        store: The acquire store.
        season: The season number.
        count: How many episodes aired.
    """
    fid = _follow(store)
    store.aired.replace_for_followed(
        fid, [(season, n, f"E{n}", f"2024-01-{n:02d}") for n in range(1, count + 1)], now=_ENQUEUED_AT
    )


def _search(store: ConcreteAcquireStore, verdict: SearchVerdict) -> None:
    """Run one search pass whose orchestrator answers *verdict*.

    Args:
        store: The acquire store.
        verdict: What the orchestrator concludes.
    """
    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = verdict
    config = MagicMock()
    config.acquire = AcquireConfig()
    AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orch,  # type: ignore[arg-type]
        event_bus=MagicMock(),
        config=config,
    ).run_search()


def _stored(store: ConcreteAcquireStore, wanted_id: int) -> list[WantedCandidate]:
    """Read the candidate set of a wanted row.

    Args:
        store: The acquire store.
        wanted_id: The wanted row's rowid.

    Returns:
        Its candidates, best rank first.
    """
    return store.candidates.list_for(wanted_id)


def _seed_previous(store: ConcreteAcquireStore, wanted_id: int) -> None:
    """Store a one-candidate set a later search must replace or leave.

    Args:
        store: The acquire store.
        wanted_id: The wanted row's rowid.
    """
    store.candidates.replace(
        wanted_id,
        [
            WantedCandidate(
                rank=1,
                provider="c411",
                title="Severance S02E05 OLD",
                info_hash="old",
                size_bytes=1,
                seeders=1,
                resolution=None,
                source=None,
                language=None,
                score=1,
                season=2,
                episode=5,
                searched_at=1,
            )
        ],
    )


def test_a_concluded_search_stores_its_ranked_survivors(store: ConcreteAcquireStore) -> None:
    """Each ranked survivor becomes a candidate: rank from 1, the result's facts, the score."""
    wid = _add(store, kind="episode", season=2, episode=5)
    best = _result("Severance S02E05 MULTi 1080p WEB-DL", info_hash="aaa", seeders=80, provider="c411")
    other = _result("Severance S02E05 VOSTFR 720p WEB", info_hash="bbb", seeders=7, provider="tr4ker")

    _search(store, _available((best, 90), (other, 40)))

    got = _stored(store, wid)
    assert [(c.rank, c.info_hash, c.score) for c in got] == [(1, "aaa", 90), (2, "bbb", 40)]
    first = got[0]
    assert (first.provider, first.title, first.size_bytes, first.seeders) == (
        "c411",
        "Severance S02E05 MULTi 1080p WEB-DL",
        5_000_000_000,
        80,
    )
    assert (first.resolution, first.source, first.language, first.searched_at) == (
        "1080p",
        "WEB",
        "MULTI",
        _PINNED_NOW,
    )


def test_a_concluded_search_replaces_the_previous_set(store: ConcreteAcquireStore) -> None:
    """The new set stands alone: the earlier candidates are gone."""
    wid = _add(store, kind="episode", season=2, episode=5)
    _seed_previous(store, wid)

    _search(store, _available((_result("Severance S02E05 1080p", info_hash="new"), 10)))

    assert [c.info_hash for c in _stored(store, wid)] == ["new"]


def test_a_concluded_search_that_found_nothing_clears_the_set(store: ConcreteAcquireStore) -> None:
    """``not_found`` is knowledge (« I looked, nothing »): the previous set is cleared."""
    wid = _add(store, kind="episode", season=2, episode=5)
    _seed_previous(store, wid)

    _search(store, SearchVerdict(disposition="not_found", outcome="all_filtered", found=0))

    assert _stored(store, wid) == []


@pytest.mark.parametrize(
    "outcome",
    ["circuit_open", "search_api_error", "trackers_unavailable", "trackers_degraded", "no_seeders"],
)
def test_an_inconclusive_search_leaves_the_set_untouched(store: ConcreteAcquireStore, outcome: str) -> None:
    """An outage is not knowledge (``found`` NULL): the previous set stays as it was."""
    wid = _add(store, kind="episode", season=2, episode=5)
    _seed_previous(store, wid)

    _search(store, SearchVerdict(disposition="retryable", outcome=outcome, found=None))

    assert [c.info_hash for c in _stored(store, wid)] == ["old"]


def test_only_the_best_twenty_are_stored(store: ConcreteAcquireStore) -> None:
    """The ranked list is cut at twenty, the best ranks kept."""
    wid = _add(store, kind="episode", season=2, episode=5)
    ranked = [(_result("Severance S02E05 1080p", info_hash=f"h{n:02d}"), 100 - n) for n in range(25)]

    _search(store, _available(*ranked))

    got = _stored(store, wid)
    assert [c.rank for c in got] == list(range(1, 21))
    assert got[-1].info_hash == "h19"


def test_an_episode_candidate_carries_its_season_and_episode(store: ConcreteAcquireStore) -> None:
    """An episode, a multi-episode span and a pack are each numbered as the name reads."""
    wid = _add(store, kind="episode", season=9, episode=5)
    ranked = (
        (_result("Show S09E05 1080p", info_hash="one"), 3),
        (_result("Show S09E05-E06 1080p", info_hash="span"), 2),
        (_result("Show S09 COMPLETE 1080p", info_hash="pack"), 1),
    )

    _search(store, _available(*ranked))

    assert [(c.info_hash, c.season, c.episode) for c in _stored(store, wid)] == [
        ("one", 9, 5),
        ("span", 9, 5),
        ("pack", 9, None),
    ]


def test_a_season_row_stores_a_full_span_as_a_pack(store: ConcreteAcquireStore) -> None:
    """DESIGN § 2.9: the season's aired count makes ``S02E01-E12`` of a 12-episode season a pack."""
    wid = _add(store, kind="season", season=2)
    _seed_aired(store, season=2, count=12)

    _search(store, _available((_result("Show S02E01-E12 1080p", info_hash="span"), 5)))

    got = _stored(store, wid)
    assert [(c.season, c.episode) for c in got] == [(2, None)]


def test_a_season_row_without_an_aired_count_numbers_a_span_by_its_first_episode(
    store: ConcreteAcquireStore,
) -> None:
    """An empty aired cache gives no count: the span keeps its first episode."""
    wid = _add(store, kind="season", season=2)

    _search(store, _available((_result("Show S02E01-E12 1080p", info_hash="span"), 5)))

    assert [(c.season, c.episode) for c in _stored(store, wid)] == [(2, 1)]


def test_an_episode_row_never_reads_a_span_as_a_pack(store: ConcreteAcquireStore) -> None:
    """For an episode row no count is passed, even when its season is fully cached."""
    wid = _add(store, kind="episode", season=2, episode=1)
    _seed_aired(store, season=2, count=12)

    _search(store, _available((_result("Show S02E01-E12 1080p", info_hash="span"), 5)))

    assert [(c.season, c.episode) for c in _stored(store, wid)] == [(2, 1)]


class _FixedTracker:
    """Tracker stub answering every search with the same results."""

    def __init__(self, results: list[TrackerResult]) -> None:
        self._results = results

    def search(self, query: str, media_type: object = None, year: int | None = None) -> list[TrackerResult]:
        """Return the configured results.

        Args:
            query: Ignored.
            media_type: Ignored.
            year: Ignored.

        Returns:
            The results.
        """
        return list(self._results)

    def get_categories(self) -> dict[str, str]:
        """Return no categories (unused here)."""
        return {}


def test_the_verdict_carries_the_ranking_the_grab_takes_from() -> None:
    """The verdict's ``ranked`` is the chain's own ranking: its first pair is ``chosen``, count ``found``."""
    results = [
        _result("Inception 2010 1080p", info_hash="low", seeders=5),
        _result("Inception 2010 1080p", info_hash="high", seeders=500, provider="tr4ker"),
    ]
    registry = TrackerRegistry(
        trackers={"c411": _FixedTracker(results[:1]), "tr4ker": _FixedTracker(results[1:])},  # type: ignore[dict-item]
        priority=["c411", "tr4ker"],
        ranking=RankingConfig(min_seeders=0),
    )
    orchestrator = GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=None,
        event_bus=EventBus(),
        ranking=RankingConfig(min_seeders=0),
        bandwidth=BandwidthConfig(),
    )
    movie = WantedItem(media_ref=MediaRef(tmdb_id=1), kind="movie", status="searching", enqueued_at=1, id=1)

    verdict = orchestrator.search(movie, QualityProfile())

    assert verdict.outcome == "available"
    assert verdict.found == len(verdict.ranked) >= 1
    assert verdict.chosen is verdict.ranked[0][0]


def test_a_row_deleted_during_the_search_does_not_abort_the_pass(store: ConcreteAcquireStore) -> None:
    """The follow is unfollowed mid-search: its row is gone, the candidates are skipped, the pass goes on."""
    wid = _add(store, kind="episode", season=2, episode=5)
    fid = _follow(store)
    verdict = _available((_result("Severance S02E05 1080p", info_hash="aaa"), 10))
    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.side_effect = lambda *_a, **_k: (store.follow.delete(fid), verdict)[1]
    config = MagicMock()
    config.acquire = AcquireConfig()

    AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orch,  # type: ignore[arg-type]
        event_bus=MagicMock(),
        config=config,
    ).run_search()

    assert store.wanted.get(wid) is None
    assert _stored(store, wid) == []

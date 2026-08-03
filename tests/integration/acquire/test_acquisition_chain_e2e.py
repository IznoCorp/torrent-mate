"""End-to-end acquisition chain: follow → detect → search → grab, ONE real store.

Every acquisition step is unit-tested in isolation with its neighbour mocked
(``test_service`` mocks the orchestrator; ``test_orchestrator`` mocks the
registry + client). Nothing wires the REAL ``GrabOrchestrator`` into the REAL
``DetectService`` / ``AcquisitionService`` over one real ``acquire.db`` — so
cross-pass wiring drift (the class that produced the Wicker #28 wrong-movie grab
and the STSNW #29 stuck scrape) is invisible to the unit suite.

This test drives the whole chain with only the two genuine externals faked — the
tracker registry (canned search results) and the torrent client (a protocol
double) — proving:
  * detect enqueues a wanted row from a follow,
  * the real search pass concludes it ``available`` (identity filters included),
  * the real grab pass sends it to the client and persists ``grabbed`` + hash,
  * and the ``#28`` movie-identity guard drops a wrong-year release END-TO-END.

Integration tier (only the network is faked): default suite, ≤20s.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.acquire.desired import QualityProfile, Resolution, quality_profile_to_json
from personalscraper.acquire.detect import DetectService
from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.events import GrabSucceeded, WantedEnqueued
from personalscraper.acquire.orchestrator import GrabOrchestrator
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._units import ByteSize
from personalscraper.api.torrent._base import TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.conf.models.acquire import AcquireConfig, BandwidthConfig, CadenceConfig
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.core.identity import MediaRef

# Pinned clock: 1h after the follow's detect time so the fresh wanted row is DUE
# in the Hot cadence tier and inside the cutoff (mirrors test_service.py's pin).
_DETECT_NOW = 1_700_000_000
_PINNED_NOW = _DETECT_NOW + 3600


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


class _StubOwnership:
    """Ownership stub: owns exactly the media_refs it was given (none here)."""

    def __init__(self, owned: set[MediaRef]) -> None:
        self._owned = owned

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        return media_ref in self._owned


class _EventSpy:
    """Capturing subscriber: records every Event it receives, in order."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def __call__(self, event: Event) -> None:
        self.events.append(event)


def _config() -> SimpleNamespace:
    """Minimal config exposing only ``acquire.cadence`` (all the services read)."""
    return SimpleNamespace(acquire=SimpleNamespace(cadence=CadenceConfig()))


def _movie_result(title: str, info_hash: str, seeders: int = 50) -> TrackerResult:
    """A conforming 1080p movie release from a fake tracker."""
    return TrackerResult(
        provider="lacale",
        tracker_id=info_hash,
        title=title,
        size=ByteSize(5_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution="1080p",
        info_hash=info_hash,
        download_url=f"https://lacale.test/torrent/{info_hash}",
    )


def _fake_registry(results: list[TrackerResult]) -> MagicMock:
    """A registry that returns canned results and one transport (fresh at grab)."""
    registry = MagicMock()
    registry.search_candidates.return_value = SearchOutcome(results=results, trackers_queried=1, trackers_errored=0)
    registry.transports.return_value = {"lacale": MagicMock()}
    return registry


def _real_orchestrator(
    store: ConcreteAcquireStore,
    registry: MagicMock,
    torrent_client: object,
    bus: EventBus,
) -> GrabOrchestrator:
    """A REAL GrabOrchestrator with title/year resolvers read from the follow.

    Mirrors ``_factory.build_acquire_context`` wiring: the resolvers read the
    follow's title/year so the movie query is « {title} {year} » and the #28
    movie-identity filter has a year to check against.
    """

    def title_resolver(item: WantedItem) -> str | None:
        if item.followed_id is None:
            return None
        follow = store.follow.get(item.followed_id)
        return follow.title if follow else None

    def year_resolver(item: WantedItem) -> int | None:
        if item.followed_id is None:
            return None
        follow = store.follow.get(item.followed_id)
        return follow.year if follow else None

    return GrabOrchestrator(
        tracker_registry=registry,
        torrent_client=torrent_client,  # type: ignore[arg-type]
        event_bus=bus,
        ranking=RankingConfig(min_seeders=0),
        title_resolver=title_resolver,
        year_resolver=year_resolver,
        bandwidth=BandwidthConfig(),
    )


def _follow_movie(store: ConcreteAcquireStore, *, title: str, year: int, tmdb_id: int) -> int:
    """Add a followed MOVIE with a permissive 720p-floor profile; return its id.

    NOTE (faithful to production): ``follow.add`` does NOT persist ``year`` — the
    INSERT omits the column — so the year the #28 identity filter reads is written
    separately by ``merge_metadata`` (the add-by-search candidate / provider
    enrichment path). Seeding via ``add`` alone leaves ``year`` NULL and the
    filter inert; we mirror the real write so the chain exercises #28 for real.
    """
    fid = store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tmdb_id=tmdb_id),
            title=title,
            added_at=_DETECT_NOW,
            kind="movie",
            year=year,
            quality_profile_json=quality_profile_to_json(QualityProfile(min_resolution=Resolution.R720P)),
        )
    )
    store.follow.merge_metadata(fid, poster_url=None, overview=None, year=year)
    return fid


def _detect(store: ConcreteAcquireStore, bus: EventBus) -> None:
    """Run the real detect pass (enqueues the followed film as a wanted row)."""
    DetectService(
        store=store,
        ownership=_StubOwnership(set()),
        registry=MagicMock(),
        event_bus=bus,
        config=_config(),
    ).run(series=None, dry_run=False, today=date(2010, 7, 16), now=_DETECT_NOW)


class TestFullAcquisitionChain:
    """follow → detect → search → grab over one real acquire.db."""

    def test_movie_chain_detect_search_grab(self, store: ConcreteAcquireStore) -> None:
        """A followed film flows detect→search→grab to a persisted grabbed hash."""
        bus = EventBus()
        spy = _EventSpy()
        bus.subscribe(Event, spy)

        fid = _follow_movie(store, title="Inception", year=2010, tmdb_id=27205)

        # 1) DETECT — the film becomes a pending wanted row.
        _detect(store, bus)
        wanted = store.wanted.find(followed_id=fid, kind="movie", season=None, episode=None)
        assert wanted is not None
        assert wanted.status == "pending"
        assert any(isinstance(e, WantedEnqueued) for e in spy.events)

        # Real orchestrator + fake registry (one conforming release) + fake client.
        adder = MagicMock(spec=TorrentAdder)
        adder.add.return_value = "grab-hash-01"
        registry = _fake_registry([_movie_result("Inception.2010.MULTi.1080p.BluRay.x265-GRP", "grab-hash-01")])
        orch = _real_orchestrator(store, registry, adder, bus)
        service = AcquisitionService(store=store, orchestrator=orch, event_bus=bus, config=_config())

        with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
            # 2) SEARCH — the row is concluded available (identity filters pass).
            service.run_search(limit=10)
            searched = store.wanted.find(followed_id=fid, kind="movie", season=None, episode=None)
            assert searched is not None
            assert searched.status == "available", f"search did not conclude available: {searched.status}"

            # 3) GRAB — the row is sent to the client and persisted grabbed + hash.
            # resolve_source (the real .torrent byte-fetch over HTTP) is the one
            # network externality faked at this tier — everything else is real.
            with patch(
                "personalscraper.acquire.orchestrator.resolve_source",
                return_value=MagicMock(spec=TorrentSource),
            ):
                # F3: the grab command passes its CliRunRecorder.run_uid down to the pass.
                summary = service.run(limit=10, run_uid="grabRUN01")

        assert summary.grabbed == 1
        grabbed = store.wanted.find(followed_id=fid, kind="movie", season=None, episode=None)
        assert grabbed is not None
        assert grabbed.status == "grabbed"
        assert grabbed.grabbed_hash == "grab-hash-01"
        adder.add.assert_called_once()
        assert any(isinstance(e, GrabSucceeded) for e in spy.events)

        # Phase 2 (provenance): the grab seeded a provenance row carrying the wanted
        # identity — the deterministic scrape seed for #30.
        prov = store.provenance.by_hash("grab-hash-01")
        assert prov is not None and prov.status == "grabbed"
        assert prov.media_ref == MediaRef(tmdb_id=27205)
        # F3 run-linkage: the grab stage stamped its own pipeline_run.run_uid.
        assert prov.grab_run_uid == "grabRUN01"

    def test_movie_chain_rejects_wrong_year_release(self, store: ConcreteAcquireStore) -> None:
        """#28 END-TO-END: a wrong-year « Wicker » release is filtered, not grabbed.

        The tracker returns ONLY a different-year film for a « Wicker » (2026)
        follow; the real ``filter_to_movie`` year guard must drop it at SEARCH
        time, so the row never concludes ``available`` and the client is never
        called.

        The load-bearing assertion is on the SEARCH pass's own conclusion
        (``status='pending'`` + ``all_filtered`` + zero found), NOT merely on
        ``grabbed==0``: the grab would fail anyway (the fake transport can't be
        fetched), so a grab-only assertion would stay green even if the year
        filter regressed — the exact #28 bug would ship undetected. Asserting the
        search verdict fails the instant ``filter_to_movie`` stops dropping the
        wrong-year film, independent of the grab path.
        """
        bus = EventBus()
        fid = _follow_movie(store, title="Wicker", year=2026, tmdb_id=1195803)
        _detect(store, bus)

        adder = MagicMock(spec=TorrentAdder)
        # Wrong film: « The Wicker Man » (2006), massively seeded — must NOT win.
        registry = _fake_registry(
            [_movie_result("The.Wicker.Man.2006.1080p.BluRay.x264-OLD", "wrong-hash", seeders=9999)]
        )
        orch = _real_orchestrator(store, registry, adder, bus)
        service = AcquisitionService(store=store, orchestrator=orch, event_bus=bus, config=_config())

        with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
            service.run_search(limit=10)
            # SEARCH pass isolates the year filter: a broken filter would conclude
            # « available » with found>=1 here, failing cleanly.
            searched = store.wanted.find(followed_id=fid, kind="movie", season=None, episode=None)
            assert searched is not None
            assert searched.status == "pending", "wrong-year-only search must NOT conclude available"
            assert searched.last_search_outcome == "all_filtered"
            assert searched.last_search_found == 0

            summary = service.run(limit=10)

        assert summary.grabbed == 0, "a wrong-year film must never be grabbed"
        adder.add.assert_not_called()
        row = store.wanted.find(followed_id=fid, kind="movie", season=None, episode=None)
        assert row is not None
        assert row.status != "grabbed"
        assert row.grabbed_hash is None
        # ACC-06: nothing was grabbed → NO provenance row was ever created.
        assert store.provenance.by_hash("wrong-hash") is None

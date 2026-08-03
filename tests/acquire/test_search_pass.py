"""Test-first: the search pass (run_search) states availability; it never downloads.

These tests INTENTIONALLY FAIL today (ImportError / AttributeError) — the
``SearchVerdict``, ``SearchRunSummary``, and ``run_search`` API do not exist
yet. Sub-phase 2.3 implements them. Do NOT mark xfail/skip.

Design: contract_phase2.md § orchestrator.search → SearchVerdict (no
torrent-client use, no add, no emit) and § service.run_search →
SearchRunSummary.  The plan is phase-02-search-grab-split.md §2.1.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import SeasonAbsorbedEpisodes, WantedEnqueued
from personalscraper.acquire.orchestrator import GrabOrchestrator, SearchVerdict
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

# ---------------------------------------------------------------------------
# Reuse the house patterns from test_service.py.
# ---------------------------------------------------------------------------


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


# Pinned service clock: 1h after the items' enqueued_at (1_700_000_000). With
# the default Hot/Warm/Cold/30d cadence this puts every _pending_item in the Hot
# tier (age 1h < 72h) and well within the 30d cutoff, so a fresh row
# (last_search_at is None) is DUE immediately. Without the pin the wall clock is
# years past the cutoff and every item would age out before being searched.
_PINNED_NOW = 1_700_003_600  # enqueued_at + 3600s


@pytest.fixture(autouse=True)
def _pin_service_clock() -> Iterator[None]:
    """Pin ``service.time.time`` so the fixture rows stay due."""
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        yield


def _pending_item(tvdb_id: int = 99) -> WantedItem:
    """Minimal pending WantedItem — mirrors test_service._pending_item."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind="movie",
        status="pending",
        enqueued_at=1_700_000_000,
    )


def _takeable_result(
    provider: str = "c411",
    info_hash: str = "aaaa1234",
    seeders: int = 50,
) -> TrackerResult:
    """A tracker result that will survive hard-filter + dedup + ranking."""
    return TrackerResult(
        provider=provider,
        tracker_id="t1",
        title="Inception 2010 MULTi 1080p BluRay x265-GRP",
        size=ByteSize(5_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution="1080p",
        info_hash=info_hash,
        download_url=f"https://{provider}.test/torrent/1",
    )


def _service(store: ConcreteAcquireStore, orchestrator: GrabOrchestrator) -> AcquisitionService:
    """Build a service with a (mock) event_bus — mirrors test_service._service."""
    config = MagicMock()
    config.acquire = AcquireConfig()
    return AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=MagicMock(),
        config=config,
    )


# ---------------------------------------------------------------------------
# THE tests — intentionally failing until 2.3 implements the contract.
# ---------------------------------------------------------------------------


def test_search_pass_adds_no_torrent(store: ConcreteAcquireStore) -> None:
    """The search pass states availability; it never downloads.

    Separating search from grab is the whole point: while they were one atomic
    operation, « À récupérer » existed for milliseconds inside a single function
    call and the operator could never see what was available but not yet taken.
    """
    store.wanted.add(_pending_item())

    # A fake torrent client that RECORDS every add() call. Wire it into the
    # mock orchestrator so if run_search() ever reaches through to
    # orchestrator._torrent_client.add(), the spy catches it.
    fake_client = MagicMock()

    orch = MagicMock(spec=GrabOrchestrator)
    orch._torrent_client = fake_client
    orch.search.return_value = SearchVerdict(
        disposition="available",
        outcome="available",
        found=3,
        chosen=_takeable_result(),
    )

    service = _service(store, orch)
    summary = service.run_search()

    # The flagship invariant: the torrent client was NEVER asked to add.
    fake_client.add.assert_not_called()

    # The item is now known-available (not still pending, not grabbed).
    assert summary.available == 1
    pending = store.wanted.list_pending()
    assert not any(i.media_ref.tvdb_id == 99 for i in pending), "a takeable item must leave the pending queue"

    available = store.wanted.list_available()
    assert len(available) == 1
    assert available[0].status == "available"
    assert available[0].last_search_outcome == "available"
    assert available[0].last_search_found == 3


def test_search_pass_records_available_verdict(store: ConcreteAcquireStore) -> None:
    """After run_search on a takeable item, the store row carries the verdict.

    The persisted triple (status, last_search_outcome, last_search_found)
    must match the contract: status='available', outcome='available',
    found == number of takeable candidates.
    """
    rowid = store.wanted.add(_pending_item())

    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="available",
        outcome="available",
        found=5,
        chosen=_takeable_result(info_hash="bbbb5678"),
    )

    service = _service(store, orch)
    summary = service.run_search()

    assert summary.available == 1

    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "available", f"expected status='available' after a takeable search; got {item.status!r}"
    assert item.last_search_outcome == "available"
    assert item.last_search_found == 5, (
        f"found must equal the count passed by the orchestrator; got {item.last_search_found}"
    )


def test_search_pass_works_without_torrent_client(store: ConcreteAcquireStore) -> None:
    """Service constructed with torrent_client=None still runs run_search successfully.

    The search pass must not require the client — the orchestrator's search()
    chain (build_search_query → search_candidates → filter → dedup → rank)
    never touches it.  A service built without one must complete the pass and
    persist the verdict.
    """
    store.wanted.add(_pending_item())

    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="available",
        outcome="available",
        found=1,
        chosen=_takeable_result(),
    )

    service = _service(store, orch)
    # Must NOT raise — the search pass has no dependency on the torrent client.
    summary = service.run_search()

    assert summary.available == 1
    available = store.wanted.list_available()
    assert len(available) == 1


# ---------------------------------------------------------------------------
# R2: Episode→Season Conversion tests
# ---------------------------------------------------------------------------


def _episode_item(
    tvdb_id: int = 99,
    season: int = 3,
    episode: int = 5,
    followed_id: int = 1,
) -> WantedItem:
    """Minimal pending episode WantedItem for conversion tests."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind="episode",
        status="pending",
        enqueued_at=1_700_000_000,
        followed_id=followed_id,
        season=season,
        episode=episode,
    )


def _season_pack_result(title: str = "Show S03E01-E12 COMPLETE 1080p") -> TrackerResult:
    """A tracker result that ``filter_to_season`` keeps."""
    return TrackerResult(
        provider="c411",
        tracker_id="t99",
        title=title,
        size=ByteSize(20_000_000_000),
        seeders=100,
        leechers=0,
        resolution="1080p",
        info_hash="seasonpack99",
        download_url="https://c411.test/torrent/99",
    )


def test_conversion_enqueues_season_when_pack_present(store: ConcreteAcquireStore) -> None:
    """R2: episode search 0-exact + pack present → season wanted enqueued.

    When an episode search returns ``no_matching_episode`` with raw_results
    carrying a whole-season pack, the search pass enqueues a season wanted
    (kind=season, status=pending), absorbs the episode's live siblings, and
    returns ``waiting``.
    """
    from personalscraper.acquire.domain import FollowedSeries

    # Create the parent followed series so the FK resolves.
    store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=99),
            title="Test Show",
            added_at=1,
        )
    )

    item = _episode_item()
    store.wanted.add(item)

    # Seed the aired catalog so _aired_episodes_for_season returns live eps.
    store.aired.replace_for_followed(
        1,
        [
            (3, 1, "E01", "2024-01-01"),
            (3, 2, "E02", "2024-01-08"),
            (3, 3, "E03", "2024-01-15"),
            (3, 4, "E04", "2024-01-22"),
            (3, 5, "E05", "2024-01-29"),
        ],
        now=1_700_000_000,
    )
    # Create sibling episode wanteds (episodes 1-4) that should be absorbed.
    for ep_num in (1, 2, 3, 4):
        store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=99),
                kind="episode",
                status="pending",
                enqueued_at=1_700_000_000,
                followed_id=1,
                season=3,
                episode=ep_num,
            ),
        )

    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="not_found",
        outcome="no_matching_episode",
        found=0,
        raw_results=(_season_pack_result(),),
    )

    event_bus = MagicMock()
    config = MagicMock()
    config.acquire = AcquireConfig()
    svc = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orch,  # type: ignore[arg-type]
        event_bus=event_bus,  # type: ignore[arg-type]
        config=config,
    )
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        svc.run_search()

    # The season wanted should exist.
    season_item = store.wanted.find(
        followed_id=1,
        kind="season",
        season=3,
        episode=None,
    )
    assert season_item is not None, "season wanted must be enqueued"
    assert season_item.kind == "season"
    assert season_item.status == "pending"

    # WantedEnqueued must have been emitted for the season.
    enqueued_calls = [
        c for c in event_bus.emit.call_args_list if isinstance(c[0][0], WantedEnqueued) and c[0][0].kind == "season"
    ]
    assert len(enqueued_calls) >= 1, "WantedEnqueued(season) must be emitted"

    # SeasonAbsorbedEpisodes must have been emitted.
    absorbed_calls = [c for c in event_bus.emit.call_args_list if isinstance(c[0][0], SeasonAbsorbedEpisodes)]
    assert len(absorbed_calls) >= 1, "SeasonAbsorbedEpisodes must be emitted"

    # The converted season wanted absorbs the triggering episode + its siblings.
    absorbed_event = absorbed_calls[0][0][0]
    assert len(absorbed_event.absorbed_ids) >= 1


def test_conversion_with_empty_aired_cache_absorbs_triggering_episode(store: ConcreteAcquireStore) -> None:
    """F12 REGRESSION: an empty aired cache must not leave the trigger spinning.

    Absorption iterates the aired-episode cache; when it is empty for the
    follow, even the TRIGGERING episode (just claimed 'searching') used to
    escape absorption and oscillate forever with a stale verdict. It must end
    ``absorbed``, with its triggering verdict recorded.
    """
    from personalscraper.acquire.domain import FollowedSeries

    store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=99), title="Test Show", added_at=1))
    # NO aired cache seeded — _aired_episodes_for_season returns [].

    ep_wid = store.wanted.add(_episode_item())

    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="not_found",
        outcome="no_matching_episode",
        found=0,
        # Bare-season pack (no episode markers) — identifiable without a
        # known episode count.
        raw_results=(_season_pack_result(title="Show S03 COMPLETE 1080p"),),
    )
    event_bus = MagicMock()
    config = MagicMock()
    config.acquire = AcquireConfig()
    svc = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orch,  # type: ignore[arg-type]
        event_bus=event_bus,  # type: ignore[arg-type]
        config=config,
    )
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        svc.run_search()

    row = store.wanted.get(ep_wid)
    assert row is not None
    assert row.status == "absorbed", f"triggering episode must be absorbed, got {row.status!r}"
    # The triggering verdict was recorded BEFORE absorption — no stale verdict.
    assert row.last_search_outcome == "no_matching_episode"
    assert row.last_search_found == 0

    season_item = store.wanted.find(followed_id=1, kind="season", season=3, episode=None)
    assert season_item is not None and season_item.status == "pending"
    assert row.absorbed_by == season_item.id

    absorbed_calls = [c for c in event_bus.emit.call_args_list if isinstance(c[0][0], SeasonAbsorbedEpisodes)]
    assert len(absorbed_calls) == 1
    assert absorbed_calls[0][0][0].absorbed_ids == (ep_wid,)


def test_conversion_refused_on_terminal_season_row_keeps_episodes_live(store: ConcreteAcquireStore) -> None:
    """F1 REGRESSION: R6→R2 ping-pong must not starve the season.

    Proved scenario: a season row at ``fallback_episodes`` + freshly
    re-enqueued pending episodes (R6) + a season pack visible in the raw
    results. The conversion used to reuse the terminal season row and absorb
    the fresh episodes onto it — whole season permanently lost, queue empty.

    After the fix: the episodes are STILL open (not absorbed), the season row
    is still ``fallback_episodes``, no new season row is minted, and the
    pending queue is non-empty.
    """
    from personalscraper.acquire.domain import FollowedSeries

    store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=99), title="Test Show", added_at=1))
    store.aired.replace_for_followed(
        1,
        [(3, n, f"E0{n}", f"2024-01-{n:02d}") for n in range(1, 6)],
        now=1_700_000_000,
    )

    # The season's FIRST life: episode rows absorbed by a season wanted...
    old_ep_ids = [store.wanted.add(_episode_item(episode=n)) for n in range(1, 6)]
    season_wid = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=99),
            kind="season",
            status="pending",
            enqueued_at=1_700_000_000,
            followed_id=1,
            season=3,
            episode=None,
        ),
    )
    store.wanted.absorb_episodes(season_wid, tuple(old_ep_ids))
    # ...then the season hit its cutoff: R6 fallback + fresh episode re-enqueues.
    assert store.wanted.fallback_season(season_wid) is True
    fresh_ep_ids = [store.wanted.add(_episode_item(episode=n)) for n in range(1, 6)]

    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="not_found",
        outcome="no_matching_episode",
        found=0,
        raw_results=(_season_pack_result(),),  # a pack IS visible
    )
    event_bus = MagicMock()
    config = MagicMock()
    config.acquire = AcquireConfig()
    svc = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orch,  # type: ignore[arg-type]
        event_bus=event_bus,  # type: ignore[arg-type]
        config=config,
    )
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        svc.run_search()

    # The season row is untouched — still terminal, never reused.
    season_row = store.wanted.get(season_wid)
    assert season_row is not None and season_row.status == "fallback_episodes"

    # No second season row was minted (anti ping-pong).
    season_rows = store.wanted.list_for_followed(1, kind="season")
    assert len(season_rows) == 1

    # The freshly re-enqueued episodes are STILL live — none absorbed.
    for wid in fresh_ep_ids:
        row = store.wanted.get(wid)
        assert row is not None
        assert row.status == "pending", f"fresh episode {wid} must stay live, got {row.status!r}"

    # Nothing was absorbed in this pass.
    absorbed_calls = [c for c in event_bus.emit.call_args_list if isinstance(c[0][0], SeasonAbsorbedEpisodes)]
    assert absorbed_calls == [], "conversion must not absorb onto a terminal season row"

    # The pending queue is non-empty — the season is not starved.
    assert store.wanted.list_pending(), "pending queue must not be emptied by a refused conversion"


def test_conversion_reuses_live_season_row_over_stale_terminal_one(store: ConcreteAcquireStore) -> None:
    """F-A REGRESSION (counter-review): a stale terminal row must not mask a live one.

    Proved scenario: an OLD season row at ``fallback_episodes`` coexists with
    a NEWER LIVE season row (re-minted by the manual web re-grab, review F5).
    The status-agnostic ``find()`` returns the OLDEST row, so the conversion
    guard used to see the terminal row, refuse, and never absorb the live
    episode onto the live season row — two parallel acquisition tracks for
    the same content.

    After the fix: the episode is absorbed onto the NEW live row
    (``absorbed_by`` == new row id), the old terminal row is untouched, and
    no third season row is minted.
    """
    from personalscraper.acquire.domain import FollowedSeries

    store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=99), title="Test Show", added_at=1))
    store.aired.replace_for_followed(
        1,
        [(3, n, f"E0{n}", f"2024-01-{n:02d}") for n in range(1, 6)],
        now=1_700_000_000,
    )

    # The season's FIRST life: absorbed episodes, then an R6 fallback → the
    # OLD season row is terminal (fallback_episodes).
    old_ep_ids = [store.wanted.add(_episode_item(episode=n)) for n in range(1, 6)]
    old_season_wid = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=99),
            kind="season",
            status="pending",
            enqueued_at=1_700_000_000,
            followed_id=1,
            season=3,
            episode=None,
        ),
    )
    store.wanted.absorb_episodes(old_season_wid, tuple(old_ep_ids))
    assert store.wanted.fallback_season(old_season_wid) is True

    # SECOND life: a NEWER LIVE season row (manual web re-grab, review F5)
    # plus a live pending episode awaiting absorption.
    new_season_wid = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=99),
            kind="season",
            status="pending",
            enqueued_at=1_700_000_000,
            followed_id=1,
            season=3,
            episode=None,
        ),
    )
    live_ep_wid = store.wanted.add(_episode_item(episode=5))

    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="not_found",
        outcome="no_matching_episode",
        found=0,
        raw_results=(_season_pack_result(),),  # a pack IS visible
    )
    event_bus = MagicMock()
    config = MagicMock()
    config.acquire = AcquireConfig()
    svc = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orch,  # type: ignore[arg-type]
        event_bus=event_bus,  # type: ignore[arg-type]
        config=config,
    )
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        svc.run_search()

    # The live episode was absorbed onto the NEW live season row.
    ep_row = store.wanted.get(live_ep_wid)
    assert ep_row is not None
    assert ep_row.status == "absorbed", f"live episode must be absorbed, got {ep_row.status!r}"
    assert ep_row.absorbed_by == new_season_wid, (
        f"episode must be absorbed by the LIVE row {new_season_wid}, got {ep_row.absorbed_by!r}"
    )

    # The old terminal row is untouched.
    old_row = store.wanted.get(old_season_wid)
    assert old_row is not None and old_row.status == "fallback_episodes"

    # No third season row was minted — reuse, not re-mint.
    season_rows = store.wanted.list_for_followed(1, kind="season")
    assert len(season_rows) == 2, f"expected exactly 2 season rows (old+new), got {len(season_rows)}"
    enqueued_calls = [
        c for c in event_bus.emit.call_args_list if isinstance(c[0][0], WantedEnqueued) and c[0][0].kind == "season"
    ]
    assert enqueued_calls == [], "reusing the live row must not emit WantedEnqueued(season)"

    # Absorption targeted the live row.
    absorbed_calls = [c for c in event_bus.emit.call_args_list if isinstance(c[0][0], SeasonAbsorbedEpisodes)]
    assert len(absorbed_calls) == 1
    assert absorbed_calls[0][0][0].season_wanted_id == new_season_wid


def test_conversion_noop_when_no_pack_in_results(store: ConcreteAcquireStore) -> None:
    """R2: raw results present but no season pack → no conversion.

    When the raw results exist but ``filter_to_season`` returns nothing,
    the conversion path is a no-op and the item stays pending.
    """
    from personalscraper.acquire.domain import FollowedSeries

    # Create the parent followed series so the FK resolves.
    store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=99),
            title="Test Show",
            added_at=1,
        )
    )

    item = _episode_item()
    store.wanted.add(item)

    orch = MagicMock(spec=GrabOrchestrator)
    # A raw result that is NOT a season pack — an individual episode.
    orch.search.return_value = SearchVerdict(
        disposition="not_found",
        outcome="no_matching_episode",
        found=0,
        raw_results=(_season_pack_result(title="Show S03E06 Single Episode 1080p"),),
    )

    event_bus = MagicMock()
    config = MagicMock()
    config.acquire = AcquireConfig()
    svc = AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orch,  # type: ignore[arg-type]
        event_bus=event_bus,  # type: ignore[arg-type]
        config=config,
    )
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        svc.run_search()

    # No season wanted should have been enqueued.
    season_item = store.wanted.find(
        followed_id=1,
        kind="season",
        season=3,
        episode=None,
    )
    assert season_item is None, "no season wanted when no pack in results"

    # No SeasonAbsorbedEpisodes should have been emitted.
    absorbed_calls = [c for c in event_bus.emit.call_args_list if isinstance(c[0][0], SeasonAbsorbedEpisodes)]
    assert len(absorbed_calls) == 0, "no absorption when no pack"

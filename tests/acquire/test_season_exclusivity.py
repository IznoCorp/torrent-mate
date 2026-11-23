"""The season's exclusivity (SR3), the grabbed episode's pointer (SR2), who launched it (SR5).

K3 P4. While a season ``wanted`` row is open, no episode of that season goes on
its own: detect does not enqueue it, the search pass absorbs a pending one
instead of searching it, the grab pass absorbs an available one instead of
grabbing it. An episode already ``grabbed`` keeps running (Q9) and only gains
the pointer to the season. Every automatic writer stamps ``trigger``.

The fallback (#542) composes: once the season row left the open set, its
re-enqueued episodes go on their own again.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire._season_fallback import fall_back_to_episodes
from personalscraper.acquire.detect import DetectOutcome, DetectService
from personalscraper.acquire.domain import AiredEpisode, FollowedSeries, SeriesCatalog, WantedItem
from personalscraper.acquire.events import SeasonAbsorbedEpisodes, WantedEnqueued
from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome, SearchVerdict
from personalscraper.acquire.season import SeasonRecovery
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.conf.models.acquire import AcquireConfig, CadenceConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.core.units import ByteSize

#: The items' enqueue clock and the pinned service clock one hour later: every
#: fresh row is in the Hot tier, due, and far from the cutoff.
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
    """Pin ``service.time.time`` so the fixture rows stay due."""
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        yield


class _NoOwnership:
    """Ownership stub: the library owns nothing."""

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Answer that nothing is owned.

        Args:
            media_ref: Ignored.
            kind: Ignored.
            season: Ignored.
            episode: Ignored.

        Returns:
            Always ``False``.
        """
        return False


def _follow(store: ConcreteAcquireStore) -> int:
    """Add the show follow every test hangs its rows on.

    Args:
        store: The acquire store.

    Returns:
        The follow's rowid.
    """
    return store.follow.add(FollowedSeries(media_ref=_REF, title="Severance", added_at=1))


def _season_row(store: ConcreteAcquireStore, fid: int, season: int, *, status: str = "pending") -> int:
    """Insert a season ``wanted`` row in the given status.

    Args:
        store: The acquire store.
        fid: The follow's rowid.
        season: The season number.
        status: The row's status.

    Returns:
        The season row's rowid.
    """
    return store.wanted.add(
        WantedItem(
            media_ref=_REF,
            kind="season",
            status=status,  # type: ignore[arg-type]
            enqueued_at=_ENQUEUED_AT,
            followed_id=fid,
            season=season,
            episode=None,
        )
    )


def _episode_row(store: ConcreteAcquireStore, fid: int, season: int, episode: int) -> int:
    """Insert a pending episode ``wanted`` row.

    Args:
        store: The acquire store.
        fid: The follow's rowid.
        season: The season number.
        episode: The episode number.

    Returns:
        The episode row's rowid.
    """
    return store.wanted.add(
        WantedItem(
            media_ref=_REF,
            kind="episode",
            status="pending",
            enqueued_at=_ENQUEUED_AT,
            followed_id=fid,
            season=season,
            episode=episode,
        )
    )


def _detect(store: ConcreteAcquireStore, episodes: list[AiredEpisode], *, today: date, bus: EventBus | None = None):
    """Run one detect pass over the given aired episodes.

    Args:
        store: The acquire store.
        episodes: The episodes the fake provider returns.
        today: The reference date.
        bus: The event bus (a fresh one when omitted).

    Returns:
        The :class:`~personalscraper.acquire.detect.DetectResult`.
    """
    catalogs = [SeriesCatalog(followed_id=None, media_ref=_REF, series_status=None, episodes=episodes)]
    svc = DetectService(
        store=store,
        ownership=_NoOwnership(),
        registry=MagicMock(),
        event_bus=bus if bus is not None else EventBus(),
        config=SimpleNamespace(acquire=SimpleNamespace(cadence=CadenceConfig())),  # type: ignore[arg-type]
    )
    with patch("personalscraper.acquire.detect.poll_catalog", return_value=catalogs):
        return svc.run(series=None, dry_run=False, today=today, now=_PINNED_NOW)


def _service(store: ConcreteAcquireStore, orchestrator: MagicMock, bus: MagicMock | None = None) -> AcquisitionService:
    """Build an acquisition service over a mock orchestrator.

    Args:
        store: The acquire store.
        orchestrator: The mock orchestrator (its ``search``/``grab`` are watched).
        bus: The event bus mock (a fresh one when omitted).

    Returns:
        The service.
    """
    config = MagicMock()
    config.acquire = AcquireConfig()
    return AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=bus if bus is not None else MagicMock(),
        config=config,
    )


# --- SeasonRecovery.covering ------------------------------------------------


@pytest.mark.parametrize("status", ["pending", "searching", "available", "grabbed"])
def test_covering_answers_the_open_season_row(store: ConcreteAcquireStore, status: str) -> None:
    """Every open status of a season row covers its episodes."""
    from personalscraper.acquire.season import SeasonRecovery

    fid = _follow(store)
    sid = _season_row(store, fid, 2, status=status)

    cover = SeasonRecovery(store).covering(fid, 2)

    assert cover is not None and cover.id == sid
    assert SeasonRecovery(store).covering(fid, 3) is None


@pytest.mark.parametrize("status", ["fallback_episodes", "done", "abandoned"])
def test_covering_ignores_a_closed_season_row(store: ConcreteAcquireStore, status: str) -> None:
    """A season row out of the open set covers nothing (the #542 fallback composes)."""
    from personalscraper.acquire.season import SeasonRecovery

    fid = _follow(store)
    _season_row(store, fid, 2, status=status)

    assert SeasonRecovery(store).covering(fid, 2) is None


def test_covering_needs_a_follow(store: ConcreteAcquireStore) -> None:
    """A follow-less row is never covered: every follow-less season row would match ``IS NULL``."""
    from personalscraper.acquire.season import SeasonRecovery

    store.wanted.add(
        WantedItem(media_ref=_REF, kind="season", status="pending", enqueued_at=1, followed_id=None, season=2)
    )

    assert SeasonRecovery(store).covering(None, 2) is None


# --- door 1: detect ---------------------------------------------------------


def test_detect_does_not_enqueue_an_episode_of_a_covered_season(store: ConcreteAcquireStore) -> None:
    """SR3's letter: an aired episode with NO row, under an open season wanted, is not enqueued."""
    fid = _follow(store)
    _season_row(store, fid, 2)
    today = date(2024, 6, 15)
    # The season is still airing (S02E04 announced), so detect's season rule mints nothing.
    episodes = [
        AiredEpisode(media_ref=_REF, season=2, episode=3, air_date=today - timedelta(days=2), title="E3"),
        AiredEpisode(media_ref=_REF, season=2, episode=4, air_date=today + timedelta(days=5), title="E4"),
        AiredEpisode(media_ref=_REF, season=3, episode=1, air_date=today - timedelta(days=1), title="S3E1"),
    ]

    result = _detect(store, episodes, today=today)

    assert store.wanted.find(followed_id=fid, kind="episode", season=2, episode=3) is None
    covered = [a for a in result.actions if a.season == 2 and a.episode == 3]
    assert [a.outcome for a in covered] == [DetectOutcome.SKIPPED_COVERED]
    assert result.summary.skipped_covered == 1
    assert result.summary.enqueued == 1
    # The uncovered season's episode still goes on its own.
    assert store.wanted.find(followed_id=fid, kind="episode", season=3, episode=1) is not None


def test_detect_enqueues_once_the_season_fell_back(store: ConcreteAcquireStore) -> None:
    """A season row past its fallback (#542) covers nothing: its episodes are enqueued again."""
    fid = _follow(store)
    _season_row(store, fid, 2, status="fallback_episodes")
    today = date(2024, 6, 15)
    episodes = [
        AiredEpisode(media_ref=_REF, season=2, episode=3, air_date=today - timedelta(days=2), title="E3"),
        AiredEpisode(media_ref=_REF, season=2, episode=4, air_date=today + timedelta(days=5), title="E4"),
    ]

    result = _detect(store, episodes, today=today)

    assert store.wanted.find(followed_id=fid, kind="episode", season=2, episode=3) is not None
    assert result.summary.skipped_covered == 0


def test_detect_cli_labels_a_covered_episode() -> None:
    """The detect table names the covered outcome rather than falling through to « enqueued »."""
    from personalscraper.acquire.detect import DetectAction
    from personalscraper.commands.follow import _detect_action_cell
    from personalscraper.i18n import t

    action = DetectAction("episode", "Severance", 2, 3, "2024-06-13", "E3", DetectOutcome.SKIPPED_COVERED)

    cell = _detect_action_cell(action, dry_run=False)

    assert t("cli_acquisition.follow.detect.cell_skipped_covered") in cell
    assert t("cli_acquisition.follow.detect.cell_enqueued") not in cell


# --- door 2: the search pass ------------------------------------------------


def test_search_pass_absorbs_a_pending_episode_of_a_covered_season(store: ConcreteAcquireStore) -> None:
    """A pending episode row of a covered season is absorbed, never searched."""
    fid = _follow(store)
    sid = _season_row(store, fid, 2)
    # The season row itself is in the queue too: only the episode's search is watched.
    eid = _episode_row(store, fid, 2, 3)
    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(disposition="not_found", outcome="no_candidates", found=0)
    bus = MagicMock()

    summary = _service(store, orch, bus).run_search()

    searched = [c.args[0].id for c in orch.search.call_args_list]
    assert eid not in searched
    assert summary.absorbed == 1
    assert summary.skipped == 0
    row = store.wanted.get(eid)
    assert row is not None and row.status == "absorbed" and row.absorbed_by == sid
    absorbed = [c.args[0] for c in bus.emit.call_args_list if isinstance(c.args[0], SeasonAbsorbedEpisodes)]
    assert [(e.season_wanted_id, e.absorbed_ids) for e in absorbed] == [(sid, (eid,))]


def test_search_pass_searches_an_episode_once_the_season_fell_back(store: ConcreteAcquireStore) -> None:
    """The #542 fallback composes: an episode re-enqueued after it is searched on its own."""
    fid = _follow(store)
    _season_row(store, fid, 2, status="fallback_episodes")
    eid = _episode_row(store, fid, 2, 3)
    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(disposition="not_found", outcome="no_candidates", found=0)

    _service(store, orch).run_search()

    assert [c.args[0].id for c in orch.search.call_args_list] == [eid]
    row = store.wanted.get(eid)
    assert row is not None and row.status == "pending" and row.absorbed_by is None


# --- door 3: the grab pass --------------------------------------------------


def test_grab_pass_absorbs_an_available_episode_of_a_covered_season(store: ConcreteAcquireStore) -> None:
    """An available episode row of a covered season is absorbed, never handed to the client."""
    fid = _follow(store)
    eid = _episode_row(store, fid, 2, 3)
    store.wanted.claim_for_search(eid, _PINNED_NOW)
    store.wanted.record_search_outcome(eid, "available", 4)
    store.wanted.set_status(eid, "available")
    # The season ask came after the episode's search concluded.
    sid = _season_row(store, fid, 2)
    orch = MagicMock(spec=GrabOrchestrator)
    orch.scope_allows_grab.return_value = True
    bus = MagicMock()

    summary = _service(store, orch, bus).run()

    orch.grab.assert_not_called()
    assert summary.grabbed == 0
    assert summary.absorbed == 1
    assert summary.skipped == 0
    row = store.wanted.get(eid)
    assert row is not None and row.status == "absorbed" and row.absorbed_by == sid
    absorbed = [c.args[0] for c in bus.emit.call_args_list if isinstance(c.args[0], SeasonAbsorbedEpisodes)]
    assert [(e.season_wanted_id, e.absorbed_ids) for e in absorbed] == [(sid, (eid,))]


# --- SR2: the grabbed episode's pointer -------------------------------------


def test_absorb_points_a_grabbed_episode_at_the_season_without_restatusing_it(store: ConcreteAcquireStore) -> None:
    """Q9: a grabbed episode keeps ``grabbed`` (its torrent runs) and gains ``absorbed_by``."""
    fid = _follow(store)
    pending_id = _episode_row(store, fid, 2, 1)
    grabbed_id = _episode_row(store, fid, 2, 2)
    store.wanted.mark_grabbed(grabbed_id, "abcd1234")
    done_id = _episode_row(store, fid, 2, 3)
    store.wanted.set_status(done_id, "done")
    sid = _season_row(store, fid, 2)

    transitioned = store.wanted.absorb_episodes(sid, (pending_id, grabbed_id, done_id))

    assert transitioned == 1  # only the pending row changed status
    pending = store.wanted.get(pending_id)
    assert pending is not None and pending.status == "absorbed" and pending.absorbed_by == sid
    grabbed = store.wanted.get(grabbed_id)
    assert grabbed is not None
    assert grabbed.status == "grabbed"
    assert grabbed.grabbed_hash == "abcd1234"
    assert grabbed.absorbed_by == sid
    done = store.wanted.get(done_id)
    assert done is not None and done.status == "done" and done.absorbed_by is None


# --- SR5: who launched it ---------------------------------------------------


def test_detect_writes_its_episode_and_film_rows_automatic(store: ConcreteAcquireStore) -> None:
    """Detect's episode and film rows carry ``trigger='automatic'``."""
    fid = _follow(store)
    movie_ref = MediaRef(tmdb_id=1184918)
    mid = store.follow.add(FollowedSeries(media_ref=movie_ref, title="Le Robot sauvage", added_at=1, kind="movie"))
    today = date(2024, 6, 15)
    episodes = [
        AiredEpisode(media_ref=_REF, season=2, episode=3, air_date=today - timedelta(days=2), title="E3"),
        AiredEpisode(media_ref=_REF, season=2, episode=4, air_date=today + timedelta(days=5), title="E4"),
    ]

    _detect(store, episodes, today=today)

    episode = store.wanted.find(followed_id=fid, kind="episode", season=2, episode=3)
    assert episode is not None and episode.trigger == "automatic"
    film = store.wanted.find(followed_id=mid, kind="movie", season=None, episode=None)
    assert film is not None and film.trigger == "automatic"


def test_detect_season_rule_writes_automatic(store: ConcreteAcquireStore) -> None:
    """Detect's season rule (R1) stamps its season row ``automatic``."""
    fid = _follow(store)
    today = date(2024, 6, 15)
    episodes = [
        AiredEpisode(media_ref=_REF, season=2, episode=n, air_date=today - timedelta(days=20 - n), title=f"E{n}")
        for n in range(1, 5)
    ]

    _detect(store, episodes, today=today)

    season = store.wanted.find(followed_id=fid, kind="season", season=2, episode=None)
    assert season is not None and season.trigger == "automatic"


def test_search_conversion_writes_its_season_row_automatic(store: ConcreteAcquireStore) -> None:
    """The R2 conversion still absorbs, and its season row is ``automatic``."""
    fid = _follow(store)
    eid = _episode_row(store, fid, 3, 5)
    store.aired.replace_for_followed(fid, [(3, n, f"E{n}", f"2024-01-{n:02d}") for n in range(1, 6)], now=_ENQUEUED_AT)
    pack = TrackerResult(
        provider="c411",
        tracker_id="t99",
        title="Severance S03 COMPLETE 1080p",
        size=ByteSize(20_000_000_000),
        seeders=100,
        leechers=0,
        resolution="1080p",
        info_hash="seasonpack99",
        download_url="https://c411.test/torrent/99",
    )
    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="not_found", outcome="no_matching_episode", found=0, raw_results=(pack,)
    )

    _service(store, orch).run_search()

    season = store.wanted.find(followed_id=fid, kind="season", season=3, episode=None)
    assert season is not None and season.trigger == "automatic"
    episode = store.wanted.get(eid)
    assert episode is not None and episode.status == "absorbed" and episode.absorbed_by == season.id


# --- review-930: a row holding a torrent is reconciled, never absorbed ------


def _hash_bearing_searching_row(store: ConcreteAcquireStore, fid: int) -> int:
    """Insert an episode row in the D2 crash window: ``searching``, stale, holding a hash.

    The torrent was added and the status write lost; only the reconciliation may close it.

    Args:
        store: The acquire store.
        fid: The follow's rowid.

    Returns:
        The episode row's rowid.
    """
    eid = _episode_row(store, fid, 2, 3)
    assert store.wanted.claim_for_search(eid, _PINNED_NOW - 7200)
    assert store.wanted.record_grab_intent(eid, "deadbeef")
    return eid


@pytest.mark.parametrize("door", ["search", "grab"])
def test_a_pass_leaves_a_hash_bearing_row_to_the_reconciliation(store: ConcreteAcquireStore, door: str) -> None:
    """A stale ``searching`` row with a hash, under an open season, keeps its status and hash; it is pointed."""
    fid = _follow(store)
    eid = _hash_bearing_searching_row(store, fid)
    sid = _season_row(store, fid, 2)
    orch = MagicMock(spec=GrabOrchestrator)
    orch.scope_allows_grab.return_value = True
    orch.search.return_value = SearchVerdict(disposition="not_found", outcome="no_candidates", found=0)
    bus = MagicMock()

    service = _service(store, orch, bus)
    summary = service.run_search() if door == "search" else service.run()

    row = store.wanted.get(eid)
    assert row is not None
    assert row.status == "searching"
    assert row.grabbed_hash == "deadbeef"
    assert row.absorbed_by == sid
    assert summary.absorbed == 0
    orch.grab.assert_not_called()
    assert eid not in [c.args[0].id for c in orch.search.call_args_list]
    assert not [c for c in bus.emit.call_args_list if isinstance(c.args[0], SeasonAbsorbedEpisodes)]


def test_absorb_points_a_live_row_holding_a_hash_without_absorbing_it(store: ConcreteAcquireStore) -> None:
    """The store guard: ``absorb_episodes`` moves only hash-less live rows, and points the others."""
    fid = _follow(store)
    eid = _hash_bearing_searching_row(store, fid)
    sid = _season_row(store, fid, 2)

    assert store.wanted.absorb_episodes(sid, (eid,)) == 0

    row = store.wanted.get(eid)
    assert row is not None and row.status == "searching" and row.absorbed_by == sid


def test_absorb_if_covered_answers_false_and_logs_when_nothing_moved(
    store: ConcreteAcquireStore, caplog: pytest.LogCaptureFixture
) -> None:
    """A covered row the guarded UPDATE cannot move is not reported absorbed: the caller's claim decides."""
    fid = _follow(store)
    eid = _episode_row(store, fid, 2, 3)
    snapshot = store.wanted.get(eid)
    assert snapshot is not None
    store.wanted.set_status(eid, "done")  # a concurrent writer closed it after the queue was read
    _season_row(store, fid, 2)
    bus = MagicMock()

    with caplog.at_level(logging.INFO):
        absorbed = SeasonRecovery(store).absorb_if_covered(snapshot, event_bus=bus, door="search")

    assert absorbed is False
    bus.emit.assert_not_called()
    assert any("acquire.season.absorb_missed" in r.getMessage() for r in caplog.records)
    row = store.wanted.get(eid)
    assert row is not None and row.status == "done"


# --- review-930: detect resurrects nothing under a covered season ----------


def test_detect_does_not_resurrect_an_abandoned_episode_of_a_covered_season(store: ConcreteAcquireStore) -> None:
    """An abandoned episode still inside its cutoff stays abandoned while its season is under recovery."""
    fid = _follow(store)
    eid = _episode_row(store, fid, 2, 3)
    store.wanted.set_status(eid, "abandoned")
    _season_row(store, fid, 2)
    today = date(2024, 6, 15)
    episodes = [
        AiredEpisode(media_ref=_REF, season=2, episode=3, air_date=today - timedelta(days=2), title="E3"),
        AiredEpisode(media_ref=_REF, season=2, episode=4, air_date=today + timedelta(days=5), title="E4"),
    ]

    result = _detect(store, episodes, today=today)

    row = store.wanted.get(eid)
    assert row is not None and row.status == "abandoned"
    covered = [a.outcome for a in result.actions if a.season == 2 and a.episode == 3]
    assert covered == [DetectOutcome.SKIPPED_COVERED]
    assert result.summary.resurrected == 0
    assert result.summary.skipped_covered == 1


# --- review-930: an abandoned season re-mints its absorbed episodes ----------


def _season_with_absorbed(store: ConcreteAcquireStore, *, status: str = "pending") -> tuple[int, int, list[int]]:
    """Insert a season row that absorbed two episode rows.

    Args:
        store: The acquire store.
        status: The season row's status.

    Returns:
        ``(followed_id, season_row_id, absorbed_episode_row_ids)``.
    """
    fid = _follow(store)
    episode_ids = [_episode_row(store, fid, 2, n) for n in (1, 2)]
    sid = _season_row(store, fid, 2, status=status)
    assert store.wanted.absorb_episodes(sid, tuple(episode_ids)) == 2
    return fid, sid, episode_ids


def _assert_reminted(store: ConcreteAcquireStore, fid: int, absorbed_ids: list[int]) -> None:
    """Assert each absorbed episode is queued again on a fresh automatic row, the old row kept.

    Args:
        store: The acquire store.
        fid: The follow's rowid.
        absorbed_ids: The episode rows the season had absorbed.
    """
    for n, old_id in zip((1, 2), absorbed_ids, strict=True):
        fresh = store.wanted.find(followed_id=fid, kind="episode", season=2, episode=n, statuses=("pending",))
        assert fresh is not None and fresh.id != old_id
        assert fresh.trigger == "automatic"
        old = store.wanted.get(old_id)
        assert old is not None and old.status == "absorbed"


def test_a_season_abandoned_by_a_terminal_search_re_mints_its_episodes(store: ConcreteAcquireStore) -> None:
    """A confirmed terminal search verdict abandons the season row and re-queues what it absorbed."""
    fid, sid, absorbed_ids = _season_with_absorbed(store)
    store.wanted.record_search_outcome(sid, "tracker_auth", None)  # the first all-auth verdict, debounced
    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(disposition="terminal", outcome="tracker_auth", found=None)

    _service(store, orch).run_search()

    season = store.wanted.get(sid)
    assert season is not None and season.status == "abandoned"
    _assert_reminted(store, fid, absorbed_ids)


def test_a_season_abandoned_by_a_terminal_grab_re_mints_its_episodes(store: ConcreteAcquireStore) -> None:
    """A terminal grab abandons the season row and re-queues what it absorbed."""
    fid, sid, absorbed_ids = _season_with_absorbed(store)
    assert store.wanted.claim_for_search(sid, _PINNED_NOW)
    store.wanted.record_search_outcome(sid, "available", 3)
    store.wanted.set_status(sid, "available")
    orch = MagicMock(spec=GrabOrchestrator)
    orch.scope_allows_grab.return_value = True
    orch.grab.return_value = GrabOutcome(disposition="terminal", reason="tracker_auth")

    _service(store, orch).run()

    season = store.wanted.get(sid)
    assert season is not None and season.status == "abandoned"
    _assert_reminted(store, fid, absorbed_ids)


# --- review-930: the automatic season writers point their grabbed siblings ---


def test_detect_season_rule_points_a_grabbed_sibling(store: ConcreteAcquireStore) -> None:
    """R5 points a grabbed episode at the season (status kept); the event names the absorbed rows only."""
    fid = _follow(store)
    pending_id = _episode_row(store, fid, 2, 1)
    grabbed_id = _episode_row(store, fid, 2, 2)
    store.wanted.mark_grabbed(grabbed_id, "abcd1234")
    today = date(2024, 6, 15)
    episodes = [
        AiredEpisode(media_ref=_REF, season=2, episode=n, air_date=today - timedelta(days=20 - n), title=f"E{n}")
        for n in range(1, 5)
    ]
    bus = EventBus()
    absorbed_events: list[SeasonAbsorbedEpisodes] = []
    bus.subscribe(SeasonAbsorbedEpisodes, absorbed_events.append)

    _detect(store, episodes, today=today, bus=bus)

    season = store.wanted.find(followed_id=fid, kind="season", season=2, episode=None)
    assert season is not None
    grabbed = store.wanted.get(grabbed_id)
    assert grabbed is not None and grabbed.status == "grabbed" and grabbed.absorbed_by == season.id
    pending = store.wanted.get(pending_id)
    assert pending is not None and pending.status == "absorbed"
    assert len(absorbed_events) == 1
    assert grabbed_id not in absorbed_events[0].absorbed_ids
    assert pending_id in absorbed_events[0].absorbed_ids


def test_search_conversion_points_a_grabbed_sibling(store: ConcreteAcquireStore) -> None:
    """The R2 conversion points a grabbed sibling at its season row; the event names the absorbed rows only."""
    fid = _follow(store)
    grabbed_id = _episode_row(store, fid, 3, 1)
    store.wanted.mark_grabbed(grabbed_id, "abcd1234")
    eid = _episode_row(store, fid, 3, 5)
    store.aired.replace_for_followed(fid, [(3, n, f"E{n}", f"2024-01-{n:02d}") for n in range(1, 6)], now=_ENQUEUED_AT)
    pack = TrackerResult(
        provider="c411",
        tracker_id="t99",
        title="Severance S03 COMPLETE 1080p",
        size=ByteSize(20_000_000_000),
        seeders=100,
        leechers=0,
        resolution="1080p",
        info_hash="seasonpack99",
        download_url="https://c411.test/torrent/99",
    )
    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="not_found", outcome="no_matching_episode", found=0, raw_results=(pack,)
    )
    bus = MagicMock()

    _service(store, orch, bus).run_search()

    season = store.wanted.find(followed_id=fid, kind="season", season=3, episode=None)
    assert season is not None
    grabbed = store.wanted.get(grabbed_id)
    assert grabbed is not None and grabbed.status == "grabbed" and grabbed.absorbed_by == season.id
    absorbed = [c.args[0] for c in bus.emit.call_args_list if isinstance(c.args[0], SeasonAbsorbedEpisodes)]
    assert [e.absorbed_ids for e in absorbed] == [(eid,)]


# --- review-930: R6 rows and the WantedEnqueued event carry the trigger ------


def test_the_r6_fallback_writes_its_episode_rows_automatic(store: ConcreteAcquireStore) -> None:
    """The fallback's re-enqueued episode rows are an engine writer's: ``trigger='automatic'``."""
    fid = _follow(store)
    sid = _season_row(store, fid, 2)
    season = store.wanted.get(sid)
    assert season is not None

    fall_back_to_episodes(store, season, now=_PINNED_NOW, event_bus=MagicMock(), episodes=[1, 2])

    for n in (1, 2):
        row = store.wanted.find(followed_id=fid, kind="episode", season=2, episode=n)
        assert row is not None and row.trigger == "automatic"


def test_detect_announces_each_enqueue_with_its_trigger(store: ConcreteAcquireStore) -> None:
    """Every ``WantedEnqueued`` detect emits (film, episode, season) carries ``trigger='automatic'``."""
    _follow(store)
    store.follow.add(
        FollowedSeries(media_ref=MediaRef(tmdb_id=1184918), title="Le Robot sauvage", added_at=1, kind="movie")
    )
    today = date(2024, 6, 15)
    episodes = [
        AiredEpisode(media_ref=_REF, season=2, episode=n, air_date=today - timedelta(days=20 - n), title=f"E{n}")
        for n in range(1, 5)
    ]
    bus = EventBus()
    enqueued: list[WantedEnqueued] = []
    bus.subscribe(WantedEnqueued, enqueued.append)

    _detect(store, episodes, today=today, bus=bus)

    assert {e.kind for e in enqueued} == {"movie", "episode", "season"}
    assert {e.trigger for e in enqueued} == {"automatic"}


def test_the_search_conversion_announces_its_season_with_its_trigger(store: ConcreteAcquireStore) -> None:
    """The conversion's ``WantedEnqueued(season)`` carries ``trigger='automatic'``."""
    fid = _follow(store)
    _episode_row(store, fid, 3, 5)
    store.aired.replace_for_followed(fid, [(3, n, f"E{n}", f"2024-01-{n:02d}") for n in range(1, 6)], now=_ENQUEUED_AT)
    pack = TrackerResult(
        provider="c411",
        tracker_id="t99",
        title="Severance S03 COMPLETE 1080p",
        size=ByteSize(20_000_000_000),
        seeders=100,
        leechers=0,
        resolution="1080p",
        info_hash="seasonpack99",
        download_url="https://c411.test/torrent/99",
    )
    orch = MagicMock(spec=GrabOrchestrator)
    orch.search.return_value = SearchVerdict(
        disposition="not_found", outcome="no_matching_episode", found=0, raw_results=(pack,)
    )
    bus = MagicMock()

    _service(store, orch, bus).run_search()

    enqueued = [c.args[0] for c in bus.emit.call_args_list if isinstance(c.args[0], WantedEnqueued)]
    assert [(e.kind, e.trigger) for e in enqueued] == [("season", "automatic")]

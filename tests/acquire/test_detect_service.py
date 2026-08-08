"""Unit tests for the DETECT service layer (ACQUIRE-03 — grab parity).

Drives :class:`~personalscraper.acquire.detect.DetectService` directly against a
REAL :class:`ConcreteAcquireStore` + a REAL :class:`EventBus`, mirroring how the
grab tests drive ``AcquisitionService``. The resurrection cadence-cutoff gate
gets its own coverage here (it used to be buried in the CLI command).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.detect import DetectOutcome, DetectService, DetectStatus
from personalscraper.acquire.domain import AiredEpisode, FollowedSeries, WantedItem
from personalscraper.acquire.events import FilmAcquired, SeasonAbsorbedEpisodes, WantedEnqueued
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig, CadenceConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef


class _StubOwnership:
    """Ownership stub: owns exactly the media_refs it was given."""

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


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _config() -> SimpleNamespace:
    """A minimal config exposing only ``acquire.cadence`` (all the service reads)."""
    return SimpleNamespace(acquire=SimpleNamespace(cadence=CadenceConfig()))


def _service(store: ConcreteAcquireStore, ownership: _StubOwnership, bus: EventBus) -> DetectService:
    """Build a DetectService with a MagicMock registry (poll_aired is patched)."""
    return DetectService(store=store, ownership=ownership, registry=MagicMock(), event_bus=bus, config=_config())


def test_detect_service_no_active_status(store: ConcreteAcquireStore) -> None:
    """An empty active set → status NO_ACTIVE, no actions."""
    result = _service(store, _StubOwnership(set()), EventBus()).run(
        series=None, dry_run=False, today=date(2024, 1, 1), now=1
    )
    assert result.status is DetectStatus.NO_ACTIVE
    assert result.actions == []


def test_detect_service_no_match_status(store: ConcreteAcquireStore) -> None:
    """A --series filter with no match → status NO_MATCH."""
    store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=99), title="Silo", added_at=1))
    result = _service(store, _StubOwnership(set()), EventBus()).run(
        series="Nonexistent", dry_run=False, today=date(2024, 1, 1), now=1
    )
    assert result.status is DetectStatus.NO_MATCH


def test_detect_service_movie_enqueue_grab_parity(store: ConcreteAcquireStore) -> None:
    """An unowned movie follow → OK result with one ENQUEUED action + a real wanted row."""
    ref = MediaRef(tmdb_id=1184918)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Le Robot sauvage", added_at=1, kind="movie"))
    bus = EventBus()
    emitted: list[WantedEnqueued] = []
    bus.subscribe(WantedEnqueued, emitted.append)

    with patch("personalscraper.acquire.detect.poll_known", return_value=[]):
        result = _service(store, _StubOwnership(set()), bus).run(
            series=None, dry_run=False, today=date(2024, 1, 1), now=100
        )

    assert result.status is DetectStatus.OK
    assert [a.outcome for a in result.actions] == [DetectOutcome.ENQUEUED]
    assert result.summary.enqueued == 1
    assert result.summary.detected == 1
    row = store.wanted.find(followed_id=fid, kind="movie", season=None, episode=None)
    assert row is not None and row.status == "pending"
    assert len(emitted) == 1 and emitted[0].kind == "movie"


def test_detect_service_movie_owned_retires_and_emits(store: ConcreteAcquireStore) -> None:
    """An OWNED movie follow → FILM_ACQUIRED action, follow retired, FilmAcquired emitted."""
    ref = MediaRef(tmdb_id=1184918)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Le Robot sauvage", added_at=1, kind="movie"))
    wid = store.wanted.add(WantedItem(media_ref=ref, kind="movie", status="pending", enqueued_at=1, followed_id=fid))
    store.wanted.mark_grabbed(wid, "abcd1234")
    bus = EventBus()
    films: list[FilmAcquired] = []
    bus.subscribe(FilmAcquired, films.append)

    with patch("personalscraper.acquire.detect.poll_known", return_value=[]):
        result = _service(store, _StubOwnership({ref}), bus).run(
            series=None, dry_run=False, today=date(2024, 1, 1), now=100
        )

    assert [a.outcome for a in result.actions] == [DetectOutcome.FILM_ACQUIRED]
    assert result.summary.skipped_owned == 1
    follow = store.follow.get(fid)
    # REMOVED, not paused: deactivating wrote the same state as « Mettre en
    # pause », so an acquired film and one the operator set aside were the
    # same row (operator report 2026-08-08).
    assert follow is None, "an acquired film leaves the follows"
    assert len(films) == 1 and films[0].followed_id == fid


def test_detect_service_replaces_an_owned_film_when_authorised(store: ConcreteAcquireStore) -> None:
    """A film the operator chose to REPLACE is acquired, not closed on sight.

    Operator, 2026-08-08: « un film déjà en médiathèque doit être
    re-téléchargé et remplacé ». The §5 dialog promises exactly that; detect
    used to close the follow the moment it saw the film owned, so nothing was
    ever fetched and the promise was false.
    """
    ref = MediaRef(tmdb_id=1184918)
    fid = store.follow.add(
        FollowedSeries(
            media_ref=ref,
            title="Le Robot sauvage",
            added_at=1,
            kind="movie",
            replace_owned=True,
        )
    )
    bus = EventBus()
    films: list[FilmAcquired] = []
    bus.subscribe(FilmAcquired, films.append)

    with patch("personalscraper.acquire.detect.poll_known", return_value=[]):
        result = _service(store, _StubOwnership({ref}), bus).run(
            series=None, dry_run=False, today=date(2024, 1, 1), now=100
        )

    # It enqueued instead of closing — the follow survives and wants something.
    assert result.summary.skipped_owned == 0
    assert DetectOutcome.FILM_ACQUIRED not in [a.outcome for a in result.actions]
    assert store.follow.get(fid) is not None
    assert films == [], "nothing was acquired yet — the fetch has not run"
    # And the authorisation is SPENT: leaving it set would re-acquire the film
    # on every later pass, which is a loop, not a replacement.
    follow = store.follow.get(fid)
    assert follow is not None and follow.replace_owned is False


def test_detect_service_resurrects_abandoned_within_cutoff(store: ConcreteAcquireStore) -> None:
    """An abandoned aired-unowned episode within cutoff → RESURRECTED (cadence gate)."""
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Silo", added_at=1))
    wid = store.wanted.add(
        WantedItem(
            media_ref=ref,
            kind="episode",
            status="pending",
            enqueued_at=int(time.time()) - 3600,
            followed_id=fid,
            season=3,
            episode=4,
        )
    )
    store.wanted.set_status(wid, "abandoned")
    ep = AiredEpisode(media_ref=ref, season=3, episode=4, air_date=date(2024, 1, 1), title="Ep")

    with patch("personalscraper.acquire.detect.poll_known", return_value=[ep]):
        result = _service(store, _StubOwnership(set()), EventBus()).run(
            series=None, dry_run=False, today=date(2024, 1, 1), now=int(time.time())
        )

    assert [a.outcome for a in result.actions] == [DetectOutcome.RESURRECTED]
    assert result.summary.resurrected == 1
    assert store.wanted.get(wid).status == "pending"  # type: ignore[union-attr]


def test_detect_service_past_cutoff_stays_abandoned(store: ConcreteAcquireStore) -> None:
    """An abandoned row past its cadence cutoff → SKIPPED_DUP (no flip-flop)."""
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Silo", added_at=1))
    wid = store.wanted.add(
        WantedItem(
            media_ref=ref, kind="episode", status="pending", enqueued_at=1_000_000, followed_id=fid, season=3, episode=4
        )
    )
    store.wanted.set_status(wid, "abandoned")
    ep = AiredEpisode(media_ref=ref, season=3, episode=4, air_date=date(2024, 1, 1), title="Ep")

    with patch("personalscraper.acquire.detect.poll_known", return_value=[ep]):
        result = _service(store, _StubOwnership(set()), EventBus()).run(
            series=None, dry_run=False, today=date(2024, 1, 1), now=int(time.time())
        )

    assert [a.outcome for a in result.actions] == [DetectOutcome.SKIPPED_DUP]
    assert result.summary.skipped_dup == 1
    assert store.wanted.get(wid).status == "abandoned"  # type: ignore[union-attr]


def test_future_episode_goes_to_cache_but_never_to_wanted(store: ConcreteAcquireStore) -> None:
    """THE INVARIANT (episode-states D1 / ACC-01): a future episode is cached, NOT enqueued.

    ``poll_known`` returns an aired AND a future episode for the same series.
    After detect:

    - the ``aired_episode`` cache holds BOTH (the future is what the matrix will
      read as ``annonce``);
    - the ``wanted`` queue holds ONLY the aired episode — a future is not
      searchable on trackers, so it must never become a wanted row.
    """
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    aired = AiredEpisode(media_ref=ref, season=2, episode=1, air_date=date(2024, 6, 1), title="Aired")
    future = AiredEpisode(media_ref=ref, season=2, episode=2, air_date=date(2025, 1, 1), title="Announced")

    with patch("personalscraper.acquire.detect.poll_known", return_value=[aired, future]):
        result = _service(store, _StubOwnership(set()), EventBus()).run(
            series=None, dry_run=False, today=today, now=int(time.time())
        )

    # Only the aired episode produced an enqueue action — the future produced
    # none, and the announced future also blocks the R1 season mint (F2).
    assert [a.outcome for a in result.actions] == [DetectOutcome.ENQUEUED]
    assert result.summary.enqueued == 1

    # The cache holds BOTH the aired and the announced episode.
    cached = {(r.season, r.episode): r.air_date for r in store.aired.list_for_followed(fid)}
    assert cached == {(2, 1): "2024-06-01", (2, 2): "2025-01-01"}, "the cache must learn the future"

    # The wanted queue holds the aired episode ONLY — the future is never enqueued.
    wanted = store.wanted.list_for_followed(fid, kind="episode")
    assert [(w.season, w.episode) for w in wanted] == [(2, 1)], "a future must NEVER become a wanted row"

    # NO season wanted: the announced S02E02 proves the season is still running.
    season_row = store.wanted.find(followed_id=fid, kind="season", season=2, episode=None)
    assert season_row is None, "a season with an announced future episode must not be minted"


# ── season detection (R1 + R5) ─────────────────────────────────────────


class _StubPerEpisodeOwnership:
    """Ownership stub that checks per-episode ownership via a set of (season, episode)."""

    def __init__(self, owned_eps: set[tuple[int, int]]) -> None:
        self._owned_eps = owned_eps

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        if kind == "episode" and season is not None and episode is not None:
            return (season, episode) in self._owned_eps
        return False


def _aired_season(
    ref: MediaRef, season: int, count: int, *, today: date, last_days_ago: int = 14
) -> list[AiredEpisode]:
    """Build aired episodes for one season, all aired before ``today``.

    The last episode (highest episode number) airs ``last_days_ago`` days
    before ``today``; earlier episodes are spread further back.
    """
    eps = []
    for ep_num in range(1, count + 1):
        days_back = last_days_ago + (count - ep_num)  # ep 1 = oldest, ep N = last_days_ago ago
        eps.append(
            AiredEpisode(
                media_ref=ref,
                season=season,
                episode=ep_num,
                air_date=today - timedelta(days=days_back),
                title=f"Ep{ep_num}",
            )
        )
    return eps


def test_season_detect_enqueues_when_conditions_met(store: ConcreteAcquireStore) -> None:
    """R1: last ep aired >= 7d, owned <= half → season wanted enqueued."""
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 6, today=today, last_days_ago=14)
    # Own 2 of 6 → 2 <= 3 (half) → enqueue
    owned = _StubPerEpisodeOwnership({(2, 1), (2, 2)})
    bus = EventBus()
    enqueued: list[WantedEnqueued] = []
    bus.subscribe(WantedEnqueued, enqueued.append)

    svc = DetectService(
        store=store,
        ownership=owned,
        registry=MagicMock(),
        event_bus=bus,
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    assert result.status is DetectStatus.OK
    season_actions = [a for a in result.actions if a.kind == "season"]
    assert len(season_actions) == 1
    assert season_actions[0].outcome is DetectOutcome.ENQUEUED
    season_wanted = store.wanted.find(followed_id=fid, kind="season", season=2, episode=None)
    assert season_wanted is not None and season_wanted.kind == "season"
    season_emitted = [e for e in enqueued if e.kind == "season"]
    assert len(season_emitted) == 1


def test_season_detect_skips_mid_season_break_and_keeps_episodes_live(store: ConcreteAcquireStore) -> None:
    """F2 REGRESSION: a mid-season break must NOT mint a season wanted.

    10-episode season, 4 aired (last one 20 days ago), 6 announced future.
    The old code counted only AIRED episodes, so the break looked like a
    finished 4-episode season: it minted the season and absorbed the live
    episode wanteds. R1 requires the season's LAST episode to have aired.
    """
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    known = [
        AiredEpisode(
            media_ref=ref,
            season=2,
            episode=n,
            air_date=today - timedelta(days=20 + (4 - n)),  # eps 1-4 aired, last 20d ago
            title=f"Ep{n}",
        )
        for n in range(1, 5)
    ] + [
        AiredEpisode(
            media_ref=ref,
            season=2,
            episode=n,
            air_date=today + timedelta(days=(n - 4) * 7),  # eps 5-10 announced future
            title=f"Ep{n}",
        )
        for n in range(5, 11)
    ]
    # Live episode wanteds for the 4 aired episodes (what detect enqueued before).
    live_ids = [
        store.wanted.add(
            WantedItem(
                media_ref=ref,
                kind="episode",
                status="pending",
                enqueued_at=1,
                followed_id=fid,
                season=2,
                episode=n,
            )
        )
        for n in range(1, 5)
    ]

    bus = EventBus()
    absorbed_events: list[SeasonAbsorbedEpisodes] = []
    bus.subscribe(SeasonAbsorbedEpisodes, absorbed_events.append)

    svc = DetectService(
        store=store,
        ownership=_StubPerEpisodeOwnership(set()),
        registry=MagicMock(),
        event_bus=bus,
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=known):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    # NO season action, NO season row.
    assert [a for a in result.actions if a.kind == "season"] == []
    assert store.wanted.find(followed_id=fid, kind="season", season=2, episode=None) is None

    # The live episode wanteds were NOT absorbed.
    assert absorbed_events == []
    for wid in live_ids:
        row = store.wanted.get(wid)
        assert row is not None and row.status == "pending", f"episode {wid} must stay live"


def test_season_detect_skips_when_last_aired_six_days_ago(store: ConcreteAcquireStore) -> None:
    """F2: all aired but the last episode aired 6 days ago → NOT enqueued.

    Pins the exact 7-day threshold from the inside (the 3-day test is weaker):
    6 days is one short of the inclusive >= 7d edge.
    """
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 6, today=today, last_days_ago=6)

    svc = DetectService(
        store=store,
        ownership=_StubPerEpisodeOwnership(set()),
        registry=MagicMock(),
        event_bus=EventBus(),
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    assert [a for a in result.actions if a.kind == "season"] == []
    assert store.wanted.find(followed_id=fid, kind="season", season=2, episode=None) is None


def test_season_detect_skips_when_last_ep_recent(store: ConcreteAcquireStore) -> None:
    """R1(b): last ep aired < 7d ago → no season wanted."""
    ref = MediaRef(tvdb_id=99)
    store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 4, today=today, last_days_ago=3)  # 3d ago < 7d
    owned = _StubPerEpisodeOwnership(set())

    svc = DetectService(
        store=store,
        ownership=owned,
        registry=MagicMock(),
        event_bus=EventBus(),
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    season_actions = [a for a in result.actions if a.kind == "season"]
    assert len(season_actions) == 0


def test_season_detect_skips_when_more_than_half_owned(store: ConcreteAcquireStore) -> None:
    """R1(c): owned > total/2 → skip."""
    ref = MediaRef(tvdb_id=99)
    store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 6, today=today, last_days_ago=14)
    owned = _StubPerEpisodeOwnership({(2, 1), (2, 2), (2, 3), (2, 4)})  # 4 of 6

    svc = DetectService(
        store=store,
        ownership=owned,
        registry=MagicMock(),
        event_bus=EventBus(),
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    season_actions = [a for a in result.actions if a.kind == "season"]
    assert len(season_actions) == 0


def test_season_detect_skips_when_fully_owned(store: ConcreteAcquireStore) -> None:
    """R1(e): owned == total → skip."""
    ref = MediaRef(tvdb_id=99)
    store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 4, today=today, last_days_ago=14)
    owned = _StubPerEpisodeOwnership({(2, 1), (2, 2), (2, 3), (2, 4)})

    svc = DetectService(
        store=store,
        ownership=owned,
        registry=MagicMock(),
        event_bus=EventBus(),
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    season_actions = [a for a in result.actions if a.kind == "season"]
    assert len(season_actions) == 0


def test_season_detect_skips_when_duplicate(store: ConcreteAcquireStore) -> None:
    """R1(d): live season wanted already exists → skip."""
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    # Pre-insert a season wanted
    store.wanted.add(
        WantedItem(
            media_ref=ref,
            kind="season",
            status="pending",
            enqueued_at=1,
            followed_id=fid,
            season=2,
            episode=None,
        )
    )
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 6, today=today, last_days_ago=14)
    owned = _StubPerEpisodeOwnership(set())

    svc = DetectService(
        store=store,
        ownership=owned,
        registry=MagicMock(),
        event_bus=EventBus(),
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    season_actions = [a for a in result.actions if a.kind == "season"]
    assert len(season_actions) == 0


def test_season_detect_absorbs_episode_wanteds(store: ConcreteAcquireStore) -> None:
    """R5: enqueued season absorbs live episode wanteds."""
    ref = MediaRef(tvdb_id=99)
    fid = store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    # Pre-insert episode wanteds for the season
    for ep_num in range(1, 7):
        store.wanted.add(
            WantedItem(
                media_ref=ref,
                kind="episode",
                status="pending",
                enqueued_at=1,
                followed_id=fid,
                season=2,
                episode=ep_num,
            )
        )
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 6, today=today, last_days_ago=14)
    owned = _StubPerEpisodeOwnership({(2, 1), (2, 2)})  # 2 owned, 4 unowned → 2 <= 3
    bus = EventBus()
    absorbed_events: list[SeasonAbsorbedEpisodes] = []
    bus.subscribe(SeasonAbsorbedEpisodes, absorbed_events.append)

    svc = DetectService(
        store=store,
        ownership=owned,
        registry=MagicMock(),
        event_bus=bus,
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    assert result.status is DetectStatus.OK
    assert len(absorbed_events) == 1
    assert absorbed_events[0].season == 2
    assert len(absorbed_events[0].absorbed_ids) == 4  # 4 unowned → 4 pending eps absorbed

    # Verify episode rows are now absorbed (or done for reconcile-closed owned ones)
    for ep_num in range(1, 7):
        row = store.wanted.find(followed_id=fid, kind="episode", season=2, episode=ep_num)
        assert row is not None
        if (2, ep_num) in owned._owned_eps:
            assert row.status == "done"  # reconcile closed these owned pre-inserted rows
        else:
            assert row.status == "absorbed"


def test_season_detect_boundary_exactly_7_days(store: ConcreteAcquireStore) -> None:
    """R1 boundary: last ep aired exactly 7 days ago → enqueue."""
    ref = MediaRef(tvdb_id=99)
    store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 6, today=today, last_days_ago=7)  # exactly 7
    owned = _StubPerEpisodeOwnership(set())

    svc = DetectService(
        store=store,
        ownership=owned,
        registry=MagicMock(),
        event_bus=EventBus(),
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    season_actions = [a for a in result.actions if a.kind == "season"]
    assert len(season_actions) == 1


def test_season_detect_boundary_exactly_half_owned(store: ConcreteAcquireStore) -> None:
    """R1 boundary: exactly half owned → enqueue."""
    ref = MediaRef(tvdb_id=99)
    store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 6, today=today, last_days_ago=14)
    owned = _StubPerEpisodeOwnership({(2, 1), (2, 2), (2, 3)})  # exactly 3 of 6

    svc = DetectService(
        store=store,
        ownership=owned,
        registry=MagicMock(),
        event_bus=EventBus(),
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=False, today=today, now=100)

    season_actions = [a for a in result.actions if a.kind == "season"]
    assert len(season_actions) == 1


def test_season_detect_dry_run_no_writes(store: ConcreteAcquireStore) -> None:
    """Dry-run: actions recorded but no wanted rows / events."""
    ref = MediaRef(tvdb_id=99)
    store.follow.add(FollowedSeries(media_ref=ref, title="Severance", added_at=1))
    today = date(2024, 6, 15)
    eps = _aired_season(ref, 2, 6, today=today, last_days_ago=14)
    owned = _StubPerEpisodeOwnership(set())

    bus = EventBus()
    emitted: list[WantedEnqueued] = []
    bus.subscribe(WantedEnqueued, emitted.append)

    svc = DetectService(
        store=store,
        ownership=owned,
        registry=MagicMock(),
        event_bus=bus,
        config=_config(),
    )
    with patch("personalscraper.acquire.detect.poll_known", return_value=eps):
        result = svc.run(series=None, dry_run=True, today=today, now=100)

    season_actions = [a for a in result.actions if a.kind == "season"]
    assert len(season_actions) == 1
    # Dry-run: no wanted row persisted
    assert store.wanted.find(followed_id=1, kind="season", season=2, episode=None) is None
    # Dry-run: no events emitted
    assert len(emitted) == 0

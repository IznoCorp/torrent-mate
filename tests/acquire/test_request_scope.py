"""K3 P6: the request scope in the engine (DESIGN O-2 A).

A one-off season request is a ``followed_series`` row of scope ``request``. It is never listed as a
follow, never detected for new episodes, and ends with its season. Nothing writes such a row yet
(P7's ``SeasonAsk`` will), so every row here is seeded by hand, the way that writer will leave it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.desired import QualityProfile, Resolution, quality_profile_to_json
from personalscraper.acquire.detect import DetectService, DetectStatus
from personalscraper.acquire.domain import AiredEpisode, FollowedSeries, SeriesCatalog, WantedItem
from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome, SearchVerdict
from personalscraper.acquire.reconcile import reconcile_wanted
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.conf.models.acquire import AcquireConfig, CadenceConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.core.units import ByteSize

_TODAY = date(2024, 6, 15)
_NOW = 1_700_003_600  # one hour after the rows' ``enqueued_at``: every fresh row is due
_ENQUEUED_AT = 1_700_000_000


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        A migrated :class:`ConcreteAcquireStore`.
    """
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _follow(
    store: ConcreteAcquireStore, tvdb_id: int, title: str = "Show", *, kind: Literal["movie", "show"] = "show"
) -> int:
    """Add a standing follow and return its rowid.

    Args:
        store: The store.
        tvdb_id: The medium's TVDB id.
        title: The medium's title.
        kind: ``"show"`` or ``"movie"``.

    Returns:
        The rowid.
    """
    return store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=tvdb_id), title=title, added_at=1, kind=kind))


def _request(
    store: ConcreteAcquireStore,
    tvdb_id: int,
    title: str = "Owned Show",
    *,
    kind: Literal["movie", "show"] = "show",
    profile: QualityProfile | None = None,
) -> int:
    """Seed a one-off request row, as P7's ``SeasonAsk`` will leave it, and return its rowid.

    Args:
        store: The store.
        tvdb_id: The medium's TVDB id.
        title: The medium's title.
        kind: ``"show"`` or ``"movie"``.
        profile: The projected quality profile, or ``None`` for none.

    Returns:
        The rowid.
    """
    followed_id = _follow(store, tvdb_id, title, kind=kind)
    store._ensure_open().execute(  # noqa: SLF001 — no writer of scope exists yet: P7's SeasonAsk is the one
        "UPDATE followed_series SET scope = 'request', quality_profile_json = ? WHERE id = ?",
        (quality_profile_to_json(profile) if profile is not None else None, followed_id),
    )
    return followed_id


def _season_row(store: ConcreteAcquireStore, followed_id: int, tvdb_id: int, *, season: int = 1) -> int:
    """Add a pending season wanted row of a follow and return its id.

    Args:
        store: The store.
        followed_id: The subject row.
        tvdb_id: The medium's TVDB id.
        season: The season number.

    Returns:
        The wanted row's id.
    """
    return store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=tvdb_id),
            kind="season",
            status="pending",
            enqueued_at=_ENQUEUED_AT,
            followed_id=followed_id,
            season=season,
            episode=None,
            trigger="manual",
        )
    )


# ---------------------------------------------------------------------------
# The readers of the follow rows
# ---------------------------------------------------------------------------


class TestReaders:
    """``list_active`` is the follows; ``list_requests`` the standing requests; ``list_all`` every row."""

    def test_list_active_returns_neither_a_request_nor_a_removed_row(self, store: ConcreteAcquireStore) -> None:
        """A request row and a removed row are not follows, whatever their ``active`` flag says."""
        follow_id = _follow(store, 1, "Followed")
        _request(store, 2, "Requested")
        removed_id = _follow(store, 3, "Removed")
        assert store.follow.mark_removed(removed_id, now=500)
        # A removed row carrying a stale ``active = 1`` (a writer that forgot the projection) is still no follow.
        stale_id = _follow(store, 4, "Stale")
        store._ensure_open().execute("UPDATE followed_series SET removed_at = 600 WHERE id = ?", (stale_id,))  # noqa: SLF001

        assert [f.id for f in store.follow.list_active()] == [follow_id]

    def test_list_requests_returns_the_standing_requests_only(self, store: ConcreteAcquireStore) -> None:
        """Follows and removed requests are not in it."""
        _follow(store, 1, "Followed")
        request_id = _request(store, 2, "Requested")
        ended_id = _request(store, 3, "Ended")
        store.follow.mark_removed(ended_id, now=500)

        assert [r.id for r in store.follow.list_requests()] == [request_id]

    def test_list_all_keeps_every_row(self, store: ConcreteAcquireStore) -> None:
        """The CLI's ``--all`` and the title maps still see requests and removed rows."""
        ids = [_follow(store, 1), _request(store, 2), _request(store, 3)]
        store.follow.mark_removed(ids[2], now=500)

        assert [f.id for f in store.follow.list_all()] == ids

    def test_mark_removed_deactivates_and_is_idempotent(self, store: ConcreteAcquireStore) -> None:
        """The first call writes ``removed_at`` and ``active = 0``; a second leaves the first stamp."""
        request_id = _request(store, 2)

        assert store.follow.mark_removed(request_id, now=500) is True
        assert store.follow.mark_removed(request_id, now=900) is False

        row = store.follow.get(request_id)
        assert row is not None
        assert (row.removed_at, row.active) == (500, False)


# ---------------------------------------------------------------------------
# Detect: a request row is polled, never enqueued
# ---------------------------------------------------------------------------


class _NothingOwned:
    """Ownership stub that owns nothing."""

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        return False


def _detect(store: ConcreteAcquireStore) -> DetectService:
    """Build a DetectService over *store* (the provider poll is patched by the caller).

    Args:
        store: The store.

    Returns:
        The service.
    """
    config = SimpleNamespace(acquire=SimpleNamespace(cadence=CadenceConfig()))
    return DetectService(
        store=store, ownership=_NothingOwned(), registry=MagicMock(), event_bus=EventBus(), config=config
    )


def _aired(ref: MediaRef, season: int, count: int) -> list[AiredEpisode]:
    """Build *count* long-aired episodes of one season.

    Args:
        ref: The series' ref.
        season: The season number.
        count: How many episodes.

    Returns:
        The episodes, oldest first.
    """
    return [
        AiredEpisode(media_ref=ref, season=season, episode=n, air_date=date(2024, 1, n), title=f"Ep{n}")
        for n in range(1, count + 1)
    ]


class TestDetect:
    """Detect reads a request row's aired cache and series status, and enqueues nothing for it."""

    def test_a_request_gets_its_aired_cache_and_status_but_no_wanted_row(self, store: ConcreteAcquireStore) -> None:
        """No episode row and no season row: the season rule never runs on a request."""
        ref = MediaRef(tvdb_id=100)
        request_id = _request(store, 100)
        catalog = SeriesCatalog(
            followed_id=request_id, media_ref=ref, series_status="Ended", episodes=_aired(ref, 1, 4)
        )

        with patch("personalscraper.acquire.detect.poll_catalog", return_value=[catalog]):
            result = _detect(store).run(series=None, dry_run=False, today=_TODAY, now=_NOW)

        assert result.status is DetectStatus.OK
        assert result.actions == []
        assert result.summary.enqueued == 0
        assert [(r.season, r.episode) for r in store.aired.list_for_followed(request_id)] == [
            (1, n) for n in range(1, 5)
        ]
        row = (
            store._ensure_open()
            .execute(  # noqa: SLF001
                "SELECT series_status FROM followed_series WHERE id = ?", (request_id,)
            )
            .fetchone()
        )
        assert row[0] == "Ended"
        assert store.wanted.list_pending() == []

    def test_a_follow_beside_a_request_is_still_detected(self, store: ConcreteAcquireStore) -> None:
        """The request's episodes stay out of the follow's enqueue pass, the follow's go in."""
        follow_ref, request_ref = MediaRef(tvdb_id=1), MediaRef(tvdb_id=100)
        follow_id = _follow(store, 1, "Followed")
        request_id = _request(store, 100)
        catalogs = [
            SeriesCatalog(
                followed_id=follow_id, media_ref=follow_ref, series_status=None, episodes=_aired(follow_ref, 1, 1)
            ),
            SeriesCatalog(
                followed_id=request_id, media_ref=request_ref, series_status=None, episodes=_aired(request_ref, 1, 3)
            ),
        ]

        with patch("personalscraper.acquire.detect.poll_catalog", return_value=catalogs):
            _detect(store).run(series=None, dry_run=False, today=_TODAY, now=_NOW)

        assert {w.followed_id for w in store.wanted.list_pending()} == {follow_id}
        assert len(store.aired.list_for_followed(request_id)) == 3

    def test_a_request_alone_is_polled_not_reported_as_no_active(self, store: ConcreteAcquireStore) -> None:
        """With no follow at all, a standing request is still read."""
        ref = MediaRef(tvdb_id=100)
        request_id = _request(store, 100)
        catalog = SeriesCatalog(followed_id=request_id, media_ref=ref, series_status=None, episodes=_aired(ref, 1, 2))

        with patch("personalscraper.acquire.detect.poll_catalog", return_value=[catalog]) as poll:
            result = _detect(store).run(series=None, dry_run=False, today=_TODAY, now=_NOW)

        assert result.status is DetectStatus.OK
        assert [f.id for f in poll.call_args.args[0]] == [request_id]

    def test_a_removed_request_is_not_polled(self, store: ConcreteAcquireStore) -> None:
        """An ended request leaves detect's read."""
        request_id = _request(store, 100)
        store.follow.mark_removed(request_id, now=500)

        with patch("personalscraper.acquire.detect.poll_catalog", return_value=[]) as poll:
            result = _detect(store).run(series=None, dry_run=False, today=_TODAY, now=_NOW)

        assert result.status is DetectStatus.NO_ACTIVE
        poll.assert_not_called()

    def test_a_film_request_enqueues_no_film_row(self, store: ConcreteAcquireStore) -> None:
        """A request of a film is not detected as a film follow is."""
        _request(store, 200, "A Film", kind="movie")

        with patch("personalscraper.acquire.detect.poll_catalog", return_value=[]):
            _detect(store).run(series=None, dry_run=False, today=_TODAY, now=_NOW)

        assert store.wanted.list_pending() == []

    def test_a_dry_run_writes_nothing_for_a_request(self, store: ConcreteAcquireStore) -> None:
        """--dry-run leaves a request's cache and status alone."""
        ref = MediaRef(tvdb_id=100)
        request_id = _request(store, 100)
        catalog = SeriesCatalog(
            followed_id=request_id, media_ref=ref, series_status="Ended", episodes=_aired(ref, 1, 2)
        )

        with patch("personalscraper.acquire.detect.poll_catalog", return_value=[catalog]):
            _detect(store).run(series=None, dry_run=True, today=_TODAY, now=_NOW)

        assert store.aired.list_for_followed(request_id) == []

    def test_the_series_filter_reaches_a_request(self, store: ConcreteAcquireStore) -> None:
        """``--series`` by id names a request row as it names a follow; another id matches none."""
        request_id = _request(store, 100)

        with patch("personalscraper.acquire.detect.poll_catalog", return_value=[]):
            hit = _detect(store).run(series=str(request_id), dry_run=False, today=_TODAY, now=_NOW)
            miss = _detect(store).run(series=str(request_id + 1), dry_run=False, today=_TODAY, now=_NOW)

        assert hit.status is DetectStatus.OK
        assert miss.status is DetectStatus.NO_MATCH


# ---------------------------------------------------------------------------
# The season of a request is searched and grabbed like a follow's
# ---------------------------------------------------------------------------


def _service(store: ConcreteAcquireStore, orchestrator: GrabOrchestrator) -> AcquisitionService:
    """Build the acquisition service over a mock orchestrator.

    Args:
        store: The store.
        orchestrator: The mock orchestrator.

    Returns:
        The service.
    """
    config = MagicMock()
    config.acquire = AcquireConfig()
    return AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=MagicMock(),
        config=config,
    )


def _takeable() -> TrackerResult:
    """A tracker result the search pass can state as available."""
    return TrackerResult(
        provider="c411",
        tracker_id="t1",
        title="Owned Show S01 MULTi 1080p WEB x265-GRP",
        size=ByteSize(5_000_000_000),
        seeders=50,
        leechers=0,
        resolution="1080p",
        info_hash="aaaa1234",
        download_url="https://c411.test/torrent/1",
    )


class TestSeasonOfARequest:
    """The request row is the season's subject: its profile reaches both passes, as a follow's does."""

    @pytest.fixture(autouse=True)
    def _clock(self) -> Iterator[None]:
        """Pin the service clock so a fresh row is due."""
        with patch("personalscraper.acquire.service.time.time", return_value=_NOW):
            yield

    def test_the_search_pass_resolves_the_request_s_profile(self, store: ConcreteAcquireStore) -> None:
        """The profile the search runs under is the request row's."""
        request_id = _request(store, 100, profile=QualityProfile(min_resolution=Resolution.R1080P))
        _season_row(store, request_id, 100)
        orch = MagicMock(spec=GrabOrchestrator)
        orch.search.return_value = SearchVerdict(
            disposition="available", outcome="available", found=1, chosen=_takeable()
        )

        summary = _service(store, orch).run_search()

        assert summary.available == 1
        item, profile = orch.search.call_args.args[:2]
        assert (item.kind, item.followed_id, item.season) == ("season", request_id, 1)
        assert profile.min_resolution is Resolution.R1080P
        assert [r.status for r in store.wanted.list_available()] == ["available"]

    def test_the_grab_pass_takes_the_season_under_the_request_s_profile(self, store: ConcreteAcquireStore) -> None:
        """An available season row of a request is grabbed, under its subject's profile."""
        request_id = _request(store, 100, profile=QualityProfile(min_resolution=Resolution.R720P))
        wanted_id = _season_row(store, request_id, 100)
        store.wanted.claim_for_search(wanted_id, _NOW)
        store.wanted.record_search_outcome(wanted_id, "available", 1)
        store.wanted.set_status(wanted_id, "available")
        orch = MagicMock(spec=GrabOrchestrator)
        orch.grab.return_value = GrabOutcome(disposition="success", info_hash="h", found=1)

        summary = _service(store, orch).run()

        assert summary.grabbed == 1
        item, profile = orch.grab.call_args.args[:2]
        assert item.followed_id == request_id
        assert profile.min_resolution is Resolution.R720P

    def test_the_aired_count_and_title_come_from_the_request_row(self, store: ConcreteAcquireStore) -> None:
        """The R2 conversion's reads (aired episodes, titles) key on the request row like a follow's."""
        request_id = _request(store, 100, "Owned Show")
        store.aired.replace_for_followed(
            request_id, [(1, n, f"E{n}", f"2024-01-{n:02d}") for n in range(1, 4)], now=_ENQUEUED_AT
        )
        orch = MagicMock(spec=GrabOrchestrator)
        service = _service(store, orch)

        assert service._aired_episodes_for_season(request_id, 1) == [1, 2, 3]  # noqa: SLF001
        assert service._follow_titles(request_id) == ["Owned Show", None]  # noqa: SLF001


# ---------------------------------------------------------------------------
# Reconciliation ends a request with its season
# ---------------------------------------------------------------------------


class _Owns:
    """Ownership stub: owns exactly the (season, episode) pairs it was given."""

    def __init__(self, pairs: set[tuple[int | None, int | None]]) -> None:
        self._pairs = pairs

    def owns(self, media_ref: MediaRef, *, kind: str, season: int | None = None, episode: int | None = None) -> bool:
        return (season, episode) in self._pairs


def _reconcile(store: ConcreteAcquireStore, owned: set[tuple[int | None, int | None]] | None = None) -> None:
    """Run one reconciliation sweep with no torrent client.

    Args:
        store: The store.
        owned: The (season, episode) pairs the library owns.
    """
    reconcile_wanted(store, _Owns(owned or set()), client_items=None, event_bus=EventBus())


def _removed(store: ConcreteAcquireStore, followed_id: int) -> bool:
    """Say whether a follow row is marked removed.

    Args:
        store: The store.
        followed_id: The row.

    Returns:
        ``True`` once ``removed_at`` is set.
    """
    row = store.follow.get(followed_id)
    assert row is not None
    return row.removed_at is not None


class TestRequestEnds:
    """A request is removed once its season wanted is closed and nothing of it is open."""

    def test_an_open_season_keeps_the_request(self, store: ConcreteAcquireStore) -> None:
        """A pending season row: the request stands."""
        request_id = _request(store, 100)
        _season_row(store, request_id, 100)

        _reconcile(store)

        assert not _removed(store, request_id)

    @pytest.mark.parametrize("status", ["done", "abandoned", "fallback_episodes"])
    def test_a_closed_season_ends_the_request(self, store: ConcreteAcquireStore, status: str) -> None:
        """Whichever way the season row closed, with nothing left open the row is removed and inactive."""
        request_id = _request(store, 100)
        wanted_id = _season_row(store, request_id, 100)
        store.wanted.set_status(wanted_id, status)  # type: ignore[arg-type]

        _reconcile(store)

        row = store.follow.get(request_id)
        assert row is not None
        assert row.removed_at is not None and row.active is False
        assert store.follow.list_requests() == []

    def test_an_open_episode_of_the_fallback_keeps_the_request(self, store: ConcreteAcquireStore) -> None:
        """The season fell back to episodes: the request lasts until those close."""
        request_id = _request(store, 100)
        wanted_id = _season_row(store, request_id, 100)
        store.wanted.set_status(wanted_id, "fallback_episodes")
        episode_id = store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=100),
                kind="episode",
                status="pending",
                enqueued_at=_ENQUEUED_AT,
                followed_id=request_id,
                season=1,
                episode=2,
            )
        )

        _reconcile(store)
        assert not _removed(store, request_id)

        store.wanted.set_status(episode_id, "done")
        _reconcile(store)
        assert _removed(store, request_id)

    def test_the_pass_that_closes_the_season_ends_the_request(self, store: ConcreteAcquireStore) -> None:
        """A grabbed season whose aired episodes are all owned closes ``done`` and ends the request in one sweep."""
        request_id = _request(store, 100)
        wanted_id = _season_row(store, request_id, 100)
        store.wanted.mark_grabbed(wanted_id, "abc123")
        store.aired.replace_for_followed(
            request_id, [(1, 1, "E1", "2024-01-01"), (1, 2, "E2", "2024-01-08")], now=_ENQUEUED_AT
        )

        _reconcile(store, owned={(1, 1), (1, 2)})

        season = store.wanted.get(wanted_id)
        assert season is not None and season.status == "done"
        assert _removed(store, request_id)

    def test_a_request_with_no_season_row_is_kept(self, store: ConcreteAcquireStore) -> None:
        """Nothing asked yet (the ask writes the season row with the request): never ended on silence."""
        request_id = _request(store, 100)

        _reconcile(store)

        assert not _removed(store, request_id)

    def test_a_follow_is_never_ended_by_its_closed_season(self, store: ConcreteAcquireStore) -> None:
        """Only a request ends with its season; a follow stands."""
        follow_id = _follow(store, 1)
        wanted_id = _season_row(store, follow_id, 1)
        store.wanted.set_status(wanted_id, "done")

        _reconcile(store)

        assert not _removed(store, follow_id)
        assert [f.id for f in store.follow.list_active()] == [follow_id]

    def test_a_removed_request_is_left_as_it_is(self, store: ConcreteAcquireStore) -> None:
        """A second sweep keeps the first stamp."""
        request_id = _request(store, 100)
        wanted_id = _season_row(store, request_id, 100)
        store.wanted.set_status(wanted_id, "done")
        _reconcile(store)
        first = store.follow.get(request_id)

        _reconcile(store)

        assert store.follow.get(request_id) == first

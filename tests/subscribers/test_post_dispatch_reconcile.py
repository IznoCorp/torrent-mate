"""Tests for the post-dispatch reconcile subscriber (ACQUIRE-02).

The dispatch-time reconciliation that used to live inside ``DeleteAuthority``
(close owned wanted rows, retire followed films, emit ``FilmAcquired``) moved
here: the subscriber listens for :class:`LibraryScanCompleted` — the dispatch
step's ``_enrich_after_dispatch`` fires one after the library is refreshed — and
runs the canonical ownership pass, then retires acquired films.

These tests use a REAL acquire store (temp ``acquire.db``) + a REAL
:class:`EventBus`, and a fake :class:`OwnershipChecker`, so they exercise the
real store writes + real bus emission rather than a vacuous mock.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock

import pytest

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.events import FilmAcquired
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.indexer.events import LibraryScanCompleted
from personalscraper.subscribers.dispatch_reconcile import (
    PostDispatchReconcileSubscriber,
    build_post_dispatch_reconcile_subscriber,
)


class _OwnsAll:
    """OwnershipChecker fake that reports every work as owned."""

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Always report ownership (the library holds the work)."""
        return True


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real lazy acquire store on a temp acquire.db, closed afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _scan_completed() -> LibraryScanCompleted:
    """Build a representative post-dispatch enrich-scan-completed event."""
    return LibraryScanCompleted(mode="enrich", scanned=3, errors=0, elapsed_s=0.1)


def test_post_dispatch_reconcile_subscriber_retires_acquired_film(store: ConcreteAcquireStore) -> None:
    """A scan-completed after dispatch closes the movie row, retires it, emits FilmAcquired.

    This is the D2-A rule the delete-permit used to own inline: the followed film
    leaves the follow list the moment its media lands, with an operator feed toast.
    """
    followed_id = store.follow.add(
        FollowedSeries(media_ref=MediaRef(tmdb_id=10_001), title="Ferrari", added_at=1_750_000_000, kind="movie")
    )
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tmdb_id=10_001),
            kind="movie",
            status="pending",
            enqueued_at=1_750_000_000,
            followed_id=followed_id,
        )
    )
    store.wanted.mark_grabbed(wanted_id, "cafef00dbaadf00d")

    bus = EventBus()
    captured: list[FilmAcquired] = []
    bus.subscribe(FilmAcquired, captured.append)
    PostDispatchReconcileSubscriber(bus, store, _OwnsAll())

    bus.emit(_scan_completed())

    row = store.wanted.get(wanted_id)
    assert row is not None
    assert row.status == "done"

    follow = store.follow.get(followed_id)
    assert follow is not None
    assert follow.active is False

    assert len(captured) == 1
    assert isinstance(captured[0], FilmAcquired)
    assert captured[0].followed_id == followed_id
    assert captured[0].title == "Ferrari"
    assert captured[0].media_ref.tmdb_id == 10_001


def test_post_dispatch_reconcile_subscriber_does_not_retire_series(store: ConcreteAcquireStore) -> None:
    """A dispatched EPISODE closes its row but never retires the series follow."""
    followed_id = store.follow.add(
        FollowedSeries(media_ref=MediaRef(tvdb_id=403245), title="Silo", added_at=1_750_000_000, kind="show")
    )
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            season=3,
            episode=5,
            followed_id=followed_id,
        )
    )
    store.wanted.mark_grabbed(wanted_id, "0badcafe0badcafe")

    bus = EventBus()
    captured: list[FilmAcquired] = []
    bus.subscribe(FilmAcquired, captured.append)
    PostDispatchReconcileSubscriber(bus, store, _OwnsAll())

    bus.emit(_scan_completed())

    assert store.wanted.get(wanted_id).status == "done"  # type: ignore[union-attr]
    follow = store.follow.get(followed_id)
    assert follow is not None
    assert follow.active is True  # the show stays followed
    assert captured == []  # no film retired → no FilmAcquired


def test_post_dispatch_reconcile_subscriber_idempotent_no_double_emit(store: ConcreteAcquireStore) -> None:
    """A second scan-completed does not re-close a done row nor re-emit FilmAcquired."""
    followed_id = store.follow.add(
        FollowedSeries(media_ref=MediaRef(tmdb_id=10_002), title="Dune", added_at=1_750_000_000, kind="movie")
    )
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tmdb_id=10_002),
            kind="movie",
            status="pending",
            enqueued_at=1_750_000_000,
            followed_id=followed_id,
        )
    )
    store.wanted.mark_grabbed(wanted_id, "beefbeefbeefbeef")

    bus = EventBus()
    captured: list[FilmAcquired] = []
    bus.subscribe(FilmAcquired, captured.append)
    PostDispatchReconcileSubscriber(bus, store, _OwnsAll())

    bus.emit(_scan_completed())
    bus.emit(_scan_completed())

    assert len(captured) == 1  # emitted once, never twice


def test_post_dispatch_reconcile_subscriber_fail_soft_on_reconcile_error() -> None:
    """A reconcile error is swallowed — the scanner's finally-block emit is never disrupted."""
    broken_store = MagicMock()
    broken_store.wanted.list_grabbed.side_effect = RuntimeError("db locked")

    bus = EventBus()
    PostDispatchReconcileSubscriber(bus, broken_store, _OwnsAll())

    # Must not raise — the subscriber wraps reconcile_wanted in a fail-soft guard.
    bus.emit(_scan_completed())


def test_post_dispatch_reconcile_subscriber_close_unsubscribes(store: ConcreteAcquireStore) -> None:
    """After close(), a scan-completed no longer triggers reconciliation."""
    wanted_id = store.wanted.add(
        WantedItem(media_ref=MediaRef(tmdb_id=10_003), kind="movie", status="pending", enqueued_at=1_750_000_000)
    )
    store.wanted.mark_grabbed(wanted_id, "0000111122223333")

    bus = EventBus()
    sub = PostDispatchReconcileSubscriber(bus, store, _OwnsAll())
    sub.close()

    bus.emit(_scan_completed())

    assert store.wanted.get(wanted_id).status == "grabbed"  # type: ignore[union-attr] — untouched


def test_build_post_dispatch_reconcile_subscriber_none_without_store() -> None:
    """The builder returns None when there is no acquire handle or no store.

    The signature is narrow (boundary rule): the builder takes the bus + the
    acquire lobe handle, never the whole AppContext — the composition roots
    destructure the bundle themselves.
    """
    bus = EventBus()
    assert build_post_dispatch_reconcile_subscriber(bus, None) is None

    acquire = MagicMock()
    acquire.store = None
    assert build_post_dispatch_reconcile_subscriber(bus, acquire) is None


class _OwnsNothingThenEverything:
    """Ownership fake that answers False on the first sweep and True afterwards.

    Reproduces the 2026-08-05 shape: the dispatch merged and RENAMED ~46 episode files,
    so the incremental scan that fires ``LibraryScanCompleted`` was still re-indexing when
    the reconcile ran — the season read « not owned », and nothing tried again until the
    grab cron twelve hours later.
    """

    def __init__(self) -> None:
        """Start out answering « not owned »."""
        self.settled = False

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        """Answer ownership, flipping to True once :attr:`settled` is set."""
        return self.settled


class TestSettleClosesWhatTheScanRaceMissed:
    """§14.3 — « la fermeture suit la médiathèque, pas une horloge »."""

    def test_settle_closes_a_row_the_scan_completed_sweep_could_not(
        self, store: ConcreteAcquireStore
    ) -> None:
        """Un second passage DÉTERMINISTE, après que la médiathèque s'est stabilisée.

        Le passage sur ``LibraryScanCompleted`` tombe pendant la ré-indexation et ne peut
        rien fermer ; ``settle()`` est appelé une fois toute la maintenance post-dispatch
        terminée et ferme la ligne. Sans lui, la file reste « récupéré » jusqu'au cron
        suivant — une fermeture qui se joue sur une course, ce que §14.3 interdit.
        """
        bus = EventBus()
        ownership = _OwnsNothingThenEverything()
        followed_id = store.follow.add(
            FollowedSeries(media_ref=MediaRef(tvdb_id=73141), title="American Dad!", added_at=1)
        )
        wanted_id = store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=73141),
                kind="episode",
                status="pending",
                enqueued_at=1_750_000_000,
                season=15,
                episode=21,
                followed_id=followed_id,
            )
        )
        store.wanted.mark_grabbed(wanted_id, "d412a66379ec")
        sub = PostDispatchReconcileSubscriber(bus, store, ownership)
        try:
            # 1) le scan se termine alors que la médiathèque est encore en cours d'écriture
            bus.emit(LibraryScanCompleted(mode="incremental", scanned=1491, errors=0, elapsed_s=1.0))
            assert store.wanted.get(wanted_id).status == "grabbed", "rien à fermer à cet instant"

            # 2) la maintenance post-dispatch se termine, la médiathèque est stable
            ownership.settled = True
            sub.settle()

            assert store.wanted.get(wanted_id).status == "done"
        finally:
            sub.close()

    def test_settle_is_a_no_op_once_everything_is_closed(self, store: ConcreteAcquireStore) -> None:
        """Idempotent : appelé sur un état déjà réconcilié, il ne change rien."""
        bus = EventBus()
        sub = PostDispatchReconcileSubscriber(bus, store, _OwnsAll())
        try:
            sub.settle()
            sub.settle()
        finally:
            sub.close()

    def test_settle_never_raises_into_its_caller(self, store: ConcreteAcquireStore) -> None:
        """Fail-soft comme le handler : le dispatch ne peut pas échouer sur un settle."""
        bus = EventBus()
        exploding = MagicMock()
        exploding.owns.side_effect = RuntimeError("library exploded")
        followed_id = store.follow.add(
            FollowedSeries(media_ref=MediaRef(tvdb_id=1), title="X", added_at=1)
        )
        wanted_id = store.wanted.add(
            WantedItem(
                media_ref=MediaRef(tvdb_id=1),
                kind="episode",
                status="pending",
                enqueued_at=1_750_000_000,
                season=1,
                episode=1,
                followed_id=followed_id,
            )
        )
        store.wanted.mark_grabbed(wanted_id, "abc")
        sub = PostDispatchReconcileSubscriber(bus, store, exploding)
        try:
            sub.settle()  # must not raise
        finally:
            sub.close()

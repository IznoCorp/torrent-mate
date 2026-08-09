"""End-to-end dispatch fan-out: one dispatch → Plex refresh AND acquisition close.

The recurring « acquis mais pas dans Plex » incident (#22/#25/#26): media landed
on disk but the chain never reached Plex, and the acquisition loop never closed.
The fix wires two subscribers on the dispatch bus — ``PlexSubscriber``
(``ItemDispatched`` → targeted Plex scan) and ``PostDispatchReconcileSubscriber``
(``LibraryScanCompleted`` → close the grabbed wanted row + retire the followed
film + emit ``FilmAcquired``).

Each subscriber is unit-tested in isolation; nothing proves they BOTH fire off a
single dispatch over one bus with a real acquire store. This test closes that
seam: a dispatched acquired film triggers the Plex refresh AND closes its
acquisition loop — the exact fan-out the #26 chain needed.

``PlexSubscriber`` refreshes on a daemon thread (fire-and-forget); the thread is
patched to run synchronously so the assertion is deterministic (no sleep/poll).

Integration tier (real store + real bus, Plex client faked): default suite.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.events import FilmAcquired
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.dispatch.events import ItemDispatched
from personalscraper.indexer.events import LibraryScanCompleted
from personalscraper.subscribers.dispatch_reconcile import PostDispatchReconcileSubscriber
from personalscraper.subscribers.plex import PlexSubscriber


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a real acquire store on a temp acquire.db, closed afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


class _OwnsAll:
    """Ownership stub: the dispatched item is now on disk, so everything is owned."""

    def owns(
        self,
        media_ref: MediaRef,
        *,
        kind: Literal["movie", "episode"],
        season: int | None = None,
        episode: int | None = None,
    ) -> bool:
        return True


class _OwnsOnly:
    """Ownership stub: owns exactly the media_refs it was given (value equality)."""

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


class _SyncThread:
    """A ``threading.Thread`` stand-in that runs its target inline on ``start()``.

    Makes the PlexSubscriber's fire-and-forget refresh deterministic — the
    assertion no longer races a real daemon thread.
    """

    def __init__(self, *, target: object = None, args: tuple[object, ...] = (), **_: object) -> None:
        self._target = target
        self._args = args

    def start(self) -> None:
        if callable(self._target):
            self._target(*self._args)


def test_dispatch_triggers_plex_refresh_and_closes_acquisition(store: ConcreteAcquireStore) -> None:
    """One dispatched acquired film → Plex refresh AND wanted done + film retired."""
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
    plex_client = MagicMock()
    PlexSubscriber(bus, plex_client)
    PostDispatchReconcileSubscriber(bus, store, _OwnsAll())
    acquired: list[FilmAcquired] = []
    bus.subscribe(FilmAcquired, acquired.append)

    target = Path("/Volumes/DiskTest/medias/films/Ferrari (2023)")

    # 1) Dispatch fires ItemDispatched → Plex refresh (synchronous via the stub).
    with patch("personalscraper.subscribers.plex.threading.Thread", _SyncThread):
        bus.emit(
            ItemDispatched(
                item="Ferrari (2023)",
                target_disk=Path("/Volumes/DiskTest"),
                category_id="movies",
                action="moved",
                target_path=target,
            )
        )
    plex_client.refresh.assert_called_once_with(target)

    # 2) The scan completes → the acquisition loop closes on the same bus.
    bus.emit(LibraryScanCompleted(mode="enrich", scanned=1, errors=0, elapsed_s=0.1))

    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"
    follow = store.follow.get(followed_id)
    # An acquired film LEAVES the follows (it is not « paused ») — the file is
    # confirmed at its destination, so the follow has nothing left to want.
    assert follow is None
    assert len(acquired) == 1 and acquired[0].followed_id == followed_id


def test_dispatch_without_target_path_skips_plex_but_still_reconciles(store: ConcreteAcquireStore) -> None:
    """A target_path-less dispatch skips the refresh yet still closes the loop.

    Honest degradation: no folder to scan → no Plex call; the reconcile half is
    independent (it keys off LibraryScanCompleted) and must still fire.
    """
    followed_id = store.follow.add(
        FollowedSeries(media_ref=MediaRef(tmdb_id=20_002), title="Le Mans", added_at=1_750_000_000, kind="movie")
    )
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tmdb_id=20_002),
            kind="movie",
            status="pending",
            enqueued_at=1_750_000_000,
            followed_id=followed_id,
        )
    )
    store.wanted.mark_grabbed(wanted_id, "deadbeefdeadbeef")

    bus = EventBus()
    plex_client = MagicMock()
    PlexSubscriber(bus, plex_client)
    PostDispatchReconcileSubscriber(bus, store, _OwnsAll())

    with patch("personalscraper.subscribers.plex.threading.Thread", _SyncThread):
        bus.emit(
            ItemDispatched(
                item="Le Mans (1971)",
                target_disk=Path("/Volumes/DiskTest"),
                category_id="movies",
                action="moved",
                target_path=None,
            )
        )
    plex_client.refresh.assert_not_called()

    bus.emit(LibraryScanCompleted(mode="enrich", scanned=1, errors=0, elapsed_s=0.1))
    row = store.wanted.get(wanted_id)
    assert row is not None and row.status == "done"


def test_reconcile_closes_only_owned_rows(store: ConcreteAcquireStore) -> None:
    """Ownership is consulted: a grabbed-but-NOT-owned row is never closed to done.

    Guards against a reconcile that ignored ownership and closed every open row.
    Two grabbed films, ownership owns only the first → only the first goes done.
    """
    owned_ref = MediaRef(tmdb_id=40_004)
    unowned_ref = MediaRef(tmdb_id=50_005)
    owned_id = store.wanted.add(
        WantedItem(media_ref=owned_ref, kind="movie", status="pending", enqueued_at=1, followed_id=None)
    )
    unowned_id = store.wanted.add(
        WantedItem(media_ref=unowned_ref, kind="movie", status="pending", enqueued_at=1, followed_id=None)
    )
    store.wanted.mark_grabbed(owned_id, "aaaa1111")
    store.wanted.mark_grabbed(unowned_id, "bbbb2222")

    bus = EventBus()
    PostDispatchReconcileSubscriber(bus, store, _OwnsOnly({owned_ref}))
    bus.emit(LibraryScanCompleted(mode="enrich", scanned=1, errors=0, elapsed_s=0.1))

    owned_row = store.wanted.get(owned_id)
    unowned_row = store.wanted.get(unowned_id)
    assert owned_row is not None and owned_row.status == "done"
    assert unowned_row is not None and unowned_row.status != "done"


def test_reconcile_prunes_orphaned_provenance_keeps_dispatched(store: ConcreteAcquireStore) -> None:
    """Phase 5 (5.1): the post-dispatch reconcile prunes ORPHANED in-flight provenance.

    FS = truth: a mid-pipeline row whose staging folder vanished is dropped; a
    dispatched row (completed journey, its staging path legitimately gone) is KEPT.
    """
    # Orphaned in-flight row — its staging path does not exist → pruned.
    store.provenance.upsert_grab("orph", followed_id=None, media_ref=MediaRef(tvdb_id=1), kind="movie", grabbed_at=1)
    store.provenance.set_ingest("orph", ingest_path="/tmp/provenance-does-not-exist-xyz", ingested_at=1)
    # Dispatched row — staging path also gone, but the journey completed → kept.
    store.provenance.upsert_grab("done", followed_id=None, media_ref=MediaRef(tvdb_id=2), kind="movie", grabbed_at=1)
    store.provenance.set_ingest("done", ingest_path="/tmp/provenance-also-gone-xyz", ingested_at=1)
    store.provenance.record_dispatch_by_path(
        "/tmp/provenance-also-gone-xyz", dispatch_path="/Volumes/Disk/films/Done", dispatched_at=2
    )

    bus = EventBus()
    PostDispatchReconcileSubscriber(bus, store, _OwnsAll())
    bus.emit(LibraryScanCompleted(mode="enrich", scanned=1, errors=0, elapsed_s=0.1))

    assert store.provenance.by_hash("orph") is None, "orphaned in-flight row must be pruned"
    assert store.provenance.by_hash("done") is not None, "dispatched (completed) row must be kept"

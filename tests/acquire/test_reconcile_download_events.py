"""Behavior tests for the download-event emission in ``reconcile_wanted`` (O4/D6-D9).

The reconcile sweep is the single truthful observation point for download
progress: for every open hash-carrying row present in the client it emits
``DownloadStarted`` / ``DownloadProgressed`` / ``DownloadCompleted`` with
exactly-once semantics backed by the ``download_marks`` table — the mark is
persisted BEFORE the emit (emit-after-persist), only the HIGHEST crossed
25/50/75 threshold fires per pass (D8), regressions never re-emit, and marks
are pruned when the row leaves the open set (D7). All against a REAL temp
store, matching the reconcile test-suite convention.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire._download_marks import DownloadMark
from personalscraper.acquire.domain import FollowedSeries, SeedObligation, WantedItem
from personalscraper.acquire.events import DownloadCompleted, DownloadProgressed, DownloadStarted
from personalscraper.acquire.reconcile import reconcile_wanted
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.core.identity import MediaRef

_HASH = "feed0001"


class _NoOwnership:
    """Ownership stub that owns nothing — rows stay open through the sweep."""

    def owns(self, media_ref: MediaRef, *, kind: str, season: int | None = None, episode: int | None = None) -> bool:
        return False


class _OwnsAllOwnership:
    """Ownership stub that owns every work — rows close ``done``."""

    def owns(self, media_ref: MediaRef, *, kind: str, season: int | None = None, episode: int | None = None) -> bool:
        return True


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    yield s
    s.close()


def _grabbed(store: ConcreteAcquireStore, *, info_hash: str = _HASH, followed_id: int | None = None) -> int:
    """Insert one grabbed episode row carrying *info_hash* and return its id."""
    wanted_id = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=403245),
            kind="episode",
            status="pending",
            enqueued_at=1_750_000_000,
            followed_id=followed_id,
            season=3,
            episode=1,
        )
    )
    store.wanted.mark_grabbed(wanted_id, info_hash)
    return wanted_id


def _item(hash_: str, progress: float) -> TorrentItem:
    """A live client item for *hash_* at *progress*."""
    return TorrentItem(hash=hash_, name=f"release-{hash_}", size_bytes=2048, progress=progress, state="downloading")


def _collector(bus: EventBus) -> list[Event]:
    """Subscribe to the three download event types; return the capture list."""
    events: list[Event] = []
    bus.subscribe(DownloadStarted, events.append)
    bus.subscribe(DownloadProgressed, events.append)
    bus.subscribe(DownloadCompleted, events.append)
    return events


def test_fresh_hash_mid_download_emits_started_only(store: ConcreteAcquireStore) -> None:
    """First sighting below every threshold → exactly one ``DownloadStarted``.

    Title comes from the follow, provider from the seed obligation recorded at
    grab time — the row itself carries neither.
    """
    followed_id = store.follow.add(
        FollowedSeries(media_ref=MediaRef(tvdb_id=403245), title="Silo", added_at=1_750_000_000, kind="show")
    )
    _grabbed(store, followed_id=followed_id)
    store.seed.add(
        SeedObligation(info_hash=_HASH, source_tracker="c411", min_seed_time_s=259_200, min_ratio=1.0, added_at=1)
    )
    bus = EventBus()
    events = _collector(bus)

    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.10)}, event_bus=bus)

    assert [type(e) for e in events] == [DownloadStarted]
    started = events[0]
    assert isinstance(started, DownloadStarted)
    assert started.info_hash == _HASH
    assert started.title == "Silo"
    assert started.provider == "c411"
    assert started.kind == "episode"


def test_already_complete_first_sighting_emits_completed_only(store: ConcreteAcquireStore) -> None:
    """Progress >= 1.0 on first sighting → ONLY Completed, no synthetic backfill.

    Without a recorded obligation the provider is an honest ``"unknown"``, and
    without a follow the title falls back to the client's own display name.
    """
    _grabbed(store)
    bus = EventBus()
    events = _collector(bus)

    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 1.0)}, event_bus=bus)

    assert [type(e) for e in events] == [DownloadCompleted]
    completed = events[0]
    assert isinstance(completed, DownloadCompleted)
    assert completed.info_hash == _HASH
    assert completed.title == f"release-{_HASH}"
    assert completed.provider == "unknown"
    mark = store.download_marks.get(_HASH)
    assert mark is not None
    assert mark.completed_emitted is True and mark.started_emitted is True


def test_threshold_25_crossing_emits_one_progressed(store: ConcreteAcquireStore) -> None:
    """Started already emitted, last_threshold=0, progress 0.30 → one Progressed(25)."""
    _grabbed(store)
    store.download_marks.upsert(_HASH, started=True)
    bus = EventBus()
    events = _collector(bus)

    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.30)}, event_bus=bus)

    assert [type(e) for e in events] == [DownloadProgressed]
    progressed = events[0]
    assert isinstance(progressed, DownloadProgressed)
    assert progressed.threshold_pct == 25
    assert progressed.progress == 0.30
    mark = store.download_marks.get(_HASH)
    assert mark is not None and mark.last_threshold == 25


def test_threshold_50_skips_25(store: ConcreteAcquireStore) -> None:
    """last_threshold=25, progress 0.55 → ONE Progressed(50) — never a replayed 25."""
    _grabbed(store)
    store.download_marks.upsert(_HASH, started=True, threshold=25)
    bus = EventBus()
    events = _collector(bus)

    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.55)}, event_bus=bus)

    assert [type(e) for e in events] == [DownloadProgressed]
    progressed = events[0]
    assert isinstance(progressed, DownloadProgressed)
    assert progressed.threshold_pct == 50


def test_big_jump_emits_only_the_highest_crossed_threshold(store: ConcreteAcquireStore) -> None:
    """D8: a 0 → 0.60 jump emits ONE Progressed with 50 — never 25 then 50."""
    _grabbed(store)
    store.download_marks.upsert(_HASH, started=True)
    bus = EventBus()
    events = _collector(bus)

    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.60)}, event_bus=bus)

    assert [type(e) for e in events] == [DownloadProgressed]
    progressed = events[0]
    assert isinstance(progressed, DownloadProgressed)
    assert progressed.threshold_pct == 50


def test_completed_mark_never_reemits_started_or_progressed(store: ConcreteAcquireStore) -> None:
    """Regression (review MAJOR): a completed mark is FINAL — no phantom Progressed.

    A qBittorrent recheck drops the observed progress below 1.0 while the row
    is still open. The completed branch never advanced ``last_threshold``, so
    the sweep emitted Progressed events AFTER the Completed. With the guard,
    a completed mark at progress 0.55 emits exactly NOTHING.
    """
    _grabbed(store)
    store.download_marks.upsert(_HASH, started=True, completed=True)
    bus = EventBus()
    events = _collector(bus)

    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.55)}, event_bus=bus)

    assert events == [], "a completed mark must never re-emit Started/Progressed on a recheck regression"
    mark = store.download_marks.get(_HASH)
    assert mark is not None and mark.completed_emitted is True


def test_progress_regression_never_reemits(store: ConcreteAcquireStore) -> None:
    """QBit recheck 0.80 → 0.20 with last_threshold=75 → zero emits, mark untouched."""
    _grabbed(store)
    store.download_marks.upsert(_HASH, started=True, threshold=75)
    bus = EventBus()
    events = _collector(bus)

    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.20)}, event_bus=bus)

    assert events == []
    mark = store.download_marks.get(_HASH)
    assert mark is not None and mark.last_threshold == 75


def test_second_pass_same_state_emits_nothing(store: ConcreteAcquireStore) -> None:
    """Exactly-once (D7): an unchanged client state re-emits NOTHING on pass two."""
    _grabbed(store)
    bus = EventBus()
    events = _collector(bus)
    client_items = {_HASH: _item(_HASH, 0.30)}

    reconcile_wanted(store, _NoOwnership(), client_items=client_items, event_bus=bus)
    first_pass = list(events)
    reconcile_wanted(store, _NoOwnership(), client_items=client_items, event_bus=bus)

    assert [type(e) for e in first_pass] == [DownloadStarted, DownloadProgressed]
    assert events == first_pass, "the second pass must emit zero download events"


def test_row_close_prunes_the_mark(store: ConcreteAcquireStore) -> None:
    """D7: once the sweep closes the row, its mark leaves ``download_marks``."""
    _grabbed(store)
    bus = EventBus()
    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.30)}, event_bus=bus)
    assert store.download_marks.get(_HASH) is not None

    events = _collector(bus)
    reconcile_wanted(store, _OwnsAllOwnership(), client_items={_HASH: _item(_HASH, 0.90)}, event_bus=bus)

    assert store.download_marks.get(_HASH) is None, "a closed row's mark must be pruned in the same sweep"
    assert events == [], "a row closed by THIS sweep must not fire download events on its way out"


def test_stale_read_concurrent_pass_never_double_emits_started(store: ConcreteAcquireStore) -> None:
    """MINOR-6: a pass whose mark READ predates another pass's write emits nothing.

    Concurrent shape: pass A claims Started (its write lands); pass B read the
    marks BEFORE that write (stale « no mark »). The unconditional upsert let
    B re-emit; the guarded ``try_mark_started`` answers False and B stays
    silent. The stale read is simulated by patching ``get`` to return None.
    """
    _grabbed(store)
    assert store.download_marks.try_mark_started(_HASH) is True, "pass A claims Started"
    bus = EventBus()
    events = _collector(bus)

    with patch.object(store.download_marks, "get", return_value=None):
        reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.10)}, event_bus=bus)

    assert events == [], "the losing pass must not emit a second DownloadStarted"


def test_stale_read_concurrent_pass_never_double_emits_completed(store: ConcreteAcquireStore) -> None:
    """MINOR-6: same guarded arbitration for Completed — the losing pass is silent."""
    _grabbed(store)
    assert store.download_marks.try_mark_completed(_HASH) is True, "pass A claims Completed"
    bus = EventBus()
    events = _collector(bus)

    with patch.object(store.download_marks, "get", return_value=None):
        reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 1.0)}, event_bus=bus)

    assert events == [], "the losing pass must not emit a second DownloadCompleted"


def test_stale_read_concurrent_pass_never_double_emits_progressed(store: ConcreteAcquireStore) -> None:
    """MINOR-6: a threshold already advanced by a concurrent pass is never re-emitted."""
    _grabbed(store)
    store.download_marks.upsert(_HASH, started=True)
    assert store.download_marks.try_advance_threshold(_HASH, 50) is True, "pass A claims the 50 crossing"
    stale_mark = DownloadMark(info_hash=_HASH, started_emitted=True, last_threshold=0, completed_emitted=False)
    bus = EventBus()
    events = _collector(bus)

    with patch.object(store.download_marks, "get", return_value=stale_mark):
        reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.55)}, event_bus=bus)

    assert events == [], "the losing pass must not emit a second DownloadProgressed(50)"
    mark = store.download_marks.get(_HASH)
    assert mark is not None and mark.last_threshold == 50


def test_blind_pass_still_prunes_mark_of_closed_row(store: ConcreteAcquireStore) -> None:
    """MINOR-5: client_items=None + ownership closes the row → the mark is pruned.

    The emission pass is skipped on a client blind spot, but the prune is not:
    a row the sweep closes ``done`` leaves the open set, so its mark must go
    even when the client was unreachable this pass.
    """
    _grabbed(store)
    store.download_marks.upsert(_HASH, started=True)
    bus = EventBus()
    events = _collector(bus)

    reconcile_wanted(store, _OwnsAllOwnership(), client_items=None, event_bus=bus)

    assert store.download_marks.get(_HASH) is None, "the closed row's mark must be pruned on a blind pass too"
    assert events == [], "a blind pass must not emit download events"


def test_emit_after_persist_mark_survives_a_raising_bus(store: ConcreteAcquireStore) -> None:
    """Emit-after-persist: the mark lands BEFORE the emit, and a raising bus never aborts the sweep."""
    _grabbed(store)
    bus = MagicMock(spec=EventBus)
    bus.emit.side_effect = RuntimeError("subscriber exploded")

    summary = reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.10)}, event_bus=bus)

    assert summary.still_in_flight == 1, "the sweep must complete despite the raising bus"
    bus.emit.assert_called_once()
    mark = store.download_marks.get(_HASH)
    assert mark is not None, "the mark must persist even when the emit raised"
    assert mark.started_emitted is True


def test_emit_after_persist_threshold_survives_a_raising_bus(store: ConcreteAcquireStore) -> None:
    """Emit-after-persist pinned for Progressed (review MAJOR — only Started was pinned).

    Started already emitted, progress 0.30, a raising bus: the 25 threshold
    must be PERSISTED before the (failed) emit — a crash between persist and
    emit loses that emit rather than duplicating it on the next pass.
    """
    _grabbed(store)
    store.download_marks.upsert(_HASH, started=True)
    bus = MagicMock(spec=EventBus)
    bus.emit.side_effect = RuntimeError("subscriber exploded")

    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 0.30)}, event_bus=bus)

    bus.emit.assert_called_once()
    mark = store.download_marks.get(_HASH)
    assert mark is not None, "the mark must persist even when the emit raised"
    assert mark.last_threshold == 25, "the crossed threshold must be persisted BEFORE the emit"


def test_emit_after_persist_completed_survives_a_raising_bus(store: ConcreteAcquireStore) -> None:
    """Emit-after-persist pinned for Completed (review MAJOR — only Started was pinned).

    No mark, progress 1.0, a raising bus: ``completed_emitted`` must be
    PERSISTED before the (failed) emit so the next pass never re-emits.
    """
    _grabbed(store)
    bus = MagicMock(spec=EventBus)
    bus.emit.side_effect = RuntimeError("subscriber exploded")

    reconcile_wanted(store, _NoOwnership(), client_items={_HASH: _item(_HASH, 1.0)}, event_bus=bus)

    bus.emit.assert_called_once()
    mark = store.download_marks.get(_HASH)
    assert mark is not None, "the mark must persist even when the emit raised"
    assert mark.completed_emitted is True, "completion must be persisted BEFORE the emit"

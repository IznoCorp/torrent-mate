"""reswitch Phase 4 — the reswitch_stalled actor.

A dead-stalled grabbed row must switch releases; a healthy one must be left
alone; and a vanished torrent is the reconciliation's business, not ours. The
pass is fail-soft: an unreachable client or a failed delete never crashes it and
never strands a row whose hash was not recorded.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from personalscraper.acquire._reswitch import ReswitchSummary, reswitch_stalled
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import GrabReswitched
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api.torrent._base import TorrentItem
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef

_NOW = 2_000_000_000.0


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _grab_row(store: ConcreteAcquireStore, info_hash: str, tvdb_id: int = 42) -> int:
    """Insert + grab a wanted row with *info_hash*; return its id."""
    rowid = store.wanted.add(
        WantedItem(media_ref=MediaRef(tvdb_id=tvdb_id), kind="episode", status="pending", enqueued_at=1_900_000_000)
    )
    assert store.wanted.claim_for_search(rowid, 1_900_000_100) is True
    store.wanted.mark_grabbed(rowid, info_hash)
    return rowid


def _torrent(
    info_hash: str,
    *,
    state: str = "stalledDL",
    progress: float = 0.0,
    swarm_seeds: int | None = 0,
    error_reason: str | None = None,
    added_on_ts: float = _NOW - 60,
) -> TorrentItem:
    """A TorrentItem as the client would report it."""
    return TorrentItem(
        hash=info_hash,
        name="Show.S03E09.mkv",
        size_bytes=1,
        progress=progress,
        state=state,
        swarm_seeds=swarm_seeds,
        error_reason=error_reason,
        added_on=datetime.fromtimestamp(added_on_ts),
    )


class _FakeClient:
    """Minimal torrent client: canned get_by_hashes + a delete recorder."""

    def __init__(self, items: list[TorrentItem], *, delete_raises: bool = False) -> None:
        self._items = items
        self.deleted: list[str] = []
        self._delete_raises = delete_raises

    def get_by_hashes(self, hashes: set[str]) -> list[TorrentItem]:
        return [t for t in self._items if t.hash.lower() in hashes]

    def delete(self, hash: str, *, delete_files: bool = False) -> None:  # noqa: A002
        if self._delete_raises:
            raise RuntimeError("qbit hiccup")
        self.deleted.append(hash)


def _bus_capturing() -> tuple[EventBus, list[GrabReswitched]]:
    """An EventBus plus the list it appends every GrabReswitched to."""
    bus = EventBus()
    seen: list[GrabReswitched] = []
    bus.subscribe(GrabReswitched, seen.append)
    return bus, seen


def test_dead_swarm_reswitches_records_deletes_and_emits(store: ConcreteAcquireStore) -> None:
    """A dead-swarm grab ⇒ requeue + hash remembered + torrent deleted + event."""
    rowid = _grab_row(store, "deadbeef")
    client = _FakeClient([_torrent("deadbeef", swarm_seeds=0)])
    bus, seen = _bus_capturing()

    summary = reswitch_stalled(store, client, _NOW, event_bus=bus)

    assert summary == ReswitchSummary(checked=1, reswitched=1)
    row = store.wanted.get(rowid)
    assert row is not None and row.status == "pending" and row.grabbed_hash is None
    assert row.tried_hashes == ("deadbeef",)
    assert client.deleted == ["deadbeef"]
    assert len(seen) == 1 and seen[0].old_hash == "deadbeef" and seen[0].reason == "dead_swarm"


def test_healthy_download_is_left_untouched(store: ConcreteAcquireStore) -> None:
    """A progressing torrent is never switched (no requeue, no delete, no event)."""
    rowid = _grab_row(store, "cafef00d")
    client = _FakeClient([_torrent("cafef00d", state="downloading", progress=0.3)])
    bus, seen = _bus_capturing()

    summary = reswitch_stalled(store, client, _NOW, event_bus=bus)

    assert summary == ReswitchSummary(checked=1, reswitched=0)
    row = store.wanted.get(rowid)
    assert row is not None and row.status == "grabbed"
    assert client.deleted == []
    assert seen == []


def test_vanished_torrent_is_left_to_reconciliation(store: ConcreteAcquireStore) -> None:
    """A grabbed hash the client no longer reports is NOT a stall — skip it."""
    _grab_row(store, "deadbeef")
    client = _FakeClient([])  # client knows nothing about the hash
    bus, seen = _bus_capturing()

    summary = reswitch_stalled(store, client, _NOW, event_bus=bus)

    assert summary == ReswitchSummary(checked=0, reswitched=0)
    assert seen == []


def test_client_unavailable_is_a_fail_soft_no_op(store: ConcreteAcquireStore) -> None:
    """get_by_hashes raising ⇒ no crash, nothing changes."""
    rowid = _grab_row(store, "deadbeef")

    class _Boom:
        def get_by_hashes(self, hashes: set[str]) -> list[TorrentItem]:
            raise RuntimeError("unreachable")

        def delete(self, hash: str, *, delete_files: bool = False) -> None:  # noqa: A002
            raise AssertionError("must not be reached")

    bus, seen = _bus_capturing()
    summary = reswitch_stalled(store, _Boom(), _NOW, event_bus=bus)

    assert summary == ReswitchSummary(checked=0, reswitched=0)
    assert store.wanted.get(rowid).status == "grabbed"  # type: ignore[union-attr]
    assert seen == []


def test_delete_failure_still_requeues_and_emits(store: ConcreteAcquireStore) -> None:
    """A delete that raises must not undo the requeue (recorded first) nor the event."""
    rowid = _grab_row(store, "deadbeef")
    client = _FakeClient([_torrent("deadbeef", swarm_seeds=0)], delete_raises=True)
    bus, seen = _bus_capturing()

    summary = reswitch_stalled(store, client, _NOW, event_bus=bus)

    assert summary == ReswitchSummary(checked=1, reswitched=1)
    row = store.wanted.get(rowid)
    assert row is not None and row.status == "pending"
    assert row.tried_hashes == ("deadbeef",)
    assert len(seen) == 1


def test_broken_torrent_reason_is_broken(store: ConcreteAcquireStore) -> None:
    """An errored torrent switches with reason 'broken'."""
    _grab_row(store, "deadbeef")
    client = _FakeClient([_torrent("deadbeef", state="error", error_reason="boom", swarm_seeds=5)])
    bus, seen = _bus_capturing()

    reswitch_stalled(store, client, _NOW, event_bus=bus)

    assert len(seen) == 1 and seen[0].reason == "broken"

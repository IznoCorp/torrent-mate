"""M9 — the intent hash closes the ``add()`` → ``mark_grabbed`` window (D2).

Before this, the chosen hash was persisted only AFTER the torrent client's
``add()`` returned. A crash in between left an ORPHAN torrent downloading in
qBittorrent with nothing pointing at it: no hash on the ``wanted`` row, no seed
obligation protecting it from the deletion authority, and a row that recovered
to 'pending' and was re-SEARCHED from scratch (a fresh decision, possibly a
different release — or a second torrent for the same episode).

The fix is a two-phase claim: the hash is written BEFORE the add (row still
'searching' — an *intention*), and ``mark_grabbed`` becomes the confirmation.
Recovery is then a replay, not a new search:

- torrent present in the client  ⇒ confirm 'grabbed' + record the seed obligation;
- torrent absent                 ⇒ clear the hash, the row is searchable again.

These tests pin the whole path, including the routing trap called out in the
plan: ``reclaim_stale_searching`` refuses a hash-carrying row (it would re-grab
an already-added torrent), so BOTH passes must leave it to the reconciling
recovery rather than skipping it forever.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.acquire.delete_authority import DeleteAuthority
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.reconcile import reconcile_wanted
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.conf.models.api_config import TrackerEconomyConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef

_HASH = "abcd" * 10
_TRACKER = "c411"
_ECONOMY = {_TRACKER: TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time=259_200)}

# Subscriber-less sink: reconcile REQUIRES a bus (event_bus contract); these
# tests pin the intent-hash recovery, not the download events.
_BUS = EventBus()


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _searching_row(store: ConcreteAcquireStore, *, tvdb_id: int = 42) -> int:
    """Insert a wanted row and claim it, leaving it 'searching' with no hash."""
    rowid = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=tvdb_id),
            kind="movie",
            status="pending",
            enqueued_at=1_700_000_000,
        )
    )
    assert store.wanted.claim_for_search(rowid, 1_700_000_100) is True
    return rowid


def _torrent(hash_: str, *, tags: list[str]) -> MagicMock:
    """A torrent item with the REAL client surface (hash / name / size_bytes / tags)."""
    item = MagicMock()
    item.hash = hash_
    item.name = "Some.Release.mkv"
    item.size_bytes = 1024
    item.tags = tags
    # Deterministic mid-download progress: the reconcile sweep now reads it for
    # the download-event emission (a bare MagicMock compares truthy vs 1.0).
    item.progress = 0.5
    return item


class TestIntentWrite:
    """``record_grab_intent`` — the pre-add write, guarded like every claim."""

    def test_writes_the_hash_while_the_row_stays_searching(self, store: ConcreteAcquireStore) -> None:
        """The intent lands on the row WITHOUT promoting it to 'grabbed'."""
        rowid = _searching_row(store)

        assert store.wanted.record_grab_intent(rowid, _HASH) is True

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "searching", "the intent must not confirm the grab"
        assert (row.grabbed_hash or "").lower() == _HASH

    def test_is_a_no_op_on_a_row_that_is_not_searching(self, store: ConcreteAcquireStore) -> None:
        """Only a claimed row may take an intent (mirrors the claim guards)."""
        rowid = _searching_row(store)
        store.wanted.set_status(rowid, "pending")

        assert store.wanted.record_grab_intent(rowid, _HASH) is False

        row = store.wanted.get(rowid)
        assert row is not None and row.grabbed_hash is None

    def test_does_not_overwrite_an_existing_intent(self, store: ConcreteAcquireStore) -> None:
        """A second intent never clobbers the first — the first add owns the row."""
        rowid = _searching_row(store)
        assert store.wanted.record_grab_intent(rowid, _HASH) is True

        assert store.wanted.record_grab_intent(rowid, "ffff" * 10) is False

        row = store.wanted.get(rowid)
        assert row is not None and (row.grabbed_hash or "").lower() == _HASH


class TestIntentConfirmation:
    """``confirm_grab_intent`` — the recovery's status transition."""

    def test_confirms_a_searching_row_carrying_its_intent(self, store: ConcreteAcquireStore) -> None:
        """Searching + hash ⇒ grabbed, hash preserved."""
        rowid = _searching_row(store)
        store.wanted.record_grab_intent(rowid, _HASH)

        assert store.wanted.confirm_grab_intent(rowid, _HASH) is True

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "grabbed"
        assert (row.grabbed_hash or "").lower() == _HASH

    def test_is_a_no_op_without_an_intent(self, store: ConcreteAcquireStore) -> None:
        """A hash-less 'searching' row belongs to the stale sweep, not to this path."""
        rowid = _searching_row(store)

        assert store.wanted.confirm_grab_intent(rowid, _HASH) is False

        row = store.wanted.get(rowid)
        assert row is not None and row.status == "searching"

    def test_second_call_is_idempotent(self, store: ConcreteAcquireStore) -> None:
        """Once confirmed the row is 'grabbed', so a replay reports False (no re-fire)."""
        rowid = _searching_row(store)
        store.wanted.record_grab_intent(rowid, _HASH)
        assert store.wanted.confirm_grab_intent(rowid, _HASH) is True

        assert store.wanted.confirm_grab_intent(rowid, _HASH) is False


class TestInFlightHashes:
    """``hashes_in_flight`` — the probe set the client is asked about."""

    def test_includes_a_searching_intent_not_only_grabbed_rows(self, store: ConcreteAcquireStore) -> None:
        """The intent hash MUST be probed, else reconcile calls a live torrent 'vanished'."""
        searching = _searching_row(store, tvdb_id=1)
        store.wanted.record_grab_intent(searching, _HASH)
        grabbed = _searching_row(store, tvdb_id=2)
        store.wanted.mark_grabbed(grabbed, "beef" * 10)

        assert store.wanted.hashes_in_flight() == {_HASH, "beef" * 10}

    def test_ignores_rows_without_a_hash(self, store: ConcreteAcquireStore) -> None:
        """Rows carrying no hash contribute nothing to the probe set."""
        _searching_row(store, tvdb_id=3)

        assert store.wanted.hashes_in_flight() == set()


class TestCrashWindowRecovery:
    """The ACC-02 scenario: crash between ``add()`` and ``mark_grabbed``."""

    def test_present_torrent_is_confirmed_and_gets_its_obligation(self, store: ConcreteAcquireStore) -> None:
        """Next run: row confirmed 'grabbed' + seed obligation recorded — zero orphan."""
        rowid = _searching_row(store)
        # --- the crash window, reproduced exactly ---
        store.wanted.record_grab_intent(rowid, _HASH)  # pre-add write
        # add() happened (the torrent is in the client, tagged with its tracker)
        client = MagicMock()
        client.get_by_hashes.return_value = [_torrent(_HASH, tags=[_TRACKER])]
        # ... and the process died BEFORE mark_grabbed.

        authority = DeleteAuthority(store=store, torrent_client=client, economy=_ECONOMY)
        items = {_HASH: _torrent(_HASH, tags=[_TRACKER])}
        rec = authority.record_grab_obligation
        owner = _ownership(owns=False)
        summary = reconcile_wanted(store, owner, client_items=items, event_bus=_BUS, record_obligation=rec)

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "grabbed", "a torrent present in the client must confirm the row"
        assert (row.grabbed_hash or "").lower() == _HASH
        assert summary.confirmed_grabbed == 1
        obligation = store.seed.find_active_by_hash(_HASH)
        assert obligation is not None, "the recovered grab must carry its seed obligation"
        assert obligation.source_tracker == _TRACKER
        assert obligation.min_seed_time_s == 259_200

    def test_absent_torrent_clears_the_intent_and_reopens_the_row(self, store: ConcreteAcquireStore) -> None:
        """The add never landed: the hash is cleared and the row is searchable again."""
        rowid = _searching_row(store)
        store.wanted.record_grab_intent(rowid, _HASH)

        summary = reconcile_wanted(store, _ownership(owns=False), client_items={}, event_bus=_BUS)

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "pending"
        assert row.grabbed_hash is None
        assert summary.requeued_missing == 1

    def test_confirmation_is_idempotent_across_two_sweeps(self, store: ConcreteAcquireStore) -> None:
        """A second sweep neither re-confirms nor writes a second obligation."""
        rowid = _searching_row(store)
        store.wanted.record_grab_intent(rowid, _HASH)
        client = MagicMock()
        client.get_by_hashes.return_value = [_torrent(_HASH, tags=[_TRACKER])]
        authority = DeleteAuthority(store=store, torrent_client=client, economy=_ECONOMY)

        items = {_HASH: _torrent(_HASH, tags=[_TRACKER])}
        rec = authority.record_grab_obligation
        owner = _ownership(owns=False)
        first = reconcile_wanted(store, owner, client_items=items, event_bus=_BUS, record_obligation=rec)
        second = reconcile_wanted(store, owner, client_items=items, event_bus=_BUS, record_obligation=rec)

        assert (first.confirmed_grabbed, second.confirmed_grabbed) == (1, 0)
        assert store.wanted.get(rowid).status == "grabbed"  # type: ignore[union-attr]

    def test_unknown_client_state_touches_nothing(self, store: ConcreteAcquireStore) -> None:
        """``client_hashes=None`` (client unavailable) leaves the intent row alone."""
        rowid = _searching_row(store)
        store.wanted.record_grab_intent(rowid, _HASH)

        summary = reconcile_wanted(store, _ownership(owns=False), client_items=None, event_bus=_BUS)

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "searching"
        assert (row.grabbed_hash or "").lower() == _HASH
        assert (summary.confirmed_grabbed, summary.requeued_missing) == (0, 1 - 1)


class TestRoutingOfAHashCarryingSearchingRow:
    """The trap: neither pass may swallow the row, and reconcile must see it."""

    def test_neither_pass_reclaims_it(self, store: ConcreteAcquireStore) -> None:
        """``reclaim_stale_searching`` refuses it — that is what routes it to reconcile."""
        rowid = _searching_row(store)
        store.wanted.record_grab_intent(rowid, _HASH)

        assert store.wanted.reclaim_stale_searching(rowid, 1_800_000_000) is False

        row = store.wanted.get(rowid)
        assert row is not None and row.status == "searching"

    def test_reconcile_sees_it_via_list_searching(self, store: ConcreteAcquireStore) -> None:
        """The row is in the reconciliation input — not invisible to every sweep."""
        rowid = _searching_row(store)
        store.wanted.record_grab_intent(rowid, _HASH)

        assert [r.id for r in store.wanted.list_searching()] == [rowid]


def _ownership(*, owns: bool) -> MagicMock:
    """An OwnershipChecker stub."""
    checker = MagicMock()
    checker.owns.return_value = owns
    return checker


class TestObligationRecorder:
    """``DeleteAuthority.record_grab_obligation`` — tracker resolved from the client tags."""

    def test_writes_the_obligation_from_the_torrent_tag(self, store: ConcreteAcquireStore) -> None:
        """The torrent's tracker tag + the economy map give the floors."""
        client = MagicMock()
        client.get_by_hashes.return_value = [_torrent(_HASH, tags=[_TRACKER])]
        authority = DeleteAuthority(store=store, torrent_client=client, economy=_ECONOMY)

        assert authority.record_grab_obligation(_HASH) is True

        obligation = store.seed.find_active_by_hash(_HASH)
        assert obligation is not None
        assert obligation.source_tracker == _TRACKER
        assert obligation.added_at <= int(time.time())

    def test_unresolvable_tracker_is_an_honest_miss(self, store: ConcreteAcquireStore) -> None:
        """No tag maps to a configured economy ⇒ no invented obligation."""
        client = MagicMock()
        client.get_by_hashes.return_value = [_torrent(_HASH, tags=["manual"])]
        authority = DeleteAuthority(store=store, torrent_client=client, economy=_ECONOMY)

        assert authority.record_grab_obligation(_HASH) is False
        assert store.seed.find_active_by_hash(_HASH) is None

    def test_existing_obligation_is_not_duplicated(self, store: ConcreteAcquireStore) -> None:
        """A second call never writes a second obligation for the same hash."""
        client = MagicMock()
        client.get_by_hashes.return_value = [_torrent(_HASH, tags=[_TRACKER])]
        authority = DeleteAuthority(store=store, torrent_client=client, economy=_ECONOMY)
        assert authority.record_grab_obligation(_HASH) is True

        assert authority.record_grab_obligation(_HASH) is False

    def test_client_error_is_fail_soft(self, store: ConcreteAcquireStore) -> None:
        """A client blowing up must not break the recovery sweep."""
        client = MagicMock()
        client.get_by_hashes.side_effect = RuntimeError("client down")
        authority = DeleteAuthority(store=store, torrent_client=client, economy=_ECONOMY)

        assert authority.record_grab_obligation(_HASH) is False

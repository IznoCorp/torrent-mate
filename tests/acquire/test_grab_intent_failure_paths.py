"""The intent hash must be RELEASED when the grab does not reach the client (D2).

``record_grab_intent`` reserves the chosen hash on the still-'searching' row
BEFORE ``add()``, so a crash in the add→confirm window leaves a replayable
intent instead of an orphan torrent. That is only half a contract: an ``add()``
that returns a FAILURE never handed anything to the client, so the reservation
it made must be released on the way out.

Left in place, the stale hash makes the row unreachable to everything:

- ``reclaim_stale_searching`` refuses a hash-carrying row (it would re-grab an
  already-added torrent), so the pre-claim gate returns ``"skipped"`` — and it
  returns it BEFORE the cutoff check, so the 30-day age-out never fires either;
- :meth:`_process_item`'s hash guard short-circuits any re-claim;
- the search pass only walks 'pending' rows.

The single remaining owner of that cell is ``reconcile_wanted``, and only when
the torrent client answers — precisely the thing that is unavailable when an
``add()`` fails because the client is down. The row then never moves again, is
never abandoned, and is counted only as an anonymous ``skipped``.

These tests pin the release on every non-success disposition, the guard that
keeps it from ever disarming a CONFIRMED grab, and the two properties the
regression cost us: the next pass retries, and the cutoff can still age the row
out.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import GrabOutcome
from personalscraper.acquire.reconcile import reconcile_wanted
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef

_HASH = "beef" * 10
_CUTOFF_DAYS = 30


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    s = build_acquire_store(AcquireConfig(db_path=tmp_path / "acquire.db"))
    try:
        yield s
    finally:
        s.close()


def _config() -> MagicMock:
    """Config whose ``acquire`` section carries the canonical Hot/Warm/Cold/30d cadence."""
    config = MagicMock()
    config.acquire = AcquireConfig()
    return config


def _available_row(store: ConcreteAcquireStore, *, enqueued_at: int | None = None) -> int:
    """Insert a row the SEARCH pass already concluded takeable ('available')."""
    rowid = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=42),
            kind="movie",
            status="pending",
            enqueued_at=enqueued_at if enqueued_at is not None else int(time.time()),
        )
    )
    store.wanted.record_search_outcome(rowid, "available", 3)
    store.wanted.set_status(rowid, "available")
    return rowid


def _service(store: ConcreteAcquireStore, orchestrator: MagicMock) -> AcquisitionService:
    """Build the service over a real store and a scripted orchestrator."""
    return AcquisitionService(
        store=store,
        orchestrator=orchestrator,
        event_bus=MagicMock(),
        config=_config(),
    )


def _orchestrator_writing_intent_then(outcome: GrabOutcome) -> MagicMock:
    """Orchestrator that reserves the intent hash then returns *outcome*.

    Reproduces the real sequence: ``resolve_source`` succeeded, the hook wrote
    the hash onto the claimed row, and only then did ``add()`` (or a later
    stage) fail.
    """
    orchestrator = MagicMock()

    def _grab(
        item: object,
        profile: object,
        *,
        on_intent: object = None,
        exclude_hashes: object = frozenset(),
    ) -> GrabOutcome:
        if on_intent is not None:
            on_intent(_HASH)  # type: ignore[operator]
        return outcome

    orchestrator.grab.side_effect = _grab
    return orchestrator


class TestClearGrabIntentStore:
    """``_WantedSubStore.clear_grab_intent`` — the release half of the claim."""

    def test_clears_the_hash_of_a_searching_row(self, store: ConcreteAcquireStore) -> None:
        """A claimed row carrying an intent is released back to hash-less 'searching'."""
        rowid = _available_row(store)
        assert store.wanted.claim_for_grab(rowid, int(time.time())) is True
        assert store.wanted.record_grab_intent(rowid, _HASH) is True

        assert store.wanted.clear_grab_intent(rowid) is True

        row = store.wanted.get(rowid)
        assert row is not None
        assert (row.status, row.grabbed_hash) == ("searching", None)

    def test_refuses_a_grabbed_row(self, store: ConcreteAcquireStore) -> None:
        """A CONFIRMED grab is never disarmed — that would orphan a live torrent."""
        rowid = _available_row(store)
        assert store.wanted.claim_for_grab(rowid, int(time.time())) is True
        store.wanted.mark_grabbed(rowid, _HASH)

        assert store.wanted.clear_grab_intent(rowid) is False

        row = store.wanted.get(rowid)
        assert row is not None
        assert (row.status, row.grabbed_hash) == ("grabbed", _HASH)

    def test_is_idempotent(self, store: ConcreteAcquireStore) -> None:
        """A second release is a no-op ``False`` — nothing to give back."""
        rowid = _available_row(store)
        assert store.wanted.claim_for_grab(rowid, int(time.time())) is True
        assert store.wanted.record_grab_intent(rowid, _HASH) is True

        assert store.wanted.clear_grab_intent(rowid) is True
        assert store.wanted.clear_grab_intent(rowid) is False


class TestFailedGrabReleasesTheIntent:
    """Every non-success disposition gives the reserved hash back."""

    @pytest.mark.parametrize(
        ("outcome", "expected_status"),
        [
            (GrabOutcome(disposition="retryable", reason="add_failed"), "available"),
            (GrabOutcome(disposition="not_found", reason="no_candidates", found=0), "pending"),
            (GrabOutcome(disposition="terminal", reason="tracker_auth"), "abandoned"),
        ],
        ids=["retryable", "not_found", "terminal"],
    )
    def test_intent_is_released(
        self,
        store: ConcreteAcquireStore,
        outcome: GrabOutcome,
        expected_status: str,
    ) -> None:
        """The row keeps its mapped status and carries NO hash — nothing was added."""
        rowid = _available_row(store)
        service = _service(store, _orchestrator_writing_intent_then(outcome))

        service.run()

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.grabbed_hash is None, "a failed grab must not keep the hash it reserved"
        assert row.status == expected_status

    def test_success_keeps_the_hash(self, store: ConcreteAcquireStore) -> None:
        """The release must not fire on the path that DID hand a torrent to the client."""
        rowid = _available_row(store)
        chosen = MagicMock()
        chosen.provider = "c411"
        outcome = GrabOutcome(disposition="success", info_hash=_HASH, chosen=chosen, found=1)
        service = _service(store, _orchestrator_writing_intent_then(outcome))

        service.run()

        row = store.wanted.get(rowid)
        assert row is not None
        assert (row.status, row.grabbed_hash) == ("grabbed", _HASH)


class TestTheRowStaysReachableAfterAFailedAdd:
    """The two properties the stranded hash cost us."""

    def test_the_next_pass_retries_the_grab(self, store: ConcreteAcquireStore) -> None:
        """Pass N+1 reaches the orchestrator again instead of short-circuiting."""
        _available_row(store)
        orchestrator = _orchestrator_writing_intent_then(GrabOutcome(disposition="retryable", reason="add_failed"))
        service = _service(store, orchestrator)

        service.run()
        calls_after_first_pass = orchestrator.grab.call_count
        service.run()

        assert calls_after_first_pass == 1
        assert orchestrator.grab.call_count == 2, "a transient add failure must stay retryable"

    def test_the_cutoff_still_ages_the_row_out(self, store: ConcreteAcquireStore) -> None:
        """A row whose add keeps failing is abandoned past the cutoff, not frozen.

        Follows the real sequence into the absorbing state: the failed add left
        the hash on an 'available' row, and the NEXT pass claimed it (→
        'searching') then short-circuited on the hash guard. From there the
        pre-claim gate returned ``"skipped"`` — ``reclaim_stale_searching``
        refuses a hash-carrying row — and it returned it BEFORE the cutoff
        check, so the 30-day age-out could never fire. The row outlived its
        cutoff indefinitely, counted only as an anonymous ``skipped``.
        """
        rowid = _available_row(store)
        service = _service(
            store,
            _orchestrator_writing_intent_then(GrabOutcome(disposition="retryable", reason="add_failed")),
        )

        service.run()  # the add fails — pre-fix this leaves the hash behind
        service.run()  # pre-fix: claim → hash guard → 'searching' + hash

        # Age the row well past its cutoff, and make its claim look stale.
        old = int(time.time()) - (_CUTOFF_DAYS + 30) * 86_400
        store._conn.execute(
            "UPDATE wanted SET enqueued_at = ?, last_search_at = ? WHERE id = ?",
            (old, old, rowid),
        )
        store._conn.commit()

        service.run()

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "abandoned", "the cutoff must remain reachable"

    def test_no_zombie_when_the_torrent_client_is_unreachable(self, store: ConcreteAcquireStore) -> None:
        """The recovery must not depend on the client that just failed the add.

        ``reconcile_wanted`` skips both hash branches when ``client_hashes`` is
        ``None`` (fail-soft on a blind spot), so a row that could ONLY be
        rescued there was stranded for exactly as long as the client stayed
        down — the very outage that caused the failed add.
        """
        rowid = _available_row(store)
        orchestrator = _orchestrator_writing_intent_then(GrabOutcome(disposition="retryable", reason="add_failed"))
        service = _service(store, orchestrator)
        ownership = MagicMock()
        ownership.owns.return_value = False

        service.run()
        calls_before = orchestrator.grab.call_count
        # The client is unreachable: reconciliation can decide nothing.
        reconcile_wanted(store, ownership, client_items=None, event_bus=EventBus())
        service.run()

        row = store.wanted.get(rowid)
        assert row is not None
        assert row.status == "available", "the row must stay in the grab queue"
        assert orchestrator.grab.call_count > calls_before, "the row must still be processed"

"""Test-first: grab walks only available items and reverts on disappearance.

These tests INTENTIONALLY FAIL today — the reworked ``run()`` and
``claim_for_grab`` do not exist yet (sub-phase 2.5).  The current ``run()``
walks ``list_pending()`` + ``list_stale_searching()``, so every item with
``status='available'`` is invisible to it.  Do NOT mark xfail/skip.

Design: contract_phase2.md § « grab pass rework (run()) » + § ARBITRATION
(post-2.3).  The plan is phase-02-search-grab-split.md §2.4.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import WantedAbandoned
from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome
from personalscraper.acquire.service import AcquisitionService
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef

# ---------------------------------------------------------------------------
# Reuse the house patterns from test_service.py + test_search_pass.py.
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


def _available_item(store: ConcreteAcquireStore, tvdb_id: int, *, found: int = 5, outcome: str = "available") -> int:
    """Insert a WantedItem, transition it through claim→search→available, return its rowid.

    Mirrors what ``run_search`` does for a takeable item: the row carries
    ``status='available'`` + ``last_search_outcome`` + ``last_search_found``
    exactly as the grab pass expects.
    """
    rowid = store.wanted.add(_pending_item(tvdb_id=tvdb_id))
    store.wanted.claim_for_search(rowid, _PINNED_NOW)
    store.wanted.record_search_outcome(rowid, outcome, found)
    store.wanted.set_status(rowid, "available")
    return rowid


def _service(
    store: ConcreteAcquireStore,
    orchestrator: GrabOrchestrator,
    event_bus: MagicMock | None = None,
) -> AcquisitionService:
    """Build a service with a (mock) event_bus — mirrors test_service._service."""
    config = MagicMock()
    config.acquire = AcquireConfig()
    return AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=event_bus if event_bus is not None else MagicMock(),
        config=config,
    )


# ---------------------------------------------------------------------------
# THE tests — intentionally failing until 2.5 implements the contract.
# ---------------------------------------------------------------------------


def test_grab_only_walks_available_items(store: ConcreteAcquireStore) -> None:
    """Grab must not re-search the whole pending backlog.

    Bounding grab to list_available() is what makes the operator's « always
    re-search » choice cheap: a handful of known-available items, never the
    full queue (NE-DOIT-PAS-8).
    """
    # Seed: 2 pending + 3 available.
    pid1 = store.wanted.add(_pending_item(tvdb_id=1))
    pid2 = store.wanted.add(_pending_item(tvdb_id=2))
    aid1 = _available_item(store, tvdb_id=10, found=3)
    aid2 = _available_item(store, tvdb_id=20, found=4)
    aid3 = _available_item(store, tvdb_id=30, found=2)

    grabbed_ids: list[int] = []

    def _grab(
        item: WantedItem,
        profile: object,
        *,
        on_intent: "Callable[[str], None] | None" = None,
        exclude_hashes: object = frozenset(),
    ) -> GrabOutcome:
        assert item.id is not None  # noqa: S101
        grabbed_ids.append(item.id)
        return GrabOutcome(disposition="success", info_hash="h", found=3)

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.side_effect = _grab

    service = _service(store, orch)
    summary = service.run()

    # CONTRACT: grab() was invoked ONLY for the available items.
    assert sorted(grabbed_ids) == sorted([aid1, aid2, aid3]), (
        f"grab must only walk list_available(); got calls for {grabbed_ids}, "
        f"expected only available ids {[aid1, aid2, aid3]}"
    )
    assert summary.grabbed == 3

    # Pending items must be UNTOUCHED (still 'pending', attempts unchanged).
    for pid in (pid1, pid2):
        item = store.wanted.get(pid)
        assert item is not None
        assert item.status == "pending", f"pending item {pid} must stay pending; got {item.status}"
        assert item.attempts == 0, f"pending item {pid} attempts must be unchanged; got {item.attempts}"


def test_grab_reverts_to_pending_when_the_torrent_vanished(store: ConcreteAcquireStore) -> None:
    """A candidate that disappeared between the two passes must not be faked."""
    rowid = _available_item(store, tvdb_id=99, found=5)

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="not_found", reason="no_candidates", found=0)

    service = _service(store, orch)
    service.run()

    # CONTRACT: after run(), the vanished item goes back to 'pending' with the
    # not_found verdict recorded.  NEVER an add, never left as 'available'.
    assert orch.grab.call_count == 1, f"grab() must be called for the available item; got {orch.grab.call_count} calls"
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "pending", f"vanished item must revert to 'pending'; got {item.status!r}"
    assert item.last_search_outcome == "no_candidates", (
        f"verdict must record the not_found reason; got {item.last_search_outcome!r}"
    )
    assert item.last_search_found == 0, f"found must be 0 for a concluded search; got {item.last_search_found!r}"
    # The item was NEVER marked grabbed.
    assert item.grabbed_hash is None, "vanished item must never carry a grabbed_hash"


def test_grab_retryable_keeps_available_and_verdict(store: ConcreteAcquireStore) -> None:
    """A retryable outcome at grab time keeps the item available with its verdict.

    Grab retryable → set_status('available'), verdict columns UNTOUCHED
    (still 'available' + found from the search pass).  The search-pass
    verdict stands because the grab's own search did not conclude.
    """
    rowid = _available_item(store, tvdb_id=99, found=5, outcome="available")

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="retryable", reason="circuit_open", found=None)

    service = _service(store, orch)
    service.run()

    assert orch.grab.call_count == 1, f"grab() must be called for the available item; got {orch.grab.call_count} calls"
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "available", f"retryable grab must keep status='available'; got {item.status!r}"
    # Verdict columns UNTOUCHED — the search-pass verdict stands.
    assert item.last_search_outcome == "available", (
        f"verdict must stay 'available' from the search pass; got {item.last_search_outcome!r}"
    )
    assert item.last_search_found == 5, f"found must stay 5 from the search pass; got {item.last_search_found!r}"


def test_grab_success_records_grabbed_verdict(store: ConcreteAcquireStore) -> None:
    """A successful grab persists the 'grabbed' verdict with the takeable count."""
    rowid = _available_item(store, tvdb_id=99, found=5)

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="success", info_hash="abc123", found=3)

    service = _service(store, orch)
    service.run()

    assert orch.grab.call_count == 1, f"grab() must be called for the available item; got {orch.grab.call_count} calls"
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "grabbed", f"successful grab → status='grabbed'; got {item.status!r}"
    assert item.grabbed_hash == "abc123", f"grabbed_hash must persist; got {item.grabbed_hash!r}"
    # The grab pass records its own verdict (the re-search count).
    assert item.last_search_outcome == "grabbed", (
        f"grab pass verdict must be 'grabbed'; got {item.last_search_outcome!r}"
    )
    assert item.last_search_found == 3, f"grab pass found must be 3 (len(ranked)); got {item.last_search_found!r}"


def test_grab_failure_reason_is_persisted_on_the_row(store: ConcreteAcquireStore) -> None:
    """A non-success grab leaves its reason ON the row (§8: rien en silence).

    Regression (Ninja Turtles 2026-08-08): four identical fetch failures and
    the card had ZERO on-screen trace — the reason only ever reached Telegram.
    """
    rowid = _available_item(store, tvdb_id=99, found=5, outcome="available")

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="retryable", reason="fetch_failed", found=None)

    _service(store, orch).run()

    row = store.wanted._conn.execute(  # noqa: SLF001 — persistence pin on the real column
        "SELECT last_grab_reason, last_grab_at FROM wanted WHERE id = ?", (rowid,)
    ).fetchone()
    assert row is not None
    assert row[0] == "fetch_failed"
    assert isinstance(row[1], int) and row[1] > 0


def test_grab_success_clears_the_failure_reason(store: ConcreteAcquireStore) -> None:
    """A successful grab CLEARS the recorded failure.

    The column always describes the LATEST attempt, never a stale one.
    """
    rowid = _available_item(store, tvdb_id=99, found=5)
    store.wanted.record_grab_failure(rowid, "fetch_failed", 1_700_000_000)

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="success", info_hash="abc123", found=3)

    _service(store, orch).run()

    row = store.wanted._conn.execute(  # noqa: SLF001 — persistence pin on the real column
        "SELECT last_grab_reason, last_grab_at FROM wanted WHERE id = ?", (rowid,)
    ).fetchone()
    assert row is not None
    assert row[0] is None and row[1] is None


def test_grab_has_no_cadence_gate(store: ConcreteAcquireStore) -> None:
    """An available item whose cadence would say « not due » is STILL grabbed.

    Cadence belongs to the SEARCH pass — it spaces re-verification of
    unavailable episodes.  An available item is already known takeable, so
    the grab pass takes it at the next tick regardless of its cadence tier.
    """
    rowid = store.wanted.add(_pending_item(tvdb_id=99))
    # Control both the search making it available AND the last_search_at:
    # last_search_at = 60s ago → just searched, cadence says « not due yet ».
    recent = _PINNED_NOW - 60
    store.wanted.claim_for_search(rowid, recent)
    store.wanted.record_search_outcome(rowid, "available", 5)
    store.wanted.set_status(rowid, "available")

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="success", info_hash="h", found=5)

    service = _service(store, orch)
    service.run()

    # CONTRACT: the grab pass has NO cadence gate — the item IS grabbed.
    assert orch.grab.call_count == 1, f"grab pass must ignore cadence; expected 1 call, got {orch.grab.call_count}"
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "grabbed", f"item must be grabbed despite recent cadence; got {item.status!r}"


def test_grab_applies_cutoff_aging(store: ConcreteAcquireStore) -> None:
    """An available item past the 30-day cutoff → abandoned, never grabbed.

    Aging at grab time bounds infinite retries on a permanently-failing add.
    Before claiming, run() applies the same cutoff check as run_search —
    past-cutoff → guarded abandon + WantedAbandoned(reason='cutoff_reached').
    """
    # An item with an ancient enqueued_at (700M s ago, ~22 years) — well past
    # the 30-day (2.6M s) cutoff.  Status is 'available' from a recent search.
    rowid = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=99),
            kind="movie",
            status="pending",
            enqueued_at=1_000_000_000,  # ancient — past any cutoff
        )
    )
    store.wanted.claim_for_search(rowid, _PINNED_NOW)
    store.wanted.record_search_outcome(rowid, "available", 5)
    store.wanted.set_status(rowid, "available")

    bus = MagicMock()
    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="success", info_hash="h", found=3)

    service = _service(store, orch, event_bus=bus)
    service.run()

    # CONTRACT: the aging item is abandoned BEFORE the orchestrator is called.
    assert orch.grab.call_count == 0, f"cutoff-aged item must never reach grab(); got {orch.grab.call_count} calls"
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "abandoned", f"cutoff-aged item must be 'abandoned'; got {item.status!r}"

    # WantedAbandoned with reason='cutoff_reached' must have been emitted.
    emitted = [c.args[0] for c in bus.emit.call_args_list]
    assert any(isinstance(e, WantedAbandoned) and e.reason == "cutoff_reached" for e in emitted), (
        f"expected WantedAbandoned('cutoff_reached'); got {emitted}"
    )


def test_grab_pass_never_walks_pending_even_when_available_is_empty(
    store: ConcreteAcquireStore,
) -> None:
    """Store with only pending items → run() performs ZERO orchestrator calls.

    The grab pass consumes only known-available items.  An empty available
    queue means nothing to do — it must not reach into the pending backlog.
    """
    store.wanted.add(_pending_item(tvdb_id=1))
    store.wanted.add(_pending_item(tvdb_id=2))
    store.wanted.add(_pending_item(tvdb_id=3))

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="success", info_hash="h", found=3)

    service = _service(store, orch)
    summary = service.run()

    # CONTRACT: ZERO orchestrator calls, ZERO summary counts.
    assert orch.grab.call_count == 0, f"grab pass must never walk pending items; got {orch.grab.call_count} calls"
    assert summary.grabbed == 0
    assert summary.retried == 0
    assert summary.abandoned == 0
    assert summary.skipped == 0


# ---------------------------------------------------------------------------
# PR #320 review cycle 1 — stale-'searching' recovery must be ATOMIC (F-B2)
# and a failed grab must not invent availability (F-M4).
# ---------------------------------------------------------------------------


def _stale_searching_row(store: ConcreteAcquireStore, tvdb_id: int = 99) -> tuple[int, WantedItem]:
    """Claim a row and back-date its claim so the sweep sees it as stale.

    Returns:
        The rowid and the SNAPSHOT the pass would have listed — the in-memory
        object a concurrent mutation is free to invalidate.
    """
    rowid = store.wanted.add(_pending_item(tvdb_id=tvdb_id))
    store.wanted.claim_for_search(rowid, _PINNED_NOW - 7200)  # 2h ago > 1h threshold
    snapshot = store.wanted.get(rowid)
    assert snapshot is not None
    assert snapshot.status == "searching"
    return rowid, snapshot


def test_stale_recovery_never_reverts_a_grab_completed_since_the_queue_snapshot(
    store: ConcreteAcquireStore,
) -> None:
    """Regression (review F-B2): the recovery must not clobber a completed grab.

    The queue is listed once at the top of the pass. The old get-then-set
    recovery trusted that snapshot's ``status`` and wrote ``'pending'``
    unconditionally seconds later — so a grab a concurrent runner completed in
    between had its ``'grabbed'`` status DELETED while its torrent kept
    downloading, and the item was handed back to the queue as if nothing had
    been added.
    """
    rowid, snapshot = _stale_searching_row(store)
    # A concurrent runner finishes the grab AFTER the snapshot was taken.
    store.wanted.mark_grabbed(rowid, "livehash")

    orch = MagicMock(spec=GrabOrchestrator)
    service = _service(store, orch)
    with patch.object(store.wanted, "list_stale_searching", return_value=[snapshot]):
        summary = service.run()

    row = store.wanted.get(rowid)
    assert row is not None
    assert row.status == "grabbed", f"a completed grab must survive the sweep; got {row.status!r}"
    assert row.grabbed_hash == "livehash"
    assert orch.grab.call_count == 0, "the row was already grabbed — it must never be re-grabbed"
    assert summary.skipped == 1


def test_stale_recovery_never_double_claims_a_row_another_pass_re_took(
    store: ConcreteAcquireStore,
) -> None:
    """Regression (review F-B2): two passes must not both claim the same stale row.

    Both passes list the stale rows. With a get-then-set recovery, the second
    pass forced the row back to ``'pending'`` even though the first had just
    re-claimed it, and then won ``claim_for_search`` on its own write — two
    tracker searches (and two potential adds) for one item.
    """
    rowid, snapshot = _stale_searching_row(store)

    # Runner A recovers it and re-claims it (its claim is now FRESH).
    assert store.wanted.reclaim_stale_searching(rowid, _PINNED_NOW - 3600) is True
    assert store.wanted.claim_for_search(rowid, _PINNED_NOW) is True
    attempts_after_a = store.wanted.get(rowid)
    assert attempts_after_a is not None
    assert attempts_after_a.attempts == 2

    # Runner B still holds the pass-start snapshot.
    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="success", info_hash="h", found=1)
    service = _service(store, orch)
    with patch.object(store.wanted, "list_stale_searching", return_value=[snapshot]):
        summary = service.run()

    assert orch.grab.call_count == 0, "runner B must not steal a row runner A just re-claimed"
    assert summary.skipped == 1
    row = store.wanted.get(rowid)
    assert row is not None
    assert row.status == "searching", f"runner A's claim must stand; got {row.status!r}"
    assert row.attempts == 2, f"runner B must not stamp a second claim; got attempts={row.attempts}"


def test_grab_retryable_does_not_promote_a_verdictless_row_to_available(
    store: ConcreteAcquireStore,
) -> None:
    """Regression (review F-M4): a failed grab must not invent « À récupérer ».

    A stale 'searching' row recovered by the sweep has NO ``available``
    verdict — its last search never concluded (or never ran). Forcing
    ``status='available'`` on the retryable path made the UI announce a takeable
    item on the strength of an outage, and the search pass (which walks only
    'pending') would never re-verify it.
    """
    rowid, _snapshot = _stale_searching_row(store)
    before = store.wanted.get(rowid)
    assert before is not None and before.last_search_outcome is None

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="retryable", reason="circuit_open", found=None)

    service = _service(store, orch)
    summary = service.run()

    assert orch.grab.call_count == 1
    row = store.wanted.get(rowid)
    assert row is not None
    assert row.status == "pending", f"a verdict-less row must fall back to 'pending'; got {row.status!r}"
    assert row.last_search_outcome is None, "the retryable path must not fabricate a verdict"
    assert summary.retried == 1


def test_claim_stamps_a_fresh_clock_not_the_pass_start(store: ConcreteAcquireStore) -> None:
    """Regression (review F-M13): claims stamp claim-time, not pass-start time.

    ``last_search_at`` is the staleness clock every other runner reads. A long
    pass stamping its START time makes its own in-flight rows read as stale to a
    concurrent sweep, which then reclaims work that is actively running.
    """
    rowid = _available_item(store, tvdb_id=99, found=2)

    # The pass starts here; the per-item claim happens 10 minutes later. The 4th
    # value feeds the provenance grabbed_at read (feature provenance) that now
    # follows mark_grabbed — a later call than the claim, so last_search_at (the
    # 2nd value) is unaffected. patch() targets the shared `time` module globally.
    clock = iter([float(_PINNED_NOW), float(_PINNED_NOW + 600), float(_PINNED_NOW + 600), float(_PINNED_NOW + 600)])

    orch = MagicMock(spec=GrabOrchestrator)
    orch.grab.return_value = GrabOutcome(disposition="success", info_hash="h", found=2)
    service = _service(store, orch)
    with patch("personalscraper.acquire.service.time.time", side_effect=lambda: next(clock)):
        service.run()

    row = store.wanted.get(rowid)
    assert row is not None
    assert row.last_search_at == _PINNED_NOW + 600, (
        f"the claim must stamp its own clock, not the pass start; got {row.last_search_at}"
    )

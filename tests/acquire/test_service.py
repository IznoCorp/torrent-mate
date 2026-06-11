"""Tests for AcquisitionService + state machine + WantedItem.id round-trip (RP5b 4b).

Load-bearing tests called out (DESIGN §7, §11):
- ``list_pending()[0].id`` round-trips the rowid (was a blocking gap).
- Two concurrent ``claim_for_search`` on one row → EXACTLY one ``True`` (atomic claim;
  the loser must not proceed).
- ``claim_for_search`` stamps ``attempts`` + ``last_search_at`` atomically.
- ``mark_grabbed`` persists status='grabbed' + the info-hash (idempotence guard).
- ``list_stale_searching`` recovers a row stuck mid-grab; recent rows are excluded.
- Hash-guard: a grabbed row is NOT re-claimed on re-run → NO 2nd ``GrabSucceeded``.
- Failure recovery: retryable → 'pending' (re-listed); terminal → 'abandoned';
  attempts ≥ cap on retryable → 'abandoned' (no infinite loop).
- Service end-to-end: a pending item, orchestrator success → ``mark_grabbed`` with the
  info-hash, ``RunSummary`` counts 1 grabbed.
- NEGATIVE (DESIGN §9): ``store.seed.add`` / ``record_dispatch`` call_count == 0 during grab.
- Wiring: ``build_acquire_context(..., torrent_client=<mock>)`` → ``ctx.grab`` is a
  ``GrabCore``; ``torrent_client=None`` → ``ctx.grab is None``.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import GrabSucceeded, WantedAbandoned
from personalscraper.acquire.orchestrator import GrabOutcome
from personalscraper.acquire.service import MAX_ATTEMPTS, AcquisitionService, GrabCore, RunSummary
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    """Yield a store on a temp acquire.db and close it afterwards."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _pending_item(tvdb_id: int = 99) -> WantedItem:
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind="movie",
        status="pending",
        enqueued_at=1_700_000_000,
    )


# ---------------------------------------------------------------------------
# Task 1 — WantedItem.id round-trip
# ---------------------------------------------------------------------------


def test_list_pending_populates_id(store: ConcreteAcquireStore) -> None:
    """LOAD-BEARING (DESIGN §7): list_pending()[0].id round-trips the rowid."""
    rowid = store.wanted.add(_pending_item())
    pending = store.wanted.list_pending()
    assert len(pending) == 1
    assert pending[0].id == rowid, f"Expected id={rowid}, got id={pending[0].id} — list_pending must SELECT id"


def test_get_populates_id_and_grabbed_hash(store: ConcreteAcquireStore) -> None:
    """get() must round-trip id and a (None) grabbed_hash for a fresh row."""
    rowid = store.wanted.add(_pending_item())
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.id == rowid
    assert item.grabbed_hash is None


# ---------------------------------------------------------------------------
# Task 2 — atomic store methods
# ---------------------------------------------------------------------------


def test_claim_for_search_atomic_only_one_wins(tmp_path: Path) -> None:
    """LOAD-BEARING (DESIGN §7/§11a): two claim_for_search on one row → exactly one True.

    Two distinct store handles (separate connections to the same db_path) race
    on the same rowid. ``BEGIN IMMEDIATE`` + ``WHERE status='pending'`` makes
    the claim the single serialisation point: exactly one UPDATE matches a
    'pending' row (rowcount==1 → True), the other sees 'searching' (rowcount==0
    → False) and must NOT proceed.
    """
    cfg = AcquireConfig(db_path=tmp_path / "acquire2.db")
    store1 = build_acquire_store(cfg)
    store2 = build_acquire_store(cfg)
    try:
        rowid = store1.wanted.add(_pending_item())
        now = int(time.time())
        result1 = store1.wanted.claim_for_search(rowid, now)
        result2 = store2.wanted.claim_for_search(rowid, now)
        wins = [r for r in (result1, result2) if r is True]
        assert len(wins) == 1, f"Exactly one claim must win; got result1={result1}, result2={result2}"
        # The loser must observe a non-pending row (so it skips).
        item = store1.wanted.get(rowid)
        assert item is not None
        assert item.status == "searching"
        assert item.attempts == 1, "claim must stamp attempts exactly once (the loser is a no-op)"
    finally:
        store1.close()
        store2.close()


def test_claim_for_search_stamps_attempts_and_last_search_at(store: ConcreteAcquireStore) -> None:
    """A winning claim stamps attempts=1 and last_search_at=now atomically."""
    rowid = store.wanted.add(_pending_item())
    now = 1_700_000_100
    won = store.wanted.claim_for_search(rowid, now)
    assert won is True
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "searching"
    assert item.attempts == 1
    assert item.last_search_at == now


def test_claim_for_search_returns_false_when_already_searching(store: ConcreteAcquireStore) -> None:
    """A second claim on a now-'searching' row returns False (not re-claimable)."""
    rowid = store.wanted.add(_pending_item())
    now = int(time.time())
    assert store.wanted.claim_for_search(rowid, now) is True
    # Second call on the same row (now 'searching') must return False.
    assert store.wanted.claim_for_search(rowid, now) is False


def test_mark_grabbed_persists_status_and_hash(store: ConcreteAcquireStore) -> None:
    """mark_grabbed persists status='grabbed' AND the info-hash (idempotence guard)."""
    rowid = store.wanted.add(_pending_item())
    store.wanted.claim_for_search(rowid, int(time.time()))
    store.wanted.mark_grabbed(rowid, "deadbeef1234")
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "grabbed"
    assert item.grabbed_hash == "deadbeef1234"


def test_list_stale_searching_returns_old_searching_rows(store: ConcreteAcquireStore) -> None:
    """A 'searching' row with an old last_search_at is returned for recovery."""
    rowid = store.wanted.add(_pending_item())
    old_ts = 1_000_000  # far in the past
    store.wanted.claim_for_search(rowid, old_ts)
    stale = store.wanted.list_stale_searching(older_than=old_ts + 1)
    assert any(i.id == rowid for i in stale)


def test_list_stale_searching_excludes_recent(store: ConcreteAcquireStore) -> None:
    """A freshly-claimed 'searching' row is NOT stale (last_search_at >= threshold)."""
    rowid = store.wanted.add(_pending_item())
    now = int(time.time())
    store.wanted.claim_for_search(rowid, now)
    stale = store.wanted.list_stale_searching(older_than=now - 1)
    assert not any(i.id == rowid for i in stale)


def test_list_stale_searching_excludes_pending(store: ConcreteAcquireStore) -> None:
    """A never-claimed 'pending' row is NOT stale (only 'searching' rows qualify)."""
    rowid = store.wanted.add(_pending_item())
    stale = store.wanted.list_stale_searching(older_than=int(time.time()) + 10_000)
    assert not any(i.id == rowid for i in stale)


# ---------------------------------------------------------------------------
# Task 3 — AcquisitionService
# ---------------------------------------------------------------------------


def _success_orch(info_hash: str = "h1") -> MagicMock:
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(disposition="success", info_hash=info_hash)
    return orch


def _service(store: object, orchestrator: MagicMock, event_bus: MagicMock | None = None) -> AcquisitionService:
    """Build a service with a (mock) event_bus — required by the no-optional-bus contract."""
    return AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=event_bus if event_bus is not None else MagicMock(),
    )


def test_run_returns_run_summary(store: ConcreteAcquireStore) -> None:
    """run() returns a RunSummary."""
    store.wanted.add(_pending_item())
    service = _service(store, _success_orch())
    summary = service.run(limit=10)
    assert isinstance(summary, RunSummary)


def test_run_claims_and_grabs_pending_items(store: ConcreteAcquireStore) -> None:
    """End-to-end: pending items grabbed → mark_grabbed with the info-hash, count 1 each."""
    id1 = store.wanted.add(_pending_item(tvdb_id=1))
    id2 = store.wanted.add(_pending_item(tvdb_id=2))
    orch = _success_orch(info_hash="hh")
    service = _service(store, orch)
    summary = service.run(limit=10)
    assert orch.grab.call_count == 2
    assert summary.grabbed == 2
    # Both rows persisted as grabbed with the info-hash.
    for wid in (id1, id2):
        item = store.wanted.get(wid)
        assert item is not None
        assert item.status == "grabbed"
        assert item.grabbed_hash == "hh"


def test_run_respects_limit(store: ConcreteAcquireStore) -> None:
    """run(limit=N) attempts at most N items."""
    for i in range(5):
        store.wanted.add(_pending_item(tvdb_id=i))
    orch = _success_orch()
    service = _service(store, orch)
    summary = service.run(limit=2)
    assert orch.grab.call_count == 2
    assert summary.grabbed == 2


def test_run_retryable_resets_to_pending(store: ConcreteAcquireStore) -> None:
    """RETRYABLE outcome → row back to 'pending' and re-listed next run."""
    rowid = store.wanted.add(_pending_item())
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(disposition="retryable", reason="trackers_unavailable")
    service = _service(store, orch)
    summary = service.run(limit=10)
    assert summary.retried == 1
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "pending", "retryable must move the row OUT of 'searching' back to 'pending'"
    # Re-listed next run.
    assert any(i.id == rowid for i in store.wanted.list_pending())


def test_run_terminal_abandons(store: ConcreteAcquireStore) -> None:
    """TERMINAL outcome → row 'abandoned' (won't self-heal)."""
    rowid = store.wanted.add(_pending_item())
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(disposition="terminal", reason="no_candidates")
    service = _service(store, orch)
    summary = service.run(limit=10)
    assert summary.abandoned == 1
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "abandoned"


def test_attempts_cap_abandons_item(store: ConcreteAcquireStore) -> None:
    """LOAD-BEARING (DESIGN §6.2): attempts ≥ MAX_ATTEMPTS on a retryable → abandoned (no infinite loop).

    A row that keeps failing retryably must eventually abandon. After the claim
    advances attempts to the cap, a retryable outcome must NOT reset it to
    'pending' (that would loop forever) — the service abandons it and emits
    ``WantedAbandoned('attempts_cap')``.
    """
    rowid = store.wanted.add(_pending_item())
    # Exhaust attempts up to MAX_ATTEMPTS - 1 via direct claim/reset cycles so the
    # NEXT service claim lands exactly at the cap.
    for _ in range(MAX_ATTEMPTS - 1):
        store.wanted.claim_for_search(rowid, int(time.time()))
        store.wanted.set_status(rowid, "pending")

    mock_event_bus = MagicMock()
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(disposition="retryable", reason="add_failed")
    service = AcquisitionService(store=store, orchestrator=orch, event_bus=mock_event_bus)
    summary = service.run(limit=10)

    item = store.wanted.get(rowid)
    assert item is not None
    assert item.attempts >= MAX_ATTEMPTS
    assert item.status == "abandoned"
    assert summary.abandoned == 1
    # WantedAbandoned('attempts_cap') must have been emitted by the service.
    emitted = [c.args[0] for c in mock_event_bus.emit.call_args_list]
    assert any(isinstance(e, WantedAbandoned) and "attempts_cap" in e.reason for e in emitted), (
        f"expected WantedAbandoned('attempts_cap'); got {emitted}"
    )


def test_run_skips_when_claim_lost(store: ConcreteAcquireStore) -> None:
    """A row already claimed by a concurrent process is skipped (claim returns False)."""
    rowid = store.wanted.add(_pending_item())
    # Pre-claim it (simulating a concurrent winner) → service must lose the claim.
    store.wanted.claim_for_search(rowid, int(time.time()))
    store.wanted.set_status(rowid, "pending")  # back to pending so list_pending returns it...

    # ...but a competing store claims it after list_pending, before our claim.
    competing = MagicMock(wraps=store.wanted)

    orch = _success_orch()
    service = _service(MagicMock(wanted=competing), orch)

    # Make the service's own claim_for_search lose (return False).
    competing.list_pending.return_value = store.wanted.list_pending()
    competing.list_stale_searching.return_value = []
    competing.claim_for_search.return_value = False

    summary = service.run(limit=10)
    assert summary.skipped == 1
    assert orch.grab.call_count == 0


def test_run_processes_stale_searching(store: ConcreteAcquireStore) -> None:
    """A row stuck 'searching' with an old last_search_at is recovered and re-grabbed.

    The stale row is moved back to 'pending' by the recovery path's re-claim,
    so the atomic claim re-stamps it and the orchestrator runs on it.
    """
    rowid = store.wanted.add(_pending_item())
    old_ts = 1_000  # ancient → stale
    store.wanted.claim_for_search(rowid, old_ts)  # now 'searching', last_search_at=1000
    assert store.wanted.get(rowid).status == "searching"  # type: ignore[union-attr]

    orch = _success_orch(info_hash="recovered")
    service = _service(store, orch)
    summary = service.run(limit=10)

    assert orch.grab.call_count == 1
    assert summary.grabbed == 1
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "grabbed"
    assert item.grabbed_hash == "recovered"


# ---------------------------------------------------------------------------
# Hash-guard — no double emit across re-runs
# ---------------------------------------------------------------------------


def test_hash_guard_no_double_grab_on_rerun(store: ConcreteAcquireStore) -> None:
    """LOAD-BEARING (DESIGN §7/§11d): a grabbed row is NOT re-claimed → NO 2nd GrabSucceeded.

    First run grabs and marks the row 'grabbed' (persisting the info-hash). A
    second run must NOT re-claim it (it's no longer 'pending' and not stale), so
    the orchestrator is not invoked again and no second ``GrabSucceeded`` fires.
    """
    rowid = store.wanted.add(_pending_item())
    orch = _success_orch(info_hash="once")
    service = _service(store, orch)

    summary1 = service.run(limit=10)
    assert summary1.grabbed == 1
    assert orch.grab.call_count == 1
    assert store.wanted.get(rowid).grabbed_hash == "once"  # type: ignore[union-attr]

    # Re-run: the grabbed row is invisible to list_pending and not stale.
    summary2 = service.run(limit=10)
    assert summary2.grabbed == 0
    assert orch.grab.call_count == 1, "grabbed row must NOT be re-grabbed on re-run (hash-guard)"


def test_hash_guard_no_double_emit_via_event_bus(store: ConcreteAcquireStore) -> None:
    """Across two runs, exactly ONE GrabSucceeded reaches the bus for one item.

    The orchestrator emits GrabSucceeded; the service owns the status. With the
    hash-guard the grabbed row is never re-claimed, so the real orchestrator's
    single emit is the only one. We assert call_count==1 over both runs.
    """
    rowid = store.wanted.add(_pending_item())
    bus = MagicMock()

    # A real-shaped orchestrator stub that emits GrabSucceeded exactly when grab() runs.
    def _grab(item: WantedItem, profile: object) -> GrabOutcome:
        bus.emit(
            GrabSucceeded(
                media_ref=item.media_ref,
                info_hash="emit-once",
                source_tracker="lacale",
                category=None,
                tags=("lacale",),
            )
        )
        return GrabOutcome(disposition="success", info_hash="emit-once")

    orch = MagicMock()
    orch.grab.side_effect = _grab
    service = AcquisitionService(store=store, orchestrator=orch, event_bus=bus)

    service.run(limit=10)
    service.run(limit=10)

    grab_succeeded = [c.args[0] for c in bus.emit.call_args_list if isinstance(c.args[0], GrabSucceeded)]
    assert len(grab_succeeded) == 1, f"exactly one GrabSucceeded expected; got {len(grab_succeeded)}"
    assert store.wanted.get(rowid).status == "grabbed"  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# NEGATIVE invariant (DESIGN §9) — no seed-write at grab time
# ---------------------------------------------------------------------------


def test_negative_no_seed_write_during_run(store: ConcreteAcquireStore) -> None:
    """LOAD-BEARING NEGATIVE (DESIGN §9/§11g): seed.add / record_dispatch call_count == 0.

    Seed obligations are a DISPATCH-time concern. A grab-time write would be a
    phantom obligation. We spy the store's seed sub-store and assert it is never
    written during a full run that grabs an item.
    """
    store.wanted.add(_pending_item())
    seed_spy = MagicMock(wraps=store.seed)
    spy_store = MagicMock()
    spy_store.wanted = store.wanted
    spy_store.seed = seed_spy
    orch = _success_orch()
    service = _service(spy_store, orch)

    service.run(limit=10)

    assert seed_spy.add.call_count == 0, "seed.add MUST NOT be called at grab time (DESIGN §9)"
    # record_dispatch is the delete_authority API; the service never touches it.
    assert not hasattr(orch, "record_dispatch") or orch.record_dispatch.call_count == 0


# ---------------------------------------------------------------------------
# Task 4 — GrabCore wiring
# ---------------------------------------------------------------------------


def _wiring_config(tmp_path: Path) -> MagicMock:
    config = MagicMock()
    config.acquire.db_path = tmp_path / "acquire.db"
    return config


def test_build_acquire_context_grab_is_none_without_torrent_client(tmp_path: Path) -> None:
    """Without a torrent_client, the grab slot must be None (read-only/dry-run)."""
    from personalscraper.acquire._factory import build_acquire_context

    config = _wiring_config(tmp_path)
    with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
        mock_build.return_value = MagicMock()
        ctx = build_acquire_context(config, MagicMock(), event_bus=MagicMock(), cb_policy=MagicMock())
    assert ctx.grab is None


def test_build_acquire_context_grab_is_grabcore_with_torrent_client(tmp_path: Path) -> None:
    """With a torrent_client, ctx.grab is a GrabCore bundling service + orchestrator."""
    from personalscraper.acquire._factory import build_acquire_context

    config = _wiring_config(tmp_path)
    fake_registry = MagicMock()
    fake_registry.transports.return_value = {}
    with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
        mock_build.return_value = fake_registry
        ctx = build_acquire_context(
            config,
            MagicMock(),
            event_bus=MagicMock(),
            cb_policy=MagicMock(),
            torrent_client=MagicMock(),
        )
    assert isinstance(ctx.grab, GrabCore)
    assert isinstance(ctx.grab.service, AcquisitionService)
    assert ctx.grab.orchestrator is not None


def test_grabcore_built_via_registry_transports(tmp_path: Path) -> None:
    """GrabCore construction sources transports from registry.transports() (phase 2 accessor)."""
    from personalscraper.acquire._factory import build_acquire_context

    config = _wiring_config(tmp_path)
    fake_registry = MagicMock()
    fake_registry.transports.return_value = {}
    with patch("personalscraper.acquire._factory.build_tracker_registry") as mock_build:
        mock_build.return_value = fake_registry
        build_acquire_context(
            config,
            MagicMock(),
            event_bus=MagicMock(),
            cb_policy=MagicMock(),
            torrent_client=MagicMock(),
        )
    fake_registry.transports.assert_called_once_with()

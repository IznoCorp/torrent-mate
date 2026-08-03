"""Tests for AcquisitionService + state machine + WantedItem.id round-trip (RP5b 4b).

``service.run()`` is the GRAB pass since acq-states phase 2: it consumes only
items a search already concluded takeable (``status='available'``), so every
run() case here seeds an AVAILABLE row. Seeding 'pending' would exercise
nothing — the pending backlog belongs to ``run_search`` (test_search_pass.py)
and is invisible to the grab pass (test_grab_pass.py pins that boundary).

Load-bearing tests called out (DESIGN §7, §11):
- ``list_pending()[0].id`` round-trips the rowid (was a blocking gap).
- Two concurrent ``claim_for_search`` on one row → EXACTLY one ``True`` (atomic claim;
  the loser must not proceed).
- ``claim_for_search`` stamps ``attempts`` + ``last_search_at`` atomically.
- ``mark_grabbed`` persists status='grabbed' + the info-hash (idempotence guard).
- ``list_stale_searching`` recovers a row stuck mid-grab; recent rows are excluded.
- Hash-guard: a grabbed row is NOT re-claimed on re-run → NO 2nd ``GrabSucceeded``.
- Failure recovery: retryable → stays 'available' (re-listed, verdict intact);
  not_found → 'pending'; terminal → 'abandoned'. NO attempts cap (dropped with
  the search/grab split — a high attempts count never abandons at grab time).
- Service end-to-end: an available item, orchestrator success → ``mark_grabbed``
  with the info-hash, ``RunSummary`` counts 1 grabbed.
- NEGATIVE (DESIGN §9): ``store.seed.add`` / ``record_dispatch`` call_count == 0 during grab.
- Wiring: ``build_acquire_context(..., torrent_client=<mock>)`` → ``ctx.grab`` is a
  ``GrabCore``; ``torrent_client=None`` → ``ctx.grab is None``.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.desired import QualityProfile, Resolution, quality_profile_to_json
from personalscraper.acquire.domain import FollowedSeries, WantedItem
from personalscraper.acquire.events import GrabSucceeded, WantedAbandoned
from personalscraper.acquire.orchestrator import GrabOutcome
from personalscraper.acquire.service import (
    AcquisitionService,
    GrabCore,
    RunSummary,
)
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
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


# Pinned service clock: 1h after the items' enqueued_at (1_700_000_000). With the
# default Hot/Warm/Cold/30d cadence this puts every _pending_item in the Hot tier
# (age 1h < 72h) and well within the 30d cutoff, so a fresh row (last_search_at is
# None) is DUE immediately — preserving the pre-cadence grab/retry/stale behaviour.
# Without this pin, real ``now`` (~2026) would be >30d past enqueued_at and the new
# cutoff gate would abandon every legacy fixture row. Cadence-specific behaviour is
# exercised in test_service_cadence.py.
_PINNED_NOW = 1_700_003_600  # enqueued_at + 3600s


@pytest.fixture(autouse=True)
def _pin_service_clock() -> Iterator[None]:
    """Pin ``service.time.time`` so legacy fixture rows stay due (not cutoff-abandoned).

    Tests that need a different clock (e.g. the §11d stale-recovery window) nest
    their own ``patch("...service.time.time", ...)`` which overrides this for the
    duration of the inner ``with`` block.
    """
    with patch("personalscraper.acquire.service.time.time", return_value=_PINNED_NOW):
        yield


def _pending_item(tvdb_id: int = 99) -> WantedItem:
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind="movie",
        status="pending",
        enqueued_at=1_700_000_000,
    )


def _available_item(tvdb_id: int = 99, *, found: int = 5) -> WantedItem:
    """A wanted row the SEARCH pass concluded takeable — the grab pass's input.

    Carries the verdict columns the search pass would have written, so the
    grab-pass tests assert against a realistic row (in particular the retryable
    case, which must leave that verdict untouched).
    """
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind="movie",
        status="available",
        enqueued_at=1_700_000_000,
        last_search_outcome="available",
        last_search_found=found,
    )


def _make_tracker_result(*, provider: str = "c411", info_hash: str = "aaaa1234") -> TrackerResult:
    """Build a minimal TrackerResult to stand in as the orchestrator's ``chosen``."""
    return TrackerResult(
        provider=provider,
        tracker_id="t1",
        title="Inception 2010 MULTi 1080p BluRay x265-GRP",
        size=ByteSize(5_000_000_000),
        seeders=50,
        leechers=0,
        resolution="1080p",
        info_hash=info_hash,
        download_url=f"https://{provider}.test/torrent/1",
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


def _config() -> MagicMock:
    """Return a config stub whose ``.acquire`` is a real default :class:`AcquireConfig`.

    The service reads ``config.acquire.cadence`` via ``cadence_from_config`` once
    per run; a real ``AcquireConfig()`` supplies the canonical Hot/Warm/Cold/30d
    cadence so the cadence helpers operate on real values (a bare MagicMock would
    not).
    """
    config = MagicMock()
    config.acquire = AcquireConfig()  # default cadence — Hot/Warm/Cold/30d
    return config


def _service(store: object, orchestrator: MagicMock, event_bus: MagicMock | None = None) -> AcquisitionService:
    """Build a service with a (mock) event_bus — required by the no-optional-bus contract."""
    return AcquisitionService(
        store=store,  # type: ignore[arg-type]
        orchestrator=orchestrator,  # type: ignore[arg-type]
        event_bus=event_bus if event_bus is not None else MagicMock(),
        config=_config(),
    )


def test_run_returns_run_summary(store: ConcreteAcquireStore) -> None:
    """run() returns a RunSummary."""
    store.wanted.add(_available_item())
    service = _service(store, _success_orch())
    summary = service.run(limit=10)
    assert isinstance(summary, RunSummary)


def test_run_claims_and_grabs_available_items(store: ConcreteAcquireStore) -> None:
    """End-to-end: available items grabbed → mark_grabbed with the info-hash, count 1 each."""
    id1 = store.wanted.add(_available_item(tvdb_id=1))
    id2 = store.wanted.add(_available_item(tvdb_id=2))
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
        store.wanted.add(_available_item(tvdb_id=i))
    orch = _success_orch()
    service = _service(store, orch)
    summary = service.run(limit=2)
    assert orch.grab.call_count == 2
    assert summary.grabbed == 2


def _available_item_for(followed_id: int, tvdb_id: int) -> WantedItem:
    """An available WantedItem bound to *followed_id* (OBJ3 per-series scoping).

    Uses ``kind="movie"`` (like :func:`_available_item`) so the item is within
    the cutoff under the pinned clock without airing-date gating — the test
    isolates the followed_id scoping, not episode airing logic.
    """
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb_id),
        kind="movie",
        status="available",
        enqueued_at=1_700_000_000,
        followed_id=followed_id,
        last_search_outcome="available",
        last_search_found=5,
    )


def test_run_scopes_to_followed_id(store: ConcreteAcquireStore) -> None:
    """run(followed_id=X) grabs only that series' items; others stay untouched (OBJ3)."""
    # Real followed_series rows so the wanted FK is satisfied.
    fid_a = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=100), title="Series A", added_at=1_700_000_000))
    fid_b = store.follow.add(FollowedSeries(media_ref=MediaRef(tvdb_id=200), title="Series B", added_at=1_700_000_000))
    a1 = store.wanted.add(_available_item_for(followed_id=fid_a, tvdb_id=1))
    a2 = store.wanted.add(_available_item_for(followed_id=fid_a, tvdb_id=2))
    other = store.wanted.add(_available_item_for(followed_id=fid_b, tvdb_id=3))
    orphan = store.wanted.add(_available_item(tvdb_id=4))  # followed_id=None

    orch = _success_orch(info_hash="hh")
    service = _service(store, orch)
    summary = service.run(followed_id=fid_a)

    # Only series A's two items were attempted + grabbed.
    assert orch.grab.call_count == 2
    assert summary.grabbed == 2
    for wid in (a1, a2):
        item = store.wanted.get(wid)
        assert item is not None
        assert item.status == "grabbed"

    # The other series' item and the un-followed orphan are untouched (still
    # available, never claimed).
    for wid in (other, orphan):
        item = store.wanted.get(wid)
        assert item is not None
        assert item.status == "available"
        assert item.attempts == 0


def test_resolve_effective_profile_uses_series_json(store: ConcreteAcquireStore) -> None:
    """§9 — the shared resolver honours the followed series' stored profile.

    Proves the real grab AND the ``grab --dry-run`` preview resolve the SAME
    effective profile (they both call resolve_effective_profile), so the
    preview never diverges from the run. A series stored with exclude_3d=False
    must yield exclude_3d=False (not the permissive default's True).
    """
    from personalscraper.acquire.desired import QualityProfile, Resolution, quality_profile_to_json
    from personalscraper.acquire.service import resolve_effective_profile

    stored = QualityProfile(min_resolution=Resolution.R1080P, exclude_3d=False)
    fid = store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=555),
            title="Custom Profile Series",
            added_at=1_700_000_000,
            quality_profile_json=quality_profile_to_json(stored),
        )
    )
    item = _available_item_for(followed_id=fid, tvdb_id=1)

    resolved = resolve_effective_profile(store, item)
    assert resolved.exclude_3d is False
    assert resolved.min_resolution == Resolution.R1080P


def test_resolve_effective_profile_default_without_follow(store: ConcreteAcquireStore) -> None:
    """An un-followed item resolves to the permissive default (exclude_3d True)."""
    from personalscraper.acquire.service import resolve_effective_profile

    resolved = resolve_effective_profile(store, _pending_item(tvdb_id=9))
    assert resolved.exclude_3d is True


def test_run_retryable_keeps_the_item_available(store: ConcreteAcquireStore) -> None:
    """RETRYABLE outcome → row back to 'available' and re-listed next run.

    The grab's own re-search did NOT conclude (outage / add failure), so the
    search pass's ``available`` verdict still stands: the row returns to the
    grab queue with its verdict untouched rather than being demoted to
    'pending' (which would claim the item is no longer known takeable).
    """
    rowid = store.wanted.add(_available_item(found=4))
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(disposition="retryable", reason="trackers_unavailable")
    service = _service(store, orch)
    summary = service.run(limit=10)
    assert summary.retried == 1
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "available", "retryable must move the row OUT of 'searching' back to 'available'"
    assert (item.last_search_outcome, item.last_search_found) == ("available", 4), (
        "a retryable grab must not overwrite the search pass's verdict"
    )
    # Re-listed next run.
    assert any(i.id == rowid for i in store.wanted.list_available())


def test_run_terminal_abandons(store: ConcreteAcquireStore) -> None:
    """TERMINAL outcome → row 'abandoned' with the reason recorded (won't self-heal)."""
    rowid = store.wanted.add(_available_item())
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(disposition="terminal", reason="tracker_auth")
    service = _service(store, orch)
    summary = service.run(limit=10)
    assert summary.abandoned == 1
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "abandoned"
    # The verdict says WHY, and found stays NULL — the search never concluded.
    assert item.last_search_outcome == "tracker_auth"
    assert item.last_search_found is None


def test_high_attempts_never_abandons_in_the_grab_pass(store: ConcreteAcquireStore) -> None:
    """The attempts cap is GONE from the grab pass (acq-states, ARBITRATION §1).

    ``attempts`` counts cadence-paced SEARCHES. While search and grab were one
    pass, ~5 of them hit the old MAX_ATTEMPTS=5 cap and the first flaky grab
    abandoned the item. After the split, a retryable grab on a
    many-times-searched item must keep it available — only the cutoff ages an
    item out.

    Mutation-proof: re-introducing an attempts-cap abandon in run() flips the
    status to 'abandoned' and emits WantedAbandoned, failing both asserts.
    """
    rowid = store.wanted.add(_available_item())
    # Push attempts well past the retired cap via claim/reset cycles.
    for _ in range(6):
        store.wanted.claim_for_search(rowid, _PINNED_NOW - 7200)
        store.wanted.set_status(rowid, "pending")
    store.wanted.set_status(rowid, "available")

    mock_event_bus = MagicMock()
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(disposition="retryable", reason="add_failed")
    service = AcquisitionService(store=store, orchestrator=orch, event_bus=mock_event_bus, config=_config())
    summary = service.run(limit=10)

    item = store.wanted.get(rowid)
    assert item is not None
    assert item.attempts > 5, "precondition: the row is way past the retired cap"
    assert item.status == "available", "a known-available item must not be abandoned on a flaky grab"
    assert summary.abandoned == 0
    assert summary.retried == 1
    emitted = [c.args[0] for c in mock_event_bus.emit.call_args_list]
    assert not any(isinstance(e, WantedAbandoned) for e in emitted), f"no abandon may fire; got {emitted}"


def test_run_skips_when_claim_lost(store: ConcreteAcquireStore) -> None:
    """A row already claimed by a concurrent process is skipped (claim returns False)."""
    store.wanted.add(_available_item())

    # A competing process claims the row after list_available, before our claim.
    competing = MagicMock(wraps=store.wanted)

    orch = _success_orch()
    service = _service(MagicMock(wanted=competing), orch)

    # Make the service's own claim_for_grab lose (return False).
    competing.list_available.return_value = store.wanted.list_available()
    competing.list_stale_searching.return_value = []
    competing.claim_for_grab.return_value = False

    summary = service.run(limit=10)
    assert summary.skipped == 1
    assert orch.grab.call_count == 0


def test_run_processes_stale_searching(store: ConcreteAcquireStore) -> None:
    """A row stuck 'searching' with an old last_search_at is recovered and re-grabbed.

    The stale row is moved back to 'pending' by the recovery path, so
    ``claim_for_search`` (which matches 'pending') re-stamps it and the
    orchestrator runs on it — the grab pass owns the sweep alongside its own
    available queue.
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
    second run must NOT re-claim it (it's no longer 'available' and not stale),
    so the orchestrator is not invoked again and no second ``GrabSucceeded``
    fires.
    """
    rowid = store.wanted.add(_available_item())
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


def test_service_emits_grab_succeeded_after_persist_exact_payload(store: ConcreteAcquireStore) -> None:
    """Emit-after-persist (DESIGN §15 / §11d): the SERVICE emits GrabSucceeded.

    The orchestrator no longer emits ``GrabSucceeded`` — it returns a success
    outcome carrying the payload. The service emits AFTER ``mark_grabbed``
    persists. Asserts exactly ONE GrabSucceeded with the carried payload, and
    that ``mark_grabbed`` ran BEFORE the emit (persist-then-emit ordering).
    """
    rowid = store.wanted.add(_available_item())
    bus = MagicMock()

    chosen = _make_tracker_result(provider="c411")
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(
        disposition="success",
        info_hash="emit-once",
        chosen=chosen,
        category="movies",
        tags=("c411",),
    )
    service = AcquisitionService(store=store, orchestrator=orch, event_bus=bus, config=_config())

    service.run(limit=10)

    # The row is persisted as grabbed with the hash BEFORE the event fires.
    item = store.wanted.get(rowid)
    assert item is not None and item.status == "grabbed" and item.grabbed_hash == "emit-once"

    grab_succeeded = [c.args[0] for c in bus.emit.call_args_list if isinstance(c.args[0], GrabSucceeded)]
    assert len(grab_succeeded) == 1, f"service must emit exactly one GrabSucceeded; got {len(grab_succeeded)}"
    ev = grab_succeeded[0]
    assert ev.media_ref == MediaRef(tvdb_id=99)
    assert ev.info_hash == "emit-once"
    assert ev.source_tracker == "c411"
    assert ev.category == "movies"
    assert ev.tags == ("c411",)


def test_hash_guard_no_double_emit_via_event_bus(store: ConcreteAcquireStore) -> None:
    """Across two runs, exactly ONE GrabSucceeded reaches the bus for one item.

    Emit-after-persist: the service emits GrabSucceeded after mark_grabbed. With
    the hash-guard the grabbed row is never re-claimed on the second run, so the
    service's single emit on run 1 is the only one. The orchestrator stub does
    NOT emit (matching the real orchestrator), so any double-emit would be a
    service bug, not a stub artefact.
    """
    rowid = store.wanted.add(_available_item())
    bus = MagicMock()

    chosen = _make_tracker_result(provider="c411")
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(disposition="success", info_hash="emit-once", chosen=chosen, tags=("c411",))
    service = AcquisitionService(store=store, orchestrator=orch, event_bus=bus, config=_config())

    service.run(limit=10)
    service.run(limit=10)

    grab_succeeded = [c.args[0] for c in bus.emit.call_args_list if isinstance(c.args[0], GrabSucceeded)]
    assert len(grab_succeeded) == 1, f"exactly one GrabSucceeded expected; got {len(grab_succeeded)}"
    assert store.wanted.get(rowid).status == "grabbed"  # type: ignore[union-attr]


def test_section_11d_crash_window_never_double_emits_grab_succeeded(store: ConcreteAcquireStore) -> None:
    """LOAD-BEARING (DESIGN §11d, revised by M9/D2): the crash window NEVER double-emits.

    Emit-after-persist still holds, but M9 changed what recovery means. The
    orchestrator now reserves the chosen hash BEFORE its ``add()``, so the row
    left behind by a ``mark_grabbed`` crash carries an INTENT:

    * run 1 — ``add`` succeeded, ``mark_grabbed`` raised: NO ``GrabSucceeded``
      (persist failed first), row stays 'searching' but now WITH its hash;
    * run 2 — the grab pass must NOT touch it: ``reclaim_stale_searching``
      refuses a hash-carrying row, so the row is skipped rather than re-grabbed.
      That is the routing which prevents a second torrent for the same item;
    * the reconciliation is what closes it (see
      ``test_grab_intent_hash.py``): the torrent is in the client, so the row is
      confirmed 'grabbed' and its seed obligation is recorded.

    The §11d guarantee is therefore **at most once, never twice**: across the
    whole lifecycle of a crashed grab, ``GrabSucceeded`` fires ZERO times — the
    recovery is a state reconciliation, not a re-grab, and it does not fabricate
    a success event whose payload (category/tags) it does not hold.
    """
    import sqlite3  # noqa: PLC0415 — local to the crash-injection test

    rowid = store.wanted.add(_available_item())

    bus = MagicMock()
    chosen = _make_tracker_result(provider="c411")
    add_calls: list[str] = []

    def _grab(
        item: WantedItem,
        profile: object,
        *,
        on_intent: "Callable[[str], None] | None" = None,
        exclude_hashes: object = frozenset(),
    ) -> GrabOutcome:
        # Mirrors the real orchestrator: reserve the intent hash (M9/D2) BEFORE
        # the add, then add. Idempotent add(): every grab returns the SAME
        # info_hash (a duplicate add is a no-op returning the existing hash,
        # never a new torrent).
        if on_intent is not None:
            on_intent("aaaa1234")
        add_calls.append("aaaa1234")
        return GrabOutcome(disposition="success", info_hash="aaaa1234", chosen=chosen, tags=("c411",))

    orch = MagicMock()
    orch.grab.side_effect = _grab

    # Wrap the real wanted sub-store so mark_grabbed raises OperationalError on
    # the FIRST call only (the add→status crash window), then behaves normally.
    real_wanted = store.wanted
    wanted_spy = MagicMock(wraps=real_wanted)
    first_mark = {"done": False}

    def _mark_grabbed(wanted_id: int, info_hash: str) -> None:
        if not first_mark["done"]:
            first_mark["done"] = True
            raise sqlite3.OperationalError("database is locked")
        real_wanted.mark_grabbed(wanted_id, info_hash)

    wanted_spy.mark_grabbed.side_effect = _mark_grabbed
    spy_store = MagicMock()
    spy_store.wanted = wanted_spy
    spy_store.follow = store.follow

    service = AcquisitionService(store=spy_store, orchestrator=orch, event_bus=bus, config=_config())

    # --- Run 1: mark_grabbed crashes → row stays 'searching', NO emit. ---
    summary1 = service.run(limit=10)
    assert summary1.grabbed == 0
    assert summary1.skipped == 1, "the locked row must be isolated (skipped) and left for the stale sweep"
    assert not [c for c in bus.emit.call_args_list if isinstance(c.args[0], GrabSucceeded)], (
        "NO GrabSucceeded may fire when mark_grabbed crashed (emit-after-persist)"
    )
    item_mid = real_wanted.get(rowid)
    assert item_mid is not None
    assert item_mid.status == "searching", "row must stay 'searching' (recoverable, not lost)"
    assert item_mid.grabbed_hash == "aaaa1234", (
        "M9: the intent hash was reserved BEFORE add(), so the crashed row points at its torrent"
    )

    # --- Run 2: the grab pass must SKIP the intent row (routing proof). ---
    # Run 1 stamped last_search_at = _PINNED_NOW. Advance the clock past both the
    # 1h stale sweep window and the 2h Hot cadence so the row is listed and DUE —
    # the only thing keeping the pass off it is the hash guard itself.
    run2_now = _PINNED_NOW + 7200 + 10
    with patch("personalscraper.acquire.service.time.time", return_value=run2_now):
        summary2 = service.run(limit=10)

    assert summary2.grabbed == 0, "a hash-carrying row must never be re-grabbed by the pass"
    assert summary2.skipped == 1, "it is skipped and left to the reconciling recovery"
    item_final = real_wanted.get(rowid)
    assert item_final is not None
    assert item_final.status == "searching"
    assert item_final.grabbed_hash == "aaaa1234"

    # ZERO GrabSucceeded across BOTH runs, and above all never TWO (the §11d guarantee).
    grab_succeeded = [c.args[0] for c in bus.emit.call_args_list if isinstance(c.args[0], GrabSucceeded)]
    assert grab_succeeded == [], f"no success event may fire for a grab that never confirmed; got {grab_succeeded}"
    # add() ran ONCE: the second pass never reached the orchestrator, so no
    # duplicate torrent was ever handed to the client.
    assert add_calls == ["aaaa1234"]


# ---------------------------------------------------------------------------
# NEGATIVE invariant (DESIGN §9) — no seed-write at grab time
# ---------------------------------------------------------------------------


def test_negative_no_seed_write_during_run(store: ConcreteAcquireStore) -> None:
    """LOAD-BEARING NEGATIVE (DESIGN §9/§11g): seed.add / record_dispatch call_count == 0.

    Seed obligations are a DISPATCH-time concern. A grab-time write would be a
    phantom obligation. We spy the store's seed sub-store and assert it is never
    written during a full run that grabs an item.
    """
    store.wanted.add(_available_item())
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


def test_factory_does_not_snapshot_transports_at_boot(tmp_path: Path) -> None:
    """The factory must NOT call registry.transports() at construction (no boot login).

    A login-style tracker's ``_transport`` is a lazy property that logs in on
    first access (none is wired today; the contract outlives the client). An
    eager ``transports()`` snapshot at boot would force that login (defeating the
    network-free build guarantee) AND freeze a one-shot map a transient blip
    could leave stale. The orchestrator now reads ``transports()`` FRESH at grab
    time, so the factory takes NO snapshot — assert ``transports()`` is never
    called while building the context.
    """
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
    fake_registry.transports.assert_not_called()


# ---------------------------------------------------------------------------
# M1 — profile-overlay handoff (follow-lookup + effective_quality → orchestrator)
# ---------------------------------------------------------------------------


def test_resolve_profile_follow_lookup_passes_floor_to_orchestrator(store: ConcreteAcquireStore) -> None:
    """M1 (DESIGN §1/§3): a followed-series profile floor reaches the orchestrator.

    Seeds a FollowedSeries whose ``quality_profile_json`` carries a non-permissive
    floor (min_resolution=1080p), then a WantedItem bound to it (followed_id). The
    service must do the follow-lookup, decode the series profile, overlay the
    (default) item criteria, and hand the orchestrator a QualityProfile carrying
    that 1080p floor — proving the live follow→overlay→grab handoff, not just the
    unit-level ``effective_quality``.
    """
    followed_id = store.follow.add(
        FollowedSeries(
            media_ref=MediaRef(tvdb_id=4242),
            title="A Followed Show",
            added_at=1_700_000_000,
            quality_profile_json=quality_profile_to_json(QualityProfile(min_resolution=Resolution.R1080P)),
        )
    )
    store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=4242),
            kind="episode",
            status="available",
            enqueued_at=1_700_000_000,
            followed_id=followed_id,
            last_search_outcome="available",
            last_search_found=2,
        )
    )

    captured: dict[str, QualityProfile] = {}

    def _grab(
        item: WantedItem,
        profile: QualityProfile,
        *,
        on_intent: "Callable[[str], None] | None" = None,
        exclude_hashes: object = frozenset(),
    ) -> GrabOutcome:
        captured["profile"] = profile
        return GrabOutcome(disposition="success", info_hash="h", chosen=_make_tracker_result())

    orch = MagicMock()
    orch.grab.side_effect = _grab
    service = _service(store, orch)

    service.run(limit=10)

    assert "profile" in captured, "orchestrator.grab must have been called with a resolved profile"
    assert captured["profile"].min_resolution == Resolution.R1080P, (
        "the followed-series 1080p floor must reach the orchestrator (follow-lookup + overlay handoff)"
    )


# ---------------------------------------------------------------------------
# C2 — per-item error isolation (one bad row never aborts the batch, DESIGN §6.2)
# ---------------------------------------------------------------------------


def test_run_isolates_db_lock_and_continues_batch(store: ConcreteAcquireStore) -> None:
    """C2 (DESIGN §6.2): item 1's mark_grabbed OperationalError must NOT abort the batch.

    A 2-item queue where item 1's ``mark_grabbed`` raises ``sqlite3.OperationalError``
    (DB lock). The locked item is isolated (left 'searching' for the stale sweep,
    counted skipped) and item 2 IS still processed and grabbed. The run completes
    (``run_complete`` fires → a RunSummary is returned) with sane counts.
    """
    import sqlite3  # noqa: PLC0415 — local to the lock-injection test

    id1 = store.wanted.add(_available_item(tvdb_id=1))
    id2 = store.wanted.add(_available_item(tvdb_id=2))

    real_wanted = store.wanted
    wanted_spy = MagicMock(wraps=real_wanted)

    def _mark_grabbed(wanted_id: int, info_hash: str) -> None:
        # Item 1 hits a DB lock; item 2 persists normally.
        if wanted_id == id1:
            raise sqlite3.OperationalError("database is locked")
        real_wanted.mark_grabbed(wanted_id, info_hash)

    wanted_spy.mark_grabbed.side_effect = _mark_grabbed
    spy_store = MagicMock()
    spy_store.wanted = wanted_spy
    spy_store.follow = store.follow

    orch = _success_orch(info_hash="ok")
    service = _service(spy_store, orch)
    summary = service.run(limit=10)

    # The run COMPLETED and returned a RunSummary (batch not aborted).
    assert isinstance(summary, RunSummary)
    # Item 2 was still processed AND grabbed despite item 1's lock.
    assert orch.grab.call_count == 2
    assert summary.grabbed == 1
    assert summary.skipped == 1, "the locked item is isolated (skipped), not a batch abort"
    item2 = real_wanted.get(id2)
    assert item2 is not None and item2.status == "grabbed" and item2.grabbed_hash == "ok"
    # The locked item stays 'searching' (recoverable by the stale-searching sweep).
    item1 = real_wanted.get(id1)
    assert item1 is not None and item1.status == "searching"


def test_run_isolates_corrupt_criteria_json_abandons_only_that_row(store: ConcreteAcquireStore) -> None:
    """C2 (DESIGN §6.2): a corrupt criteria_json row is abandoned, the batch continues.

    Item 1 carries an un-decodable ``criteria_json`` → ``json.JSONDecodeError`` in
    ``_resolve_profile``. That single row is set 'abandoned' (guarded) and the run
    continues; item 2 is grabbed normally. The run completes with sane counts.
    """
    id1 = store.wanted.add(
        WantedItem(
            media_ref=MediaRef(tvdb_id=1),
            kind="movie",
            status="available",
            enqueued_at=1_700_000_000,
            criteria_json="{not valid json",
        )
    )
    id2 = store.wanted.add(_available_item(tvdb_id=2))

    orch = _success_orch(info_hash="ok")
    service = _service(store, orch)
    summary = service.run(limit=10)

    assert isinstance(summary, RunSummary)
    assert summary.abandoned == 1
    assert summary.grabbed == 1
    # The bad row is abandoned, the good row grabbed.
    bad = store.wanted.get(id1)
    assert bad is not None and bad.status == "abandoned"
    good = store.wanted.get(id2)
    assert good is not None and good.status == "grabbed"


def test_not_found_reverts_to_pending_and_never_abandons(store: ConcreteAcquireStore) -> None:
    """B.4 regression: a clean no-result re-search NEVER abandons, whatever the attempts.

    The House-of-the-Dragon bug: a just-aired episode searched 20 minutes after
    detect found zero hits and was permanently abandoned. With the ``not_found``
    disposition the row goes back to ``pending`` under cadence pacing regardless
    of the attempts count — only the cadence cutoff may age it out. At grab time
    ``not_found`` also means « the torrent vanished between the two passes », and
    the honest answer is the same revert, with the verdict recorded.
    """
    rowid = store.wanted.add(_available_item())
    # Push attempts well past the retired cap so an attempts-based abandon would fire.
    for _ in range(6):
        store.wanted.claim_for_search(rowid, _PINNED_NOW - 7200)
        store.wanted.set_status(rowid, "pending")
    store.wanted.set_status(rowid, "available")

    mock_event_bus = MagicMock()
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(disposition="not_found", reason="no_candidates", found=0)
    service = AcquisitionService(store=store, orchestrator=orch, event_bus=mock_event_bus, config=_config())
    summary = service.run(limit=10)

    item = store.wanted.get(rowid)
    assert item is not None
    assert item.attempts > 5
    assert item.status == "pending", "a not-out-yet episode must stay wanted"
    assert (item.last_search_outcome, item.last_search_found) == ("no_candidates", 0), (
        "the revert must record WHY, with found=0 — this search did conclude"
    )
    assert summary.retried == 1
    assert summary.abandoned == 0
    emitted = [c.args[0] for c in mock_event_bus.emit.call_args_list]
    assert not any(isinstance(e, WantedAbandoned) for e in emitted)


# ---------------------------------------------------------------------------
# Seed obligation at grab time (2026-07-15 — TV obligations undercount)
# ---------------------------------------------------------------------------


def _config_with_economy(tracker: str = "c411") -> MagicMock:
    """Config stub whose tracker registry carries a real economy block."""
    from types import SimpleNamespace

    from personalscraper.conf.models.api_config import TrackerEconomyConfig

    config = _config()
    config.tracker.providers = {
        tracker: SimpleNamespace(economy=TrackerEconomyConfig(target_ratio=2.0, min_ratio=1.0, min_seed_time=259200))
    }
    return config


def test_grab_success_records_seed_obligation(store: ConcreteAcquireStore) -> None:
    """A successful grab writes the obligation with hash + tracker + floors.

    Live gap: obligations were only written by the dispatch-time name+size
    correlation, which can never match a renamed/aggregated TV show folder —
    the seed_obligation table undercounted every TV grab. At grab time the
    identity is fully known; the path is backfilled at dispatch when the
    correlation hits.
    """
    store.wanted.add(_available_item())
    chosen = _make_tracker_result(provider="c411")
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(
        disposition="success",
        info_hash="tvhash01",
        chosen=chosen,
        category="tv",
        tags=("c411",),
    )
    service = AcquisitionService(store=store, orchestrator=orch, event_bus=MagicMock(), config=_config_with_economy())

    service.run(limit=10)

    row = store._conn.execute(
        "SELECT info_hash, source_tracker, dispatched_path, min_seed_time_s, min_ratio FROM seed_obligation"
    ).fetchone()
    assert row is not None, "a successful grab must record its seed obligation"
    assert tuple(row) == ("tvhash01", "c411", None, 259200, 1.0)


def test_grab_without_economy_records_nothing(store: ConcreteAcquireStore) -> None:
    """Activation-only trackers (no economy block) stay obligation-free."""
    store.wanted.add(_available_item())
    chosen = _make_tracker_result(provider="c411")
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(
        disposition="success", info_hash="nohash01", chosen=chosen, category="tv", tags=()
    )
    config = _config()
    config.tracker.providers = {}
    service = AcquisitionService(store=store, orchestrator=orch, event_bus=MagicMock(), config=config)

    service.run(limit=10)

    n = store._conn.execute("SELECT COUNT(*) FROM seed_obligation").fetchone()[0]
    assert n == 0


def test_grab_obligation_not_duplicated(store: ConcreteAcquireStore) -> None:
    """Two grabs resolving to the same info-hash keep a single active row."""
    store.wanted.add(_available_item())
    store.wanted.add(_available_item(tvdb_id=100))
    chosen = _make_tracker_result(provider="c411")
    orch = MagicMock()
    orch.grab.return_value = GrabOutcome(
        disposition="success", info_hash="duphash1", chosen=chosen, category="tv", tags=()
    )
    service = AcquisitionService(store=store, orchestrator=orch, event_bus=MagicMock(), config=_config_with_economy())

    service.run(limit=10)

    n = store._conn.execute("SELECT COUNT(*) FROM seed_obligation").fetchone()[0]
    assert n == 1, "the same info-hash must not accumulate duplicate active obligations"

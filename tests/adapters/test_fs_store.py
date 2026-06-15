"""Tests for :mod:`kanbanmate.adapters.store.fs_store`.

Exercises the filesystem-backed state store against a ``tmp_path`` root so
tests never touch the real ``~/.kanban/``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.ports.store import TicketState, TicketStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(
    issue_number: int = 42,
    item_id: str = "PVTI_001",
    session_id: str | None = "tmux-kanban-42",
    status: TicketStatus = TicketStatus.RUNNING,
    heartbeat: float = 1234567890.0,
    stage: str = "",
    profile: str = "",
    mode: str = "",
    started: float = 0.0,
    worktree: str = "",
    retries: int = 0,
) -> TicketState:
    """Build a :class:`TicketState` with sensible defaults for tests."""
    return TicketState(
        issue_number=issue_number,
        item_id=item_id,
        session_id=session_id,
        status=status,
        heartbeat=heartbeat,
        stage=stage,
        profile=profile,
        mode=mode,
        started=started,
        worktree=worktree,
        retries=retries,
    )


def _state_file_exists(store: FsStateStore, issue_number: int) -> bool:
    """Return ``True`` if the state JSON file for *issue_number* exists."""
    return (store.root / "state" / f"{issue_number}.json").exists()


def _temp_files(store: FsStateStore, issue_number: int) -> list[Path]:
    """Return any leftover ``.tmp`` files for *issue_number*."""
    return list((store.root / "state").glob(f"{issue_number}.json.*.tmp"))


# ---------------------------------------------------------------------------
# Round-trip save → load
# ---------------------------------------------------------------------------


class TestSaveLoadRoundTrip:
    """Verify that saving then loading a TicketState returns equivalent data."""

    def test_round_trip_running_state(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        original = _make_state()

        store.save(original)
        loaded = store.load(original.issue_number)

        assert loaded is not None
        assert loaded.issue_number == original.issue_number
        assert loaded.item_id == original.item_id
        assert loaded.session_id == original.session_id
        assert loaded.status == original.status
        assert loaded.heartbeat == original.heartbeat

    def test_round_trip_idle_state(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        original = _make_state(status=TicketStatus.IDLE, session_id=None)

        store.save(original)
        loaded = store.load(original.issue_number)

        assert loaded is not None
        assert loaded.status == "idle"
        assert loaded.session_id is None

    def test_round_trip_widened_metadata_fields(self, tmp_path: Path) -> None:
        """The widened stage + header-metadata fields (DESIGN §8.1.d) round-trip."""
        store = FsStateStore(root=tmp_path)
        original = _make_state(
            issue_number=37,
            stage="Implement",
            profile="dev",
            mode="acceptEdits",
            started=1700000000.0,
            worktree="/home/izno/.kanban/worktrees/ticket-37",
        )

        store.save(original)
        loaded = store.load(37)

        assert loaded is not None
        assert loaded.stage == "Implement"
        assert loaded.profile == "dev"
        assert loaded.mode == "acceptEdits"
        assert loaded.started == 1700000000.0
        assert loaded.worktree == "/home/izno/.kanban/worktrees/ticket-37"

    def test_round_trip_retries_field(self, tmp_path: Path) -> None:
        """The ``retries`` field (reaper relaunch-once counter) round-trips
        through save → load, and defaults to 0 for a fresh state."""
        store = FsStateStore(root=tmp_path)

        # Default: a fresh state has retries == 0.
        original_default = _make_state(issue_number=10)
        assert original_default.retries == 0

        store.save(original_default)
        loaded_default = store.load(10)
        assert loaded_default is not None
        assert loaded_default.retries == 0

        # Non-zero retries round-trip.
        original_bumped = _make_state(issue_number=11, retries=1)
        store.save(original_bumped)
        loaded_bumped = store.load(11)
        assert loaded_bumped is not None
        assert loaded_bumped.retries == 1

    def test_round_trip_relaunch_inputs(self, tmp_path: Path) -> None:
        """The relaunch inputs (prompt / script / on_fail / advance) round-trip (phase-25 §25.2).

        These are persisted at launch so the reaper can rebuild the EXACT LaunchAction and re-deliver
        the prompt (PoC parity). They must survive save → load; defaults (None / "") apply when a
        launch carried no prompt/script.
        """
        store = FsStateStore(root=tmp_path)
        original = TicketState(
            issue_number=140,
            item_id="PVTI_140",
            session_id="sess-140",
            status=TicketStatus.RUNNING,
            heartbeat=500.0,
            stage="Spec",
            profile="docs",
            mode="acceptEdits",
            prompt="/implement:brainstorm #140",
            script="check.sh",
            on_fail="block",
            advance="next",
        )

        store.save(original)
        loaded = store.load(140)

        assert loaded is not None
        assert loaded.prompt == "/implement:brainstorm #140"
        assert loaded.script == "check.sh"
        assert loaded.on_fail == "block"
        assert loaded.advance == "next"

        # A bare (prompt-less) launch round-trips the defaults (None / None / "" / "").
        bare = TicketState(
            issue_number=141,
            item_id="PVTI_141",
            session_id="sess-141",
            status=TicketStatus.RUNNING,
            heartbeat=500.0,
        )
        store.save(bare)
        loaded_bare = store.load(141)
        assert loaded_bare is not None
        assert loaded_bare.prompt is None
        assert loaded_bare.script is None
        assert loaded_bare.on_fail == ""
        assert loaded_bare.advance == ""

    def test_old_format_state_without_new_fields_loads_via_defaults(self, tmp_path: Path) -> None:
        """An OLD-shaped state file lacking the widened fields still loads.

        The new fields are DEFAULTED (DESIGN §8.1.d + 15.1), so the adapter's
        ``TicketState(**data)`` tolerates a JSON object that predates the
        widening — the absent fields fall back to their defaults rather than
        raising a ``TypeError``.
        """
        store = FsStateStore(root=tmp_path)
        # Exactly the pre-8.1.d on-disk shape: NO stage/profile/mode/started/worktree/retries keys.
        (store.root / "state" / "8.json").write_text(
            json.dumps(
                {
                    "issue_number": 8,
                    "item_id": "PVTI_OLD",
                    "session_id": "tmux-8",
                    "status": "running",
                    "heartbeat": 1234.0,
                }
            )
        )

        loaded = store.load(8)

        assert loaded is not None
        assert loaded.issue_number == 8
        assert loaded.item_id == "PVTI_OLD"
        # The widened fields degrade to their defaults — no crash, no metadata.
        assert loaded.stage == ""
        assert loaded.profile == ""
        assert loaded.mode == ""
        assert loaded.started == 0.0
        assert loaded.worktree == ""
        # 15.1: retries defaults to 0 when absent (old-format state still loads).
        assert loaded.retries == 0
        # phase-25 §25.2: the relaunch-input fields also default when absent (old-format state
        # predating them still loads — no TypeError, no field regression).
        assert loaded.prompt is None
        assert loaded.script is None
        assert loaded.on_fail == ""
        assert loaded.advance == ""

    def test_touch_heartbeat_preserves_widened_fields(self, tmp_path: Path) -> None:
        """A heartbeat touch must carry the widened launch metadata forward."""
        store = FsStateStore(root=tmp_path)
        original = _make_state(
            issue_number=21,
            stage="Plan",
            profile="docs",
            mode="acceptEdits",
            started=1700000000.0,
            worktree="/wt/ticket-21",
            heartbeat=100.0,
        )
        store.save(original)

        store.touch_heartbeat(21, now=200.0)

        reloaded = store.load(21)
        assert reloaded is not None
        assert reloaded.heartbeat == 200.0
        # The widened fields survive the read-modify-write cycle.
        assert reloaded.stage == "Plan"
        assert reloaded.profile == "docs"
        assert reloaded.mode == "acceptEdits"
        assert reloaded.started == 1700000000.0
        assert reloaded.worktree == "/wt/ticket-21"


class TestLoadAbsent:
    """When no state file exists, ``load`` returns ``None``."""

    def test_load_never_saved(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        assert store.load(99) is None

    def test_load_after_purge(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        state = _make_state(issue_number=7)
        store.save(state)
        store.purge_ticket(7)
        assert store.load(7) is None


# ---------------------------------------------------------------------------
# Load corrupt / unreadable / partial state files
# ---------------------------------------------------------------------------


class TestLoadCorrupt:
    """A corrupt state file is treated the same as absent — ``load`` returns ``None``,
    never raises (mirroring ``list_running``'s defensive skip)."""

    def test_corrupt_json_returns_none(self, tmp_path: Path) -> None:
        """Malformed JSON in a state file must not crash ``load``."""
        store = FsStateStore(root=tmp_path)
        (store.root / "state" / "42.json").write_text("{not json")

        result = store.load(42)
        assert result is None

    def test_corrupt_json_emits_named_logger_diagnostic(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A corrupt state file's ``load`` emits ONE named breadcrumb via the logger (#17/#8).

        Port of the PoC ``state.py:333-387`` corrupt-skip diagnostic: the skip must NOT be
        silent — the operator needs the offending file named. #8 routes it through the module
        logger (so it lands in ``daemon.jsonl`` where ``kanban logs`` reads it) instead of stderr.
        The skip itself still returns ``None`` (no raise)."""
        import logging

        store = FsStateStore(root=tmp_path)
        path = store.root / "state" / "42.json"
        path.write_text("{not json")

        with caplog.at_level(logging.WARNING):
            result = store.load(42)

        assert result is None  # still degrades to the no-state path, no raise
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert str(path) in messages  # the offending file is named in the breadcrumb

    def test_corrupt_state_is_quarantined(self, tmp_path: Path) -> None:
        """#11: a corrupt state file is MOVED to ``state/corrupt/`` (evidence preserved, no re-noise).

        After ``load`` hits the poison file it must be gone from ``state/`` (so the next tick does
        not re-parse it) but preserved under ``state/corrupt/`` for the operator to inspect.
        """
        store = FsStateStore(root=tmp_path)
        path = store.root / "state" / "42.json"
        path.write_text("{not json")

        assert store.load(42) is None

        # The poison file is no longer in state/ (the re-parse storm stops).
        assert not path.exists()
        # It was preserved (not deleted) under state/corrupt/.
        corrupt_files = list((store.root / "state" / "corrupt").glob("42-*.json"))
        assert len(corrupt_files) == 1
        assert corrupt_files[0].read_text() == "{not json"

    def test_corrupt_state_quarantine_stops_reparse_on_next_load(self, tmp_path: Path) -> None:
        """#11: after quarantine, a second load sees no state file (not the poison one again)."""
        store = FsStateStore(root=tmp_path)
        (store.root / "state" / "7.json").write_text('{"status": "BOGUS"}')

        assert store.load(7) is None  # first load quarantines it
        assert store.load(7) is None  # second load finds NO state file (clean no-state path)
        # Only one quarantined copy (the second load did not re-process / re-quarantine).
        assert len(list((store.root / "state" / "corrupt").glob("7-*.json"))) == 1

    def test_partial_json_missing_required_fields_returns_none(self, tmp_path: Path) -> None:
        """A JSON object that lacks required :class:`TicketState` fields must not
        crash ``load`` (TypeError from ``TicketState(**data)`` is caught)."""
        store = FsStateStore(root=tmp_path)
        # Missing `item_id`, `session_id`, `status`, `heartbeat`.
        (store.root / "state" / "99.json").write_text(json.dumps({"issue_number": 99}))

        result = store.load(99)
        assert result is None

    def test_empty_state_file_returns_none(self, tmp_path: Path) -> None:
        """An empty (zero-byte) state file is not valid JSON — must return None."""
        store = FsStateStore(root=tmp_path)
        (store.root / "state" / "7.json").write_text("")

        result = store.load(7)
        assert result is None

    def test_unknown_status_returns_none_with_breadcrumb(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Valid JSON with an unknown status enum value returns None WITH a
        named logger breadcrumb (#12 / M3, routed via logger #8)."""
        import logging

        store = FsStateStore(root=tmp_path)
        path = store.root / "state" / "9.json"
        data = {
            "issue_number": 9,
            "item_id": "PVTI_009",
            "session_id": None,
            "status": "BOGUS",
            "heartbeat": 1234567890.0,
        }
        path.write_text(json.dumps(data))

        with caplog.at_level(logging.WARNING):
            result = store.load(9)

        assert result is None  # degrades to no-state path (skip-don't-raise)
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert str(path) in messages

    def test_extra_field_typeerror_returns_none_with_breadcrumb(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Valid JSON + valid status but an unknown field (``TicketState(**data)``
        raises TypeError) returns None WITH a named stderr breadcrumb (#12 / M3)."""
        store = FsStateStore(root=tmp_path)
        path = store.root / "state" / "10.json"
        data = {
            "issue_number": 10,
            "item_id": "PVTI_010",
            "session_id": None,
            "status": "running",
            "heartbeat": 1234567890.0,
            "zzz_unknown": 1,  # extra field → TicketState(**data) raises TypeError
        }
        path.write_text(json.dumps(data))

        result = store.load(10)

        assert result is None  # degrades to no-state path (skip-don't-raise)
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert str(path) in messages


# ---------------------------------------------------------------------------
# Atomic save
# ---------------------------------------------------------------------------


class TestAtomicSave:
    """``save()`` writes are atomic: no partial/temp file remains observable."""

    def test_no_leftover_temp_files(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        state = _make_state()

        store.save(state)

        assert _state_file_exists(store, state.issue_number)
        assert _temp_files(store, state.issue_number) == []

    def test_loaded_content_is_complete(self, tmp_path: Path) -> None:
        """After a save, the loaded record must contain all fields (not partial)."""
        store = FsStateStore(root=tmp_path)
        state = _make_state(issue_number=1)

        store.save(state)
        loaded = store.load(1)

        assert loaded is not None
        # Every field must match — no missing key from a torn write.
        assert loaded.issue_number == state.issue_number
        assert loaded.item_id == state.item_id
        assert loaded.session_id == state.session_id
        assert loaded.status == state.status
        assert loaded.heartbeat == state.heartbeat

    def test_save_overwrites_previous(self, tmp_path: Path) -> None:
        """A second save on the same issue should replace, not append."""
        store = FsStateStore(root=tmp_path)
        state_v1 = _make_state(heartbeat=1.0)
        state_v2 = _make_state(heartbeat=2.0)

        store.save(state_v1)
        store.save(state_v2)

        loaded = store.load(_make_state().issue_number)
        assert loaded is not None
        assert loaded.heartbeat == 2.0


# ---------------------------------------------------------------------------
# touch_heartbeat
# ---------------------------------------------------------------------------


class TestTouchHeartbeat:
    """``touch_heartbeat`` refreshes liveness for an existing ticket and is a
    strict no-op (no-resurrection) when the ticket state is absent."""

    def test_updates_heartbeat_on_existing(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        state = _make_state(heartbeat=100.0)
        store.save(state)

        store.touch_heartbeat(state.issue_number, now=200.0)

        updated = store.load(state.issue_number)
        assert updated is not None
        assert updated.heartbeat == 200.0
        # Other fields untouched.
        assert updated.issue_number == state.issue_number
        assert updated.item_id == state.item_id
        assert updated.status == state.status

    def test_noop_when_state_absent(self, tmp_path: Path) -> None:
        """DESIGN §8.3 no-resurrection: touch_heartbeat must NEVER create a
        state file for a ticket that was torn down."""
        store = FsStateStore(root=tmp_path)
        store.touch_heartbeat(999, now=300.0)

        assert store.load(999) is None
        assert not _state_file_exists(store, 999)

    def test_noop_after_purge(self, tmp_path: Path) -> None:
        """After purge_ticket removed the state, touch_heartbeat must not
        resurrect it."""
        store = FsStateStore(root=tmp_path)
        state = _make_state(issue_number=5)
        store.save(state)
        store.purge_ticket(5)

        store.touch_heartbeat(5, now=400.0)

        assert store.load(5) is None
        assert not _state_file_exists(store, 5)

    def test_touch_heartbeat_preserves_other_fields(self, tmp_path: Path) -> None:
        """Only heartbeat should change; all other fields are carried forward."""
        store = FsStateStore(root=tmp_path)
        original = _make_state(
            issue_number=3,
            item_id="PVTI_XYZ",
            session_id="sess-3",
            status=TicketStatus.RUNNING,
            heartbeat=10.0,
        )
        store.save(original)
        store.touch_heartbeat(3, now=99.0)

        reloaded = store.load(3)
        assert reloaded is not None
        assert reloaded.issue_number == 3
        assert reloaded.item_id == "PVTI_XYZ"
        assert reloaded.session_id == "sess-3"
        assert reloaded.status == "running"
        assert reloaded.heartbeat == 99.0


# ---------------------------------------------------------------------------
# release_slot
# ---------------------------------------------------------------------------


class TestReleaseSlot:
    """``release_slot`` releases the slot marker AND the retry counters (15.1):
    it unlinks ``slots/ticket-<n>`` + every ``retries/<n>__*`` marker but leaves
    state / breadcrumb / queue / moves intact — the exhaustive teardown is
    :meth:`purge_ticket`."""

    def test_release_slot_unlinks_slot_and_retries_leaves_everything_else(
        self, tmp_path: Path
    ) -> None:
        """Slot + retries release: the slot marker and retry counters go, but
        state / queue / moves / breadcrumb all SURVIVE (the keep-marker invariant).

        The retries purge (15.1) is part of release_slot so a cancelled or
        clean-exit ticket leaves no stale fix-CI ledger.  The queue marker +
        rate-limit history still SURVIVE — those are the exhaustive purge's job.
        """
        store = FsStateStore(root=tmp_path)
        # Reserve a slot + seed every other per-ticket marker.
        assert store.reserve_slot(issue_number=10, cap=3) is True
        store.save(_make_state(issue_number=10))
        store.record_agent_advance(10, now=1000.0)
        store.enqueue_launch(10, {"item_id": "PVTI_10", "stage": "Impl", "enqueued_at": 1.0})
        store.record_move_for_item(10, now=1000.0)
        store.bump_retry(10, "onfail:Blocked")

        store.release_slot(10)

        # Slot marker is gone.
        assert not (store.root / "slots" / "ticket-10").exists()
        # Retry counters are gone (15.1: release_slot purges retries).
        assert list((store.root / "retries").glob("10__*")) == []
        # Everything else SURVIVES (the keep-marker invariant).
        assert store.load(10) is not None
        assert store.recent_agent_advance(10, now=1000.0) is True
        assert store.load_queued(10) is not None
        assert store.move_count_for_item_last_hour(10, now=1000.0) == 1

    def test_release_slot_idempotent_on_absent(self, tmp_path: Path) -> None:
        """Releasing a slot that was never reserved must not raise."""
        store = FsStateStore(root=tmp_path)
        store.release_slot(404)  # Must not raise.

    def test_release_slot_idempotent_double_release(self, tmp_path: Path) -> None:
        """A teardown/session-end race must not double-free the slot."""
        store = FsStateStore(root=tmp_path)
        assert store.reserve_slot(issue_number=11, cap=3) is True

        store.release_slot(11)
        store.release_slot(11)  # Second call must be harmless.

        assert not (store.root / "slots" / "ticket-11").exists()

    def test_release_slot_then_fresh_reserve_succeeds(self, tmp_path: Path) -> None:
        """After a slot-only release, a fresh reservation for the same issue
        succeeds — the slot was actually freed (the leak-safety contract)."""
        store = FsStateStore(root=tmp_path)
        assert store.reserve_slot(issue_number=12, cap=1) is True
        # The cap is full now — a different issue is refused.
        assert store.reserve_slot(issue_number=13, cap=1) is False

        store.release_slot(12)

        # The freed slot is reusable.
        assert store.reserve_slot(issue_number=13, cap=1) is True


class TestPurgeTicket:
    """``purge_ticket`` is the EXHAUSTIVE, idempotent teardown (13.7 PoC split):
    it removes state, slot, breadcrumb, queue, moves, AND retries."""

    def test_purges_state_and_slot(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        assert store.reserve_slot(issue_number=10, cap=3) is True
        store.save(_make_state(issue_number=10))

        store.purge_ticket(10)

        assert store.load(10) is None
        assert not (store.root / "slots" / "ticket-10").exists()

    def test_idempotent_on_absent(self, tmp_path: Path) -> None:
        """Purging a never-reserved ticket must not raise."""
        store = FsStateStore(root=tmp_path)
        store.purge_ticket(404)  # Must not raise.

    def test_idempotent_double_purge(self, tmp_path: Path) -> None:
        """A teardown/session-end race must not double-free."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=11))

        store.purge_ticket(11)
        store.purge_ticket(11)  # Second call must be harmless.

        assert store.load(11) is None

    def test_purge_removes_advance_breadcrumb(self, tmp_path: Path) -> None:
        """purge_ticket removes the advance breadcrumb (DESIGN §8.1.d).

        A cancelled ticket must leave no stale breadcrumb that a later
        session-end could misread as a clean advance.
        """
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=12))
        store.record_agent_advance(12, now=1000.0)
        assert (store.root / "advances" / "12").exists()

        store.purge_ticket(12)

        assert not (store.root / "advances" / "12").exists()
        assert store.recent_agent_advance(12, now=1000.0) is False

    def test_purge_breadcrumb_is_noop_when_already_cleared(self, tmp_path: Path) -> None:
        """The breadcrumb purge is unlink-if-exists / no-raise (idempotent).

        On a clean exit, session-end (8.1.f) already cleared the breadcrumb, so
        the subsequent ``purge_ticket`` must no-op silently — exercising the
        clean-exit path where the breadcrumb is already gone.
        """
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=13))
        store.record_agent_advance(13, now=1000.0)
        store.clear_agent_advance(13)  # the clean-exit path already cleared it
        assert not (store.root / "advances" / "13").exists()

        # Must not raise even though the breadcrumb is already absent.
        store.purge_ticket(13)

        assert store.load(13) is None


# ---------------------------------------------------------------------------
# list_running
# ---------------------------------------------------------------------------


class TestListRunning:
    """``list_running`` returns all persisted states with status ``"running"``."""

    def test_empty_when_nothing_persisted(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        assert store.list_running() == ()

    def test_filters_to_running_only(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        running_1 = _make_state(issue_number=1, status=TicketStatus.RUNNING)
        running_2 = _make_state(issue_number=2, status=TicketStatus.RUNNING)
        idle = _make_state(issue_number=3, status=TicketStatus.IDLE)

        store.save(running_1)
        store.save(running_2)
        store.save(idle)

        result = store.list_running()
        assert len(result) == 2
        assert {ts.issue_number for ts in result} == {1, 2}

    def test_includes_waiting(self, tmp_path: Path) -> None:
        """``list_running`` includes WAITING tickets (a LIVE status, phase-27 §B).

        A WAITING agent is alive but blocked on the human — the reaper must keep observing it (to
        restore it on a heartbeat refresh or reap it on a dead session), so it must appear in the
        live list alongside RUNNING. IDLE stays excluded.
        """
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        store.save(_make_state(issue_number=2, status=TicketStatus.WAITING))
        store.save(_make_state(issue_number=3, status=TicketStatus.IDLE))

        result = store.list_running()
        # RUNNING + WAITING are returned (both LIVE); IDLE is excluded.
        assert {ts.issue_number for ts in result} == {1, 2}
        assert {ts.status for ts in result} == {TicketStatus.RUNNING, TicketStatus.WAITING}

    def test_live_statuses_constant_is_running_and_waiting(self) -> None:
        """#3: ``LIVE_STATUSES`` is exactly {RUNNING, WAITING} — the one authoritative live set."""
        from kanbanmate.ports.store import LIVE_STATUSES

        assert LIVE_STATUSES == frozenset({TicketStatus.RUNNING, TicketStatus.WAITING})
        assert TicketStatus.IDLE not in LIVE_STATUSES

    def test_excludes_purged(self, tmp_path: Path) -> None:
        """A purged ticket must not show up in list_running.

        Slot-only ``release_slot`` leaves the state file (so the ticket would
        still list); only the exhaustive ``purge_ticket`` removes the state
        record, so it is the purge — not the slot release — that drops it.
        """
        store = FsStateStore(root=tmp_path)
        state = _make_state(issue_number=50, status=TicketStatus.RUNNING)
        store.save(state)
        store.purge_ticket(50)
        assert store.list_running() == ()

    def test_skips_corrupt_file(self, tmp_path: Path) -> None:
        """A non-JSON state file must not crash list_running (H1 safety-net)."""
        store = FsStateStore(root=tmp_path)
        # Write a valid state so there's something to find alongside the junk.
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        # Drop a corrupt file.
        (store.root / "state" / "corrupt.json").write_text("not json {{{")

        result = store.list_running()
        assert len(result) == 1
        assert result[0].issue_number == 1

    def test_corrupt_file_emits_named_stderr_diagnostic(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A corrupt state file is skipped WITH a named stderr breadcrumb (#17 PORT).

        The poison file must not abort the reaper sweep (the valid state is still returned)
        AND the operator gets the diagnostic naming the offending file."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        bad = store.root / "state" / "corrupt.json"
        bad.write_text("not json {{{")

        result = store.list_running()

        # The sweep survived the poison file (skip-don't-raise).
        assert len(result) == 1
        assert result[0].issue_number == 1
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert str(bad) in messages

    def test_skips_non_int_filename(self, tmp_path: Path) -> None:
        """A state file whose stem is not a valid int is silently skipped."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        (store.root / "state" / "nonsense.json").write_text(json.dumps({"issue_number": 99}))

        result = store.list_running()
        # The nonsense file has a non-int stem; list_running sorts by path
        # name so `nonsense.json` is visited but its glob yields it after
        # `1.json` — we just verify it doesn't crash.
        assert len(result) == 1
        assert result[0].issue_number == 1

    def test_skips_unknown_status_file_with_breadcrumb(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Valid JSON with an unknown status enum value is skipped WITH a named
        stderr breadcrumb (#12 / M3)."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        bad = store.root / "state" / "99.json"
        data = {
            "issue_number": 99,
            "item_id": "PVTI_099",
            "session_id": None,
            "status": "BOGUS",
            "heartbeat": 1234567890.0,
        }
        bad.write_text(json.dumps(data))

        result = store.list_running()

        # The sweep survived the schema-broken file (skip-don't-raise).
        assert len(result) == 1
        assert result[0].issue_number == 1
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert str(bad) in messages

    def test_skips_typeerror_file_with_breadcrumb(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Valid JSON + valid status but an extra field causing ``TicketState(**data)``
        TypeError is skipped WITH a named stderr breadcrumb (#12 / M3)."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        bad = store.root / "state" / "98.json"
        data = {
            "issue_number": 98,
            "item_id": "PVTI_098",
            "session_id": None,
            "status": "running",
            "heartbeat": 1234567890.0,
            "zzz_unknown": 1,  # extra field → TicketState(**data) raises TypeError
        }
        bad.write_text(json.dumps(data))

        result = store.list_running()

        assert len(result) == 1
        assert result[0].issue_number == 1
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert str(bad) in messages


# ---------------------------------------------------------------------------
# list_all
# ---------------------------------------------------------------------------


class TestListAll:
    """``list_all`` returns every persisted state regardless of status —
    the PoC ``_known_issues`` analogue."""

    def test_empty_when_nothing_persisted(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        assert store.list_all() == ()

    def test_returns_all_statuses(self, tmp_path: Path) -> None:
        """``list_all`` returns running AND non-running states; ``list_running``
        returns only the running ones — the contract split."""
        store = FsStateStore(root=tmp_path)
        running_1 = _make_state(issue_number=1, status=TicketStatus.RUNNING)
        idle = _make_state(issue_number=2, status=TicketStatus.IDLE)

        store.save(running_1)
        store.save(idle)

        all_result = store.list_all()
        assert len(all_result) == 2
        assert {ts.issue_number for ts in all_result} == {1, 2}
        assert {ts.status for ts in all_result} == {TicketStatus.RUNNING, TicketStatus.IDLE}

        # list_running returns only the running one (contract preserved).
        running_result = store.list_running()
        assert len(running_result) == 1
        assert running_result[0].issue_number == 1
        assert running_result[0].status == TicketStatus.RUNNING

    def test_skips_corrupt_file(self, tmp_path: Path) -> None:
        """A non-JSON state file must not crash list_all (H1 safety-net)."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        (store.root / "state" / "corrupt.json").write_text("not json {{{")

        result = store.list_all()
        assert len(result) == 1
        assert result[0].issue_number == 1

    def test_corrupt_file_emits_named_stderr_diagnostic(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``list_all`` skips a corrupt file WITH a named stderr breadcrumb (#17 PORT)."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        bad = store.root / "state" / "corrupt.json"
        bad.write_text("not json {{{")

        result = store.list_all()

        assert len(result) == 1
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert str(bad) in messages

    def test_skips_unknown_status_file_with_breadcrumb(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``list_all`` skips a valid-JSON-but-unknown-status file WITH a named
        stderr breadcrumb (#12 / M3)."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        bad = store.root / "state" / "99.json"
        data = {
            "issue_number": 99,
            "item_id": "PVTI_099",
            "session_id": None,
            "status": "BOGUS",
            "heartbeat": 1234567890.0,
        }
        bad.write_text(json.dumps(data))

        result = store.list_all()

        assert len(result) == 1
        assert result[0].issue_number == 1
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert str(bad) in messages

    def test_skips_typeerror_file_with_breadcrumb(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``list_all`` skips a file whose extra field causes ``TicketState(**data)``
        TypeError WITH a named stderr breadcrumb (#12 / M3)."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=1, status=TicketStatus.RUNNING))
        bad = store.root / "state" / "98.json"
        data = {
            "issue_number": 98,
            "item_id": "PVTI_098",
            "session_id": None,
            "status": "running",
            "heartbeat": 1234567890.0,
            "zzz_unknown": 1,  # extra field → TicketState(**data) raises TypeError
        }
        bad.write_text(json.dumps(data))

        result = store.list_all()

        assert len(result) == 1
        assert result[0].issue_number == 1
        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert str(bad) in messages


# ---------------------------------------------------------------------------
# Per-dispatch append-only audit log (dispatch.jsonl)
# ---------------------------------------------------------------------------


class TestAppendDispatch:
    """``append_dispatch`` writes one JSON line per dispatch to
    ``<root>/log/dispatch.jsonl``, append-only, stamped with a ``logged_at``
    float (port of the PoC ``audit.append_dispatch``)."""

    def test_first_call_creates_log_and_parses(self, tmp_path: Path) -> None:
        """The first call creates ``log/dispatch.jsonl``; the line parses as JSON
        with the caller's fields plus a float ``logged_at``."""
        store = FsStateStore(root=tmp_path)

        store.append_dispatch({"a": 1})

        log_path = store.root / "log" / "dispatch.jsonl"
        assert log_path.exists()
        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["a"] == 1
        # logged_at is stamped INSIDE the adapter (time.time()) — assert it is a
        # float (presence), not its exact value (the determinism split).
        assert isinstance(record["logged_at"], float)

    def test_second_call_appends_not_overwrites(self, tmp_path: Path) -> None:
        """A second call APPENDS a second line — the log is append-only."""
        store = FsStateStore(root=tmp_path)

        store.append_dispatch({"a": 1})
        store.append_dispatch({"a": 2})

        log_path = store.root / "log" / "dispatch.jsonl"
        lines = log_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["a"] == 1
        assert json.loads(lines[1])["a"] == 2

    def test_record_is_not_mutated(self, tmp_path: Path) -> None:
        """The caller's dict is shallow-copied — ``logged_at`` is not injected
        into the literal the caller passed (no mutation surprise)."""
        store = FsStateStore(root=tmp_path)
        record: dict[str, object] = {"a": 1}

        store.append_dispatch(record)

        assert "logged_at" not in record

    def test_ensure_ascii_false_roundtrips_non_ascii(self, tmp_path: Path) -> None:
        """A non-ASCII value round-trips intact (``ensure_ascii=False``)."""
        store = FsStateStore(root=tmp_path)

        store.append_dispatch({"repo": "owner/dépôt-café"})

        log_path = store.root / "log" / "dispatch.jsonl"
        raw = log_path.read_text(encoding="utf-8")
        # The non-ASCII chars are written verbatim (not \uXXXX-escaped).
        assert "dépôt-café" in raw
        record = json.loads(raw.splitlines()[0])
        assert record["repo"] == "owner/dépôt-café"


# ---------------------------------------------------------------------------
# Agent-advance breadcrumb (the ✅/⚠️ discriminator)
# ---------------------------------------------------------------------------


class TestAgentAdvanceBreadcrumb:
    """``record_agent_advance`` / ``recent_agent_advance`` / ``clear_agent_advance``
    implement the ✅/⚠️ discriminator, keyed by ISSUE number throughout."""

    def test_record_then_recent_within_ttl_is_true(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        store.record_agent_advance(42, now=1000.0)

        # Exactly at the boundary (_ADVANCE_TTL = 300 s) still counts as recent.
        assert store.recent_agent_advance(42, now=1000.0) is True
        assert store.recent_agent_advance(42, now=1299.0) is True
        assert store.recent_agent_advance(42, now=1300.0) is True

    def test_recent_is_false_past_ttl(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        store.record_agent_advance(42, now=1000.0)

        # One second past the 300 s window — no longer recent.
        assert store.recent_agent_advance(42, now=1301.0) is False

    def test_recent_is_false_when_absent(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        assert store.recent_agent_advance(99, now=1000.0) is False

    def test_clear_removes_breadcrumb(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        store.record_agent_advance(42, now=1000.0)
        assert store.recent_agent_advance(42, now=1000.0) is True

        store.clear_agent_advance(42)

        assert store.recent_agent_advance(42, now=1000.0) is False
        assert not (store.root / "advances" / "42").exists()

    def test_clear_is_noop_when_absent(self, tmp_path: Path) -> None:
        """Clearing a never-written (or already-consumed) breadcrumb must not raise."""
        store = FsStateStore(root=tmp_path)
        store.clear_agent_advance(404)  # Must not raise.

    def test_writer_and_readers_key_by_issue_number(self, tmp_path: Path) -> None:
        """The breadcrumb-keying INVARIANT (DESIGN §8.1.d): writer + readers all
        key by the ISSUE number — the marker file is ``advances/<issue>``, and a
        breadcrumb for one issue is invisible to a read keyed by a different issue."""
        store = FsStateStore(root=tmp_path)
        store.record_agent_advance(7, now=1000.0)

        # The marker file is keyed by the issue number, verbatim.
        assert (store.root / "advances" / "7").exists()
        # A read keyed by a DIFFERENT issue sees no breadcrumb (no cross-key bleed).
        assert store.recent_agent_advance(7, now=1000.0) is True
        assert store.recent_agent_advance(8, now=1000.0) is False
        # Clearing the other issue does not consume issue 7's breadcrumb.
        store.clear_agent_advance(8)
        assert store.recent_agent_advance(7, now=1000.0) is True

    def test_corrupt_breadcrumb_is_treated_as_absent(self, tmp_path: Path) -> None:
        """A malformed breadcrumb must not crash ``recent_agent_advance``."""
        store = FsStateStore(root=tmp_path)
        (store.root / "advances" / "5").write_text("{not json")
        assert store.recent_agent_advance(5, now=1000.0) is False


# ---------------------------------------------------------------------------
# Slot reservation (O_EXCL + flock)
# ---------------------------------------------------------------------------


class TestSlotReservation:
    """``reserve_slot`` atomically reserves a concurrency-cap slot."""

    def test_first_reservation_succeeds(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        assert store.reserve_slot(issue_number=10, cap=3) is True
        assert (store.root / "slots" / "ticket-10").exists()

    def test_idempotent_reservation(self, tmp_path: Path) -> None:
        """Reserving the same ticket twice returns True both times."""
        store = FsStateStore(root=tmp_path)
        assert store.reserve_slot(issue_number=10, cap=3) is True
        assert store.reserve_slot(issue_number=10, cap=3) is True

    def test_cap_exhausted_returns_false(self, tmp_path: Path) -> None:
        """When the cap is full, further reservations fail."""
        store = FsStateStore(root=tmp_path)
        # Fill cap=2 with tickets 1 and 2.
        assert store.reserve_slot(issue_number=1, cap=2) is True
        assert store.reserve_slot(issue_number=2, cap=2) is True
        # Ticket 3 must be refused.
        assert store.reserve_slot(issue_number=3, cap=2) is False

    def test_o_excl_prevents_double_create(self, tmp_path: Path) -> None:
        """Using ``os.open(O_CREAT | O_EXCL)`` on an already-existing marker
        must raise ``FileExistsError`` (defence-in-depth).

        This simulates what happens if two processes somehow race on the same
        ticket: the O_EXCL guarantees only one wins the creation."""
        store = FsStateStore(root=tmp_path)
        marker = store.root / "slots" / "ticket-99"

        # First creation succeeds.
        fd1 = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.close(fd1)

        # Second creation on the same path must fail.
        with pytest.raises(FileExistsError):
            os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)

    def test_slot_marker_removed_by_release(self, tmp_path: Path) -> None:
        """After release_slot, a new reservation for the same ticket succeeds."""
        store = FsStateStore(root=tmp_path)
        assert store.reserve_slot(issue_number=20, cap=3) is True
        store.release_slot(20)
        assert store.reserve_slot(issue_number=20, cap=3) is True


# ---------------------------------------------------------------------------
# Default root
# ---------------------------------------------------------------------------


class TestDefaultRoot:
    """When no root is provided, the store defaults to ``~/.kanban/``."""

    def test_default_root_is_expandeduser(self) -> None:
        """Verify the default root uses the user's home directory."""
        store = FsStateStore()
        expected = Path("~/.kanban/").expanduser().resolve()
        assert store.root.resolve() == expected


# ---------------------------------------------------------------------------
# Per-issue AUTO/bot move rate-limit (DESIGN §6 durable backstop)
# ---------------------------------------------------------------------------


class TestMoveRateLimit:
    """``record_move_for_item`` / ``move_count_for_item_last_hour`` implement the
    durable per-issue move rate-limit, keyed by ISSUE number throughout."""

    def test_record_then_count_within_window(self, tmp_path: Path) -> None:
        """Entries within _RATE_WINDOW (3600 s) are counted."""
        store = FsStateStore(root=tmp_path)
        store.record_move_for_item(42, now=1000.0)
        store.record_move_for_item(42, now=2000.0)
        store.record_move_for_item(42, now=3000.0)

        # All three entries are within 3600 s of now=4000.0
        assert store.move_count_for_item_last_hour(42, now=4000.0) == 3

    def test_drops_entries_older_than_rate_window(self, tmp_path: Path) -> None:
        """Entries past _RATE_WINDOW are excluded from the count."""
        store = FsStateStore(root=tmp_path)
        store.record_move_for_item(42, now=100.0)  # very old
        store.record_move_for_item(42, now=5000.0)

        # now=8601.0: the 100.0 entry is 8501 s old → excluded; 5000.0 is 3601 s
        # old → excluded (strictly > _RATE_WINDOW).  Both dropped.
        assert store.move_count_for_item_last_hour(42, now=8601.0) == 0
        # now=8600.0: 5000.0 is exactly 3600 s old → still counted (<= _RATE_WINDOW).
        assert store.move_count_for_item_last_hour(42, now=8600.0) == 1

    def test_count_zero_for_issue_with_no_history(self, tmp_path: Path) -> None:
        """An issue that has never been recorded returns 0."""
        store = FsStateStore(root=tmp_path)
        assert store.move_count_for_item_last_hour(99, now=1000.0) == 0

    def test_corrupt_moves_file_returns_zero(self, tmp_path: Path) -> None:
        """A corrupt moves/<issue>.json must return 0 (no raise) — the
        poison-file degrade pattern mirrors ``load``."""
        store = FsStateStore(root=tmp_path)
        (store.root / "moves" / "5.json").write_text("{not valid json [[")

        # Must not raise; degrades to 0 (a bad moves file cannot wedge the gate).
        assert store.move_count_for_item_last_hour(5, now=1000.0) == 0

    def test_corrupt_moves_file_emits_named_breadcrumb(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """#13: a corrupt moves/<issue>.json degrades to 0 but emits a NAMED breadcrumb.

        Before #13 the degrade was SILENT, so a poison rate-limit file under-counted the §6
        backstop invisibly (a runaway could slip the cap unseen). The degrade-to-0 is kept
        (the gate must not wedge), but the same ``_warn_corrupt_state`` breadcrumb the
        schema-corrupt state files use now names the offending file on stderr.
        """
        store = FsStateStore(root=tmp_path)
        moves_file = store.root / "moves" / "5.json"
        moves_file.write_text("{not valid json [[")

        assert store.move_count_for_item_last_hour(5, now=1000.0) == 0

        messages = " ".join(r.getMessage() for r in caplog.records)
        assert "skipping corrupt state file" in messages
        assert "5.json" in messages  # the offending file is NAMED

    def test_record_move_overwrites_corrupt_with_new_entry(self, tmp_path: Path) -> None:
        """A corrupt moves file is replaced when a new move is recorded
        (record_move_for_item reads-or-[] then appends)."""
        store = FsStateStore(root=tmp_path)
        (store.root / "moves" / "5.json").write_text("{corrupt")

        store.record_move_for_item(5, now=1000.0)

        # The corrupt history is replaced; the new entry is recorded.
        assert store.move_count_for_item_last_hour(5, now=1000.0) == 1

    def test_history_is_issue_keyed_not_node_keyed(self, tmp_path: Path) -> None:
        """The history file is ``moves/<issue>.json`` — issue-keyed, NOT the
        PoC's ``moves/item_<node>.json`` (boundary 2 divergence)."""
        store = FsStateStore(root=tmp_path)
        store.record_move_for_item(42, now=1000.0)

        # The history is keyed by issue number.
        assert (store.root / "moves" / "42.json").exists()
        # The old PoC path (keyed by content node id) must NOT be created.
        assert not list((store.root / "moves").glob("item_*.json"))

    def test_history_survives_fresh_store_instance(self, tmp_path: Path) -> None:
        """The rate-limit history is DURABLE: a fresh FsStateStore over the same
        root sees the moves recorded by a previous instance (the whole point of
        §6 on-disk persistence — the cap must survive a daemon restart)."""
        store1 = FsStateStore(root=tmp_path)
        store1.record_move_for_item(42, now=1000.0)
        store1.record_move_for_item(42, now=2000.0)

        # A brand-new instance over the same root.
        store2 = FsStateStore(root=tmp_path)
        assert store2.move_count_for_item_last_hour(42, now=3000.0) == 2

    def test_different_issues_have_independent_histories(self, tmp_path: Path) -> None:
        """Move history for issue 7 must not bleed into issue 8."""
        store = FsStateStore(root=tmp_path)
        store.record_move_for_item(7, now=1000.0)
        store.record_move_for_item(7, now=2000.0)
        store.record_move_for_item(8, now=1500.0)

        assert store.move_count_for_item_last_hour(7, now=3000.0) == 2
        assert store.move_count_for_item_last_hour(8, now=3000.0) == 1


# ---------------------------------------------------------------------------
# Per-(issue,key) fix-CI retry counter (DESIGN §6 bounded loop cap, N=2)
# ---------------------------------------------------------------------------


class TestFixCIRetryCounter:
    """``bump_retry`` / ``reset_retry`` implement the durable per-(issue,key)
    fix-CI retry counter, keyed by ISSUE number throughout."""

    def test_bump_retry_returns_1_then_2_then_3(self, tmp_path: Path) -> None:
        """Each call to bump_retry increments and returns the new count."""
        store = FsStateStore(root=tmp_path)

        assert store.bump_retry(42, "onfail:Blocked") == 1
        assert store.bump_retry(42, "onfail:Blocked") == 2
        assert store.bump_retry(42, "onfail:Blocked") == 3

    def test_reset_retry_unlinks_then_next_bump_returns_1(self, tmp_path: Path) -> None:
        """After reset (unlink), the counter starts fresh — next bump returns 1."""
        store = FsStateStore(root=tmp_path)

        store.bump_retry(42, "onfail:Blocked")
        store.bump_retry(42, "onfail:Blocked")
        assert store.bump_retry(42, "onfail:Blocked") == 3

        store.reset_retry(42, "onfail:Blocked")
        # The marker was unlinked; next bump returns 1 (absent file → count 0 + 1).
        assert store.bump_retry(42, "onfail:Blocked") == 1

    def test_distinct_keys_keep_independent_counters(self, tmp_path: Path) -> None:
        """Two different keys on the same issue have separate counters (per-loop
        budget keyed by destination — port of OLD's ``onfail:<to>`` semantics)."""
        store = FsStateStore(root=tmp_path)

        # Bump key A three times, key B once.
        assert store.bump_retry(42, "onfail:Blocked") == 1
        assert store.bump_retry(42, "onfail:Blocked") == 2
        assert store.bump_retry(42, "onfail:Deploy") == 1

        # Key A is still at 2.
        assert store.bump_retry(42, "onfail:Blocked") == 3
        # Key B is still independent.
        assert store.bump_retry(42, "onfail:Deploy") == 2

        # Reset key A; key B is untouched.
        store.reset_retry(42, "onfail:Blocked")
        assert store.bump_retry(42, "onfail:Blocked") == 1
        assert store.bump_retry(42, "onfail:Deploy") == 3

    def test_key_with_space_is_sanitised_no_dir_escape(self, tmp_path: Path) -> None:
        """A key containing a space is sanitised to a single file under
        ``retries/`` — the marker path stays confined, no directory escape."""
        store = FsStateStore(root=tmp_path)

        store.bump_retry(42, "PR Ready")
        store.bump_retry(42, "PR Ready")

        # The counter is stored under retries/ — the space was sanitised.
        retries_dir = store.root / "retries"
        markers = list(retries_dir.iterdir())
        assert len(markers) == 1
        marker_name = markers[0].name
        # Must be under retries/, not escaped to parent.
        assert ".." not in marker_name
        assert "/" not in marker_name
        # Must contain the issue number.
        assert marker_name.startswith("42__")
        # The space in "PR Ready" was replaced (not kept as a path separator).
        assert " " not in marker_name

    def test_key_with_slash_is_sanitised_no_dir_escape(self, tmp_path: Path) -> None:
        """A key containing a slash is sanitised — must not create a subdirectory."""
        store = FsStateStore(root=tmp_path)

        store.bump_retry(99, "deploy/prod")
        store.bump_retry(99, "deploy/prod")

        retries_dir = store.root / "retries"
        # No subdirectory was created — the slash was replaced.
        assert retries_dir.is_dir()
        markers = list(retries_dir.iterdir())
        assert len(markers) == 1
        marker_name = markers[0].name
        assert "/" not in marker_name
        assert "\\" not in marker_name
        assert marker_name.startswith("99__")

    def test_empty_key_defaults_to_underscore(self, tmp_path: Path) -> None:
        """An empty key defaults to ``"_"`` — the same fallback the PoC used
        via ``_INFLIGHT_SAFE``."""
        store = FsStateStore(root=tmp_path)

        store.bump_retry(42, "")
        store.bump_retry(42, "")

        retries_dir = store.root / "retries"
        markers = list(retries_dir.iterdir())
        assert len(markers) == 1
        # The safe key part is "_" (empty → fallback).
        assert markers[0].name == "42___"

    def test_reset_retry_absent_is_noop(self, tmp_path: Path) -> None:
        """``reset_retry`` on a never-bumped key is a no-op — no raise, no file created."""
        store = FsStateStore(root=tmp_path)

        # Must not raise on a never-written marker.
        store.reset_retry(42, "onfail:NeverSeen")

        # No file was created.
        assert not list((store.root / "retries").glob("42__*"))

    def test_reset_retry_absent_after_already_reset_is_noop(self, tmp_path: Path) -> None:
        """``reset_retry`` on an already-reset (unlinked) marker is a no-op —
        double-reset never raises."""
        store = FsStateStore(root=tmp_path)
        store.bump_retry(42, "onfail:Blocked")
        store.reset_retry(42, "onfail:Blocked")

        # Second reset — must not raise (marker already gone).
        store.reset_retry(42, "onfail:Blocked")

        # Still gone.
        assert not list((store.root / "retries").glob("42__*"))

    def test_two_ledgers_do_not_collide(self, tmp_path: Path) -> None:
        """The bare ``TicketState.retries`` field and the ``(issue, key)`` retry
        ledger are INDEPENDENT — bumping one does not affect the other.

        The reaper retry (15.2) rides on ``TicketState.retries`` (refreshed via
        ``save``); the fix-CI cap (15.7) rides on the ``retries/<issue>__<key>``
        ledger via ``bump_retry``/``reset_retry``.  Two distinct counters, never
        conflated — matching the PoC's separation of ``data["retries"]`` vs
        ``bump_retry``.
        """
        store = FsStateStore(root=tmp_path)

        # Save a state with retries=0 (the default).
        state = _make_state(issue_number=42)
        store.save(state)

        # Bump the ledger for "onfail:PR Ready" — the TicketState.retries field is untouched.
        assert store.bump_retry(42, "onfail:PR Ready") == 1
        assert store.bump_retry(42, "onfail:PR Ready") == 2

        loaded = store.load(42)
        assert loaded is not None
        # The bare retries field is STILL 0 — the ledger bump did not touch it.
        assert loaded.retries == 0

        # Now bump the bare field via save — the ledger is untouched.
        store.save(_make_state(issue_number=42, retries=1))
        loaded2 = store.load(42)
        assert loaded2 is not None
        assert loaded2.retries == 1

        # The ledger counter is still at 2 (independent).
        assert store.bump_retry(42, "onfail:PR Ready") == 3

        # Reset the ledger — the bare field is STILL 1.
        store.reset_retry(42, "onfail:PR Ready")
        loaded3 = store.load(42)
        assert loaded3 is not None
        assert loaded3.retries == 1

    def test_counter_survives_fresh_store_instance(self, tmp_path: Path) -> None:
        """The retry counter is DURABLE: a fresh FsStateStore over the same
        root sees the counter persisted by a previous instance."""
        store1 = FsStateStore(root=tmp_path)
        store1.bump_retry(42, "onfail:Blocked")
        store1.bump_retry(42, "onfail:Blocked")

        # A brand-new instance over the same root.
        store2 = FsStateStore(root=tmp_path)
        assert store2.bump_retry(42, "onfail:Blocked") == 3

        # Reset via store2 persists.
        store2.reset_retry(42, "onfail:Blocked")
        store3 = FsStateStore(root=tmp_path)
        assert store3.bump_retry(42, "onfail:Blocked") == 1


# ---------------------------------------------------------------------------
# Queue persistence (DESIGN §7 concurrency-cap queue)
# ---------------------------------------------------------------------------


class TestQueuePersistence:
    """``enqueue_launch`` / ``dequeue_pending`` / ``load_queued`` /
    ``clear_queued`` implement the durable queue for capped launches."""

    def test_enqueue_then_dequeue_returns_issue(self, tmp_path: Path) -> None:
        """After enqueuing a ticket, ``dequeue_pending`` returns its issue."""
        store = FsStateStore(root=tmp_path)
        store.enqueue_launch(
            42, {"item_id": "PVTI_001", "stage": "Implement", "enqueued_at": 1000.0}
        )

        pending = store.dequeue_pending()
        assert pending == (42,)

    def test_load_queued_round_trips_payload(self, tmp_path: Path) -> None:
        """The enqueued payload is recovered verbatim by ``load_queued``."""
        store = FsStateStore(root=tmp_path)
        payload = {"item_id": "PVTI_XYZ", "stage": "Review", "enqueued_at": 2000.0}
        store.enqueue_launch(7, payload)

        loaded = store.load_queued(7)
        assert loaded == payload

    def test_load_queued_returns_none_when_absent(self, tmp_path: Path) -> None:
        """A never-enqueued ticket returns ``None`` (no crash)."""
        store = FsStateStore(root=tmp_path)
        assert store.load_queued(404) is None

    def test_load_queued_returns_none_when_corrupt(self, tmp_path: Path) -> None:
        """A corrupt queue marker returns ``None`` — the poison-file degrade."""
        store = FsStateStore(root=tmp_path)
        (store.root / "queue").mkdir(parents=True, exist_ok=True)
        (store.root / "queue" / "ticket-5").write_text("{not json")

        assert store.load_queued(5) is None

    def test_clear_queued_removes_marker(self, tmp_path: Path) -> None:
        """After ``clear_queued``, the ticket is no longer pending and its
        payload is gone."""
        store = FsStateStore(root=tmp_path)
        store.enqueue_launch(
            42, {"item_id": "PVTI_001", "stage": "Implement", "enqueued_at": 1000.0}
        )

        store.clear_queued(42)

        assert store.dequeue_pending() == ()
        assert store.load_queued(42) is None

    def test_clear_queued_noop_when_absent(self, tmp_path: Path) -> None:
        """Clearing a never-enqueued ticket must not raise."""
        store = FsStateStore(root=tmp_path)
        store.clear_queued(404)  # Must not raise.

    def test_dequeue_pending_returns_sorted(self, tmp_path: Path) -> None:
        """``dequeue_pending`` returns issue numbers sorted ascending."""
        store = FsStateStore(root=tmp_path)
        store.enqueue_launch(10, {"item_id": "a", "stage": "Plan", "enqueued_at": 1.0})
        store.enqueue_launch(5, {"item_id": "b", "stage": "Plan", "enqueued_at": 1.0})
        store.enqueue_launch(20, {"item_id": "c", "stage": "Plan", "enqueued_at": 1.0})

        pending = store.dequeue_pending()
        # Sorted lexicographically by path name, mirroring OLD's
        # ``sorted(store.queue_dir().glob("ticket-*"))`` (Path objects).
        assert pending == (10, 20, 5)

    def test_dequeue_pending_skips_non_ticket_int_file(self, tmp_path: Path) -> None:
        """A file under ``queue/`` whose name does not parse to an int is
        skipped — port of OLD's ``try/except (IndexError, ValueError)``."""
        store = FsStateStore(root=tmp_path)
        store.enqueue_launch(
            42, {"item_id": "PVTI_001", "stage": "Implement", "enqueued_at": 1000.0}
        )
        # Drop a stray file that does not conform to the ``ticket-<int>`` naming.
        (store.root / "queue" / "ticket-notanumber").write_text("{}")
        (store.root / "queue" / "ticket-").write_text("{}")

        pending = store.dequeue_pending()
        assert pending == (42,)

    def test_queue_dir_created_by_init(self, tmp_path: Path) -> None:
        """The ``queue/`` directory is created on initialisation (like the
        other marker dirs)."""
        store = FsStateStore(root=tmp_path)
        assert (store.root / "queue").is_dir()

    def test_dequeue_pending_empty_when_no_queue(self, tmp_path: Path) -> None:
        """When no tickets are enqueued, ``dequeue_pending`` returns an empty
        tuple."""
        store = FsStateStore(root=tmp_path)
        assert store.dequeue_pending() == ()


# ---------------------------------------------------------------------------
# release_slot widened purge (port of PoC purge_ticket)
# ---------------------------------------------------------------------------


class TestPurgeTicketExhaustive:
    """``purge_ticket`` performs the exhaustive purge — queue, moves, and
    retries markers are removed in addition to state/slots/advances."""

    def test_purge_removes_queue_marker(self, tmp_path: Path) -> None:
        """``purge_ticket`` removes the queue marker for the issue."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=42))
        store.enqueue_launch(
            42, {"item_id": "PVTI_001", "stage": "Implement", "enqueued_at": 1000.0}
        )
        assert (store.root / "queue" / "ticket-42").exists()

        store.purge_ticket(42)

        assert not (store.root / "queue" / "ticket-42").exists()
        assert store.load_queued(42) is None

    def test_purge_removes_moves_history(self, tmp_path: Path) -> None:
        """``purge_ticket`` removes the per-issue move rate-limit history."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=42))
        store.record_move_for_item(42, now=1000.0)
        store.record_move_for_item(42, now=2000.0)
        assert (store.root / "moves" / "42.json").exists()

        store.purge_ticket(42)

        assert not (store.root / "moves" / "42.json").exists()
        assert store.move_count_for_item_last_hour(42, now=3000.0) == 0

    def test_purge_removes_retries_counters(self, tmp_path: Path) -> None:
        """``purge_ticket`` removes every per-(issue, key) retry counter via
        glob."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=42))
        store.bump_retry(42, "onfail:Blocked")
        store.bump_retry(42, "onfail:Blocked")
        store.bump_retry(42, "onfail:Deploy")
        # Verify the retry files exist.
        retries_dir = store.root / "retries"
        assert len(list(retries_dir.iterdir())) >= 1

        store.purge_ticket(42)

        # All retries for issue 42 are gone.
        remaining = list(retries_dir.glob("42__*"))
        assert remaining == []

    def test_purge_is_idempotent(self, tmp_path: Path) -> None:
        """A second ``purge_ticket`` after a full purge must not raise —
        the exhaustive teardown is idempotent (port of OLD's ``purge_ticket``
        contract)."""
        store = FsStateStore(root=tmp_path)
        store.save(_make_state(issue_number=42))
        store.enqueue_launch(
            42, {"item_id": "PVTI_001", "stage": "Implement", "enqueued_at": 1000.0}
        )
        store.record_move_for_item(42, now=1000.0)
        store.bump_retry(42, "onfail:Blocked")

        store.purge_ticket(42)
        # Second call must be harmless — no raise.
        store.purge_ticket(42)

        # All markers still gone.
        assert store.load(42) is None
        assert not (store.root / "slots" / "ticket-42").exists()
        assert not (store.root / "queue" / "ticket-42").exists()
        assert not (store.root / "moves" / "42.json").exists()
        assert list((store.root / "retries").glob("42__*")) == []

    def test_purge_does_not_collaterally_delete_sibling_retries(self, tmp_path: Path) -> None:
        """A ``retries/<n>__*`` glob must not collaterally delete a sibling
        issue's retry counters — over-match defence ported from OLD's
        ``purge_ticket`` (``glob.escape`` on the interpolated issue)."""
        store = FsStateStore(root=tmp_path)

        # Seed retry counters for issue 7.
        store.bump_retry(7, "onfail:Blocked")
        store.bump_retry(7, "onfail:Blocked")
        # Seed a retry counter for issue 70 — a sibling whose name would
        # match a naive ``f"{issue}__*"`` glob if ``glob.escape`` were
        # omitted (the ``7`` in ``7__*`` matches the ``7`` at the start of
        # ``70__*`` only when ``7`` is treated as a glob — but since issue
        # numbers are ints, the pattern is always ``7__*`` and ``70__*``
        # does NOT match because ``0`` ≠ ``_``; the defence is present for
        # the principle and for any future non-int keying).
        store.bump_retry(70, "onfail:Blocked")

        # Also seed retries for issue 7 with a second key.
        store.bump_retry(7, "onfail:Deploy")

        retries_dir = store.root / "retries"
        assert len(list(retries_dir.glob("7__*"))) >= 2  # at least 2 files for issue 7
        assert len(list(retries_dir.glob("70__*"))) == 1  # 1 file for issue 70

        # Save state so purge_ticket can unlink it.
        store.save(_make_state(issue_number=7))

        store.purge_ticket(7)

        # All retries for issue 7 are gone.
        assert list(retries_dir.glob("7__*")) == []
        # Issue 70's retry counter SURVIVES.
        remaining_70 = list(retries_dir.glob("70__*"))
        assert len(remaining_70) == 1
        # The surviving counter is still functional.
        assert store.bump_retry(70, "onfail:Blocked") == 2


class TestScriptOutput:
    """The per-issue check-script output marker (15.6/15.7 ``{{script_output}}`` sink)."""

    def test_save_then_load_round_trips_output(self, tmp_path: Path) -> None:
        """A saved script output reads back verbatim via :meth:`load_script_output`."""
        store = FsStateStore(root=tmp_path)
        output = "CI failed: 3 tests red\n  test_foo\n  test_bar\n"
        store.save_script_output(7, output)
        assert store.load_script_output(7) == output

    def test_load_absent_returns_empty_string(self, tmp_path: Path) -> None:
        """An issue that never stashed output reads back ``""`` (absent marker)."""
        store = FsStateStore(root=tmp_path)
        assert store.load_script_output(99) == ""

    def test_save_empty_clears_to_empty_string(self, tmp_path: Path) -> None:
        """Writing ``""`` clears a prior failure output (the success-path clear, 15.6)."""
        store = FsStateStore(root=tmp_path)
        store.save_script_output(7, "stale failure dump")
        store.save_script_output(7, "")  # the success path clears it
        assert store.load_script_output(7) == ""

    def test_save_overwrites_prior_output(self, tmp_path: Path) -> None:
        """A second save replaces the first (atomic overwrite, no append)."""
        store = FsStateStore(root=tmp_path)
        store.save_script_output(7, "first")
        store.save_script_output(7, "second")
        assert store.load_script_output(7) == "second"

    def test_save_is_atomic_no_temp_file_left(self, tmp_path: Path) -> None:
        """The atomic temp-file is renamed away — no ``.tmp`` residue under ``script_output/``."""
        store = FsStateStore(root=tmp_path)
        store.save_script_output(7, "x")
        leftovers = list((store.root / "script_output").glob("*.tmp"))
        assert leftovers == []

    def test_load_corrupt_unreadable_degrades_to_empty(self, tmp_path: Path) -> None:
        """An unreadable marker degrades to ``""`` (poison-file degrade, never raises)."""
        store = FsStateStore(root=tmp_path)
        # Make the marker a DIRECTORY so ``read_text`` raises OSError → degrade to "".
        marker = store.root / "script_output" / "7"
        marker.mkdir(parents=True)
        assert store.load_script_output(7) == ""

    def test_issue_keyed_independent_markers(self, tmp_path: Path) -> None:
        """Two issues keep independent script-output markers (issue-keyed)."""
        store = FsStateStore(root=tmp_path)
        store.save_script_output(7, "seven")
        store.save_script_output(8, "eight")
        assert store.load_script_output(7) == "seven"
        assert store.load_script_output(8) == "eight"


class TestStatusUpdateState:
    """Rolling project status-update state: id, body hash, and the events ring (phase-24 §24.2)."""

    def test_update_id_round_trips(self, tmp_path: Path) -> None:
        """The rolling status-update node id round-trips through set/get."""
        store = FsStateStore(root=tmp_path)
        assert store.get_status_update_id() is None  # first contact
        store.set_status_update_id("PVTSU_123")
        assert store.get_status_update_id() == "PVTSU_123"

    def test_update_id_clear_with_none(self, tmp_path: Path) -> None:
        """Setting the id to ``None`` clears the marker (stale-id re-create path)."""
        store = FsStateStore(root=tmp_path)
        store.set_status_update_id("PVTSU_123")
        store.set_status_update_id(None)
        assert store.get_status_update_id() is None

    def test_update_id_atomic_no_temp_residue(self, tmp_path: Path) -> None:
        """The id write is atomic — no ``.tmp`` residue under ``status/``."""
        store = FsStateStore(root=tmp_path)
        store.set_status_update_id("PVTSU_123")
        assert list((store.root / "status").glob("*.tmp")) == []

    def test_body_hash_round_trips(self, tmp_path: Path) -> None:
        """The last-posted body hash round-trips through set/get."""
        store = FsStateStore(root=tmp_path)
        assert store.get_status_body_hash() is None
        store.set_status_body_hash("deadbeef")
        assert store.get_status_body_hash() == "deadbeef"

    def test_body_hash_clear_with_none(self, tmp_path: Path) -> None:
        """Setting the body hash to ``None`` clears the marker."""
        store = FsStateStore(root=tmp_path)
        store.set_status_body_hash("deadbeef")
        store.set_status_body_hash(None)
        assert store.get_status_body_hash() is None

    def test_project_id_round_trips(self, tmp_path: Path) -> None:
        """The status-state project binding round-trips through set/get (phase-33)."""
        store = FsStateStore(root=tmp_path)
        assert store.get_status_project_id() is None  # never bound → fresh post
        store.set_status_project_id("PVT_proj")
        assert store.get_status_project_id() == "PVT_proj"

    def test_project_id_clear_with_none(self, tmp_path: Path) -> None:
        """Setting the project binding to ``None`` clears the marker (phase-33)."""
        store = FsStateStore(root=tmp_path)
        store.set_status_project_id("PVT_proj")
        store.set_status_project_id(None)
        assert store.get_status_project_id() is None

    def test_last_enum_round_trips(self, tmp_path: Path) -> None:
        """The last-posted status enum round-trips through set/get (re-create-on-change)."""
        store = FsStateStore(root=tmp_path)
        assert store.get_status_last_enum() is None  # never posted → first render posts
        store.set_status_last_enum("OFF_TRACK")
        assert store.get_status_last_enum() == "OFF_TRACK"
        store.set_status_last_enum("ON_TRACK")
        assert store.get_status_last_enum() == "ON_TRACK"

    def test_last_enum_clear_with_none(self, tmp_path: Path) -> None:
        """Setting the last-posted enum to ``None`` clears the marker (project rebind)."""
        store = FsStateStore(root=tmp_path)
        store.set_status_last_enum("ON_TRACK")
        store.set_status_last_enum(None)
        assert store.get_status_last_enum() is None

    def test_events_ring_round_trips_oldest_first(self, tmp_path: Path) -> None:
        """The events ring round-trips in append (oldest-first) order."""
        store = FsStateStore(root=tmp_path)
        assert store.read_status_events() == ()  # empty ring
        store.append_status_event({"ts": 1.0, "kind": "launch", "issue": 7, "detail": "a"})
        store.append_status_event({"ts": 2.0, "kind": "teardown", "issue": 7, "detail": "b"})
        events = store.read_status_events()
        assert [e["kind"] for e in events] == ["launch", "teardown"]
        assert events[0]["issue"] == 7 and events[0]["detail"] == "a"

    def test_events_ring_caps_at_ten_newest(self, tmp_path: Path) -> None:
        """Appending past the cap drops the oldest, keeping the 10 NEWEST events."""
        store = FsStateStore(root=tmp_path)
        # Append 12 events; only the last 10 (ts 3..12) must survive, oldest-first.
        for i in range(1, 13):
            store.append_status_event({"ts": float(i), "kind": "auto", "issue": i, "detail": ""})
        events = store.read_status_events()
        assert len(events) == 10
        assert [e["ts"] for e in events] == [float(i) for i in range(3, 13)]
        # The two oldest (ts 1, 2) were evicted.
        assert all(e["ts"] not in (1.0, 2.0) for e in events)

    def test_events_ring_atomic_no_temp_residue(self, tmp_path: Path) -> None:
        """The events-ring write is atomic — no ``.tmp`` residue under ``status/``."""
        store = FsStateStore(root=tmp_path)
        store.append_status_event({"ts": 1.0, "kind": "launch", "issue": 1, "detail": ""})
        assert list((store.root / "status").glob("*.tmp")) == []

    def test_events_ring_corrupt_degrades_to_empty(self, tmp_path: Path) -> None:
        """A corrupt ring file degrades to an empty tuple (never raises)."""
        store = FsStateStore(root=tmp_path)
        (store.root / "status" / "events.json").write_text("{not json")
        assert store.read_status_events() == ()

    def test_events_ring_non_list_degrades_to_empty(self, tmp_path: Path) -> None:
        """A ring file that is valid JSON but not a list degrades to empty."""
        store = FsStateStore(root=tmp_path)
        (store.root / "status" / "events.json").write_text(json.dumps({"oops": True}))
        assert store.read_status_events() == ()

    def test_serialisation_is_json_on_disk(self, tmp_path: Path) -> None:
        """The ring is persisted as a JSON list on disk (reused store serialisation)."""
        store = FsStateStore(root=tmp_path)
        store.append_status_event({"ts": 1.0, "kind": "block", "issue": None, "detail": "x"})
        on_disk = json.loads((store.root / "status" / "events.json").read_text())
        assert isinstance(on_disk, list)
        assert on_disk[0]["kind"] == "block" and on_disk[0]["issue"] is None

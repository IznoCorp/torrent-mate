"""Tests for the per-card Health field reporter (:mod:`kanbanmate.app.health_reporter`).

``apply_health`` is the tick's fail-soft Health step: it ensures the custom 'Health'
single-select field (lazily, store-cached), computes each card's Health (PURE), and writes
ONLY the changed cards — swallowing every error (observability, never a launch blocker).

These tests drive ``apply_health`` against a REAL ``FsStateStore`` (so the on-change +
cache + rebind persistence is exercised end to end) and a recording fake health-reporter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from kanbanmate.adapters.github.types import HealthField
from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.app.actions import Deps
from kanbanmate.app.health_reporter import apply_health
from kanbanmate.app.tick import TickConfig
from kanbanmate.core.columns import load_columns
from kanbanmate.core.domain import BoardSnapshot, Ticket
from kanbanmate.core.transitions_defaults import default_transition_config
from kanbanmate.ports.store import TicketState, TicketStatus

PROJECT = "PVT_PROJECT"

# A minimal column model; ``apply_health`` reads only blocked_column/done_column off config.
_COLUMNS_YAML = """
columns:
  - key: InProgress
    name: In Progress
"""

# The 5-option Health field a real reporter would resolve.
_HEALTH_OPTIONS = {n: n.lower() for n in ("INACTIVE", "WAITING", "ACTIVE", "BLOCKED", "COMPLETE")}


def _config() -> TickConfig:
    """Build a TickConfig with the default Blocked/Done column keys."""
    return TickConfig(
        columns=load_columns(_COLUMNS_YAML),
        transitions=default_transition_config(),
        blocked_column="Blocked",
        done_column="Done",
    )


@dataclass
class _FakeHealthReporter:
    """A recording :class:`~kanbanmate.ports.board.ProjectHealthReporter`."""

    ensured: list[str] = field(default_factory=list)
    set_calls: list[tuple[str, str]] = field(default_factory=list)
    ensure_raises: bool = False
    set_raises: bool = False
    field_id: str = "HEALTH_F"
    options: dict[str, str] = field(default_factory=lambda: dict(_HEALTH_OPTIONS))

    def ensure_health_field(self, project_id: str) -> HealthField:
        """Record the ensure call and return a fully-populated field."""
        self.ensured.append(project_id)
        if self.ensure_raises:
            raise RuntimeError("simulated ensure failure")
        return HealthField(field_id=self.field_id, options=dict(self.options))

    def set_item_health(self, item_id: str, value: str) -> None:
        """Record the set call."""
        self.set_calls.append((item_id, value))
        if self.set_raises:
            raise RuntimeError("simulated set failure")


def _deps(store: FsStateStore, reporter: _FakeHealthReporter, *, project_id: str = PROJECT) -> Deps:
    """Assemble a Deps wiring the health fakes (other ports unused by apply_health)."""
    placeholder = object()
    return Deps(
        board_writer=placeholder,  # type: ignore[arg-type]
        board_reader=placeholder,  # type: ignore[arg-type]
        workspace=placeholder,  # type: ignore[arg-type]
        sessions=placeholder,  # type: ignore[arg-type]
        store=store,
        clock=placeholder,  # type: ignore[arg-type]
        pull_requests=placeholder,  # type: ignore[arg-type]
        health_reporter=reporter,
        project_id=project_id,
    )


def _ticket(issue: int, item_id: str, column: str) -> Ticket:
    """Build a board Ticket."""
    return Ticket(item_id=item_id, issue_number=issue, title=f"#{issue}", column_key=column)


def _snapshot(*tickets: Ticket) -> BoardSnapshot:
    """Wrap tickets in a BoardSnapshot."""
    return BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)


def _running(issue: int, status: TicketStatus) -> TicketState:
    """Build a live TicketState (the running view)."""
    return TicketState(
        issue_number=issue, item_id=f"PVTI_{issue}", session_id="s", status=status, heartbeat=1.0
    )


# ---------------------------------------------------------------------------
# Snapshot-None early return
# ---------------------------------------------------------------------------


def test_snapshot_none_is_a_noop(tmp_path: Path) -> None:
    """No snapshot this tick → early return, zero GitHub calls."""
    store = FsStateStore(tmp_path)
    reporter = _FakeHealthReporter()
    apply_health(_deps(store, reporter), _config(), running=(), snapshot=None, now=1.0)
    assert reporter.ensured == []
    assert reporter.set_calls == []


# ---------------------------------------------------------------------------
# Idempotent provisioning + cache
# ---------------------------------------------------------------------------


def test_first_call_ensures_and_persists_field(tmp_path: Path) -> None:
    """First call ensures the field and persists its id + options in the store."""
    store = FsStateStore(tmp_path)
    reporter = _FakeHealthReporter()
    snap = _snapshot(_ticket(1, "PVTI_1", "Backlog"))
    apply_health(_deps(store, reporter), _config(), running=(), snapshot=snap, now=1.0)
    assert reporter.ensured == [PROJECT]
    assert store.get_health_field_id() == "HEALTH_F"
    assert store.get_health_options() == _HEALTH_OPTIONS


def test_second_call_uses_store_cache_no_reensure(tmp_path: Path) -> None:
    """A second call (store cache populated) does NOT call ensure_health_field again."""
    store = FsStateStore(tmp_path)
    reporter = _FakeHealthReporter()
    snap = _snapshot(_ticket(1, "PVTI_1", "Backlog"))
    deps = _deps(store, reporter)
    apply_health(deps, _config(), running=(), snapshot=snap, now=1.0)
    apply_health(deps, _config(), running=(), snapshot=snap, now=2.0)
    # ensure_health_field was called exactly once (the second used the store cache).
    assert reporter.ensured == [PROJECT]


# ---------------------------------------------------------------------------
# On-change dedup
# ---------------------------------------------------------------------------


def test_on_change_dedup_skips_unchanged_card(tmp_path: Path) -> None:
    """A card whose computed value equals the last-written one is NOT re-written."""
    store = FsStateStore(tmp_path)
    reporter = _FakeHealthReporter()
    snap = _snapshot(_ticket(1, "PVTI_1", "Done"))  # no agent + Done → COMPLETE
    deps = _deps(store, reporter)
    apply_health(deps, _config(), running=(), snapshot=snap, now=1.0)
    assert reporter.set_calls == [("PVTI_1", "COMPLETE")]
    # Second identical tick → no second write.
    apply_health(deps, _config(), running=(), snapshot=snap, now=2.0)
    assert reporter.set_calls == [("PVTI_1", "COMPLETE")]


def test_changed_value_writes_and_persists(tmp_path: Path) -> None:
    """A card whose value changes gets one write + the new value persisted."""
    store = FsStateStore(tmp_path)
    reporter = _FakeHealthReporter()
    deps = _deps(store, reporter)
    # Tick 1: card in Backlog, no agent → INACTIVE.
    apply_health(
        deps, _config(), running=(), snapshot=_snapshot(_ticket(1, "PVTI_1", "Backlog")), now=1.0
    )
    # Tick 2: an agent is now RUNNING on it → ACTIVE (a change).
    apply_health(
        deps,
        _config(),
        running=(_running(1, TicketStatus.RUNNING),),
        snapshot=_snapshot(_ticket(1, "PVTI_1", "Backlog")),
        now=2.0,
    )
    assert reporter.set_calls == [("PVTI_1", "INACTIVE"), ("PVTI_1", "ACTIVE")]
    assert store.get_item_health("PVTI_1") == "ACTIVE"


# ---------------------------------------------------------------------------
# Running-state mapping
# ---------------------------------------------------------------------------


def test_running_state_mapping(tmp_path: Path) -> None:
    """RUNNING → ACTIVE; WAITING → WAITING; reaped-to-Blocked (no live) → BLOCKED."""
    store = FsStateStore(tmp_path)
    reporter = _FakeHealthReporter()
    snap = _snapshot(
        _ticket(1, "PVTI_1", "InProgress"),  # RUNNING agent → ACTIVE
        _ticket(2, "PVTI_2", "InProgress"),  # WAITING agent → WAITING
        _ticket(3, "PVTI_3", "Blocked"),  # no live state, parked Blocked → BLOCKED
    )
    running = (_running(1, TicketStatus.RUNNING), _running(2, TicketStatus.WAITING))
    apply_health(_deps(store, reporter), _config(), running=running, snapshot=snap, now=1.0)
    assert set(reporter.set_calls) == {
        ("PVTI_1", "ACTIVE"),
        ("PVTI_2", "WAITING"),
        ("PVTI_3", "BLOCKED"),
    }


# ---------------------------------------------------------------------------
# Fail-soft
# ---------------------------------------------------------------------------


def test_fail_soft_whole_step_on_ensure_error(tmp_path: Path) -> None:
    """ensure_health_field raising → step swallows, no per-card writes, no raise."""
    store = FsStateStore(tmp_path)
    reporter = _FakeHealthReporter(ensure_raises=True)
    snap = _snapshot(_ticket(1, "PVTI_1", "Backlog"))
    apply_health(_deps(store, reporter), _config(), running=(), snapshot=snap, now=1.0)
    assert reporter.set_calls == []  # no writes attempted


def test_fail_soft_per_card_continues_after_one_failure(tmp_path: Path) -> None:
    """A set_item_health error is logged + swallowed; other cards still processed."""
    store = FsStateStore(tmp_path)
    reporter = _FakeHealthReporter(set_raises=True)
    snap = _snapshot(_ticket(1, "PVTI_1", "Backlog"), _ticket(2, "PVTI_2", "Done"))
    # No raise; both cards attempted despite each failing.
    apply_health(_deps(store, reporter), _config(), running=(), snapshot=snap, now=1.0)
    assert {c[0] for c in reporter.set_calls} == {"PVTI_1", "PVTI_2"}
    # A failed write did NOT persist the last-written value (so it retries next tick).
    assert store.get_item_health("PVTI_1") is None


# ---------------------------------------------------------------------------
# Rebind guard + multi-root
# ---------------------------------------------------------------------------


def test_rebind_guard_clears_markers_and_reensures(tmp_path: Path) -> None:
    """A store bound to a DIFFERENT project → markers cleared + re-bound + fresh ensure."""
    store = FsStateStore(tmp_path)
    # Pre-seed markers as if a PREVIOUS project owned them.
    store.set_health_project_id("PVT_OLD")
    store.set_health_field_id("OLD_F")
    store.set_health_options({"ACTIVE": "old"})
    store.set_item_health("PVTI_1", "ACTIVE")

    reporter = _FakeHealthReporter()
    snap = _snapshot(_ticket(1, "PVTI_1", "InProgress"))
    apply_health(
        _deps(store, reporter, project_id=PROJECT),
        _config(),
        running=(_running(1, TicketStatus.RUNNING),),
        snapshot=snap,
        now=1.0,
    )

    # Re-bound to the live project + the old per-card marker was cleared then rewritten fresh.
    assert store.get_health_project_id() == PROJECT
    assert store.get_health_field_id() == "HEALTH_F"
    assert reporter.ensured == [PROJECT]
    assert store.get_item_health("PVTI_1") == "ACTIVE"


def test_multi_root_independent_caches(tmp_path: Path) -> None:
    """Two stores (two roots) keep independent last-written caches."""
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    store_a = FsStateStore(root_a)
    store_b = FsStateStore(root_b)
    reporter_a = _FakeHealthReporter()
    reporter_b = _FakeHealthReporter()
    snap = _snapshot(_ticket(1, "PVTI_1", "Done"))  # → COMPLETE

    # Root A writes once.
    apply_health(_deps(store_a, reporter_a), _config(), running=(), snapshot=snap, now=1.0)
    assert reporter_a.set_calls == [("PVTI_1", "COMPLETE")]
    # Root B has NOT seen this card → it writes too (A's marker does not suppress B).
    apply_health(_deps(store_b, reporter_b), _config(), running=(), snapshot=snap, now=1.0)
    assert reporter_b.set_calls == [("PVTI_1", "COMPLETE")]

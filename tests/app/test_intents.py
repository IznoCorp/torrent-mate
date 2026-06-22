"""Tests for the daemon-side intent executor (:mod:`kanbanmate.app.intents`, cockpit PR2).

Drives ``drain_intents`` against in-memory fakes, asserting the load-bearing invariants: operator move
executes (move_card + baseline advance + done result + cleared), unknown-column / off-board rejection,
agent re-fire guard (authority derived from the running set), the PAUSE matrix (agent held / operator
runs), same-issue ordering (earliest runs, rest deferred), optimistic idempotence, and poison/raise
fail-soft.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

import pytest

from kanbanmate.app.actions import Deps
from kanbanmate.app.intents import drain_intents
from kanbanmate.app.tick import TickConfig
from kanbanmate.core.columns import load_columns
from kanbanmate.core.domain import BoardSnapshot, Ticket
from kanbanmate.core.transitions import load_transitions
from kanbanmate.ports.store import TicketState, TicketStatus

_COLUMNS_YAML = """
columns:
  - key: Backlog
    name: Backlog
  - key: Spec
    name: Spec
  - key: Done
    name: Done
"""

# Backlog->Spec is prompt-bearing (a launch target); Backlog->Done is not.
_WHITELIST = """
project: owner/repo
transitions:
  - from: Backlog
    to: Spec
    profile: docs
    prompt: "design it"
"""


def _config() -> TickConfig:
    return TickConfig(
        columns=load_columns(_COLUMNS_YAML),
        transitions=load_transitions(_WHITELIST),
        concurrency_cap=3,
    )


@dataclass
class _FakeWriter:
    moves: list[tuple[str, str]] = field(default_factory=list)
    created: list[tuple[str, str, str, list[str]]] = field(default_factory=list)
    added: list[tuple[str, str]] = field(default_factory=list)
    raises: bool = False
    _next_number: int = 200

    def move_card(self, item_id: str, column_key: str) -> None:
        self.moves.append((item_id, column_key))
        if self.raises:
            raise RuntimeError("simulated move_card failure")

    def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> tuple[str, int]:
        self.created.append((repo, title, body, list(labels)))
        self._next_number += 1
        return (f"NODE_{self._next_number}", self._next_number)

    def add_to_project(self, project_id: str, issue_node_id: str) -> str:
        self.added.append((project_id, issue_node_id))
        return f"PVTI_{issue_node_id}"

    edited: list[tuple[str, str]] = field(default_factory=list)
    closed: list[str] = field(default_factory=list)
    missing_issues: frozenset[int] = frozenset()

    def fetch_issue(self, issue_number: int):  # type: ignore[no-untyped-def]
        from kanbanmate.adapters.github.types import IssueRef

        if issue_number in self.missing_issues:
            raise RuntimeError("issue not found")
        return IssueRef(node_id=f"NODE_{issue_number}", number=issue_number, title="t", body="b")

    def update_issue_body(self, issue_node_id: str, body: str) -> None:
        self.edited.append((issue_node_id, body))

    def close_issue(self, issue_node_id: str) -> None:
        self.closed.append(issue_node_id)


@dataclass
class _FakeStore:
    intents: dict[str, dict[str, object]] = field(default_factory=dict)
    results: dict[str, dict[str, object]] = field(default_factory=dict)
    running: list[TicketState] = field(default_factory=list)

    def list_pending_intents(self) -> tuple[str, ...]:
        return tuple(sorted(self.intents))

    def enqueue_intent(self, intent_id: str, payload: dict[str, object]) -> None:
        # Used by the ticket_create checkpoint (re-enqueue with merged args).
        self.intents[intent_id] = dict(payload)

    def load_intent(self, intent_id: str) -> dict[str, object] | None:
        return self.intents.get(intent_id)

    def clear_intent(self, intent_id: str) -> None:
        self.intents.pop(intent_id, None)

    def save_intent_result(self, intent_id: str, payload: dict[str, object]) -> None:
        self.results[intent_id] = dict(payload)

    gc_calls: list[tuple[float, float]] = field(default_factory=list)

    def gc_intent_results(self, *, now: float, ttl: float) -> None:
        # Record the GC sweep (cockpit DESIGN §10); the fake keeps results in memory so this is a
        # no-op beyond recording that the drain invoked it once per drain.
        self.gc_calls.append((now, ttl))

    def list_running(self) -> list[TicketState]:
        return list(self.running)

    override_enum: str | None = None
    override_note: str | None = None

    def set_status_override_enum(self, status: str | None) -> None:
        self.override_enum = status

    def set_status_override_note(self, note: str | None) -> None:
        self.override_note = note

    reserved: list[int] = field(default_factory=list)
    released: list[int] = field(default_factory=list)
    slot_cap_full: bool = False

    def reserve_slot(self, issue_number: int, cap: int) -> bool:
        if self.slot_cap_full:
            return False
        self.reserved.append(issue_number)
        return True

    def release_slot(self, issue_number: int) -> None:
        self.released.append(issue_number)

    # Restart-durable pending-launch breadcrumb (#55): _execute_move records one on a launch edge.
    pending_launch_records: list[tuple[str, str, str]] = field(default_factory=list)
    pending_launch_cleared: list[str] = field(default_factory=list)

    def record_pending_launch(
        self, item_id: str, *, from_col: str, to_col: str, now: float
    ) -> None:
        self.pending_launch_records.append((item_id, from_col, to_col))

    def pending_launches(self, *, now: float) -> dict[str, object]:
        return {}

    def clear_pending_launch(self, item_id: str) -> None:
        self.pending_launch_cleared.append(item_id)


def _deps(store: _FakeStore, writer: _FakeWriter, *, kanban_root: str = "") -> Deps:
    placeholder = object()
    return Deps(
        board_writer=writer,  # type: ignore[arg-type]
        board_reader=placeholder,  # type: ignore[arg-type]
        workspace=placeholder,  # type: ignore[arg-type]
        sessions=placeholder,  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        clock=placeholder,  # type: ignore[arg-type]
        pull_requests=placeholder,  # type: ignore[arg-type]
        status_reporter=placeholder,  # type: ignore[arg-type]
        project_id="PVT_proj",
        repo="o/r",
        seeder=writer,  # type: ignore[arg-type]
        kanban_root=kanban_root,
    )


def _snapshot(*tickets: Ticket) -> BoardSnapshot:
    return BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)


def _ticket(n: int, col: str) -> Ticket:
    return Ticket(item_id=f"PVTI_{n}", issue_number=n, title=f"t{n}", column_key=col)


def _running(n: int) -> TicketState:
    return TicketState(
        issue_number=n,
        item_id=f"PVTI_{n}",
        session_id="s",
        status=TicketStatus.RUNNING,
        heartbeat=1.0,
        stage="Backlog",
        profile="dev",
        started=0.0,
    )


def _move_intent(issue: int, to_col: str, requested_at: float = 1.0) -> dict[str, object]:
    return {
        "kind": "move",
        "issue": issue,
        "args": {"to_col": to_col},
        "requested_at": requested_at,
    }


def _drain(
    store: _FakeStore,
    writer: _FakeWriter,
    *,
    kill_switch: bool = False,
    kanban_root: str = "",
) -> dict[str, str]:
    """Run drain_intents with a Backlog snapshot for #8 and #9; return next_columns."""
    next_columns: dict[str, str] = {}
    drain_intents(
        _deps(store, writer, kanban_root=kanban_root),
        _config(),
        snapshot=_snapshot(_ticket(8, "Backlog"), _ticket(9, "Backlog")),
        next_columns=next_columns,
        running=tuple(store.running),
        status_events=[],
        now=1000.0,
        kill_switch=kill_switch,
    )
    return next_columns


def test_operator_move_executes() -> None:
    store = _FakeStore(intents={"i1": _move_intent(8, "Done")})
    writer = _FakeWriter()
    next_columns = _drain(store, writer)
    assert writer.moves == [("PVTI_8", "Done")]
    assert (
        next_columns["PVTI_8"] == "Done"
    )  # baseline advanced (Backlog->Done is not prompt-bearing)
    assert store.results["i1"]["state"] == "done"
    assert "i1" not in store.intents  # cleared


def test_operator_move_into_launch_column_does_not_advance_baseline() -> None:
    """An operator move INTO a launch-bearing column must NOT advance the diff baseline.

    Regression for the live #55 bug: moving ReadyToDev→PrepareFeature from the Monitoring panel
    launched no prepare/create-branch agent because the intent advanced the baseline (next_columns),
    so the next tick's diff never re-detected the arrival. Leaving the baseline unadvanced makes the
    next diff fire the column's entry agent — exactly like a GitHub board drag. (Backlog->Spec is the
    prompt-bearing launch target in the fixture.)
    """
    store = _FakeStore(
        intents={"i1": _move_intent(8, "Spec")}
    )  # operator authority (nothing running)
    writer = _FakeWriter()
    next_columns = _drain(store, writer)
    assert writer.moves == [("PVTI_8", "Spec")]  # the move still lands
    assert "PVTI_8" not in next_columns, (
        "launch edge must NOT advance baseline (next diff fires it)"
    )
    assert store.results["i1"]["state"] == "done"
    assert "i1" not in store.intents


def test_operator_move_into_launch_column_records_pending_launch() -> None:
    """A launch-edge move drops a restart-durable pending_launch breadcrumb (#55).

    Pairs with the baseline-not-advanced behaviour: leaving the baseline unadvanced makes the next
    tick's diff fire the entry agent, but a daemon restart in that window wipes the in-memory
    baseline (#20) and the launch is silently dropped. The breadcrumb lets the tick re-create the
    transition after a restart. Recorded with (item_id, from_col KEY, to_col KEY).
    """
    store = _FakeStore(intents={"i1": _move_intent(8, "Spec")})
    writer = _FakeWriter()
    _drain(store, writer)
    assert store.pending_launch_records == [("PVTI_8", "Backlog", "Spec")]


def test_operator_move_into_noop_column_records_no_pending_launch() -> None:
    """A NON-launch (no-action) move must NOT drop a pending_launch breadcrumb (#55).

    Backlog->Done carries no prompt: the baseline advances normally and there is nothing to recover
    after a restart, so no breadcrumb is written (it would otherwise re-fire a non-launch move).
    """
    store = _FakeStore(intents={"i1": _move_intent(8, "Done")})
    writer = _FakeWriter()
    _drain(store, writer)
    assert store.pending_launch_records == []


def test_move_translates_column_key_to_github_name() -> None:
    """A move to a column KEY whose name differs (``PRCI`` → ``PR/CI``) must call move_card with the
    GitHub option NAME, not the raw key.

    ``move_card`` indexes the Status options by display NAME; the raw key raised ``KeyError: 'PRCI'``
    for the one shipped column whose key != name, so the agent's ``kanban-move 'PR/CI'`` was rejected
    every cycle (the engine bug that, compounded with the broken CI gate, stranded #5). The drain now
    translates via ``resolve_column`` like the session-end / script-route move paths.
    """
    columns_yaml = _COLUMNS_YAML + "  - key: PRCI\n    name: PR/CI\n"
    config = TickConfig(
        columns=load_columns(columns_yaml),
        transitions=load_transitions(_WHITELIST),
        concurrency_cap=3,
    )
    store = _FakeStore(intents={"i1": _move_intent(8, "PRCI")})  # operator authority (no running)
    writer = _FakeWriter()
    next_columns: dict[str, str] = {}
    drain_intents(
        _deps(store, writer),
        config,
        snapshot=_snapshot(_ticket(8, "Backlog")),
        next_columns=next_columns,
        running=tuple(store.running),
        status_events=[],
        now=1000.0,
        kill_switch=False,
    )
    assert writer.moves == [("PVTI_8", "PR/CI")]  # the NAME, not the raw key 'PRCI'
    assert next_columns["PVTI_8"] == "PRCI"  # baseline records the stable KEY
    assert store.results["i1"]["state"] == "done"
    assert "i1" not in store.intents


def test_move_idempotent_across_name_key_seam() -> None:
    """Idempotence holds across the name/key seam.

    A card already in ``PR/CI`` (the NAME the adapter emits as ``column_key``) with a move intent to
    the ``PRCI`` KEY is a no-op done — NOT a redundant move_card that would needlessly consume the
    per-ticket auto-advance rate-limit budget.
    """
    columns_yaml = _COLUMNS_YAML + "  - key: PRCI\n    name: PR/CI\n"
    config = TickConfig(
        columns=load_columns(columns_yaml),
        transitions=load_transitions(_WHITELIST),
        concurrency_cap=3,
    )
    store = _FakeStore(intents={"i1": _move_intent(8, "PRCI")})
    writer = _FakeWriter()
    next_columns: dict[str, str] = {}
    drain_intents(
        _deps(store, writer),
        config,
        snapshot=_snapshot(_ticket(8, "PR/CI")),  # already there (adapter emits the NAME)
        next_columns=next_columns,
        running=tuple(store.running),
        status_events=[],
        now=1000.0,
        kill_switch=False,
    )
    assert writer.moves == []  # no redundant move_card
    assert store.results["i1"]["state"] == "done"
    assert "already in" in str(store.results["i1"]["detail"])


def test_drain_runs_result_gc_once_even_with_no_pending() -> None:
    """The drain fires the result GC every tick — even when no intents are pending (cockpit §10)."""
    store = _FakeStore(intents={})  # nothing pending
    writer = _FakeWriter()
    _drain(store, writer)
    assert store.gc_calls == [(1000.0, 3600.0)]  # GC ran once with the configured TTL


def test_move_to_unknown_column_rejected() -> None:
    store = _FakeStore(intents={"i1": _move_intent(8, "Nope")})
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.moves == []
    assert store.results["i1"]["state"] == "rejected"
    assert "i1" not in store.intents


def test_agent_move_into_launch_target_rejected() -> None:
    # #8 is a running agent → agent authority; Backlog->Spec is prompt-bearing → re-fire reject.
    store = _FakeStore(intents={"i1": _move_intent(8, "Spec")}, running=[_running(8)])
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.moves == []
    assert store.results["i1"]["state"] == "rejected"
    assert "re-fire" in str(store.results["i1"]["detail"])


# ---------------------------------------------------------------------------
# Agent-authority end-to-end (0.4.0 move-unification): agents now ENQUEUE move
# intents (caller="agent", advisory) which the daemon drains under agent authority.
# ---------------------------------------------------------------------------


def _agent_move_intent(issue: int, to_col: str, requested_at: float = 1.0) -> dict[str, object]:
    """A move intent carrying the ADVISORY ``caller="agent"`` (as the helper enqueues, 0.4.0)."""
    return {
        "kind": "move",
        "issue": issue,
        "args": {"to_col": to_col},
        "requested_at": requested_at,
        "caller": "agent",
    }


def test_agent_move_to_non_triggering_on_own_issue_executes() -> None:
    """An agent move to a NON-triggering column on its OWN in-flight issue applies + advances baseline.

    #8 is in the running set → agent authority; Backlog->Done is not prompt-bearing → allowed. The
    move lands and ``next_columns`` advances so the next diff does NOT re-fire a launch.
    """
    store = _FakeStore(intents={"i1": _agent_move_intent(8, "Done")}, running=[_running(8)])
    writer = _FakeWriter()
    next_columns = _drain(store, writer)
    assert writer.moves == [("PVTI_8", "Done")]
    assert next_columns["PVTI_8"] == "Done"  # baseline advanced → no re-fire
    assert store.results["i1"]["state"] == "done"
    assert "i1" not in store.intents


def test_agent_move_on_different_issue_rejected_r1() -> None:
    """R1: the daemon passes ``launching_issue=intent.issue``, so an agent's own issue is the only
    one it can act on — there is no path to move a DIFFERENT issue under agent authority.

    Authority is derived per-issue: only the issue in the running set is bridled-agent. An intent for
    a NON-running issue is OPERATOR authority (see the security-heart test below); an agent can never
    smuggle a foreign-issue move because the issue it names IS the authority key.
    """
    # #8 running; the intent names #9 (not running) → authority resolves to OPERATOR, not agent.
    store = _FakeStore(intents={"i1": _agent_move_intent(9, "Spec")}, running=[_running(8)])
    writer = _FakeWriter()
    _drain(store, writer)
    # #9 → Spec under OPERATOR authority is broad (no re-fire guard) → it executes (proves authority
    # is derived from the running set, not the spoofable caller field).
    assert writer.moves == [("PVTI_9", "Spec")]
    assert store.results["i1"]["state"] == "done"


def test_caller_agent_but_not_running_resolves_to_operator() -> None:
    """SECURITY HEART: ``caller="agent"`` is advisory — a non-running issue is OPERATOR authority.

    An attacker-controlled ``caller="agent"`` for an issue the daemon did NOT launch must NOT bridle
    the move (or, conversely, must not grant agent privileges); the daemon derives authority SOLELY
    from its running-set bookkeeping. #8 is not running, so despite ``caller="agent"`` the move into a
    launch target (Spec) is allowed under operator authority (the re-fire guard is agent-only).
    """
    store = _FakeStore(intents={"i1": _agent_move_intent(8, "Spec")}, running=[])  # nothing running
    writer = _FakeWriter()
    _drain(store, writer)
    # Operator authority → broad → the move into the prompt-bearing Spec executes (no agent re-fire
    # guard applied), proving authority came from the running set, not the caller field.
    assert writer.moves == [("PVTI_8", "Spec")]
    assert store.results["i1"]["state"] == "done"


def test_agent_move_into_merge_rejected() -> None:
    """An agent move into the human-only ``Merge`` column is rejected (merge=human-only)."""
    columns_yaml = _COLUMNS_YAML + "  - key: Merge\n    name: Merge\n"
    config = TickConfig(
        columns=load_columns(columns_yaml),
        transitions=load_transitions(_WHITELIST),
        concurrency_cap=3,
    )
    store = _FakeStore(intents={"i1": _agent_move_intent(8, "Merge")}, running=[_running(8)])
    writer = _FakeWriter()
    next_columns: dict[str, str] = {}
    drain_intents(
        _deps(store, writer),
        config,
        snapshot=_snapshot(_ticket(8, "Backlog")),
        next_columns=next_columns,
        running=tuple(store.running),
        status_events=[],
        now=1000.0,
        kill_switch=False,
    )
    assert writer.moves == []
    assert store.results["i1"]["state"] == "rejected"
    assert "Merge" in str(store.results["i1"]["detail"])


def test_agent_move_held_under_pause() -> None:
    """An agent move (own running issue) is HELD under PAUSE (left pending until resume)."""
    store = _FakeStore(intents={"i1": _agent_move_intent(8, "Done")}, running=[_running(8)])
    writer = _FakeWriter()
    _drain(store, writer, kill_switch=True)
    assert writer.moves == []
    assert store.results["i1"]["state"] == "held"
    assert "i1" in store.intents  # held → still pending


def test_pause_holds_agent_intent_but_runs_operator() -> None:
    # Agent intent (#8 running) is HELD under PAUSE (left pending); operator intent (#9) still runs.
    store = _FakeStore(
        intents={"agent": _move_intent(8, "Done"), "op": _move_intent(9, "Done")},
        running=[_running(8)],
    )
    writer = _FakeWriter()
    _drain(store, writer, kill_switch=True)
    assert ("PVTI_9", "Done") in writer.moves
    assert ("PVTI_8", "Done") not in writer.moves
    assert store.results["agent"]["state"] == "held"
    assert "agent" in store.intents  # held → still pending
    assert store.results["op"]["state"] == "done"


def test_same_issue_ordering_defers_later_intent() -> None:
    # Two intents for #8: the earlier (requested_at 1.0) runs; the later (2.0) is deferred + pending.
    store = _FakeStore(
        intents={
            "later": _move_intent(8, "Spec", requested_at=2.0),
            "earlier": _move_intent(8, "Done", requested_at=1.0),
        }
    )
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.moves == [("PVTI_8", "Done")]  # only the earlier ran
    assert store.results["earlier"]["state"] == "done"
    assert store.results["later"]["state"] == "deferred"
    assert "later" in store.intents and "earlier" not in store.intents


def test_optimistic_idempotent_noop_when_already_in_destination() -> None:
    # Card #8 is already in Backlog; a move to Backlog is a no-op done (no move_card).
    store = _FakeStore(intents={"i1": _move_intent(8, "Backlog")})
    writer = _FakeWriter()
    next_columns = _drain(store, writer)
    assert writer.moves == []
    assert store.results["i1"]["state"] == "done"
    assert next_columns["PVTI_8"] == "Backlog"


def test_issue_not_on_board_rejected() -> None:
    store = _FakeStore(intents={"i1": _move_intent(404, "Done")})
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.moves == []
    assert store.results["i1"]["state"] == "rejected"


def test_poison_intent_rejected_and_cleared() -> None:
    store = _FakeStore(intents={"i1": {"garbage": True}})  # no kind → unparseable
    writer = _FakeWriter()
    _drain(store, writer)
    assert store.results["i1"]["state"] == "rejected"
    assert "i1" not in store.intents


def test_move_card_raise_is_isolated() -> None:
    store = _FakeStore(intents={"i1": _move_intent(8, "Done")})
    writer = _FakeWriter(raises=True)
    # Must not raise (fail-soft); the intent is rejected + cleared.
    _drain(store, writer)
    assert store.results["i1"]["state"] == "rejected"
    assert "i1" not in store.intents


# ---------------------------------------------------------------------------
# ticket_create (cockpit PR3) — operator-only, idempotent multi-step.
# ---------------------------------------------------------------------------


def _create_intent(**args: object) -> dict[str, object]:
    return {"kind": "ticket_create", "issue": None, "args": dict(args), "requested_at": 1.0}


def test_ticket_create_executes() -> None:
    store = _FakeStore(intents={"i1": _create_intent(title="New", body="b", labels=["x"])})
    writer = _FakeWriter()
    _drain(store, writer)
    assert len(writer.created) == 1
    assert writer.created[0][1] == "New"  # title
    assert len(writer.added) == 1
    assert store.results["i1"]["state"] == "done"
    assert "created #201" in str(store.results["i1"]["detail"])
    assert "i1" not in store.intents


def test_ticket_create_with_initial_column_moves() -> None:
    store = _FakeStore(intents={"i1": _create_intent(title="N", column="Done")})
    writer = _FakeWriter()
    _drain(store, writer)
    assert len(writer.created) == 1
    assert writer.moves and writer.moves[-1][1] == "Done"
    assert store.results["i1"]["state"] == "done"


def test_ticket_create_into_launch_column_rejected() -> None:
    # Backlog->Spec is prompt-bearing → Spec is a launch target → refuse creating directly into it.
    store = _FakeStore(intents={"i1": _create_intent(title="N", column="Spec")})
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.created == []
    assert store.results["i1"]["state"] == "rejected"
    assert "launch column" in str(store.results["i1"]["detail"])


def test_ticket_create_missing_title_rejected() -> None:
    store = _FakeStore(intents={"i1": _create_intent(body="no title")})
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.created == []
    assert store.results["i1"]["state"] == "rejected"


def test_ticket_create_resumes_from_checkpoint() -> None:
    # The intent already carries the checkpoint (issue created + added) → resume, do NOT re-create.
    store = _FakeStore(
        intents={
            "i1": _create_intent(
                title="N", _created_number=201, _node_id="NODE_201", _item_id="PVTI_NODE_201"
            )
        }
    )
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.created == []  # resumed, not re-created
    assert writer.added == []
    assert store.results["i1"]["state"] == "done"
    assert "i1" not in store.intents


# ---------------------------------------------------------------------------
# ticket_edit / ticket_close (cockpit PR3.2) — operator-only.
# ---------------------------------------------------------------------------


def test_ticket_edit_executes() -> None:
    store = _FakeStore(
        intents={
            "i1": {"kind": "ticket_edit", "issue": 8, "args": {"body": "new"}, "requested_at": 1.0}
        }
    )
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.edited == [("NODE_8", "new")]
    assert store.results["i1"]["state"] == "done"
    assert "i1" not in store.intents


def test_ticket_edit_missing_body_rejected() -> None:
    store = _FakeStore(
        intents={"i1": {"kind": "ticket_edit", "issue": 8, "args": {}, "requested_at": 1.0}}
    )
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.edited == []
    assert store.results["i1"]["state"] == "rejected"


def test_ticket_edit_issue_not_found_rejected() -> None:
    store = _FakeStore(
        intents={
            "i1": {"kind": "ticket_edit", "issue": 8, "args": {"body": "x"}, "requested_at": 1.0}
        }
    )
    writer = _FakeWriter(missing_issues=frozenset({8}))
    _drain(store, writer)
    assert writer.edited == []
    assert store.results["i1"]["state"] == "rejected"
    assert "not found" in str(store.results["i1"]["detail"])


def test_ticket_close_executes() -> None:
    store = _FakeStore(
        intents={"i1": {"kind": "ticket_close", "issue": 8, "args": {}, "requested_at": 1.0}}
    )
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.closed == ["NODE_8"]
    assert store.results["i1"]["state"] == "done"
    assert "i1" not in store.intents


def test_agent_cannot_edit_its_ticket() -> None:
    # #8 is a running agent → agent authority; ticket_edit is not in AGENT_ALLOWED_KINDS → rejected.
    store = _FakeStore(
        intents={
            "i1": {"kind": "ticket_edit", "issue": 8, "args": {"body": "x"}, "requested_at": 1.0}
        },
        running=[_running(8)],
    )
    writer = _FakeWriter()
    _drain(store, writer)
    assert writer.edited == []
    assert store.results["i1"]["state"] == "rejected"
    assert "may not" in str(store.results["i1"]["detail"])


def test_ticket_edit_preserves_markers() -> None:
    """tiller §6.2: a ticket_edit with marker-bearing body preserves markers via split/merge."""
    body_with_marker = "**roadmap**: A1\n\nOld freeform."
    writer = _FakeWriter()
    # Override the default body="b" so fetch_issue returns a marker-bearing body.

    def _fetch_with_marker(issue_number: int):  # type: ignore[no-untyped-def]
        from kanbanmate.adapters.github.types import IssueRef

        return IssueRef(
            node_id=f"NODE_{issue_number}",
            number=issue_number,
            title="[A1] T",
            body=body_with_marker,
        )

    writer.fetch_issue = _fetch_with_marker  # type: ignore[method-assign]
    store = _FakeStore(
        intents={
            "i1": {
                "kind": "ticket_edit",
                "issue": 8,
                # `freeform` (SPA merge path) → markers are preserved around the new prose.
                "args": {"freeform": "New freeform only."},
                "requested_at": 1.0,
            }
        }
    )
    _drain(store, writer)
    assert len(writer.edited) == 1
    updated = writer.edited[0][1]
    assert "New freeform only." in updated  # operator freeform landed
    assert "**roadmap**: A1" in updated  # marker preserved
    assert store.results["i1"]["state"] == "done"


# ---------------------------------------------------------------------------
# pill override (cockpit PR3.3) — operator-only; writes override markers only.
# ---------------------------------------------------------------------------


def test_pill_set_health_sets_override() -> None:
    store = _FakeStore(
        intents={
            "i1": {
                "kind": "pill_set_health",
                "issue": None,
                "args": {"enum": "WAITING", "note": "incident"},
                "requested_at": 1.0,
            }
        }
    )
    _drain(store, _FakeWriter())
    assert store.override_enum == "WAITING"
    assert store.override_note == "incident"
    assert store.results["i1"]["state"] == "done"


def test_pill_set_health_bad_enum_rejected() -> None:
    store = _FakeStore(
        intents={
            "i1": {
                "kind": "pill_set_health",
                "issue": None,
                "args": {"enum": "BOGUS"},
                "requested_at": 1.0,
            }
        }
    )
    _drain(store, _FakeWriter())
    assert store.override_enum is None
    assert store.results["i1"]["state"] == "rejected"


def test_pill_note_sets_note() -> None:
    store = _FakeStore(
        intents={
            "i1": {
                "kind": "pill_note",
                "issue": None,
                "args": {"text": "hello"},
                "requested_at": 1.0,
            }
        }
    )
    _drain(store, _FakeWriter())
    assert store.override_note == "hello"
    assert store.results["i1"]["state"] == "done"


def test_pill_clear_clears_override() -> None:
    store = _FakeStore(
        intents={"i1": {"kind": "pill_clear", "issue": None, "args": {}, "requested_at": 1.0}}
    )
    store.override_enum = "WAITING"
    store.override_note = "x"
    _drain(store, _FakeWriter())
    assert store.override_enum is None
    assert store.override_note is None
    assert store.results["i1"]["state"] == "done"


# --- ad-hoc launch intent (tiller follow-up, 2026-06-21) -------------------------------------------


def _seed_launch_secret(root) -> bytes:  # type: ignore[no-untyped-def]
    """Mint the runtime-root launch secret (FIX 4) so the UI-minted op_token verifies; return it."""
    from kanbanmate.app.intents import load_launch_secret

    secret = load_launch_secret(root, create=True)
    assert secret is not None
    return secret


def _launch_intent(
    issue: int,
    prompt: str = "fix the bug",
    profile: str = "dev",
    requested_at: float = 1.0,
    *,
    op_token: str | None = None,
    secret: bytes | None = None,
) -> dict[str, object]:
    """Build a launch intent.

    Pass ``secret`` (the runtime-root launch secret) to mint a VALID op_token for (issue, profile) —
    the operator-authorized path. Pass ``op_token`` to force a specific (possibly forged) token. Omit
    both to enqueue a TOKEN-LESS launch (the agent-forged case the FIX-4 guard rejects).
    """
    from kanbanmate.app.intents import compute_launch_token

    args: dict[str, object] = {"prompt": prompt, "profile": profile}
    if op_token is not None:
        args["op_token"] = op_token
    elif secret is not None:
        args["op_token"] = compute_launch_token(secret, issue, profile)
    return {
        "kind": "launch",
        "issue": issue,
        "args": args,
        "requested_at": requested_at,
    }


class _SpyLaunch:
    """Stand-in for LaunchAction recording its construction + execution (no real worktree/tmux I/O)."""

    last: _SpyLaunch | None = None

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.executed = False
        _SpyLaunch.last = self

    def execute(self, deps: object) -> None:
        self.executed = True


def test_operator_launch_executes_without_moving(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    import kanbanmate.app.actions as actions_mod

    _SpyLaunch.last = None
    monkeypatch.setattr(actions_mod, "LaunchAction", _SpyLaunch)
    secret = _seed_launch_secret(tmp_path)
    store = _FakeStore(
        intents={"i1": _launch_intent(8, prompt="fix it", profile="dev", secret=secret)}
    )
    writer = _FakeWriter()
    _drain(store, writer, kanban_root=str(tmp_path))
    # The agent was launched but the card NEVER moved (no transition).
    assert writer.moves == []
    assert store.reserved == [8]
    assert _SpyLaunch.last is not None
    assert _SpyLaunch.last.executed
    assert _SpyLaunch.last.kwargs["advance"] == "stop"
    assert _SpyLaunch.last.kwargs["prompt"] == "fix it"
    assert _SpyLaunch.last.kwargs["profile"] == "dev"
    # Ad-hoc operator prompt is delivered VERBATIM (no placeholder fill → no KeyError on `{{...}}`).
    assert _SpyLaunch.last.kwargs["fill_prompt"] is False
    # The ad-hoc session is killed on claude exit so it disappears (state already purged by session-end).
    assert _SpyLaunch.last.kwargs["terminate_on_exit"] is True
    assert store.results["i1"]["state"] == "done"
    assert "i1" not in store.intents


def test_launch_merge_profile_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The `merge` profile (which lifts the gh-pr-merge ban) is REFUSED for an ad-hoc launch.

    merge=human-only: the merge-capable profile is reachable only via the engine-gated Review→Merge
    stage, never an ad-hoc launch (else a bridled agent could escalate via a non-running target issue).
    The refusal happens BEFORE reserving a slot or constructing the action.
    """
    import kanbanmate.app.actions as actions_mod

    _SpyLaunch.last = None
    monkeypatch.setattr(actions_mod, "LaunchAction", _SpyLaunch)
    store = _FakeStore(intents={"i1": _launch_intent(8, profile="merge")})
    _drain(store, _FakeWriter())
    assert store.results["i1"]["state"] == "rejected"
    assert "merge" in str(store.results["i1"]["detail"]).lower()
    assert _SpyLaunch.last is None  # action never constructed
    assert store.reserved == []  # rejected before reserving a slot
    assert "i1" not in store.intents


def test_agent_launch_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """A launch whose issue is a daemon-tracked running agent → agent authority → rejected."""
    import kanbanmate.app.actions as actions_mod

    _SpyLaunch.last = None
    monkeypatch.setattr(actions_mod, "LaunchAction", _SpyLaunch)
    store = _FakeStore(intents={"i1": _launch_intent(8)}, running=[_running(8)])
    _drain(store, _FakeWriter())
    assert store.results["i1"]["state"] == "rejected"
    assert _SpyLaunch.last is None  # never constructed
    assert store.reserved == []
    assert "i1" not in store.intents


def test_launch_empty_prompt_launches_bare(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """An empty prompt is OPTIONAL → launch a BARE claude (prompt=None) the operator drives manually."""
    import kanbanmate.app.actions as actions_mod

    _SpyLaunch.last = None
    monkeypatch.setattr(actions_mod, "LaunchAction", _SpyLaunch)
    secret = _seed_launch_secret(tmp_path)
    store = _FakeStore(intents={"i1": _launch_intent(8, prompt="   ", secret=secret)})
    _drain(store, _FakeWriter(), kanban_root=str(tmp_path))
    assert store.results["i1"]["state"] == "done"
    assert _SpyLaunch.last is not None
    assert _SpyLaunch.last.kwargs["prompt"] is None  # bare claude — nothing injected into the REPL
    assert _SpyLaunch.last.kwargs["advance"] == "stop"
    assert store.reserved == [8]


def test_launch_cap_full_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    import kanbanmate.app.actions as actions_mod

    _SpyLaunch.last = None
    monkeypatch.setattr(actions_mod, "LaunchAction", _SpyLaunch)
    secret = _seed_launch_secret(tmp_path)
    store = _FakeStore(intents={"i1": _launch_intent(8, secret=secret)}, slot_cap_full=True)
    _drain(store, _FakeWriter(), kanban_root=str(tmp_path))
    assert store.results["i1"]["state"] == "rejected"
    assert _SpyLaunch.last is None  # cap rejected BEFORE constructing the action
    assert "i1" not in store.intents


def test_launch_failure_releases_slot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """If the launch raises, the reserved slot is released (no leak) and the intent is rejected."""
    import kanbanmate.app.actions as actions_mod

    class _BoomLaunch:
        def __init__(self, **kwargs: object) -> None:
            pass

        def execute(self, deps: object) -> None:
            raise RuntimeError("boom")

    monkeypatch.setattr(actions_mod, "LaunchAction", _BoomLaunch)
    secret = _seed_launch_secret(tmp_path)
    store = _FakeStore(intents={"i1": _launch_intent(8, secret=secret)})
    _drain(store, _FakeWriter(), kanban_root=str(tmp_path))
    assert store.reserved == [8]
    assert store.released == [8]  # slot released on failure
    assert store.results["i1"]["state"] == "rejected"
    assert "i1" not in store.intents


# ---------------------------------------------------------------------------
# Reviewed defects (intents.py): FIX 1 (no-overwrite on fetch fail), FIX 2
# (explicit freeform-merge vs body-replace), FIX 3 (coherence gate on merge),
# FIX 4 (launch op_token guard against agent-forged ad-hoc launches).
# ---------------------------------------------------------------------------


def _marker_body() -> str:
    """A body carrying a status block + a roadmap marker + freeform (the protected regions)."""
    return (
        "<!-- kanban:status:begin -->\nWAITING\n<!-- kanban:status:end -->\n\n"
        "Original freeform prose.\n\n**roadmap**: A1"
    )


def _fetch_returning(writer: _FakeWriter, *, body: str, title: str) -> None:
    """Patch the writer fake's fetch_issue to return a specific body + title for #8."""

    def _fetch(issue_number: int):  # type: ignore[no-untyped-def]
        from kanbanmate.adapters.github.types import IssueRef

        return IssueRef(node_id=f"NODE_{issue_number}", number=issue_number, title=title, body=body)

    writer.fetch_issue = _fetch  # type: ignore[method-assign]


def test_ticket_edit_merge_rejects_on_fetch_failure_never_overwrites() -> None:
    """FIX 1: a fetch failure on the MERGE path REJECTS — it must NEVER write (no region loss).

    The old code swallowed the fetch error and merged against an EMPTY current body, writing only the
    new freeform — permanently deleting the real status block + markers + ## Brainstorm. The fix
    refuses the write entirely (mirroring the SPA route's 404).
    """
    writer = _FakeWriter(missing_issues=frozenset({8}))
    store = _FakeStore(
        intents={
            "i1": {
                "kind": "ticket_edit",
                "issue": 8,
                "args": {"freeform": "New prose."},
                "requested_at": 1.0,
            }
        }
    )
    _drain(store, writer)
    assert writer.edited == []  # CRITICAL: nothing written → no region loss
    assert store.results["i1"]["state"] == "rejected"
    assert "not found" in str(store.results["i1"]["detail"])
    assert "i1" not in store.intents


def test_ticket_edit_merge_fetches_issue_only_once() -> None:
    """FIX 1: the merge path fetches the issue ONCE (node id + body + title), not twice."""
    calls: list[int] = []
    writer = _FakeWriter()
    orig = writer.fetch_issue

    def _counting(issue_number: int):  # type: ignore[no-untyped-def]
        calls.append(issue_number)
        return orig(issue_number)

    writer.fetch_issue = _counting  # type: ignore[method-assign]
    store = _FakeStore(
        intents={
            "i1": {
                "kind": "ticket_edit",
                "issue": 8,
                "args": {"freeform": "x"},
                "requested_at": 1.0,
            }
        }
    )
    _drain(store, writer)
    assert calls == [8]  # exactly one fetch (was two: _resolve_node_id + the body fetch)
    assert store.results["i1"]["state"] == "done"


def test_ticket_edit_body_is_full_replace_not_merge() -> None:
    """FIX 2: ``args["body"]`` (the CLI path) is a FULL replace — markers are NOT re-appended.

    Regression: the executor briefly treated every edit as freeform-only, so the CLI ``--body`` (a
    complete intended body) had STALE markers re-appended and its content mangled.
    """
    writer = _FakeWriter()
    _fetch_returning(writer, body=_marker_body(), title="[A1] T")
    store = _FakeStore(
        intents={
            "i1": {
                "kind": "ticket_edit",
                "issue": 8,
                "args": {"body": "Complete new body, no markers."},
                "requested_at": 1.0,
            }
        }
    )
    _drain(store, writer)
    assert writer.edited == [("NODE_8", "Complete new body, no markers.")]  # verbatim, no merge
    assert store.results["i1"]["state"] == "done"


def test_ticket_edit_freeform_merges_preserving_status_block() -> None:
    """FIX 2: ``args["freeform"]`` (the SPA path) MERGES — protected regions survive."""
    writer = _FakeWriter()
    _fetch_returning(writer, body=_marker_body(), title="[A1] T")
    store = _FakeStore(
        intents={
            "i1": {
                "kind": "ticket_edit",
                "issue": 8,
                "args": {"freeform": "Edited prose only."},
                "requested_at": 1.0,
            }
        }
    )
    _drain(store, writer)
    assert len(writer.edited) == 1
    updated = writer.edited[0][1]
    assert "Edited prose only." in updated
    assert "kanban:status:begin" in updated  # status block preserved
    assert "**roadmap**: A1" in updated  # marker preserved
    assert "Original freeform prose." not in updated  # old freeform replaced


def test_ticket_edit_merge_rejected_on_roadmap_title_incoherence() -> None:
    """FIX 3: the merge path runs the same coherence gate the SPA route enforces (reject on mismatch).

    A merged body whose ``**roadmap**`` code disagrees with the title ``[CODE]`` is refused — the
    ticket↔roadmap binding must stay coherent (§29.1).
    """
    writer = _FakeWriter()
    # Body marker says A1; title bracket says B2 → incoherent → the merge must be refused.
    _fetch_returning(writer, body=_marker_body(), title="[B2] T")
    store = _FakeStore(
        intents={
            "i1": {
                "kind": "ticket_edit",
                "issue": 8,
                "args": {"freeform": "New prose."},
                "requested_at": 1.0,
            }
        }
    )
    _drain(store, writer)
    assert writer.edited == []  # refused → not written
    assert store.results["i1"]["state"] == "rejected"
    assert "roadmap" in str(store.results["i1"]["detail"]).lower()
    assert "i1" not in store.intents


def test_launch_without_op_token_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """FIX 4: a token-LESS launch for an idle issue (the agent-forged case) is REJECTED.

    Authority for an idle issue derives to OPERATOR, so the running-set check does not stop a bridled
    agent from enqueuing a launch. Without a valid op_token (which only the UI can mint from the
    runtime-root secret) the launch is refused — no slot reserved, no action constructed.
    """
    import kanbanmate.app.actions as actions_mod

    _SpyLaunch.last = None
    monkeypatch.setattr(actions_mod, "LaunchAction", _SpyLaunch)
    _seed_launch_secret(tmp_path)  # secret exists, but the intent carries NO token
    store = _FakeStore(intents={"i1": _launch_intent(8)})  # no secret/op_token → token-less
    _drain(store, _FakeWriter(), kanban_root=str(tmp_path))
    assert store.results["i1"]["state"] == "rejected"
    assert "op_token" in str(store.results["i1"]["detail"])
    assert _SpyLaunch.last is None  # never constructed
    assert store.reserved == []  # never reserved a slot
    assert "i1" not in store.intents


def test_launch_with_forged_op_token_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """FIX 4: a launch carrying a WRONG op_token (a guessed/forged value) is rejected."""
    import kanbanmate.app.actions as actions_mod

    _SpyLaunch.last = None
    monkeypatch.setattr(actions_mod, "LaunchAction", _SpyLaunch)
    _seed_launch_secret(tmp_path)
    store = _FakeStore(intents={"i1": _launch_intent(8, op_token="deadbeef" * 8)})
    _drain(store, _FakeWriter(), kanban_root=str(tmp_path))
    assert store.results["i1"]["state"] == "rejected"
    assert _SpyLaunch.last is None
    assert store.reserved == []


def test_launch_op_token_bound_to_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """FIX 4: a token minted for one profile cannot be replayed to escalate to another profile."""
    import kanbanmate.app.actions as actions_mod
    from kanbanmate.app.intents import compute_launch_token

    _SpyLaunch.last = None
    monkeypatch.setattr(actions_mod, "LaunchAction", _SpyLaunch)
    secret = _seed_launch_secret(tmp_path)
    # Token minted for `docs`, but the intent requests `dev` → mismatch → rejected.
    token_for_docs = compute_launch_token(secret, 8, "docs")
    store = _FakeStore(intents={"i1": _launch_intent(8, profile="dev", op_token=token_for_docs)})
    _drain(store, _FakeWriter(), kanban_root=str(tmp_path))
    assert store.results["i1"]["state"] == "rejected"
    assert _SpyLaunch.last is None


def test_launch_rejected_when_no_secret_minted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """FIX 4: with NO launch secret on disk, no launch can be proven operator-originated → reject.

    Fail-CLOSED: a missing secret must never silently trust a launch.
    """
    import kanbanmate.app.actions as actions_mod

    _SpyLaunch.last = None
    monkeypatch.setattr(actions_mod, "LaunchAction", _SpyLaunch)
    # tmp_path has NO launch_secret file; even a (necessarily un-verifiable) token is refused.
    store = _FakeStore(intents={"i1": _launch_intent(8, op_token="anything")})
    _drain(store, _FakeWriter(), kanban_root=str(tmp_path))
    assert store.results["i1"]["state"] == "rejected"
    assert _SpyLaunch.last is None
    assert store.reserved == []

"""Tests for the daemon-side intent executor (:mod:`kanbanmate.app.intents`, cockpit PR2).

Drives ``drain_intents`` against in-memory fakes, asserting the load-bearing invariants: operator move
executes (move_card + baseline advance + done result + cleared), unknown-column / off-board rejection,
agent re-fire guard (authority derived from the running set), the PAUSE matrix (agent held / operator
runs), same-issue ordering (earliest runs, rest deferred), optimistic idempotence, and poison/raise
fail-soft.
"""

from __future__ import annotations

from dataclasses import dataclass, field

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

    def list_running(self) -> list[TicketState]:
        return list(self.running)

    override_enum: str | None = None
    override_note: str | None = None

    def set_status_override_enum(self, status: str | None) -> None:
        self.override_enum = status

    def set_status_override_note(self, note: str | None) -> None:
        self.override_note = note


def _deps(store: _FakeStore, writer: _FakeWriter) -> Deps:
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


def _drain(store: _FakeStore, writer: _FakeWriter, *, kill_switch: bool = False) -> dict[str, str]:
    """Run drain_intents with a Backlog snapshot for #8 and #9; return next_columns."""
    next_columns: dict[str, str] = {}
    drain_intents(
        _deps(store, writer),
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
    assert next_columns["PVTI_8"] == "Done"  # baseline advanced
    assert store.results["i1"]["state"] == "done"
    assert "i1" not in store.intents  # cleared


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

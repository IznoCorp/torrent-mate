"""Tests for the MCP read serializers (:mod:`kanbanmate.mcp.resources`, conduit Phase 2).

Each serializer is exercised against small in-memory fakes pre-seeded with REAL values (real column
KEYS, a snapshot with ≥1 ``Ticket``, a non-empty events ring, a live ``TicketState``). The produced
``dict`` is asserted against the documented shape — never two empty sides. The fakes mirror the
``tests/cli/test_state.py`` style (the ``board`` serializer reuses the ``cli.state.state`` shell).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from kanbanmate.adapters.github.types import IssueContext
from kanbanmate.core.domain import BoardSnapshot, Ticket
from kanbanmate.mcp import resources
from kanbanmate.ports.store import TicketState, TicketStatus


@dataclass
class _FakeBoardReader:
    """A board reader whose ``snapshot`` / ``issue_context`` return fixed values."""

    snapshot_obj: BoardSnapshot
    contexts: dict[int, IssueContext] = field(default_factory=dict)

    def snapshot(self) -> BoardSnapshot:
        return self.snapshot_obj

    def issue_context(self, number: int) -> IssueContext:
        return self.contexts[number]


@dataclass
class _FakeStore:
    """An in-memory store implementing exactly the read methods the resources touch."""

    running: list[TicketState] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    last_status: str | None = None
    queued_ids: tuple[int, ...] = ()
    queued_payloads: dict[int, dict[str, object]] = field(default_factory=dict)
    paused: bool = False

    # --- board() (via cli.state.state) ---
    def list_running(self) -> list[TicketState]:
        return list(self.running)

    def read_status_events(self) -> tuple[dict[str, object], ...]:
        return tuple(self.events)

    def get_status_last_enum(self) -> str | None:
        return self.last_status

    # --- queue() ---
    def dequeue_pending(self) -> tuple[int, ...]:
        return self.queued_ids

    def load_queued(self, issue_number: int) -> dict[str, object] | None:
        return self.queued_payloads.get(issue_number)

    def kill_switch_active(self) -> bool:
        return self.paused


def _ticket(n: int, col: str) -> Ticket:
    return Ticket(item_id=f"PVTI_{n}", issue_number=n, title=f"t{n}", column_key=col)


def _running(n: int = 7) -> TicketState:
    return TicketState(
        issue_number=n,
        item_id=f"PVTI_{n}",
        session_id="sess",
        status=TicketStatus.RUNNING,
        heartbeat=990.0,
        stage="InProgress",
        profile="dev",
        mode="auto",
        started=900.0,
        worktree="/tmp/wt-7",
        retries=1,
    )


def _reader() -> _FakeBoardReader:
    return _FakeBoardReader(
        BoardSnapshot(
            tickets=(_ticket(7, "InProgress"), _ticket(8, "Backlog")),
            fetched_at=0.0,
        ),
        contexts={
            7: IssueContext(
                body="the spec body",
                comments=("first comment", "second comment"),
                linked_issue_body="the linked design",
            )
        },
    )


def _store() -> _FakeStore:
    return _FakeStore(
        running=[_running(7)],
        events=[
            {"ts": 1000.0, "kind": "launch", "issue": 7, "detail": "x"},
            {"ts": 2000.0, "kind": "teardown", "issue": 8, "detail": "done"},
        ],
        last_status="WAITING",
        queued_ids=(8,),
        queued_payloads={8: {"stage": "Backlog", "enqueued_at": 1500.0, "item_id": "PVTI_8"}},
    )


def test_board_serializes_unified_state(tmp_path: Path) -> None:
    """board() returns the stable unified shape (health/paused/board/agents/queue/events/daemon)."""
    data = resources.board(_reader(), _store(), root=tmp_path)  # type: ignore[arg-type]
    assert data["health"] == "WAITING"
    assert data["paused"] is False
    assert data["board"] == {"columns": {"InProgress": 1, "Backlog": 1}, "total": 2}
    agents = cast("list[dict[str, object]]", data["agents"])
    assert [a["issue_number"] for a in agents] == [7]
    # The events ring is rendered newest-first by the shell (teardown #8 above launch #7).
    events_list = cast("list[dict[str, object]]", data["events"])
    assert events_list[0]["issue"] == 8
    assert events_list[1]["issue"] == 7
    assert "daemon" in data


def test_ticket_crosses_context_with_snapshot() -> None:
    """ticket() carries the issue body, comments, linked body + the snapshot title/column key."""
    data = resources.ticket(_reader(), 7)  # type: ignore[arg-type]
    assert data == {
        "issue_number": 7,
        "title": "t7",
        "column_key": "InProgress",  # the REAL column KEY, not a display label
        "body": "the spec body",
        "comments": ["first comment", "second comment"],
        "linked_issue_body": "the linked design",
    }


def test_agents_serializes_live_ticketstate() -> None:
    """agents() returns one row per live TicketState with its real fields (status as the enum value)."""
    rows = resources.agents(_store())  # type: ignore[arg-type]
    assert len(rows) == 1
    row = rows[0]
    assert row["issue_number"] == 7
    assert row["item_id"] == "PVTI_7"
    assert row["session_id"] == "sess"
    assert row["status"] == "running"  # TicketStatus.RUNNING.value
    assert row["heartbeat"] == 990.0
    assert row["stage"] == "InProgress"
    assert row["profile"] == "dev"
    assert row["mode"] == "auto"
    assert row["worktree"] == "/tmp/wt-7"
    assert row["retries"] == 1


def test_queue_crosses_pending_with_marker_payload() -> None:
    """queue() returns one row per pending ticket with its stage + enqueued_at marker fields."""
    rows = resources.queue(_store())  # type: ignore[arg-type]
    assert rows == [{"issue_number": 8, "stage": "Backlog", "enqueued_at": 1500.0}]


def test_health_returns_last_enum() -> None:
    """health() surfaces the last-posted status enum."""
    assert resources.health(_store()) == "WAITING"  # type: ignore[arg-type]


def test_events_returns_ring_newest_first() -> None:
    """events() returns the recent-events ring newest-first as plain dicts."""
    rows = resources.events(_store())  # type: ignore[arg-type]
    assert [e["issue"] for e in rows] == [8, 7]
    assert rows[0] == {"ts": 2000.0, "kind": "teardown", "issue": 8, "detail": "done"}

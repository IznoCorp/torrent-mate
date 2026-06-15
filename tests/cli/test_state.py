"""Tests for the read-only unified ``kanban state`` view (:mod:`kanbanmate.cli.state`, cockpit PR1).

``state`` extends the existing ``status`` read model with the recent-events ring + the health pill
(read off the daemon's ``status/last_status`` marker) + a ``--json`` machine shape. These tests drive
the pure ``build_state`` aggregation + the two renderers against small in-memory fakes (mirroring the
``test_status`` fake style); the imperative ``state()`` shell is covered by the CLI smoke at the gate.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from kanbanmate.cli.state import build_state, render_state_human, render_state_json
from kanbanmate.cli.status import QueuedRow
from kanbanmate.core.domain import BoardSnapshot, Ticket
from kanbanmate.ports.store import TicketState, TicketStatus


@dataclass
class _FakeBoardReader:
    """A board reader whose ``snapshot`` returns a fixed :class:`BoardSnapshot`."""

    snapshot_obj: BoardSnapshot

    def snapshot(self) -> BoardSnapshot:
        return self.snapshot_obj


@dataclass
class _FakeStore:
    """An in-memory store implementing exactly the read methods ``build_state`` touches."""

    running: list[TicketState] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    last_status: str | None = None

    def list_running(self) -> list[TicketState]:
        return list(self.running)

    def read_status_events(self) -> tuple[dict[str, object], ...]:
        return tuple(self.events)

    def get_status_last_enum(self) -> str | None:
        return self.last_status


def _ticket(n: int, col: str) -> Ticket:
    return Ticket(item_id=f"PVTI_{n}", issue_number=n, title=f"t{n}", column_key=col)


def _running(n: int = 7, *, stage: str = "InProgress", heartbeat: float = 990.0) -> TicketState:
    return TicketState(
        issue_number=n,
        item_id=f"PVTI_{n}",
        session_id="sess",
        status=TicketStatus.RUNNING,
        heartbeat=heartbeat,
        stage=stage,
        profile="dev",
        started=900.0,
    )


def _reader() -> _FakeBoardReader:
    return _FakeBoardReader(
        BoardSnapshot(
            tickets=(_ticket(7, "InProgress"), _ticket(8, "Backlog"), _ticket(9, "Backlog")),
            fetched_at=0.0,
        )
    )


def _store() -> _FakeStore:
    return _FakeStore(
        running=[_running(7)],
        events=[
            {"ts": 1000.0, "kind": "launch", "issue": 7, "detail": "x"},
            {"ts": 2000.0, "kind": "teardown", "issue": 8, "detail": "done"},
        ],
        last_status="AT_RISK",
    )


def test_build_state_aggregates_status_events_health() -> None:
    """build_state crosses the status read model with the events ring + the health-pill marker."""
    report = build_state(_reader(), _store(), now=3000.0)  # type: ignore[arg-type]
    assert report.status.total_cards == 3
    assert report.status.column_counts["Backlog"] == 2
    assert report.health == "AT_RISK"
    assert tuple(e["kind"] for e in report.events) == ("launch", "teardown")


def test_render_state_json_shape_and_events_newest_first() -> None:
    """The JSON shape carries health/board/agents/queue/events; events are newest-first."""
    report = build_state(
        _reader(),  # type: ignore[arg-type]
        _store(),  # type: ignore[arg-type]
        queued=[QueuedRow(issue_number=8, stage="Backlog", age=12.0)],
        now=3000.0,
    )
    data = json.loads(render_state_json(report))
    assert data["health"] == "AT_RISK"
    assert data["board"]["total"] == 3
    assert data["board"]["columns"]["Backlog"] == 2
    assert [a["issue_number"] for a in data["agents"]] == [7]
    assert data["queue"][0]["issue_number"] == 8
    # The ring is stored oldest-first; the JSON renders newest-first (teardown #8 above launch #7).
    assert data["events"][0]["issue"] == 8
    assert data["events"][1]["issue"] == 7


def test_render_state_human_includes_health_and_events_newest_first() -> None:
    """The human render shows the board, a Health line, and a newest-first Recent events block."""
    out = render_state_human(build_state(_reader(), _store(), now=3000.0))  # type: ignore[arg-type]
    assert "AT_RISK" in out
    assert "Recent events" in out
    # Within the events block, the newest event (teardown #8) is listed above the older launch (#7).
    events_block = out[out.index("Recent events") :]
    assert events_block.index("#8") < events_block.index("#7")


def test_health_defaults_to_dash_and_null_when_unset() -> None:
    """With no posted enum yet, JSON health is null and the human render shows an em-dash."""
    store = _store()
    store.last_status = None
    report = build_state(_reader(), store, now=3000.0)  # type: ignore[arg-type]
    assert json.loads(render_state_json(report))["health"] is None
    assert "—" in render_state_human(report)

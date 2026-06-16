"""Tests for :mod:`kanbanmate.cli.status`, :mod:`kanbanmate.cli.sessions`, and
:mod:`kanbanmate.cli.reset`.

``status`` crosses a board snapshot with persisted running state into a per-column count table plus
a running-agents section; ``sessions`` crosses persisted running state with live tmux to flag reaper
candidates; ``reset`` archives the kanban root aside without deleting it. Every test injects fakes
(no network, no tmux, no real ``~/.kanban``) and asserts on the returned read-model / rendered text.
"""

from __future__ import annotations

import time
from pathlib import Path

from kanbanmate.adapters.github.types import IssueContext
from kanbanmate.cli.reset import reset
from kanbanmate.cli.sessions import build_sessions, render_sessions, sessions
from kanbanmate.cli.status import (
    DaemonHealth,
    QueuedRow,
    build_status,
    pause,
    read_daemon_health,
    read_queued,
    render_pause,
    render_resume,
    render_status,
    resume,
    status,
)
from kanbanmate.core.domain import BoardSnapshot, Ticket
from kanbanmate.core.heartbeat import Heartbeat, render_heartbeat
from kanbanmate.ports.store import TicketState, TicketStatus


class _FakeBoardReader:
    """A scripted :class:`~kanbanmate.ports.board.BoardReader` returning a fixed snapshot."""

    def __init__(self, snapshot: BoardSnapshot) -> None:
        """Store the snapshot to return and zero the call counter."""
        self._snapshot = snapshot
        self.snapshot_calls = 0

    def cheap_probe(self) -> str:  # pragma: no cover - status never probes
        """Unused by status (it always takes a full snapshot)."""
        return "probe"

    def snapshot(self) -> BoardSnapshot:
        """Return the scripted snapshot and count the call."""
        self.snapshot_calls += 1
        return self._snapshot

    def issue_state(self, number: int) -> bool:  # noqa: ARG002
        """Stub: always returns False (status never exercises off-board deps)."""
        return False

    def issue_context(self, number: int) -> IssueContext:  # noqa: ARG002
        """Stub: empty context (status never exercises launch-prompt enrichment, 18.2)."""
        return IssueContext(body="", comments=(), linked_issue_body=None)


class _FakeStore:
    """A :class:`~kanbanmate.ports.store.StateStore` stub backed by an in-memory list."""

    def __init__(
        self,
        running: list[TicketState],
        *,
        all_states: list[TicketState] | None = None,
        queued: dict[int, dict[str, object]] | None = None,
    ) -> None:
        """Store the running and all-known states the store reports.

        Args:
            running: The states ``list_running`` returns (the reaper's view).
            all_states: The states ``list_all`` returns (the sessions report's
                view — the PoC ``_known_issues`` analogue). Defaults to
                ``running`` so existing tests that only care about running
                tickets work unchanged.
            queued: A ``{issue: payload}`` map of queue markers the operator-pane
                read crosses (``dequeue_pending`` / ``load_queued``); defaults to
                empty so existing tests see no queue.
        """
        self._running = running
        self._all = all_states if all_states is not None else running
        self._queued = queued if queued is not None else {}

    def load(self, issue_number: int) -> TicketState | None:  # pragma: no cover - unused here
        """Look up a state by issue number (unused by status/sessions)."""
        for st in self._running:
            if st.issue_number == issue_number:
                return st
        return None

    def save(self, state: TicketState) -> None:  # pragma: no cover - unused here
        """Unused by the read-only commands."""
        raise AssertionError("status/sessions must not write state")

    def touch_heartbeat(self, issue_number: int, now: float) -> None:  # pragma: no cover
        """Unused by the read-only commands."""
        raise AssertionError("status/sessions must not touch heartbeats")

    def reserve_slot(self, issue_number: int, cap: int) -> bool:  # pragma: no cover
        """Unused by the read-only commands (gate 13.5 cap gate)."""
        raise AssertionError("status/sessions must not reserve slots")

    def release_slot(self, issue_number: int) -> None:  # pragma: no cover
        """Unused by the read-only commands (slot-only release, 13.7 split)."""
        raise AssertionError("status/sessions must not release slots")

    def purge_ticket(  # pragma: no cover
        self, issue_number: int, *, keep_budgets: bool = False
    ) -> None:
        """Unused by the read-only commands (teardown purge, 13.7 split / 13.8 keep_budgets)."""
        raise AssertionError("status/sessions must not purge tickets")

    def list_running(self) -> tuple[TicketState, ...]:
        """Return the configured running states."""
        return tuple(self._running)

    def list_all(self) -> tuple[TicketState, ...]:
        """Return every configured state (the PoC ``_known_issues`` analogue)."""
        return tuple(self._all)

    def append_dispatch(  # pragma: no cover - unused by read-only commands
        self, record: dict[str, object]
    ) -> None:
        """Unused by the read-only commands (per-dispatch audit log, 15.3)."""
        raise AssertionError("status/sessions must not append dispatch records")

    def record_agent_advance(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, *, now: float
    ) -> None:
        """Unused by the read-only commands (advance breadcrumb, 8.1.d)."""
        raise AssertionError("status/sessions must not record advances")

    def recent_agent_advance(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, *, now: float
    ) -> bool:
        """Unused by the read-only commands (advance breadcrumb, 8.1.d)."""
        raise AssertionError("status/sessions must not read advances")

    def clear_agent_advance(  # pragma: no cover - unused by read-only commands
        self, issue_number: int
    ) -> None:
        """Unused by the read-only commands (advance breadcrumb, 8.1.d)."""
        raise AssertionError("status/sessions must not clear advances")

    def record_agent_done(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, *, now: float
    ) -> None:
        """Unused by the read-only commands (done breadcrumb, #1)."""
        raise AssertionError("status/sessions must not record done")

    def recent_agent_done(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, *, now: float
    ) -> bool:
        """Unused by the read-only commands (done breadcrumb, #1)."""
        raise AssertionError("status/sessions must not read done")

    def clear_agent_done(  # pragma: no cover - unused by read-only commands
        self, issue_number: int
    ) -> None:
        """Unused by the read-only commands (done breadcrumb, #1)."""
        raise AssertionError("status/sessions must not clear done")

    def kill_switch_active(self) -> bool:  # pragma: no cover - unused by read-only commands
        """Unused by the read-only status/sessions commands."""
        return False

    def record_move_for_item(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, *, now: float
    ) -> None:
        """Unused by the read-only commands (move rate-limit, §6)."""
        return None

    def move_count_for_item_last_hour(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, *, now: float
    ) -> int:
        """Unused by the read-only commands (move rate-limit, §6)."""
        return 0

    def bump_retry(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, key: str
    ) -> int:
        """Unused by the read-only commands (fix-CI retry counter, §6)."""
        return 0

    def reset_retry(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, key: str
    ) -> None:
        """Unused by the read-only commands (fix-CI retry counter, §6)."""
        pass

    def save_script_output(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, output: str
    ) -> None:
        """Unused by the read-only commands (script-output sink, 15.6/15.7)."""
        pass

    def load_script_output(  # pragma: no cover - unused by read-only commands
        self, issue_number: int
    ) -> str:
        """Unused by the read-only commands (script-output sink, 15.6/15.7)."""
        return ""

    def enqueue_launch(  # pragma: no cover - unused by read-only commands
        self, issue_number: int, payload: object = None
    ) -> None:
        """Unused by the read-only commands (queue persistence, §7)."""
        pass

    def dequeue_pending(self) -> tuple[int, ...]:
        """Return the queued issue numbers (operator-pane read, 31.1)."""
        return tuple(self._queued)

    def load_queued(self, issue_number: int) -> dict[str, object] | None:
        """Return the queue marker payload for ``issue_number`` (operator-pane read, 31.1)."""
        return self._queued.get(issue_number)

    def clear_queued(self, issue_number: int) -> None:  # pragma: no cover
        """Unused by the read-only commands (queue persistence, §7)."""
        pass

    def get_status_update_id(self) -> str | None:  # pragma: no cover
        """Unused by the read-only commands (status-update state, phase-24)."""
        return None

    def set_status_update_id(  # pragma: no cover - unused by read-only commands
        self, status_update_id: str | None
    ) -> None:
        """Unused by the read-only commands (status-update state, phase-24)."""
        pass

    def get_status_body_hash(self) -> str | None:  # pragma: no cover
        """Unused by the read-only commands (status-update state, phase-24)."""
        return None

    def set_status_body_hash(self, body_hash: str | None) -> None:  # pragma: no cover
        """Unused by the read-only commands (status-update state, phase-24)."""
        pass

    def get_status_last_enum(self) -> str | None:  # pragma: no cover
        """Unused by the read-only commands (status-update enum marker)."""
        return None

    def set_status_last_enum(self, status: str | None) -> None:  # pragma: no cover
        """Unused by the read-only commands (status-update enum marker)."""
        pass

    def get_status_override_enum(self) -> str | None:  # pragma: no cover
        """Unused by the read-only commands (pill override marker, cockpit PR3)."""
        return None

    def set_status_override_enum(self, status: str | None) -> None:  # pragma: no cover
        """Unused by the read-only commands (pill override marker, cockpit PR3)."""
        pass

    def get_status_override_note(self) -> str | None:  # pragma: no cover
        """Unused by the read-only commands (pill override note, cockpit PR3)."""
        return None

    def set_status_override_note(self, note: str | None) -> None:  # pragma: no cover
        """Unused by the read-only commands (pill override note, cockpit PR3)."""
        pass

    def get_status_project_id(self) -> str | None:  # pragma: no cover
        """Unused by the read-only commands (status-state project binding, phase-33)."""
        return None

    def set_status_project_id(self, project_id: str | None) -> None:  # pragma: no cover
        """Unused by the read-only commands (status-state project binding, phase-33)."""
        pass

    def append_status_event(  # pragma: no cover - unused by read-only commands
        self, event: object = None
    ) -> None:
        """Unused by the read-only commands (status-update state, phase-24)."""
        pass

    def read_status_events(self) -> tuple[dict[str, object], ...]:  # pragma: no cover
        """Unused by the read-only commands (status-update state, phase-24)."""
        return ()

    def get_health_project_id(self) -> str | None:  # pragma: no cover
        """Unused by the read-only commands (Health field state, health-field)."""
        return None

    def set_health_project_id(self, project_id: str | None) -> None:  # pragma: no cover
        """Unused by the read-only commands (Health field state, health-field)."""
        pass

    def get_health_field_id(self) -> str | None:  # pragma: no cover
        """Unused by the read-only commands (Health field state, health-field)."""
        return None

    def set_health_field_id(self, field_id: str | None) -> None:  # pragma: no cover
        """Unused by the read-only commands (Health field state, health-field)."""
        pass

    def get_health_options(self) -> dict[str, str]:  # pragma: no cover
        """Unused by the read-only commands (Health field state, health-field)."""
        return {}

    def set_health_options(self, options: dict[str, str]) -> None:  # pragma: no cover
        """Unused by the read-only commands (Health field state, health-field)."""
        pass

    def get_item_health(self, item_id: str) -> str | None:  # pragma: no cover
        """Unused by the read-only commands (Health field state, health-field)."""
        return None

    def set_item_health(self, item_id: str, value: str | None) -> None:  # pragma: no cover
        """Unused by the read-only commands (Health field state, health-field)."""
        pass

    def clear_health_markers(self) -> None:  # pragma: no cover
        """Unused by the read-only commands (Health field state, health-field)."""
        pass

    def enqueue_intent(self, intent_id: str, payload: object) -> None:  # pragma: no cover
        """Unused by the read-only commands (intent queue, cockpit PR2)."""
        pass

    def load_intent(self, intent_id: str) -> dict[str, object] | None:  # pragma: no cover
        """Unused by the read-only commands (intent queue, cockpit PR2)."""
        return None

    def clear_intent(self, intent_id: str) -> None:  # pragma: no cover
        """Unused by the read-only commands (intent queue, cockpit PR2)."""
        pass

    def list_pending_intents(self) -> tuple[str, ...]:  # pragma: no cover
        """Unused by the read-only commands (intent queue, cockpit PR2)."""
        return ()

    def save_intent_result(self, intent_id: str, payload: object) -> None:  # pragma: no cover
        """Unused by the read-only commands (intent queue, cockpit PR2)."""
        pass

    def load_intent_result(self, intent_id: str) -> dict[str, object] | None:  # pragma: no cover
        """Unused by the read-only commands (intent queue, cockpit PR2)."""
        return None


class _FakeSessions:
    """A :class:`~kanbanmate.ports.workspace.Sessions` stub with scripted liveness."""

    def __init__(self, alive: dict[str, bool]) -> None:
        """Store the ``{session_name: alive}`` map and a probe log."""
        self._alive = alive
        self.probed: list[str] = []

    def launch(self, name: str, cwd: str, command: str) -> str:  # pragma: no cover - unused
        """Unused by sessions (read-only)."""
        raise AssertionError("sessions must not launch")

    def capture(self, name: str) -> str:  # pragma: no cover - unused
        """Unused by read-only status commands."""
        raise AssertionError("sessions must not capture")

    def send_text(
        self, name: str, text: str, *, literal: bool = True, enter: bool = False
    ) -> None:  # pragma: no cover - unused
        """Unused by read-only status commands."""
        raise AssertionError("sessions must not send_text")

    def is_alive(self, name: str) -> bool:
        """Record the probe and return the scripted liveness (default ``False``)."""
        self.probed.append(name)
        return self._alive.get(name, False)

    def kill(self, name: str) -> None:  # pragma: no cover - unused
        """Unused by sessions (read-only)."""
        raise AssertionError("sessions must not kill")

    def end_session(self, name: str) -> None:  # pragma: no cover - unused
        """Unused by read-only status commands (#1 Protocol member)."""
        raise AssertionError("sessions must not end_session")


def _state(
    issue: int, *, status: TicketStatus = TicketStatus.RUNNING, session: str | None = None
) -> TicketState:
    """Build a running :class:`TicketState` for the given issue."""
    return TicketState(
        issue_number=issue,
        item_id=f"PVTI_{issue}",
        session_id=session if session is not None else f"ticket-{issue}",
        status=status,
        heartbeat=1000.0,
    )


def _snapshot(*tickets: Ticket) -> BoardSnapshot:
    """Wrap tickets into a :class:`BoardSnapshot`."""
    return BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


def test_status_counts_cards_per_column() -> None:
    """``build_status`` counts cards per column and totals them."""
    reader = _FakeBoardReader(
        _snapshot(
            Ticket(item_id="A", issue_number=1, title="a", column_key="Backlog"),
            Ticket(item_id="B", issue_number=2, title="b", column_key="Backlog"),
            Ticket(item_id="C", issue_number=3, title="c", column_key="InProgress"),
        )
    )
    report = build_status(reader, _FakeStore([]))

    assert report.column_counts == {"Backlog": 2, "InProgress": 1}
    assert report.total_cards == 3
    assert report.agents == []


def test_status_lists_running_agents_sorted() -> None:
    """``build_status`` lists running agents from the store, issue-number ascending."""
    reader = _FakeBoardReader(_snapshot())
    store = _FakeStore([_state(9), _state(4)])

    report = build_status(reader, store)

    assert [row.issue_number for row in report.agents] == [4, 9]
    assert report.agents[0].session_id == "ticket-4"
    assert report.agents[0].status == "running"


def test_status_renders_expected_table() -> None:
    """``render_status``/``status`` print the per-column counts and the running-agent rows."""
    reader = _FakeBoardReader(
        _snapshot(Ticket(item_id="A", issue_number=1, title="a", column_key="Backlog"))
    )
    store = _FakeStore([_state(7)])

    rendered = status(reader, store, ttl=120.0)

    # With no root crossed (board-only view), the rendered text is the pure two-section table; the
    # only ``now``-dependent field (heartbeat age) is never rendered, so it matches a fixed-now build.
    assert rendered == render_status(build_status(reader, store, now=1000.0))
    assert "Board columns:" in rendered
    assert "Backlog" in rendered
    assert "TOTAL" in rendered
    assert "Running agents:" in rendered
    assert "#7" in rendered
    assert "session=ticket-7" in rendered


def test_status_agent_row_resolves_current_column_from_snapshot() -> None:
    """#9: each running agent's CURRENT column is resolved from the live snapshot by issue number.

    The PoC's per-ticket ``#issue column status session_uuid`` tuple is recovered: a running
    ticket that is on the board reports its column, while a running ticket absent from the snapshot
    reports ``None`` (rendered ``?``).
    """
    reader = _FakeBoardReader(
        _snapshot(
            Ticket(item_id="A", issue_number=7, title="a", column_key="InProgress"),
            Ticket(item_id="B", issue_number=1, title="b", column_key="Backlog"),
        )
    )
    # Issue 7 is on the board (column resolvable); issue 9 is a running agent whose card
    # is no longer on the snapshot (column → None → "?").
    store = _FakeStore([_state(7), _state(9)])

    report = build_status(reader, store)

    by_issue = {row.issue_number: row for row in report.agents}
    assert by_issue[7].column_key == "InProgress"
    assert by_issue[9].column_key is None


def test_status_running_section_renders_column_session_status() -> None:
    """#9: the running-agents section renders column + session + status per running ticket."""
    reader = _FakeBoardReader(
        _snapshot(Ticket(item_id="A", issue_number=7, title="a", column_key="InProgress"))
    )
    store = _FakeStore([_state(7, session="ticket-7"), _state(9)])

    rendered = render_status(build_status(reader, store))

    # On-board running ticket: explicit column from the snapshot, session uuid, status.
    assert f"#7  column=InProgress  session=ticket-7  status={TicketStatus.RUNNING}" in rendered
    # Off-board running ticket: column unresolved → "?", but still shown (never blank).
    assert f"#9  column=?  session=ticket-9  status={TicketStatus.RUNNING}" in rendered


def test_status_empty_board_renders_none() -> None:
    """An empty board and no agents render explicit (none) markers, never blank."""
    rendered = status(_FakeBoardReader(_snapshot()), _FakeStore([]), ttl=120.0)

    assert "Board columns:" in rendered
    assert "Running agents:" in rendered
    # Board-only view (no root): the queued section is NOT rendered, so exactly the two original
    # ``(none)`` markers (empty board + no agents) appear.
    assert rendered.count("(none)") == 2


# ---------------------------------------------------------------------------
# operator pane (31.1): paused banner / degraded / daemon health / queue / attach hint
# ---------------------------------------------------------------------------


def test_status_renders_paused_banner_and_attach_hints(tmp_path: Path) -> None:
    """A PAUSE sentinel renders the banner and each agent line carries a tmux attach hint (31.1)."""
    root = tmp_path / ".kanban"
    root.mkdir()
    (root / "PAUSE").touch()  # kill-switch engaged
    reader = _FakeBoardReader(
        _snapshot(Ticket(item_id="A", issue_number=7, title="a", column_key="InProgress"))
    )
    store = _FakeStore([_state(7, session="ticket-7")])

    rendered = status(reader, store, root=root, ttl=120.0)

    assert "PAUSED" in rendered
    assert "kill-switch engaged" in rendered
    # Concrete drop-in hint per agent (31.1).
    assert "attach: tmux attach -t ticket-7" in rendered
    # The queue section is rendered (operator pane active) and shows (none) when empty.
    assert "Queued (waiting for a free slot):" in rendered


def test_status_renders_degraded_and_failing_daemon(tmp_path: Path) -> None:
    """A DEGRADED breadcrumb + a failing heartbeat marker surface on the pane (31.1)."""
    root = tmp_path / ".kanban"
    root.mkdir()
    (root / "DEGRADED").write_text("auth HTTP 401: token invalid", encoding="utf-8")
    # A heartbeat marker with 3 consecutive failures → FAILING even though it is fresh.
    fresh_failing = Heartbeat(ts=time.time(), last_tick_ok=False, consecutive_failures=3)
    (root / "daemon.heartbeat").write_text(render_heartbeat(fresh_failing), encoding="utf-8")

    rendered = status(_FakeBoardReader(_snapshot()), _FakeStore([]), root=root, ttl=120.0)

    assert "DEGRADED — auth HTTP 401: token invalid" in rendered
    assert "Daemon: FAILING" in rendered
    assert "failures=3" in rendered


def test_status_renders_queued_tickets_with_ages(tmp_path: Path) -> None:
    """Queued cards render with their stage + age so they are not mistaken for dead cards (31.1)."""
    root = tmp_path / ".kanban"
    root.mkdir()
    now = 5000.0
    store = _FakeStore(
        [],
        queued={
            12: {"item_id": "PVTI_12", "stage": "Plan", "enqueued_at": now - 90.0},
            5: {"item_id": "PVTI_5", "stage": "Design"},  # old-format: no enqueued_at → age None
        },
    )

    rows = read_queued(store, now)

    # Issue-number ascending; ages crossed from enqueued_at (None when the marker lacks it).
    assert [r.issue_number for r in rows] == [5, 12]
    by_issue = {r.issue_number: r for r in rows}
    assert by_issue[12].stage == "Plan"
    assert by_issue[12].age == 90.0
    assert by_issue[5].age is None

    # The ``status`` shell uses real wall-clock time, so assert structure (stage + presence), not
    # the exact issue-12 age; the old-format issue-5 marker always renders ``queued=?``.
    rendered = status(_FakeBoardReader(_snapshot()), store, root=root, ttl=120.0)
    assert "#12  stage=Plan  queued=" in rendered
    assert "#5  stage=Design  queued=?" in rendered


def test_read_daemon_health_absent_marker(tmp_path: Path) -> None:
    """A missing heartbeat marker reports the daemon as not-present with a note (31.1)."""
    health = read_daemon_health(tmp_path, now=1000.0, ttl=120.0)

    assert health.present is False
    assert health.ok is False
    assert "no heartbeat marker" in health.note


def test_read_daemon_health_fresh_ok(tmp_path: Path) -> None:
    """A fresh, zero-failure marker reports OK with the crossed age (31.1)."""
    (tmp_path / "daemon.heartbeat").write_text(
        render_heartbeat(Heartbeat(ts=1000.0, last_tick_ok=True, consecutive_failures=0)),
        encoding="utf-8",
    )

    health = read_daemon_health(tmp_path, now=1010.0, ttl=120.0)

    assert health.present is True
    assert health.ok is True
    assert health.age == 10.0


def test_read_daemon_health_stale_not_ok(tmp_path: Path) -> None:
    """A marker older than the TTL is not OK even with zero failures (31.1)."""
    (tmp_path / "daemon.heartbeat").write_text(
        render_heartbeat(Heartbeat(ts=1000.0, last_tick_ok=True, consecutive_failures=0)),
        encoding="utf-8",
    )

    health = read_daemon_health(tmp_path, now=2000.0, ttl=120.0)  # 1000s old > 120s TTL

    assert health.present is True
    assert health.ok is False


def test_read_daemon_health_unparseable_marker(tmp_path: Path) -> None:
    """A garbage heartbeat marker degrades to a parse note rather than crashing (31.1)."""
    (tmp_path / "daemon.heartbeat").write_text("not-json-not-a-float", encoding="utf-8")

    health = read_daemon_health(tmp_path, now=1000.0, ttl=120.0)

    assert health.present is True
    assert health.ok is False
    assert "cannot parse" in health.note


def test_render_banner_omitted_without_pane_data() -> None:
    """The board-only render (no operator-pane signals) has no banner or queue section (31.1)."""
    reader = _FakeBoardReader(
        _snapshot(Ticket(item_id="A", issue_number=1, title="a", column_key="Backlog"))
    )
    rendered = render_status(build_status(reader, _FakeStore([]), now=1000.0))

    assert "PAUSED" not in rendered
    assert "Daemon:" not in rendered
    assert "Queued" not in rendered


def test_daemon_health_value_object_defaults() -> None:
    """:class:`DaemonHealth` / :class:`QueuedRow` carry sane defaults for the pure path (31.1)."""
    assert DaemonHealth(present=False).ok is False
    assert QueuedRow(issue_number=1, stage="Plan").age is None


# ---------------------------------------------------------------------------
# pause / resume (31.1)
# ---------------------------------------------------------------------------


def test_pause_creates_sentinel_and_is_idempotent(tmp_path: Path) -> None:
    """``pause`` creates the PAUSE sentinel; a second pause is a no-op (31.1)."""
    root = tmp_path / ".kanban"
    root.mkdir()

    first = pause(root)
    assert first.paused is True
    assert first.changed is True
    assert (root / "PAUSE").exists()
    assert "ENGAGED" in render_pause(first)

    second = pause(root)
    assert second.paused is True
    assert second.changed is False
    assert "already paused" in render_pause(second)


def test_resume_removes_sentinel_and_is_idempotent(tmp_path: Path) -> None:
    """``resume`` removes the PAUSE sentinel; resuming a non-paused root is a no-op (31.1)."""
    root = tmp_path / ".kanban"
    root.mkdir()
    (root / "PAUSE").touch()

    first = resume(root)
    assert first.paused is False
    assert first.changed is True
    assert not (root / "PAUSE").exists()
    assert "RELEASED" in render_resume(first)

    second = resume(root)
    assert second.paused is False
    assert second.changed is False
    assert "not paused" in render_resume(second)


# ---------------------------------------------------------------------------
# sessions
# ---------------------------------------------------------------------------


def test_sessions_flags_alive_and_dead() -> None:
    """``build_sessions`` marks a live session alive, a gone running session DEAD,
    and neither as stopped."""
    store = _FakeStore([_state(1, session="ticket-1"), _state(2, session="ticket-2")])
    agent_sessions = _FakeSessions({"ticket-1": True, "ticket-2": False})

    report = build_sessions(store, agent_sessions)

    by_issue = {row.issue_number: row for row in report.rows}
    assert by_issue[1].alive is True and by_issue[1].dead is False and by_issue[1].stopped is False
    assert by_issue[2].alive is False and by_issue[2].dead is True and by_issue[2].stopped is False
    assert agent_sessions.probed == ["ticket-1", "ticket-2"]


def test_sessions_renders_dead_tsv() -> None:
    """``sessions`` renders the PoC TSV with the DEAD flag for a gone running session."""
    store = _FakeStore([_state(2, session="ticket-2")])
    agent_sessions = _FakeSessions({"ticket-2": False})

    rendered = sessions(store, agent_sessions)

    assert rendered == render_sessions(build_sessions(store, agent_sessions))
    assert rendered == "#2\tticket-2\tDEAD\trunning"


def test_sessions_empty_renders_none() -> None:
    """No persisted tickets renders an explicit (none)."""
    rendered = sessions(_FakeStore([]), _FakeSessions({}))

    assert rendered == "(none)"


def test_sessions_stopped_bucket() -> None:
    """A non-running persisted ticket with a gone session is flagged ``stopped``.

    This is the restored third bucket — the PoC parity assertion
    (``reports.py:56-58``).
    """
    idle = _state(3, status=TicketStatus.IDLE, session="ticket-3")
    store = _FakeStore([], all_states=[idle])
    agent_sessions = _FakeSessions({"ticket-3": False})

    report = build_sessions(store, agent_sessions)

    assert len(report.rows) == 1
    row = report.rows[0]
    assert row.issue_number == 3
    assert row.alive is False
    assert row.dead is False
    assert row.stopped is True
    assert row.flag == "stopped"


def test_sessions_tsv_format_exact() -> None:
    """The rendered line is the exact PoC TSV ``#N\\t<tmux>\\t<flag>\\t<status>``
    with literal tab separators."""
    live = _state(1, session="ticket-1")
    dead = _state(2, session="ticket-2")
    idle = _state(3, status=TicketStatus.IDLE, session="ticket-3")
    store = _FakeStore([], all_states=[live, dead, idle])
    agent_sessions = _FakeSessions(
        {
            "ticket-1": True,
            "ticket-2": False,
            "ticket-3": False,
        }
    )

    rendered = render_sessions(build_sessions(store, agent_sessions))

    lines = rendered.split("\n")
    assert lines[0] == "#1\tticket-1\tlive\trunning"
    assert lines[1] == "#2\tticket-2\tDEAD\trunning"
    assert lines[2] == "#3\tticket-3\tstopped\tidle"


def test_sessions_ascending_order() -> None:
    """Rows are issue-number ascending across mixed statuses."""
    dead = _state(10, session="ticket-10")
    live = _state(2, session="ticket-2")
    idle = _state(7, status=TicketStatus.IDLE, session="ticket-7")
    store = _FakeStore([], all_states=[dead, live, idle])
    agent_sessions = _FakeSessions(
        {
            "ticket-2": True,
            "ticket-10": False,
            "ticket-7": False,
        }
    )

    report = build_sessions(store, agent_sessions)

    assert [row.issue_number for row in report.rows] == [2, 7, 10]
    assert [row.flag for row in report.rows] == ["live", "stopped", "DEAD"]


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


def test_reset_archives_root_without_deleting(tmp_path: Path) -> None:
    """``reset`` renames the root aside to a deterministic backup, preserving its content."""
    root = tmp_path / ".kanban"
    root.mkdir()
    (root / "token").write_text("SECRET", encoding="utf-8")

    result = reset(root, suffix="20260604")

    assert result.archived is True
    assert result.backup == tmp_path / ".kanban.bak-20260604"
    # Non-destructive: the original is gone but the backup holds the exact content.
    assert not root.exists()
    assert (result.backup / "token").read_text(encoding="utf-8") == "SECRET"


def test_reset_no_root_is_noop(tmp_path: Path) -> None:
    """``reset`` on an absent root is a clean no-op (nothing archived)."""
    root = tmp_path / "absent"

    result = reset(root, suffix="20260604")

    assert result.archived is False
    assert result.backup is None


def test_reset_does_not_clobber_existing_backup(tmp_path: Path) -> None:
    """A second reset with the same suffix appends a counter rather than overwriting."""
    root = tmp_path / ".kanban"
    root.mkdir()
    # Pre-create the would-be backup so the resolver must pick the -1 variant.
    (tmp_path / ".kanban.bak-20260604").mkdir()

    result = reset(root, suffix="20260604")

    assert result.backup == tmp_path / ".kanban.bak-20260604-1"
    assert result.backup is not None and result.backup.exists()

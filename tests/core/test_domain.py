"""Tests for the pure domain model in :mod:`kanbanmate.core.domain`.

Verifies that all dataclasses are truly frozen, all enum members are accessible,
and the key constructors work as expected.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from kanbanmate.core.domain import (
    Action,
    ActionKind,
    BoardSnapshot,
    Column,
    ColumnClass,
    Ticket,
    Transition,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ticket(
    item_id: str = "PVTI_001",
    issue_number: int | None = 42,
    title: str = "Test ticket",
    column_key: str = "Backlog",
) -> Ticket:
    """Build a :class:`Ticket` with sensible defaults for tests."""
    return Ticket(item_id=item_id, issue_number=issue_number, title=title, column_key=column_key)


# ---------------------------------------------------------------------------
# ColumnClass
# ---------------------------------------------------------------------------


class TestColumnClass:
    """Tests for the :class:`ColumnClass` enum."""

    def test_members(self) -> None:
        """The two non-launch column classes are accessible (no AGENT — DESIGN §8.0.6)."""
        assert ColumnClass.REACTIVE is not None
        assert ColumnClass.INERT is not None

    def test_no_agent_class(self) -> None:
        """There is no launch-related class: the agent launches at the transition (§8.0.6)."""
        assert not hasattr(ColumnClass, "AGENT")

    def test_values(self) -> None:
        """Enum values match the string representation."""
        assert ColumnClass.REACTIVE.value == "reactive"
        assert ColumnClass.INERT.value == "inert"

    def test_count(self) -> None:
        """There are exactly two column classes in the transitions-only model."""
        assert len(ColumnClass) == 2


# ---------------------------------------------------------------------------
# Column
# ---------------------------------------------------------------------------


class TestColumn:
    """Tests for the :class:`Column` frozen dataclass."""

    def test_construction(self) -> None:
        """A Column can be built with the required fields (key/name/class — no launch fields)."""
        col = Column(key="InProgress", name="In Progress", column_class=ColumnClass.INERT)
        assert col.key == "InProgress"
        assert col.name == "In Progress"
        assert col.column_class == ColumnClass.INERT

    def test_frozen(self) -> None:
        """Mutating any field raises FrozenInstanceError."""
        col = Column(key="Backlog", name="Backlog", column_class=ColumnClass.INERT)
        with pytest.raises(FrozenInstanceError):
            col.key = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Ticket
# ---------------------------------------------------------------------------


class TestTicket:
    """Tests for the :class:`Ticket` frozen dataclass."""

    def test_construction(self) -> None:
        """A Ticket can be built with all fields."""
        t = Ticket(item_id="PVTI_001", issue_number=42, title="Fix login", column_key="Backlog")
        assert t.item_id == "PVTI_001"
        assert t.issue_number == 42
        assert t.title == "Fix login"
        assert t.column_key == "Backlog"

    def test_issue_number_none_for_draft(self) -> None:
        """issue_number may be None for draft (non-issue) items."""
        t = Ticket(item_id="PVTI_draft", issue_number=None, title="Draft note", column_key="Ideas")
        assert t.issue_number is None

    def test_frozen(self) -> None:
        """Mutating any field raises FrozenInstanceError."""
        t = _make_ticket()
        with pytest.raises(FrozenInstanceError):
            t.title = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# BoardSnapshot
# ---------------------------------------------------------------------------


class TestBoardSnapshot:
    """Tests for the :class:`BoardSnapshot` frozen dataclass."""

    def test_construction_from_tuple(self) -> None:
        """A BoardSnapshot can be built from a tuple of Tickets."""
        tickets = (
            _make_ticket(item_id="A", title="First"),
            _make_ticket(item_id="B", title="Second"),
        )
        snap = BoardSnapshot(tickets=tickets, fetched_at=1000.0)
        assert len(snap.tickets) == 2
        assert snap.tickets[0].title == "First"
        assert snap.fetched_at == 1000.0

    def test_empty_board(self) -> None:
        """A BoardSnapshot with no tickets is valid (empty board)."""
        snap = BoardSnapshot(tickets=(), fetched_at=0.0)
        assert snap.tickets == ()
        assert snap.fetched_at == 0.0

    def test_frozen(self) -> None:
        """Mutating any field raises FrozenInstanceError."""
        snap = BoardSnapshot(tickets=(), fetched_at=0.0)
        with pytest.raises(FrozenInstanceError):
            snap.fetched_at = 42.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Transition
# ---------------------------------------------------------------------------


class TestTransition:
    """Tests for the :class:`Transition` frozen dataclass."""

    def test_construction_with_from_column(self) -> None:
        """A Transition representing a move from one column to another."""
        t = _make_ticket()
        tr = Transition(ticket=t, from_column="Backlog", to_column="InProgress")
        assert tr.ticket is t
        assert tr.from_column == "Backlog"
        assert tr.to_column == "InProgress"

    def test_construction_from_column_none(self) -> None:
        """from_column=None means a brand-new item (first time seen)."""
        t = _make_ticket()
        tr = Transition(ticket=t, from_column=None, to_column="Backlog")
        assert tr.from_column is None
        assert tr.to_column == "Backlog"

    def test_frozen(self) -> None:
        """Mutating any field raises FrozenInstanceError."""
        tr = Transition(ticket=_make_ticket(), from_column=None, to_column="Backlog")
        with pytest.raises(FrozenInstanceError):
            tr.to_column = "InProgress"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ActionKind
# ---------------------------------------------------------------------------


class TestActionKind:
    """Tests for the :class:`ActionKind` enum."""

    def test_all_seven_members_exposed(self) -> None:
        """The seven action kinds are present and mutually distinct."""
        distinct = {
            ActionKind.LAUNCH,
            ActionKind.TEARDOWN,
            ActionKind.RESET,
            ActionKind.BLOCK,
            ActionKind.NOOP,
            ActionKind.ROLLBACK,
            ActionKind.RUN_SCRIPT,
        }
        assert len(distinct) == 7
        # Explicit iteration to prove the enum exposes exactly those seven members.
        members = list(ActionKind)
        assert len(members) == 7

    def test_values(self) -> None:
        """Enum values match documented strings."""
        assert ActionKind.LAUNCH.value == "launch"
        assert ActionKind.TEARDOWN.value == "teardown"
        assert ActionKind.RESET.value == "reset"
        assert ActionKind.BLOCK.value == "block"
        assert ActionKind.NOOP.value == "noop"
        assert ActionKind.ROLLBACK.value == "rollback"
        assert ActionKind.RUN_SCRIPT.value == "run_script"


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------


class TestAction:
    """Tests for the :class:`Action` frozen dataclass."""

    def test_construction(self) -> None:
        """An Action binds a kind, a ticket, and a human-readable reason."""
        t = _make_ticket()
        action = Action(kind=ActionKind.LAUNCH, ticket=t, reason="Ticket entered InProgress")
        assert action.kind == ActionKind.LAUNCH
        assert action.ticket is t
        assert action.reason == "Ticket entered InProgress"

    def test_backcompat_minimal_construction(self) -> None:
        """An Action built with only kind/ticket/reason still compiles — the
        new transition-routing fields all default to neutral values so existing
        constructions in ``decide.py`` are unchanged.
        """
        t = _make_ticket()
        action = Action(kind=ActionKind.NOOP, ticket=t, reason="")
        # Verify the routing fields defaulted as documented.
        assert action.to_column == ""
        assert action.prompt is None
        assert action.script is None
        assert action.on_fail == ""
        assert action.advance == "stop"
        assert action.profile == ""
        assert action.permission_mode == "auto"

    def test_rollback_action_carries_from_col_in_to_column(self) -> None:
        """On ROLLBACK, ``to_column`` carries the bounce target (the original
        ``from_col``) — the load-bearing dual use documented in the field docstring.
        """
        t = _make_ticket()
        action = Action(
            kind=ActionKind.ROLLBACK,
            ticket=t,
            reason="Unwhitelisted move",
            to_column="Backlog",
        )
        assert action.kind == ActionKind.ROLLBACK
        assert action.to_column == "Backlog"

    def test_run_script_action_carries_script_field(self) -> None:
        """A RUN_SCRIPT action carries the script + routing fields for the
        mechanical runner to consume.
        """
        t = _make_ticket()
        action = Action(
            kind=ActionKind.RUN_SCRIPT,
            ticket=t,
            reason="Mechanical CI check",
            script="bin/check-pr-ready.sh",
            on_fail="move:Implement",
            advance="auto:PRReady",
        )
        assert action.kind == ActionKind.RUN_SCRIPT
        assert action.script == "bin/check-pr-ready.sh"
        assert action.on_fail == "move:Implement"
        assert action.advance == "auto:PRReady"

    def test_launch_action_carries_full_routing(self) -> None:
        """A LAUNCH action carries the full set of per-transition routing fields."""
        t = _make_ticket()
        action = Action(
            kind=ActionKind.LAUNCH,
            ticket=t,
            reason="Whitelisted move to agent column",
            to_column="InProgress",
            prompt="/implement:phase {{codename}}",
            script="bin/check-branch.sh",
            profile="dev",
            permission_mode="acceptEdits",
            on_fail="rollback",
            advance="auto:PRReady",
        )
        assert action.kind == ActionKind.LAUNCH
        assert action.to_column == "InProgress"
        assert action.prompt == "/implement:phase {{codename}}"
        assert action.script == "bin/check-branch.sh"
        assert action.profile == "dev"
        assert action.permission_mode == "acceptEdits"
        assert action.on_fail == "rollback"
        assert action.advance == "auto:PRReady"

    def test_frozen(self) -> None:
        """Mutating any field raises FrozenInstanceError."""
        action = Action(kind=ActionKind.NOOP, ticket=_make_ticket(), reason="Nothing to do")
        with pytest.raises(FrozenInstanceError):
            action.reason = "changed"  # type: ignore[misc]

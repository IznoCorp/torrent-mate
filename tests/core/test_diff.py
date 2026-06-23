"""Tests for the polling-heart diff in :mod:`kanbanmate.core.diff`.

Covers the four cases the polling loop relies on: an unchanged board yields no
transitions, a single move is detected, a brand-new item carries
``from_column = None``, and several simultaneous moves are all reported.
"""

from __future__ import annotations

from kanbanmate.core.diff import diff
from kanbanmate.core.domain import BoardSnapshot, Ticket


def _ticket(item_id: str, column_key: str, issue_number: int | None = None) -> Ticket:
    """Build a minimal :class:`Ticket` for diff tests.

    Args:
        item_id: The opaque project item id.
        column_key: The column the ticket currently sits in.
        issue_number: Optional issue number; defaults to ``None``.

    Returns:
        A frozen :class:`Ticket` with a throwaway title.
    """
    return Ticket(item_id=item_id, issue_number=issue_number, title="t", column_key=column_key)


def _snapshot(*tickets: Ticket) -> BoardSnapshot:
    """Wrap tickets in a :class:`BoardSnapshot` with a fixed fetch time."""
    return BoardSnapshot(tickets=tickets, fetched_at=0.0)


def test_no_change_yields_no_transitions() -> None:
    """A board identical to persisted state produces an empty diff."""
    snapshot = _snapshot(_ticket("a", "Backlog"), _ticket("b", "InProgress"))
    persisted = {"a": "Backlog", "b": "InProgress"}
    assert diff(persisted, snapshot) == []


def test_single_move_detected() -> None:
    """A ticket that changed column yields exactly one transition."""
    snapshot = _snapshot(_ticket("a", "InProgress"))
    persisted = {"a": "Backlog"}
    transitions = diff(persisted, snapshot)
    assert len(transitions) == 1
    transition = transitions[0]
    assert transition.ticket.item_id == "a"
    assert transition.from_column == "Backlog"
    assert transition.to_column == "InProgress"


def test_brand_new_item_has_no_from_column() -> None:
    """A ticket absent from persisted state appears with ``from_column = None``."""
    snapshot = _snapshot(_ticket("new", "Backlog"))
    transitions = diff({}, snapshot)
    assert len(transitions) == 1
    assert transitions[0].from_column is None
    assert transitions[0].to_column == "Backlog"


def test_multiple_moves_all_reported_in_order() -> None:
    """Several simultaneous moves are all detected, in snapshot order."""
    snapshot = _snapshot(
        _ticket("a", "InProgress"),  # moved
        _ticket("b", "Done"),  # unchanged
        _ticket("c", "Review"),  # moved
        _ticket("d", "Backlog"),  # brand-new
    )
    persisted = {"a": "Backlog", "b": "Done", "c": "PRCI"}
    transitions = diff(persisted, snapshot)
    assert [(t.ticket.item_id, t.from_column, t.to_column) for t in transitions] == [
        ("a", "Backlog", "InProgress"),
        ("c", "PRCI", "Review"),
        ("d", None, "Backlog"),
    ]


def test_empty_snapshot_yields_no_transitions() -> None:
    """An empty board produces no transitions regardless of persisted state."""
    assert diff({"a": "Backlog"}, _snapshot()) == []


def test_duplicated_item_yields_one_transition_last_occurrence_wins() -> None:
    """P4: a snapshot carrying the same item_id twice emits ONE transition (last occurrence wins).

    A malformed forge page / stale cursor / JOIN glitch could duplicate an item; without de-dup the
    diff would emit two transitions for one card → a dropped or mis-routed launch (the second decide
    clobbering the first's baseline advance). The de-dup keeps the LAST occurrence's column.
    """
    snapshot = _snapshot(
        _ticket("a", "InProgress"),  # first occurrence
        _ticket("a", "Review"),  # duplicate — the LATER column the snapshot reported
    )
    transitions = diff({"a": "Backlog"}, snapshot)
    assert len(transitions) == 1, "a duplicated item must yield exactly one transition"
    assert transitions[0].to_column == "Review", "the LAST occurrence's column must win"
    assert transitions[0].from_column == "Backlog"


def test_duplicated_item_collapsing_to_unchanged_yields_no_transition() -> None:
    """P4: if the LAST occurrence of a duplicated item matches persisted state, no transition fires.

    The de-dup must compare the LAST occurrence (not the first) against persisted state, so a card
    whose latest reported column equals where it already was produces no spurious launch.
    """
    snapshot = _snapshot(
        _ticket("a", "Review"),  # first occurrence (would diff vs Backlog)
        _ticket("a", "Backlog"),  # last occurrence == persisted → no change
    )
    assert diff({"a": "Backlog"}, snapshot) == []

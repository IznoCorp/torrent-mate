"""The heart of polling: reconcile persisted state against a fresh snapshot.

This module replaces the entire PoC payload / HMAC parsing pipeline (DESIGN
§3.1).  Instead of decoding a signed webhook payload, the daemon simply compares
the column each ticket *was* in (persisted state) against the column it is in
*now* (a fresh :class:`~kanbanmate.core.domain.BoardSnapshot`) and emits one
:class:`~kanbanmate.core.domain.Transition` per ticket that moved.

The function is pure: a persisted mapping and a snapshot in, a list of
transitions out, with no I/O and no clock access.  It imports only the domain
model from the KanbanMate core layer.
"""

from __future__ import annotations

from kanbanmate.core.domain import BoardSnapshot, Ticket, Transition


def diff(persisted: dict[str, str], snapshot: BoardSnapshot) -> list[Transition]:
    """Compute the column transitions between persisted state and a snapshot.

    For every ticket in ``snapshot`` whose current ``column_key`` differs from
    the column recorded in ``persisted`` (keyed by ``item_id``), a
    :class:`Transition` is emitted.  A ticket absent from ``persisted`` is
    brand-new: it yields a transition with ``from_column = None``.  Tickets
    whose column is unchanged produce no transition.

    The diff is intentionally one-directional — it only inspects tickets present
    in the snapshot.  Items that vanished from the board (e.g. archived) are not
    reported here; their teardown/cleanup is handled by the reap step of the
    tick, not by the diff.

    **One transition per item (P4 de-dup).** A well-formed snapshot carries each
    ``item_id`` once, but a duplicated item — a malformed forge page, a stale
    cursor that re-listed an item, or a native↔forge JOIN that emitted the same
    id twice — would otherwise yield TWO transitions for one card and could
    drop or mis-route the launch (two ``decide`` verdicts, the second clobbering
    the first's baseline advance). To make the diff robust to a duplicated item
    the LAST occurrence per ``item_id`` wins (it reflects the latest column the
    snapshot reported), so exactly one :class:`Transition` is emitted per card.

    Args:
        persisted: Mapping of ``item_id`` to the column key the ticket occupied
            at the previous poll.  Items unknown to the daemon are simply absent.
        snapshot: The freshly fetched board state.

    Returns:
        A list of :class:`Transition` objects, one per moved or new ticket, in
        snapshot order (first-seen position; the LAST occurrence's column wins on
        a duplicated id).  An empty list means the board is unchanged relative to
        the persisted state.
    """
    # Collapse to the LAST occurrence per item_id (P4): a dict keyed by item_id keeps the latest
    # ticket the snapshot reported for that id while preserving first-seen insertion order, so a
    # duplicated item can never emit two transitions (a dropped / mis-routed launch).
    latest_by_item: dict[str, Ticket] = {}
    for ticket in snapshot.tickets:
        latest_by_item[ticket.item_id] = ticket
    transitions: list[Transition] = []
    for ticket in latest_by_item.values():
        previous_column = persisted.get(ticket.item_id)
        # No change → nothing to decide on. ``previous_column`` is ``None`` for a
        # brand-new item, which always differs from a real column key.
        if ticket.column_key == previous_column:
            continue
        transitions.append(
            Transition(
                ticket=ticket,
                from_column=previous_column,
                to_column=ticket.column_key,
            )
        )
    return transitions

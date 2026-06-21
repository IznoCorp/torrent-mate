"""Port protocols for the native board state store (anchor §6.4).

Defines the read/write surface for the per-project ``board.json`` document:
a placement authority holding ordered columns, item→column mapping, and
per-column ordered item list. Separate from ``ports/board.py`` because this
is a persistence port (I/O), not a board-communication port.

``BoardOrdering`` is interface-segregated (the ``PullRequests``/
``ProjectStatusReporter`` precedent, ``ports/board.py:154,348``) — only the
helm HTTP API and ``kanban board`` CLI need reorder; the daemon tick never does.
"""

from __future__ import annotations

from typing import Any, Protocol


class BoardStateStore(Protocol):
    """Read/write the native board placement document (``board.json``).

    Every mutating call holds an exclusive ``flock`` for the duration of the
    read-modify-write and bumps the monotonic ``version`` counter inside the
    lock. Atomic replace (temp-file + ``os.replace``) ensures a concurrent
    reader never sees a torn file.
    """

    def load(self) -> dict[str, Any]:
        """Return the current ``board.json`` document (an empty skeleton when absent).

        Returns:
            The parsed document. When the file does not yet exist, the empty SKELETON
            ``{"version": 0, "columns": [], "placement": {}, "order": {}, "shadow": {}, "pending":
            {}}`` (not a bare ``{}``) — so callers can read ``doc["columns"]`` / ``doc["order"]``
            without a KeyError. ``shadow`` / ``pending`` are the hybrid board-sync bookkeeping.
        """
        ...

    def place_card(
        self,
        item_id: str,
        column_key: str,
        index: int | None = None,
        *,
        if_version: int | None = None,
    ) -> int:
        """Move ``item_id`` to ``column_key`` at ``index`` (tail when ``None``).

        Removes the item from its current column's order list (if present),
        inserts it into ``column_key``'s list at ``index`` or appends to the
        tail, updates ``placement``, bumps ``version``, writes atomically.

        Args:
            item_id: The ``ProjectV2Item`` node id to place.
            column_key: The destination column key (must be in ``columns``).
            index: Position within the column; ``None`` appends to the tail.
            if_version: When set, raises ``ValueError`` if the stored version
                does not match (optimistic concurrency — the HTTP layer maps
                this to ``409``).

        Returns:
            The new ``version`` after the write.

        Raises:
            ValueError: Unknown ``column_key``; stale ``if_version``.
        """
        ...

    def reorder_column(
        self,
        column_key: str,
        ordered_item_ids: list[str],
        *,
        if_version: int | None = None,
    ) -> int:
        """Replace ``column_key``'s full ordered item list.

        Validates that every ``item_id`` in ``ordered_item_ids`` is currently
        in ``column_key`` (no unknown / cross-column / duplicate ids), replaces
        the list, bumps ``version``, writes atomically.

        Args:
            column_key: The column whose order to set.
            ordered_item_ids: The new full ordered list of item ids in this column.
            if_version: Optimistic-concurrency precondition (see :meth:`place_card`).

        Returns:
            The new ``version`` after the write.

        Raises:
            ValueError: Unknown ``column_key``; unknown/duplicate/missing item id;
                stale ``if_version``.
        """
        ...


class BoardOrdering(Protocol):
    """Dedicated reorder/place capability — never on the engine hot path (anchor §4.3).

    Interface-segregated from ``BoardStateStore`` so callers that only need the
    ordering surface (helm HTTP API, ``kanban board`` CLI) do not depend on the
    full store. ``NativeBoardBackend`` satisfies both this protocol and
    ``BoardWriter``.
    """

    def reorder_column(
        self,
        column_key: str,
        ordered_item_ids: list[str],
        *,
        if_version: int | None = None,
    ) -> int:
        """Replace ``column_key``'s full ordered item list; return the new version.

        Args:
            column_key: The column whose order to set.
            ordered_item_ids: Full ordered item id list for the column.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new store version.

        Raises:
            ValueError: Unknown column; unknown/duplicate/missing item id; stale version.
        """
        ...

    def place_card(
        self,
        item_id: str,
        column_key: str,
        index: int | None = None,
        *,
        if_version: int | None = None,
    ) -> int:
        """Place ``item_id`` at ``(column_key, index)``; return the new version.

        Args:
            item_id: The item to place.
            column_key: The destination column key.
            index: Position within the column; ``None`` appends.
            if_version: Optimistic-concurrency precondition.

        Returns:
            The new store version.

        Raises:
            ValueError: Unknown column; stale version.
        """
        ...

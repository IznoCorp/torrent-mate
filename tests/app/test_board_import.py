"""Tests for board_import: seeding, idempotent re-run, dry-run (anchor §12.8)."""

from __future__ import annotations

import pathlib
from unittest.mock import MagicMock

from kanbanmate.adapters.store.fs_board import FsBoardStateStore
from kanbanmate.app.board_import import import_board
from kanbanmate.core.domain import BoardSnapshot, Column, ColumnClass, Ticket

# Column model keyed by key; for these keys name == key, so a ticket whose Status name equals the
# key resolves cleanly (the multi-word name/key mismatch is exercised separately below).
COLUMNS = {
    key: Column(key=key, name=key, column_class=ColumnClass.INERT)
    for key in (
        "Backlog",
        "Brainstorming",
        "Spec",
        "Plan",
        "Planned",
        "ReadyToDev",
        "PrepareFeature",
        "InProgress",
        "PRCI",
        "Review",
        "Merge",
        "Done",
        "Cancel",
        "Blocked",
    )
}


def _forge_with_tickets(*tickets: Ticket) -> MagicMock:
    forge = MagicMock()
    forge.snapshot.return_value = BoardSnapshot(tickets=tuple(tickets), fetched_at=0.0)
    return forge


def _ticket(item_id: str, col: str) -> Ticket:
    return Ticket(item_id=item_id, issue_number=1, title="T", column_key=col, body="")


def test_import_seeds_board_from_snapshot(tmp_path: pathlib.Path) -> None:
    """import_board seeds board.json from the live GitHub snapshot."""
    forge = _forge_with_tickets(
        _ticket("a", "Backlog"),
        _ticket("b", "InProgress"),
    )
    store = FsBoardStateStore(tmp_path)
    result = import_board(forge, store, COLUMNS)

    assert result["version"] == 1
    assert result["dry_run"] is False
    doc = store.load()
    assert doc["placement"]["a"] == "Backlog"
    assert doc["placement"]["b"] == "InProgress"
    assert "a" in doc["order"]["Backlog"]
    assert "b" in doc["order"]["InProgress"]


def test_import_idempotent_rerun_preserves_native_order(tmp_path: pathlib.Path) -> None:
    """A re-run increments version, preserves existing native order for unchanged items."""
    store = FsBoardStateStore(tmp_path)
    # First import.
    forge = _forge_with_tickets(_ticket("a", "Backlog"), _ticket("b", "Backlog"))
    import_board(forge, store, COLUMNS)
    # Manually set a custom native order.
    store.reorder_column("Backlog", ["b", "a"])

    # Second import (same snapshot). The store's single monotonic version is bumped on
    # every mutating write (anchor §6.2): import1 → 1, the reorder above → 2, import2 → 3.
    result = import_board(forge, store, COLUMNS)
    assert result["version"] == 3

    doc = store.load()
    # Native order ["b", "a"] must be preserved since both items are still in Backlog.
    assert doc["order"]["Backlog"] == ["b", "a"]


def test_import_rerun_reconciles_moved_card(tmp_path: pathlib.Path) -> None:
    """A card moved to a DIFFERENT column on GitHub between imports lands in the new column on re-run.

    Exercises the ``moved_in`` ordering branch (board_import.py): the card is neither ``still_here``
    (it left its old column) nor ``newly_seen`` (it already existed), so only ``moved_in`` places it.
    """
    store = FsBoardStateStore(tmp_path)
    # First import: card "a" in Backlog, "b" in Backlog.
    import_board(
        _forge_with_tickets(_ticket("a", "Backlog"), _ticket("b", "Backlog")), store, COLUMNS
    )
    doc1 = store.load()
    assert doc1["placement"]["a"] == "Backlog"

    # Second import: "a" moved to InProgress on GitHub; "b" unchanged.
    result = import_board(
        _forge_with_tickets(_ticket("a", "InProgress"), _ticket("b", "Backlog")), store, COLUMNS
    )
    doc2 = store.load()
    assert doc2["placement"]["a"] == "InProgress", "moved card must be reconciled to its new column"
    assert doc2["order"]["InProgress"] == ["a"], (
        "moved_in branch must place it in the new column order"
    )
    assert "a" not in doc2["order"]["Backlog"], "moved card must leave its old column order"
    assert doc2["order"]["Backlog"] == ["b"]
    assert result["summary"]["per_column"]["InProgress"] == 1


def test_import_dryrun_does_not_write(tmp_path: pathlib.Path) -> None:
    """--dry-run computes the result but does not write board.json."""
    forge = _forge_with_tickets(_ticket("a", "Backlog"))
    store = FsBoardStateStore(tmp_path)
    result = import_board(forge, store, COLUMNS, dry_run=True)

    assert result["dry_run"] is True
    assert result["version"] == 1
    # board.json must NOT exist (no write).
    assert not (tmp_path / "board.json").exists()


def test_import_unknown_column_lands_in_entry(tmp_path: pathlib.Path) -> None:
    """A ticket with an unknown GitHub Status column falls back to the entry column."""
    forge = _forge_with_tickets(_ticket("x", "UnknownGitHubStatus"))
    store = FsBoardStateStore(tmp_path)
    import_board(forge, store, COLUMNS)
    doc = store.load()
    assert doc["placement"]["x"] == "Backlog", "entry column is COLUMNS[0] = Backlog"


def test_import_resolves_status_name_to_column_key(tmp_path: pathlib.Path) -> None:
    """A GitHub Status NAME that differs from the column KEY must resolve to the key, not fall back.

    Regression for the live #55 bug: the GitHub adapter emits the Status display NAME
    (``"Ready to Dev"``) as the ticket's ``column_key``, but the native store is keyed by the stable
    column KEY (``"ReadyToDev"``). The import must bridge that name/key seam via ``resolve_column`` —
    the old code compared the name against the key list, missed, and dumped the card into
    ``columns[0]`` (Brainstorming).
    """
    columns = {
        "Brainstorming": Column(
            key="Brainstorming", name="Brainstorming", column_class=ColumnClass.INERT
        ),
        "ReadyToDev": Column(key="ReadyToDev", name="Ready to Dev", column_class=ColumnClass.INERT),
    }
    # The snapshot emits the Status NAME, exactly as the GitHub adapter does in production.
    forge = _forge_with_tickets(_ticket("55", "Ready to Dev"))
    store = FsBoardStateStore(tmp_path)
    import_board(forge, store, columns)

    doc = store.load()
    assert doc["placement"]["55"] == "ReadyToDev", (
        "Status name must resolve to its column key, not fall back to columns[0]"
    )
    assert "55" in doc["order"]["ReadyToDev"]
    assert "55" not in doc["order"]["Brainstorming"]


def test_import_summary_counts_per_column(tmp_path: pathlib.Path) -> None:
    forge = _forge_with_tickets(
        _ticket("a", "Backlog"),
        _ticket("b", "Backlog"),
        _ticket("c", "InProgress"),
    )
    store = FsBoardStateStore(tmp_path)
    result = import_board(forge, store, COLUMNS)
    assert result["summary"]["total"] == 3
    assert result["summary"]["per_column"]["Backlog"] == 2
    assert result["summary"]["per_column"]["InProgress"] == 1

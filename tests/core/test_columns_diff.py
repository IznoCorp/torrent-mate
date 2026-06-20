"""Tests for the pure column-set diff backing the Sync-board preview."""

from kanbanmate.core.columns_diff import ColumnChange, diff_columns


def test_identical_sets_is_noop() -> None:
    d = diff_columns(["Backlog", "Spec", "Done"], ["Backlog", "Spec", "Done"])
    assert d.is_noop is True
    assert d.changes == []
    assert d.removals == []


def test_added_column_is_add() -> None:
    d = diff_columns(["Backlog", "Done"], ["Backlog", "Spec", "Done"])
    assert d.is_noop is False
    assert ColumnChange(kind="add", column="Spec") in d.changes
    assert d.removals == []


def test_removed_column_is_surfaced_not_in_changes() -> None:
    d = diff_columns(["Backlog", "Old", "Done"], ["Backlog", "Done"])
    assert d.removals == [ColumnChange(kind="remove", column="Old")]
    # removals never appear in the applied change list
    assert all(c.kind != "remove" for c in d.changes)


def test_reorder_detected_by_index() -> None:
    d = diff_columns(["Backlog", "Review", "Merge"], ["Backlog", "Merge", "Review"])
    kinds = {(c.kind, c.column) for c in d.changes}
    assert ("reorder", "Review") in kinds or ("reorder", "Merge") in kinds


def test_rename_map_reclassifies_add_remove() -> None:
    # "PR Ready" removed + "PR/CI" added, but the operator asserts it's a rename.
    d = diff_columns(
        ["Backlog", "PR Ready", "Done"],
        ["Backlog", "PR/CI", "Done"],
        renames={"PR Ready": "PR/CI"},
    )
    assert ColumnChange(kind="rename", column="PR Ready", to="PR/CI") in d.changes
    assert d.removals == []  # the remove was reclassified
    assert all(c.kind != "add" or c.column != "PR/CI" for c in d.changes)

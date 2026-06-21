"""Tests for FsBoardStateStore — round-trip, version monotonicity,
flock concurrency, fail-loud validation, and torn-write safety (anchor §12.1).
"""

from __future__ import annotations

import os
import pathlib
import threading

import pytest

from kanbanmate.adapters.store.fs_board import FsBoardStateStore, seed_board


@pytest.fixture()
def store(tmp_path: pathlib.Path) -> FsBoardStateStore:
    """A fresh store rooted at a temp directory."""
    return FsBoardStateStore(tmp_path)


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_load_absent_returns_empty(store: FsBoardStateStore) -> None:
    doc = store.load()
    assert doc == {
        "version": 0,
        "columns": [],
        "placement": {},
        "order": {},
        "shadow": {},
        "pending": {},
    }


def test_seed_then_load_round_trips(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog", "InProgress", "Done"],
        placement={"item1": "Backlog"},
        order={"Backlog": ["item1"], "InProgress": [], "Done": []},
    )
    doc = s.load()
    assert doc["version"] == 1
    assert doc["columns"] == ["Backlog", "InProgress", "Done"]
    assert doc["placement"] == {"item1": "Backlog"}
    assert doc["order"]["Backlog"] == ["item1"]


# ---------------------------------------------------------------------------
# place_card — happy path
# ---------------------------------------------------------------------------


def test_place_card_append_to_tail(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog", "InProgress"],
        placement={"a": "Backlog", "b": "Backlog"},
        order={"Backlog": ["a", "b"], "InProgress": []},
    )
    v = s.place_card("a", "InProgress")
    doc = s.load()
    assert doc["placement"]["a"] == "InProgress"
    assert "a" not in doc["order"]["Backlog"]
    assert doc["order"]["InProgress"] == ["a"]
    assert doc["version"] == v == 2


def test_place_card_at_index(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["InProgress"],
        placement={"a": "InProgress", "b": "InProgress"},
        order={"InProgress": ["a", "b"]},
    )
    s.place_card("b", "InProgress", index=0)
    doc = s.load()
    assert doc["order"]["InProgress"] == ["b", "a"]


# ---------------------------------------------------------------------------
# place_card — fail-loud
# ---------------------------------------------------------------------------


def test_place_card_unknown_column_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={}, order={"Backlog": []})
    with pytest.raises(ValueError, match="unknown column_key"):
        s.place_card("item1", "NonExistent")


def test_place_card_stale_if_version_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={"x": "Backlog"}, order={"Backlog": ["x"]})
    with pytest.raises(ValueError, match="optimistic concurrency"):
        s.place_card("x", "Backlog", if_version=99)


def test_place_card_matching_if_version_succeeds(tmp_path: pathlib.Path) -> None:
    """The optimistic-concurrency SUCCESS path: a correct if_version writes (guards a flipped check)."""
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog", "Done"],
        placement={"x": "Backlog"},
        order={"Backlog": ["x"], "Done": []},
    )
    v = s.place_card("x", "Done", if_version=1)  # seeded version is 1
    assert v == 2
    assert s.load()["placement"]["x"] == "Done"


def test_place_card_stale_if_version_raises_version_conflict(tmp_path: pathlib.Path) -> None:
    """The stale-version error is the typed VersionConflict (so the HTTP layer maps 409 by type)."""
    from kanbanmate.adapters.store.fs_board import VersionConflict

    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={"x": "Backlog"}, order={"Backlog": ["x"]})
    with pytest.raises(VersionConflict):
        s.place_card("x", "Backlog", if_version=99)


def test_place_card_negative_index_raises(tmp_path: pathlib.Path) -> None:
    """A negative index is rejected fail-loud (not silently treated as offset-from-end)."""
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s, columns=["InProgress"], placement={"a": "InProgress"}, order={"InProgress": ["a"]}
    )
    with pytest.raises(ValueError, match="out of range"):
        s.place_card("b", "InProgress", index=-1)


def test_place_card_out_of_range_index_raises(tmp_path: pathlib.Path) -> None:
    """An index beyond the column length is rejected (not silently clamped/appended)."""
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s, columns=["InProgress"], placement={"a": "InProgress"}, order={"InProgress": ["a"]}
    )
    # Column has 1 item → valid insert positions are 0..1; index 5 is out of range.
    with pytest.raises(ValueError, match="out of range"):
        s.place_card("b", "InProgress", index=5)


def test_place_card_boolean_index_rejected(tmp_path: pathlib.Path) -> None:
    """A JSON ``true`` (Python ``bool``) is rejected, not silently read as index 1."""
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s, columns=["InProgress"], placement={"a": "InProgress"}, order={"InProgress": ["a"]}
    )
    with pytest.raises(ValueError, match="must be an integer"):
        s.place_card("b", "InProgress", index=True)


def test_corrupt_board_json_raises_clear_error(tmp_path: pathlib.Path) -> None:
    """A truncated/hand-corrupted board.json fails LOUD with an actionable message, not a raw traceback."""
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={}, order={"Backlog": []})
    (tmp_path / "board.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ValueError, match="is corrupt"):
        s.load()


# ---------------------------------------------------------------------------
# reorder_column — happy path
# ---------------------------------------------------------------------------


def test_reorder_column_sets_order(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog"],
        placement={"a": "Backlog", "b": "Backlog", "c": "Backlog"},
        order={"Backlog": ["a", "b", "c"]},
    )
    v = s.reorder_column("Backlog", ["c", "a", "b"])
    doc = s.load()
    assert doc["order"]["Backlog"] == ["c", "a", "b"]
    assert doc["version"] == v == 2


# ---------------------------------------------------------------------------
# reorder_column — fail-loud
# ---------------------------------------------------------------------------


def test_reorder_column_unknown_column_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={}, order={"Backlog": []})
    with pytest.raises(ValueError, match="unknown column_key"):
        s.reorder_column("NoSuchCol", [])


def test_reorder_column_duplicate_item_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog"],
        placement={"a": "Backlog"},
        order={"Backlog": ["a"]},
    )
    with pytest.raises(ValueError, match="duplicate"):
        s.reorder_column("Backlog", ["a", "a"])


def test_reorder_column_unknown_item_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={}, order={"Backlog": []})
    with pytest.raises(ValueError, match="not in column"):
        s.reorder_column("Backlog", ["ghost"])


def test_reorder_column_missing_item_raises(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog"],
        placement={"a": "Backlog", "b": "Backlog"},
        order={"Backlog": ["a", "b"]},
    )
    with pytest.raises(ValueError, match="missing"):
        s.reorder_column("Backlog", ["a"])  # missing "b"


# ---------------------------------------------------------------------------
# Version monotonicity across writes
# ---------------------------------------------------------------------------


def test_version_monotonic_across_writes(tmp_path: pathlib.Path) -> None:
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog", "InProgress"],
        placement={"a": "Backlog"},
        order={"Backlog": ["a"], "InProgress": []},
    )
    v1 = s.place_card("a", "InProgress")
    v2 = s.reorder_column("InProgress", ["a"])
    assert v1 == 2
    assert v2 == 3


# ---------------------------------------------------------------------------
# Concurrent writers — no lost update (flock serialisation)
# ---------------------------------------------------------------------------


def test_concurrent_writers_no_lost_update(tmp_path: pathlib.Path) -> None:
    """Two threads each place a distinct item; both must land."""
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog", "Done"],
        placement={"a": "Backlog", "b": "Backlog"},
        order={"Backlog": ["a", "b"], "Done": []},
    )

    errors: list[Exception] = []

    def move_a() -> None:
        try:
            s.place_card("a", "Done")
        except Exception as exc:
            errors.append(exc)

    def move_b() -> None:
        try:
            s.place_card("b", "Done")
        except Exception as exc:
            errors.append(exc)

    t1 = threading.Thread(target=move_a)
    t2 = threading.Thread(target=move_b)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"Concurrent write errors: {errors}"
    doc = s.load()
    assert set(doc["order"]["Done"]) == {"a", "b"}
    assert doc["version"] == 3  # seed=1, move_a=2, move_b=3 (or 3 regardless of order)


# ---------------------------------------------------------------------------
# Torn-write safety — interrupting before os.replace leaves prior file intact
# ---------------------------------------------------------------------------


def test_torn_write_prior_file_intact(tmp_path: pathlib.Path) -> None:
    """If the process is interrupted after writing the tmp but before os.replace,
    the original board.json is untouched."""
    s = FsBoardStateStore(tmp_path)
    seed_board(
        s,
        columns=["Backlog"],
        placement={"a": "Backlog"},
        order={"Backlog": ["a"]},
    )
    original = s.load()

    # Simulate a torn write: write a corrupt tmp file but do NOT replace.
    tmp = s._board_path.with_name(f"board.{os.getpid()}.tmp")
    tmp.write_text("{corrupt", encoding="utf-8")
    # Do NOT call os.replace — the original must be intact.

    doc = s.load()
    assert doc == original, "board.json must be unchanged after a torn tmp write"
    tmp.unlink(missing_ok=True)


def test_seed_board_preserves_existing_sync_state(tmp_path: pathlib.Path) -> None:
    """A re-import (seed_board) must NOT wipe the hybrid sync bookkeeping (shadow + pending)."""
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={}, order={"Backlog": []})
    s.set_sync_state({"item1": "Done"}, {"item2": "Review"})
    # Re-import (idempotent re-run) with new placement.
    seed_board(s, columns=["Backlog"], placement={"item1": "Backlog"}, order={"Backlog": ["item1"]})
    doc = s.load()
    assert doc["shadow"] == {"item1": "Done"}, "re-import must preserve the shadow"
    assert doc["pending"] == {"item2": "Review"}, "re-import must preserve pending"


def test_set_sync_state_does_not_bump_version(tmp_path: pathlib.Path) -> None:
    """set_sync_state is bookkeeping only — it must NOT bump version (no cheap_probe churn)."""
    s = FsBoardStateStore(tmp_path)
    seed_board(s, columns=["Backlog"], placement={}, order={"Backlog": []})
    v_before = s.load()["version"]
    s.set_sync_state({"item1": "Done"}, {"item1": "Review"})
    assert s.load()["version"] == v_before, "sync-state write must not change version"

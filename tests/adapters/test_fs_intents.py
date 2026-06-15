"""Tests for the intent-queue persistence mixin (:mod:`kanbanmate.adapters.store.fs_intents`, PR2).

Drives the mixin through :class:`~kanbanmate.adapters.store.fs_store.FsStateStore` (how it ships):
round-trip of pending intents + results, ``list_pending_intents`` excluding result files, clearing,
lazy directory creation, poison-tolerant reads, and atomic writes (no ``.tmp`` residue).
"""

from __future__ import annotations

from pathlib import Path

from kanbanmate.adapters.store.fs_store import FsStateStore


class TestIntentQueue:
    """The board-mutation intent queue under ``<root>/intents/`` (cockpit PR2)."""

    def test_enqueue_and_load_round_trip(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        payload = {"kind": "move", "issue": 7, "args": {"to_col": "Done"}, "requested_at": 1.5}
        store.enqueue_intent("abc", payload)
        assert store.load_intent("abc") == payload

    def test_list_pending_excludes_result_files(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        store.enqueue_intent("a1", {"kind": "move", "issue": 1})
        store.enqueue_intent("a2", {"kind": "move", "issue": 2})
        store.save_intent_result("a1", {"state": "done"})
        # Only the two PENDING ids — the result file for a1 is not a pending intent.
        assert store.list_pending_intents() == ("a1", "a2")

    def test_clear_intent_removes_marker(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        store.enqueue_intent("z", {"kind": "move", "issue": 9})
        store.clear_intent("z")
        assert store.load_intent("z") is None
        assert store.list_pending_intents() == ()

    def test_result_round_trip(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        store.save_intent_result("r", {"state": "rejected", "detail": "nope"})
        assert store.load_intent_result("r") == {"state": "rejected", "detail": "nope"}

    def test_absent_queue_degrades_to_empty(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        # No intent ever enqueued → the directory may not exist; reads degrade cleanly.
        assert store.list_pending_intents() == ()
        assert store.load_intent("missing") is None
        assert store.load_intent_result("missing") is None

    def test_poison_intent_degrades_to_none(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        store.enqueue_intent("bad", {"kind": "move", "issue": 1})
        (tmp_path / "intents" / "bad.json").write_text("{ not json")
        # A corrupt marker must not raise — it degrades to None (the drain rejects it).
        assert store.load_intent("bad") is None

    def test_atomic_write_no_temp_residue(self, tmp_path: Path) -> None:
        store = FsStateStore(root=tmp_path)
        store.enqueue_intent("t", {"kind": "move", "issue": 1})
        store.save_intent_result("t", {"state": "done"})
        assert list((tmp_path / "intents").glob("*.tmp")) == []

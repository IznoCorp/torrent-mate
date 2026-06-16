"""Tests for the intent-queue persistence mixin (:mod:`kanbanmate.adapters.store.fs_intents`, PR2).

Drives the mixin through :class:`~kanbanmate.adapters.store.fs_store.FsStateStore` (how it ships):
round-trip of pending intents + results, ``list_pending_intents`` excluding result files, clearing,
lazy directory creation, poison-tolerant reads, and atomic writes (no ``.tmp`` residue).
"""

from __future__ import annotations

import os
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


class TestIntentResultGc:
    """The TTL result-file GC (cockpit DESIGN §10 — ``intents/`` must not grow unbounded)."""

    def test_expired_result_is_unlinked(self, tmp_path: Path) -> None:
        """A result file older than the TTL is unlinked by the GC."""
        store = FsStateStore(root=tmp_path)
        store.save_intent_result("old", {"state": "done"})
        result_path = tmp_path / "intents" / "old.result.json"
        # Age it well beyond the TTL by back-dating its mtime.
        old_mtime = 1000.0
        os.utime(result_path, (old_mtime, old_mtime))
        store.gc_intent_results(now=1000.0 + 7200.0, ttl=3600.0)
        assert not result_path.exists()

    def test_fresh_result_is_kept(self, tmp_path: Path) -> None:
        """A result file younger than the TTL survives the GC."""
        store = FsStateStore(root=tmp_path)
        store.save_intent_result("fresh", {"state": "done"})
        result_path = tmp_path / "intents" / "fresh.result.json"
        now = result_path.stat().st_mtime + 10.0  # 10s old, well within a 1h TTL
        store.gc_intent_results(now=now, ttl=3600.0)
        assert result_path.exists()

    def test_pending_marker_is_never_gcd(self, tmp_path: Path) -> None:
        """The GC touches ONLY ``*.result.json`` — a still-pending ``<id>.json`` is left intact."""
        store = FsStateStore(root=tmp_path)
        store.enqueue_intent("p", {"kind": "move", "issue": 1})
        pending = tmp_path / "intents" / "p.json"
        os.utime(pending, (1000.0, 1000.0))  # ancient, but it is NOT a result file
        store.gc_intent_results(now=1000.0 + 7200.0, ttl=3600.0)
        assert pending.exists()

    def test_missing_dir_is_noop(self, tmp_path: Path) -> None:
        """GC on an absent ``intents/`` directory never raises."""
        store = FsStateStore(root=tmp_path)
        store.gc_intent_results(now=1.0, ttl=3600.0)  # must not raise

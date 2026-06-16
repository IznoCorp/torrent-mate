"""Tests for per-project store namespacing + the daemon-level nudge root (ingress-multiproject §3.2).

The collision fix: two projects with the SAME issue number must not collide on disk. The N=1 escape
hatch: a bare-root store keeps the legacy flat layout (the nudge lives under its own root). The N>1
case: the per-ticket queue lives under the sub-root while the nudge sentinel lives under the shared
runtime root (one daemon, one wake).
"""

from __future__ import annotations

from pathlib import Path

from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.ports.store import TicketState, TicketStatus


def _state(issue: int) -> TicketState:
    return TicketState(
        issue_number=issue,
        item_id=f"I{issue}",
        session_id=f"S{issue}",
        status=TicketStatus.RUNNING,
        heartbeat=0.0,
    )


def test_same_issue_two_projects_no_collision(tmp_path: Path) -> None:
    """Issue #5 on two per-project sub-roots stays in two separate files (the collision fix)."""
    root_a = tmp_path / "projects" / "PVT_A"
    root_b = tmp_path / "projects" / "PVT_B"
    store_a = FsStateStore(root_a, nudge_root=tmp_path)
    store_b = FsStateStore(root_b, nudge_root=tmp_path)

    store_a.save(_state(5))
    store_b.save(_state(5))
    # Distinct on-disk state files (no clobber).
    loaded_a = store_a.load(5)
    loaded_b = store_b.load(5)
    assert loaded_a is not None and loaded_a.item_id == "I5"
    assert loaded_b is not None and loaded_b.item_id == "I5"
    # Two separate files under two sub-roots.
    assert (root_a / "state" / "5.json").exists()
    assert (root_b / "state" / "5.json").exists()


def test_nudge_sentinel_is_daemon_level_under_runtime_root(tmp_path: Path) -> None:
    """N>1: the nudge sentinel lands under the SHARED runtime root, not the per-project sub-root."""
    sub_root = tmp_path / "projects" / "PVT_A"
    store = FsStateStore(sub_root, nudge_root=tmp_path)

    store.nudge_daemon()

    # The nudge is at <runtime_root>/intents/.nudge (NOT under the per-project sub-root).
    assert (tmp_path / "intents" / ".nudge").exists()
    assert not (sub_root / "intents" / ".nudge").exists()
    assert store.nudge_mtime() > 0.0


def test_n1_nudge_defaults_to_store_root(tmp_path: Path) -> None:
    """N=1 (no nudge_root): the nudge defaults to the store root — byte-identical to today."""
    store = FsStateStore(tmp_path)  # no nudge_root → defaults to root
    store.nudge_daemon()
    assert (tmp_path / "intents" / ".nudge").exists()
    assert store.nudge_mtime() > 0.0


def test_per_project_intent_queue_under_sub_root(tmp_path: Path) -> None:
    """N>1: the intent QUEUE lives under the per-project sub-root (each project drains its own)."""
    sub_root = tmp_path / "projects" / "PVT_A"
    store = FsStateStore(sub_root, nudge_root=tmp_path)

    store.enqueue_intent("abc123", {"kind": "move", "issue": 5, "args": {"to_col": "Done"}})

    # The queue file is under the sub-root, the nudge under the runtime root.
    assert (sub_root / "intents" / "abc123.json").exists()
    assert store.list_pending_intents() == ("abc123",)

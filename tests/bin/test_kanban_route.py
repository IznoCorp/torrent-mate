"""Tests for ``kanban-route`` helper (skiff fast-track routing)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kanbanmate.bin import kanban_route
from kanbanmate.bin.kanban_route import main


def _patch_store(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    store = MagicMock()
    monkeypatch.setattr(kanban_route, "FsStateStore", lambda *a, **k: store)
    monkeypatch.setattr(kanban_route, "helper_store_root", lambda: ("/root", None))
    monkeypatch.setattr(kanban_route, "check_pin", lambda issue: None)
    return store


def _write_pin(worktree: Path, issue: int) -> None:
    """Write ``<worktree>/.claude/kanban-issue`` carrying ``issue`` (the R1 worktree pin)."""
    claude = worktree / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "kanban-issue").write_text(f"{issue}\n", encoding="utf-8")


def test_records_the_chosen_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid <issue> <lane> records the route breadcrumb and exits 0."""
    store = _patch_store(monkeypatch)
    assert main(["7", "express"]) == 0
    store.record_agent_route.assert_called_once()
    assert store.record_agent_route.call_args.args[0] == 7
    assert store.record_agent_route.call_args.args[1] == "express"


def test_unknown_lane_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unknown lane is a usage error (exit 2); the store is never touched."""
    store = _patch_store(monkeypatch)
    assert main(["7", "turbo"]) == 2
    store.record_agent_route.assert_not_called()


def test_missing_args_is_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    store = _patch_store(monkeypatch)
    assert main(["7"]) == 2
    store.record_agent_route.assert_not_called()


def test_pin_mismatch_refuses_and_writes_no_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worktree PINNED to a different issue refuses (exit 1); no route marker is written.

    Mirrors ``kanban_done``'s pin-mismatch contract (R1, §29.1): the real pin check runs BEFORE the
    store write, so a mismatched issue never lands a breadcrumb.
    """
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setenv("KANBAN_ROOT", str(root))
    # The agent's worktree is pinned to #7, but it tries kanban-route for #9.
    worktree = tmp_path / "wt"
    worktree.mkdir()
    _write_pin(worktree, 7)
    monkeypatch.chdir(worktree)

    assert main(["9", "express"]) == 1
    # The pin check runs BEFORE the store write — no route marker for the mismatched issue.
    assert not (root / "route" / "9").exists()


def test_pin_match_writes_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A worktree pinned to the SAME issue proceeds (exit 0); the route marker is written."""
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setenv("KANBAN_ROOT", str(root))
    worktree = tmp_path / "wt"
    worktree.mkdir()
    _write_pin(worktree, 7)
    monkeypatch.chdir(worktree)

    assert main(["7", "express"]) == 0
    assert (root / "route" / "7").exists()

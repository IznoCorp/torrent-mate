"""Tests for the ``kanban-done`` agent helper (:mod:`kanbanmate.bin.kanban_done`).

The contract (#1, Option 1 — the agent's terminal step):

* a valid issue drops a persisted DONE breadcrumb
  (:meth:`~kanbanmate.adapters.store.fs_store.FsStateStore.record_agent_done`) and exits ``0``;
* a bad/missing arg is a usage error (exit ``2``); a store failure is reported (exit ``1``),
  never a crash;
* a pin mismatch (worktree PINNED to a different issue) is refused (exit ``1``), no marker written;
* the store root is resolved from ``$KANBAN_ROOT`` (the km-worktree-helper-root fix) — the marker
  lands under that root, not ~/.kanban.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kanbanmate.adapters.store.fs_store import FsStateStore
from kanbanmate.bin.kanban_done import main


def _write_pin(worktree: Path, issue: int) -> None:
    """Write ``<worktree>/.claude/kanban-issue`` carrying ``issue`` (the R1 worktree pin)."""
    claude = worktree / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "kanban-issue").write_text(f"{issue}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Usage / argument handling
# ---------------------------------------------------------------------------


def test_missing_arg_is_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No issue argument is a usage error (exit 2); no marker written."""
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    assert main([]) == 2
    assert not (tmp_path / "done").exists() or not any((tmp_path / "done").iterdir())


def test_two_args_is_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two arguments is a usage error (exit 2)."""
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    assert main(["7", "extra"]) == 2


def test_non_int_arg_is_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-integer issue is rejected (exit 2)."""
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))
    assert main(["abc"]) == 2


# ---------------------------------------------------------------------------
# Happy path + KANBAN_ROOT resolution
# ---------------------------------------------------------------------------


def test_valid_issue_writes_done_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A valid issue drops the done breadcrumb under the KANBAN_ROOT and exits 0."""
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))

    assert main(["7"]) == 0

    # The marker lands under the env-provided root, not ~/.kanban.
    assert (tmp_path / "done" / "7").exists()
    store = FsStateStore(root=tmp_path)
    assert store.recent_agent_done(7, now=0.0) is True


def test_strips_leading_hash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An agent typing ``#7`` is parsed to issue 7 (defect-3 leading-# strip)."""
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))

    assert main(["#7"]) == 0
    assert (tmp_path / "done" / "7").exists()


def test_kanban_root_unset_falls_back_to_home_kanban(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With KANBAN_ROOT UNSET the helper falls back to the ``~/.kanban`` default and writes there.

    We monkeypatch ``$HOME`` to a tmp dir so ``Path("~/.kanban").expanduser()`` resolves under tmp
    (never the operator's real home), then invoke ``main(["7"])`` and assert the marker landed at
    ``$HOME/.kanban/done/7`` — proving the fallback is real, not a no-op (the previous test never
    called ``main`` and asserted only that a never-created path was absent — tautological).
    """
    monkeypatch.delenv("KANBAN_ROOT", raising=False)
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    assert main(["7"]) == 0

    # The marker lands under the ~/.kanban default (resolved against the patched HOME), NOT tmp_path.
    assert (fake_home / ".kanban" / "done" / "7").exists()
    assert not (tmp_path / "done" / "7").exists()


def test_store_failure_reports_exit_1_never_crashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A store failure is reported (exit 1), never a crash (the documented fail-soft contract).

    ``record_agent_done`` is forced to raise; ``main`` must catch it, print to stderr, and return
    exit code 1 — never propagate the exception into the calling agent shell.
    """
    monkeypatch.setenv("KANBAN_ROOT", str(tmp_path))

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(FsStateStore, "record_agent_done", _boom)

    assert main(["7"]) == 1


# ---------------------------------------------------------------------------
# Pin enforcement (R1, §29.1)
# ---------------------------------------------------------------------------


def test_pin_mismatch_refuses_and_writes_no_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A worktree PINNED to a different issue refuses (exit 1); no marker is written."""
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setenv("KANBAN_ROOT", str(root))
    # The agent's worktree is pinned to #7, but it tries kanban-done for #9.
    worktree = tmp_path / "wt"
    worktree.mkdir()
    _write_pin(worktree, 7)
    monkeypatch.chdir(worktree)

    assert main(["9"]) == 1
    # The pin check runs BEFORE the store write — no done marker for the mismatched issue.
    assert not (root / "done" / "9").exists()


def test_pin_match_writes_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A worktree pinned to the SAME issue proceeds (exit 0); the marker is written."""
    root = tmp_path / "root"
    root.mkdir()
    monkeypatch.setenv("KANBAN_ROOT", str(root))
    worktree = tmp_path / "wt"
    worktree.mkdir()
    _write_pin(worktree, 7)
    monkeypatch.chdir(worktree)

    assert main(["7"]) == 0
    assert (root / "done" / "7").exists()

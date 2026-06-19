"""Tests for the MCP pin guard (:mod:`kanbanmate.mcp.pin`, conduit DESIGN §7).

Covers the pure pin-mismatch refusal (:func:`pin_violation`) and the defense-in-depth worktree
pin-FILE reader (:func:`read_worktree_pin`) the server uses to assert ``--issue`` agrees with the
bins' ``.claude/kanban-issue`` pin. The file reader mirrors ``bin/_pin.find_pinned_issue`` (which the
``mcp`` layer may NOT import) — same file name, same upward walk, same corrupt-pin tolerance.
"""

from __future__ import annotations

from pathlib import Path

from kanbanmate.mcp.pin import pin_violation, read_worktree_pin


def _write_pin(worktree: Path, issue: int | str) -> None:
    """Write ``<worktree>/.claude/kanban-issue`` carrying ``issue`` (the bins' pin format)."""
    claude = worktree / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "kanban-issue").write_text(f"{issue}\n", encoding="utf-8")


# --------------------------------------------------------------------------- pin_violation


def test_pin_violation_mismatch_returns_refusal() -> None:
    """A requested issue different from the pin returns a refusal naming both."""
    out = pin_violation(99, 42)
    assert out is not None
    assert "#99" in out and "#42" in out


def test_pin_violation_match_returns_none() -> None:
    """A matching issue returns ``None`` (the write may proceed)."""
    assert pin_violation(42, 42) is None


# --------------------------------------------------------------------------- read_worktree_pin


def test_read_worktree_pin_at_start_dir(tmp_path: Path) -> None:
    """The pin is read from the start dir's ``.claude/kanban-issue``."""
    _write_pin(tmp_path, 9)
    assert read_worktree_pin(tmp_path) == 9


def test_read_worktree_pin_walks_up_from_subdir(tmp_path: Path) -> None:
    """The pin is found by walking UP from a nested working dir (the agent's cwd)."""
    _write_pin(tmp_path, 7)
    nested = tmp_path / "src" / "kanbanmate"
    nested.mkdir(parents=True)
    assert read_worktree_pin(nested) == 7


def test_read_worktree_pin_absent_returns_none(tmp_path: Path) -> None:
    """An absent pin file → ``None`` (the server proceeds on ``--issue`` alone)."""
    assert read_worktree_pin(tmp_path) is None


def test_read_worktree_pin_corrupt_returns_none(tmp_path: Path) -> None:
    """A non-integer (corrupt) pin file is treated as ABSENT — a corrupt pin must not hard-block."""
    _write_pin(tmp_path, "not-a-number")
    assert read_worktree_pin(tmp_path) is None

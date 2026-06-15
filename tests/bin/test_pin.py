"""Tests for the worktree issue-pin reader (:mod:`kanbanmate.bin._pin`, §29.1).

The pin file (``<worktree>/.claude/kanban-issue``) constrains a launched agent to its own ticket.
These cover: finding the pin by walking up from the cwd, the matched/mismatched verdict, the
unpinned fallback (no file), and a corrupt-pin tolerance.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kanbanmate.bin._pin import check_pin, find_pinned_issue, parse_issue_arg


def _write_pin(worktree: Path, issue: int | str) -> None:
    """Write ``<worktree>/.claude/kanban-issue`` carrying ``issue``."""
    claude = worktree / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / "kanban-issue").write_text(f"{issue}\n", encoding="utf-8")


def test_find_pin_at_start_dir(tmp_path: Path) -> None:
    """The pin is found in the start dir's ``.claude/``."""
    _write_pin(tmp_path, 42)
    assert find_pinned_issue(tmp_path) == 42


def test_find_pin_walks_up_from_subdir(tmp_path: Path) -> None:
    """The pin is found by walking UP from a nested working dir (the agent's cwd)."""
    _write_pin(tmp_path, 7)
    nested = tmp_path / "src" / "pkg"
    nested.mkdir(parents=True)
    assert find_pinned_issue(nested) == 7


def test_no_pin_returns_none(tmp_path: Path) -> None:
    """Absent pin file → ``None`` (the unpinned operator fallback)."""
    assert find_pinned_issue(tmp_path) is None


def test_corrupt_pin_treated_as_absent(tmp_path: Path) -> None:
    """A non-integer pin is tolerated as absent (never hard-blocks)."""
    _write_pin(tmp_path, "not-a-number")
    assert find_pinned_issue(tmp_path) is None


def test_check_pin_match_returns_none(tmp_path: Path) -> None:
    """A matching issue passes (no error)."""
    _write_pin(tmp_path, 7)
    assert check_pin(7, start=tmp_path) is None


def test_check_pin_mismatch_returns_error(tmp_path: Path) -> None:
    """A mismatched issue returns a clear refusal message naming both numbers."""
    _write_pin(tmp_path, 7)
    err = check_pin(9, start=tmp_path)
    assert err is not None
    assert "#9" in err and "#7" in err


def test_check_pin_unpinned_passes(tmp_path: Path) -> None:
    """No pin file → any issue passes (operator use outside a worktree)."""
    assert check_pin(123, start=tmp_path) is None


# ---------------------------------------------------------------------------
# parse_issue_arg — defensive leading-'#' strip (defect 3)
# ---------------------------------------------------------------------------


def test_parse_issue_arg_bare_int() -> None:
    """A bare integer token parses unchanged (the contract value the prompts fill)."""
    assert parse_issue_arg("151") == 151


def test_parse_issue_arg_strips_leading_hash() -> None:
    """A leading ``#`` (and surrounding whitespace) is stripped before int-parsing (defect 3)."""
    assert parse_issue_arg("#151") == 151
    assert parse_issue_arg("  #7 ") == 7


def test_parse_issue_arg_rejects_non_int() -> None:
    """A non-integer token (after the strip) raises ValueError for the caller to surface."""
    with pytest.raises(ValueError):
        parse_issue_arg("nope")

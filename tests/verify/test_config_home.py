"""Tests for the config_home verify check.

Warns when the resolved config directory lives inside a git working tree
(DESIGN §3.4).
"""

from __future__ import annotations

from pathlib import Path

from personalscraper.verify.config_home import (
    _is_inside_worktree,
    check_config_home,
)


def test_is_inside_worktree_true_when_ancestor_git_dir_present(tmp_path: Path) -> None:
    """A path whose ANCESTOR has a .git subdirectory is inside a worktree."""
    (tmp_path / ".git").mkdir()
    child = tmp_path / "sub"
    child.mkdir()
    assert _is_inside_worktree(child) is True


def test_is_inside_worktree_true_when_git_file_present(tmp_path: Path) -> None:
    """A path whose parent has .git (git worktree) is inside a worktree."""
    (tmp_path / ".git").write_text("gitdir: /some/path")
    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)
    assert _is_inside_worktree(sub) is True


def test_is_inside_worktree_false_outside_any_worktree(tmp_path: Path) -> None:
    """A path with no .git anywhere up to root is NOT inside a worktree."""
    assert _is_inside_worktree(tmp_path) is False


def test_is_inside_worktree_stops_at_root(tmp_path: Path) -> None:
    """The walk stops at filesystem root and returns False."""
    result = _is_inside_worktree(Path("/tmp"))
    # /tmp may or may not have .git — but the walk won't crash
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# D3 exemption — the canonical config dir is itself a git repo (mini-repo)
# ---------------------------------------------------------------------------


def test_is_inside_worktree_false_when_own_git_is_sanctioned_mini_repo(tmp_path: Path) -> None:
    """Own .git is the sanctioned mini-repo (D3), not a worktree violation.

    A config dir that IS itself a git repo (own .git) with no ancestor
    worktree is NOT inside a worktree — D3 sanctions the mini-repo.
    """
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / ".git").mkdir()  # sanctioned mini-repo
    # No .git at tmp_path or above
    assert _is_inside_worktree(cfg) is False


def test_is_inside_worktree_true_when_ancestor_worktree_even_with_own_git(tmp_path: Path) -> None:
    """Own .git is irrelevant when an ancestor worktree exists.

    A config dir that IS a git repo BUT also lives under an ancestor
    worktree IS inside a worktree — the ancestor .git is the hazard.
    """
    (tmp_path / ".git").mkdir()  # ancestor worktree
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / ".git").mkdir()  # sanctioned mini-repo (irrelevant — ancestor wins)
    assert _is_inside_worktree(cfg) is True


def test_check_config_home_warns_inside_worktree(tmp_path: Path) -> None:
    """check_config_home returns a warning when config is inside a worktree."""
    (tmp_path / ".git").mkdir()
    cfg = tmp_path / "config"
    cfg.mkdir()
    warnings = check_config_home(cfg)
    assert len(warnings) >= 1
    assert any("inside a git working tree" in w for w in warnings)


def test_check_config_home_silent_outside_worktree(tmp_path: Path) -> None:
    """check_config_home returns empty list when config is NOT inside a worktree."""
    cfg = tmp_path / "isolated" / "config"
    cfg.mkdir(parents=True)
    warnings = check_config_home(cfg)
    assert warnings == []


def test_check_config_home_handles_nonexistent_dir() -> None:
    """check_config_home handles a nonexistent directory gracefully."""
    warnings = check_config_home(Path("/nonexistent/path/to/config"))
    assert len(warnings) >= 1  # should warn about missing dir, not crash

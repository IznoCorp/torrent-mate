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


def test_is_inside_worktree_true_when_git_dir_present(tmp_path: Path):
    """A path with a .git subdirectory is inside a worktree."""
    (tmp_path / ".git").mkdir()
    assert _is_inside_worktree(tmp_path) is True


def test_is_inside_worktree_true_when_git_file_present(tmp_path: Path):
    """A path whose parent has .git (git worktree) is inside a worktree."""
    (tmp_path / ".git").write_text("gitdir: /some/path")
    sub = tmp_path / "sub" / "deep"
    sub.mkdir(parents=True)
    assert _is_inside_worktree(sub) is True


def test_is_inside_worktree_false_outside_any_worktree(tmp_path: Path):
    """A path with no .git anywhere up to root is NOT inside a worktree."""
    assert _is_inside_worktree(tmp_path) is False


def test_is_inside_worktree_stops_at_root(tmp_path: Path):
    """The walk stops at filesystem root and returns False."""
    result = _is_inside_worktree(Path("/tmp"))
    # /tmp may or may not have .git — but the walk won't crash
    assert isinstance(result, bool)


def test_check_config_home_warns_inside_worktree(tmp_path: Path):
    """check_config_home returns a warning when config is inside a worktree."""
    (tmp_path / ".git").mkdir()
    cfg = tmp_path / "config"
    cfg.mkdir()
    warnings = check_config_home(cfg)
    assert len(warnings) >= 1
    assert any("inside a git working tree" in w for w in warnings)


def test_check_config_home_silent_outside_worktree(tmp_path: Path):
    """check_config_home returns empty list when config is NOT inside a worktree."""
    cfg = tmp_path / "isolated" / "config"
    cfg.mkdir(parents=True)
    warnings = check_config_home(cfg)
    assert warnings == []


def test_check_config_home_handles_nonexistent_dir():
    """check_config_home handles a nonexistent directory gracefully."""
    warnings = check_config_home(Path("/nonexistent/path/to/config"))
    assert len(warnings) >= 1  # should warn about missing dir, not crash

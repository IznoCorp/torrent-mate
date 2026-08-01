"""Unit tests for config_git mini-repo helper (DESIGN §3.2)."""

import subprocess
from pathlib import Path

from personalscraper.conf.config_git import (
    commit_config_dir,
    ensure_config_repo,
)


def _configure_git_user(config_dir: Path) -> None:
    """Set git user.name and user.email for tests that commit.

    CI/sandbox environments may not have a global git user configured,
    so we set it explicitly in the test repo to avoid commit failures.
    """
    subprocess.run(
        ["git", "-C", str(config_dir), "config", "user.email", "test@test"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(config_dir), "config", "user.name", "Test"],
        capture_output=True,
    )


def test_ensure_config_repo_creates_git_dir(tmp_path: Path):
    """ensure_config_repo runs git init when .git is absent."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    result = ensure_config_repo(cfg)
    assert result is True
    assert (cfg / ".git").is_dir()


def test_ensure_config_repo_idempotent(tmp_path: Path):
    """Calling ensure_config_repo on an existing repo is a no-op."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    ensure_config_repo(cfg)
    result = ensure_config_repo(cfg)
    assert result is True


def test_commit_config_dir_creates_initial_commit(tmp_path: Path):
    """commit_config_dir commits all files in an initialized repo."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    ensure_config_repo(cfg)
    _configure_git_user(cfg)
    (cfg / "test.json5").write_text('{"key": "val"}')
    result = commit_config_dir(cfg, "initial commit")
    assert result is True
    # Verify commit exists
    log = subprocess.run(
        ["git", "-C", str(cfg), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert "initial commit" in log.stdout


def test_commit_config_dir_returns_false_on_git_failure(tmp_path: Path):
    """commit_config_dir returns False (not raises) when git fails."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    # No git init → commit should fail softly
    result = commit_config_dir(cfg, "should fail")
    assert result is False


def test_commit_config_dir_handles_no_changes(tmp_path: Path):
    """commit_config_dir returns True even if there's nothing to commit."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    ensure_config_repo(cfg)
    _configure_git_user(cfg)
    # Create and commit a file
    (cfg / "test.json5").write_text('{"key": "val"}')
    commit_config_dir(cfg, "first")
    # Second commit with no changes
    result = commit_config_dir(cfg, "no changes")
    # Should still return True (not an error condition)
    assert result is True


def test_commit_config_dir_stages_untracked_files(tmp_path: Path):
    """commit_config_dir uses -A to stage new, modified, and deleted files."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    ensure_config_repo(cfg)
    _configure_git_user(cfg)
    (cfg / "a.json5").write_text('{"a": 1}')
    commit_config_dir(cfg, "add a")
    # Add new file, modify existing
    (cfg / "b.json5").write_text('{"b": 2}')
    (cfg / "a.json5").write_text('{"a": 2}')
    result = commit_config_dir(cfg, "add b, modify a")
    assert result is True
    log = subprocess.run(
        ["git", "-C", str(cfg), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert "add b, modify a" in log.stdout

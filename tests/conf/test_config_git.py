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


def _rev_count(config_dir: Path) -> int:
    """Return the number of commits on HEAD (rev-list --count)."""
    result = subprocess.run(
        ["git", "-C", str(config_dir), "rev-list", "--count", "HEAD"],
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip())


def _ls_tree_files(config_dir: Path) -> list[str]:
    """Return the sorted list of tracked files from ``git ls-tree -r HEAD``."""
    result = subprocess.run(
        ["git", "-C", str(config_dir), "ls-tree", "-r", "HEAD", "--name-only"],
        capture_output=True,
        text=True,
    )
    return sorted(result.stdout.strip().splitlines())


def test_ensure_config_repo_creates_git_dir(tmp_path: Path):
    """ensure_config_repo runs git init when .git is absent."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    result = ensure_config_repo(cfg)
    assert result is True
    assert (cfg / ".git").is_dir()


def test_ensure_config_repo_idempotent(tmp_path: Path):
    """Calling ensure_config_repo on an existing repo is a no-op (F-K).

    Verifies that a second call does NOT re-initialize: .git directory
    mtime is unchanged and no side effects occur.
    """
    cfg = tmp_path / "config"
    cfg.mkdir()
    ensure_config_repo(cfg)
    git_mtime = (cfg / ".git").stat().st_mtime
    result = ensure_config_repo(cfg)
    assert result is True
    # .git mtime unchanged — no re-init occurred.
    assert (cfg / ".git").stat().st_mtime == git_mtime


def test_ensure_config_repo_writes_gitignore(tmp_path: Path):
    """ensure_config_repo writes .gitignore ignoring .backups/ (F-I)."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    ensure_config_repo(cfg)
    gitignore = cfg / ".gitignore"
    assert gitignore.is_file()
    content = gitignore.read_text()
    assert ".backups/" in content


def test_commit_config_dir_creates_initial_commit(tmp_path: Path):
    """commit_config_dir commits all files in an initialized repo (F-K).

    Asserts commit content via ``git ls-tree``, not just log message.
    """
    cfg = tmp_path / "config"
    cfg.mkdir()
    ensure_config_repo(cfg)
    _configure_git_user(cfg)
    (cfg / "test.json5").write_text('{"key": "val"}')
    result = commit_config_dir(cfg, "initial commit")
    assert result is True
    # Verify commit exists.
    log = subprocess.run(
        ["git", "-C", str(cfg), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    assert "initial commit" in log.stdout
    # Verify commit CONTENT (F-K): ls-tree must contain the expected file.
    files = _ls_tree_files(cfg)
    assert "test.json5" in files, f"ls-tree missing test.json5, got: {files}"
    assert ".gitignore" in files, f"ls-tree missing .gitignore, got: {files}"


def test_commit_config_dir_returns_false_on_git_failure(tmp_path: Path):
    """commit_config_dir returns False (not raises) when git fails."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    # No git init → add fails softly
    result = commit_config_dir(cfg, "should fail")
    assert result is False


def test_commit_config_dir_handles_no_changes(tmp_path: Path):
    """commit_config_dir returns True with NO new commit when tree is clean (F-H).

    After a first commit, a second call with no changes must:
    - Return True (not an error).
    - NOT create an additional commit (rev-list count unchanged).
    """
    cfg = tmp_path / "config"
    cfg.mkdir()
    ensure_config_repo(cfg)
    _configure_git_user(cfg)
    # Create and commit a file.
    (cfg / "test.json5").write_text('{"key": "val"}')
    commit_config_dir(cfg, "first")
    count_before = _rev_count(cfg)
    # Second commit with no changes.
    result = commit_config_dir(cfg, "no changes")
    # Should still return True (not an error condition).
    assert result is True
    # NO new commit — rev-list count unchanged (F-H kill-probe).
    count_after = _rev_count(cfg)
    assert count_after == count_before, (
        f"Expected {count_before} commits, got {count_after} — an empty commit was created when it should not have been"
    )


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
    # Content assertion: ls-tree contains both files.
    files = _ls_tree_files(cfg)
    assert "a.json5" in files
    assert "b.json5" in files


def test_commit_config_dir_staging_not_skipped(tmp_path: Path):
    """Probe (e) kill: staging MUST happen.

    A file added but not staged before commit_config_dir still lands in the
    commit. This test fails if ``git add -A`` is ever skipped or bypassed — it
    proves the commit actually captured the file content, not an empty tree.
    """
    cfg = tmp_path / "config"
    cfg.mkdir()
    ensure_config_repo(cfg)
    _configure_git_user(cfg)
    # Initial commit captures .gitignore.
    commit_config_dir(cfg, "initial")
    count_before = _rev_count(cfg)

    # Add a NEW file — this is NOT staged manually.  commit_config_dir
    # must auto-stage it via ``git add -A`` and commit it.
    (cfg / "untracked.json5").write_text('{"untracked": true}')
    result = commit_config_dir(cfg, "stage untracked")
    assert result is True

    # A new commit must exist.
    count_after = _rev_count(cfg)
    assert count_after == count_before + 1, (
        f"Expected {count_before + 1} commits, got {count_after} — commit_config_dir may have skipped staging"
    )
    # The untracked file must be in the commit.
    files = _ls_tree_files(cfg)
    assert "untracked.json5" in files, f"untracked.json5 not in commit, ls-tree: {files}"

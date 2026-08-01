# Phase 02 — Config Git Mini-Repo + S4 Auto-Commit Hook

**Goal:** Create the `config_git.py` helper for the canonical mini-repo, then wire the S4 web config save path to auto-commit after each successful write.

**Design ref:** §3.2 Canonical mini-repo (D3).

## Gate (entry conditions)

- [ ] Phase 01 complete — `personalscraper/conf/sync.py` exists with `sync_config_dir()` working.
- [ ] `personalscraper/conf/loader.py` and `personalscraper/web/routes/config.py` understood (save path at `put_file()`, line 587).

---

## Sub-phase 2.1 — `config_git.py` helper module (test-first)

**Commit:** `feat(config-home): add config_git mini-repo helper with fail-soft contract`

**Files:**

- Create: `personalscraper/conf/config_git.py`
- Create: `tests/conf/test_config_git.py`

**Interfaces:**

- Produces: `commit_config_dir(config_dir: Path, message: str) -> bool` — returns `True` on success, `False` on any failure (fail-soft). Logs warnings on failure.
- Produces: `ensure_config_repo(config_dir: Path) -> bool` — `git init` if no `.git` exists; returns `True` if the dir is now a git repo (newly created or already was).

### Task 2.1.1: Write unit tests

```python
# tests/conf/test_config_git.py
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from personalscraper.conf.config_git import (
    commit_config_dir,
    ensure_config_repo,
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
    (cfg / "test.json5").write_text('{"key": "val"}')
    result = commit_config_dir(cfg, "initial commit")
    assert result is True
    # Verify commit exists
    log = subprocess.run(
        ["git", "-C", str(cfg), "log", "--oneline"],
        capture_output=True, text=True,
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
    (cfg / "a.json5").write_text('{"a": 1}')
    commit_config_dir(cfg, "add a")
    # Add new file, modify existing
    (cfg / "b.json5").write_text('{"b": 2}')
    (cfg / "a.json5").write_text('{"a": 2}')
    result = commit_config_dir(cfg, "add b, modify a")
    assert result is True
    log = subprocess.run(
        ["git", "-C", str(cfg), "log", "--oneline"],
        capture_output=True, text=True,
    )
    assert "add b, modify a" in log.stdout
```

- [ ] Run: `pytest tests/conf/test_config_git.py -v` — expect FAIL

### Task 2.1.2: Implement `config_git.py`

```python
# personalscraper/conf/config_git.py
"""Mini-repo helper for the canonical config directory (DESIGN §3.2).

The canonical config lives at ``~/.torrentmate/config`` and is a local-only
git repo (no remote, never pushed).  This module provides fail-soft wrappers
so that a git failure never blocks a config save.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("conf.config_git")

_GIT = "git"


def _run_git(
    config_dir: Path,
    *args: str,
    timeout: int = 10,
) -> subprocess.CompletedProcess[str]:
    """Run a git command in *config_dir* and return the CompletedProcess.

    Args:
        config_dir: Path to the git working tree.
        *args: Git sub-command and arguments.
        timeout: Seconds before the subprocess is killed.

    Returns:
        CompletedProcess with captured stdout/stderr as text.
    """
    return subprocess.run(
        [_GIT, "-C", str(config_dir), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def ensure_config_repo(config_dir: Path) -> bool:
    """Initialize a git repo in *config_dir* if one doesn't exist.

    Idempotent: calling on an already-initialized directory is a no-op.

    Args:
        config_dir: Path to the config directory.

    Returns:
        ``True`` if the directory is now a git repo (pre-existing or newly
        created). ``False`` if ``git init`` failed.
    """
    if (config_dir / ".git").is_dir():
        return True
    try:
        result = _run_git(config_dir, "init")
        if result.returncode != 0:
            log.warning(
                "config_git.init_failed",
                config_dir=str(config_dir),
                stderr=result.stderr.strip(),
            )
            return False
        log.info("config_git.repo_initialized", config_dir=str(config_dir))
        return True
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning(
            "config_git.init_error",
            config_dir=str(config_dir),
            error=str(exc),
        )
        return False


def commit_config_dir(config_dir: Path, message: str) -> bool:
    """Commit all changes in *config_dir* with the given *message*.

    Uses ``git add -A`` to stage new, modified, and deleted files, then
    ``git commit``.  **Fail-soft**: a git failure never raises — it returns
    ``False`` and logs a warning.

    If there is nothing to commit (clean tree), returns ``True`` — an empty
    commit is not an error.

    Args:
        config_dir: Path to the git working tree.
        message: Commit message (e.g. ``"config_edit: web.json5 (web-UI)"``).

    Returns:
        ``True`` if the commit succeeded or there was nothing to commit.
        ``False`` on any git failure.
    """
    try:
        # Stage everything.
        result = _run_git(config_dir, "add", "-A")
        if result.returncode != 0:
            log.warning(
                "config_git.add_failed",
                config_dir=str(config_dir),
                stderr=result.stderr.strip(),
            )
            return False

        # Commit. --allow-empty avoids exit-1 on a clean tree.
        result = _run_git(
            config_dir, "commit", "--allow-empty", "-m", message,
        )
        if result.returncode != 0:
            log.warning(
                "config_git.commit_failed",
                config_dir=str(config_dir),
                stderr=result.stderr.strip(),
            )
            return False

        # Distinguish "nothing to commit" from a real commit for logging.
        if "nothing to commit" in result.stdout.lower() or "nothing added" in result.stdout.lower():
            log.debug("config_git.nothing_to_commit", config_dir=str(config_dir))
        else:
            log.info("config_git.committed", config_dir=str(config_dir), message=message)

        return True
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning(
            "config_git.commit_error",
            config_dir=str(config_dir),
            error=str(exc),
        )
        return False
```

- [ ] Run: `pytest tests/conf/test_config_git.py -v` — expect all PASS
- [ ] Commit: `git add personalscraper/conf/config_git.py tests/conf/test_config_git.py && git commit -m "feat(config-home): add config_git mini-repo helper with fail-soft contract"`

---

## Sub-phase 2.2 — Wire S4 auto-commit hook

**Commit:** `feat(config-home): auto-commit config saves to canonical mini-repo (S4 web-UI)`

**Files:**

- Modify: `personalscraper/web/routes/config.py` — insert `commit_config_dir` call after successful save
- Modify: `tests/web/test_config_routes_write.py` — add test asserting auto-commit fires

**Interfaces:**

- Consumes: `commit_config_dir(config_dir, message) -> bool` from Phase 2.1

### Task 2.2.1: Add auto-commit in `put_file()`

In `personalscraper/web/routes/config.py`, after line 701 (`atomic_write_text(file_path, content)`) and the `os.chmod` on line 704, insert:

```python
            # Auto-commit to the canonical mini-repo (DESIGN §3.2).
            # Fail-soft: a git failure never blocks or fails the save.
            try:
                from personalscraper.conf.config_git import (
                    commit_config_dir,
                    ensure_config_repo,
                )
                if ensure_config_repo(config_dir):
                    commit_config_dir(
                        config_dir,
                        f"config_edit: {name} (web-UI)",
                    )
            except Exception:
                # Fail-soft per DESIGN §3.2 — log already emitted by
                # commit_config_dir; double-wrap for any import/other error.
                pass
```

### Task 2.2.2: Add test for auto-commit

Add to `tests/web/test_config_routes_write.py`:

```python
def test_put_file_auto_commits_to_mini_repo(
    client, auth_headers, writable_config_dir
):
    """After a successful PUT, the config dir gets a git commit (DESIGN §3.2)."""
    import subprocess

    # Initialize the config dir as a git repo
    subprocess.run(
        ["git", "-C", str(writable_config_dir), "init"],
        capture_output=True,
    )
    # Set git user for the test (required for commit)
    subprocess.run(
        ["git", "-C", str(writable_config_dir), "config", "user.email", "test@test"],
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(writable_config_dir), "config", "user.name", "Test"],
        capture_output=True,
    )

    sha_before = _git_head_sha(writable_config_dir)

    # Perform a valid save
    paths_file = writable_config_dir / "paths.json5"
    original = json5.loads(paths_file.read_text())
    resp = client.put(
        f"/api/config/files/paths.json5",
        json={"values": original, "base_sha256": _sha256(paths_file)},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    sha_after = _git_head_sha(writable_config_dir)
    # A new commit must have been created
    assert sha_after is not None
    assert sha_after != sha_before


def test_put_file_save_succeeds_even_when_git_fails(
    client, auth_headers, writable_config_dir
):
    """Fail-soft: a broken git repo does not block the config save."""
    # Corrupt .git to simulate a git failure
    git_dir = writable_config_dir / ".git"
    git_dir.mkdir(exist_ok=True)
    (git_dir / "HEAD").write_text("garbage")

    paths_file = writable_config_dir / "paths.json5"
    original = json5.loads(paths_file.read_text())
    resp = client.put(
        f"/api/config/files/paths.json5",
        json={"values": original, "base_sha256": _sha256(paths_file)},
        headers=auth_headers,
    )
    # Save must still succeed (git failure is non-blocking)
    assert resp.status_code == 200
```

- [ ] Run: `pytest tests/web/test_config_routes_write.py -v -k "auto_commit or git_fail"` — expect all PASS
- [ ] Commit: `git add personalscraper/web/routes/config.py tests/web/test_config_routes_write.py && git commit -m "feat(config-home): auto-commit config saves to canonical mini-repo (S4 web-UI)"`

---

## Gate (exit conditions)

- [ ] `pytest tests/conf/test_config_git.py -v` — all unit tests pass
- [ ] `pytest tests/web/test_config_routes_write.py -v` — all write tests pass (including new auto-commit tests)
- [ ] Manual: `git -C ~/.torrentmate/config log --oneline` after a web-UI save — shows a `config_edit` commit
- [ ] `make lint` — zero errors

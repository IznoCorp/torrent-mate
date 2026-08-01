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


_GITIGNORE_CONTENT = "# Gitignore for the canonical config mini-repo.\n.backups/\n"


def ensure_config_repo(config_dir: Path) -> bool:
    """Initialize a git repo in *config_dir* if one doesn't exist.

    Idempotent: calling on an already-initialized directory is a no-op.
    Writes a minimal ``.gitignore`` (ignores ``.backups/``) so that S4
    backup churn is not versioned.

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
        # Write minimal .gitignore so backup churn isn't versioned (F-I).
        (config_dir / ".gitignore").write_text(_GITIGNORE_CONTENT, encoding="utf-8")
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
    checks ``git status --porcelain``.  If the staging area is empty
    (nothing to commit), returns ``True`` **without** creating a commit
    — no empty commits pollute the history.  Otherwise creates a single
    commit with ``-m``.

    **Fail-soft**: a git failure never raises — it returns ``False`` and
    logs a warning.

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

        # Check if there is anything staged — no empty commits (F-H).
        status_result = _run_git(config_dir, "status", "--porcelain")
        if status_result.returncode != 0:
            log.warning(
                "config_git.status_failed",
                config_dir=str(config_dir),
                stderr=status_result.stderr.strip(),
            )
            return False

        if not status_result.stdout.strip():
            log.debug("config_git.nothing_to_commit", config_dir=str(config_dir))
            return True

        # Commit only when there are staged changes.
        result = _run_git(
            config_dir,
            "commit",
            "-m",
            message,
        )
        if result.returncode != 0:
            log.warning(
                "config_git.commit_failed",
                config_dir=str(config_dir),
                stderr=result.stderr.strip(),
            )
            return False

        log.info("config_git.committed", config_dir=str(config_dir), message=message)
        return True
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning(
            "config_git.commit_error",
            config_dir=str(config_dir),
            error=str(exc),
        )
        return False

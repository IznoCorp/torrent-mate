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
            config_dir,
            "commit",
            "--allow-empty",
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

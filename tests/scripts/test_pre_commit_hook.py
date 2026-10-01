"""The pre-commit hook's refusals reach every commit, not only some (B-304).

WHAT IT PAID FOR. `git add -f` applied to a PATH rather than to the ignored
files it was needed for swept 28 375 files into a commit, `node_modules` entire,
and nothing in the repository refused it. And the hook's one refusal of a
committed command — `check-command-safety.py`, a `curl` with no timeout, an
unfiltered `rg` — sat BELOW an early `exit 0` taken whenever no
`test_design_*.py` was staged, so it ran on a design-contract commit and on
nothing else.

The hook is run as git runs it, in a throwaway repository holding the hook and
the script it calls.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def repository(tmp_path: Path) -> Path:
    """A throwaway repository with the hook and the safety script in place.

    Args:
        tmp_path: The pytest scratch directory.

    Returns:
        The repository's root.
    """
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(ROOT / "scripts" / "check-command-safety.py", repo / "scripts")
    environment = clean_environment()
    for command in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        subprocess.run(["git", *command], cwd=repo, check=True, env=environment)
    return repo


def clean_environment() -> dict[str, str]:
    """The environment with a hook's git variables stripped."""
    return {
        key: value
        for key, value in os.environ.items()
        if key not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")
    }


def stage_and_run(repo: Path, path: str, content: str) -> subprocess.CompletedProcess[str]:
    """Stages one file, forced, and runs the hook over the index.

    Args:
        repo: The throwaway repository.
        path: The file to write and stage.
        content: What it holds.

    Returns:
        The hook's finished process.
    """
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    environment = clean_environment()
    subprocess.run(["git", "add", "-f", path], cwd=repo, check=True, env=environment)
    return subprocess.run(
        ["bash", str(ROOT / "hooks" / "pre-commit")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def test_a_staged_node_modules_is_refused(tmp_path: Path) -> None:
    """A vendored tree forced into the index is refused, and named."""
    done = stage_and_run(repository(tmp_path), "frontend/node_modules/left-pad/index.js", "module.exports = 1;\n")
    assert done.returncode != 0
    assert "node_modules" in done.stderr


def test_an_unsafe_command_is_refused_without_a_design_test(tmp_path: Path) -> None:
    """A timeout-less `curl` in a script is refused on an ordinary commit."""
    # Spelled in two halves so this file is not itself the unsafe command.
    unsafe = "cu" + "rl https://example.org/"
    done = stage_and_run(repository(tmp_path), "scripts/fetch.sh", f"#!/bin/sh\n{unsafe}\n")
    assert done.returncode != 0


def test_prose_quoting_a_command_passes(tmp_path: Path) -> None:
    """A note that QUOTES a command is not one: only scripts are read."""
    quoted = "r" + "g pattern"
    done = stage_and_run(repository(tmp_path), "notes.md", f"It was found with `{quoted}`.\n")
    assert done.returncode == 0, done.stderr

"""Regression test for scripts/pre-push leaking git-hook env vars into checks.

Git invokes hooks with GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE set in the
environment. Left unsanitized, that leaks into every subprocess the hook
spawns — including pytest, which runs tests/scripts/test_phase_gate.py-style
tests that build an "isolated" git repo in a tmp_path. Those tests' `git -C
<tmp_path> commit` calls get silently redirected by the leaked GIT_DIR /
GIT_WORK_TREE into the REAL repo the hook is running in, clobbering whatever
branch happens to be checked out (observed in the wild: a worktree's checked
-out branch was overwritten with a test's synthetic "chore: init" commits).

This test simulates the leaked hook environment, runs the real
scripts/pre-push with a stub ``python`` (so it never actually spends minutes
re-running ruff/mypy/pytest) and asserts none of the sensitive git env vars
survive into any of the 5 checks.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRE_PUSH = ROOT / "scripts" / "pre-push"

_LEAKED_VARS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX")


def _fake_python(tmp_path: Path, dump_file: Path) -> Path:
    """Create a stub ``python`` that records env vars instead of doing real work.

    Args:
        tmp_path: Directory to place the stub executable in (prepended to PATH).
        dump_file: File the stub appends one env snapshot to per invocation.

    Returns:
        Path to the stub script.
    """
    script = tmp_path / "python"
    lines = [f'echo "{var}=${{{var}:-UNSET}}" >> "{dump_file}"' for var in _LEAKED_VARS]
    script.write_text(
        "#!/usr/bin/env bash\n" + "\n".join(lines) + '\necho "---" >> "' + str(dump_file) + '"\nexit 0\n',
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


def test_pre_push_unsets_leaked_git_env_before_any_check(tmp_path: Path) -> None:
    """None of the leaked GIT_* vars must survive into any of the 5 checks."""
    dump_file = tmp_path / "env_dump.txt"
    _fake_python(tmp_path, dump_file)

    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env['PATH']}"
    # Simulate exactly what git sets when invoking a hook.
    env["GIT_DIR"] = "/tmp/leaked-git-dir/.git"
    env["GIT_WORK_TREE"] = "/tmp/leaked-git-dir"
    env["GIT_INDEX_FILE"] = "/tmp/leaked-git-dir/.git/index"
    env["GIT_PREFIX"] = ""

    result = subprocess.run(
        [str(PRE_PUSH)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    dump = dump_file.read_text(encoding="utf-8")
    # 5 checks -> 5 snapshots, every var UNSET in every one of them.
    assert dump.count("---") == 5, f"expected 5 check invocations, got dump:\n{dump}"
    for var in _LEAKED_VARS:
        assert f"{var}=UNSET" in dump, f"{var} leaked into a check:\n{dump}"
        assert f"{var}=/tmp/leaked-git-dir" not in dump

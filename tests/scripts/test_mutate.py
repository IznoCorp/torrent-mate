"""The mutation tool's verdict, exercised on a sandbox repository.

WHY THESE EXIST. `scripts/mutate.sh` is how every rule of this repository is
proved: break the behaviour, watch the rule fall, restore. A tool that says
« NO RULE FELL » over a rule that fell is a false green, and it said exactly that
twice over `audit2.py`'s R13 — a rule that prints « 1 violations » and gives its
verdict by exiting 1, with no `FAIL` line for the tool's grep to find.

Every test copies the script into a throwaway git repository with a stand-in
served copy and a stand-in `npm`, so none of them builds the maquette or touches
the copy the harness reads.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "mutate.sh"


def sandbox(tmp_path: Path, rule_body: str) -> tuple[Path, dict[str, str]]:
    """A committed repository holding the script, a target, a rule and the stand-ins."""
    repository = tmp_path / "repository"
    (repository / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repository / "scripts" / "mutate.sh")
    harness = repository / "frontend" / "maquette" / "harness"
    harness.mkdir(parents=True)
    (harness / "served_copy.py").write_text("")
    (repository / "frontend" / "maquette" / "design").mkdir()
    (repository / "target.txt").write_text("before\n")
    (repository / "rule.py").write_text(rule_body)
    stand_ins = tmp_path / "bin"
    stand_ins.mkdir()
    npm = stand_ins / "npm"
    npm.write_text("#!/bin/sh\nexit 0\n")
    npm.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{stand_ins}:{os.environ['PATH']}",
        "GIT_AUTHOR_NAME": "tester",
        "GIT_AUTHOR_EMAIL": "tester@example.invalid",
        "GIT_COMMITTER_NAME": "tester",
        "GIT_COMMITTER_EMAIL": "tester@example.invalid",
    }
    for command in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "sandbox"]):
        subprocess.run(command, cwd=repository, check=True, env=environment)
    return repository, environment


def mutate(repository: Path, environment: dict[str, str]) -> subprocess.CompletedProcess:
    """Runs the copied script with one mutation of the target against the rule."""
    return subprocess.run(
        ["bash", "scripts/mutate.sh", "target.txt", 't.replace("before", "after")', "rule.py"],
        cwd=repository,
        capture_output=True,
        text=True,
        timeout=60,
        env=environment,
    )


def test_a_rule_whose_verdict_is_its_exit_code_is_seen_to_fall(tmp_path: Path) -> None:
    """A rule that exits 1 without a `FAIL` line has fallen, and the tool says so and says how."""
    repository, environment = sandbox(tmp_path, 'print("TOTAL, second pass: 2 violations")\nraise SystemExit(1)\n')
    result = mutate(repository, environment)
    assert result.returncode == 0, result.stderr
    assert "NO RULE FELL" not in result.stdout, result.stdout
    assert "exited 1" in result.stdout, result.stdout
    assert (repository / "target.txt").read_text() == "before\n"


def test_a_rule_that_holds_is_still_reported_as_not_falling(tmp_path: Path) -> None:
    """The control: exit 0 and no `FAIL` line is still « no rule fell »."""
    repository, environment = sandbox(tmp_path, 'print("0 violations")\n')
    result = mutate(repository, environment)
    assert result.returncode == 0, result.stderr
    assert "NO RULE FELL" in result.stdout, result.stdout

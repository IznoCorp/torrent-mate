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
import socket
import subprocess
import time
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "mutate.sh"

# A stand-in for `server.py --serve PORT DIRECTORY`: it only listens.
STAND_IN_HOST = (
    "import socket, sys, time\n"
    "server = socket.socket()\n"
    "server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)\n"
    "server.bind(('127.0.0.1', int(sys.argv[2])))\n"
    "server.listen()\n"
    "time.sleep(60)\n"
)


def free_port() -> int:
    """A port nothing listens on, so no sandbox ever touches the real harness host."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def listening(port: int) -> bool:
    """Whether something accepts a connection on the port."""
    try:
        socket.create_connection(("127.0.0.1", port), timeout=1).close()
    except OSError:
        return False
    return True


def sandbox(tmp_path: Path, rule_body: str) -> tuple[Path, dict[str, str]]:
    """A committed repository holding the script, a target, a rule and the stand-ins."""
    repository = tmp_path / "repository"
    (repository / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repository / "scripts" / "mutate.sh")
    harness = repository / "frontend" / "maquette" / "harness"
    harness.mkdir(parents=True)
    (harness / "served_copy.py").write_text("")
    (harness / "server.py").write_text(STAND_IN_HOST)
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
        "TM_HARNESS_PORT": str(free_port()),
    }
    for command in (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        ["git", "commit", "-qm", "sandbox"],
    ):
        subprocess.run(command, cwd=repository, check=True, env=environment)
    return repository, environment


def mutate(repository: Path, environment: dict[str, str], rule: str = "rule.py") -> subprocess.CompletedProcess:
    """Runs the copied script with one mutation of the target against the rule."""
    return subprocess.run(
        [
            "bash",
            "scripts/mutate.sh",
            "target.txt",
            't.replace("before", "after")',
            rule,
        ],
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


def test_a_rule_that_hangs_is_an_instrument_fall_and_not_a_verdict(
    tmp_path: Path,
) -> None:
    """A rule past its bound is TIMED OUT: never « no rule fell », the file restored all the same."""
    repository, environment = sandbox(tmp_path, "import time\ntime.sleep(40)\n")
    environment["TM_RULE_TIMEOUT_SECONDS"] = "2"
    started = time.monotonic()
    result = mutate(repository, environment)
    assert time.monotonic() - started < 30, result.stdout
    assert result.returncode == 3, result.stdout + result.stderr
    assert "TIMED OUT" in result.stdout, result.stdout
    assert "NO RULE FELL" not in result.stdout, result.stdout
    assert (repository / "target.txt").read_text() == "before\n"


def test_a_rule_path_that_does_not_exist_is_refused_before_anything_is_mutated(
    tmp_path: Path,
) -> None:
    """A missing rule is « RULE NOT FOUND », exit 64, the target untouched — never a FELL over nothing.

    A rule named without its directory made `python3` answer « can't open file »
    with exit 2, and the tool printed « FELL » for every one of eight runs.
    """
    repository, environment = sandbox(tmp_path, "raise SystemExit(0)\n")
    result = mutate(repository, environment, rule="missing.py")
    assert result.returncode == 64, result.stdout + result.stderr
    assert "RULE NOT FOUND: missing.py" in result.stdout + result.stderr
    assert "FELL" not in result.stdout, result.stdout
    assert "mutated" not in result.stdout, result.stdout
    assert (repository / "target.txt").read_text() == "before\n"


def test_a_rule_that_crashes_is_an_instrument_fall_and_not_a_verdict(tmp_path: Path) -> None:
    """A traceback with no `FAIL` line is RULE CRASHED whatever the exit — never FELL."""
    repository, environment = sandbox(tmp_path, "raise RuntimeError('connection refused')\n")
    result = mutate(repository, environment)
    assert result.returncode == 3, result.stdout + result.stderr
    assert "RULE CRASHED" in result.stdout, result.stdout
    assert "FELL" not in result.stdout.replace("INSTRUMENT FELL", ""), result.stdout
    assert (repository / "target.txt").read_text() == "before\n"


def test_the_harness_host_is_started_when_absent_and_stopped_after(tmp_path: Path) -> None:
    """With nothing listening the tool starts the host its rules read, and stops what it started.

    A wrapped run stops the host it started, and eight rules then raised
    « connection refused » and were each reported « FELL ».
    """
    rule = (
        "import os, socket\n"
        "socket.create_connection(('127.0.0.1', int(os.environ['TM_HARNESS_PORT'])), timeout=2).close()\n"
    )
    repository, environment = sandbox(tmp_path, rule)
    port = int(environment["TM_HARNESS_PORT"])
    assert not listening(port)
    result = mutate(repository, environment)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "NO RULE FELL" in result.stdout, result.stdout
    for _ in range(20):
        if not listening(port):
            break
        time.sleep(0.1)
    assert not listening(port), "the host the tool started is still listening"

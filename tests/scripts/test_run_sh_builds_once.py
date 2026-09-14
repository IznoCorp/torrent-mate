"""`run.sh` builds the served copy ONCE for the contracts tier, the oracle and the phase's rules.

WHAT IT PAID FOR. A phase gate is the contracts tier and the oracle, and each was
its own invocation of `frontend/maquette/harness/run.sh` — so each rebuilt and
re-copied the prototype, about two minutes spent measuring nothing. The form
`run.sh --contracts --oracle` runs both over one build: the contract rules and
the repository's guards first, the oracle after them, the accessibility audit
never. Rule names after the two flags are the phase's re-aimed rules, replayed
in the same pass; the oracle runs even when a rule falls, and one verdict block
names both halves — a phase holds the mutex once.

HOW IT IS READ. The script is copied into a scratch tree whose every
collaborator is a stub writing one line to a journal — the build (`npm`), the
served copy's helper, each contract rule, each guard, the oracle and the audit.
The journal is the reading: nothing here launches a browser or builds anything.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUN_SCRIPT = ROOT / "frontend" / "maquette" / "harness" / "run.sh"

# A stub collaborator: appends its own name and arguments to the journal, and
# answers `--token` with a constant so the stamp around every rule never moves.
STUB_PYTHON = """import os, sys
with open(os.environ["RUN_JOURNAL"], "a") as journal:
    journal.write(" ".join([os.path.basename(sys.argv[0])] + sys.argv[1:]) + "\\n")
if sys.argv[1:] == ["--token"]:
    print("stamp")
"""


def _array(name: str, text: str) -> list[str]:
    """Read one bash array's entries out of the script's text.

    Args:
        name: The array's name, `CONTRACTS` or `REPOSITORY_GUARDS`.
        text: The whole text of `run.sh`.

    Returns:
        The array's entries, in order.
    """
    match = re.search(rf"^{name}=\((.*?)\)", text, re.MULTILINE | re.DOTALL)
    assert match, f"run.sh declares no {name} array"
    return [quoted or bare for quoted, bare in re.findall(r'"([^"]+)"|(\S+)', match.group(1))]


def _write_executable(path: Path, content: str) -> None:
    """Write a file and mark it executable.

    Args:
        path: Where the file goes.
        content: Its text.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def scratch_tree(tmp_path: Path) -> Path:
    """Lay out a copy of `run.sh` among stubs of everything it calls.

    Args:
        tmp_path: Pytest's per-test directory.

    Returns:
        The scratch repository root.
    """
    text = RUN_SCRIPT.read_text()
    harness = tmp_path / "frontend" / "maquette" / "harness"
    harness.mkdir(parents=True)
    shutil.copy(RUN_SCRIPT, harness / "run.sh")
    (tmp_path / "frontend" / "maquette" / "design").mkdir()
    _write_executable(harness / "served_copy.py", STUB_PYTHON)
    # A rule outside the contracts tier, as a phase names one, and one that falls.
    _write_executable(harness / "settings.py", STUB_PYTHON)
    _write_executable(harness / "fallen.py", STUB_PYTHON + "sys.exit(1)\n")
    _write_executable(harness / "hung.py", STUB_PYTHON + "import time\ntime.sleep(40)\n")
    for rule in _array("CONTRACTS", text):
        _write_executable(harness / rule, STUB_PYTHON)
    for guard in _array("REPOSITORY_GUARDS", text):
        _write_executable(tmp_path / guard.split()[0], STUB_PYTHON)
    _write_executable(tmp_path / "frontend" / "maquette" / "oracle.py", STUB_PYTHON)
    _write_executable(tmp_path / "frontend" / "maquette" / "a11y.py", STUB_PYTHON)
    binaries = tmp_path / "bin"
    # `npm` records the build; `lsof` answers « the host is listening » so no
    # server is started.
    _write_executable(binaries / "npm", '#!/bin/sh\necho "npm $*" >> "$RUN_JOURNAL"\n')
    _write_executable(binaries / "lsof", "#!/bin/sh\nexit 0\n")
    return tmp_path


def _run(tree: Path, *flags: str, **environment: str) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the copied script with the given flags and read its journal.

    Args:
        tree: The scratch repository root.
        *flags: The arguments handed to `run.sh`.
        **environment: Variables added to the run's environment.

    Returns:
        The completed process and the journal's lines.
    """
    journal = tree / "journal"
    journal.touch()
    result = subprocess.run(
        ["bash", str(tree / "frontend" / "maquette" / "harness" / "run.sh"), *flags],
        capture_output=True,
        text=True,
        timeout=120,
        env={
            **os.environ,
            "PATH": f"{tree / 'bin'}:{os.environ['PATH']}",
            "RUN_JOURNAL": str(journal),
            "TM_HARNESS_JOBS": "2",
            **environment,
        },
    )
    return result, journal.read_text().splitlines()


def _count(journal: list[str], entry: str) -> int:
    """Count the journal lines naming one collaborator.

    Args:
        journal: The journal's lines.
        entry: The collaborator's journal line, or its first word.

    Returns:
        How many lines start with it.
    """
    return sum(1 for line in journal if line == entry or line.startswith(entry + " "))


def test_the_contracts_tier_and_the_oracle_share_one_build(scratch_tree: Path) -> None:
    """One invocation, one build, every contract rule, every guard, the oracle once."""
    result, journal = _run(scratch_tree, "--contracts", "--oracle")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _count(journal, "npm run build") == 1, journal
    assert _count(journal, "oracle.py --check") == 1, journal
    assert _count(journal, "a11y.py") == 0, journal
    assert _count(journal, "check-bug-register.py") == 1, journal
    assert _count(journal, "audit2.py") == 1, journal


def test_the_contracts_tier_alone_still_runs_no_oracle(scratch_tree: Path) -> None:
    """THE CONTROL: the form CI runs on every pull request is unchanged."""
    result, journal = _run(scratch_tree, "--contracts")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _count(journal, "npm run build") == 1, journal
    assert _count(journal, "audit2.py") == 1, journal
    assert _count(journal, "oracle.py --check") == 0, journal
    assert _count(journal, "a11y.py") == 0, journal


def test_the_oracle_alone_still_runs_no_rule(scratch_tree: Path) -> None:
    """THE CONTROL: the single-purpose oracle tier answers one question."""
    result, journal = _run(scratch_tree, "--oracle")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _count(journal, "oracle.py --check") == 1, journal
    assert _count(journal, "audit2.py") == 0, journal
    assert _count(journal, "check-bug-register.py") == 0, journal


def test_a_phase_gate_replays_its_named_rules_over_the_same_build(
    scratch_tree: Path,
) -> None:
    """The named rule runs once, beside the contract rules, and one verdict closes the run."""
    result, journal = _run(scratch_tree, "--contracts", "--oracle", "settings.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _count(journal, "npm run build") == 1, journal
    assert _count(journal, "settings.py") == 1, journal
    assert _count(journal, "audit2.py") == 1, journal
    assert _count(journal, "oracle.py --check") == 1, journal
    assert "gate: no violation" in result.stdout, result.stdout


def test_a_fallen_rule_still_leaves_the_oracle_its_reading(scratch_tree: Path) -> None:
    """One invocation answers both questions: the oracle runs, the verdict fails."""
    result, journal = _run(scratch_tree, "--contracts", "--oracle", "fallen.py")

    assert result.returncode == 1, result.stdout + result.stderr
    assert _count(journal, "oracle.py --check") == 1, journal
    assert "1 failed" in result.stdout and "gate: FAILED" in result.stdout, result.stdout


def test_a_rule_name_with_no_file_is_refused_before_the_build(
    scratch_tree: Path,
) -> None:
    """A mistyped rule would otherwise be a gate that silently replayed nothing."""
    result, journal = _run(scratch_tree, "--contracts", "--oracle", "no_such_rule.py")

    assert result.returncode == 2, result.stdout + result.stderr
    assert _count(journal, "npm run build") == 0, journal


def test_a_hung_rule_is_an_instrument_fall_and_the_gate_still_ends(
    scratch_tree: Path,
) -> None:
    """A rule past its bound is TIMED OUT, counted as failed, and the oracle still reads."""
    started = time.monotonic()
    result, journal = _run(scratch_tree, "--contracts", "--oracle", "hung.py", TM_RULE_TIMEOUT_SECONDS="2")

    assert time.monotonic() - started < 30, result.stdout
    assert result.returncode == 1, result.stdout + result.stderr
    assert "TIMED OUT: hung.py" in result.stdout, result.stdout
    assert "(1 timed out)" in result.stdout, result.stdout
    assert _count(journal, "oracle.py --check") == 1, journal


def test_a_rule_name_after_a_single_tier_is_refused_before_the_build(
    scratch_tree: Path,
) -> None:
    """`--contracts selection.py` read no name and still ran: a green over a rule that never ran.

    Rule names are read only after `--contracts --oracle`; anywhere else the name
    was dropped in silence, the log said « 0 named rule(s) » and the tier exited 0.
    """
    result, journal = _run(scratch_tree, "--contracts", "selection.py")

    assert result.returncode == 64, result.stdout + result.stderr
    assert "only read with --contracts --oracle" in result.stderr, result.stderr
    assert _count(journal, "npm run build") == 0, journal


def test_a_bare_rule_name_is_refused_rather_than_run_as_the_full_suite(
    scratch_tree: Path,
) -> None:
    """`run.sh selection.py` fell through to the full suite: the one rule asked for was never singled out."""
    result, journal = _run(scratch_tree, "selection.py")

    assert result.returncode == 64, result.stdout + result.stderr
    assert "only read with --contracts --oracle" in result.stderr, result.stderr
    assert _count(journal, "npm run build") == 0, journal

"""`run.sh` runs the full suite as CI shards: split, CI form, and kept durations.

WHAT IT IS FOR. The full suite left the operator's machine for CI, split into
shards that each runner computes on its own. Three properties carry that move,
and each one fails in silence when it breaks:

  * the shards of one run partition the suite — every rule runs, and exactly
    once — whether the rules are dealt by name or by recorded durations;
  * `--ci` leaves out exactly the rules named in `CI_EXCLUDED`, and the oracle,
    and nothing else — a rule dropped by accident is a rule nobody notices has
    stopped running;
  * a kept run writes every rule's duration, which is what the next split is
    balanced by.

HOW IT IS READ. As in `test_run_sh_builds_once.py`: the script is copied into a
scratch tree whose every collaborator is a stub writing one line to a journal.
Nothing here launches a browser or builds anything.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
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

# Rules of the scratch suite beside the ones `run.sh` itself names: enough that
# four shards each hold several, with names that sort in a different order than
# they were written.
PLAIN_RULES = [f"rule_{letter}.py" for letter in "kbhadjfcgei"]

# Shared plumbing the full suite never runs as a rule.
PLUMBING = ["common.py", "factories.py", "desktop_frame_page.py"]


def _array(name: str, text: str) -> list[str]:
    """Read one bash array's entries out of the script's text.

    Args:
        name: The array's name.
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


def _excluded() -> list[str]:
    """The rules `run.sh` names as out of reach of a CI runner.

    Returns:
        The `CI_EXCLUDED` entries.
    """
    return _array("CI_EXCLUDED", RUN_SCRIPT.read_text())


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
    for rule in PLAIN_RULES + _excluded() + PLUMBING:
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


def _suite(tree: Path) -> list[str]:
    """Every rule the full suite of the scratch tree holds.

    Args:
        tree: The scratch repository root.

    Returns:
        The rule file names, plumbing left out, sorted.
    """
    harness = tree / "frontend" / "maquette" / "harness"
    return sorted(path.name for path in harness.glob("*.py") if path.name not in PLUMBING)


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
    journal.write_text("")
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


def _rules_run(journal: list[str], suite: list[str]) -> list[str]:
    """The rules a run executed, read from its journal.

    A rule runs with no argument, so its journal line is its bare name; the
    served copy's helper also writes lines under its name, always WITH one.

    Args:
        journal: The journal's lines.
        suite: The rule names to look for.

    Returns:
        Each executed rule, once per execution, sorted.
    """
    return sorted(line for line in journal if line in suite)


def _count(journal: list[str], entry: str) -> int:
    """Count the journal lines naming one collaborator.

    Args:
        journal: The journal's lines.
        entry: The collaborator's journal line, or its first word.

    Returns:
        How many lines start with it.
    """
    return sum(1 for line in journal if line == entry or line.startswith(entry + " "))


def _durations_file(tree: Path, suite: list[str]) -> Path:
    """Write a durations file where one rule outweighs all the others together.

    Args:
        tree: The scratch repository root.
        suite: The rule names.

    Returns:
        The file's path.
    """
    path = tree / "recorded-durations.tsv"
    heavy = suite[0]
    lines = [f"{rule}\t{1000 if rule == heavy else 3}\tok" for rule in suite[1:]]
    # A rule the file does not know is weighed, never dropped: leave one out.
    path.write_text(f"{heavy}\t1000\tok\n" + "\n".join(lines[1:]) + "\n")
    return path


@pytest.mark.parametrize("balanced", [False, True], ids=["by-name", "by-durations"])
@pytest.mark.parametrize("count", [1, 2, 3, 4])
def test_the_shards_run_every_rule_exactly_once(scratch_tree: Path, count: int, balanced: bool) -> None:
    """The union of the shards is the suite, each rule once, and only shard 1 runs the guards.

    Args:
        scratch_tree: The scratch repository root.
        count: How many shards the suite is split into.
        balanced: Whether a durations file deals the rules.
    """
    suite = _suite(scratch_tree)
    environment = {"TM_HARNESS_DURATIONS": str(_durations_file(scratch_tree, suite))} if balanced else {}
    executed: list[str] = []
    for index in range(1, count + 1):
        result, journal = _run(scratch_tree, "--shard", f"{index}/{count}", **environment)
        assert result.returncode == 0, result.stdout + result.stderr
        assert _count(journal, "npm run build") == 1, journal
        shard_rules = _rules_run(journal, suite)
        assert shard_rules, f"shard {index}/{count} ran no rule"
        executed += shard_rules
        # The suite-wide checks run once per suite: on the first shard alone.
        assert _count(journal, "check-bug-register.py") == (1 if index == 1 else 0), journal
        assert _count(journal, "a11y.py") == (1 if index == 1 else 0), journal
    assert sorted(executed) == suite


def test_the_durations_deal_the_heaviest_rule_a_shard_of_its_own(scratch_tree: Path) -> None:
    """With durations, the rule outweighing all others shares its shard with nothing."""
    suite = _suite(scratch_tree)
    durations = _durations_file(scratch_tree, suite)
    result, journal = _run(scratch_tree, "--shard", "1/2", TM_HARNESS_DURATIONS=str(durations))

    assert result.returncode == 0, result.stdout + result.stderr
    assert _rules_run(journal, suite) == [suite[0]], journal
    assert f"dealt by the durations in {durations}" in result.stdout, result.stdout


def test_without_durations_the_rules_are_dealt_by_name(scratch_tree: Path) -> None:
    """THE CONTROL: no durations file, a round robin over the sorted names."""
    suite = _suite(scratch_tree)
    result, journal = _run(scratch_tree, "--shard", "2/3")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _rules_run(journal, suite) == suite[1::3], journal
    assert "dealt by name" in result.stdout, result.stdout


def test_ci_leaves_out_exactly_the_named_rules_and_the_oracle(scratch_tree: Path) -> None:
    """`--ci` runs the suite minus `CI_EXCLUDED`, and the oracle not at all."""
    suite = _suite(scratch_tree)
    excluded = _excluded()
    result, journal = _run(scratch_tree, "--ci")

    assert result.returncode == 0, result.stdout + result.stderr
    assert sorted(excluded) == sorted(set(excluded)), "CI_EXCLUDED names a rule twice"
    assert _rules_run(journal, suite) == sorted(set(suite) - set(excluded)), journal
    assert _count(journal, "oracle.py --check") == 0, journal
    assert _count(journal, "a11y.py --check") == 1, journal
    # SAID, never silent: the run names what it left out.
    for rule in excluded:
        assert rule in result.stdout, result.stdout


def test_without_ci_the_named_rules_and_the_oracle_run(scratch_tree: Path) -> None:
    """THE CONTROL: the full suite on the operator's machine is unchanged."""
    suite = _suite(scratch_tree)
    result, journal = _run(scratch_tree)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _rules_run(journal, suite) == suite, journal
    assert _count(journal, "oracle.py --check") == 1, journal


def test_ci_and_shard_compose(scratch_tree: Path) -> None:
    """The four CI shards together run the CI form of the suite, each rule once."""
    suite = _suite(scratch_tree)
    executed: list[str] = []
    for index in range(1, 5):
        result, journal = _run(scratch_tree, "--ci", "--shard", f"{index}/4")
        assert result.returncode == 0, result.stdout + result.stderr
        assert _count(journal, "oracle.py --check") == 0, journal
        executed += _rules_run(journal, suite)
    assert sorted(executed) == sorted(set(suite) - set(_excluded()))


def test_a_kept_run_writes_every_rule_duration(scratch_tree: Path) -> None:
    """`TM_HARNESS_LOG_DIR` keeps each rule's log and a `durations.tsv` of every rule."""
    harness = scratch_tree / "frontend" / "maquette" / "harness"
    _write_executable(harness / "rule_slow.py", STUB_PYTHON + "import time\ntime.sleep(1.2)\n")
    suite = _suite(scratch_tree)
    logs = scratch_tree / "kept-logs"
    result, _ = _run(scratch_tree, TM_HARNESS_LOG_DIR=str(logs))

    assert result.returncode == 0, result.stdout + result.stderr
    rows = [line.split("\t") for line in (logs / "durations.tsv").read_text().splitlines()]
    assert sorted(row[0] for row in rows) == suite
    assert all(row[1].isdigit() and row[2] == "ok" for row in rows), rows
    assert int(dict((row[0], row[1]) for row in rows)["rule_slow.py"]) >= 1, rows
    for rule in suite:
        assert (logs / f"{rule}.out").is_file(), rule


def test_a_kept_run_feeds_the_next_split(scratch_tree: Path) -> None:
    """The file a kept run writes is the file `--shard` balances by."""
    logs = scratch_tree / "kept-logs"
    result, _ = _run(scratch_tree, TM_HARNESS_LOG_DIR=str(logs))
    assert result.returncode == 0, result.stdout + result.stderr

    result, _ = _run(scratch_tree, "--shard", "1/2", TM_HARNESS_DURATIONS=str(logs / "durations.tsv"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "dealt by the durations" in result.stdout, result.stdout


def test_a_log_directory_already_holding_files_is_refused(scratch_tree: Path) -> None:
    """An earlier run's `.ok` marker would read as this run's pass."""
    logs = scratch_tree / "kept-logs"
    logs.mkdir()
    (logs / "rule_a.py.ok").touch()
    result, journal = _run(scratch_tree, TM_HARNESS_LOG_DIR=str(logs))

    assert result.returncode == 64, result.stdout + result.stderr
    assert _count(journal, "npm run build") == 0, journal


def test_the_temporary_logs_are_still_removed(scratch_tree: Path) -> None:
    """THE CONTROL: with no directory named, the exit leaves nothing behind."""
    temporary = scratch_tree / "temporary"
    temporary.mkdir()
    result, _ = _run(scratch_tree, TMPDIR=str(temporary))

    assert result.returncode == 0, result.stdout + result.stderr
    assert "kept in" not in result.stdout, result.stdout
    assert list(temporary.iterdir()) == []


@pytest.mark.parametrize(
    "flags",
    [
        ("--shard", "5/4"),
        ("--shard", "0/4"),
        ("--shard", "two"),
        ("--shard",),
        ("--contracts", "--shard", "1/2"),
        ("--ci", "--contracts"),
        ("--ci", "--rules", "rule_a.py"),
    ],
    ids=[
        "index-past-count",
        "index-zero",
        "not-a-fraction",
        "no-value",
        "beside-contracts",
        "ci-beside-contracts",
        "ci-beside-rules",
    ],
)
def test_a_shard_or_ci_the_script_cannot_honour_is_refused(scratch_tree: Path, flags: tuple[str, ...]) -> None:
    """A flag the script cannot honour is refused before anything is built.

    Args:
        scratch_tree: The scratch repository root.
        flags: The arguments handed to `run.sh`.
    """
    result, journal = _run(scratch_tree, *flags)

    assert result.returncode == 64, result.stdout + result.stderr
    assert _count(journal, "npm run build") == 0, journal


def test_an_empty_shard_is_refused(scratch_tree: Path) -> None:
    """More shards than rules leaves one empty, and a run of nothing reads green."""
    count = len(_suite(scratch_tree)) + 1
    result, journal = _run(scratch_tree, "--shard", f"{count}/{count}")

    assert result.returncode == 64, result.stdout + result.stderr
    assert _count(journal, "npm run build") == 0, journal

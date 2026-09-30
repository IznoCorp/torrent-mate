"""The full suite's own workflow runs every shard, on demand, and never on a draft.

`.github/workflows/harness-full.yml` is a separate workflow because its
triggers carry no pull request, and `ci.yml`'s draft gate reads one. So it
holds its own copy of that gate, guarded by the event's name — and a copy is
exactly what drifts: a job whose condition loses the draft clause runs the four
browser shards on every draft carrying the label, and one whose condition loses
the event guard stands down on every nightly, green and silent.

The other holds keep the matrix and the command in step: four shards declared
and a command splitting into three runs a quarter of the suite nowhere.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "harness-full.yml"

# The same shape `test_ci_skips_draft_pull_requests.py` reads in `ci.yml`, the
# label captured so a wrong spelling is named rather than shared.
DRAFT_CLAUSE = re.compile(
    r"github\.event\.pull_request\.draft\s*==\s*false\s*\|\|\s*"
    r"contains\(\s*github\.event\.pull_request\.labels\.\*\.name\s*,\s*'([^']+)'\s*\)"
)
EVENT_GUARD = re.compile(r"github\.event_name\s*!=\s*'pull_request'\s*\|\|")
ON_DEMAND_LABEL = re.compile(r"contains\(\s*github\.event\.pull_request\.labels\.\*\.name\s*,\s*'full-suite'\s*\)")


def workflow() -> dict:
    """The parsed workflow.

    Returns:
        The whole mapping, keys as YAML reads them.
    """
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def trigger() -> dict:
    """The `on:` mapping, which YAML 1.1 may file under `True`.

    Returns:
        The trigger mapping.
    """
    parsed = workflow()
    for key in ("on", True):
        if key in parsed:
            return parsed[key]
    raise AssertionError("the workflow declares no trigger at all")


def job() -> dict:
    """The one job of the workflow.

    Returns:
        The `harness-full` job's mapping.
    """
    return workflow()["jobs"]["harness-full"]


def condition() -> str:
    """The job's `if`, its folded line breaks collapsed.

    Returns:
        The condition as one line.
    """
    return " ".join(str(job().get("if", "")).split())


def run_steps() -> list[dict]:
    """The job's steps that run a command.

    Returns:
        Each step carrying a `run`.
    """
    return [step for step in job()["steps"] if "run" in step]


def test_the_job_stands_down_on_a_draft() -> None:
    """The draft clause is there, with the escape hatch `ci.yml` spells."""
    found = DRAFT_CLAUSE.search(condition())
    assert found, f"the job carries no draft clause; its `if` reads: {condition()!r}"
    assert found.group(1) == "run-ci-on-draft", found.group(1)


def test_the_draft_clause_is_guarded_by_the_event_name() -> None:
    """Outside a pull request the clause reads a null, so it must not be reached."""
    assert EVENT_GUARD.match(condition()), (
        "the condition does not open on `github.event_name != 'pull_request' ||`: "
        "under `schedule` and `workflow_dispatch` the draft clause reads a null "
        f"pull request and stands the job down. Its `if` reads: {condition()!r}"
    )


def test_a_pull_request_runs_it_only_with_the_label() -> None:
    """On a pull request the suite is asked for by `full-suite`, never implied."""
    assert ON_DEMAND_LABEL.search(condition()), condition()


def test_it_is_triggered_by_hand_nightly_and_by_the_label() -> None:
    """The three ways in, and the label's event among the pull request's types."""
    declared = trigger()
    assert "workflow_dispatch" in declared, declared
    assert declared.get("schedule"), declared
    types = declared["pull_request"]["types"]
    assert "labeled" in types and "ready_for_review" in types, types


def test_the_matrix_and_the_command_split_the_suite_the_same_way() -> None:
    """Every shard the matrix declares is one the command asks for, out of as many."""
    shards = job()["strategy"]["matrix"]["shard"]
    commands = [step["run"] for step in run_steps() if "harness/run.sh" in step["run"]]
    assert len(commands) == 1, commands
    match = re.search(r"--shard \$\{\{ matrix\.shard \}\}/(\d+)", commands[0])
    assert match, commands[0]
    assert shards == list(range(1, int(match.group(1)) + 1)), (shards, commands[0])
    assert "--ci" in commands[0].split(), commands[0]
    assert job()["strategy"].get("fail-fast") is False


def test_each_shard_runs_two_rules_at_a_time_and_keeps_its_logs() -> None:
    """The fan-out is named, and the logs the run keeps are the ones uploaded."""
    step = next(step for step in run_steps() if "harness/run.sh" in step["run"])
    environment = step["env"]
    assert environment["TM_HARNESS_JOBS"] == "2", environment
    uploads = [step for step in job()["steps"] if str(step.get("uses", "")).startswith("actions/upload-artifact")]
    assert len(uploads) == 1, uploads
    assert uploads[0]["with"]["path"] == environment["TM_HARNESS_LOG_DIR"], uploads[0]
    assert uploads[0].get("if") == "always()", uploads[0]


def test_both_engines_the_rules_launch_are_installed() -> None:
    """A rule launching WebKit on a runner without it falls for a reason foreign to the change."""
    installs = " ".join(step["run"] for step in run_steps() if "playwright install" in step["run"])
    assert "chromium" in installs.split() and "webkit" in installs.split(), installs

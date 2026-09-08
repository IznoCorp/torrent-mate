"""A draft pull request must cost no runner minute, and leaving draft must dispatch.

The saving is worth exactly what the gate covers. It is written as a job-level
condition repeated on every job — GitHub Actions expands no YAML anchor, so
there is no single place to write it — and a job added later without it runs on
drafts again while the fourteen others stand down. Nothing in a pull request's
own reading shows that: one job running among thirteen skipped ones is not a
shape anyone inspects.

The other half is the trigger. Every job standing down on a draft is only safe
because `ready_for_review` dispatches the run that reads the branch; without
that type the checks would never run at all, which is the dead end the workflow
already records for a trigger `paths-ignore`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# The escape hatch: a branch that needs a green reading before it leaves draft
# adds this label, and `labeled` being among the trigger's types makes the
# addition itself the dispatching event.
ESCAPE_HATCH_LABEL = "run-ci-on-draft"

# The condition's shape, read from a whitespace-normalised `if`. The label is
# captured rather than spelled into the pattern, so a job carrying the right
# shape with the WRONG label is a disagreement this file can name instead of a
# silence it would share.
DRAFT_CLAUSE = re.compile(
    r"github\.event\.pull_request\.draft\s*==\s*false\s*\|\|\s*"
    r"contains\(\s*github\.event\.pull_request\.labels\.\*\.name\s*,\s*'([^']+)'\s*\)"
)


def workflow() -> dict:
    """The parsed workflow.

    Returns:
        The whole mapping, keys as YAML reads them.
    """
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def trigger() -> dict:
    """The `on:` mapping, whichever key YAML gave it.

    YAML 1.1 reads the bare word `on` as the boolean true, so a workflow parsed
    with `yaml.safe_load` carries its trigger under `True` and not under `"on"`
    — a lookup by the string alone finds nothing and a hold built on it would
    pass over an empty answer.

    Returns:
        The trigger mapping.
    """
    parsed = workflow()
    for key in ("on", True):
        if key in parsed:
            return parsed[key]
    raise AssertionError("the workflow declares no trigger at all")


def job_names() -> list[str]:
    """Every job key in the workflow, in file order."""
    return list(workflow()["jobs"])


def condition(job: str) -> str:
    """One job's `if`, with its folded line breaks collapsed.

    Args:
        job: The job's key in the workflow.

    Returns:
        The condition as one line, or the empty string when the job has none.
    """
    return " ".join(str(workflow()["jobs"][job].get("if", "")).split())


@pytest.mark.parametrize("job", job_names())
def test_every_job_stands_down_on_a_draft(job: str) -> None:
    """A job without the condition runs on drafts while every other one skips.

    Args:
        job: The job's key in the workflow.
    """
    assert DRAFT_CLAUSE.search(condition(job)), (
        f"the `{job}` job carries no draft condition, so it runs on every draft "
        "pull request while the others stand down — the saving is worth exactly "
        "what this condition covers. Add `github.event.pull_request.draft == "
        f"false || contains(github.event.pull_request.labels.*.name, "
        f"'{ESCAPE_HATCH_LABEL}')`, composed with `&&` when the job already has "
        f"a condition of its own. Its `if` reads: {condition(job)!r}"
    )


def test_leaving_draft_dispatches_the_run() -> None:
    """Without `ready_for_review` the gate above becomes a permanent silence.

    Every job stands down on a draft, so the event taking the pull request out
    of draft is the only one left that can read the branch. The trigger's other
    types fire on a push or a label, and neither of those is what happens when
    someone clicks « Ready for review ».
    """
    types = trigger()["pull_request"]["types"]
    assert "ready_for_review" in types, (
        "`ready_for_review` is not among the trigger's types "
        f"({types}), and every job now stands down on a draft: taking a pull "
        "request out of draft would dispatch nothing and its checks would never "
        "run at all. This type is half of the draft gate, not an option."
    )


def test_the_escape_hatch_is_spelled_one_way() -> None:
    """Fourteen copies of a condition are fourteen chances to spell it differently.

    A label that disagrees by one character is a job that keeps skipping while
    the others run — green, silent, and indistinguishable from a job that was
    meant to skip.
    """
    spellings: dict[str, list[str]] = {}
    for job in job_names():
        found = DRAFT_CLAUSE.search(condition(job))
        if found:
            spellings.setdefault(found.group(1), []).append(job)
    assert len(spellings) == 1, (
        "the draft condition names more than one label across the jobs: "
        f"{spellings}. Adding one of "
        "them to a pull request would dispatch some jobs and not others."
    )
    assert ESCAPE_HATCH_LABEL in spellings, (
        f"the escape hatch is spelled {list(spellings)} in the workflow and "
        f"`{ESCAPE_HATCH_LABEL}` in this hold and in the directives that tell an "
        "author which label to add — a label nobody spells the same way twice is "
        "a hatch that opens for nobody."
    )


# The events whose payload carries a `pull_request` object. On any other event
# `github.event.pull_request` is null, `null.draft == false` evaluates false,
# and the escape hatch's `contains(…labels.*.name, …)` finds nothing either — so
# EVERY job stands down and the run reports `skipped`, which reads exactly like
# the draft case this file exists to protect.
EVENTS_CARRYING_A_PULL_REQUEST = {"pull_request", "pull_request_target"}


def test_no_trigger_reaches_the_condition_without_a_pull_request() -> None:
    """A trigger with no pull request in its payload would stand every job down.

    THE QUESTION THIS FILE DID NOT ASK. The holds above check the condition and
    the trigger's types, and both are about the pull request that IS there. The
    condition is an expression, though, and an expression is evaluated for every
    event that reaches it: add a `push` trigger and `github.event.pull_request`
    is null on it, so the whole disjunction is false and the pipeline stands down
    on every push — reporting `skipped`, which is a legitimate conclusion, under
    a green checks tab.

    **If you are here because this hold refuses a trigger you added**, it is not
    asking you to remove it: it is saying the draft condition on every job has no
    meaning under that event and would disable the pipeline there. Give those
    jobs a condition that answers your event, or guard the draft clause with the
    event name, and this hold's list is where the decision is recorded.
    """
    declared = set(trigger())
    foreign = declared - EVENTS_CARRYING_A_PULL_REQUEST
    assert not foreign, (
        f"the workflow declares the trigger(s) {sorted(foreign)}, whose payload "
        "carries no `pull_request`. The draft condition on every job reads "
        "`github.event.pull_request.draft`, which is null there, so the whole "
        "disjunction is false and EVERY job stands down — a pipeline disabled "
        f"under a green `skipped`. Declared: {sorted(declared)}."
    )
    assert "pull_request" in declared, (
        f"the workflow declares {sorted(declared)} and not `pull_request`, and "
        "every hold in this file is about a pull request's draft state"
    )

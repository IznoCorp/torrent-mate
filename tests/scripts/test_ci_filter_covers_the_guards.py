"""A guard whose subject no CI filter names runs in no job at all.

This is not hypothetical twice over. `check-mock-seeds.py` and
`extract-maquette-fixtures.mjs` both live under `scripts/` and are read by the
`harness-contracts` job alone; a pull request touching only one of them ran the
guard NOWHERE until 2026-08-26. Then `check-bug-register.py` shipped reading
`BUGS.md`, which no filter named either — so a register-only pull request, the
exact shape the `no-version-bump` label exists for, ran the register's own
guard in no job.

Both were found by a person reading the workflow. This hold reads it instead:
for every guard the contracts tier invokes, every repository path that guard
declares must be matched by at least one filter pattern.
"""

from __future__ import annotations

import re
from fnmatch import fnmatch
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RUN_SCRIPT = ROOT / "frontend" / "maquette" / "harness" / "run.sh"

# `NAME = ROOT / "a" / "b"` — the shape every guard in `scripts/` declares its
# subject with. The parts are joined back into a repository-relative path.
DECLARED_PATH = re.compile(r"=\s*ROOT\s*/\s*(\"[^\"]+\"(?:\s*/\s*\"[^\"]+\")*)")
QUOTED = re.compile(r"\"([^\"]+)\"")


def contract_guards() -> list[str]:
    """Reads the guards the contracts tier runs, from the script that runs them.

    Returns:
        The `scripts/…py` names, without their arguments.
    """
    body = RUN_SCRIPT.read_text(encoding="utf-8")
    return sorted({match.split()[0] for match in re.findall(r'"(scripts/[\w.-]+\.py[^"]*)"', body)})


def filters() -> dict[str, list[str]]:
    """Reads the workflow's filters, by name.

    Returns:
        `{filter name: globs}`.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if "paths-filter" not in str(step.get("uses", "")):
                continue
            return yaml.safe_load(step["with"]["filters"])
    raise AssertionError("no paths-filter step found in the workflow")


def filter_patterns() -> list[str]:
    """Every glob any filter declares, flattened."""
    return [pattern for group in filters().values() for pattern in group]


def gating_filter(job: str) -> str:
    """The filter output every step of a job is gated on.

    THE QUESTION THIS FUNCTION EXISTS TO MAKE ASKABLE. « Is this path named by
    ANY filter? » is not the question — B-244: `check-implementation-state.py`
    reads `IMPLEMENTATION.md`, which the `docs` filter names, while the job
    that runs it gates every step on `maquette`. A pull request touching that
    file alone — which is what a post-merge gesture IS — ran the guard in no
    job at all, and this hold passed over it, because its two earlier cases
    were both fixed by adding the path to `maquette` and the two questions
    happened to have one answer.

    Args:
        job: The job's key in the workflow.

    Returns:
        The filter output name, e.g. `maquette`.

    Raises:
        AssertionError: When the job's steps are gated on several filters or on
            none — either way the answer this hold needs does not exist, and
            guessing one is worse than saying so.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    gates = set()
    for step in workflow["jobs"][job].get("steps", []):
        for output in re.findall(r"needs\.changes\.outputs\.(\w+)", str(step.get("if", ""))):
            gates.add(output)
    assert len(gates) == 1, (
        f"the {job} job's steps are gated on {sorted(gates)}; this hold needs "
        "exactly one filter to compare a guard's subject against"
    )
    return gates.pop()


def covered(path: str, patterns: list[str]) -> bool:
    """Says whether any filter pattern selects a repository path.

    Args:
        path: A repository-relative path, or the directory a guard reads.
        patterns: Every declared glob.

    Returns:
        True when at least one pattern matches the path or an ancestor of it.
    """
    candidates = [path] + [f"{path}/x" for _ in (0,)]
    for pattern in patterns:
        for candidate in candidates:
            if fnmatch(candidate, pattern) or fnmatch(candidate, pattern.replace("**", "*")):
                return True
        # `a/**` selects everything under `a`, including `a` itself as a subject.
        if pattern.endswith("/**") and (path + "/").startswith(pattern[:-2]):
            return True
    return False


def declared_subjects(guard: str) -> list[str]:
    """The repository paths a guard declares and that exist.

    Args:
        guard: One `scripts/…py`.

    Returns:
        The repository-relative paths.
    """
    source = (ROOT / guard).read_text(encoding="utf-8")
    found = []
    for declaration in DECLARED_PATH.findall(source):
        path = "/".join(QUOTED.findall(declaration))
        if (ROOT / path).exists():
            found.append(path)
    return found


@pytest.mark.parametrize("guard", contract_guards())
def test_every_path_a_contract_guard_reads_is_named_by_a_filter(guard):
    """A guard reading a file no filter names runs in no job.

    Args:
        guard: One `scripts/…py` from the contracts tier.
    """
    patterns = filter_patterns()
    unnamed = [path for path in declared_subjects(guard) if not covered(path, patterns)]
    assert not unnamed, (
        f"{guard} reads {unnamed}, which no filter in ci.yml names. On a pull "
        "request touching only that, this guard runs in no job — the shape "
        "check-mock-seeds and check-bug-register both shipped in."
    )


@pytest.mark.parametrize("guard", contract_guards())
def test_every_path_is_named_by_the_filter_that_gates_the_job(guard):
    """And named by the RIGHT filter — the one gating the job that runs it.

    B-244. The hold above asks « is this path named by ANY filter? », and its
    two earlier cases were both fixed by adding the path to `maquette`, so the
    two questions have never yet had different answers. They did:
    `check-implementation-state.py` reads `IMPLEMENTATION.md`, named by `docs`
    alone, while `harness-contracts` gates every step on `maquette`. A pull
    request touching that file — a post-merge gesture — ran the guard nowhere,
    under a green hold.

    Args:
        guard: One `scripts/…py` from the contracts tier.
    """
    gating = gating_filter("harness-contracts")
    patterns = filters()[gating]
    unnamed = [path for path in declared_subjects(guard) if not covered(path, patterns)]
    assert not unnamed, (
        f"{guard} runs in the `harness-contracts` job, which gates every step "
        f"on the `{gating}` filter — and that filter names none of {unnamed}. "
        "A pull request touching only those runs this guard in NO job, however "
        "many other filters name them (B-244)."
    )

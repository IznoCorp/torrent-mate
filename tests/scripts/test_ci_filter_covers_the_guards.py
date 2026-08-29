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


def filter_patterns() -> list[str]:
    """Reads every glob any filter in the workflow declares.

    Returns:
        The patterns, flattened across all filters.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if "paths-filter" not in str(step.get("uses", "")):
                continue
            declared = yaml.safe_load(step["with"]["filters"])
            return [pattern for group in declared.values() for pattern in group]
    raise AssertionError("no paths-filter step found in the workflow")


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


@pytest.mark.parametrize("guard", contract_guards())
def test_every_path_a_contract_guard_reads_is_named_by_a_filter(guard):
    """A guard reading a file no filter names runs in no job.

    Args:
        guard: One `scripts/…py` from the contracts tier.
    """
    source = (ROOT / guard).read_text(encoding="utf-8")
    patterns = filter_patterns()
    unnamed = []
    for declaration in DECLARED_PATH.findall(source):
        path = "/".join(QUOTED.findall(declaration))
        if not (ROOT / path).exists():
            continue
        if not covered(path, patterns):
            unnamed.append(path)
    assert not unnamed, (
        f"{guard} reads {unnamed}, which no filter in ci.yml names. On a pull "
        "request touching only that, this guard runs in no job — the shape "
        "check-mock-seeds and check-bug-register both shipped in."
    )

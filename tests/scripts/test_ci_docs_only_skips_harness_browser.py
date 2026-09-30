"""A docs-only pull request pays no Playwright minute in `harness-contracts` (order 95).

THE DEFECT THIS CLOSES. `BUGS.md` and `IMPLEMENTATION.md` are named under the
`maquette` filter so their own guards (`check-bug-register.py`,
`check-implementation-state.py`) run somewhere — `harness-contracts` is their
only home. That filter says nothing about the 11-rule browser subset the same
job also pays for, so a pull request touching `BUGS.md` alone ran Chromium and
the browser rules too — B-574's chronic red, on heads that cannot touch the
maquette at all. Those same guards already ran LOCALLY, by name, in the
pre-push hook's own docs-only path before the push ever reached CI, so
skipping the redundant browser half costs nothing this repository does not
already have.

HOW IT IS READ. The workflow's `docs_only` computation is one `jq` filter
string, extracted from the `raffine` step's script and run for real against
sample file lists — not re-derived here, so this hold cannot drift from what
CI actually executes. Every step of `harness-contracts` that reads `maquette`
must also read `docs_only == 'false'`, checked by parsing the workflow itself.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

DOCS_ONLY_FILTER = re.compile(r"docs_only=\$\(jq -r '(.*?)' <<< \"\$\{ALL_FILES\}\"\)")


def _refine_step_script() -> str:
    """The `changes` job's `raffine` step, as one shell script.

    Returns:
        The step's `run:` text.
    """
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["changes"]["steps"]:
        if step.get("id") == "raffine":
            return str(step["run"])
    raise AssertionError("the `changes` job declares no `raffine` step")


def _jq_filter() -> str:
    """The exact `jq` expression CI runs to decide `docs_only`.

    Returns:
        The filter string, unmodified from the workflow.
    """
    match = DOCS_ONLY_FILTER.search(_refine_step_script())
    assert match, (
        "the `raffine` step no longer computes `docs_only` the way this hold expects — "
        f"its script reads:\n{_refine_step_script()}"
    )
    return match.group(1)


def _docs_only(files: list[str]) -> bool:
    """Runs the REAL `jq` filter CI uses, over a sample file list.

    Args:
        files: The pull request's changed paths, as `dorny/paths-filter` would list them.

    Returns:
        Whether CI would treat this file list as docs-only.
    """
    import json

    result = subprocess.run(
        ["jq", "-r", _jq_filter()],
        input=json.dumps(files),
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return result.stdout.strip() == "true"


@pytest.mark.parametrize(
    "files",
    [
        ["BUGS.md"],
        ["docs/reference/frontend-steward.md"],
        ["docs/features/l99/DESIGN.md", "BUGS.md", "IMPLEMENTATION.md"],
        ["README.md"],
    ],
)
def test_a_docs_or_markdown_only_change_reads_docs_only(files: list[str]) -> None:
    """`docs/**`, `BUGS.md` and every root `*.md` are exactly the pre-push hook's own definition."""
    assert _docs_only(files), f"{files} should read docs_only=true"


@pytest.mark.parametrize(
    "files",
    [
        ["BUGS.md", "personalscraper/cli.py"],
        ["frontend/maquette/design/src/app/arrival.ts"],
        ["scripts/check-bug-register.py"],
        ["docs/reference/frontend-steward.md", "frontend/maquette/harness/run.sh"],
    ],
)
def test_a_change_outside_docs_and_markdown_is_not_docs_only(files: list[str]) -> None:
    """One file the pre-push hook would not call docs-only is enough to keep the browser tier."""
    assert not _docs_only(files), f"{files} should read docs_only=false"


def test_every_maquette_gated_step_of_harness_contracts_also_reads_docs_only() -> None:
    """A step reading `maquette` alone would still pay Playwright on a docs-only pull request."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["harness-contracts"]["steps"]
    maquette_gated = [s for s in steps if "needs.changes.outputs.maquette" in str(s.get("if", ""))]
    assert maquette_gated, "harness-contracts carries no maquette-gated step any more — read by hand"
    missing = [s.get("run", s.get("uses", "?")) for s in maquette_gated if "docs_only" not in str(s["if"])]
    assert not missing, (
        "these harness-contracts steps read `maquette` without also reading "
        f"`docs_only == 'false'`, so they still run on a docs-only pull request: {missing}"
    )

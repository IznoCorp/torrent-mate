#!/usr/bin/env python3
"""Generates the lots progress the design host's `/dev/lots` page draws.

WHAT IT READS, AND WHERE FROM. A lots definition (JSON) names each lot, its
plan, its phases with their codename and their dispatch rows, and the dispatch
record (JSON lines) beside it. The repository's pull requests come from one
read-only `gh pr list`. Every input path comes from the ENVIRONMENT, never from
this file: the definition, the plans and the record are the work's own
artifacts and live outside the repository.

    TM_DEV_LOTS_DEFINITION  the lots definition; its relative paths resolve
                            against its own directory
    TM_DEV_LOTS_OUT         where the generated JSON is written

WHAT IT WRITES. `{"available": true, "generatedAt", "lots": [...]}`, each
phase with its title (the plan's heading), its state, its pull requests and
what blocks it. No dispatch label and no input path is copied out: the page
shows states, titles and links, nothing of the orchestration's prose.

WHEN AN INPUT IS ABSENT the output is `{"available": false}` and the page says
there is nothing to show — never half a picture. When `gh` fails, the run
exits 1 and the previous output stays in place, its `generatedAt` saying how
old it is.

Run by the design host's schedule and after each of its redeploys; it is
inert anywhere those two do not call it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from pathlib import Path

DEFINITION_ENV = "TM_DEV_LOTS_DEFINITION"
OUT_ENV = "TM_DEV_LOTS_OUT"

# The one listing asked of GitHub: every state, only the fields the page needs.
GH_COMMAND = [
    "gh",
    "pr",
    "list",
    "--state",
    "all",
    "--limit",
    "1000",
    "--json",
    "number,title,state,headRefName,url",
]
GH_TIMEOUT_SECONDS = 60

# The dispatch states that mean someone is working on the phase right now.
ACTIVE_DISPATCH = ("in-flight", "in-review", "ready-unarmed", "armed")

# A phase heading: `## <id>` then the title after a separator, decorations aside.
HEADING = re.compile(r"^## (?P<id>[A-Za-z0-9][A-Za-z0-9.-]*):?\s+(?P<rest>.+)$")
# What may stand between a heading's id and its title: emoji marks and a separator.
TITLE_LEAD = re.compile(r"^[^\w(]*?(?:—|–|:|-)\s*")
# A conventional commit title's scope: `type(scope): …`.
TITLE_SCOPE = re.compile(r"^\w+\((?P<scope>[^)]+)\):")

GhRunner = Callable[[list[str]], str]


def plan_titles(plan: str) -> dict[str, str]:
    """Reads the phase titles a plan's level-two headings give.

    Args:
        plan: The plan's markdown.

    Returns:
        Each phase id to its title, the decorations (emoji marks, the separator,
        the ` · branch · tier` tail) removed.
    """
    titles: dict[str, str] = {}
    for line in plan.splitlines():
        match = HEADING.match(line.rstrip())
        if match is None:
            continue
        rest = TITLE_LEAD.sub("", match.group("rest"), count=1)
        titles[match.group("id")] = rest.split(" · ", 1)[0].strip()
    return titles


def read_dispatch(path: Path) -> dict[int, str]:
    """Reads the dispatch record's state per row.

    Args:
        path: The record, one JSON object per line.

    Returns:
        Each row id to its state word; the labels are not kept.
    """
    states: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            states[int(row["id"])] = str(row.get("state", ""))
    return states


def run_gh(arguments: list[str]) -> str:
    """Runs `gh` with the machine's own authentication.

    Args:
        arguments: The command line.

    Returns:
        What `gh` printed.

    Raises:
        subprocess.CalledProcessError: When `gh` fails.
        subprocess.TimeoutExpired: When it does not answer in time.
    """
    return subprocess.run(arguments, capture_output=True, text=True, check=True, timeout=GH_TIMEOUT_SECONDS).stdout


def belongs_to(pull_request: Mapping[str, object], codename: str) -> bool:
    """Whether a pull request is a phase's: its branch or its title scope names the codename.

    Args:
        pull_request: One entry of the listing.
        codename: The phase's codename.

    Returns:
        True when the branch's last segment, or the title's scope, IS the codename.
    """
    branch = str(pull_request.get("headRefName", ""))
    if branch.rsplit("/", 1)[-1] == codename:
        return True
    scope = TITLE_SCOPE.match(str(pull_request.get("title", "")))
    return scope is not None and scope.group("scope") == codename


def phase_entry(
    phase: Mapping[str, object],
    titles: Mapping[str, str],
    dispatch: Mapping[int, str],
    pull_requests: list[Mapping[str, object]],
) -> dict[str, object]:
    """Builds one phase as the page draws it.

    The state is the furthest fact: an open PR, then a merged one, then a
    dispatch row being worked, then planned.

    Args:
        phase: The phase as the definition gives it.
        titles: The plan's titles, by phase id.
        dispatch: The dispatch record's states, by row id.
        pull_requests: The repository's pull requests.

    Returns:
        The phase's entry.
    """
    phase_id = str(phase["id"])
    codename = str(phase["codename"])
    prs = [
        {"number": int(str(pr["number"])), "url": str(pr["url"]), "state": str(pr["state"]).lower()}
        for pr in pull_requests
        if belongs_to(pr, codename) and str(pr.get("state")) in ("OPEN", "MERGED")
    ]
    prs.sort(key=lambda pr: int(str(pr["number"])))
    rows = [dispatch.get(int(str(row)), "") for row in phase.get("dispatch", []) or []]  # type: ignore[union-attr]
    active = next((state for state in rows if state in ACTIVE_DISPATCH), None)
    if any(pr["state"] == "open" for pr in prs):
        state = "pr-open"
    elif any(pr["state"] == "merged" for pr in prs):
        state = "merged"
    elif active is not None:
        state = "in-progress"
    else:
        state = "planned"
    return {
        "id": phase_id,
        "title": titles.get(phase_id) or str(phase.get("title") or phase_id),
        "state": state,
        "dispatch": active,
        "blockedBy": phase.get("blockedBy"),
        "prs": prs,
    }


def build(
    definition: Mapping[str, object],
    base: Path,
    dispatch: Mapping[int, str],
    pull_requests: list[Mapping[str, object]],
    now: int,
) -> dict[str, object]:
    """Builds the whole document from the inputs already read.

    Args:
        definition: The lots definition.
        base: The directory its relative paths resolve against.
        dispatch: The dispatch record's states, by row id.
        pull_requests: The repository's pull requests.
        now: The generation time, epoch seconds.

    Returns:
        The document the page draws.
    """
    lots = []
    for lot in definition.get("lots", []) or []:  # type: ignore[union-attr]
        plan = base / str(lot.get("plan", ""))
        titles = plan_titles(plan.read_text(encoding="utf-8")) if lot.get("plan") and plan.is_file() else {}
        lots.append(
            {
                "id": str(lot["id"]),
                "name": str(lot.get("name") or lot["id"]),
                "blockedBy": lot.get("blockedBy"),
                "phases": [phase_entry(phase, titles, dispatch, pull_requests) for phase in lot.get("phases", [])],
            }
        )
    return {"available": True, "generatedAt": now, "lots": lots}


def write(out: Path, document: Mapping[str, object]) -> None:
    """Writes the document whole or not at all: a reader never sees half a file.

    Args:
        out: The output path.
        document: What to write.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    partial = out.with_name(out.name + ".partial")
    partial.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    partial.replace(out)


def main(environment: Mapping[str, str] | None = None, run_gh: GhRunner = run_gh) -> int:
    """Generates the lots progress once.

    Args:
        environment: Where the paths are read; the process environment by default.
        run_gh: What answers the pull-request listing.

    Returns:
        0 when the output is written (or there is nowhere to write it), 1 when
        `gh` failed and the previous output was kept.
    """
    environment = os.environ if environment is None else environment
    out_value = environment.get(OUT_ENV)
    if not out_value:
        print(f"dev-lots: {OUT_ENV} is not set, nothing written", file=sys.stderr)
        return 0
    out = Path(out_value).expanduser()
    definition_value = environment.get(DEFINITION_ENV)
    definition_path = Path(definition_value).expanduser() if definition_value else None
    if definition_path is None or not definition_path.is_file():
        print("dev-lots: no lots definition, writing an unavailable document", file=sys.stderr)
        write(out, {"available": False})
        return 0
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    base = definition_path.parent
    dispatch_path = base / str(definition.get("dispatch", ""))
    if not definition.get("dispatch") or not dispatch_path.is_file():
        print("dev-lots: no dispatch record, writing an unavailable document", file=sys.stderr)
        write(out, {"available": False})
        return 0
    try:
        pull_requests = json.loads(run_gh(GH_COMMAND))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError, ValueError) as failure:
        print(f"dev-lots: the pull-request listing failed ({type(failure).__name__}), output kept", file=sys.stderr)
        return 1
    write(out, build(definition, base, read_dispatch(dispatch_path), pull_requests, int(time.time())))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Computes what the maquette's interface asks of the backend, and writes it down.

WHY COMPUTED AND NOT WRITTEN. D7 says every divergence between the contract the
interface REQUIRES and the contract the backend HAS is recorded as a demand, and
that the recorded divergences ARE that future specification, delivered as a diff
rather than a blank page. A register written by hand rots the first time
either contract moves, and a specification nobody recalculates is one nobody can
act on. `--check` refuses a committed register that differs from the computed
one, so the two cannot separate.

WHAT IT COMPARES, and what it deliberately does not. Five kinds:

  missing      an operation the interface requires and the backend does not
               have. The whole library read surface is here.
  shape        an operation both declare, whose RESPONSE carries different
               property names. Names, not types: a type comparison across two
               documents written by different hands reports difference for
               every optional field and drowns the real findings.
  spelling     an operation both declare, whose path parameter is spelled
               differently — `{followedId}` against `{followed_id}`. A real
               divergence, and a small one.
  formatted    a field the interface carries PRE-FORMATTED because the fixture
               does (D-L08-5). The demand is supply the underlying fact.
               These are found by their own description marker, which the
               contract writes deliberately.
  unused       an operation the backend has and the interface does not use.
               Recorded because it says what the switchover may retire — never
               as a suggestion to remove anything.

WHAT IT DOES NOT DO: it touches no backend. Nothing under `personalscraper/`
is read or written; this reads two JSON documents and writes one Markdown file.

Usage:
    python3 scripts/compare-contracts.py --write   # (re)compute the register
    python3 scripts/compare-contracts.py --check   # report drift, exit 1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WANTED = ROOT / "frontend" / "maquette" / "contract" / "openapi.json"
HAVE = ROOT / "frontend" / "openapi.json"
REGISTER = ROOT / "docs" / "reference" / "frontend-backend-demands.md"

METHODS = ("get", "post", "put", "patch", "delete")

# The marker the maquette's contract writes on a field it carries pre-formatted.
# It is a phrase the contract itself declares, so this reader and the document
# agree by construction rather than by a convention someone has to remember.
CARRIED = "CARRIED VERBATIM FROM THE FIXTURE"



def shape_of(key: str) -> str:
    """Returns one operation key with its path parameter NAMES blanked.

    THE TWO DOCUMENTS SPELL THEIR PARAMETERS DIFFERENTLY — the interface writes
    `{followedId}`, the backend writes `{followed_id}` — and comparing the
    literal strings reports the backend does not have this operation about
    operations it plainly has. ELEVEN were reported that way, and the count of
    truly missing operations fell from 24 to 13 when it was fixed. The spelling
    IS a divergence and it is recorded as its own kind below; it is not the same
    finding as an operation that does not exist.

    Args:
        key: `METHOD /path/{parameter}`.

    Returns:
        The same key with every `{...}` replaced by `{}`.
    """
    return re.sub(r"\{[^}]*\}", "{}", key)


def operations(document: dict) -> dict:
    """Reads a document's operations, keyed by `METHOD path`."""
    found = {}
    for path, entry in document["paths"].items():
        for method, operation in entry.items():
            if method in METHODS:
                found[f"{method.upper()} {path}"] = operation
    return found


def response_properties(document: dict, operation: dict) -> set:
    """Collects every property name the 200 response can carry.

    `$ref`s are resolved and cycles are guarded, so a self-referential schema
    cannot hang the walk.

    Args:
        document: The whole document, for resolving references.
        operation: One operation.

    Returns:
        Every property name reachable from its 200 response.
    """
    ok = operation.get("responses", {}).get("200", {})
    content = ok.get("content", {}).get("application/json", {})
    names: set = set()
    seen: set = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            reference = node.get("$ref")
            if isinstance(reference, str):
                if reference in seen:
                    return
                seen.add(reference)
                target: object = document
                for part in reference.lstrip("#/").split("/"):
                    if isinstance(target, dict):
                        target = target.get(part, {})
                walk(target)
                return
            for name, schema in (node.get("properties") or {}).items():
                names.add(name)
                walk(schema)
            for key in ("items", "additionalProperties"):
                walk(node.get(key))
            for key in ("oneOf", "anyOf", "allOf"):
                for member in node.get(key) or []:
                    walk(member)
        elif isinstance(node, list):
            for member in node:
                walk(member)

    walk(content.get("schema"))
    return names


def formatted_fields(document: dict) -> list:
    """Finds every field the contract carries pre-formatted, with where it is."""
    found = []

    def walk(node: object, where: str) -> None:
        if isinstance(node, dict):
            for name, schema in (node.get("properties") or {}).items():
                if isinstance(schema, dict) and CARRIED in str(schema.get("description", "")):
                    found.append((where, name))
                walk(schema, f"{where}.{name}" if where else name)
            for key in ("items", "additionalProperties"):
                walk(node.get(key), where)
            # THE COMPOSITION KEYWORDS TOO. The property walk beside this one
            # follows them and this one did not, so a field carried
            # pre-formatted inside a `oneOf` would never reach the register —
            # latent today, and latent is not held.
            for key in ("oneOf", "anyOf", "allOf"):
                for member in node.get(key) or []:
                    walk(member, where)
        elif isinstance(node, list):
            for member in node:
                walk(member, where)

    for name, schema in document["components"]["schemas"].items():
        walk(schema, name)
    for path, entry in document["paths"].items():
        for method, operation in entry.items():
            if method in METHODS:
                walk(operation.get("responses", {}), f"{method.upper()} {path}")
    return sorted(set(found))


def compute() -> str:
    """Builds the register from the two documents."""
    wanted = json.loads(WANTED.read_text(encoding="utf-8"))
    have = json.loads(HAVE.read_text(encoding="utf-8"))
    ours, theirs = operations(wanted), operations(have)

    # Matched on the path with its parameter NAMES blanked, so a `{followedId}`
    # against a `{followed_id}` is not read as a missing operation.
    theirs_by_shape = {shape_of(key): key for key in theirs}
    ours_by_shape = {shape_of(key): key for key in ours}
    missing = sorted(key for key in ours if shape_of(key) not in theirs_by_shape)
    unused = sorted(key for key in theirs if shape_of(key) not in ours_by_shape)
    shared = sorted(key for key in ours if shape_of(key) in theirs_by_shape)

    spelling = sorted(
        (key, theirs_by_shape[shape_of(key)])
        for key in shared
        if key != theirs_by_shape[shape_of(key)]
    )

    shape = []
    for key in shared:
        counterpart = theirs[theirs_by_shape[shape_of(key)]]
        mine = response_properties(wanted, ours[key])
        yours = response_properties(have, counterpart)
        added, dropped = sorted(mine - yours), sorted(yours - mine)
        if added or dropped:
            shape.append((key, ours[key]["operationId"], added, dropped))

    formatted = formatted_fields(wanted)

    lines = [
        "# What the interface asks of the backend",
        "",
        "**COMPUTED, NEVER WRITTEN.** `python3 scripts/compare-contracts.py --write` builds this",
        "file by diffing `frontend/maquette/contract/openapi.json` — the contract the maquette's",
        "interface REQUIRES — against `frontend/openapi.json`, which is generated FROM the running",
        "backend. `--check` refuses a committed register that differs from the computed one, so the",
        "two cannot separate. Edit the contract, not this file.",
        "",
        "**NOBODY IS BUILDING THIS YET, and that is D7.** No backend work happens until the",
        "interface is frozen; starting earlier means rebuilding against a specification that is",
        "still moving. What this file is FOR is that the specification arrives as a diff rather",
        "than a blank page.",
        "",
        "| | |",
        "| --- | ---: |",
        f"| operations the interface requires | {len(ours)} |",
        f"| operations the backend has | {len(theirs)} |",
        f"| required and missing | {len(missing)} |",
        f"| declared by both, different response shape | {len(shape)} |",
        f"| declared by both, path parameter spelled differently | {len(spelling)} |",
        f"| fields carried pre-formatted | {len(formatted)} |",
        f"| the backend has and the interface does not use | {len(unused)} |",
        "",
        "---",
        "",
        "## 1. Operations the interface requires and the backend does not have",
        "",
    ]
    if missing:
        lines += ["| operation | operationId | what it is for |", "| --- | --- | --- |"]
        for key in missing:
            operation = ours[key]
            lines.append(f"| `{key}` | `{operation['operationId']}` | "
                         f"{operation.get('summary', '')} |")
    else:
        lines.append("None.")

    lines += [
        "",
        "## 2. Operations both declare, whose response carries different property names",
        "",
        "Names, never types. A type comparison across two documents written by different hands",
        "reports a difference for every optional field and drowns the real findings.",
        "",
    ]
    if shape:
        lines += ["| operation | the interface adds | the backend has and the interface does not use |",
                  "| --- | --- | --- |"]
        for key, operation_id, added, dropped in shape:
            lines.append(
                f"| `{key}` (`{operation_id}`) | "
                f"{', '.join(f'`{name}`' for name in added) or '—'} | "
                f"{', '.join(f'`{name}`' for name in dropped) or '—'} |")
    else:
        lines.append("None.")

    lines += [
        "",
        "## 2b. Operations both declare, whose path parameter is spelled differently",
        "",
        "The interface writes a parameter in camelCase, the backend in snake_case. It is a real",
        "divergence and a small one — the demand is one spelling, and which one is the",
        "operator's call rather than this file's.",
        "",
    ]
    if spelling:
        lines += ["| the interface requires | the backend has |", "| --- | --- |"]
        for mine, yours in spelling:
            lines.append(f"| `{mine}` | `{yours}` |")
    else:
        lines.append("None.")

    lines += [
        "",
        "## 3. Fields the interface carries pre-formatted",
        "",
        "**The demand is the same for every one of them: supply the underlying fact and let the",
        "interface format it.** They are carried verbatim today because the maquette's fixture",
        "holds them that way, and because a mock returning exactly what the fixture returns is",
        "what makes L09 provable at zero divergence (D-L08-5). Decomposing them in the contract",
        "would be a better contract and would forfeit that proof for something nobody is building",
        "yet.",
        "",
    ]
    if formatted:
        lines += ["| where | field |", "| --- | --- |"]
        for where, name in formatted:
            lines.append(f"| `{where}` | `{name}` |")
    else:
        lines.append("None.")

    lines += [
        "",
        "## 4. Operations the backend has and the interface does not use",
        "",
        "Recorded because it says what the switchover MAY retire. It is not a suggestion to",
        "remove anything: an operation the maquette does not call may still be called by the",
        "production app, by a script, or by the operator.",
        "",
    ]
    if unused:
        for key in unused:
            lines.append(f"- `{key}`")
    else:
        lines.append("None.")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Writes or checks the register."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="(re)compute the register")
    group.add_argument("--check", action="store_true", help="report drift, exit 1")
    arguments = parser.parse_args()

    computed = compute()
    if arguments.write:
        REGISTER.parent.mkdir(parents=True, exist_ok=True)
        REGISTER.write_text(computed, encoding="utf-8")
        print(f"compare-contracts: wrote {REGISTER.relative_to(ROOT)}")
        return 0

    if not REGISTER.is_file():
        print(f"compare-contracts: {REGISTER.relative_to(ROOT)} is missing — the register "
              f"is the deliverable, not a by-product", file=sys.stderr)
        return 1
    if REGISTER.read_text(encoding="utf-8") != computed:
        print(f"compare-contracts: {REGISTER.relative_to(ROOT)} differs from the two "
              f"contracts it is computed from. Rebuild with "
              f"`python3 scripts/compare-contracts.py --write`", file=sys.stderr)
        return 1
    print(f"compare-contracts: {REGISTER.relative_to(ROOT)} matches the computed diff")
    return 0


if __name__ == "__main__":
    sys.exit(main())

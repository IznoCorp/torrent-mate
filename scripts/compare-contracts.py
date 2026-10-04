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

TWO BACKENDS, TWO REGISTERS. `--have v0` (the default) compares the contract
against today's backend (`frontend/openapi.json`) and writes
`frontend-backend-demands.md`; `--have v1` compares it against the v1
application (`frontend/openapi-v1.json`) and writes
`frontend-backend-demands-v1.md`, whose row count is the measure of the
backend's end. Either mode ends on one summary line,
`compare-contracts: <have> missing=<n> shape=<n> spelling=<n> status=<n> unused=<n>`.

Usage:
    python3 scripts/compare-contracts.py --write   # (re)compute the register
    python3 scripts/compare-contracts.py --check   # report drift, exit 1
    python3 scripts/compare-contracts.py --check --have v1   # the same, against v1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from _repo_paths import CONTRACT

ROOT = Path(__file__).resolve().parents[1]
WANTED = CONTRACT
HAVE = ROOT / "frontend" / "openapi.json"
REGISTER = ROOT / "docs" / "reference" / "frontend-backend-demands.md"

METHODS = ("get", "post", "put", "patch", "delete")

# The marker the maquette's contract writes on a field it carries pre-formatted.
# It is a phrase the contract itself declares, so this reader and the document
# agree by construction rather than by a convention someone has to remember.
CARRIED = "CARRIED VERBATIM FROM THE FIXTURE"

# WHERE THE BACKEND THAT EXISTS SERVES ITS OPERATIONS. Its document declares no
# `servers` and writes every path absolute, under this root; the interface's
# contract declares its own root (`/api/v1`) and writes its paths relative to
# it. The two are matched on the path BELOW each root, so the new root is one
# demand said once in the register's head, not every operation reported missing.
V0_ROOT = "/api"

# WHERE v1 IS MOUNTED. Its generated document declares no `servers` and writes
# its paths below the mount, as the contract writes them below its own root.
V1_ROOT = "/api/v1"


@dataclass(frozen=True)
class Backend:
    """One backend the contract is compared against.

    Attributes:
        name: `v0` or `v1`, as `--have` names it.
        document: Its OpenAPI document, generated from it.
        mount: What its document's paths are written below — empty when absolute.
        root: The root its operations are matched below.
        register: The register this comparison writes.
        flag: The `--have` flag a rebuild command names (empty for the default).
    """

    name: str
    document: Path
    mount: str
    root: str
    register: Path
    flag: str


BACKENDS = {
    "v0": Backend("v0", HAVE, "", V0_ROOT, REGISTER, ""),
    "v1": Backend("v1", ROOT / "frontend" / "openapi-v1.json", V1_ROOT, V1_ROOT,
                  ROOT / "docs" / "reference" / "frontend-backend-demands-v1.md", " --have v1"),
}



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


def served_under(document: dict) -> str:
    """Names the root a document's paths are relative to.

    Args:
        document: One OpenAPI document.

    Returns:
        Its first server URL without a trailing slash, or the empty string when
        it declares none (or only the origin) and writes its paths absolute.
    """
    servers = document.get("servers") or [{"url": "/"}]
    return str(servers[0].get("url", "/")).rstrip("/")


def operations(document: dict, mount: str | None = None) -> dict:
    """Reads a document's operations, keyed by `METHOD address` — its root and its path.

    Args:
        document: One OpenAPI document.
        mount: Where its paths are served below, when the document does not say
            (`None` reads its `servers`).

    Returns:
        Each operation, by `METHOD address`.
    """
    root = served_under(document) if mount is None else mount
    found = {}
    for path, entry in document["paths"].items():
        for method, operation in entry.items():
            if method in METHODS:
                found[f"{method.upper()} {root}{path}"] = operation
    return found


def below(key: str, root: str) -> str:
    """Returns one operation key with its document's root taken off its address.

    Args:
        key: `METHOD address`.
        root: The root the document serves its operations under.

    Returns:
        `METHOD path`, the path as it reads below that root.
    """
    method, address = key.split(" ", 1)
    return f"{method} {address[len(root):] if address.startswith(root) else address}"


def success_codes(operation: dict) -> list:
    """Names the 2xx statuses one operation answers with.

    Args:
        operation: One operation.

    Returns:
        Its success statuses, sorted, so two readings are comparable.
    """
    return sorted(
        code for code in (operation.get("responses") or {}) if code.startswith("2")
    )


def response_properties(document: dict, operation: dict) -> set:
    """Collects every property name a SUCCESSFUL response can carry.

    EVERY 2xx, NOT `200` ALONE, and the difference is not a refinement — it is
    the difference between reading an operation and skipping it. This function
    took `responses["200"]` and nothing else, so an operation whose success is a
    201, a 202 or a 204 was compared as though neither side answered anything:
    both sets came back empty, no difference was emitted, and the register said
    nothing at all about it.

    WHAT THAT HID, measured when the tunnel's verbs were declared: three
    operations of this contract answer 201 or 202 and contributed nothing to the
    shape table, and TWELVE operations both documents declare have a success
    status spelled differently on the two sides. On the ones whose backend
    answer carries a BODY the silence was worse than silence — it was a wrong
    cause. `POST /api/pipeline/run` read as « the interface requires `state` and
    `uid`, the backend answers neither », when the backend answers `queued` and
    `run_uid` under 202; `POST /api/acquisition/followed` read the same way over
    a 201 carrying thirty-four properties. A 204 genuinely carries no body, so
    those rows were right by accident and stay unchanged.

    THE STATUS ITSELF IS STILL NOT A DEMAND THIS FILE CAN EXPRESS. Reading every
    2xx makes the SHAPES comparable; it does not record that one side says 202
    where the other says 200. That table does not exist, and until it is
    decided, a status demand is written by hand where the register cannot carry
    it.

    `$ref`s are resolved and cycles are guarded, so a self-referential schema
    cannot hang the walk.

    Args:
        document: The whole document, for resolving references.
        operation: One operation.

    Returns:
        Every property name reachable from any of its 2xx responses.
    """
    answers = [
        answer for code, answer in (operation.get("responses") or {}).items()
        if code.startswith("2")
    ]
    schemas = [
        (answer.get("content", {}).get("application/json", {}) or {}).get("schema")
        for answer in answers
    ]
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

    for schema in schemas:
        walk(schema)
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


def compute(backend: Backend = BACKENDS["v0"], wanted_path: Path = WANTED) -> tuple[str, dict]:
    """Builds one backend's register from the contract and that backend's document.

    Args:
        backend: The backend the contract is compared against.
        wanted_path: The contract.

    Returns:
        The register's text, and the count of each kind of row for the summary line.
    """
    wanted = json.loads(wanted_path.read_text(encoding="utf-8"))
    have = json.loads(backend.document.read_text(encoding="utf-8"))
    ours, theirs = operations(wanted), operations(have, backend.mount)
    root = served_under(wanted)

    def ours_below(key: str) -> str:
        return below(key, root)

    def theirs_below(key: str) -> str:
        return below(key, backend.root)

    # Matched on the path below each document's root with its parameter NAMES
    # blanked, so a `{followedId}` against a `{followed_id}` is not read as a
    # missing operation, nor `/api/v1/…` against `/api/…`.
    theirs_by_shape = {shape_of(theirs_below(key)): key for key in theirs}
    ours_by_shape = {shape_of(ours_below(key)): key for key in ours}
    missing = sorted(key for key in ours if shape_of(ours_below(key)) not in theirs_by_shape)
    unused = sorted(key for key in theirs if shape_of(theirs_below(key)) not in ours_by_shape)
    shared = sorted(key for key in ours if shape_of(ours_below(key)) in theirs_by_shape)

    def counterpart_of(key: str) -> str:
        return theirs_by_shape[shape_of(ours_below(key))]

    spelling = sorted(
        (key, counterpart_of(key))
        for key in shared
        if ours_below(key) != theirs_below(counterpart_of(key))
    )

    # WHICH STATUS EACH SIDE ANSWERS ON SUCCESS, and it is a demand of its own.
    # Reading every 2xx made the SHAPES comparable; it says nothing about one
    # side answering 202 where the other says 200, and that is exactly the
    # difference NE-DOIT-PAS-3 turns on: the backend refuses a second ask with a
    # 409 where §20 requires the interface to show it QUEUED. A demand nobody
    # computes is a demand that drifts, so it is computed.
    status = sorted(
        (key, ours[key]["operationId"], required, answered)
        for key, required, answered in (
            (key, success_codes(ours[key]), success_codes(theirs[counterpart_of(key)]))
            for key in shared
        )
        if required != answered
    )

    shape = []
    for key in shared:
        counterpart = theirs[counterpart_of(key)]
        required_names = response_properties(wanted, ours[key])
        answered_names = response_properties(have, counterpart)
        added, dropped = sorted(required_names - answered_names), sorted(answered_names - required_names)
        if added or dropped:
            shape.append((key, ours[key]["operationId"], added, dropped))

    formatted = formatted_fields(wanted)
    counts = {"missing": len(missing), "shape": len(shape), "spelling": len(spelling),
              "status": len(status), "unused": len(unused)}
    if backend.name == "v1":
        return render_v1(root, len(ours), len(theirs), missing, ours, shape, spelling, status,
                         formatted, unused), counts

    lines = [
        "# What the interface asks of the backend",
        "",
        "**COMPUTED, NEVER WRITTEN.** `python3 scripts/compare-contracts.py --write` builds this",
        "file by diffing `frontend/maquette/contract/openapi.json` — the contract the maquette's",
        "interface REQUIRES — against `frontend/openapi.json`, which is generated FROM the running",
        "backend. `--check` refuses a committed register that differs from the computed one, so the",
        "two cannot separate. Edit the contract, not this file.",
        "",
        f"**THE INTERFACE ADDRESSES EVERY OPERATION UNDER `{root}`** — its contract's `servers`",
        f"URL, its paths relative to it — where the backend serves them under `{V0_ROOT}`. That",
        "root is one demand, said here once: the operations below are matched on the path BELOW",
        "each root, and written as each side addresses them.",
        "",
        "**IT DESCRIBES OPERATIONS, AND A WEBSOCKET IS NOT ONE.** OpenAPI cannot declare",
        f"`{root}/events`, so nothing about the event stream can ever appear below — and nothing",
        "reads as identical to no demands (B-153). The stream's demands are written BY HAND in",
        "`docs/reference/frontend-backend-demands-stream.md`. This pointer lives in the",
        "GENERATOR, so regenerating this file cannot drop it.",
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
        f"| declared by both, answered with a different status | {len(status)} |",
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
        "## 2c. Operations both declare, answered with a different status",
        "",
        "**A STATUS IS A DEMAND, and it was invisible here until 2026-09-06.** The comparison",
        "above reads property NAMES; two documents can agree on every name and still disagree",
        "on what the answer means. `POST /api/acquisition/journeys/{infoHash}/requeue` is the",
        "case this table was built for: the backend answers **409** when a requeue for the item",
        "is already in flight, and NE-DOIT-PAS-3 with §20 forbid the interface showing that — an",
        "ask at the bound is QUEUED, visibly, never refused. So the interface declares a queued",
        "202 and the difference is recorded rather than reconciled.",
        "",
        "**Most rows here predate the lot that built the table.** Twelve operations already",
        "disagreed, and they are the backend's own business — a 202 where the interface expects",
        "a 200 is not a defect in either document, it is a decision nobody had written down.",
        "",
    ]
    if status:
        lines += ["| operation | operationId | the interface requires | the backend answers |",
                  "| --- | --- | --- | --- |"]
        for key, operation_id, mine, yours in status:
            lines.append(
                f"| `{key}` | `{operation_id}` | "
                f"{', '.join(f'`{code}`' for code in mine) or '—'} | "
                f"{', '.join(f'`{code}`' for code in yours) or '—'} |")
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
    return "\n".join(lines), counts


def table(rows: list, header: str, divider: str) -> list:
    """Renders one register table, or « None. » when it has no row.

    Args:
        rows: The table's rows, already rendered.
        header: Its header line.
        divider: Its divider line.

    Returns:
        The table's lines.
    """
    return [header, divider, *rows] if rows else ["None."]


def render_v1(root: str, required: int, served: int, missing: list, ours: dict, shape: list,
              spelling: list, status: list, formatted: list, unused: list) -> str:
    """Writes v1's register: the same tables as v0's, in v1's words.

    Args:
        root: The root the contract addresses its operations under.
        required: How many operations the contract declares.
        served: How many operations v1 serves.
        missing: The contract's operations v1 does not serve.
        ours: The contract's operations, by key.
        shape: The shared operations whose response names differ.
        spelling: The shared operations whose path parameters are spelled differently.
        status: The shared operations answered with a different success status.
        formatted: The fields the contract carries pre-formatted.
        unused: The operations v1 serves and the contract does not declare.

    Returns:
        The register's text.
    """
    def codes(found: list) -> str:
        return ", ".join(f"`{code}`" for code in found) or "—"

    lines = [
        "# What the interface asks of v1",
        "",
        "**COMPUTED, NEVER WRITTEN.** `python3 scripts/compare-contracts.py --write --have v1`",
        "builds this file by diffing `frontend/maquette/contract/openapi.json` — the contract the",
        "interface REQUIRES — against `frontend/openapi-v1.json`, which",
        "`python scripts/export-openapi.py --v1` generates FROM the v1 application.",
        "`--check --have v1` refuses a committed register that differs from the computed one, so",
        "the two cannot separate. Edit the contract or v1, not this file.",
        "",
        "**ITS ROW COUNT IS THE MEASURE OF THE BACKEND'S END**: v1 is done when sections 1, 2,",
        "2b, 2c and 4 read « None. » (section 3 is a demand on the contract's fields, which v1",
        "answers as declared). The v0 register, `docs/reference/frontend-backend-demands.md`,",
        "compares the same contract against today's backend; this one does not replace it.",
        "",
        f"**BOTH SIDES ADDRESS EVERY OPERATION UNDER `{root}`**: the contract's `servers` URL, and",
        "where the web application mounts v1. Operations are matched on the path below it.",
        "",
        "**IT DESCRIBES OPERATIONS, AND A WEBSOCKET IS NOT ONE.** OpenAPI cannot declare",
        f"`{root}/events`; the stream's demands are written by hand in",
        "`docs/reference/frontend-backend-demands-stream.md`.",
        "",
        "**A SERVED OPERATION IS HELD TO MORE THAN THIS.** Names and statuses are what a register",
        "can carry; `tests/http_v1/test_contract_conformance.py` holds every operation v1 serves to",
        "the contract field by field — enums, required sets, request bodies, refusals and rights.",
        "",
        "| | |",
        "| --- | ---: |",
        f"| operations the interface requires | {required} |",
        f"| operations v1 serves | {served} |",
        f"| required and not served | {len(missing)} |",
        f"| served, different response shape | {len(shape)} |",
        f"| served, path parameter spelled differently | {len(spelling)} |",
        f"| served, answered with a different status | {len(status)} |",
        f"| fields carried pre-formatted | {len(formatted)} |",
        f"| v1 serves and the interface does not declare | {len(unused)} |",
        "",
        "---",
        "",
        "## 1. Operations the interface requires and v1 does not serve",
        "",
        *table([f"| `{key}` | `{ours[key]['operationId']}` | {ours[key].get('summary', '')} |"
                for key in missing],
               "| operation | operationId | what it is for |", "| --- | --- | --- |"),
        "",
        "## 2. Operations both declare, whose response carries different property names",
        "",
        *table([f"| `{key}` (`{operation_id}`) | {codes(added)} | {codes(dropped)} |"
                for key, operation_id, added, dropped in shape],
               "| operation | the interface adds | v1 has and the interface does not use |",
               "| --- | --- | --- |"),
        "",
        "## 2b. Operations both declare, whose path parameter is spelled differently",
        "",
        *table([f"| `{mine}` | `{yours}` |" for mine, yours in spelling],
               "| the interface requires | v1 has |", "| --- | --- |"),
        "",
        "## 2c. Operations both declare, answered with a different status",
        "",
        *table([f"| `{key}` | `{operation_id}` | {codes(mine)} | {codes(yours)} |"
                for key, operation_id, mine, yours in status],
               "| operation | operationId | the interface requires | v1 answers |",
               "| --- | --- | --- | --- |"),
        "",
        "## 3. Fields the interface carries pre-formatted",
        "",
        "The demand is the same for every one of them: supply the underlying fact and let the",
        "interface format it.",
        "",
        *table([f"| `{where}` | `{name}` |" for where, name in formatted],
               "| where | field |", "| --- | --- |"),
        "",
        "## 4. Operations v1 serves and the interface does not declare",
        "",
        "v1 is written from the contract, so a row here is a defect: the contract declares it, or",
        "v1 drops it.",
        "",
        *([f"- `{key}`" for key in unused] or ["None."]),
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    """Writes or checks one backend's register, then prints its summary line."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="(re)compute the register")
    group.add_argument("--check", action="store_true", help="report drift, exit 1")
    parser.add_argument("--have", choices=sorted(BACKENDS), default="v0",
                        help="the backend compared against the contract (default: v0)")
    arguments = parser.parse_args()
    backend = BACKENDS[arguments.have]
    register = backend.register

    computed, counts = compute(backend)
    summary = f"compare-contracts: {backend.name} " + " ".join(
        f"{kind}={count}" for kind, count in counts.items())
    if arguments.write:
        register.parent.mkdir(parents=True, exist_ok=True)
        register.write_text(computed, encoding="utf-8")
        print(f"compare-contracts: wrote {register.relative_to(ROOT)}")
        print(summary)
        return 0

    if not register.is_file():
        print(f"compare-contracts: {register.relative_to(ROOT)} is missing — the register "
              f"is the deliverable, not a by-product", file=sys.stderr)
        print(summary)
        return 1
    if register.read_text(encoding="utf-8") != computed:
        print(f"compare-contracts: {register.relative_to(ROOT)} differs from the two "
              f"contracts it is computed from. Rebuild with "
              f"`python3 scripts/compare-contracts.py --write{backend.flag}`", file=sys.stderr)
        print(summary)
        return 1
    print(f"compare-contracts: {register.relative_to(ROOT)} matches the computed diff")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())

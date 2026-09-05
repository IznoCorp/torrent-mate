#!/usr/bin/env python3
"""A maquette comment must still read years from now, out of context.

THE RULE IS `CLAUDE.md` § Language, and it had no arm: « Maquette/harness
comments carry no reference to a session, a phase or a dated decision — they
must still read years from now, out of context. » A comment saying « moved at
L19 » or « arbitrated on 2026-08-31 » is written for the reader who was there.
Everyone after them has to find a wave that no longer exists in the tree to
learn what the sentence means, and the sentence is usually one they need.

WHAT IT COUNTS, and the boundary is the operator's own (2026-09-05): a LOT CODE
(`L19`), a PHASE (`phase 13`) and a DATE (`2026-08-31`). Not a register entry
(`B-247`), not a rule (`R103`), not a clause (`DOIT-8`, `§20`), not a decision
(`D-L08-5`) and not a path — those name things that outlive the wave that wrote
them, and they are how a comment stays checkable.

IT IS A RATCHET, NOT A GATE, and it is per file. There were three hundred such
references when this arm was written, across ninety-eight files, and a wave that
had to clear them all before it could land would be a wave nobody starts. What
it refuses is a file's count going UP — which is what makes a debt a debt rather
than a habit. `--record` re-takes the baseline; a file below its record is
printed with `[RE-RECORD]` and refused nothing, exactly as the size ledger's
count is.

WHAT IT READS THAT IS NOT A COMMENT, and there is one: `contract/openapi.json`.
The contract's descriptions are prose under the same rule, and they reach the
tree twice — once at the source, once inside `design/src/contract/types.d.ts`,
which a generator writes. A generated file is opened by no one and edited by no
one, so it is EXEMPT and named as such with its generator; reading it instead of
its source would report one defect as two and send its reader to the file nobody
may edit.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1] / "frontend" / "maquette"
BASELINE = ROOT / "comment-references-baseline.json"

# The sources whose comments are read. `.js` is here for the dying engine, which
# holds more of these than any other file and must not gain one.
SUFFIXES = (".py", ".ts", ".tsx", ".css", ".js")

# Never read: a build's output, an installed dependency, and the files a
# generator writes. A generated file is opened by no one, so a rule about how a
# comment READS has no subject in it — and its prose is held at its source.
SKIPPED_DIRECTORIES = ("/dist/", "/node_modules/", "/.vite/")
GENERATED = {
    "design/src/contract/types.d.ts":
        "npm run generate-contract-types — the descriptions inside it are "
        "copied from contract/openapi.json, which this arm reads instead",
}

# Prose the contract carries, read at the SOURCE for the reason above.
CONTRACT = "contract/openapi.json"

# What names a wave rather than a thing. A lot code, a phase, a date.
TEMPORAL = (
    ("a lot code", re.compile(r"(?<![A-Za-z0-9-])L\d{2}(?![\d])")),
    ("a phase", re.compile(r"\bphases?\s+\d", re.I)),
    ("a date", re.compile(r"\b20\d\d-\d\d-\d\d\b")),
)

# What is NOT one, blanked before the patterns above are asked. A DECISION is
# `D-L08-5` and carries a lot code inside it: it names a decision that stands
# until it is replaced, which is the opposite of a wave. Blanked rather than
# excluded by a look-behind, because the look-behind would have to know every
# prefix anyone invents.
NOT_TEMPORAL = re.compile(r"\bD-L\d{2}-\d+\b")


def comments(source: str, suffix: str):
    """Yields the comment text of one source, and nothing else.

    A guard that counted its own subject inside a string literal would refuse
    code that merely quotes a lot code — and this arm's own tests do.

    Args:
        source: The file's text.
        suffix: Its extension, which decides the comment syntax.

    Yields:
        Each comment's text.
    """
    if suffix == ".py":
        for line in source.splitlines():
            hit = re.search(r"#(.*)$", line)
            if hit:
                yield hit.group(1)
        for block in re.findall(r'"""(.*?)"""', source, re.S):
            yield block
        return
    for block in re.findall(r"/\*.*?\*/", source, re.S):
        yield block
    for line in source.splitlines():
        hit = re.search(r"//(.*)$", line)
        if hit:
            yield hit.group(1)


def references(text: str) -> list[str]:
    """Every temporal reference in one piece of prose.

    Args:
        text: The prose.

    Returns:
        One entry per reference, naming what it is and what it said.
    """
    readable = NOT_TEMPORAL.sub(" ", text)
    found = []
    for what, pattern in TEMPORAL:
        found.extend(f"{what} — « {hit.group(0)} »"
                     for hit in pattern.finditer(readable))
    return found


def sources():
    """Yields every file this arm reads, with its text.

    Yields:
        (relative path, text, suffix).
    """
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        relative = path.relative_to(ROOT).as_posix()
        if any(part in "/" + relative for part in SKIPPED_DIRECTORIES):
            continue
        if relative in GENERATED:
            continue
        yield relative, path.read_text(encoding="utf-8", errors="replace"), path.suffix


def contract_prose():
    """Every string the contract carries, which is prose under the same rule.

    Yields:
        Each string value in `contract/openapi.json`.
    """
    path = ROOT / CONTRACT
    if not path.is_file():
        return
    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)
        elif isinstance(node, str):
            yield node
    yield from walk(json.loads(path.read_text(encoding="utf-8")))


def measure() -> tuple[dict[str, int], dict[str, list[str]]]:
    """Counts the temporal references of the whole tree.

    Returns:
        `(count per file, the references per file)`.
    """
    counts: dict[str, int] = {}
    detail: dict[str, list[str]] = {}
    for relative, text, suffix in sources():
        found: list[str] = []
        for comment in comments(text, suffix):
            found.extend(references(comment))
        if found:
            counts[relative] = len(found)
            detail[relative] = found
    found = [entry for prose in contract_prose() for entry in references(prose)]
    if found:
        counts[CONTRACT] = len(found)
        detail[CONTRACT] = found
    return counts, detail


def compare(counts: dict[str, int], recorded: dict[str, int]):
    """Holds each file's count against its record, and never the total alone.

    PER FILE, because a total hides a trade: one file clearing three references
    while another gains three leaves the total where it was, and the habit this
    refuses is per file.

    Args:
        counts: What the tree reads now.
        recorded: What the baseline holds.

    Returns:
        `(grown, shrunk)` — the violations, and the entries to re-record.
    """
    grown, shrunk = [], []
    for relative in sorted(set(counts) | set(recorded)):
        now = counts.get(relative, 0)
        was = recorded.get(relative, 0)
        if now > was:
            grown.append(
                f"{relative}: {now} reference(s) to a lot, a phase or a date "
                f"in its comments, recorded at {was}. A maquette comment must "
                f"read years from now, out of context — say what changed, not "
                f"which wave changed it")
        elif now < was:
            shrunk.append(f"{relative}: {now}, recorded at {was}")
    return grown, shrunk


def main() -> int:
    """Runs the arm.

    Returns:
        The process's exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true",
                        help="re-take the baseline from the tree")
    parser.add_argument("--list", action="store_true",
                        help="print every reference, not only the counts")
    arguments = parser.parse_args()

    counts, detail = measure()
    total = sum(counts.values())

    if arguments.record:
        BASELINE.write_text(
            json.dumps({"note": "One entry per file: how many references to a "
                                "lot, a phase or a date its comments hold. "
                                "Refused UPWARD; re-record a file that has "
                                "shrunk in the commit that shrinks it.",
                        "files": dict(sorted(counts.items()))},
                       indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"check-maquette-comments: recorded {total} reference(s) in "
              f"{len(counts)} file(s)")
        return 0

    if arguments.list:
        for relative in sorted(detail):
            for entry in detail[relative]:
                print(f"    {relative}: {entry}")

    if not BASELINE.is_file():
        print(f"check-maquette-comments: {BASELINE.name} is missing — this arm "
              f"has nothing to compare and refuses to report clean",
              file=sys.stderr)
        return 1
    recorded = json.loads(BASELINE.read_text(encoding="utf-8"))["files"]

    # A CORPUS FLOOR, because a reader that finds nothing reports clean. If the
    # tree stops being readable — a moved directory, a suffix list that no
    # longer matches — this arm would print « 0 references » and pass for the
    # one reason it must never pass for.
    read = sum(1 for _ in sources())
    if read < 100:
        print(f"check-maquette-comments: {read} file(s) read, which is fewer "
              f"than this tree holds — the reader stopped reading",
              file=sys.stderr)
        return 1

    grown, shrunk = compare(counts, recorded)

    print(f"check-maquette-comments: {total} reference(s) in {len(counts)} of "
          f"{read} file(s) read, {len(GENERATED)} generated file(s) exempt, "
          f"{len(grown)} grown")
    for name, why in sorted(GENERATED.items()):
        print(f"      {name}: {why}")
    for entry in shrunk:
        print(f"    [RE-RECORD] {entry} — re-record it in THIS commit, with "
              f"`--record`: a count re-recorded later is a count nobody compared")
    for entry in grown:
        print(f"    {entry}", file=sys.stderr)
    if grown:
        print(f"check-maquette-comments: {len(grown)} violation(s)", file=sys.stderr)
        return 1
    print("check-maquette-comments: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())

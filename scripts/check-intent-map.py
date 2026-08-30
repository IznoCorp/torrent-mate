#!/usr/bin/env python3
"""B-142 — every clause of the constitution names the surface that serves it.

WHY IT EXISTS, and it is the whole of B-142. Three instruments compare this
interface to what already EXISTS — `IMPLEMENTATION.md` § THE OBJECTIVE, the
demands register, `audit_design_coverage.py` — pages against pages, the maquette
against the running backend, design documents against tests. **None reads
`docs/reference/product-intent.md`**, the only document saying what the product
must BE. A capability the constitution requires that neither the maquette nor
the backend has is invisible to every gate here, and that is how three sections
dictated in one day went a month unnoticed.

WHAT IT CANNOT DO, said before what it can so nobody expects it. **It cannot
tell whether a named proof READS the clause.** Two rows of the first map named a
print statement and a rule about PM2 processes as proof, and only a READER found
them. That check is a review's, at every amendment of the map, and this guard
prints the proof beside every clause so a reader has it in front of them rather
than having to go looking.

THE MAPPING IS A DESIGN DECISION, NOT A GREP (`MODEL.md` § 4). It was written
clause by clause against the tree by L10-ter and ratified by the operator on
2026-08-30. **Seeding it from what exists would certify the status quo** — the
vocabulary file did exactly that and let twenty-four French words in with the
rest — so this guard never generates a row, only refuses one.

WHERE THE CLAUSES ARE. Inside the two sections « Ce que l'interface DOIT faire »
and « Ce que l'interface NE DOIT PAS faire » and nowhere else: the same pattern
over the whole file matches 24 lines for 23 clauses, because §19's fourth point
begins « 4. **NE-DOIT-PAS-8 est la limite dure.** ». The section bound is what
makes 24 into 23, and the floors below refuse a reading that finds neither.

IT PRINTS ONE LINE PER CLAUSE AND NEVER A COUNT ALONE. A number that is printed
and not compared is a number nobody reads: a control drifted by seven inside the
pull request that introduced it as a control.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONSTITUTION = ROOT / "docs" / "reference" / "product-intent.md"
MAP = ROOT / "docs" / "reference" / "product-intent-map.md"
PLAN = ROOT / "docs" / "reference" / "frontend-architecture.md"
DESIGN = ROOT / "frontend" / "maquette" / "design" / "src"

# The two sections the clauses live in, by their headings.
# THE TWO HEADINGS, VERBATIM. french-ok: the constitution is an operator-facing
# document and is French by the rule's own exemption (`CLAUDE.md` § Language);
# these are the headings it really carries, and a guard that reads a French
# document has to say the words that document uses. Translating them would make
# this guard find nothing and report « no violation » about it.
SECTIONS = (
    # french-ok: the constitution's own heading, verbatim
    "## Ce que l'interface DOIT faire",
    # french-ok: the constitution's own heading, verbatim
    "## Ce que l'interface NE DOIT PAS faire",
)
CLAUSE = re.compile(r"^\d+\. \*\*((?:NE-)?DOIT(?:-PAS)?-\d+)\b", re.MULTILINE)

# One row of either table: `| **DOIT-1** — … | surface | verdict | proof |`.
ROW = re.compile(
    r"^\|\s*\*\*((?:NE-)?DOIT(?:-PAS)?-\d+)\*\*[^|]*\|([^|]*)\|([^|]*)\|(.*)\|\s*$",
    re.MULTILINE,
)

# THE FIVE WORDS THE MAP DECLARES, and no sixth. A verdict outside them is a
# verdict nobody has defined, which is worse than a missing row: a row reads as
# an answer.
VERDICTS = {"served", "served, unproved", "partly", "to draw", "outside the interface"}

# The verdicts that must NAME a surface in the tree. `to draw` names none by
# definition, and `outside the interface` says the clause binds the backend or
# the method.
MUST_NAME_A_SURFACE = {"served", "served, unproved", "partly"}

# The verdicts that owe a lot: the half of the work nobody has done yet.
MUST_NAME_A_LOT = {"to draw", "partly"}

FEATURE = re.compile(r"`?features/([a-z-]+)")
ROUTE = re.compile(r"`(/[\w$/-]*)`")
LOT = re.compile(r"\bL(\d{2})\b")
# A proof is a numbered rule, a harness script, or a repository guard. Prose is
# not a proof, and neither is a lot: a lot is what is OWED.
PROOF = re.compile(r"\bR\d+\b|harness/[\w.]+\.py|scripts/[\w.-]+\.py")

# Floors. A reading that finds fewer has stopped reading, and « no violation »
# over nothing read is the shape this repository counts.
CLAUSE_FLOOR = 20
ROW_FLOOR = 20


def clauses() -> list[str]:
    """The clause names, from the two sections that hold them.

    Returns:
        The names in document order, e.g. `["DOIT-1", …, "NE-DOIT-PAS-9"]`.
    """
    body = CONSTITUTION.read_text(encoding="utf-8")
    found: list[str] = []
    for heading in SECTIONS:
        start = body.find(heading)
        if start == -1:
            return []
        # The section ends at the next `## ` heading after its own.
        end = body.find("\n## ", start + len(heading))
        found.extend(CLAUSE.findall(body[start : end if end != -1 else len(body)]))
    return found


def rows() -> dict[str, tuple[str, str, str]]:
    """The map's rows, by clause name.

    Returns:
        `{clause: (surface, verdict, proof)}`, each cell stripped.
    """
    body = MAP.read_text(encoding="utf-8")
    # THE VERDICT IS STRIPPED OF ITS BACKTICKS. The map writes it as code —
    # `partly` — because it is a word from a closed vocabulary and reads as one;
    # the vocabulary itself is the five bare words. Comparing the two spellings
    # is how the first version of this guard refused all twenty-three rows.
    return {
        name: (surface.strip(), verdict.strip().strip("`"), proof.strip())
        for name, surface, verdict, proof in ROW.findall(body)
    }


def declared_lots() -> set[str]:
    """Every lot the plan declares, as `L15` and so on."""
    return set(re.findall(r"^#### (L\d+)", PLAN.read_text(encoding="utf-8"), re.MULTILINE))


def served_routes() -> set[str]:
    """Every path a route file serves."""
    paths: set[str] = set()
    for route in sorted((DESIGN / "routes").glob("*.tsx")):
        paths.update(re.findall(r'path:\s*"([^"]+)"', route.read_text(encoding="utf-8")))
    return paths


def main() -> int:
    """Holds the map against the constitution and against the tree.

    Returns:
        0 when every clause has a row this guard can defend, 1 otherwise.
    """
    named = clauses()
    table = rows()
    lots = declared_lots()
    routes = served_routes()
    features = {path.name for path in (DESIGN / "features").iterdir() if path.is_dir()}
    violations = 0

    if len(named) < CLAUSE_FLOOR or len(table) < ROW_FLOOR:
        print(
            f"  check-intent-map: {len(named)} clause(s) and {len(table)} row(s) "
            f"read, against floors of {CLAUSE_FLOOR} and {ROW_FLOOR}. A reader "
            "that has stopped reading refuses nothing, and says so as « no "
            "violation ».",
            file=sys.stderr,
        )
        return 1

    for name in named:
        row = table.get(name)
        if row is None:
            violations += 1
            print(
                f"  {name}: the constitution declares it and "
                f"{MAP.name} carries no row. A clause with no surface is a "
                "clause nobody owes — which is how three dictated sections went "
                "a month unnoticed (B-142).",
                file=sys.stderr,
            )
            continue
        surface, verdict, proof = row
        print(f"  {name:<16} {verdict:<22} {surface[:46]}")
        if verdict not in VERDICTS:
            violations += 1
            print(
                f"  {name}: verdict « {verdict} » is not one of the five the "
                f"map declares ({', '.join(sorted(VERDICTS))}). A word nobody "
                "defined reads as an answer.",
                file=sys.stderr,
            )
            continue
        if verdict in MUST_NAME_A_SURFACE:
            missing = [
                f"features/{feature}"
                for feature in FEATURE.findall(surface)
                if feature not in features
            ] + [path for path in ROUTE.findall(surface) if path not in routes]
            # A ROW MAY NAME NO SURFACE AT ALL and be right: several clauses
            # bind « every surface » — nothing to mistake, and nothing this
            # guard could check. What it refuses is a surface NAMED and absent,
            # which is the row reading as though something served the clause.
            if missing:
                violations += 1
                print(
                    f"  {name}: names {missing}, which the tree does not have. "
                    "A surface that is not there serves nothing, and the row "
                    "reads as though it did.",
                    file=sys.stderr,
                )
        if verdict in MUST_NAME_A_LOT:
            owed = {f"L{number}" for number in LOT.findall(proof)}
            if not owed:
                violations += 1
                print(
                    f"  {name}: « {verdict} » names no lot. What is not drawn "
                    "yet is owed by SOMEONE, and a clause nobody owes is the "
                    "defect this guard exists for.",
                    file=sys.stderr,
                )
            for lot in sorted(owed - lots):
                violations += 1
                print(
                    f"  {name}: names {lot}, which "
                    f"{PLAN.name} § 4 does not declare. A lot that does not "
                    "exist owes nothing.",
                    file=sys.stderr,
                )
        if verdict == "served" and not PROOF.search(proof):
            violations += 1
            print(
                f"  {name}: « served » and its Proof cell names no rule, no "
                "harness script and no guard. « Served » without a proof is an "
                "opinion.",
                file=sys.stderr,
            )

    extra = sorted(set(table) - set(named))
    for name in extra:
        violations += 1
        print(
            f"  {name}: the map carries a row and the constitution's two "
            "clause sections declare no such clause. A row for nothing is a "
            "row nobody re-reads.",
            file=sys.stderr,
        )

    print(
        f"check-intent-map: {len(named)} clause(s) read inside the two clause "
        f"sections (floor {CLAUSE_FLOOR}) against {len(table)} row(s) "
        f"(floor {ROW_FLOOR}), over {len(routes)} served route(s) and "
        f"{len(features)} feature directory(ies), {len(lots)} declared lot(s) — "
        f"{violations} violation(s). WHAT THIS GUARD CANNOT DO: tell whether a "
        "named proof READS its clause. That is a reader's, at every amendment "
        "of the map, which is why the proof is printed beside each clause."
    )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

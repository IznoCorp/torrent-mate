#!/usr/bin/env python3
"""Refuses the dying engine's CSS residue growing.

D-L07-5 let one hand-written stylesheet survive the conversion:
`frontend/maquette/design/src/styles/legacy.css`, the CSS for markup the
engine writes or the engine's class toggles select. It is an exception with a
date of death — L13, when `legacy.js` goes — and an exception nobody counts is
indistinguishable from an oversight.

WHAT THIS REFUSES, and it is a ratchet rather than a wall: the residue may
SHRINK freely, and every conversion that reaches into it should make it
shrink. It may not grow. A new hand-written rule for a surface this lot already
converted would be the conversion undone one file over, and it would be
invisible to every other guard: the residue is legitimate CSS in a file whose
whole purpose is to hold legitimate CSS.

THE CEILING IS DATA, NOT A LITERAL IN THE CODE. It lives beside the file it
measures, in `legacy-css-residue.json`, so lowering it after a conversion is a
one-line reviewed change and raising it is one somebody has to argue for in a
diff.

THREE FIGURES RATHER THAN ONE, because they fail differently: rules and
declarations both move when styling is added, and CLASSES is the one that says
whether a NEW SURFACE has been given hand-written CSS — the thing the lot
forbids. A rule added to a class already here is debt deepening; a class added
is debt spreading.

Usage:
    python3 scripts/check-legacy-css-residue.py
    python3 scripts/check-legacy-css-residue.py --record   # after a shrink
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESIDUE = ROOT / "frontend" / "maquette" / "design" / "src" / "styles" / "legacy.css"
CEILING = ROOT / "frontend" / "maquette" / "legacy-css-residue.json"

# A CSS comment. Stripped before anything is counted: this file explains each
# block it keeps, and the prose names class selectors while doing so — a count
# over raw text would read the explanation as the thing explained. The sibling
# guards learned this by mutation and it is not re-learned here.
COMMENT = re.compile(r"/\*.*?\*/", re.S)

# A rule: a prelude and a flat body. Nested at-rules ride the next prelude,
# which is why the class scan runs over the preludes rather than the file.
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")

# A class name inside a prelude.
CLASS = re.compile(r"\.([a-zA-Z][\w-]*)")

# A declaration's property. Counted per rule body so a nested at-rule's
# prelude cannot contribute one.
PROPERTY = re.compile(r"[\w-]+\s*:")


def measure() -> dict[str, int] | None:
    """Counts the residue's rules, classes and declarations.

    Returns:
        The three figures, or `None` when the file is absent — which is not a
        pass. The residue disappearing is either L13 having landed (and this
        guard going with it) or a build reading the wrong tree; neither is
        something a gate should answer with silence.
    """
    if not RESIDUE.exists():
        print(
            f"check-legacy-css-residue: {RESIDUE.relative_to(ROOT)} not found. "
            "If the residue has died with the engine, this guard dies with it "
            "— deliberately, in the same commit. It does not pass by absence.",
            file=sys.stderr,
        )
        return None
    stripped = COMMENT.sub(" ", RESIDUE.read_text(encoding="utf-8"))
    rules = RULE.findall(stripped)
    if not rules:
        print(
            "check-legacy-css-residue: the residue declares no rule at all — "
            "this guard measured nothing rather than finding nothing.",
            file=sys.stderr,
        )
        return None
    classes = {name for prelude, _ in rules for name in CLASS.findall(prelude)}
    declarations = sum(len(PROPERTY.findall(body)) for _, body in rules)
    return {"rules": len(rules), "classes": len(classes), "declarations": declarations}


def main() -> int:
    """Compares the residue against its recorded ceiling.

    Returns:
        0 when nothing grew, 1 when any figure did or the ceiling is missing.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--record",
        action="store_true",
        help="write the current figures as the ceiling — only ever after a SHRINK",
    )
    arguments = parser.parse_args()

    found = measure()
    if found is None:
        return 1

    if arguments.record:
        CEILING.write_text(
            json.dumps(
                {
                    "$comment": (
                        "The ceiling under `src/styles/legacy.css`, the CSS residue "
                        "D-L07-5 let survive the conversion. It dies with the engine "
                        "at L13. These figures may be LOWERED after a conversion "
                        "shrinks the residue; raising one is the conversion undone "
                        "one file over. Read by `scripts/check-legacy-css-residue.py`."
                    ),
                    "ceiling": found,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"legacy-css residue: ceiling recorded — {found}")
        return 0

    if not CEILING.exists():
        print(
            f"check-legacy-css-residue: {CEILING.relative_to(ROOT)} not found — "
            "the residue has no ceiling, so nothing bounds it. Record one with "
            "`--record`.",
            file=sys.stderr,
        )
        return 1

    ceiling = json.loads(CEILING.read_text(encoding="utf-8"))["ceiling"]
    grew = {key: (ceiling[key], value) for key, value in found.items() if value > ceiling[key]}
    if grew:
        for key, (was, now) in sorted(grew.items()):
            print(
                f"  legacy-css residue: {key} {was} → {now}. The residue is an "
                "exception with a date of death, and it may only shrink. A "
                "surface this lot converted does not get hand-written CSS back "
                "one file over.",
                file=sys.stderr,
            )
        return 1

    shrank = {key: (ceiling[key], value) for key, value in found.items() if value < ceiling[key]}
    line = ", ".join(f"{key} {value}" for key, value in sorted(found.items()))
    if shrank:
        print(
            f"legacy-css residue: {line} — under the ceiling. Lower it with "
            "`--record` so the next addition is measured against what is "
            "actually here."
        )
        return 0
    print(f"legacy-css residue: {line} — at the ceiling, nothing grew.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

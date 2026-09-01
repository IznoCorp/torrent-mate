#!/usr/bin/env python3
"""P29 — every poster box declares its size, so a loading image shifts nothing.

An `<img>` with no declared box is zero-high until its bytes arrive, and
everything below it jumps down the moment they do. On a gallery of 1 861 titles
that is the whole page moving under the reader's thumb, repeatedly, and it is
the defect a virtualiser makes WORSE rather than better: a windowed list
measures its rows, so a row that grows after paint moves the scroll position
under the finger.

THIS IS WHY P29 IS ORDERED BEFORE P24 (D-L12-2). A declared box is not a
neighbour of virtualisation, it is its precondition — a virtualiser measuring an
undeclared box measures a box that is still growing.

WHERE IT READS, AND WHY BOTH PLACES. The five declarations live in
`styles/legacy.css` today, which is the dying stylesheet with a date of death at
L13 (D10). Moving them into the typed variants is that lot's work, not this one's
— so this guard reads the variants AND the stylesheets, exactly as
`check-compositor-css.py` does and for the same reason: a guard that read only
one of them would report the whole inventory missing on the day the declarations
move, and — far worse — would report nothing at all once they had.

WHAT IT HOLDS: a floor on the number of declared poster boxes, so a declaration
that vanishes is a failure rather than a silence. The floor is a measurement, not
a preference: raise it until the guard falls, and the last value that passed is
the true count. That is the method B-272 established after this repository found
three deletable declarations sitting under a floor nobody had re-taken.

WHAT IT DOES NOT READ: whether the declared box is the RIGHT shape, and whether
the layout actually holds when a real image arrives late. The first is a drawing
decision the oracle owns at rest; the second is a runtime fact no static read can
reach, and it is `harness/poster.py`'s CLS probe. A static read alone would be
green over a declared box the layout ignores.

Exit code is the verdict: 0 when the floor is met, 1 naming what went missing.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESIGN = ROOT / "frontend" / "maquette" / "design" / "src"

# A declared box: an aspect ratio, or a height paired with a width. Written to
# match the CSS declaration and the Tailwind utility both, because the
# declarations are moving from one to the other and this guard outlives the move.
#
# THE POSTER'S OWN RATIO, not any ratio. Counting every `aspect-ratio` in the
# tree makes the floor satisfiable by declarations that are not poster boxes at
# all — a 16/9 hero added tomorrow would pay for a 2/3 poster deleted the same
# day, under a floor that never moved. A floor is only a floor over a corpus
# that cannot substitute for itself.
DECLARED_BOX = re.compile(
    r"aspect-ratio\s*:\s*2\s*/\s*3"              # CSS
    r"|aspect-\[\s*2\s*/\s*3\s*\]",              # Tailwind arbitrary
)

# `styles/harness.css` is the measuring apparatus and ships nowhere — the same
# exemption the compositor guard makes, for the same reason: an instrument may
# not satisfy a property of the thing it measures.
EXEMPT = {"styles/harness.css"}

SUFFIXES = {".css", ".ts", ".tsx"}
SKIP = {"node_modules", "dist", "__pycache__"}

# Measured on 2026-08-31 by raising it until the guard fell: five declarations in
# `styles/legacy.css` (`.poster`, the card poster, `.tile .p`, `.sheetposter`,
# `.sk.tile`). Re-take it the same way whenever it legitimately moves — a floor
# somebody typed is a floor that drifts, which is B-272.
BOX_FLOOR = 5

CORPUS_FLOOR = 100

# A comment is not a declaration. Blanked rather than removed so a reported line
# number still points at the line the declaration is on — and blanked at all
# because the compositor guard paid for reading its own prose as evidence.
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def sources() -> list[pathlib.Path]:
    """Every stylesheet and variant file under the prototype's tree.

    Returns:
        The paths, sorted.
    """
    found = []
    for path in sorted(DESIGN.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        if any(part in SKIP for part in path.parts):
            continue
        if str(path.relative_to(DESIGN)) in EXEMPT:
            continue
        found.append(path)
    return found


def main() -> int:
    """Holds the floor on declared poster boxes.

    Returns:
        0 when the floor is met.
    """
    files = sources()
    violations = 0
    if len(files) < CORPUS_FLOOR:
        print(f"  check-poster-box: {len(files)} file(s) read under "
              f"{DESIGN.relative_to(ROOT)} — under the floor of {CORPUS_FLOOR}. "
              "A reader that has stopped reading refuses nothing.",
              file=sys.stderr)
        violations += 1

    boxes = 0
    where: list[str] = []
    for path in files:
        body = path.read_text(encoding="utf-8", errors="replace")
        code = CSS_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), body)
        found = DECLARED_BOX.findall(code)
        if found:
            boxes += len(found)
            where.append(f"{path.relative_to(DESIGN)}×{len(found)}")

    if boxes < BOX_FLOOR:
        violations += 1
        print(f"  {boxes} declared poster box(es), under the floor of "
              f"{BOX_FLOOR} (P29). An image with no declared box is zero-high "
              "until its bytes arrive and everything below it jumps when they "
              "do — and a virtualiser measuring a box that is still growing "
              "moves the scroll position under the finger.", file=sys.stderr)

    print(f"check-poster-box: {len(files)} source(s) read under "
          f"{DESIGN.relative_to(ROOT)} (floor {CORPUS_FLOOR}), {boxes} declared "
          f"poster box(es) (floor {BOX_FLOOR}) in {', '.join(where) or 'nothing'}, "
          f"{violations} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

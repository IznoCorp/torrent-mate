#!/usr/bin/env python3
"""Refuses `maximum-scale` and `user-scalable=no` anywhere in the maquette.

WHY A GUARD AND NOT THE ACCESSIBILITY TIER. `axe` reports `meta-viewport` when
the directive is PRESENT on the document it audits, and B-230 was never present
on that document: the dying engine added a viewport meta — carrying both
directives — only to a host that had NONE, and the maquette's own host has one.
So the branch was dead here and live on every other host the file could be
served from, and the tier that exists to catch exactly this violation could not
see it. A landmine is not a defect: it is a defect waiting for a different
reader.

WHAT IT READS. Every source under `frontend/maquette/design` — markup, script
and stylesheet alike — because the defect was a STRING built in JavaScript, and
a reader that only opened the HTML would have found nothing. Comments are read
too, and deliberately: this file's own subject is a directive nobody reads, and
a directive commented out is one edit away from being live. The only file
allowed to spell either of them is this one.

WHY 1.4.4. Those two directives forbid the pinch-zoom WCAG 1.4.4 requires, and
axe reported the failure on all 83 named states when they were declared: the
single largest per-state count in L03's opening measurement. They were there to
stop iOS zooming a focused input; iOS Safari has ignored `user-scalable=no`
since version 10, so what they bought was the violation and nothing else.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# THE WHOLE MAQUETTE, NOT ONLY THE PROTOTYPE'S TREE. The first version read
# `design/` alone — and B-230's own story is a directive added to a host that
# had no viewport meta, so the HOSTS are where the next one lands.
# `frontend/maquette/serve.py` emits four viewport metas and
# `frontend/maquette/installable.py` a fifth, and every one of them was outside
# this guard while its docstring told the story of a host.
MAQUETTE = ROOT / "frontend" / "maquette"

# The two directives, in the spellings a browser accepts: whitespace around the
# separator is legal and `USER-SCALABLE` is case-insensitive, so neither is
# matched as a bare literal.
FORBIDDEN = (
    ("maximum-scale", re.compile(r"maximum\s*-\s*scale", re.IGNORECASE)),
    # `false` too: Blink's viewport parser reads it as a refusal, and the
    # first version accepted only `no` and `0`.
    ("user-scalable refused",
     re.compile(r"user\s*-\s*scalable\s*=\s*(no|0|false)", re.IGNORECASE)),
)

# What this guard reads. `dist/` is a build of the same sources and would
# double every finding; `node_modules/` is nobody's to fix.
# `.py` is here because the hosts are Python and they emit the meta.
SUFFIXES = {".html", ".js", ".jsx", ".ts", ".tsx", ".css", ".py"}
SKIP = {"node_modules", "dist", "__pycache__"}

# THE ONE PLACE THE WORDS MAY APPEAR, and it is this file. A guard that cannot
# name its own subject cannot be documented, and a blanket exemption for
# comments would let the directive come back one uncomment away.
ALLOWED = {Path(__file__).resolve()}

# A reading that finds fewer than this has stopped reading, whatever it says
# about the directives. Re-run `--help` on the printed figure rather than
# trusting this comment for the size: the guard prints its corpus on every
# run, and a comment that states the number is the thing this repository
# keeps having to correct. The floor is set low enough that an ordinary
# deletion does not trip it and high enough that a broken glob does.
CORPUS_FLOOR = 50


# `"maximum" + "-scale=1"` is the same directive with a plus sign in the middle,
# and a reader of raw text sees neither half. Written as the mutation that found
# it: the guard's first version passed over exactly that, which is the shape
# L07's split-class hold had — 35 of 89 sites read, and the rest invisible.
CONCATENATION = re.compile(r"""["'`]\s*\+\s*["'`]""")


def fold_concatenations(body: str) -> str:
    """Joins adjacent string literals so a split directive reads as one.

    WHAT IT STILL CANNOT SEE, said rather than left to be discovered: a value
    composed at RUNTIME — `"maximum-" + suffix`, a template with an
    interpolation, a name assembled from an array. No reader of source text can,
    and a guard claiming otherwise would be claiming more than it does. What
    this fold covers is the shape a person writes to get past a text search,
    which is the shape that actually happens.

    Args:
        body: A file's text.

    Returns:
        The same text with `"a" + "b"` read as `ab`.
    """
    return CONCATENATION.sub("", body)


def sources() -> list[Path]:
    """Every file this guard reads, in a stable order.

    Returns:
        The paths, sorted.
    """
    found = []
    for path in sorted(MAQUETTE.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        if any(part in SKIP for part in path.parts):
            continue
        found.append(path)
    return found


def main() -> int:
    """Refuses either directive, and refuses an empty corpus.

    Returns:
        0 when neither directive appears; 1 otherwise.
    """
    files = sources()
    violations = 0
    if len(files) < CORPUS_FLOOR:
        print(
            f"  check-viewport-directives: {len(files)} file(s) read under "
            f"{MAQUETTE.relative_to(ROOT)} — under the floor of {CORPUS_FLOOR}. "
            "A reader that has stopped reading refuses nothing and says so as "
            "« no violation ».",
            file=sys.stderr,
        )
        violations += 1
    for path in files:
        if path.resolve() in ALLOWED:
            continue
        body = fold_concatenations(path.read_text(encoding="utf-8", errors="replace"))
        for name, pattern in FORBIDDEN:
            found = pattern.search(body)
            if not found:
                continue
            line = body.count("\n", 0, found.start()) + 1
            violations += 1
            print(
                f"  {path.relative_to(ROOT)}:{line}: declares « {name} », "
                "which forbids the pinch-zoom WCAG 1.4.4 requires (B-230). iOS "
                "Safari has ignored it since version 10, so what it buys is the "
                "violation and nothing else. The accessibility tier cannot see "
                "it where it is written into a string a branch may never take.",
                file=sys.stderr,
            )
    print(
        f"check-viewport-directives: {len(files)} source file(s) read under "
        f"{MAQUETTE.relative_to(ROOT)} (floor {CORPUS_FLOOR}), {violations} "
        "violation(s) — neither `maximum-scale` nor a `user-scalable` refusal, "
        "in markup, in script or in a stylesheet"
    )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

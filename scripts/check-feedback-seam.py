#!/usr/bin/env python3
"""Holds the feedback seam: ONE implementation, and every gesture through it.

WHY A COUNT AND NOT A CONVENTION. D9 refuses the haptic capability and builds
the seam instead:

    Haptics — refuse the capability, build the seam. The target platform exposes
    no public API; the workarounds ride an implementation detail that has already
    been tightened once. One `feedback()` call site all gestures pass through,
    visual today — so adopting it later changes one file.

« So adopting it later changes ONE FILE » is the whole value, and it is a
property that decays silently: a surface that writes its own acknowledgement
works perfectly today and is a gesture that stays mute the day haptics arrive,
with nothing to say why. Nobody notices a seam that has quietly stopped being
one — which is exactly the shape a count refuses and a convention does not.

WHAT IT READS, AND WHY IT IS THE WHOLE TREE. A guard that grepped `lib/` would
be green over a second implementation in `features/`, in `app/`, in `ui/` or in
the engine — and `features/` is precisely where a surface would be tempted to
write one. The B-085 question is asked here in advance rather than answered
after: this reads every source under the prototype's tree, and prints the
directories it walked so a corpus that has stopped being read says so.

THE TWO HOLDS:

  1. EXACTLY ONE IMPLEMENTATION. One module declares `feedback`; everything else
     imports it. The floor and the ceiling are the same number, because « at
     least one » would pass over two and « at most one » would pass over none.
  2. EVERY GESTURE PASSES THROUGH IT. The gestures are named here rather than
     discovered, and that is deliberate: a rule that discovered them would find
     whatever exists and hold it against itself, which is « a rule can certify
     the defect ». Adding a gesture means adding a line here, in review.

WHAT IT DOES NOT READ, said rather than left to be found: whether the
acknowledgement is CORRECT — that a commit is marked and a refusal is not, that
the mark is removed again. That is a rendering and a behaviour, held by the
harness rule that drives a real finger. This guard holds the SHAPE of the seam.

Exit code is the verdict: 0 when both holds pass, 1 naming what went wrong.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESIGN = ROOT / "frontend" / "maquette" / "design" / "src"

# The module that is allowed to DECLARE the seam. Every other file imports it.
SEAM = "lib/feedback.ts"

# A declaration of the function, in any of the spellings this tree uses. An
# IMPORT of the name is not a declaration and must not be counted as one — the
# first version of this pattern matched both and reported eleven
# implementations, which is a guard that cannot tell its subject from its users.
DECLARATION = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?function\s+feedback\s*\(", re.MULTILINE)

# Every gesture in the interface, and the file that arbitrates it. NAMED, not
# discovered — see the docstring's second hold.
GESTURES = {
    "the long press": "lib/press-arbitration.ts",
    "the drawer's dismiss swipe": "app/drawer-gesture.ts",
    "the sheet's dismiss drag": "ui/sheet.tsx",
    "the pull to refresh": "lib/pull-gesture.ts",
}

# A reading that finds fewer than this has stopped reading, whatever it says
# about the seam.
CORPUS_FLOOR = 100

SUFFIXES = {".ts", ".tsx", ".js", ".jsx"}
SKIP = {"node_modules", "dist", "__pycache__"}


# COMMENTS ARE STRIPPED BEFORE ANYTHING IS MATCHED, and this guard shipped
# without it while its twin `check-poster-box.py` did the same thing for the
# same reason on the same day.
#
# `press-arbitration.ts` carries the sentence « the interface passes through
# `feedback()` » in a comment above the real call. Delete the CALL and keep the
# sentence, and this guard read « 3 of 3 gestures passing » and exited 0 — the
# repository's own named trap, which the compositor guard paid for when five of
# thirteen `touch-action` sites turned out to be prose, two of them the sentence
# naming that guard.
#
# Blanked rather than removed, so a reported line number still points at the
# line the code is on.
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
LINE_COMMENT = re.compile(r"//[^\n]*")


def without_comments(body: str) -> str:
    """Blanks every comment, keeping the line structure.

    Args:
        body: A source file's text.

    Returns:
        The same text with comment bodies replaced by spaces.
    """
    blanked = BLOCK_COMMENT.sub(
        lambda found: re.sub(r"[^\n]", " ", found.group(0)), body)
    return LINE_COMMENT.sub(
        lambda found: " " * len(found.group(0)), blanked)


def sources() -> list[pathlib.Path]:
    """Every source under the prototype's tree, in a stable order.

    Returns:
        The paths, sorted.
    """
    found = []
    for path in sorted(DESIGN.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        if any(part in SKIP for part in path.parts):
            continue
        found.append(path)
    return found


def main() -> int:
    """Holds the seam's shape.

    Returns:
        0 when one module declares the seam and every named gesture uses it.
    """
    files = sources()
    violations = 0
    if len(files) < CORPUS_FLOOR:
        print(f"  check-feedback-seam: {len(files)} file(s) read under "
              f"{DESIGN.relative_to(ROOT)} — under the floor of {CORPUS_FLOOR}. "
              "A reader that has stopped reading refuses nothing and says so as "
              "« no violation ».", file=sys.stderr)
        violations += 1

    declaring = []
    for path in files:
        body = without_comments(
            path.read_text(encoding="utf-8", errors="replace"))
        if DECLARATION.search(body):
            declaring.append(str(path.relative_to(DESIGN)))

    if declaring != [SEAM]:
        violations += 1
        if not declaring:
            print("  no module declares `feedback` — the seam is gone, and "
                  "every gesture that called it is now silent.", file=sys.stderr)
        else:
            print(f"  `feedback` is declared in {len(declaring)} module(s): "
                  f"{', '.join(declaring)}. Exactly one may — a second "
                  "implementation works perfectly today and is a gesture that "
                  "stays mute the day haptics arrive (D9).", file=sys.stderr)

    passing = 0
    for what, where in sorted(GESTURES.items()):
        path = DESIGN / where
        if not path.exists():
            violations += 1
            print(f"  {where} is gone, and it arbitrated {what}. A gesture whose "
                  "file has moved is a gesture this guard stopped reading — "
                  "move the entry with it.", file=sys.stderr)
            continue
        body = without_comments(path.read_text(encoding="utf-8", errors="replace"))
        # The call, not the import, and not a COMMENT. Importing the name and
        # never calling it is the silence this holds against — and so is talking
        # about it.
        if re.search(r"\bfeedback\s*\(", body):
            passing += 1
            continue
        violations += 1
        print(f"  {where} arbitrates {what} and does not pass through "
              "`feedback()`. Every gesture goes through the seam, or adopting "
              "haptics stops being one file's change.", file=sys.stderr)

    print(f"check-feedback-seam: {len(files)} source(s) read under "
          f"{DESIGN.relative_to(ROOT)} (floor {CORPUS_FLOOR}), "
          f"{len(declaring)} implementation(s) of `feedback` (exactly 1 allowed), "
          f"{passing} of {len(GESTURES)} named gesture(s) passing through it, "
          f"{violations} violation(s)")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Motion's own half of the token guard — the durations AND the curves.

WHY IT IS A FILE. `check-css-tokens.py` stood at 905 non-blank lines against a
hard ceiling of 1 000 that exits 1, and B-059 is the record of what happens
when that slope is not watched: the same file crossed 1 000 twice inside L07
and the repository's own guard, not the wave's, is what stopped it.

The split follows a SUBJECT, the way `csstokens_login.py`'s did. Everything
here answers one question — is a motion value on the motion scale? — and a
motion value is written in two places that share nothing but that question: in
a CSS declaration (`transition: … 200ms var(--ease-standard)`), where the
duration is a number the scale arm counts and the CURVE is a shape no length
pattern could ever see; and inside a CLASS NAME (`duration-200`), where no
declaration exists at all and the scale arm is structurally blind.

`off_curve()` is called by the scale arm and `motion_classes_arm()` is an arm
in its own right. Imported by `check-css-tokens.py` and by nothing else.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Borrowed rather than restated, for the reason `csstokens_patterns.py` gives
# about its own three: a second copy of a value reader is a second thing to
# keep in step, and the first to drift would do so with both halves still
# reporting « no violation » about a value they were reading differently.
from csstokens_patterns import comma_segments

ROOT = Path(__file__).resolve().parent.parent


# ── The motion family's second dimension: the curve ──────────────────────────
# A duration is a number and the scale arm counts it. A CURVE is not: the
# scale holds two of them by name, and nothing below is a literal a length
# pattern could ever see. Left unheld, the family reports zero while a keyword
# easing, a copied bezier, or no easing at all sits in the sheet — which is
# exactly the state eight rules were found in, each rendering the browser's
# initial `ease` because nobody had written one.

# The two shorthands that let an easing be OMITTED. Their longhand siblings
# (`transition-duration`, `animation-delay`, `animation-name`) carry no timing
# function at all, so a missing curve there is the grammar, not an oversight.
TIMING_SHORTHAND = {"transition", "animation"}

# A duration term, however it is written. Its presence is what makes a segment
# a motion segment at all: `transition: none` and `animation: fadein` name no
# time and have no curve to answer for.
DURATION_TERM = re.compile(r"var\(\s*--duration-[\w-]+\s*[,)]|(?<![\w.])-?\d*\.?\d+m?s(?![\w-])")

# A curve read from the scale — the one shape that is ON it.
SCALE_EASING = re.compile(r"var\(\s*--ease-[\w-]+\s*[,)]")

# `linear`, and it is the ONE keyword the motion scale keeps. It is the loops'
# timing function: a spinner that eases stutters. It is exempt by name here for
# that reason and no other.
LINEAR_EASING = re.compile(r"(?<![\w-])linear(?![\w-])")

# The easing keywords CSS ships. Each is refused by name: they are four curves
# nobody chose, sitting beside two the scale declares.
KEYWORD_EASING = re.compile(r"(?<![\w-])(ease-in-out|ease-in|ease-out|ease)(?![\w-])")

# A curve written out rather than named. The two curves have names since the
# scale block landed, so a literal is a copy that stays behind the day the
# named one moves.
LITERAL_CURVE = re.compile(r"(?<![\w-])cubic-bezier\s*\([^)]*\)")

# A discrete timing function. There is not one in the stylesheet today, and
# that is precisely why it is REFUSED rather than exempted: an exemption for a
# shape with zero occurrences tolerates nothing and reads as foresight. The
# first `steps()` in this interface should be a decision someone signs, not a
# shape that matched a list written before there was anything to match.
DISCRETE_TIMING = re.compile(r"(?<![\w-])(steps\s*\([^)]*\)|step-start(?![\w-])|step-end(?![\w-]))")





# THE FOUR TOUCH-RESPONSE STEPS, AS TAILWIND SPELLS THEM. `--duration-*` is
# not a Tailwind namespace, and `duration-2` is ALREADY a utility meaning two
# milliseconds — so the one family of L06's scale that does not lift is also
# the only one that compiles to a WRONG VALUE instead of an error. Redefining
# the utility does not take the name back: the core one wins, measured. The
# operator arbitrated bare milliseconds (D-L07-3), and this arm is the half
# that makes the scale still a scale.
#
# NOTHING ELSE MEASURES THIS. `transition-duration` is not among the oracle's
# nineteen properties, and the scale arm above reads CSS DECLARATIONS — a value
# living inside a class name is invisible to it. `duration-137` would compile
# happily and no gate would say a word.
MOTION_STEPS = {"150": "--duration-1", "200": "--duration-2", "300": "--duration-3", "450": "--duration-4"}

# Where a class name may be written. The engine is excluded because it keeps
# hand-written CSS until L13 and receives no utility (D-L07-5) — and it is
# 34 000 lines whose prose would yield false candidates.
CLASS_SOURCES = (
    ROOT / "frontend" / "maquette" / "design" / "index.html",
    ROOT / "frontend" / "maquette" / "design" / "src" / "app",
    ROOT / "frontend" / "maquette" / "design" / "src" / "features",
    ROOT / "frontend" / "maquette" / "design" / "src" / "lib",
    ROOT / "frontend" / "maquette" / "design" / "src" / "routes",
    ROOT / "frontend" / "maquette" / "design" / "src" / "ui",
)

# A Tailwind duration utility as it is written in markup: an optional variant
# prefix (`hover:`, `motion-safe:`), the utility, a bare number, and a boundary.
# The arbitrary and custom-property forms — `duration-[…]`, `duration-(…)` —
# are NOT matched: they name a value explicitly and are somebody's deliberate
# choice, where a bare number is the shape that silently means milliseconds.
_DURATION_UTILITY = re.compile(r"(?<![\w-])duration-(\d+)(?![\w-])")


def off_curve(prop: str, value: str) -> list[str]:
    """Lists the ways a motion declaration's EASING sits outside the scale.

    Args:
        prop: The property name, lowercased by the caller.
        value: The declaration's value text, whitespace already collapsed.

    Returns:
        One phrase per finding, in the order they appear, ready to be joined
        into the same message the duration findings are named in. Empty when
        every term reads a named curve or `linear`.
    """
    findings: list[str] = []
    for segment in comma_segments(value):
        if not DURATION_TERM.search(segment):
            # No time named, so no curve is owed: `transition: none`, and the
            # `animation` shorthands that name only a keyframes rule.
            continue
        for found in KEYWORD_EASING.finditer(segment):
            findings.append(f"`{found.group(1)}` is not one of the two named curves")
        for found in LITERAL_CURVE.finditer(segment):
            findings.append(f"`{found.group(0)}` is a curve written out rather than named, and a copy nobody updates")
        for found in DISCRETE_TIMING.finditer(segment):
            findings.append(f"`{found.group(0)}` is a discrete timing function, and the motion scale holds none")
        if (
            prop in TIMING_SHORTHAND
            and not SCALE_EASING.search(segment)
            and not LINEAR_EASING.search(segment)
            and not KEYWORD_EASING.search(segment)
            and not LITERAL_CURVE.search(segment)
            and not DISCRETE_TIMING.search(segment)
        ):
            findings.append(
                f"`{' '.join(segment.split())}` names a duration and no "
                "easing at all, so it renders the browser's initial "
                "`ease` — a curve nobody chose"
            )
    # Two segments can be wrong the same way; naming it twice adds a line and
    # no information.
    return list(dict.fromkeys(findings))



def motion_classes_arm() -> int:
    """Refuses a `duration-<n>` outside the four arbitrated steps.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    files: list[Path] = []
    for source in CLASS_SOURCES:
        if source.is_dir():
            for pattern in ("*.tsx", "*.ts", "*.html"):
                files.extend(sorted(source.rglob(pattern)))
        elif source.exists():
            files.append(source)
    if not files:
        print(
            "check-motion: no source carries a class name — either the tree moved or this arm is reading nothing",
            file=sys.stderr,
        )
        return 1

    findings: list[str] = []
    seen = 0
    for path in files:
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), 1):
            for match in _DURATION_UTILITY.finditer(line):
                seen += 1
                value = match.group(1)
                if value not in MOTION_STEPS:
                    findings.append(
                        f"  {path.relative_to(ROOT)}:{number} — `duration-{value}` "
                        "is not a step. The motion scale is 150, 200, 300, 450 "
                        f"({', '.join(sorted(MOTION_STEPS))}); a fifth value is a "
                        "value outside the scale, and nothing else in this "
                        "repository would have caught it."
                    )
    if findings:
        print(f"check-motion: {len(findings)} off-scale duration(s).", file=sys.stderr)
        print("\n".join(findings), file=sys.stderr)
        return 1
    print(f"motion: {seen} duration utilitie(s) in {len(files)} source(s), every one a step.")
    return 0


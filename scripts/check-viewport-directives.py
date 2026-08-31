#!/usr/bin/env python3
"""Holds the viewport: the two directives refused, the one required, and the unit.

THE SUBJECT IS THE VIEWPORT, not one directive, and it widened twice. It began
as « refuses `maximum-scale` and `user-scalable=no` »; L12 added the directive
that is REQUIRED (`interactive-widget=resizes-content`, P17/B-234) and the
viewport UNIT the frame is sized in (`100dvh`, never `100vh`, P11). All three
are the same question — does this interface describe the viewport a phone
actually has — and splitting them across three files would have put the
answer in three places, which is how one of them goes stale unnoticed.

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

# P17 / B-234 — THE POSITIVE HALF. The two directives above are refused; this
# one is REQUIRED, and it is required of EVERY viewport meta rather than of one
# document.
#
# Without it a phone shrinks the VIEWPORT when the virtual keyboard opens, so a
# frame sized to the viewport is re-laid out under the finger while a field is
# focused: the layout jumps, and anything anchored to the bottom edge lands
# behind the keyboard. `resizes-content` leaves the viewport alone and resizes
# the content instead, which is what a native application does.
#
# WHY EVERY META AND NOT `index.html` ALONE, and this is B-230's lesson read
# forwards rather than backwards. That defect WAS a host with a different meta
# from the prototype's, and the tier that should have caught it could not,
# because it audits one document at a time. Fixing the prototype and leaving
# five hosts on the old spelling would make P17 half-true in a way no single
# file reveals — and the host that matters most is the SIGN-IN page, which is
# the one surface here that is nothing but a focused field.
REQUIRED = (
    "interactive-widget=resizes-content",
    re.compile(r"interactive\s*-\s*widget\s*=\s*resizes-content", re.IGNORECASE),
)

# A viewport meta, wherever it is written — in markup or in a Python host's
# string. Anything matching this must satisfy REQUIRED.
VIEWPORT_META = re.compile(r"""name\s*=\s*["']viewport["']""", re.IGNORECASE)

# How far past the meta's own position to look for the directive. The metas in
# this tree are written on one line in the hosts and across four in the
# prototype's markup, so a window rather than a line.
META_WINDOW = 400

# Six metas exist today — one in the prototype's markup, four in `serve.py`,
# one in `installable.py`. The floor refuses a reader that has stopped
# finding them: zero metas found would otherwise satisfy the arm above
# vacuously, which is B-085's shape written into a brand-new rule.
META_FLOOR = 6

# P11 — THE UNIT THE FRAME IS SIZED IN.
#
# `100vh` is the LARGE viewport by definition: the height the page has when the
# browser's own bars are retracted. A frame sized in it is taller than the space
# it actually has whenever a toolbar is showing, so the last row of a list sits
# underneath one. `100dvh` is the same number when nothing overlays and the
# right one when something does.
#
# `height: 100%` on the root has the same defect for the same reason — it
# resolves against the initial containing block, which is the large viewport —
# but it is not refused here: `100%` is a legitimate value everywhere else in a
# stylesheet, and a rule refusing it would refuse hundreds of correct uses to
# reach one. What is held instead is the POSITIVE: the frame declares `100dvh`,
# and if that declaration is ever removed this arm falls.
FORBIDDEN_UNIT = re.compile(r"\b\d+vh\b")
DYNAMIC_UNIT = re.compile(r"\b100dvh\b")

# `styles/harness.css` is the phone frame the oracle measures INSIDE. It is in
# the maquette's own build and in no production build, so its `100svh` is the
# apparatus and not the product — the same exemption the compositor guard makes
# for the same file, and for the same reason: an instrument may not satisfy, or
# violate, a property of the thing it measures.
UNIT_EXEMPT = {"styles/harness.css"}

# The frame declares it once, in `styles/base.css`. The floor is what makes the
# arm positive rather than merely absent-of-`vh`.
DVH_FLOOR = 1

# COMMENTS ARE BLANKED FOR THE UNIT ARM AND READ FOR THE DIRECTIVE ONE, and the
# asymmetry is deliberate rather than an oversight.
#
# A commented-out `maximum-scale` is one uncomment away from being live and
# nothing else explains it being written down, so the directive arm reads prose
# on purpose. A `vh` in a comment is almost always the OPPOSITE: a sentence
# explaining why the unit is refused. This arm caught its own explanation the
# first time it ran — the note in `base.css` saying « `100vh` is the trap this
# replaces » — which is exactly the shape the compositor guard paid for, where
# five of thirteen `touch-action` sites turned out to be prose, two of them the
# sentence naming that guard.
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


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
    metas_held = 0
    dynamic_units = 0
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
        for meta in VIEWPORT_META.finditer(body):
            window = body[meta.start():meta.start() + META_WINDOW]
            if REQUIRED[1].search(window):
                metas_held += 1
                continue
            line = body.count("\n", 0, meta.start()) + 1
            violations += 1
            print(
                f"  {path.relative_to(ROOT)}:{line}: a viewport meta that does "
                f"not declare « {REQUIRED[0]} » (P17, B-234). Without it the "
                "virtual keyboard shrinks the VIEWPORT, so a frame sized to it "
                "is re-laid out while a field is focused and anything anchored "
                "to the bottom edge lands behind the keyboard. Required of "
                "EVERY meta, not of one document: B-230 was a HOST whose meta "
                "differed from the prototype's, and a per-document audit could "
                "not see it.",
                file=sys.stderr,
            )
        if path.suffix != ".css" or any(
            str(path).endswith(name) for name in UNIT_EXEMPT
        ):
            continue
        # Blanked rather than removed, so a reported line number still points
        # at the line the declaration is actually on.
        code = CSS_COMMENT.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), body)
        dynamic_units += len(DYNAMIC_UNIT.findall(code))
        for found in FORBIDDEN_UNIT.finditer(code):
            line = code.count("\n", 0, found.start()) + 1
            violations += 1
            print(
                f"  {path.relative_to(ROOT)}:{line}: sizes in `vh` (P11). That "
                "is the LARGE viewport — the height the page has with the "
                "browser's bars retracted — so a frame sized in it is taller "
                "than the space it has whenever a toolbar shows, and the last "
                "row of a list sits under one. Use `dvh`.",
                file=sys.stderr,
            )
    # THE FLOORS ARE COUNTED BEFORE THE SUMMARY IS PRINTED, and the ordering is
    # the whole point. Written the other way round first, both floors fired on
    # stderr and set the exit code correctly while the summary line — the line a
    # human and a log actually read — still said « 0 violation(s) ». A guard
    # whose own report contradicts its verdict is B-085's shape inside a rule
    # written the same hour, and it was found by mutation rather than by
    # reading: the mutation removing the sizing looked like a rule that had not
    # bitten.
    if metas_held < META_FLOOR:
        print(
            f"  only {metas_held} viewport meta(s) found at all, under the "
            f"floor of {META_FLOOR} — the reader has stopped finding them, "
            "which is not the same as their being correct.",
            file=sys.stderr,
        )
        violations += 1
    if dynamic_units < DVH_FLOOR:
        print(
            f"  {dynamic_units} `100dvh` declaration(s), under the floor of "
            f"{DVH_FLOOR} — the frame has stopped declaring the dynamic "
            "viewport (P11). Refusing `vh` says nothing on its own: a "
            "stylesheet that sizes in nothing at all passes that half.",
            file=sys.stderr,
        )
        violations += 1
    print(
        f"check-viewport-directives: {len(files)} source file(s) read under "
        f"{MAQUETTE.relative_to(ROOT)} (floor {CORPUS_FLOOR}), {violations} "
        "violation(s) — neither `maximum-scale` nor a `user-scalable` refusal, "
        f"in markup, in script or in a stylesheet; and {metas_held} viewport "
        f"meta(s) declaring « {REQUIRED[0]} » (floor {META_FLOOR}). A positive "
        "arm that matched NOTHING reads exactly like one that passed, so the "
        "count is printed and floored rather than left to be inferred."
    )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Refuses the silent removal of a declaration the compositor reads.

Some CSS in the maquette is load-bearing rather than cosmetic, and a utility
conversion is exactly how it disappears without a sound. Deleting one selector
from a group once took the whole `user-drag: none` block with it: native image
drag came back, swallowed the pointer stream — one `pointerdown`, two
`pointermove`, never a `pointerup` — and three gesture holds failed for a reason
that looked nothing like a CSS deletion.

WHAT THIS READS, AND WHY IT IS NOT ONE FILE. During L07 these declarations move
out of a stylesheet and into component markup, as Tailwind utilities. A guard
that read only the stylesheet would report the whole inventory missing on the
first conversion, and — far worse — would report nothing at all once the
inventory had been rewritten to match. It therefore reads BOTH the stylesheets
and the component tree, and it understands the utility spellings as well as the
declarations: `touch-none` and `touch-action: none` are the same fact.

WHAT IT HOLDS. Three things, and none of them is a rewritable baseline:

    1. A per-property FLOOR. The number of sites for each property never falls
       below the manifest's figure. Lowering one is a one-line diff somebody
       has to justify in review — which is the whole difference between a
       ratchet and a record.
    2. THE NAMED BLOCK. The `user-drag` / `-webkit-touch-callout` group on the
       draggable images is required to exist by property AND value, wherever it
       lives. That is the incident above, written as a rule.
    3. EVERY `required` ENTRY CARRIES ITS REASON. A manifest entry with an
       empty `why` is itself a violation, the same shape as a `french-ok`
       pragma with no reason: an inventory nobody has to justify is an
       inventory nobody reads. The FLOORS carry theirs in the manifest's
       `taken_at` and `floors_note` rather than one per line — hold 3 reads
       `required`, and saying « every entry » of the whole file overstated it.

    AND NOTHING IS READ THROUGH A COMMENT. Every site below is found by
    searching text, so a sentence explaining a compositor declaration counted
    as one until 2026 — five of thirteen `touch-action` sites were prose, two
    of them the sentence naming this guard. Comments are blanked first, and
    `styles/harness.css` is out of the corpus: the instrument may not satisfy
    a floor the product no longer meets.

Exit code is the verdict: 0 when every hold passes, 1 naming what went missing.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "frontend" / "maquette" / "compositor-css.json"
DESIGN = ROOT / "frontend" / "maquette" / "design"

# The seven properties the compositor reads. `overscroll-behavior` is matched
# with its axis suffixes because `-y` is the spelling actually used, and
# `tap-highlight-color` is watched at a floor of ZERO: the prototype declares
# none, and a property absent from this tuple cannot be noticed the day one
# appears.
PROPERTIES = (
    "touch-action",
    "user-select",
    "user-drag",
    "overscroll-behavior",
    "touch-callout",
    "tap-highlight-color",
    "will-change",
)

# A CSS declaration, vendor prefix optional. The axis suffix of
# `overscroll-behavior` is folded onto the base name so a site counts the same
# whichever spelling it uses.
_DECLARATION = re.compile(
    r"(?:^|[;{\s])(?:-webkit-|-moz-|-ms-)?"
    r"(touch-action|user-select|user-drag|overscroll-behavior(?:-[xy])?"
    r"|touch-callout|tap-highlight-color|will-change)"
    r"\s*:\s*([^;}\n]+)"
)

# Tailwind's spellings of the same facts, plus the arbitrary-property escape
# hatch `[touch-action:none]`. Written out rather than derived, because a
# derivation would have to guess and a wrong guess here reads as "absent".
_UTILITIES = {
    "touch-auto": ("touch-action", "auto"),
    "touch-none": ("touch-action", "none"),
    "touch-pan-x": ("touch-action", "pan-x"),
    "touch-pan-y": ("touch-action", "pan-y"),
    "touch-manipulation": ("touch-action", "manipulation"),
    "select-none": ("user-select", "none"),
    "select-text": ("user-select", "text"),
    "select-auto": ("user-select", "auto"),
    "overscroll-none": ("overscroll-behavior", "none"),
    "overscroll-y-none": ("overscroll-behavior", "none"),
    "overscroll-x-none": ("overscroll-behavior", "none"),
    "overscroll-contain": ("overscroll-behavior", "contain"),
    "will-change-transform": ("will-change", "transform"),
    "will-change-scroll": ("will-change", "scroll-position"),
}
_ARBITRARY = re.compile(r"\[(-webkit-)?([a-z-]+):([^\]]+)\]")


def sources() -> list[pathlib.Path]:
    """Returns every file a compositor declaration may legitimately live in.

    Returns:
        The prototype fragment while it still exists, the shell document, the
        stylesheets of D3 once they do, and the whole component tree — minus
        the harness's own sheet, which is the instrument rather than the
        product. A path that does not exist is skipped rather than raising:
        this list spans the wave, and half of it does not exist when the wave
        opens.
    """
    found: list[pathlib.Path] = []
    for name in ("refonte.html", "index.html"):
        candidate = DESIGN / name
        if candidate.exists():
            found.append(candidate)
    for directory, patterns in ((DESIGN / "src", ("*.css", "*.tsx", "*.ts", "*.js")),):
        if not directory.exists():
            continue
        for pattern in patterns:
            found.extend(sorted(directory.rglob(pattern)))
    # THE INSTRUMENT IS NOT THE PRODUCT. `styles/harness.css` is the phone
    # frame and the measuring hides; a `touch-action` written there could
    # satisfy a floor the product no longer meets, which is the harness
    # certifying the thing it exists to measure. `common.py` draws the same
    # line around `engine/states.js` for the same reason.
    return [path for path in found if path.name not in _NOT_THE_PRODUCT]


# The instrument's own sources, excluded from the product's floors.
_NOT_THE_PRODUCT = {"harness.css"}

# A block comment, in CSS and in JS/TS alike.
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)

# A line comment, JS/TS only — `//` is not a comment in CSS, and a bare
# `https://` must not be mistaken for one, which is what the lookbehind on `:`
# refuses.
_LINE_COMMENT = re.compile(r"(?<!:)//[^\n]*")

_SCRIPT_SUFFIXES = {".ts", ".tsx", ".js", ".mjs"}


def _without_comments(text: str, suffix: str) -> str:
    """Blanks every comment while keeping the text's line numbering.

    THIS IS THE HOLD, NOT HOUSEKEEPING. Every site below is found by searching
    raw lines, so a sentence EXPLAINING a compositor declaration counts as one
    — and this file's subject is declarations whose absence is invisible, so a
    prose site is a floor met by its own documentation. Measured before the
    strip: five of thirteen `touch-action` sites were comments, two of them
    the sentence « `touch-none` is COMPOSITOR-FACING and held by this guard ».
    Deleting the one real `touch-action: none` in the tree then left the guard
    green, with the grab handle taking no compositor axis claim.

    The sibling Tailwind guard learned the same thing by mutation and says so
    in its own words: a guard that reads its own documentation as code is a
    guard that fails on being explained.

    Args:
        text: The file's contents.
        suffix: The file's extension, which decides whether `//` is a comment.

    Returns:
        The text with comment bodies replaced by spaces, newlines preserved so
        every reported line number still points where it did.
    """
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    text = _BLOCK_COMMENT.sub(blank, text)
    if suffix in _SCRIPT_SUFFIXES:
        text = _LINE_COMMENT.sub(blank, text)
    return text


def observed() -> dict[str, list[tuple[str, str, int]]]:
    """Collects every compositor-facing site across the design sources.

    Returns:
        A mapping of property name to the list of `(value, path, line)` sites
        found for it. Values are whitespace-normalised so `pan-x  pan-y` and
        `pan-x pan-y` are one fact.
    """
    sites: dict[str, list[tuple[str, str, int]]] = {name: [] for name in PROPERTIES}
    for path in sources():
        relative = str(path.relative_to(ROOT))
        text = _without_comments(path.read_text(encoding="utf-8"), path.suffix)
        for number, line in enumerate(text.splitlines(), 1):
            for match in _DECLARATION.finditer(line):
                prop = match.group(1)
                # Fold `overscroll-behavior-y` onto its base name.
                prop = "overscroll-behavior" if prop.startswith("overscroll") else prop
                value = " ".join(match.group(2).split()).rstrip(";").strip()
                sites[prop].append((value, relative, number))
            for utility, (prop, value) in _UTILITIES.items():
                # Word-bounded, so `touch-none` is not found inside
                # `group-touch-none-x` or a longer identifier.
                if re.search(rf"(?<![\w-]){re.escape(utility)}(?![\w-])", line):
                    sites[prop].append((value, relative, number))
            for match in _ARBITRARY.finditer(line):
                prop = match.group(2)
                prop = "overscroll-behavior" if prop.startswith("overscroll") else prop
                if prop in sites:
                    sites[prop].append((" ".join(match.group(3).split()), relative, number))
    return sites


def main() -> int:
    """Runs the three holds and prints the verdict.

    Returns:
        0 when every hold passes, 1 when any fails.
    """
    if not MANIFEST.exists():
        print(f"compositor guard: the manifest is missing at {MANIFEST}")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    sites = observed()
    failures: list[str] = []
    holds = 0

    # Hold 1 — the per-property floor.
    for prop, floor in sorted(manifest["floors"].items()):
        holds += 1
        count = len(sites.get(prop, ()))
        if count < floor:
            failures.append(
                f"  {prop}: {count} site(s), floor is {floor}. "
                "A declaration the compositor reads has gone missing — if that "
                "is deliberate, lower the floor in "
                "frontend/maquette/compositor-css.json and say why."
            )

    # Hold 2 — the named block, the one that has already gone off.
    for entry in manifest["required"]:
        holds += 1
        prop, value = entry["property"], entry["value"]
        if not any(found == value for found, _, _ in sites.get(prop, ())):
            failures.append(f"  {prop}: {value} is absent entirely. {entry['why']}")

    # Hold 3 — an entry with no reason is itself a violation.
    for entry in manifest["required"]:
        holds += 1
        if not entry.get("why", "").strip():
            failures.append(
                f"  {entry['property']}: the manifest entry carries no reason. "
                "An inventory nobody has to justify is an inventory nobody reads."
            )

    total = sum(len(found) for found in sites.values())
    if failures:
        print(f"compositor guard: {len(failures)} violation(s) over {holds} hold(s).")
        print("\n".join(failures))
        return 1
    print(
        f"compositor guard: {holds} hold(s), no violation — "
        f"{total} site(s) over {len(manifest['floors'])} propert"
        f"{'y' if len(manifest['floors']) == 1 else 'ies'}, "
        f"read across {len(sources())} design source(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

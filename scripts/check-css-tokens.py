#!/usr/bin/env python3
"""Refuses a `var()` the maquette's application CSS cannot resolve.

WHAT THIS CLOSES. `frontend/maquette/design/refonte.html` is split in two:
BLOCK 1 is the prototype harness — the phone frame, the demo bars, the design
notes — and BLOCK 2 is the application's own CSS, the stylesheet that BECOMES
the app's when the maquette replaces it (product-intent §15).

Every token BLOCK 2 uses must be declared in BLOCK 2. A `var()` resolved only
by a declaration sitting up in BLOCK 1 works today, inside the prototype, and
resolves to nothing the day BLOCK 1 stops shipping — which is the whole point
of the split. That is exactly the state this rule was written for: thirty-five
tokens used and ONE declared, across 458 `var()` calls.

WHAT COUNTS AS RESOLVED. The same block declares the custom property, OR it is
a RUNTIME token: `--tm-*` names are measured and published by script
(`design/src/engine/legacy.js`), never declared in CSS. Those must carry a
fallback at every use — a runtime token with no fallback resolves to nothing
until the script that sets it has run, which is a flash this rule also prevents.

A token declared ONLY under a conditional scope (a theme attribute, a media
condition) and used unconditionally is refused too: it renders correctly in the
one state someone happened to look at, and to nothing everywhere else.

THE SCALE ARM. `--arm scale` holds a second thing: every design constant BLOCK 2
spends is a STEP declared in the scale block, and nowhere else. It is a wall:
the first off-scale declaration is refused, by selector, property and literal,
with the step it sits nearest to so the reader can fold it in one edit.

It was a ratchet while the stylesheet was being folded onto the scale — a
recorded per-family count the arm refused to see rise, lowered fold by fold.
The last fold brought every family to zero, and a tolerance that tolerates
nothing is a tolerance waiting to be spent: the record and the mode that wrote
it are gone, and the floor is zero with no branch that can lift it. What
survived it is the pair of named exemptions below, which are measurements
rather than steps.

The motion family is held in TWO dimensions, because a curve is not a number
and a length pattern can never see one: the duration reads a step of the ramp,
AND the easing is one of the two the scale names. A keyword easing, a
`cubic-bezier(…)` written out beside the named one, and a transition that names
a duration and NO easing — which renders the browser's initial `ease`, a curve
nobody chose — are each refused, and a declaration wrong in both dimensions is
named in one message.

THE LOGIN ARM. `--arm login` holds the composition of the standalone sign-in
page, which `serve.py` builds by text search over `login:*` marked chunks rather
than by block. A chunk that uses a token no OTHER extracted chunk declares
resolves to nothing on the design host — a landmine, not a crash, because CSS
answers an unresolvable `var()` with silence. The set of chunks is read from
`serve.py`'s own `extract()` calls: what the files offer is not what the page
gets, and dropping a chunk from the composition is exactly how a page loses a
declaration it still uses.

Usage:
    python3 scripts/check-css-tokens.py          # every arm; exit 1 on any find
    python3 scripts/check-css-tokens.py --arm scale
    python3 scripts/check-css-tokens.py --arm login
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The four patterns both halves of this guard read a stylesheet with. They
# live in one module because the two must agree about what a comment is and
# what a `var()` use looks like — the first copy to drift would do so in
# silence, both halves still reporting « no violation ».
from csstokens_patterns import COMMENT, DECLARATION, HTML_COMMENT, RUNTIME_PREFIX, USE

ROOT = Path(__file__).resolve().parent.parent

# The maquette's own application CSS — BLOCK 2 of the prototype. It used to be
# the GENERATED copy under `frontend/src/styles/ps/`; that copy existed to carry
# the design into the shipped app surface by surface, a model the operator
# reversed. The maquette replaces the app, so the source is the subject.
FRAGMENT = ROOT / "frontend" / "maquette" / "design" / "refonte.html"

# The comment that opens the application half. The extractor used the same
# boundary, and reusing it is the point: a rule that disagreed with the file
# about where the application CSS begins would be measuring a third thing.
BLOCK_2 = "BLOCK 2"


# One top-level rule: its selector prelude, and its body.
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)

# The scope the extraction puts every selector under.
SCOPE = ".tm"

# The markup half of the prototype. The sign-in page's chunks are split across
# both files — the CSS chunks live in the stylesheet, the markup chunks here —
# and the composer reads both, so the arm that holds the composition must too.
MARKUP = ROOT / "frontend" / "maquette" / "design" / "index.html"

# The base layer (D3), which L07 moved out of the fragment's BLOCK 1. It holds
# the typeface and the reset the sign-in gate inherits, so it is a third source
# of the composition and not merely another stylesheet.
BASE_LAYER = ROOT / "frontend" / "maquette" / "design" / "src" / "styles" / "base.css"

# The token layer (D3), where L07 moved the scale. It is a Tailwind `@theme`
# block now rather than a `:root` one — the declarations between the markers
# are unchanged, which is what lets this arm read it the same way it always did.
THEME_LAYER = ROOT / "frontend" / "maquette" / "design" / "src" / "styles" / "theme.css"

# The residue (D-L07-5). It holds `login:style` and `login:splashstyle`: the
# sign-in screen and the splash belong to L13, so their CSS stays hand-written
# — which is what keeps the gate composable at all, since a page built by text
# extraction cannot receive utilities from a stylesheet it never loads.
LEGACY_LAYER = ROOT / "frontend" / "maquette" / "design" / "src" / "styles" / "legacy.css"

# The scale block's own markers. Its declarations ARE the steps, so the ratchet
# excludes the span before it counts anything: a scale that had to answer for
# itself would report nine violations the moment it was written.
SCALE_START = "/* scale:start */"
SCALE_END = "/* scale:end */"

# The families the scale answers for, keyed by the property names that spend a
# design constant. Longhands are matched by prefix (`padding-left`) and by the
# radius corners' suffix (`border-top-left-radius`); `scroll-padding` and plain
# `border` are NOT in the set, which is why the exact names are listed rather
# than a substring test used.
FAMILY_EXACT = {
    "padding": "spacing",
    "margin": "spacing",
    "gap": "spacing",
    "row-gap": "spacing",
    "column-gap": "spacing",
    "font-size": "text",
    # The `font` shorthand carries a size too, and reading `font-size` alone is
    # a hole the size of however many shorthands the stylesheet happens to hold:
    # four literals — two of them fractional — sat inside one while the text
    # family reported zero. Only its size term is measured; see
    # `font_shorthand_size`.
    "font": "text",
    "border-radius": "radius",
    "transition": "motion",
    "animation": "motion",
}
FAMILY_PREFIX = {
    "padding-": "spacing",
    "margin-": "spacing",
    "transition-": "motion",
    "animation-": "motion",
}
FAMILIES = ("spacing", "text", "radius", "motion")

# A declaration inside a rule body: its property and its value. Anchored the
# same way DECLARATION is, and for the same reason — `.tm{padding:0}` is valid
# CSS and anchoring to the start of a line alone would not see it.
BODY_DECLARATION = re.compile(r"(?:^|[{;])\s*([a-zA-Z-][\w-]*)\s*:\s*([^;}]*)", re.M)

# `var(` / `env(` as a function head. Their whole call is removed before a value
# is read for raw literals: a step read through `var()` is ON the scale, a
# runtime `var(--tm-…, 0px)` is a measurement rather than a design constant, and
# `env()` is a device inset. None of the three is something a scale can hold.
RESOLVED_CALL = re.compile(r"(?<![\w-])(?:var|env)\(")

# A raw length. `0` and `0px` are the absence of a step and are filtered by
# value, not by pattern. Percentages, `em`, bare numbers (line-height style) and
# the keywords `inherit` / `auto` never match: a relative unit is not a step.
LENGTH_LITERAL = re.compile(r"(?<![\w.])-?\d*\.?\d+px(?![\w-])")

# A raw duration. Easing keywords and `cubic-bezier(…)` do not match — the
# numbers inside a bezier carry no unit and are a curve's shape, not a step.
TIME_LITERAL = re.compile(r"(?<![\w.])-?\d*\.?\d+m?s(?![\w-])")

# ── The motion family's second dimension: the curve ──────────────────────────
# A duration is a number and the ratchet above counts it. A CURVE is not: the
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

# The `<font-size>` term of a `font` shorthand, with the `/ <line-height>` the
# grammar lets ride behind it. The terms that may precede it — style, variant,
# weight, stretch — are keywords or a bare number (`600`), so a value carrying a
# unit is the size and nothing else can be mistaken for it. The family list that
# follows carries no length at all. `font: inherit` matches nothing, which is
# the answer: a keyword is not a step.
FONT_SHORTHAND_SIZE = re.compile(
    r"(?<![\w.%/-])"
    r"(?:-?\d*\.?\d+(?:px|pt|em|rem|ex|ch|vh|vw|vmin|vmax|%)"
    r"|xx-small|x-small|small|medium|large|x-large|xx-large|smaller|larger)"
    r"(?:\s*/\s*[^\s,;]+)?"
)

# A step of the scale, by name. Tailwind v4's theme namespaces, so the block
# lifts into `@theme` without a rename when L07 lands.
SCALE_TOKEN = re.compile(r"^--(?:spacing|text|radius|duration|ease)-[\w-]+$")







# The constants `serve.py` reads its sources from, resolved to the files this
# arm already knows. A source it names and this table does not is refused
# rather than skipped: the composition measured would not be the one served.
#


# THE exemption list: the selectors the scale arm skips entirely, each with the
# reason it is not a step. There is no file to default from any more — these two
# were arbitrated, and an exemption can only join them by being written here, in
# a reviewed file, exactly as `regions.json`'s `$vocabulary` holds its frozen
# class names.
EXEMPTIONS = {
    ".dcard .cap": (
        "reserved footprint: the caption clears the floating add button; a measured clearance, not a space step"
    ),
    ".hero": (
        "hero overlap: the title is pulled up over the poster's melt — a "
        "composition measurement, not a space step (the rule's own comment "
        "says so)"
    ),
    # THE TWO BELOW ARE NOT ARBITRATIONS — they are DEBT this arm could not see
    # until it was widened, and they are exempted so it can go green over what
    # it CAN answer for while the two values wait for someone who may change
    # what the screen does. Both rules came out of the prototype's harness
    # block, which was never under the scale rule, and entered the shipped base
    # layer when that block was cut. B-066 holds the two off-scale values and
    # the reason the fix is not a call-site edit.
    ".visually-hidden": (
        "the one-pixel clip idiom: `width: 1px`, `height: 1px`, `margin: -1px` "
        "are the technique for hiding an element from sight and not from a "
        "screen reader — a measurement of the technique, not a space step, and "
        "no step of any ramp would do"
    ),
    ".skip-link": (
        "the accessibility skip link, off screen until focused. Its `16px` pad "
        "and `10px` radius are on no step (the ramps read 14 then 18, and 8 "
        "then 12), so honouring the scale would change what a keyboard user "
        "sees — a design change, not a token substitution. Recorded as B-066 "
        "rather than decided here"
    ),
}

# A step declaration inside the scale block: its name and its value. The scale
# is the only place these are read from, so the arm can name what a refused
# literal sits nearest to without a table of its own going stale beside it.
STEP_DECLARATION = re.compile(r"(?:^|[{;])\s*(--[\w-]+)\s*:\s*([^;}]*)", re.M)

# The scale's own namespaces, mapped to the family each answers for. `--ease-*`
# is deliberately absent: a curve is not a number and has no nearest anything.
STEP_FAMILY = {
    "--spacing-": "spacing",
    "--text-": "text",
    "--radius-": "radius",
    "--duration-": "motion",
}


def family_of(prop: str) -> str | None:
    """Names the scale family a CSS property spends a constant from.

    Args:
        prop: The property name as written, in any case.

    Returns:
        `spacing`, `text`, `radius`, `motion`, or `None` when the property
        spends no design constant the scale answers for.
    """
    name = prop.strip().lower()
    if name in FAMILY_EXACT:
        return FAMILY_EXACT[name]
    for prefix, family in FAMILY_PREFIX.items():
        if name.startswith(prefix):
            return family
    # `border-top-left-radius` and its three siblings: a corner is still a
    # radius, and folding three corners while leaving the fourth raw is exactly
    # the half-done state the ratchet exists to make visible.
    if name.startswith("border-") and name.endswith("-radius"):
        return "radius"
    return None


def without_resolved_functions(value: str) -> str:
    """Removes every `var()` and `env()` call, fallbacks included.

    A balanced-paren scan rather than a regex: `var(--x, calc(1px + 2px))`
    nests, and a non-nesting pattern would leave the fallback's literals behind
    and report a declaration that already reads a step.

    Args:
        value: A declaration's value text.

    Returns:
        The value with every resolved call replaced by a space.
    """
    kept: list[str] = []
    index = 0
    while index < len(value):
        head = RESOLVED_CALL.match(value, index)
        if head is None:
            kept.append(value[index])
            index += 1
            continue
        depth = 1
        cursor = head.end()
        while cursor < len(value) and depth:
            if value[cursor] == "(":
                depth += 1
            elif value[cursor] == ")":
                depth -= 1
            cursor += 1
        kept.append(" ")
        index = cursor
    return "".join(kept)


def raw_literals(value: str, family: str) -> list[str]:
    """Lists the raw design constants a value still carries.

    Args:
        value: A declaration's value text, as written.
        family: The scale family the declaration belongs to.

    Returns:
        Every literal that is on no step — empty when the declaration already
        reads the scale, is zero, or is a keyword or a relative unit.
    """
    remainder = without_resolved_functions(value)
    pattern = TIME_LITERAL if family == "motion" else LENGTH_LITERAL
    found: list[str] = []
    for literal in pattern.findall(remainder):
        number = literal.rstrip("pxms")
        # Zero is the absence of a step, not a step: `--spacing-0` would be a
        # token that means nothing and costs a lookup at every use.
        if float(number) != 0:
            found.append(literal)
    return found


def comma_segments(value: str) -> list[str]:
    """Splits a value on its TOP-LEVEL commas.

    `cubic-bezier(0.22, 0.61, 0.36, 1)` holds three commas of its own, so a
    plain `split(",")` would tear one transition into four and report a curve
    that has no duration beside it.

    Args:
        value: A declaration's value text.

    Returns:
        The comma-separated terms, each as written.
    """
    segments: list[str] = []
    current: list[str] = []
    depth = 0
    for character in value:
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        if character == "," and depth == 0:
            segments.append("".join(current))
            current = []
            continue
        current.append(character)
    segments.append("".join(current))
    return segments


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


def step_size(literal: str) -> float | None:
    """Reads a step's or a literal's magnitude, in pixels or in milliseconds.

    Args:
        literal: A raw length or duration, as written.

    Returns:
        The number, comparable within its family, or `None` for a unit this
        function does not measure — a step written in a relative unit has no
        pixel value and must not be offered as the nearest anything.
    """
    for suffix, factor in (("ms", 1.0), ("px", 1.0), ("s", 1000.0)):
        if literal.endswith(suffix):
            try:
                return float(literal[: -len(suffix)]) * factor
            except ValueError:
                return None
    return None


def nearest_step(literal: str, steps: list[tuple[str, str, float]]) -> str:
    """Names the step a refused literal sits nearest to.

    The next reader has to be able to fold the declaration without opening a
    plan or the scale block, so the refusal carries the step to fold it onto.
    A tie goes to the SMALLER step, deterministically: two names in one message
    would be an arbitration the message cannot make.

    Args:
        literal: The refused literal, as written.
        steps: The family's steps — name, value as declared, magnitude.

    Returns:
        The clause to append to the refusal, or an empty string when nothing
        comparable was found.
    """
    target = step_size(literal)
    if target is None or not steps:
        return ""
    name, written, _ = min(steps, key=lambda step: (abs(step[2] - target), step[2]))
    return f"; the nearest step is `{name}` ({written})"


def off_scale_findings(
    prop: str,
    value: str,
    family: str,
    steps: dict[str, list[tuple[str, str, float]]] | None = None,
) -> list[str]:
    """Names everything a declaration spends outside its family's scale.

    Args:
        prop: The property name as written, in any case.
        value: The declaration's value text, whitespace already collapsed.
        family: The scale family the declaration belongs to.
        steps: The scale's steps per family, when the caller has them. Omitted
            by the caller that only asks WHETHER a declaration is off-scale.

    Returns:
        One phrase per finding — the raw constants first, each with the step it
        is nearest to, then the curve findings the motion family alone can
        have. Empty when the declaration reads the scale.
    """
    findings: list[str] = []
    for literal in raw_literals(measurable_value(prop, value), family):
        findings.append(
            f"`{literal}` is on no step of the {family} scale" + nearest_step(literal, (steps or {}).get(family, []))
        )
    if family == "motion":
        findings.extend(off_curve(prop.strip().lower(), value))
    # The same literal twice in one value — `padding: 13px 13px` — is one
    # finding: naming it twice adds a line and no information.
    return list(dict.fromkeys(findings))


def font_shorthand_size(value: str) -> str:
    """Isolates the size a `font` shorthand sets, if it sets one.

    Args:
        value: The shorthand's value text, whitespace already collapsed.

    Returns:
        The `<font-size>` term with the `/ <line-height>` that may follow it, or
        an empty string when the shorthand names no size — `font: inherit`, or a
        size already read through `var()`, which the caller removes before the
        literals are counted anyway.
    """
    found = FONT_SHORTHAND_SIZE.search(value)
    return found.group(0) if found else ""


def measurable_value(prop: str, value: str) -> str:
    """Narrows a declaration's value to the part the scale answers for.

    Every property in the table spends its whole value on one family; `font` is
    the exception, because most of what it holds — the weight, the family list —
    is not a design constant and never was.

    Args:
        prop: The property name as written, in any case.
        value: The declaration's value text.

    Returns:
        The text whose literals the scale holds this declaration to.
    """
    if prop.strip().lower() == "font":
        return font_shorthand_size(value)
    return value


def declarations_by_scope(css: str) -> tuple[set[str], set[str]]:
    """Splits declared tokens by whether their scope is CONDITIONAL.

    A token declared only under `:root[data-theme="light"] .tm` exists only
    when that attribute is set. Counting it as « declared » lets an
    unconditional use resolve to nothing on every other theme — which is the
    same class of hole this whole rule exists to close, one level down.

    Args:
        css: The stylesheet, comments already stripped.

    Returns:
        `(unconditional, conditional)` — token names declared in a base scope,
        and token names declared only under a qualified one.
    """
    unconditional: set[str] = set()
    conditional: set[str] = set()
    for prelude, body in RULE.findall(css):
        # A prelude carries everything since the previous rule closed, which
        # includes any statement at-rule in between — `@import …;`, `@source
        # …;`. Splitting on `}` alone left those glued to the selector, so the
        # `@theme` block read as a long unrecognised string and its whole scale
        # was reported « conditional ». Cut on both terminators, in the order a
        # parser would.
        selector = prelude.strip().rsplit("}", 1)[-1].rsplit(";", 1)[-1].strip()
        names = {m for m in DECLARATION.findall("{" + body)}
        if not names:
            continue
        # Base scope: the scope class itself, or a bare document root. Anything
        # else — an attribute, a class, a media condition — is conditional, and
        # a token that only ever lands there is not available unconditionally.
        # `@theme` joined this set with L07. It is not a selector at all — it
        # is where Tailwind is told the scale, and it emits those declarations
        # into `:root`. Reading it as conditional would report the whole scale
        # as « declared only under a qualified scope », which is the opposite
        # of what it is.
        # `@theme` matched by its AT-RULE NAME, never by the whole prelude:
        # the block carries modifiers (`@theme static`, and `inline` exists
        # too), and an exact-string test silently reclassified the entire scale
        # as conditional the moment `static` was added.
        head = selector.split()[0] if selector else ""
        base = selector in {SCOPE, ":root", "html", "body"} or head == "@theme"
        (unconditional if base else conditional).update(names)
    # Declared in BOTH places is simply declared: the conditional block is then
    # an override, which is exactly what a theme is.
    return unconditional, conditional - unconditional


def unresolved(css: str) -> tuple[list[str], list[str], list[str]]:
    """Splits a stylesheet's `var()` uses into the three ways they can be wrong.

    Args:
        css: The stylesheet's text.

    Returns:
        `(undefined, conditional_only, runtime_without_fallback)` — names used
        but declared nowhere, names declared ONLY under a conditional scope,
        and runtime tokens used with no usable fallback.
    """
    css = COMMENT.sub(" ", css)
    unconditional, conditional = declarations_by_scope(css)
    undefined: set[str] = set()
    only_conditional: set[str] = set()
    bare_runtime: set[str] = set()
    for name, fallback in USE.findall(css):
        if name.startswith(RUNTIME_PREFIX):
            if fallback is None or not fallback.strip():
                bare_runtime.add(name)
        elif name in unconditional:
            continue
        elif name in conditional:
            only_conditional.add(name)
        else:
            undefined.add(name)
    return sorted(undefined), sorted(only_conditional), sorted(bare_runtime)


def block_two() -> str | None:
    """Slices BLOCK 2 out of the prototype, comments and all.

    One slicing for every arm: an arm that disagreed with the file about where
    the application CSS begins would be measuring a third thing.

    Returns:
        BLOCK 2's text, or `None` when the harness/application split is gone —
        in which case the caller has already been told why.
    """
    if not FRAGMENT.exists():
        print(
            f"check-css-tokens: {FRAGMENT} not found — the scope is empty, so "
            "a « no violation » here would mean nothing",
            file=sys.stderr,
        )
        return None

    whole = FRAGMENT.read_text(encoding="utf-8")
    start = whole.find("<style")
    end = whole.find("</style>", start)
    marker = whole.find(BLOCK_2, start) if start >= 0 else -1
    if start < 0 or end < 0 or marker < 0 or marker > end:
        print(
            "check-css-tokens: no <style> carrying BLOCK 2 in the maquette — "
            "the harness/application split is gone and this rule cannot tell "
            "them apart",
            file=sys.stderr,
        )
        return None
    return whole[whole.rfind("/*", start, marker) : end]


def application_stylesheet() -> str | None:
    """Returns every stylesheet the APPLICATION ships, concatenated.

    THE SUBJECT IS UNCHANGED AND THE FILES ARE NOT. This arm has always asked
    one question: does the application's own CSS resolve every `var()` it uses
    ON ITS OWN, once the prototype's harness stops shipping? That used to be
    `refonte.html`'s BLOCK 2 and nothing else. Since L07 the application's CSS
    is FOUR files — the tokens, the base layer, the residue, and what is left
    of BLOCK 2 — and reading only the last of them reported the entire scale as
    dangling the moment it moved into `@theme`.

    Widening the read is therefore the opposite of relaxing the arm: a token
    declared in a file that does NOT ship would still be counted missing,
    because these three are named one by one rather than globbed.

    Returns:
        The concatenation, joined by a newline so no pattern matches across the
        seam between two files, or `None` when BLOCK 2 cannot be located — the
        failure that must stay loud.
    """
    fragment = block_two()
    if fragment is None:
        return None
    parts = [fragment]
    # THE RESIDUE SHIPS, so its `var()` calls must resolve like any other. It
    # joined this list when L07 emptied BLOCK 2: 462 of the uses this arm was
    # written to check had moved into it, and a scope that empties makes « no
    # violation » mean nothing — which is what the guard's own test says.
    for path in (THEME_LAYER, BASE_LAYER, LEGACY_LAYER):
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def token_arm() -> int:
    """Reads the generated sheet and reports every `var()` it cannot resolve.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    css = application_stylesheet()
    if css is None:
        return 1
    stripped = COMMENT.sub(" ", css)
    used = {name for name, _ in USE.findall(stripped)}
    declared = set(DECLARATION.findall(stripped))
    undefined, only_conditional, bare_runtime = unresolved(css)

    if not used:
        print(
            "check-css-tokens: the sheet uses no `var()` at all — either the "
            "extraction broke or this rule is reading the wrong file",
            file=sys.stderr,
        )
        return 1

    for name in undefined:
        print(
            f"  {name} is used and declared in none of the stylesheets that "
            "ship — it resolves to nothing the day the harness sheet stops "
            "shipping. Declare it in `src/styles/theme.css`, beside the "
            "tokens, or drop the use. (Telling the reader to « declare it in "
            "BLOCK 2 » is what this message said until 2026: BLOCK 2 must now "
            "hold no rule at all, so the instruction pointed at the one place "
            "the declaration may not go.)",
            file=sys.stderr,
        )
    for name in only_conditional:
        print(
            f"  {name} is declared ONLY under a conditional scope (a theme "
            "attribute, a media condition) and used unconditionally — on "
            "every other condition it resolves to nothing. Declare it in the "
            "base scope too.",
            file=sys.stderr,
        )
    for name in bare_runtime:
        print(
            f"  {name} is a runtime token used with NO fallback — it resolves "
            "to nothing until the script that publishes it has run. Write "
            f"`var({name}, <default>)`.",
            file=sys.stderr,
        )

    if undefined or only_conditional or bare_runtime:
        print(
            f"\ncheck-css-tokens: "
            f"{len(undefined) + len(only_conditional) + len(bare_runtime)} "
            "unresolved token(s) in the application's stylesheet.",
            file=sys.stderr,
        )
        return 1

    # NAMED IN FULL, and the list is the one `application_stylesheet()` reads.
    # It said « theme.css, base.css » while reading three, which understates
    # what a green run covers — and a reader who trusts the line would look for
    # the residue's own tokens somewhere else entirely.
    shipped = ", ".join(
        name for name, path in (
            ("theme.css", THEME_LAYER), ("base.css", BASE_LAYER), ("legacy.css", LEGACY_LAYER),
        ) if path.exists()
    )
    print(
        f"check-css-tokens: the application's stylesheet "
        f"({FRAGMENT.name} BLOCK 2{', ' + shipped if shipped else ''}) — "
        f"{len(used)} token(s) used, {len(declared)} declared, "
        "no unresolved `var()`."
    )
    return 0


def scale_steps(block: str) -> dict[str, list[tuple[str, str, float]]]:
    """Reads the steps the scale block declares, per family.

    Args:
        block: The scale block's text, comments included.

    Returns:
        Name, value as declared and comparable magnitude, keyed by family. A
        family the block declares nothing for is present and empty, so a
        refusal simply carries no nearest step rather than crashing.
    """
    steps: dict[str, list[tuple[str, str, float]]] = {family: [] for family in FAMILIES}
    for name, value in STEP_DECLARATION.findall(COMMENT.sub(" ", block)):
        family = next((f for prefix, f in STEP_FAMILY.items() if name.startswith(prefix)), None)
        if family is None:
            continue
        pattern = TIME_LITERAL if family == "motion" else LENGTH_LITERAL
        found = pattern.search(value)
        if found is None:
            continue
        size = step_size(found.group(0))
        if size is not None:
            steps[family].append((name, found.group(0), size))
    return steps


def scale_measurement(
    exemptions: dict[str, str],
) -> (
    tuple[
        dict[str, list[tuple[str, str, str]]],
        list[str],
        dict[str, list[tuple[str, str, float]]],
    ]
    | None
):
    """Counts what the shipped stylesheets spend outside the scale, and where.

    The scale block is cut out BEFORE comments are stripped, in that order and
    not the other: its markers are comments, and a strip-first reading would
    lose the boundary and then hold the scale to answer for itself.

    Args:
        exemptions: Selectors to skip entirely, keyed by selector.

    Returns:
        `(inventory, duplicated, steps)` — the off-scale declarations per
        family, the scale tokens declared outside the scale block, and the
        steps the block declares. `None` when the scale block could not be
        located, or when the shipped stylesheets declare no rule at all.
    """
    # THE STEPS AND WHAT SPENDS THEM NOW LIVE IN DIFFERENT FILES. The scale is
    # a Tailwind `@theme` block in `src/styles/theme.css` rather than a `:root`
    # one. This arm therefore reads two places instead of partitioning one —
    # and it still refuses to run when the block is absent, because an arm that
    # cannot find the scale would otherwise measure every declaration against
    # an empty set of steps and call the result « no violation ».
    if not THEME_LAYER.exists():
        print(
            f"check-scale: {THEME_LAYER} not found — the scale has no home, so this arm has nothing to measure against",
            file=sys.stderr,
        )
        return None
    theme = THEME_LAYER.read_text(encoding="utf-8")
    _, marker, rest = theme.partition(SCALE_START)
    if not marker:
        print(
            f"check-scale: no {SCALE_START} in {THEME_LAYER.name} — the "
            "scale has no home, so this arm has nothing to measure against",
            file=sys.stderr,
        )
        return None
    block, closing, after = rest.partition(SCALE_END)
    if not closing:
        print(
            f"check-scale: {SCALE_START} is never closed by {SCALE_END} — the "
            "arm cannot tell the steps apart from what spends them",
            file=sys.stderr,
        )
        return None

    # WHAT SPENDS THE STEPS IS EVERY STYLESHEET THAT SHIPS, MINUS THE SCALE
    # ITSELF. Reading one file was right while that file held every rule; it
    # stopped being right the moment the rules moved out of it, and a scope
    # that empties turns « no violation » into « nothing was read ». The same
    # correction the token arm already carries, made in the same shape: the
    # files are NAMED one by one, never globbed, so a stylesheet that does not
    # ship cannot quietly join the measurement — which is why the harness sheet
    # is absent from `application_stylesheet()` and absent here.
    #
    # The scale block is cut out before anything is measured. Left in, every
    # step would read as a scale token declared outside the scale — the very
    # duplicate the hold below exists to name.
    spending = application_stylesheet()
    if spending is None:
        return None
    spending = spending.replace(marker + block + closing, "\n")
    outside = COMMENT.sub(" ", spending)

    # AND IT REFUSES AN EMPTY READ, which is the failure this widening repairs.
    # A measurement over text that declares nothing is not « every declaration
    # reads a step »; it is an arm that looked at nothing and said so as
    # success.
    if not RULE.findall(outside):
        print(
            "check-scale: the shipped stylesheets declare no rule at all — "
            "this arm measured nothing rather than finding nothing",
            file=sys.stderr,
        )
        return None

    inventory: dict[str, list[tuple[str, str, str]]] = {family: [] for family in FAMILIES}
    for prelude, body in RULE.findall(outside):
        # Stripped the way declarations_by_scope strips it — the closing brace
        # of an enclosing at-rule rides the next prelude, and one selector text
        # keeps the two readings comparable.
        selector = " ".join(prelude.strip().rsplit("}", 1)[-1].split())
        if selector in exemptions:
            continue
        for prop, value in BODY_DECLARATION.findall("{" + body):
            family = family_of(prop)
            if family is None:
                continue
            text = " ".join(value.split())
            if off_scale_findings(prop, text, family):
                inventory[family].append((selector, prop.strip().lower(), text))

    duplicated = sorted({name for name in DECLARATION.findall(outside) if SCALE_TOKEN.match(name)})
    return inventory, duplicated, scale_steps(block)


def scale_arm() -> int:
    """Refuses a design constant that is on no step, and a scale declared twice.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    measured = scale_measurement(EXEMPTIONS)
    if measured is None:
        return 1
    inventory, duplicated, steps = measured

    failed = False
    for name in duplicated:
        print(
            f"  scale: {name} is declared in two places; one block, or the next reader edits the copy nobody reads.",
            file=sys.stderr,
        )
        failed = True

    off_scale = 0
    for family in FAMILIES:
        for triple in sorted(dict.fromkeys(inventory[family])):
            selector, prop, value = triple
            # ONE message per declaration, however many ways it is wrong: a
            # motion declaration off the ramp AND off the curve is one edit,
            # and two messages would have the reader fix half of it.
            findings = ", and ".join(off_scale_findings(prop, value, family, steps))
            print(f"  `{selector}` `{prop}: {value}` — {findings}", file=sys.stderr)
            off_scale += 1

    if off_scale:
        print(
            f"\nscale: {off_scale} declaration(s) outside the scale — every design "
            "constant the shipped stylesheets spend is a step declared in the "
            "scale block, and there is no floor above zero.",
            file=sys.stderr,
        )
    if failed or off_scale:
        return 1

    print("scale: " + ", ".join(f"{family} 0" for family in FAMILIES) + " — every declaration reads a step.")
    return 0




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


from csstokens_login import login_arm  # noqa: E402


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


def main() -> int:
    """Runs the arm asked for, or every arm when none is.

    Returns:
        1 when any arm found something, 0 otherwise.
    """
    parser = argparse.ArgumentParser(
        description="Holds the maquette's application CSS to the tokens it can resolve, "
        "the steps it declares, and the chunks the sign-in page is composed from."
    )
    parser.add_argument(
        "--arm", choices=("scale", "login", "motion-classes"), help="run one arm alone; the default runs all of them"
    )
    args = parser.parse_args()

    if args.arm == "scale":
        return scale_arm()
    if args.arm == "login":
        return login_arm()
    if args.arm == "motion-classes":
        return motion_classes_arm()
    # Every arm runs, even after one has failed: a reader who has to fix and
    # re-run to discover the second finding fixes one thing per round trip.
    verdicts = [token_arm(), scale_arm(), login_arm(), motion_classes_arm()]
    return 1 if any(verdicts) else 0


if __name__ == "__main__":
    raise SystemExit(main())

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

# Tokens published at RUNTIME by script rather than declared in CSS. The prefix
# is the contract, and it is narrow on purpose: a name that merely happens to be
# missing must not be able to join this set by being renamed.
RUNTIME_PREFIX = "--tm-"

# Comments are stripped before anything is read: a declaration commented OUT
# used to satisfy a use, and `var(/*c*/--x)` used to be invisible. Both were
# found by an adversarial review, and both are the same mistake — reading CSS
# as text rather than as CSS.
COMMENT = re.compile(r"/\*.*?\*/", re.S)

# The document's own comment syntax. The sign-in page is composed from CSS AND
# markup chunks, so the arm that reads the composition meets both.
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

# A declaration may open a line, or follow `{` or `;` on one. Anchoring to the
# start of a line alone refused `.tm{--x:red}`, which is valid CSS.
DECLARATION = re.compile(r"(?:^|[{;])\s*(--[\w-]+)\s*:", re.M)

# `var(--x)` and `var(--x, fallback)`. The fallback is captured, not merely
# detected: `var(--tm-h,)` carries a comma and nothing after it, and resolves
# to exactly as much as no fallback at all.
USE = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,([^)]*))?\)")

# One top-level rule: its selector prelude, and its body.
RULE = re.compile(r"([^{}]+)\{([^{}]*)\}", re.S)

# The scope the extraction puts every selector under.
SCOPE = ".tm"

# The markup half of the prototype. The sign-in page's chunks are split across
# both files — the CSS chunks live in the stylesheet, the markup chunks here —
# and the composer reads both, so the arm that holds the composition must too.
MARKUP = ROOT / "frontend" / "maquette" / "design" / "index.html"

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
DURATION_TERM = re.compile(
    r"var\(\s*--duration-[\w-]+\s*[,)]|(?<![\w.])-?\d*\.?\d+m?s(?![\w-])")

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
DISCRETE_TIMING = re.compile(
    r"(?<![\w-])(steps\s*\([^)]*\)|step-start(?![\w-])|step-end(?![\w-]))")

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

# The composer itself. The sign-in page is whatever IT extracts — a chunk the
# files offer and `serve.py` never asks for is not on the page, so the arm reads
# the composition rather than the markers.
COMPOSER = ROOT / "frontend" / "maquette" / "serve.py"

# `styles_source = PROTOTYPE.read_text()`: the local name an `extract()` call
# passes, bound to the constant that names the file it was read from.
SOURCE_BINDING = re.compile(r"(\w+)\s*=\s*(\w+)\.read_text\(")

# `extract(styles_source, "scale")`. The second argument is quoted, so the
# `def extract(source: str, marker: str)` line is not a call and does not match.
EXTRACT_CALL = re.compile(r"\bextract\(\s*(\w+)\s*,\s*\"([\w-]+)\"\s*\)")

# The constants `serve.py` reads its two sources from, resolved to the files
# this arm already knows. A source it names and this table does not is refused
# rather than skipped: the composition measured would not be the one served.
SOURCE_FILES = {"PROTOTYPE": FRAGMENT, "SHELL_DOCUMENT": MARKUP}

# THE exemption list: the selectors the scale arm skips entirely, each with the
# reason it is not a step. There is no file to default from any more — these two
# were arbitrated, and an exemption can only join them by being written here, in
# a reviewed file, exactly as `regions.json`'s `$vocabulary` holds its frozen
# class names.
EXEMPTIONS = {
    ".dcard .cap": (
        "reserved footprint: the caption clears the floating add button; "
        "a measured clearance, not a space step"
    ),
    ".hero": (
        "hero overlap: the title is pulled up over the poster's melt — a "
        "composition measurement, not a space step (the rule's own comment "
        "says so)"
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
            findings.append(f"`{found.group(0)}` is a curve written out rather than "
                            "named, and a copy nobody updates")
        for found in DISCRETE_TIMING.finditer(segment):
            findings.append(f"`{found.group(0)}` is a discrete timing function, and "
                            "the motion scale holds none")
        if (prop in TIMING_SHORTHAND
                and not SCALE_EASING.search(segment)
                and not LINEAR_EASING.search(segment)
                and not KEYWORD_EASING.search(segment)
                and not LITERAL_CURVE.search(segment)
                and not DISCRETE_TIMING.search(segment)):
            findings.append(f"`{' '.join(segment.split())}` names a duration and no "
                            "easing at all, so it renders the browser's initial "
                            "`ease` — a curve nobody chose")
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
        findings.append(f"`{literal}` is on no step of the {family} scale"
                        + nearest_step(literal, (steps or {}).get(family, [])))
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
        selector = prelude.strip().rsplit("}", 1)[-1].strip()
        names = {m for m in DECLARATION.findall("{" + body)}
        if not names:
            continue
        # Base scope: the scope class itself, or a bare document root. Anything
        # else — an attribute, a class, a media condition — is conditional, and
        # a token that only ever lands there is not available unconditionally.
        base = selector in {SCOPE, ":root", "html", "body"}
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
        print(f"check-css-tokens: {FRAGMENT} not found — the scope is empty, so "
              "a « no violation » here would mean nothing", file=sys.stderr)
        return None

    whole = FRAGMENT.read_text(encoding="utf-8")
    start = whole.find("<style")
    end = whole.find("</style>", start)
    marker = whole.find(BLOCK_2, start) if start >= 0 else -1
    if start < 0 or end < 0 or marker < 0 or marker > end:
        print("check-css-tokens: no <style> carrying BLOCK 2 in the maquette — "
              "the harness/application split is gone and this rule cannot tell "
              "them apart", file=sys.stderr)
        return None
    return whole[whole.rfind("/*", start, marker):end]


def token_arm() -> int:
    """Reads the generated sheet and reports every `var()` it cannot resolve.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    css = block_two()
    if css is None:
        return 1
    stripped = COMMENT.sub(" ", css)
    used = {name for name, _ in USE.findall(stripped)}
    declared = set(DECLARATION.findall(stripped))
    undefined, only_conditional, bare_runtime = unresolved(css)

    if not used:
        print("check-css-tokens: the sheet uses no `var()` at all — either the "
              "extraction broke or this rule is reading the wrong file",
              file=sys.stderr)
        return 1

    for name in undefined:
        print(f"  {name} is used and declared nowhere in {FRAGMENT.name} BLOCK 2 — it "
              "resolves to nothing the day BLOCK 1 stops shipping. Declare it "
              "in BLOCK 2, beside the rules that use it, or drop the use.", file=sys.stderr)
    for name in only_conditional:
        print(f"  {name} is declared ONLY under a conditional scope (a theme "
              "attribute, a media condition) and used unconditionally — on "
              "every other condition it resolves to nothing. Declare it in the "
              "base scope too.", file=sys.stderr)
    for name in bare_runtime:
        print(f"  {name} is a runtime token used with NO fallback — it resolves "
              "to nothing until the script that publishes it has run. Write "
              f"`var({name}, <default>)`.", file=sys.stderr)

    if undefined or only_conditional or bare_runtime:
        print(f"\ncheck-css-tokens: "
              f"{len(undefined) + len(only_conditional) + len(bare_runtime)} "
              f"unresolved token(s) in {FRAGMENT.name} BLOCK 2.", file=sys.stderr)
        return 1

    print(f"check-css-tokens: {FRAGMENT.name} BLOCK 2 — {len(used)} token(s) used, "
          f"{len(declared)} declared, no unresolved `var()`.")
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
) -> tuple[
    dict[str, list[tuple[str, str, str]]],
    list[str],
    dict[str, list[tuple[str, str, float]]],
] | None:
    """Counts what BLOCK 2 still spends outside the scale, and where.

    The scale block is cut out BEFORE comments are stripped, in that order and
    not the other: its markers are comments, and a strip-first reading would
    lose the boundary and then hold the scale to answer for itself.

    Args:
        exemptions: Selectors to skip entirely, keyed by selector.

    Returns:
        `(inventory, duplicated, steps)` — the off-scale declarations per
        family, the scale tokens declared outside the scale block, and the
        steps the block declares. `None` when BLOCK 2 or the scale block could
        not be located.
    """
    css = block_two()
    if css is None:
        return None
    head, marker, rest = css.partition(SCALE_START)
    if not marker:
        print(f"check-scale: no {SCALE_START} in {FRAGMENT.name} BLOCK 2 — the "
              "scale has no home, so this arm has nothing to measure against",
              file=sys.stderr)
        return None
    block, closing, tail = rest.partition(SCALE_END)
    if not closing:
        print(f"check-scale: {SCALE_START} is never closed by {SCALE_END} — the "
              "arm cannot tell the steps apart from what spends them",
              file=sys.stderr)
        return None
    outside = COMMENT.sub(" ", head + tail)

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
        print(f"  scale: {name} is declared in two places; one block, or the next "
              "reader edits the copy nobody reads.", file=sys.stderr)
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
        print(f"\nscale: {off_scale} declaration(s) outside the scale — every design "
              "constant BLOCK 2 spends is a step declared in the scale block, and "
              "there is no floor above zero.", file=sys.stderr)
    if failed or off_scale:
        return 1

    print("scale: " + ", ".join(f"{family} 0" for family in FAMILIES)
          + " — every declaration reads a step.")
    return 0


def without_python_comments(source: str) -> str:
    """Blanks out `#` comments, quotes respected.

    A commented-out `extract()` call composes nothing, and an arm that counted
    it would report a chunk the page never receives. A naive per-line split on
    `#` would also cut a line at a `#` inside a string literal, so the scan
    tracks the quote it is in.

    Args:
        source: Python source text.

    Returns:
        The same text with every comment replaced by spaces, line breaks kept
        so a reader can still map a match back to a line.
    """
    kept: list[str] = []
    quote = ""
    index = 0
    while index < len(source):
        char = source[index]
        if quote:
            kept.append(char)
            if char == "\\" and index + 1 < len(source):
                kept.append(source[index + 1])
                index += 2
                continue
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
            kept.append(char)
        elif char == "#":
            end = source.find("\n", index)
            end = len(source) if end < 0 else end
            kept.append(" " * (end - index))
            index = end
            continue
        else:
            kept.append(char)
        index += 1
    return "".join(kept)


def composed_chunks() -> dict[str, str] | None:
    """Collects the chunks `serve.py` actually composes the sign-in page from.

    The set is read from the composer rather than from the markers: a chunk the
    files offer and `serve.py` never extracts is not on the page, and holding
    the page to it would report a token the browser is in fact given. Which
    file each chunk comes from is read the same way — `serve.py` binds its two
    sources by name, and this follows the binding rather than guessing.

    Returns:
        Chunk text keyed by chunk name, or `None` when the composer cannot be
        read, names a source this arm cannot resolve, or extracts a chunk whose
        markers are missing — the same failure `extract()` itself raises on.
    """
    if not COMPOSER.exists():
        print(f"check-login: {COMPOSER} not found — the composition cannot be "
              "read, so a « no violation » here would mean nothing", file=sys.stderr)
        return None
    composer = without_python_comments(COMPOSER.read_text(encoding="utf-8"))

    # `styles_source = PROTOTYPE.read_text()` and its sibling: the local name an
    # `extract()` call passes, bound to the constant that names the file.
    bound = {local: constant for local, constant in SOURCE_BINDING.findall(composer)}
    calls = EXTRACT_CALL.findall(composer)
    if not calls:
        print(f"check-login: no `extract(<source>, \"<chunk>\")` call in "
              f"{COMPOSER.name} — an arm that reads zero chunks holds nothing",
              file=sys.stderr)
        return None

    texts: dict[Path, str] = {}
    chunks: dict[str, str] = {}
    for local, name in calls:
        path = SOURCE_FILES.get(bound.get(local, ""))
        if path is None:
            print(f"  login: {COMPOSER.name} extracts login:{name} from `{local}`, "
                  "which this arm cannot resolve to a file — the composition it "
                  "measures would not be the one served.", file=sys.stderr)
            return None
        if not path.exists():
            print(f"check-login: {path} not found — the composed page cannot be "
                  "read, so a « no violation » here would mean nothing", file=sys.stderr)
            return None
        if name in chunks:
            continue
        text = texts.setdefault(path, path.read_text(encoding="utf-8"))
        start = text.find(f"login:{name}:start")
        end = text.find(f"login:{name}:end")
        if start < 0 or end < 0 or end < start:
            print(f"  login: {COMPOSER.name} extracts login:{name} from "
                  f"{path.name}, which carries no such marker pair — `extract()` "
                  "raises on this and serves no sign-in page at all.", file=sys.stderr)
            return None
        # The same slicing serve.extract() uses, deliberately: an arm that read
        # one character more than the composer would hold a chunk the page
        # never receives.
        chunks[name] = text[text.index("\n", start) + 1: text.rindex("\n", start, end) + 1]
    return chunks


def login_arm() -> int:
    """Refuses a token the composed sign-in page uses but is never given.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    chunks = composed_chunks()
    if chunks is None:
        return 1

    # Both comment syntaxes: the CSS chunks live in a <style>, the markup chunks
    # in the document. A declaration commented out in either satisfied nothing.
    composed = COMMENT.sub(" ", "\n".join(chunks.values()))
    composed = HTML_COMMENT.sub(" ", composed)
    declared = set(DECLARATION.findall(composed))
    used: set[str] = set()
    missing: set[str] = set()
    for name, fallback in USE.findall(composed):
        used.add(name)
        # A runtime token carrying a usable fallback is not owed a declaration:
        # nothing declares `--tm-*` in CSS, the shell publishes it, and the
        # fallback is what the page renders with until it has.
        if name.startswith(RUNTIME_PREFIX) and fallback.strip():
            continue
        if name not in declared:
            missing.add(name)

    for name in sorted(missing):
        print(f"  login: {name} is used by the composed sign-in page but declared "
              "in no chunk serve.py composes — the page is not given it, and "
              "resolves it to nothing.", file=sys.stderr)
    if missing:
        return 1

    print(f"login: {len(used)} var() use(s) in the composed chunks, all declared there.")
    return 0


def main() -> int:
    """Runs the arm asked for, or every arm when none is.

    Returns:
        1 when any arm found something, 0 otherwise.
    """
    parser = argparse.ArgumentParser(
        description="Holds the maquette's application CSS to the tokens it can resolve, "
                    "the steps it declares, and the chunks the sign-in page is composed from.")
    parser.add_argument("--arm", choices=("scale", "login"),
                        help="run one arm alone; the default runs all of them")
    args = parser.parse_args()

    if args.arm == "scale":
        return scale_arm()
    if args.arm == "login":
        return login_arm()
    # Every arm runs, even after one has failed: a reader who has to fix and
    # re-run to discover the second finding fixes one thing per round trip.
    verdicts = [token_arm(), scale_arm(), login_arm()]
    return 1 if any(verdicts) else 0


if __name__ == "__main__":
    raise SystemExit(main())

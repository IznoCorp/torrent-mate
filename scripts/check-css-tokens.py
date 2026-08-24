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
spends is a STEP declared in the scale block, and nowhere else. It is a ratchet
rather than a wall — `frontend/maquette/scale-baseline.json` records what sits
outside the scale today, the arm refuses that count going UP, and the folding
phases lower it. The baseline is deleted when the last fold lands, and the arm
then refuses the first off-scale declaration outright.

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
    python3 scripts/check-css-tokens.py --record-scale-baseline
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
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

# The ratchet's memory: what sits outside the scale today, per family, and the
# commit it was taken at. A tolerance, not a target — phase 6 deletes it.
SCALE_BASELINE = ROOT / "frontend" / "maquette" / "scale-baseline.json"

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

# Selectors the ratchet skips entirely, each with the reason it is not a step.
# Seeded into the baseline at record time; the baseline is the authority
# afterwards, so an exemption can only be added by editing a reviewed file.
DEFAULT_EXEMPTIONS = {
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


def load_scale_baseline() -> dict[str, object] | None:
    """Reads the ratchet's baseline, when there still is one.

    Returns:
        The recorded inventory, or `None` once phase 6 has deleted the file —
        which is not an error but the end state: no tolerance left to grant.
    """
    if not SCALE_BASELINE.exists():
        return None
    return json.loads(SCALE_BASELINE.read_text(encoding="utf-8"))


def scale_measurement(
    exemptions: dict[str, str],
) -> tuple[dict[str, list[tuple[str, str, str]]], list[str]] | None:
    """Counts what BLOCK 2 still spends outside the scale, and where.

    The scale block is cut out BEFORE comments are stripped, in that order and
    not the other: its markers are comments, and a strip-first reading would
    lose the boundary and then hold the scale to answer for itself.

    Args:
        exemptions: Selectors to skip entirely, keyed by selector.

    Returns:
        `(inventory, duplicated)` — the off-scale declarations per family, and
        the scale tokens declared outside the scale block. `None` when BLOCK 2
        or the scale block could not be located.
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
    _, closing, tail = rest.partition(SCALE_END)
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
            if raw_literals(measurable_value(prop, text), family):
                inventory[family].append((selector, prop.strip().lower(), text))

    duplicated = sorted({name for name in DECLARATION.findall(outside) if SCALE_TOKEN.match(name)})
    return inventory, duplicated


def scale_arm() -> int:
    """Refuses a design constant that is on no step, and a scale declared twice.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    baseline = load_scale_baseline()
    exemptions: dict[str, str] = {}
    if baseline is not None:
        exemptions = dict(baseline.get("exemptions", {}))  # type: ignore[arg-type]
    measured = scale_measurement(exemptions)
    if measured is None:
        return 1
    inventory, duplicated = measured

    failed = False
    for name in duplicated:
        print(f"  scale: {name} is declared in two places; one block, or the next "
              "reader edits the copy nobody reads.", file=sys.stderr)
        failed = True

    recorded: dict[str, Counter[tuple[str, str, str]]] = {}
    if baseline is not None:
        families = baseline.get("families", {})
        for family in FAMILIES:
            rows = families.get(family, []) if isinstance(families, dict) else []
            recorded[family] = Counter(tuple(row) for row in rows)

    for family in FAMILIES:
        current = Counter(inventory[family])
        known = recorded.get(family, Counter())
        for triple in sorted(current):
            if current[triple] <= known[triple]:
                continue
            selector, prop, value = triple
            literals = raw_literals(measurable_value(prop, value), family)
            quoted = ", ".join(f"`{literal}`" for literal in literals)
            verb = "is" if len(literals) == 1 else "are"
            print(f"  `{selector}` `{prop}: {value}` — {quoted} {verb} on no step of "
                  f"the {family} scale", file=sys.stderr)
            failed = True

    if baseline is None:
        if failed or any(inventory[family] for family in FAMILIES):
            print("\nscale: no baseline tolerates an off-scale declaration any more "
                  "— every declaration reads a step.", file=sys.stderr)
            return 1
        print("scale: " + ", ".join(f"{family} 0" for family in FAMILIES)
              + " — every declaration reads a step.")
        return 0

    for family in FAMILIES:
        current = len(inventory[family])
        known = sum(recorded[family].values())
        if current > known:
            print(f"\nscale: the {family} count went UP against its baseline "
                  f"({current} > {known})", file=sys.stderr)
            failed = True
    if failed:
        return 1

    print("scale: " + ", ".join(
        f"{family} {len(inventory[family])}/{sum(recorded[family].values())}"
        for family in FAMILIES) + " — nothing new outside the scale.")
    return 0


def record_scale_baseline() -> int:
    """Writes the ratchet's baseline from the stylesheet as it stands.

    Returns:
        1 when the measurement or the commit could not be taken, 0 otherwise.
    """
    previous = load_scale_baseline()
    exemptions = DEFAULT_EXEMPTIONS
    if previous is not None:
        exemptions = dict(previous.get("exemptions", {}))  # type: ignore[arg-type]
    measured = scale_measurement(exemptions)
    if measured is None:
        return 1
    inventory, _ = measured

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True, check=False)
    if head.returncode != 0:
        # A baseline nobody can date is a baseline nobody can audit: the whole
        # point of the commit field is that a reader can replay the measurement.
        print("check-scale: `git rev-parse HEAD` failed, so the baseline would "
              "carry no provenance — refusing to write it", file=sys.stderr)
        return 1

    payload = {
        "commit": head.stdout.strip(),
        "exemptions": exemptions,
        "families": {family: [list(triple) for triple in inventory[family]]
                     for family in FAMILIES},
    }
    SCALE_BASELINE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                              encoding="utf-8")
    print(f"check-scale: recorded {SCALE_BASELINE.relative_to(ROOT)} at "
          f"{payload['commit'][:8]} — " + ", ".join(
              f"{family} {len(inventory[family])}" for family in FAMILIES)
          + f", {len(exemptions)} named exemption(s).")
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
    parser.add_argument("--record-scale-baseline", action="store_true",
                        help="rewrite the ratchet's baseline from the stylesheet as it stands")
    args = parser.parse_args()

    if args.record_scale_baseline:
        return record_scale_baseline()
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

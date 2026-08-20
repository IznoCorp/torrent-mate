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
tokens used and ONE declared, across 449 `var()` calls.

WHAT COUNTS AS RESOLVED. The same block declares the custom property, OR it is
a RUNTIME token: `--tm-*` names are measured and published by script
(`design/src/engine/legacy.js`), never declared in CSS. Those must carry a
fallback at every use — a runtime token with no fallback resolves to nothing
until the script that sets it has run, which is a flash this rule also prevents.

A token declared ONLY under a conditional scope (a theme attribute, a media
condition) and used unconditionally is refused too: it renders correctly in the
one state someone happened to look at, and to nothing everywhere else.

Usage:
    python3 scripts/check-css-tokens.py          # exit 1 on any unresolved var()
"""

from __future__ import annotations

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


def main() -> int:
    """Reads the generated sheet and reports every `var()` it cannot resolve.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    if not FRAGMENT.exists():
        print(f"check-css-tokens: {FRAGMENT} not found — the scope is empty, so "
              "a « no violation » here would mean nothing", file=sys.stderr)
        return 1

    whole = FRAGMENT.read_text(encoding="utf-8")
    start = whole.find("<style")
    end = whole.find("</style>", start)
    marker = whole.find(BLOCK_2, start) if start >= 0 else -1
    if start < 0 or end < 0 or marker < 0 or marker > end:
        print("check-css-tokens: no <style> carrying BLOCK 2 in the maquette — "
              "the harness/application split is gone and this rule cannot tell "
              "them apart", file=sys.stderr)
        return 1
    css = whole[whole.rfind("/*", start, marker):end]
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


if __name__ == "__main__":
    raise SystemExit(main())

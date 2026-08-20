#!/usr/bin/env python3
"""Refuses a `var()` the shipped stylesheet cannot resolve.

WHAT THIS CLOSES, AND WHY NOTHING ELSE COULD. Two guards already watch the
extracted stylesheet and neither can see this one:

  * `extract-maquette-css.py --check` compares the generated file against what
    the extractor emits. An extractor that emits a `var()` nobody defines
    agrees with itself perfectly.
  * `parity-probe.py` renders the same DOM twice, once dressed by the maquette
    and once by the extraction, and compares computed styles. It keeps BLOCK 1
    in the document for BOTH passes — its own comment says so, and it is right
    to: BLOCK 1 is the phone frame the prototype lives inside, and removing it
    would move every region for a reason that has nothing to do with the
    extraction. BLOCK 1 WAS where the tokens were declared, so during the probe
    they were in the room, and the probe reported no divergence over a sheet
    that would have resolved them to nothing anywhere else.

That is why this rule exists, and the past tense is deliberate: SP5a moved the
declarations into BLOCK 2, so the sheet now carries them and the probe does
exercise them. What has NOT changed is that the probe cannot be the guard —
put one declaration back in BLOCK 1 tomorrow and it would go green again.

The state this closed: the sheet that IS the redesign used thirty-five tokens
and declared ONE, under two green gates. That is the shape of B-014 — named,
and defined by nothing — and it was the material reason the redesign could not
simply be switched on.

WHAT COUNTS AS RESOLVED. A `var()` resolves when the same sheet declares the
custom property, OR when it is a RUNTIME token: `--tm-*` names are measured and
published by script (`frontend/src/components/layout/bottom-bar-metrics.ts`,
`design/src/engine/legacy.js`), never declared in CSS. Those are required to
carry a fallback at every use — a runtime token with no fallback resolves to
nothing before the script that sets it has run, which is the flash this rule
also exists to prevent.

Usage:
    python3 scripts/check-css-tokens.py          # exit 1 on any unresolved var()
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The generated stylesheet — the one the app would import the day the redesign
# ships. Nothing imports it yet, and that is the operator's decision; this rule
# makes sure that decision is not the moment the defects are discovered.
SHEET = ROOT / "frontend" / "src" / "styles" / "ps" / "app-surface.css"

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
    if not SHEET.exists():
        print(f"check-css-tokens: {SHEET} not found — the scope is empty, so a "
              "« no violation » here would mean nothing", file=sys.stderr)
        return 1

    css = SHEET.read_text(encoding="utf-8")
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
        print(f"  {name} is used and declared nowhere in {SHEET.name} — it "
              "resolves to nothing the day this sheet is imported. Declare it "
              "in the maquette's BLOCK 2 so the extraction carries it, or drop "
              "the use.", file=sys.stderr)
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
              f"unresolved token(s) in {SHEET.name}.", file=sys.stderr)
        return 1

    print(f"check-css-tokens: {SHEET.name} — {len(used)} token(s) used, "
          f"{len(declared)} declared, no unresolved `var()`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

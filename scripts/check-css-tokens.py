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
    extraction. But BLOCK 1 is where the tokens are DECLARED, so during the
    probe they are in the room, and the probe reports no divergence over a
    sheet that would resolve them to nothing anywhere else.

So the sheet that IS the redesign used thirty-five tokens and declared one,
across 444 `var()` calls, under two green gates. That is the shape of B-014 —
named, and defined by nothing — and it is the material reason the redesign
cannot simply be switched on.

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

DECLARATION = re.compile(r"^\s*(--[a-zA-Z0-9_-]+)\s*:", re.M)
# `var(--x)` and `var(--x, fallback)` — the fallback is what tells the two apart.
USE = re.compile(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*(,)?")


def unresolved(css: str) -> tuple[list[str], list[str]]:
    """Splits a stylesheet's `var()` uses into the two ways they can be wrong.

    Args:
        css: The stylesheet's text.

    Returns:
        `(undefined, runtime_without_fallback)` — names used but declared
        nowhere and not runtime tokens, and runtime tokens used with no
        fallback. Both sorted, both deduplicated.
    """
    declared = set(DECLARATION.findall(css))
    undefined: set[str] = set()
    bare_runtime: set[str] = set()
    for name, comma in USE.findall(css):
        if name.startswith(RUNTIME_PREFIX):
            if not comma:
                bare_runtime.add(name)
        elif name not in declared:
            undefined.add(name)
    return sorted(undefined), sorted(bare_runtime)


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
    used = {name for name, _ in USE.findall(css)}
    declared = set(DECLARATION.findall(css))
    undefined, bare_runtime = unresolved(css)

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
    for name in bare_runtime:
        print(f"  {name} is a runtime token used with NO fallback — it resolves "
              "to nothing until the script that publishes it has run. Write "
              f"`var({name}, <default>)`.", file=sys.stderr)

    if undefined or bare_runtime:
        print(f"\ncheck-css-tokens: {len(undefined) + len(bare_runtime)} "
              f"unresolved token(s) in {SHEET.name}.", file=sys.stderr)
        return 1

    print(f"check-css-tokens: {SHEET.name} — {len(used)} token(s) used, "
          f"{len(declared)} declared, no unresolved `var()`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Refuses an interpolation whose two ends disagree.

A placeholder is a contract with TWO ends: the name a caller passes to `t()`,
and the `{{name}}` written in `fr.json`. Move one alone and nothing fails — no
type error, no test, no lint. The string simply renders with the placeholder
still in it, and the operator reads « Série {{statut}} » on screen.

That is exactly what the naming campaign did: it anglicised the caller
(`status`) and left the resource (`{{statut}}`), in four places, on surfaces the
operator uses. `screens/media.tsx` already carried the correct shape for
`missingList` — pragma and all — so the trap was known and still cost four
sites, because nothing was checking.

The placeholders themselves stay French: CLAUDE.md lists interpolation
placeholders among the things that are NOT French-in-the-code, and `fr.json` is
the translation resource. So the CALLER is the end that must agree.

Usage:
    python3 scripts/check-i18n-placeholders.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHELL = ROOT / "frontend" / "maquette" / "design" / "src"
RESOURCE = SHELL / "i18n" / "fr.json"

# `t("key", { … })` — the argument object, comments and nesting included.
CALL = re.compile(r"""\bt\(\s*["'](?P<key>[\w.]+)["']\s*,\s*\{(?P<args>.*?)\}\s*\)""", re.S)
# A key in that object: `name:` or the `{ name }` shorthand.
ARG = re.compile(r"(?:^|[,{\s])(?P<name>[A-Za-z_]\w*)\s*(?::|(?=[,}\s]*$))", re.M)
PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
COMMENT = re.compile(r"//[^\n]*")


def leaves(node: object, prefix: str = "") -> dict[str, str]:
    """Flattens the resource into dotted key → string."""
    out: dict[str, str] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            out.update(leaves(value, f"{prefix}.{key}" if prefix else key))
    elif isinstance(node, str):
        out[prefix] = node
    return out


def main() -> int:
    """Reports every placeholder no caller supplies.

    Returns:
        1 when a contract is broken, 0 otherwise.
    """
    table = leaves(json.loads(RESOURCE.read_text(encoding="utf-8")))
    violations: list[str] = []
    checked = 0

    for path in sorted(SHELL.rglob("*")):
        if path.suffix not in {".ts", ".tsx"} or "i18n" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        for call in CALL.finditer(source):
            value = table.get(call.group("key"))
            if not isinstance(value, str):
                continue
            wanted = set(PLACEHOLDER.findall(value))
            if not wanted:
                continue
            checked += 1
            # Comments are stripped first: a `french-ok` note between the brace
            # and the argument would otherwise read as an argument name.
            supplied = set(ARG.findall(COMMENT.sub("", call.group("args"))))
            missing = wanted - supplied
            if missing:
                line = source.count("\n", 0, call.start()) + 1
                violations.append(
                    f"{path.relative_to(ROOT)}:{line}: {call.group('key')} renders "
                    f"{', '.join('{{' + m + '}}' for m in sorted(missing))} literally — "
                    f"fr.json expects {sorted(wanted)}, the caller passes {sorted(supplied)}")

    if violations:
        print("i18n placeholder contract broken:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(f"\n{len(violations)} broken. The placeholder is named by fr.json; "
              "the CALLER is the end that must agree — fr.json is the translation "
              "resource and does not move.", file=sys.stderr)
        return 1
    print(f"check-i18n-placeholders: {checked} interpolated call(s), every "
          "placeholder supplied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

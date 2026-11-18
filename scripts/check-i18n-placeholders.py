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
from _repo_paths import DESIGN_SRC

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHELL = DESIGN_SRC
RESOURCE = SHELL / "i18n" / "fr.json"

# `t("key", { … })` — the argument object, comments and nesting included.
CALL = re.compile(r"""\bt\(\s*["'](?P<key>[\w.]+)["']\s*,\s*\{(?P<args>.*?)\}\s*\)""", re.S)
# One entry of that object: `name: value`, `"name": value` or the `name` shorthand.
ENTRY = re.compile(r"""^\s*["']?(?P<name>[A-Za-z_]\w*)["']?\s*(?::|$)""")
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


def top_level_entries(args: str) -> list[str]:
    """Splits the text of an argument object at its top-level commas.

    Commas inside a string, a template literal or a nested bracket belong to the entry.

    Args:
        args: The text between the braces of the call's argument object.

    Returns:
        The entries, in order, unstripped.
    """
    entries: list[str] = []
    current: list[str] = []
    depth = 0
    quote = ""
    escaped = False
    for char in args:
        if quote:
            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in "\"'`":
            quote = char
        elif char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            entries.append("".join(current))
            current = []
            continue
        current.append(char)
    entries.append("".join(current))
    return entries


def supplied_names(args: str) -> set[str]:
    """Reads the argument names a `t()` call passes, from the text of its object.

    A name is read from the start of each top-level entry, so `{ start, end }` on one line
    yields both, and `{ a: foo }` yields `a` and not the identifier `foo`.

    Args:
        args: The text between the braces of the call's argument object.

    Returns:
        The names the call supplies.
    """
    # Comments are stripped first: a `french-ok` note between the brace
    # and the argument would otherwise read as an argument name.
    names: set[str] = set()
    for entry in top_level_entries(COMMENT.sub("", args)):
        found = ENTRY.match(entry)
        if found:
            names.add(found.group("name"))
    return names


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
            supplied = supplied_names(call.group("args"))
            missing = wanted - supplied
            if missing:
                line = source.count("\n", 0, call.start()) + 1
                violations.append(
                    f"{path.relative_to(ROOT)}:{line}: {call.group('key')} renders "
                    f"{', '.join('{{' + m + '}}' for m in sorted(missing))} literally — "
                    f"fr.json expects {sorted(wanted)}, the caller passes {sorted(supplied)}"
                )

    if violations:
        print("i18n placeholder contract broken:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(
            f"\n{len(violations)} broken. The placeholder is named by fr.json; "
            "the CALLER is the end that must agree — fr.json is the translation "
            "resource and does not move.",
            file=sys.stderr,
        )
        return 1
    print(f"check-i18n-placeholders: {checked} interpolated call(s), every placeholder supplied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

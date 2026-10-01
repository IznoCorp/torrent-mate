#!/usr/bin/env python3
"""Block ripgrep (``rg``) commands without an explicit type/glob filter.

``rg`` mmap's every file it scans. The repo contains ``tests/e2e/perf/.fixture/``
(~14 GB of binary media). Without a type or glob filter, ``rg`` loads it all into
RAM and either:

- consumes 40+ GB of RAM (incident 2026-05-28, operator had to kill manually);
- gets OOM-killed silently;
- crashes the machine (PID 39685 prior incident).

This hook enforces that every ``rg`` invocation carries at least one of:

- ``-t TYPE`` / ``--type TYPE``       (e.g. ``-t py``)
- ``-T TYPE`` / ``--type-not TYPE``
- ``-g PATTERN`` / ``--glob PATTERN``
- ``--iglob PATTERN``
- ``--files-from FILE``

Meta-only invocations (``--help``, ``--version``, ``--type-list``) are exempt.

``.rgignore`` at repo root is defense-in-depth; the type/glob filter is the
authoritative safeguard because new fixtures appear and ``.rgignore`` lag.
"""

from __future__ import annotations

import json
import re
import sys

# Match a top-level ``rg`` invocation: either at the start of the command, after
# a shell separator (``|``, ``;``, ``&``), or after whitespace. Accept absolute
# bin paths (e.g. ``/opt/homebrew/bin/rg``). Followed by a space (i.e., has args)
# OR end of string (bare ``rg``).
_RG_CMD = re.compile(r"(?:^|[|;&\s])(?:/[^\s]+/)?rg(?:\s|$)")

# Meta flags that don't scan files at all — exempt from the filter requirement.
_META_FLAGS = re.compile(
    r"(?:^|\s)(?:--help|-h|--version|-V|--type-list|--type-add\s+\S+\s*$|--pcre2-version)\b"
)

# Scope-limiting flags that satisfy the filter requirement. Each must have an
# argument (``\S+``) to be a real filter (bare ``-t`` would be a typo).
# Combined as a single alternation to keep regex compilation cheap.
_FILTER_FLAGS = re.compile(
    r"(?:^|\s)(?:"
    r"-t\s+\S+"
    r"|--type[= ]\S+"
    r"|-T\s+\S+"
    r"|--type-not[= ]\S+"
    r"|-g\s+\S+"
    r"|--glob[= ]\S+"
    r"|--iglob[= ]\S+"
    r"|--files-from[= ]\S+"
    r")"
)


def _strip_quoted(command: str) -> str:
    """Strip single- and double-quoted substrings so a ``rg`` reference inside
    a quoted argument (e.g. ``echo "use rg foo"``) doesn't trip the detector.

    Imperfect (does not handle escapes) but sufficient for typical CLI usage.
    """
    return re.sub(r"'[^']*'|\"[^\"]*\"", "", command)


def main() -> None:
    """Block ``rg`` calls missing a type/glob filter."""
    try:
        input_data = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"continue": True}))
        return

    if input_data.get("tool_name") != "Bash":
        print(json.dumps({"continue": True}))
        return

    command: str = input_data.get("tool_input", {}).get("command", "")
    scrubbed = _strip_quoted(command)

    if not _RG_CMD.search(scrubbed):
        print(json.dumps({"continue": True}))
        return

    if _META_FLAGS.search(scrubbed):
        print(json.dumps({"continue": True}))
        return

    if _FILTER_FLAGS.search(scrubbed):
        print(json.dumps({"continue": True}))
        return

    print(
        json.dumps(
            {
                "decision": "block",
                "reason": (
                    "BLOCKED: rg call missing a type/glob filter. "
                    "Without --type/--glob, rg scans tests/e2e/perf/.fixture/ "
                    "(~14 GB of binary media) and exhausts RAM (40 GB+ incident "
                    "2026-05-28). Add one of:\n"
                    "  -t py                       (Python files only)\n"
                    "  -g '*.py' -g '*.md'         (multi-extension glob)\n"
                    "  --type-not log              (exclude logs)\n"
                    "See CLAUDE.md §'Search Safety' for the rule."
                ),
            }
        )
    )


if __name__ == "__main__":
    main()

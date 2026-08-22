#!/usr/bin/env python3
"""Arm 9 — every line a shell script prints is the tool speaking.

SPLIT OUT OF `check-no-french.py` for the room the arms of sub-phase 6.6 took,
and it is a clean seam because the CORPUS is its own: `.sh` files and the
Makefile, which no other arm reads. That is exactly why it exists — no arm read
one at all until three all-French scripts turned up under a green gate.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nofrench_lexicon import (  # noqa: E402
    ROOT, examined, french_tokens_in, has_accent, offending_string, read,
    pragma_on, relative, tracked_paths,
)


SHELL_BY_NAME = {"Makefile"}


def first_line(path: Path) -> str:
    """The file's first line, or "" when it cannot be read as text."""
    try:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            return handle.readline()
    except OSError:
        return ""


def check_shell_scripts(violations: list[str]) -> None:
    """Refuses French in a `.sh` — every line of one is the tool speaking.

    NO ARM READ `.sh` AT ALL, and three of this repository's nine shell scripts
    were written in French throughout — the two deploy scripts and the poller,
    which between them are the only sanctioned way to put anything in front of
    the operator. The rule has always covered them: a message a tool prints is
    English. Nothing had ever looked.

    A shell script has no i18n bundle and renders nothing to a reader of the
    interface, so the distinction the other arms draw — code here, copy there —
    does not exist in one. Every line is read, comment and message alike.

    Args:
        violations: The accumulator every arm appends to.
    """
    for relative_path in tracked_paths():
        path = ROOT / relative_path
        if not path.is_file():
            continue
        # A SCRIPT IS A SCRIPT WHETHER OR NOT ITS NAME ENDS IN `.sh`. Matching
        # the extension alone left every git hook out — `hooks/pre-commit`,
        # `hooks/pre-push`, `hooks/commit-msg`, `scripts/pre-push` — plus the
        # Makefile and a PM2 `.cjs` declaration, all of which print to the
        # operator and none of which any arm read. Three all-French `.sh` files
        # were once found this way; these are the same class, one naming
        # convention over.
        # `.py` carries a shebang too and is already read, line by line, by the
        # string and identifier arms; pulling it in here would double every
        # finding and trip on the accent RANGES in this file's own regexes.
        if path.suffix == ".py":
            continue
        if not (relative_path.endswith((".sh", ".cjs", ".mjs"))
                or path.name in SHELL_BY_NAME
                or first_line(path).startswith("#!")):
            continue
        lines = read(path).splitlines()
        for line_no, line in enumerate(lines, start=1):
            examined["lines / shell scripts"] += 1
            reason = offending_string(line)
            if not reason:
                continue
            if pragma_on(lines, line_no):
                continue
            violations.append(
                f"{relative_path}:{line_no}: French in a shell script "
                f"({reason}) — a developer tool speaks English: {line.strip()[:60]!r}")

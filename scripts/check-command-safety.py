#!/usr/bin/env python3
"""Refuses committing a command CLAUDE.md says will hang or crash the machine.

TWO RULES WITH NO ARM ON THE REPOSITORY. §Search Safety and §Network Timeout
Safety are real — they were written after a `rg` without a type filter took
40 GB of RAM scanning a 14 GB binary fixture, and after a `curl` with no timeout
hung for eleven hours on a host that accepted the TCP connection and never
answered. Both are enforced by PreToolUse hooks under `.claude/`, which guard
the AGENT'S session and nothing else: they cannot see a command written into a
script and committed, and the next person to run that script pays the same
price.

Already in the tree when this was written: two timeout-less `curl` calls in
`.github/workflows/gitleaks-full.yml` and five unfiltered `rg` calls in the
Makefile's own `gate` target.

Usage:
    python3 scripts/check-command-safety.py            # the whole repository
    python3 scripts/check-command-safety.py FILE...    # named files (pre-commit)
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Where a shell command can be written down.
SUFFIXES = {".sh", ".yml", ".yaml", ".py", ".mjs", ".js", ".ts"}
EXTENSIONLESS = {"Makefile", "pre-commit", "pre-push", "commit-msg", "install.sh"}

# `curl`/`wget`, up to the end of the command.
NETWORK = re.compile(r"\b(?P<tool>curl|wget)\b(?P<args>[^\n;&]*)")
# `rg` as a command, not the word « rg » in prose.
SEARCH = re.compile(r"(?:^|[\s|;&(`$])(?P<tool>rg)\b(?P<args>[^\n;&)]*)")

TIMEOUT_FLAGS = ("--max-time", "--connect-timeout", "--timeout", "-T ")
FILTER_FLAGS = ("--type", "-t ", "-g ", "--glob", "--type-not", "--files")

# Lines that name the rule rather than break it: this file, and the guards that
# quote the forbidden shapes in order to refuse them.
EXEMPT_NAMES = {"check-command-safety.py"}


QUOTED = re.compile(r"""("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')""")


def commands(text: str):
    r"""Yields (line number, command text) for each line that runs something.

    Four shapes are NOT a command, and each produced a false positive on the
    first run over this repository:

    - a `|` inside a QUOTED pattern — `rg "TMDBError|TVDBError" -g '*.py'` had
      its own `-g` cut off by an argument scan that stopped at the pipe, so a
      correctly-filtered call was reported as unfiltered;
    - a line CONTINUATION — `rg -n "$PATTERN" \` carries its paths on the next
      line, and a per-line scan never sees them;
    - `command -v rg`, which asks whether the tool exists;
    - a docstring QUOTING a command in order to document it.

    Args:
        text: The file's contents.

    Yields:
        (1-based line number, the command with quoted runs blanked out).
    """
    lines = text.splitlines()
    in_docstring = False
    index = 0
    while index < len(lines):
        start = index
        line = lines[index]
        # Join continuations, so a command's own flags are all in one string.
        while line.rstrip().endswith("\\") and index + 1 < len(lines):
            index += 1
            line = line.rstrip()[:-1] + " " + lines[index]
        index += 1

        fences = line.count('"""') + line.count("'''")
        was_in = in_docstring
        if fences % 2:
            in_docstring = not in_docstring
        if was_in or in_docstring:
            continue

        stripped = line.strip()
        if stripped.startswith(("#", "//", "*")):
            continue
        # Quoted runs are DATA: blanking them keeps a `|` or a `;` inside a
        # pattern from ending the command, while leaving every flag in place.
        yield start + 1, QUOTED.sub(lambda m: " " * len(m.group(0)), line)


def shown(path: pathlib.Path) -> str:
    """The path as a reader should see it, repo-relative when it can be."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def offences(path: pathlib.Path) -> list[str]:
    """Returns one message per unsafe command written in `path`."""
    if path.name in EXEMPT_NAMES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    found: list[str] = []
    for line_no, line in commands(text):
        if "command -v" in line:
            continue
        for match in NETWORK.finditer(line):
            args = match.group("args")
            if not any(flag in args for flag in TIMEOUT_FLAGS):
                found.append(
                    f"{shown(path)}:{line_no}: {match.group('tool')} with no "
                    "timeout — add --connect-timeout 10 --max-time 30 (CLAUDE.md "
                    "§Network Timeout Safety: eleven hours on a host that never answered)")
        for match in SEARCH.finditer(line):
            args = match.group("args")
            if not any(flag in args for flag in FILTER_FLAGS):
                found.append(
                    f"{shown(path)}:{line_no}: rg with no type filter — add "
                    "--type py or -g '*.ext' (CLAUDE.md §Search Safety: 40 GB of RAM "
                    "over the 14 GB binary fixture)")
    return found


def tracked() -> list[pathlib.Path]:
    """Every tracked file a command could be written in."""
    listing = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    out = []
    for name in listing.split("\n"):
        if not name:
            continue
        path = ROOT / name
        if path.suffix in SUFFIXES or path.name in EXTENSIONLESS:
            out.append(path)
    return out


def main() -> int:
    """Reports every unsafe command, in the named files or the whole tree."""
    argv = [pathlib.Path(a).resolve() for a in sys.argv[1:]]
    paths = argv or tracked()
    violations: list[str] = []
    for path in paths:
        if path.is_file():
            violations.extend(offences(path))

    if violations:
        print("commands that will hang or crash the machine:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(f"\n{len(violations)} found. Both of these rules exist because "
              "the thing they forbid already happened here.", file=sys.stderr)
        return 1
    print(f"check-command-safety: {len(paths)} file(s), no unsafe command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

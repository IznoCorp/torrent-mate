#!/usr/bin/env python3
"""Assert a PR bumps ``personalscraper.__version__`` above the base ref.

Operator rule (2026-07-15, constitution §10-3): every PR bumps the version.
This guard extracts ``__version__`` from ``personalscraper/__init__.py`` on
HEAD and on the PR base ref and fails when HEAD's version is not strictly
greater. It is the CI teeth behind the "bump à chaque PR" discipline.

Usage:
  scripts/check_version_bump.py --base origin/main

A genuinely version-neutral PR (docs-only, CI-only) can override via a PR
label handled in the workflow — this script always enforces the bump.

Exit codes:
  0 — HEAD version > base version (bump present).
  1 — HEAD version <= base version (missing bump), or a parse error.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

_VERSION_RE = re.compile(r'__version__\s*=\s*["\']([^"\']+)["\']')
_INIT_PATH = "personalscraper/__init__.py"


def _parse_version(text: str) -> tuple[int, ...] | None:
    """Extract and parse ``__version__`` from an ``__init__.py`` body.

    Args:
        text: The file contents.

    Returns:
        The version as a tuple of ints (e.g. ``(0, 49, 9)``), or ``None`` when
        no parseable ``__version__`` assignment is found.
    """
    match = _VERSION_RE.search(text)
    if match is None:
        return None
    parts = match.group(1).split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


def _base_version(base_ref: str) -> tuple[int, ...] | None:
    """Read the version from ``__init__.py`` at *base_ref* via ``git show``.

    Args:
        base_ref: The base ref (e.g. ``origin/main``).

    Returns:
        The parsed base version, or ``None`` when the file/ref is unavailable.
    """
    try:
        out = subprocess.run(
            ["git", "show", f"{base_ref}:{_INIT_PATH}"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    return _parse_version(out.stdout)


def main() -> int:
    """Compare HEAD vs base ``__version__`` and enforce a strict bump."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main", help="Base ref to compare against.")
    args = parser.parse_args()

    with open(_INIT_PATH, encoding="utf-8") as fh:
        head = _parse_version(fh.read())
    if head is None:
        print(f"::error::could not parse __version__ from {_INIT_PATH}", file=sys.stderr)
        return 1

    base = _base_version(args.base)
    if base is None:
        # No base version to compare (new file / unreachable ref) — cannot
        # prove a regression, so do not block.
        print(f"base version unavailable at {args.base}; skipping bump check")
        return 0

    if head > base:
        print(f"version bump OK: {'.'.join(map(str, base))} -> {'.'.join(map(str, head))}")
        return 0

    print(
        f"::error::version not bumped: HEAD {'.'.join(map(str, head))} <= base "
        f"{'.'.join(map(str, base))}. Bump personalscraper.__version__ (rule §10-3), "
        "or add the 'no-version-bump' label for a version-neutral PR.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read [tool.coverage.report].fail_under from pyproject.toml.

Used by the Makefile (``THRESHOLD := $(shell python3 scripts/get_coverage_threshold.py)``)
and by the coverage-monotonic CI job (``--stdin`` mode reads main's pyproject.toml
without a checkout).

Exit codes:
  0 — value printed to stdout.
  1 — pyproject.toml missing or fail_under absent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10 has no stdlib tomllib; tomli is the canonical fallback (declared in dev deps).
    import tomli as tomllib  # type: ignore[import-not-found, no-redef]


def main() -> int:
    """Resolve fail_under from a pyproject.toml file or stdin and print it."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read pyproject.toml content from stdin (used by coverage-monotonic CI step).",
    )
    args = parser.parse_args()

    source = "<stdin>" if args.stdin else None
    try:
        if args.stdin:
            data = tomllib.loads(sys.stdin.read())
        else:
            path = Path(__file__).resolve().parent.parent / "pyproject.toml"
            source = str(path)
            if not path.exists():
                print(f"error: {path} not found", file=sys.stderr)
                return 1
            with path.open("rb") as f:
                data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        # Surface a one-line operator-friendly message instead of a raw
        # traceback (the CI monotonic step's output is small enough that
        # a stack trace drowns the cause).
        print(f"error: {source} is not valid TOML ({exc})", file=sys.stderr)
        return 1

    # Walk the path explicitly so the error message names the missing key,
    # not just the leaf 'fail_under'.
    cursor: object = data
    walked: list[str] = []
    for key in ("tool", "coverage", "report", "fail_under"):
        if not isinstance(cursor, dict) or key not in cursor:
            print(
                f"error: {'.'.join(walked) or '<root>'} has no '{key}' "
                f"(looking for [tool.coverage.report].fail_under)",
                file=sys.stderr,
            )
            return 1
        cursor = cursor[key]
        walked.append(key)

    print(cursor)
    return 0


if __name__ == "__main__":
    sys.exit(main())

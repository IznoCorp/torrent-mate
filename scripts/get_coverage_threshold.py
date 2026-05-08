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
except ImportError:  # Python 3.10
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

    if args.stdin:
        data = tomllib.loads(sys.stdin.read())
    else:
        path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            return 1
        with path.open("rb") as f:
            data = tomllib.load(f)

    try:
        threshold = data["tool"]["coverage"]["report"]["fail_under"]
    except KeyError:
        print("error: [tool.coverage.report].fail_under not set", file=sys.stderr)
        return 1

    print(threshold)
    return 0


if __name__ == "__main__":
    sys.exit(main())

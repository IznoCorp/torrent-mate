"""Hard-block module-size guardrail (promoted from advisory in 0.10.0).

Walks the personalscraper/ package (or --root) and reports files exceeding
soft (WARN) and hard (REPORT) thresholds. Excludes __init__.py, tests
directories, and migration directories.

Exit code:
  - 0 when no REPORT-level findings exist (WARN-only is OK)
  - 1 when one or more REPORT-level findings exist (>= 1000 LOC)
  - 2 when the root directory is missing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

WARN_LOC = 800
BLOCK_LOC = 1000
DEFAULT_ROOT = Path("personalscraper")
EXCLUDED_FILENAMES = {"__init__.py"}
EXCLUDED_DIR_PARTS = {"tests", "migrations"}


def _count_lines(path: Path) -> int:
    """Count non-blank lines as a cheap cognitive-load proxy."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
    except (OSError, UnicodeDecodeError):
        return 0


def _is_excluded(path: Path) -> bool:
    """Return True when a Python file is excluded from module-size reporting."""
    if path.name in EXCLUDED_FILENAMES:
        return True
    return any(part in EXCLUDED_DIR_PARTS for part in path.parts)


def main() -> int:
    """Run the module-size advisory check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=DEFAULT_ROOT, type=Path)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 on REPORT-level findings (post-0.10.0 mode).",
    )
    args = parser.parse_args()

    root: Path = args.root
    if not root.exists():
        print(f"check-module-size: root not found: {root}", file=sys.stderr)
        return 2

    findings: list[tuple[str, Path, int]] = []
    for path in sorted(root.rglob("*.py")):
        if _is_excluded(path):
            continue
        loc = _count_lines(path)
        if loc >= BLOCK_LOC:
            findings.append(("REPORT", path, loc))
        elif loc >= WARN_LOC:
            findings.append(("WARN", path, loc))

    if not findings:
        print(f"check-module-size: clean (root={root})")
        return 0

    print(f"check-module-size: {len(findings)} finding(s) (root={root})")
    for level, path, loc in findings:
        dest = sys.stderr if level == "WARN" else sys.stdout
        print(f"  [{level}] {path}: {loc} non-blank lines", file=dest)

    if any(level == "REPORT" for level, _, _ in findings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

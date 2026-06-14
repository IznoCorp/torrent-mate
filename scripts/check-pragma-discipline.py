"""PRAGMA discipline lint guard (DEV #33, #34).

Fails if any Python file under ``personalscraper/`` contains a raw
``sqlite3.connect(`` call that is **not** immediately followed (within 5 lines)
by a call to ``_apply_pragmas(`` or ``apply_pragmas(``.

The authorised exceptions are:

* ``personalscraper/indexer/db.py`` — **defines** :func:`_apply_pragmas`
  (the original helper) via ``open_db`` which uses ``sqlite3.connect`` internally.
* ``personalscraper/core/sqlite/_pragmas.py`` — **defines** the canonical
  :func:`apply_pragmas` (no leading underscore) helper; its docstring mentions
  ``sqlite3.connect()``.  The module performs NO actual connection.

All other sites MUST use ``_apply_pragmas`` or ``apply_pragmas`` after every
raw ``sqlite3.connect`` call.

Usage::

    python3 scripts/check-pragma-discipline.py

Exit codes:
    0 — all sites comply (or are in the allowlist).
    1 — one or more violations found; details printed to stdout.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Root of the personalscraper package (relative to this script's parent dir).
PACKAGE_ROOT = Path(__file__).parent.parent / "personalscraper"

# Files explicitly allowed to contain raw ``sqlite3.connect(`` without an
# immediately following ``_apply_pragmas`` or ``apply_pragmas`` call.
ALLOWLIST: frozenset[str] = frozenset(
    {
        str(PACKAGE_ROOT / "indexer" / "db.py"),
        # definition site of apply_pragmas; its docstring mentions sqlite3.connect()
        str(PACKAGE_ROOT / "core" / "sqlite" / "_pragmas.py"),
        # RP6 ownership adapter (IndexerOwnershipChecker): opens a deliberately
        # read-only, lock-free connection to library.db with ``PRAGMA
        # query_only=ON``. It MUST bypass the canonical writer PRAGMA set
        # (WAL + foreign_keys=ON would defeat the read-only / no-writer-lock
        # intent and could take a lock at the shared composition root).
        str(PACKAGE_ROOT / "indexer" / "ownership.py"),
    }
)

# How many source lines after the ``sqlite3.connect(`` line we scan for the
# ``_apply_pragmas(`` call before declaring a violation.
LOOKAHEAD_LINES = 5


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------


def _check_file(path: Path) -> list[str]:
    """Return a list of violation messages for *path*.

    Args:
        path: Python source file to inspect.

    Returns:
        A list of human-readable violation strings (empty when the file is
        clean).
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path}: cannot read — {exc}"]

    lines = source.splitlines()
    violations: list[str] = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match raw sqlite3.connect( calls.  We intentionally use a simple
        # substring check (not AST) so that aliased imports like
        # ``import sqlite3 as _sqlite3`` are also caught.
        if "sqlite3.connect(" not in stripped:
            continue
        # Skip comment lines — a ``#`` or ``#:`` prefix before the token means
        # this is documentation, not live code.  Also skip lines where the
        # token only appears inside a string literal (e.g. docstrings that
        # explain the guard pattern).  Simple heuristic: if the first non-space
        # character is ``#``, it is a comment.
        if stripped.startswith("#"):
            continue

        # Look ahead up to LOOKAHEAD_LINES for _apply_pragmas( or apply_pragmas(
        # (the bare "apply_pragmas(" substring matches both spellings).
        window = lines[i + 1 : i + 1 + LOOKAHEAD_LINES]
        found_apply = any("apply_pragmas(" in wl for wl in window)
        if not found_apply:
            violations.append(
                f"{path}:{i + 1}: raw sqlite3.connect() without _apply_pragmas — "
                "use _apply_pragmas(conn) immediately after connect"
            )

    return violations


def main() -> int:
    """Run the PRAGMA discipline check across the package.

    Returns:
        Exit code: 0 for clean, 1 for violations.
    """
    all_violations: list[str] = []

    for py_file in sorted(PACKAGE_ROOT.rglob("*.py")):
        if str(py_file) in ALLOWLIST:
            continue
        all_violations.extend(_check_file(py_file))

    if all_violations:
        print("PRAGMA discipline violations found:")
        for v in all_violations:
            print(f"  {v}")
        print(
            f"\n{len(all_violations)} violation(s). "
            "Add _apply_pragmas(conn) after every sqlite3.connect() call, "
            "or add the file to ALLOWLIST in scripts/check-pragma-discipline.py "
            "only if it truly must bypass the canonical PRAGMA set."
        )
        return 1

    print(f"PRAGMA discipline: OK ({_count_py_files()} files checked, 0 violations)")
    return 0


def _count_py_files() -> int:
    """Return the count of Python files checked (excluding allowlist).

    Returns:
        Number of ``.py`` files scanned under the package root.
    """
    return sum(1 for p in PACKAGE_ROOT.rglob("*.py") if str(p) not in ALLOWLIST)


if __name__ == "__main__":
    sys.exit(main())

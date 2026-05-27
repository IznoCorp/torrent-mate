#!/usr/bin/env python3
"""AST-based linter: forbid `except RegistryError` / `except WrongSemanticBug`.

DESIGN §7.1 — `WrongSemanticBug` and the broader `RegistryError` family must
never be caught around registry call sites: they are programmer bugs (caller
invoked the wrong operation) and must bubble up, not be silenced.

This linter walks every `*.py` under `personalscraper/` and reports `try`/`except`
blocks whose `ExceptHandler.type` references `RegistryError` or `WrongSemanticBug`
(directly or via tuple). Exits 1 with a file:line list if any violation is found,
exits 0 otherwise.

Usage: python3 scripts/check-no-broad-registry-catch.py
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_CATCHES = {"RegistryError", "WrongSemanticBug"}


def _names_from_handler(handler: ast.ExceptHandler) -> list[str]:
    """Extract the simple names from an except handler type expression."""
    if handler.type is None:
        return []
    if isinstance(handler.type, ast.Name):
        return [handler.type.id]
    if isinstance(handler.type, ast.Tuple):
        out = []
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name):
                out.append(elt.id)
        return out
    # Attribute access like `_errors.RegistryError` — extract the attribute name
    if isinstance(handler.type, ast.Attribute):
        return [handler.type.attr]
    return []


def check_file(path: Path) -> list[str]:
    """Return violations (file:line) for one file."""
    violations: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            for name in _names_from_handler(handler):
                if name in FORBIDDEN_CATCHES:
                    violations.append(
                        f"{path}:{handler.lineno}: forbidden `except {name}` "
                        f"(DESIGN §7.1 — programmer bug, must not be caught)"
                    )
    return violations


def main() -> int:
    """Walk personalscraper/, collect violations, exit code = found count."""
    root = Path(__file__).resolve().parent.parent / "personalscraper"
    if not root.is_dir():
        print(f"ERROR: package directory not found: {root}", file=sys.stderr)
        return 2

    all_violations: list[str] = []
    for py_file in sorted(root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        all_violations.extend(check_file(py_file))

    if all_violations:
        print("Broad registry-error catches found:", file=sys.stderr)
        for v in all_violations:
            print(f"  {v}", file=sys.stderr)
        print(f"\nTotal: {len(all_violations)} violation(s)", file=sys.stderr)
        return 1

    print("OK: no broad registry-error catches in personalscraper/")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Puts a harness rule's own invocation behind `if __name__ == "__main__":`.

WHY (B-325). Every rule module ended in a bare `asyncio.run(main())`, so a rule
could not be IMPORTED without running: an independent reader wanting to point a
rule at its own build had to rebind a module constant from a wrapper outside the
tree, and nothing that reads rules as modules — a test, a lister, a tool that
counts holds — could exist at all.

WHY A TOOL RATHER THAN A HAND. The change is mechanical over eighty-odd files,
and this repository has paid for hand edits at that scale more than once. The
tool parses each file with `ast` rather than matching text, so what it moves is
what Python would have executed, and it refuses anything it cannot recognise
instead of guessing. IT IS STILL NOT THE PROOF: the diff is read afterwards and
the rule suite is run, because a tool reporting « N files touched » is a tool
reporting its own opinion.

    python3 scripts/guard-module-entry-points.py <path>...      # rewrite
    python3 scripts/guard-module-entry-points.py --check <path>...
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys

GUARD = 'if __name__ == "__main__":'


# What may stand BETWEEN two invocations and still let the second be moved up
# beside the first. `pop.py` runs one rule, defines a second, and runs that —
# so its first invocation is not trailing, and a tool that only looked at the
# tail would leave the module running half of itself on import. Moving a call
# past a definition changes nothing: a `def` binds a name, it does not act. A
# statement that ACTS is refused rather than reordered.
INERT_BETWEEN = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef,
                 ast.ClassDef, ast.Assign, ast.AnnAssign)


class NotMechanical(Exception):
    """Raised when a module's shape is not one this tool may rewrite."""


def invocation_lines(source: str) -> list[int]:
    """The 1-based lines of the module-level statements that RUN it.

    Only expression statements that are CALLS count: a constant, an assignment
    or a definition is never an invocation. They are collected wherever they
    sit, and gathered into one guard at the end — which is order-preserving as
    long as nothing that ACTS stands between the first of them and the last.

    Args:
        source: The module's text.

    Returns:
        The line numbers to move, in order.

    Raises:
        NotMechanical: When a statement that acts stands between two
            invocations, so moving them would change what the module does.
    """
    tree = ast.parse(source)
    # AFTER THE FIRST DEFINITION, and that clause is not a refinement — it is
    # the difference between a repair and a corruption. Every rule here opens
    # with `sys.path.insert(0, …)` so that `from common import …` resolves, and
    # that is a top-level call too: a first version of this tool moved it into
    # the guard in FORTY-ONE files, leaving each one unable to import the module
    # it depends on. `ruff` passed over all of them and so did the tool's own
    # count; reading the diff is what caught it. A module's entry point calls
    # something the module DEFINED, so nothing before the first definition is
    # one.
    first_definition = next(
        (statement.lineno for statement in tree.body
         if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))),
        None)
    if first_definition is None:
        return []
    calls = [statement for statement in tree.body
             if isinstance(statement, ast.Expr)
             and isinstance(statement.value, ast.Call)
             and statement.lineno > first_definition]
    if not calls:
        return []
    first, last = calls[0].lineno, calls[-1].lineno
    for statement in tree.body:
        if statement in calls or not (first < statement.lineno < last):
            continue
        if not isinstance(statement, INERT_BETWEEN):
            raise NotMechanical(
                f"line {statement.lineno}: {type(statement).__name__} stands "
                "between two invocations and acts")
    lines: list[int] = []
    for statement in calls:
        end = statement.end_lineno
        assert end is not None
        lines.extend(range(statement.lineno, end + 1))
    return lines


def guarded(source: str) -> str | None:
    """The module with its invocation behind the guard, or None when untouched.

    Args:
        source: The module's text.

    Returns:
        The rewritten text, or None when the module already has a guard or has
        no trailing invocation to move.
    """
    if GUARD in source:
        return None
    lines = invocation_lines(source)
    if not lines:
        return None
    text = source.splitlines(keepends=True)
    moved = ["    " + text[index - 1] for index in lines]
    # A module's last line may lack its newline; the guard block must not run
    # into whatever a later edit appends.
    if not moved[-1].endswith("\n"):
        moved[-1] += "\n"
    kept = [line for number, line in enumerate(text, start=1) if number not in set(lines)]
    while kept and kept[-1].strip() == "":
        kept.pop()
    return "".join(kept) + "\n\n" + GUARD + "\n" + "".join(moved)


def main() -> int:
    """Guard, or report, every module named on the command line.

    Returns:
        Zero when nothing needed changing, one otherwise (so `--check` can gate).
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=pathlib.Path)
    parser.add_argument("--check", action="store_true",
                        help="report what would change and rewrite nothing")
    arguments = parser.parse_args()

    changed = 0
    refused = 0
    for path in arguments.paths:
        source = path.read_text(encoding="utf-8")
        try:
            rewritten = guarded(source)
        except NotMechanical as why:
            refused += 1
            print(f"{path}: REFUSED — {why}. Move it by hand and say so.",
                  file=sys.stderr)
            continue
        if rewritten is None:
            continue
        changed += 1
        print(f"{path}: {len(invocation_lines(source))} line(s) moved behind the guard")
        if not arguments.check:
            path.write_text(rewritten, encoding="utf-8")
    print(f"guard-module-entry-points: {changed} of {len(arguments.paths)} module(s) "
          f"{'would be' if arguments.check else ''} changed, {refused} refused")
    return 1 if refused or (changed and arguments.check) else 0


if __name__ == "__main__":
    sys.exit(main())

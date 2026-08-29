#!/usr/bin/env python3
"""Runs the maquette's unit suite and refuses a run that collected too little.

WHY A FLOOR AND NOT JUST THE EXIT CODE. Vitest exits 1 when it finds no test
file at all, which is the loudest half of the problem and not the whole of it: a
run that collects ONE file out of two is green, reports a smaller number nobody
compares, and the arm that stopped running falls silent. This repository has
paid twenty-six times for a guard that was green because of what it did not
read; a runner is a guard, and it gets the same treatment as the others.

WHAT THIS DOES NOT READ, said before what it does:

  - It does not read whether the tests are any GOOD. A floor counts; only
    mutation testing says a test bites, and that is invariant 11's job at the
    moment a test is written.
  - It does not read the maquette's browser rules. Those are the harness's, and
    a rule proved in a browser is a different instrument from a pure function
    proved in a runner — the whole reason this layer was owed.
  - It cannot run where the maquette's dependencies are absent. That case is
    announced and SKIPPED LOUDLY rather than passed: a skip printed as a pass is
    the shape this file exists to refuse.

THE FLOOR MOVES ONE WAY. It is raised as the suite grows and it is never
lowered to accommodate a deletion — a deleted test is a decision somebody makes
in a diff, with this number in it.
"""
import json
import pathlib
import ast
import tokenize
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DESIGN = ROOT / "frontend" / "maquette" / "design"

# What the suite must collect at least. Raised in the commit that adds tests,
# never lowered to let a deletion through.
#
# AND IT IS RAISED TO THE CORPUS, not to something under it. These sat at 36 and
# 2 while the suite held 58 tests in 4 files — so an entire test FILE could be
# deleted with both floors clear, which is precisely the mutation the phase that
# wrote them watched fall. A floor 37 % below what it guards is a floor nothing
# stands on: the smallest of the four files is 7 tests, so the file floor is the
# file count and the test floor is the test count.
TEST_FLOOR = 93
FILE_FLOOR = 5


# THE PER-PULL-REQUEST TIER'S COMPOSITION, and it is this module's second
# subject for one reason: both questions are « does the runner run what it says
# it runs? ». A rule reading the operator's LIVE databases cannot be in
# `--contracts` — `arrivals.py` was, and failed on the runner for want of
# `library.db`, which says nothing about the change under test (B-049). That was
# corrected by hand and nothing has held it since; a second rule joining the
# tier with a `sqlite3.connect` in it would go unnoticed exactly as the first
# did.
#
# WHAT MAKES IT DECIDABLE: a rule that reads a database says so in its source —
# it names a `.db` path or opens a connection. That is a text question with a
# text answer, and it is the whole of the disqualifying property.
HARNESS = ROOT / "frontend" / "maquette" / "harness"
RUNNER = HARNESS / "run.sh"
LIVE_DATABASE = re.compile(r"\.db\b|sqlite3\.connect")


def executable_source(path: pathlib.Path) -> str:
    """Returns a module's text with comments and docstrings removed.

    A `.db` NAMED IN PROSE IS NOT A READ. Every paragraph in this repository
    that explains B-049 writes `library.db`, and a rule carrying that
    explanation in its own header was disqualified for describing the defect it
    avoids. String LITERALS stay — a database path reaches the code as one, and
    dropping those would be the opposite mistake.

    Args:
        path: The module to read.

    Returns:
        The source with comment tokens dropped and docstring expressions blanked.
    """
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    spans = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        first = node.body[0] if node.body else None
        if (isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)):
            spans.append((first.lineno, first.end_lineno))
    lines = source.splitlines()
    for start, end in spans:
        for number in range(start, end + 1):
            lines[number - 1] = ""
    kept = []
    for line in lines:
        try:
            tokens = tokenize.generate_tokens(iter([line + "\n"]).__next__)
            kept.append("".join(text for kind, text, *_ in tokens
                                if kind != tokenize.COMMENT))
        except (tokenize.TokenError, IndentationError):
            kept.append(line)
    return "\n".join(kept)


def import_closure(path: pathlib.Path) -> list[pathlib.Path]:
    """Returns a rule and every harness module it can reach by import.

    READING ONE FILE ANSWERS A NARROWER QUESTION THAN THE ONE ASKED. A rule that
    imports a sibling which opens the database reads the database; the arm saw
    only the rule's own text, so moving one `sqlite3.connect` into a helper
    would have let B-049 back into the tier through the front door.

    Args:
        path: The rule to start from.

    Returns:
        The rule and its reachable harness siblings, without duplicates.
    """
    seen, pending = {}, [path]
    while pending:
        current = pending.pop()
        if current.name in seen or not current.is_file():
            continue
        source = current.read_text(encoding="utf-8")
        seen[current.name] = current
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names.add(node.module.split(".")[0])
        for name in names:
            sibling = HARNESS / f"{name}.py"
            if sibling.is_file():
                pending.append(sibling)
    return list(seen.values())


def contract_tier() -> list[str]:
    """Returns the rule files `run.sh` puts in the per-pull-request tier.

    Returns:
        The names in `CONTRACTS=(…)`, or an empty list when the declaration
        cannot be found — which the caller refuses rather than reads as « the
        tier is empty ».
    """
    found = re.search(r"^CONTRACTS=\(([^)]*)\)", RUNNER.read_text(encoding="utf-8"),
                      re.MULTILINE)
    return found.group(1).split() if found else []


def check_contract_tier_reads_no_database() -> int:
    """Refuses a rule that reads a live database from the per-PR tier.

    Returns:
        1 when the tier holds such a rule, or when the tier cannot be read.
    """
    tier = contract_tier()
    if not tier:
        print("check-maquette-unit-tests: `CONTRACTS=(…)` could not be read in "
              f"{RUNNER} — an empty tier satisfies every question anyone asks "
              "of it, so this refuses rather than reports clean.",
              file=sys.stderr)
        return 1
    offenders = []
    for name in tier:
        rule = HARNESS / name
        if not rule.is_file():
            offenders.append((name, "is named by the tier and does not exist"))
            continue
        reached = [module for module in import_closure(rule)
                   if LIVE_DATABASE.search(executable_source(module))]
        if reached:
            through = ("" if reached == [rule] else
                       " through " + ", ".join(sorted(
                           module.name for module in reached
                           if module.name != rule.name)))
            offenders.append((
                name,
                f"reads a live database{through}. The tier runs in CI on every "
                "pull "
                "request touching the maquette, where the operator's databases "
                "do not exist — the rule would fail for a reason foreign to "
                "every change under test (B-049)"))
    for name, why in offenders:
        print(f"  {RUNNER.name}: CONTRACTS names `{name}`, which {why}.",
              file=sys.stderr)
    print(f"check-maquette-unit-tests: {len(tier)} rule(s) in the per-pull-request "
          + (f"tier, {len(offenders)} of them disqualified"
             if offenders else "tier, none reading a live database"))
    return 1 if offenders else 0


def main() -> int:
    """Runs the suite and holds its counts against the floors.

    Returns:
        0 when the suite passed and collected at least the floor, 1 otherwise.
    """
    # THE TIER'S COMPOSITION FIRST, and it runs whatever happens to the suite:
    # it reads two files and needs neither node nor a browser, so a machine
    # without the maquette's dependencies still holds it. Skipping it beside the
    # suite would have made it exactly the kind of check that is only ever green.
    tier = check_contract_tier_reads_no_database()
    if not (DESIGN / "node_modules").is_dir():
        print("check-maquette-unit-tests: SKIPPED — "
              f"{DESIGN}/node_modules is absent, so nothing was measured. "
              "This is not a pass.")
        return tier
    if shutil.which("npm") is None:
        print("check-maquette-unit-tests: SKIPPED — npm is not on the PATH, "
              "so nothing was measured. This is not a pass.")
        return tier

    with tempfile.TemporaryDirectory() as scratch:
        report = pathlib.Path(scratch) / "vitest.json"
        done = subprocess.run(
            ["npm", "test", "--", "--run", "--reporter=json",
             f"--outputFile={report}"],
            cwd=DESIGN, capture_output=True, text=True)
        if not report.is_file():
            print("check-maquette-unit-tests: the runner wrote no report at all")
            print((done.stderr or done.stdout).strip()[-2000:])
            return 1
        result = json.loads(report.read_text(encoding="utf-8"))

    total = result.get("numTotalTests", 0)
    passed = result.get("numPassedTests", 0)
    failed = result.get("numFailedTests", 0)
    files = len(result.get("testResults", []))

    print(f"check-maquette-unit-tests: {files} file(s), {total} test(s), "
          f"{passed} passed, {failed} failed "
          f"(floors: {FILE_FLOOR} file(s), {TEST_FLOOR} test(s))")

    violations = []
    if done.returncode != 0 or failed:
        violations.append(f"{failed} test(s) failed")
    if files < FILE_FLOOR:
        violations.append(f"only {files} file(s) collected, floor is {FILE_FLOOR}")
    if total < TEST_FLOOR:
        violations.append(f"only {total} test(s) collected, floor is {TEST_FLOOR}")
    if violations:
        for violation in violations:
            print(f"  VIOLATION: {violation}")
        return 1
    return tier


if __name__ == "__main__":
    sys.exit(main())

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
import shutil
import subprocess
import sys
import tempfile

DESIGN = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "maquette" / "design"

# What the suite must collect at least. Raised in the commit that adds tests,
# never lowered to let a deletion through.
TEST_FLOOR = 36
FILE_FLOOR = 2


def main() -> int:
    """Runs the suite and holds its counts against the floors.

    Returns:
        0 when the suite passed and collected at least the floor, 1 otherwise.
    """
    if not (DESIGN / "node_modules").is_dir():
        print("check-maquette-unit-tests: SKIPPED — "
              f"{DESIGN}/node_modules is absent, so nothing was measured. "
              "This is not a pass.")
        return 0
    if shutil.which("npm") is None:
        print("check-maquette-unit-tests: SKIPPED — npm is not on the PATH, "
              "so nothing was measured. This is not a pass.")
        return 0

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
    return 0


if __name__ == "__main__":
    sys.exit(main())

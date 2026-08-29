#!/usr/bin/env python3
"""Refuses an « In flight » row that names a wave which has already landed.

THE DEFECT THIS ENDS, and it is the only one this project keeps re-earning.
§ 5 of `docs/reference/frontend-architecture.md` lists the gestures a wave
performs after its merge, and the first of them moves `IMPLEMENTATION.md`'s
« In flight » row back to *none*. That list has been skipped three times out of
four by the file's own count, and the steward has now measured a miss at the
close of L09, of L10 and of L10-bis in a row.

Every previous answer was another sentence on a list nobody reads. § 5 already
says what the answer is instead, and states it as a diagnosis with its mechanism
rather than as code:

    if `personalscraper/__init__.py` on `main` has reached the version the
    « In flight » row names, that wave has landed and the row is stale —
    offline, exact, and it stays green on the wave's own branch, where the two
    differ by construction.

**« HAS REACHED » IS AN ORDERING, NOT AN EQUALITY, and building this found that
out.** Written as equality — the reading the sentence invites — the arm reported
clean over the exact defect it was written for: L10-bis's row named 0.98.51
while `main` carried 0.98.52, because the follow-up pull request that re-anchored
the oracle bumped the version once more. A row is stale the moment `main` reaches
OR PASSES it, and a wave that merges alongside any other change overshoots by
construction. The plan's sentence is amended in the same move, because a
mechanism that cannot catch the case that prompted it is a mechanism nobody
should inherit.

THE COMPARISON IS AGAINST `main`, NOT AGAINST THE WORKING TREE, and that single
detail is the rest of the design. On a wave's own branch both the row and the tree
carry the wave's new version, so comparing the tree against the row would refuse
every open wave — the one state this guard must never refuse. `main` has not
moved yet, so the two differ there and the row is legitimately in flight. The
moment the squash lands, `main` reaches that version and the row is stale by the
same arithmetic.

WHAT IT DOES NOT READ, and saying so is the point:

  - It reads the VERSION, never the pull request number or the branch name. A
    row naming a merged PR while its version still lags is invisible here.
  - It cannot see whether the other two post-merge gestures were performed —
    the archive of `docs/features/<codename>/` and the wave's trace row. Those
    are a different subject and this guard would report clean over both.
  - It needs `origin/main` reachable. A clone without it is refused rather than
    passed: « cannot check » and « nothing to report » are indistinguishable in
    a log, and this repository has paid for that confusion seventy-three times.

AND THE SILENCE IS MADE LEGIBLE. Between waves the row reads *none* and names no
version. § 5 asks explicitly that whoever builds this « make that silence
legible rather than let a vacuous pass read as a verdict », so the arm prints
what it found in the row instead of printing nothing and exiting zero.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "IMPLEMENTATION.md"
PACKAGE_VERSION = "personalscraper/__init__.py"

# The row, and the version inside it. The table's first cell is the label, so
# the row is anchored on it; the version is read from the whole cell because a
# wave writes it in prose (« branch `x`, version 0.98.51, PR #516 ») rather than
# in a column of its own.
IN_FLIGHT_ROW = re.compile(r"^\|\s*\*\*In flight\*\*\s*\|([^|]*)\|", re.M)
VERSION_IN_ROW = re.compile(r"\bversion\s+(\d+\.\d+\.\d+)")
VERSION_IN_PACKAGE = re.compile(r"^__version__\s*=\s*[\"'](\d+\.\d+\.\d+)[\"']", re.M)


def version_on_main() -> tuple[str | None, str | None]:
    """Read the package version as `main` carries it.

    NOT the merge base and not the working tree. The merge base is where the
    branch started, which still names the previous wave's version and would let
    a stale row pass on a long-lived branch; the working tree is the branch's
    own bump, which would refuse every open wave. What settles the question is
    what `main` carries NOW.

    Returns:
        A `(version, failure)` pair. Exactly one is not None.
    """
    tried = ("origin/main", "main")
    for base in tried:
        show = subprocess.run(["git", "show", f"{base}:{PACKAGE_VERSION}"],
                              capture_output=True, text=True, check=False,
                              cwd=ROOT)
        if show.returncode == 0:
            found = VERSION_IN_PACKAGE.search(show.stdout)
            if found:
                return found.group(1), None
            return None, f"{base}:{PACKAGE_VERSION} declares no __version__"
    # THE MESSAGE NAMES WHAT WAS ACTUALLY TRIED. A hardcoded « neither
    # origin/main nor main » survived a mutation that pointed the lookup
    # somewhere else entirely and reported the two names it had not opened —
    # a small lie, and the same species as a guard reporting a corpus it did
    # not read.
    return None, f"none of {', '.join(tried)} is reachable from this clone"


def as_ordered(version: str) -> tuple[int, ...]:
    """Turn a dotted version into something comparable.

    A STRING COMPARISON IS NOT AN ORDERING HERE: « 0.98.9 » sorts above
    « 0.98.52 » on text and below it on arithmetic, and this project is four
    patch releases from meeting that.

    Args:
        version: A dotted release, `0.98.52`.

    Returns:
        Its parts as integers.
    """
    return tuple(int(part) for part in version.split("."))


def arm_in_flight() -> int:
    """Refuse a row naming a version `main` has already reached."""
    if not STATE.is_file():
        print(f"check-implementation-state[in-flight]: {STATE.name} is not in "
              f"the tree — refused rather than passed, because a missing "
              f"subject and a clean subject are the same exit code",
              file=sys.stderr)
        return 1

    row = IN_FLIGHT_ROW.search(STATE.read_text(encoding="utf-8"))
    if row is None:
        print("check-implementation-state[in-flight]: no « In flight » row "
              "could be read in IMPLEMENTATION.md — the row this arm exists to "
              "check is the one it cannot find", file=sys.stderr)
        return 1

    cell = " ".join(row.group(1).split())
    named = VERSION_IN_ROW.search(cell)
    if named is None:
        # THE LEGIBLE SILENCE § 5 asks for. Between waves the row says *none*
        # and there is nothing to compare; printing what was read keeps a
        # vacuous pass from reading as a verdict.
        print(f"check-implementation-state[in-flight]: the row names no "
              f"version, so nothing is in flight to check — read: "
              f"« {cell[:72]} »")
        return 0

    main_version, failure = version_on_main()
    if failure is not None:
        print(f"check-implementation-state[in-flight]: {failure}. This arm "
              f"compares the row's version against what `main` carries, and "
              f"with `main` out of reach it would be reporting « no violation »"
              f" over a comparison it never made", file=sys.stderr)
        return 1

    print(f"check-implementation-state[in-flight]: the row names version "
          f"{named.group(1)}, `main` carries {main_version}")
    if as_ordered(main_version) >= as_ordered(named.group(1)):
        print(f"    IMPLEMENTATION.md: the « In flight » row names version "
              f"{named.group(1)} and `main` carries {main_version}, which has "
              f"reached it, so that wave has landed and the row is stale. Move "
              f"it back to *none* and write the wave's trace into its own row "
              f"— the first post-merge gesture of § 5.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    """Run every arm and report.

    Returns:
        1 when any arm refused, 0 otherwise.
    """
    violations = arm_in_flight()
    print(f"check-implementation-state: {'clean' if not violations else f'{violations} violation(s)'}")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())

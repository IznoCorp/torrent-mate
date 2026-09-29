#!/usr/bin/env python3
"""Every harness Chrome takes the mock keychain, or the guard refuses it.

THE DEFECT THIS ARM CLOSES: each harness rule launches its own ephemeral
Chrome (`p.chromium.launch(channel="chrome")`), and an ephemeral profile still
talks to the real OS keychain for the device-bound session key Chrome asks it
to hold. The key outlives the profile that asked for it — nothing in its
access group's class is ever pruned — so a harness launching Chrome hundreds
of times a run leaves hundreds of rows nobody removes, in a keychain group one
macOS process ends up re-serving whole on every read against it, at a cost
proportional to the group's size.

`common.chrome_launch_args()` answers this once, for every rule, with the
Chromium switch built for exactly this: `--use-mock-keychain`. The fix is a
convention, and a convention with no arm rots the day a new rule launches
Chrome its own way — this arm is what keeps `launch(channel="chrome"` from
ever reappearing bare.

WHAT IT READS: `frontend/maquette/harness/*.py`, as text — the same corpus
`common.py`'s own docstring names as this rule's readers, not parsed as an
AST. A launch call site in this corpus has one shape today, so a regular
expression is answered here the same way `check-poster-box.py` answers a
declared box: matched at the call's own opening, not by balancing every
parenthesis after it.

WHAT IT DOES NOT READ: whether `chrome_launch_args` still adds the flag —
that is `common.py`'s own contract, read by nothing static; a rule that wants
that proof reads `p.chromium.launch`'s recorded arguments at runtime. This arm
answers only "did the call route through the helper", which is the half a
static read can prove.

Exit code is the verdict: 0 when every Chrome launch in the corpus takes the
helper's arguments, 1 naming the ones that do not.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HARNESS = ROOT / "frontend" / "maquette" / "harness"

# A launch call opening on Chrome, whatever comes after it.
CHROME_LAUNCH = re.compile(r'launch\(\s*channel\s*=\s*"chrome"')

# THE ONE SHAPE THE HELPER PRODUCES. `chrome_launch_args` takes an optional
# per-rule `extra` and is always the `args=` value directly — never assigned
# to a local first — so a call routed through it reads `args=chrome_launch_args(`
# right where a bare call would already have its closing paren. A call that
# builds its `args` list some other way and merely PASSES the helper's flag by
# hand would still be refused here, which is the point: the flag is not the
# contract, the helper is.
VALID_CHROME_LAUNCH = re.compile(
    r'launch\(\s*channel\s*=\s*"chrome"\s*,\s*args\s*=\s*chrome_launch_args\s*\('
)

# 179 files read the day this arm was written, none of them named `common.py`
# itself (which defines the helper and calls no launch). A tenth going missing
# is this reader having stopped reading, not the corpus having shrunk.
CORPUS_FLOOR = 160


def sources() -> list[pathlib.Path]:
    """Every harness Python source, sorted.

    Returns:
        The paths this arm reads.
    """
    return sorted(p for p in HARNESS.glob("*.py") if p.is_file())


def violations_in(text: str) -> list[int]:
    """The 1-indexed line of every Chrome launch not routed through the helper.

    Args:
        text: One file's source.

    Returns:
        One entry per offending call, in the order they appear.
    """
    found = []
    for match in CHROME_LAUNCH.finditer(text):
        if VALID_CHROME_LAUNCH.match(text, match.start()) is None:
            found.append(text.count("\n", 0, match.start()) + 1)
    return found


def main() -> int:
    """Holds every harness Chrome launch to the mock-keychain helper.

    Returns:
        0 when the corpus is clean.
    """
    files = sources()
    if len(files) < CORPUS_FLOOR:
        print(f"check-mock-keychain: {len(files)} file(s) read under "
              f"{HARNESS.relative_to(ROOT)} — under the floor of {CORPUS_FLOOR}. "
              "A reader that has stopped reading refuses nothing.",
              file=sys.stderr)
        return 1

    violations: list[str] = []
    launches = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        launches += len(CHROME_LAUNCH.findall(text))
        for line in violations_in(text):
            violations.append(f"{path.relative_to(ROOT)}:{line}")

    if violations:
        print(f"check-mock-keychain: {len(violations)} violation(s) — a Chrome "
              "launch bypassing common.chrome_launch_args() re-opens the "
              "keychain bloat this arm exists to close:", file=sys.stderr)
        for entry in violations:
            print(f"  {entry}", file=sys.stderr)
        return 1

    print(f"check-mock-keychain: {len(files)} file(s) read under "
          f"{HARNESS.relative_to(ROOT)} (floor {CORPUS_FLOOR}), {launches} "
          "Chrome launch(es), 0 violation(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

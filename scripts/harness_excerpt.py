#!/usr/bin/env python3
"""What `webui/harness/run.sh` prints of a failed rule's log.

A rule's log can run to hundreds of lines; the summary shows the lines that say
why it failed. It used to be a `grep` for twelve lines matching `FAIL`, `Error`,
`Traceback`…, which kept a traceback's first and last lines and dropped every
`File …, line N` frame between them (B-571): `pwa.py` and `entry.py` each reach
two hosts by two `goto` calls, and a timeout's own line could not say which one
expired. A traceback is now printed whole — its frames are what name the call.

Usage:
    python3 scripts/harness_excerpt.py < rule.out
"""
from __future__ import annotations

import re
import sys

# A line that says a hold or the run failed.
FAILING = re.compile(r"FAIL|Error|error:|violation|TIMED OUT|■")

# How many failing lines are kept, and how many lines of a traceback.
FAILING_LINES = 12
TRACEBACK_LINES = 60


def excerpt(log: str) -> str:
    """The part of a rule's log that says why it failed.

    Args:
        log: The rule's whole output.

    Returns:
        The failing lines before the last traceback, then that traceback whole
        (its frames included); or, with no traceback, the failing lines; or,
        with neither, the log's last lines.
    """
    lines = log.splitlines()
    starts = [index for index, line in enumerate(lines) if line.startswith("Traceback")]
    if starts:
        before = [line.strip() for line in lines[:starts[-1]] if FAILING.search(line)]
        trace = lines[starts[-1]:][:TRACEBACK_LINES]
        return "\n".join(before[:FAILING_LINES] + trace) + "\n"
    failing = [line.strip() for line in lines if FAILING.search(line)]
    return "\n".join(failing[:FAILING_LINES] or lines[-FAILING_LINES:]) + "\n"


if __name__ == "__main__":
    sys.stdout.write(excerpt(sys.stdin.read()))

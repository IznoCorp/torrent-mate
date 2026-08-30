#!/usr/bin/env python3
"""Captures and compares the per-rule hold counts of the maquette harness suite.

WHY THIS EXISTS. ACC-08 promises the suite is green at UNCHANGED per-rule hold
counts, and the criterion named `run.sh`. But `run.sh` captures each rule's
output into a variable and prints it only on FAILURE — a passing rule's
`N rules EXECUTED — no violation` never reaches the log, so "unchanged" was
not obtainable from the command the criterion named. This tool runs every rule
the way `run.sh` does — the same glob, `harness/*.py` minus `common.py` — and
KEEPS each one's printed hold count instead of discarding it.

WHY THE COUNT MATTERS. A rule that still passes while holding FEWER things has
stopped measuring, and the count is the only thing that says so. Phases 2 to 6
of the lot promise the rendering and the behaviour are unchanged; the count is
what makes the second half of that promise checkable.

WHAT IS PARSED. Two shapes, tried in this order — the first that matches
decides, so the tally can never override a real count line:

    A printed figure, read from the line whose PURPOSE is to report how many
    holds executed:
        1. `N rules EXECUTED`       — the common.Journal rules
        2. `N <words> EXECUTED`     — chrome.py, pwa.py, cards.py
        3. `N/M rules executed`     — audit.py, audit2.py (N is the executed set)
        4. `N/M states conform`     — states.py (M is the total checked)
        5. `N/M renders conform`    — scen.py (M is the total checked)
      The LAST match of the pattern is used, because the summary is the last
      thing a rule prints (shell.py prints it twice, with the same figure).

    A per-hold PASS/FAIL tally, used ONLY when no figure line exists: the
    number of lines matching `^\\s+(PASS|FAIL)\\b` (bugs.py, filters.py,
    scroll.py). Each such line is one hold carrying its verdict. The tally
    counts verdict-PREFIXED lines only, and it under-counts honestly: a hold
    whose verdict prints mid-line (filters.py's category sum), a hold that
    prints nothing on the happy path (pop.py's outline FAIL), and a verdict
    printed with no indent (sweep.py) are all invisible to it. A named
    under-count is the trade for a rule that otherwise reports no figure at
    all.

UNPARSEABLE IS A STATE, NOT A ZERO. A rule whose output matches none of the
patterns is recorded as unparseable, NAMED, with the reason — never silently
skipped, never defaulted to 0, because a missing count that reads as 0 is the
failure mode this tool exists to catch. `--compare` treats every transition
to or from unparseable as a movement, and lists the rules unparseable on both
sides on every run, so the blind spot stays visible.

THE COVERAGE CEILING IS STATED, NOT HIDDEN. Some rules report a hold count;
the others print a prose verdict and are compared on their exit status alone.
The two figures are COUNTED on every run, printed on the `coverage:` line and
recorded in the baseline's `what` field — they are deliberately not repeated
here, because a figure written where nothing recounts it is a figure that goes
stale unread, and this one had. That line is the honest ceiling of ACC-08. A rule with no count is compared on EXIT STATUS — the baseline and
the run both record each rule's exit code, and a no-count rule that goes from
green to red fails the comparison like any movement.

A FAILING RULE IS VISIBLE ON ITS OWN LINE. The progress line of a rule whose
exit code is not 0 ends with `— RULE FAILED (exit N)`, and the final summary
NAMES every failed rule — a detail line that reads like a passing one while
only the summary says otherwise is an instrument that cannot be believed.

MODES:

    --record FILE    runs the suite (one headless Chrome per rule, several
                     at a time) and writes the table to FILE. Exits 1 if any rule
                     failed — a baseline is only meaningful on a green suite
                     — but writes the table anyway so the failure can be
                     read.
    --compare FILE   runs the suite and exits 1 naming every rule whose count
                     MOVED, in either direction, with before -> after. A
                     count that fell is a rule that stopped measuring; a
                     count that rose is a rule measuring something it was not
                     asked to. Rules that APPEARED or DISAPPEARED since the
                     baseline are reported the same way: a rule vanishing
                     must never look like a rule passing.
    --only RULES     comma-separated rule basenames, for both modes: run only
                     those. A quick mutation proof compares a small recorded
                     subset instead of the whole suite. `--record --only`
                     refuses unknown names; `--compare --only` accepts a name
                     that has left the disk since the baseline, so its
                     disappearance is reported instead of rejected.

Like `run.sh`, both modes build the prototype and copy it where the harness
reads it first — a stale copy at /tmp/tm-refonte/wrapped.html measures the
previous build in silence. Unlike `run.sh`, this tool does not start the
harness host: if http://127.0.0.1:8899/ does not answer 200, run
`frontend/maquette/harness/run.sh --contracts` once (it builds, copies and
starts the host), then retry.

The baseline recorded at commit c78c9d66 (2026-08-21) lives at
`frontend/maquette/hold-counts-baseline.json`.
"""

from __future__ import annotations

import argparse
import atexit
import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "frontend" / "maquette" / "harness"
DESIGN = ROOT / "frontend" / "maquette" / "design"
SERVED = Path("/tmp/tm-refonte")

# The harness owns the served copy: its lock, its stamp, and how it is assembled.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                       / "frontend" / "maquette" / "harness"))
import served_copy  # noqa: E402 — the path line above must run first
PROTOTYPE_URL = "http://127.0.0.1:8899/"
RULE_TIMEOUT_SECONDS = 600


def default_jobs():
    """Says how many rules to run at once when nothing asked for a number.

    The rules are independent processes reading a static file server, so what
    bounds them is the machine — each one launches its own headless Chrome —
    not correctness. `TM_HARNESS_JOBS` is the same knob `run.sh` reads, so one
    setting governs both runners; `TM_HARNESS_JOBS=1` restores the strictly
    serial run.

    Returns:
        The requested count, at least 1. A value that is not a positive
        integer is ignored rather than obeyed: a typo in an environment
        variable must not silently halve the parallelism.
    """
    asked = os.environ.get("TM_HARNESS_JOBS", "").strip()
    if asked.isdigit() and int(asked) > 0:
        return int(asked)
    return os.cpu_count() or 4

# (label, pattern, shape, group) — tried in order, first pattern with a match
# wins. Shape "number": the count is a figure the rule printed; the LAST match
# is used because the summary is the last thing a rule prints. Shape "tally":
# the count is the NUMBER of matching lines — each line is one hold carrying
# its verdict. The tally sits LAST on purpose: it fires only for rules that
# print no figure at all, so it can never override a real count line.
COUNT_PATTERNS = (
    ("common.Journal summary", re.compile(r"(\d+) rules EXECUTED"),
     "number", 1),
    ("own EXECUTED count line",
     re.compile(r"(\d+)[A-Za-z0-9/ -]+ EXECUTED"), "number", 1),
    ("audit rules-executed line", re.compile(r"(\d+)/(\d+) rules executed"),
     "number", 1),
    ("states-conform verdict", re.compile(r"(\d+)/(\d+) states conform"),
     "number", 2),
    ("renders-conform verdict", re.compile(r"(\d+)/(\d+) renders conform"),
     "number", 2),
    ("per-hold PASS/FAIL tally", re.compile(r"^\s+(PASS|FAIL)\b",
                                            re.MULTILINE), "tally", 0),
)


def rule_scripts():
    """Returns the rule scripts, in the order run.sh runs them.

    Returns:
        The basenames of every `harness/*.py` file except `common.py`,
        sorted — bash glob expansion and `Path.glob` both order
        alphabetically, so this is the order run.sh's loop uses.
    """
    return sorted(p.name for p in HARNESS.glob("*.py")
                  if p.name != "common.py")


def select_rules(spec, allowed):
    """Splits and validates a `--only` spec against `allowed` basenames.

    Args:
        spec: The raw comma-separated `--only` value.
        allowed: An iterable of basenames the selection may name.

    Returns:
        A (selected, unknown) pair: the deduplicated, stripped names in the
        order given, and the names among them that `allowed` does not know.
    """
    selected = list(dict.fromkeys(
        name.strip() for name in spec.split(",") if name.strip()))
    known = set(allowed)
    return selected, sorted(set(selected) - known)


def hold_the_served_copy():
    """Takes the served copy for this whole run, and gives it back at exit.

    THE COPY IS HELD FOR THE WHOLE RUN and not only for the rebuild. This tool
    rebuilds the prototype and then reads 79 rules against it, which is exactly
    the shape B-256 describes: without the lock a suite can start beside it, and
    without the stamp neither would ever know they had swapped prototypes.

    `atexit` rather than a `try`/`finally` around the body: the release must
    happen on an unhandled exception and on a `SystemExit` alike, and wrapping
    two hundred lines to say so would bury what they do.
    """
    served_copy.acquire(f"harness-hold-counts, pid {os.getpid()}", os.getpid())
    atexit.register(served_copy.release, os.getpid())


def ensure_fresh_prototype():
    """Builds the prototype and copies it where the harness reads it.

    Mirrors run.sh: a stale `wrapped.html` measures the previous build and
    says nothing, which has cost this project two debugging sessions.

    Raises:
        SystemExit: If `npm run build` fails — the exit code is the message.
    """
    print("Building the prototype — a stale copy measures the previous build…",
          file=sys.stderr)
    build = subprocess.run(["npm", "run", "build"], cwd=DESIGN,
                           capture_output=True, text=True)
    if build.returncode != 0:
        print(f"npm run build failed:\n{build.stderr[-800:]}", file=sys.stderr)
        raise SystemExit(2)
    # PUBLISHED THROUGH THE HARNESS'S OWN FUNCTION, which also writes the
    # stamp (B-256). This step used to be a third copy of the same assembly —
    # `run.sh` and `scripts/mutate.sh` had the other two — and it took neither
    # the lock nor the stamp, so a suite running beside THIS tool read its
    # prototype and said nothing. It had also fallen behind: `sw.js` and
    # `build.json` joined the copy at L11 here and nowhere else, so a copy this
    # tool made served a worker from a previous build.
    served_copy.publish(DESIGN)


def host_serves_prototype():
    """Checks that the harness host answers 200 on the wrapped prototype.

    Returns:
        True when the host answers 200 within 10 seconds; False when it is
        down or serving something else — a suite run against a missing host
        would fail 51 times for a reason that has nothing to do with the
        rules.
    """
    try:
        with urllib.request.urlopen(PROTOTYPE_URL, timeout=10) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def parse_hold_count(output):
    """Parses a rule's hold count from its own printed output.

    Args:
        output: The rule's stdout and stderr, merged the way run.sh merges
            them with `2>&1`.

    Returns:
        A (count, pattern) pair; count is None when no pattern matched —
        an unparseable count is a named unknown, never a 0.
    """
    for label, pattern, shape, group in COUNT_PATTERNS:
        matches = pattern.findall(output)
        if not matches:
            continue
        if shape == "tally":
            # Each matching line is one hold; the count is how many there
            # are, not a figure any of them prints.
            return len(matches), label
        # A one-group pattern yields plain strings, a multi-group one yields
        # tuples — normalizing keeps the group index meaningful.
        last = matches[-1]
        if not isinstance(last, tuple):
            last = (last,)
        return int(last[group - 1]), label
    return None, ""


def run_rule(name):
    """Runs one rule script the way run.sh does and parses its hold count.

    Args:
        name: The rule's basename under `harness/`.

    Returns:
        A dict with `exit` (the process exit code, or "timeout"), `count`
        (the parsed hold count, None when unparseable) and `pattern` (which
        pattern matched, for the progress line).
    """
    try:
        proc = subprocess.run(
            [sys.executable, str(HARNESS / name)],
            cwd=HARNESS, capture_output=True, text=True,
            timeout=RULE_TIMEOUT_SECONDS,
        )
        exit_code = proc.returncode
        output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        print(f"    TIMED OUT after {RULE_TIMEOUT_SECONDS}s", file=sys.stderr)
        return {"exit": "timeout", "count": None, "pattern": ""}
    count, pattern = parse_hold_count(output)
    return {"exit": exit_code, "count": count, "pattern": pattern}


def run_suite(only=None, jobs=None):
    """Runs the rules in run.sh's order, printing progress to stderr.

    Args:
        only: An optional list of basenames restricting the run; a selected
            name that has left the disk since the baseline keeps its slot
            and is reported on the progress line instead of being hidden.
        jobs: How many rules to run at once; None asks default_jobs().

    Returns:
        A dict mapping each rule's basename to its run_rule() result. A
        rule that could not be run is absent from the dict — that absence
        is what --compare reads as MISSING.
    """
    available = rule_scripts()
    if only is None:
        names = available
    else:
        names = [name for name in available if name in only]
        # A selected rule that is no longer on disk keeps its slot, so the
        # runner can say so rather than silently drop the selection.
        names += [name for name in only if name not in available]
    scope = (f"subset ({len(names)} of {len(available)} rule(s) — --only)"
             if only is not None
             else f"the full suite ({len(names)} rule(s))")
    jobs = max(1, min(jobs or default_jobs(), len(names) or 1))
    print(f"running {scope} — one headless Chrome per rule, {jobs} at a time",
          file=sys.stderr)
    results = {}
    # The rules run concurrently, but the progress lines are printed in the
    # RULE order, not the order they finished: `map` yields in submission
    # order. A progress log whose order depends on scheduling cannot be
    # diffed against the previous one, which is most of what it is read for.
    # The trade is live feedback — a slow early rule holds back the lines of
    # the rules that finished behind it.
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
        planned = [(name, pool.submit(run_rule, name)
                    if (HARNESS / name).is_file() else None)
                   for name in names]
        for index, (name, future) in enumerate(planned, start=1):
            print(f"[{index}/{len(names)}] {name}", end="",
                  file=sys.stderr, flush=True)
            if future is None:
                print(" — not on disk, skipped", file=sys.stderr, flush=True)
                continue
            result = future.result()
            parts = []
            if result["count"] is None:
                parts.append(f"unparseable (exit {result['exit']})")
            else:
                parts.append(f"{result['count']} hold(s) — {result['pattern']}")
            # A failing rule must read as failing ON ITS OWN LINE — a detail
            # line shaped like a passing one, with only the summary saying
            # otherwise, is an instrument that cannot be believed.
            if result["exit"] == "timeout":
                parts.append("RULE FAILED (timed out)")
            elif result["exit"] != 0:
                parts.append(f"RULE FAILED (exit {result['exit']})")
            print(f" — {' — '.join(parts)}", file=sys.stderr, flush=True)
            results[name] = result
    return results


def rule_entry(result):
    """Builds one baseline entry from a rule's run result.

    Args:
        result: A run_rule() dict.

    Returns:
        The JSON entry. Every entry records `exit` — the process exit code,
        or "timeout" — so a rule with no count still has a status to be
        compared on. A parseable run adds `count` and the `source` pattern
        that produced it; `reason` explains a null or a failure.
    """
    if result["exit"] == "timeout":
        return {"exit": "timeout", "count": None,
                "reason": f"rule timed out after {RULE_TIMEOUT_SECONDS}s"}
    if result["count"] is not None:
        entry = {"exit": result["exit"], "count": result["count"],
                 "source": result["pattern"]}
        if result["exit"] != 0:
            entry["reason"] = (f"rule failed (exit {result['exit']}); the "
                               f"count is what it printed")
        return entry
    reason = ("no recognized executed-count line in its output"
              if result["exit"] == 0
              else f"rule failed (exit {result['exit']}) and printed no "
                   f"count line")
    return {"exit": result["exit"], "count": None, "reason": reason}


def current_commit():
    """Returns the HEAD commit sha, so a baseline names what it measured."""
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True)
    return proc.stdout.strip()


def provenance_of(commit):
    """Says whether a baseline's commit can still be placed in this history.

    A SQUASH MERGE ANSWERS « no », and that is the case this exists for. A
    baseline is recorded on a feature branch and names the branch commit it
    measured; squashing replaces every one of those with a single new commit,
    so the sha in the file stops existing — on a fresh clone it is not there at
    all. Nothing was wrong with the measurement. The pointer went dangling,
    silently, and `hold-counts-baseline.json` sat that way for four days under a
    green gate because this tool read the field only to print it.

    Args:
        commit: The sha the baseline carries.

    Returns:
        One of `"ancestor"`, `"unreachable"` (the object is not in this clone)
        or `"not-an-ancestor"` (it exists but is not in HEAD's history).
    """
    if not commit or commit == "unknown":
        return "unreachable"
    exists = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                            cwd=ROOT, capture_output=True, check=False)
    if exists.returncode != 0:
        return "unreachable"
    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=ROOT, capture_output=True, check=False)
    return "ancestor" if ancestry.returncode == 0 else "not-an-ancestor"


def print_coverage(results):
    """States the coverage ceiling of the run that just happened.

    Args:
        results: The run_suite() dict.

    The sentence is the honest limit of ACC-08: rules without a count are
    compared on their exit status alone, and this says so out loud.
    """
    total = len(results)
    parseable = sum(1 for result in results.values()
                    if result["count"] is not None)
    print(f"coverage: {parseable} of {total} rule(s) report a hold count; "
          f"the other {total - parseable} print a prose verdict and are "
          f"compared on their exit status alone.")


def _print_host_hint():
    """Prints the one command that rebuilds, copies and starts the host."""
    print(f"no harness host answers on {PROTOTYPE_URL} — run "
          f"frontend/maquette/harness/run.sh --contracts once (it builds, "
          f"copies and starts the host), then retry.", file=sys.stderr)


def cmd_record(target, only=None, jobs=None):
    """Runs the suite and writes the per-rule table to `target`.

    Args:
        target: The JSON file to write.
        only: An optional list of basenames restricting the run.
        jobs: How many rules to run at once; None asks default_jobs().

    Returns:
        0 when the suite was green, 1 when any rule failed (the table is
        written either way, but a baseline recorded on a red suite must not
        be committed), 2 when the host is down, the build failed, or a
        selected rule name is unknown.
    """
    if only is not None:
        selected, unknown = select_rules(only, rule_scripts())
        if unknown:
            print(f"unknown rule(s) for --only: {', '.join(unknown)}",
                  file=sys.stderr)
            return 2
        only = selected
    hold_the_served_copy()
    ensure_fresh_prototype()
    if not host_serves_prototype():
        _print_host_hint()
        return 2
    results = run_suite(only, jobs=jobs)
    rules = {name: rule_entry(result) for name, result in results.items()}
    parseable = [entry for entry in rules.values()
                 if entry["count"] is not None]
    unparseable = [name for name, entry in rules.items()
                   if entry["count"] is None]
    failed = [name for name, result in results.items() if result["exit"] != 0]
    payload = {
        "what": (
            "Per-rule hold counts of the maquette harness suite — the figure "
            "each rule prints as the number of holds it executed. ACC-08 "
            "compares against this file: a wave is green only at unchanged "
            f"per-rule hold counts. {len(parseable)} of {len(results)} "
            f"rule(s) report a hold count; the other {len(unparseable)} "
            "print a prose verdict and are compared on their exit status "
            "alone. A count of null is a named unparseable, never a zero. A "
            "count from the per-hold PASS/FAIL tally counts verdict-prefixed "
            "hold lines only — a hold whose verdict prints mid-line or "
            "conditionally is not visible to it."
        ),
        "taken_at_commit": current_commit(),
        "taken_on": datetime.date.today().isoformat(),
        "suite": f"{len(results)} of {len(rule_scripts())} rule(s)",
        "host": PROTOTYPE_URL,
        "rules": rules,
        "totals": {
            "rules": len(results),
            "parseable": len(parseable),
            "unparseable": len(unparseable),
            "holds": sum(entry["count"] for entry in parseable),
            "failed": len(failed),
        },
    }
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    os.replace(tmp, target)
    print(f"recorded {len(results)} rule(s) to {target} at commit "
          f"{payload['taken_at_commit'][:8]}")
    if unparseable:
        print(f"{len(unparseable)} rule(s) unparseable: "
              f"{', '.join(unparseable)}")
    print(f"{len(parseable)} rule(s) parseable — "
          f"{payload['totals']['holds']} holds in total")
    print_coverage(results)
    if failed:
        named = ", ".join(f"{name} (exit {results[name]['exit']})"
                          for name in failed)
        print(f"harness: {len(failed)} of {len(results)} rule(s) FAILED — "
              f"{named} — the table was written, but a baseline recorded on "
              f"a red suite must not be committed.", file=sys.stderr)
        return 1
    print(f"harness: {len(results)} rule(s), no violation.")
    return 0


def cmd_compare(baseline_path, only=None, jobs=None):
    """Runs the suite and fails on ANY movement against the baseline.

    Args:
        baseline_path: A file written by --record.
        only: An optional list of basenames restricting the run. Unlike
            --record, a selected name may have left the disk since the
            baseline: it is then reported MISSING, not rejected.
        jobs: How many rules to run at once; None asks default_jobs().

    Returns:
        0 when the suite is green at unchanged per-rule hold counts; 1 when
        any rule failed, moved (either direction), appeared or disappeared,
        or moved its exit status while holding no count; 2 when the baseline
        cannot be read, a selected name is unknown to both disk and
        baseline, or the host is down.
    """
    if not baseline_path.is_file():
        print(f"baseline not found: {baseline_path}", file=sys.stderr)
        return 2
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        base_rules = baseline["rules"]
        base_commit = baseline.get("taken_at_commit", "unknown")
    except (json.JSONDecodeError, KeyError) as exc:
        print(f"unreadable baseline {baseline_path}: {exc}", file=sys.stderr)
        return 2

    # THE PROVENANCE GATE, AND IT REFUSES WHERE THE ORACLE ONLY WARNS.
    #
    # `oracle.py --check` appends « NOT an ancestor of HEAD » to its output and
    # compares anyway. That is a defensible choice for a 36 000-line rendering
    # reference. It is the wrong one here, and the evidence is this very file:
    # the baseline shipped pointing at `c7714c38`, a commit the L02 squash
    # replaced, and nothing said so for four days — because a warning nobody
    # reads and a field nobody checks fail the same way.
    #
    # What a hold-count comparison IS makes the difference. It is the whole of
    # « the suite is green at unchanged hold counts », the proof that catches
    # what a green suite cannot: at L02 only this comparison saw the logout
    # contract fall. Run against a baseline whose provenance cannot be
    # established, that proof degrades into a sentence.
    #
    # Refusing is affordable because it enforces a step that already exists: a
    # wave re-records this file at its close, exactly as it re-records the
    # oracle's reference.
    provenance = provenance_of(base_commit)
    if provenance != "ancestor":
        why = ("does not exist in this clone" if provenance == "unreachable"
               else "exists but is not an ancestor of HEAD")
        print(f"refusing to compare: the baseline names {base_commit[:8]}, "
              f"which {why}.\n"
              "  A squash merge replaces the commit a branch-recorded baseline "
              "names, so the pointer goes dangling while every count in the "
              "file stays perfectly good.\n"
              "  Re-record it on this tree, the full suite:\n"
              f"    python3 scripts/harness-hold-counts.py --record "
              f"{baseline_path}", file=sys.stderr)
        return 2

    if only is not None:
        allowed = set(rule_scripts()) | set(base_rules)
        selected, unknown = select_rules(only, allowed)
        if unknown:
            print(f"unknown rule(s) for --only: {', '.join(unknown)}",
                  file=sys.stderr)
            return 2
        only = selected
        base_rules = {name: entry for name, entry in base_rules.items()
                      if name in only}

    hold_the_served_copy()
    ensure_fresh_prototype()
    if not host_serves_prototype():
        _print_host_hint()
        return 2
    print(f"baseline taken at commit {base_commit[:8]}", file=sys.stderr)
    results = run_suite(only, jobs=jobs)

    changed = []          # (name, before, after) — before/after: int or None
    exit_changed = []     # (name, before_exit, after_exit) — countless rules
    unparseable_both = []
    failed = [name for name, result in results.items() if result["exit"] != 0]

    for name in sorted(results):
        if name not in base_rules:
            continue
        before = base_rules[name].get("count")
        after = results[name]["count"]
        if before is None and after is None:
            # No count on either side: the recorded exit status is all the
            # rule can be held to. Green -> red must fail like any movement.
            if ("exit" in base_rules[name]
                    and base_rules[name]["exit"] != results[name]["exit"]):
                exit_changed.append((name, base_rules[name]["exit"],
                                     results[name]["exit"]))
            else:
                unparseable_both.append(name)
        elif before != after:
            changed.append((name, before, after))
    new = [name for name in sorted(results) if name not in base_rules]
    missing = [name for name in sorted(base_rules) if name not in results]

    for name, before, after in changed:
        if before is None:
            print(f"CHANGED  {name}: unparseable -> {after} "
                  f"(newly parseable)")
        elif after is None:
            print(f"CHANGED  {name}: {before} -> unparseable "
                  f"(stopped printing its count)")
        else:
            delta = after - before
            direction = "fell" if delta < 0 else "rose"
            print(f"CHANGED  {name}: {before} -> {after} "
                  f"({direction} by {abs(delta)})")
    for name, before_exit, after_exit in exit_changed:
        print(f"CHANGED  {name}: exit {before_exit} -> exit {after_exit} "
              f"(no hold count on either side)")
    for name in missing:
        before = base_rules[name].get("count")
        was = str(before) if before is not None else "unparseable"
        print(f"MISSING  {name} (baseline had {was})")
    for name in new:
        after = results[name]["count"]
        now = str(after) if after is not None else "unparseable"
        print(f"NEW      {name} ({now})")

    if failed:
        named = ", ".join(f"{name} (exit {results[name]['exit']})"
                          for name in failed)
        print(f"harness: {len(failed)} of {len(results)} rule(s) FAILED — "
              f"{named} — run the rule alone to see which hold fell.")
    else:
        print(f"harness: {len(results)} rule(s), no violation.")
    print(f"{len(changed)} rule(s) changed hold count")
    if exit_changed:
        print(f"{len(exit_changed)} rule(s) changed exit status while "
              f"holding no count")
    if missing:
        print(f"{len(missing)} rule(s) missing since the baseline")
    if new:
        print(f"{len(new)} rule(s) new since the baseline")
    if unparseable_both:
        print(f"{len(unparseable_both)} rule(s) hold count unparseable "
              f"(baseline and now): {', '.join(unparseable_both)}")
    print_coverage(results)
    return 1 if (changed or exit_changed or missing or new or failed) else 0


def main(argv=None):
    """Parses the command line and dispatches to --record or --compare.

    Args:
        argv: The argument list; None for sys.argv.

    Returns:
        The process exit code: 0 green, 1 movement or failure, 2 unusable
        environment (build failed, host down, baseline unreadable, unknown
        rule name).
    """
    parser = argparse.ArgumentParser(
        description="Captures and compares the maquette harness per-rule "
                    "hold counts.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", metavar="FILE",
                      help="run the suite and write the per-rule table to "
                           "FILE")
    mode.add_argument("--compare", metavar="FILE",
                      help="run the suite and fail on any movement against "
                           "FILE")
    parser.add_argument("--only", metavar="RULES",
                        help="comma-separated rule basenames — run and "
                             "compare only those (a quick mutation proof "
                             "compares a small recorded subset instead of "
                             "the whole suite)")
    parser.add_argument("--jobs", metavar="N", type=int, default=None,
                        help="how many rules to run at once (default: the "
                             "machine's processor count, or TM_HARNESS_JOBS; "
                             "1 runs them strictly one after another)")
    args = parser.parse_args(argv)
    only = None if args.only is None else args.only
    if args.record:
        return cmd_record(Path(args.record), only=only, jobs=args.jobs)
    return cmd_compare(Path(args.compare), only=only, jobs=args.jobs)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""The two arms that COUNT French rather than refuse it.

SPLIT OUT OF `check-no-french.py`, which arm 13 pushed past the 1 000-line
block. The seam is not arbitrary. The other eleven arms REFUSE French; these
two do something categorically different — they measure an exemption the
operator GRANTED and hold it to a baseline, so it can only ever shrink.
`frontend/src` has no i18n layer at all and its French is accepted; the French
a test asserts is the app's own rendered output and is legitimate. Neither may
GROW, and both baselines live in `scripts/french-exemption-baseline.json`.

An exemption nobody counts is indistinguishable from an oversight — which is
exactly how 842 of these strings sat under a green gate.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from _repo_paths import DESIGN

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nofrench_lexicon import (  # noqa: E402
    walk,
    ROOT, examined, exempted, offending_string, read, relative,
)
from nofrench_scan import (  # noqa: E402
    python_string_literals, script_string_literals,
)


# JSX text for the EXEMPTION COUNT. Deliberately a distinct name from arm 1's
# `JSX_TEXT` above: defining a second `JSX_TEXT` here shadowed it and quietly
# dropped that arm's coverage from 124 rendered strings to 59.
JSX_TEXT_NODE = re.compile(  # french-ok: a Latin-1 letter RANGE, not a word
    r">([^<>{}]*[A-Za-zÀ-ÿ][^<>{}]*)<")


def jsx_text(source: str) -> list[str]:
    """Returns the text nodes of a JSX source.

    Interface copy in JSX carries no quotes, so a scanner reading only string
    literals walks past the very thing it is looking for.

    Args:
        source: The `.tsx` source.

    Returns:
        Each text node, whitespace-trimmed, long enough to be a sentence.
    """
    return [body.strip() for body in JSX_TEXT_NODE.findall(source)
            if len(body.strip().split()) >= 3]


def check_app_interface_text(violations: list[str]) -> None:
    """Measures the French interface text `frontend/src` carries, and says so.

    THIS ARM DOES NOT REFUSE. `frontend/src` is the React application the
    maquette shell is being built to replace, and it has no i18n layer at all —
    no `i18n/` directory, no `useTranslation`. Its French is written straight
    into the components. The operator ruled that this is an ACCEPTED state
    rather than a defect: moving that copy into resources would be work thrown
    away with the app that holds it. §Language names two i18n surfaces — the
    maquette shell and `serve.py`'s pages — and this is deliberately neither.

    So why an arm at all? Because the string arm walks the shell, the servers,
    the harness tools and the repository tools, and NOT this tree — and an
    unread scope reports « no violation » about a place it never opened. That
    is how 842 French strings sat under a green gate, and how `id="coquille"`
    and three all-French shell scripts sat under it before them. An exemption
    nobody counts is indistinguishable from an oversight.

    The count is therefore published in the ledger beside every other scope. It
    reads the whole tree, so it drops to zero only if the tree empties — and
    the ledger already refuses a scope that examined NOTHING.

    Args:
        violations: The accumulator every arm appends to. Nothing is added:
            this arm measures, and the measurement is its whole output.
    """
    app = ROOT / "frontend" / "src"
    production = tests = 0
    for path in sorted(walk(app, "*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        source = read(path)
        literals = script_string_literals(source)
        examined["interface text / app (exempt)"] += len(literals)
        # JSX TEXT CARRIES NO QUOTES, which is the very shape arm 1 exists to
        # find — and this arm walked straight past it, so the published number
        # was short by ~9% and could not move when French JSX copy was added.
        found = sum(1 for _, body in literals if offending_string(body))
        found += sum(1 for body in jsx_text(source) if offending_string(body))
        if path.name.endswith((".test.ts", ".test.tsx")) or "__tests__" in path.parts:
            tests += found
        else:
            production += found
    # SPLIT, because they are not the same thing. French a test ASSERTS is the
    # app's rendered output — CLAUDE.md already rules it legitimate — and it was
    # 72% of the headline figure, masking the number that matters.
    exempted["french interface strings / app (production)"] = production
    exempted["french interface strings / app (asserted by tests)"] = tests

    # A RATCHET, not a print. The count drifted +7 inside the very PR that
    # introduced it as a control, and nothing noticed: a number nobody compares
    # is a number nobody reads. Only the PRODUCTION figure is pinned — lowering
    # it is the only thing that lowers the baseline.
    baseline_path = ROOT / "scripts" / "french-exemption-baseline.json"
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["production"]
    except (OSError, ValueError, KeyError):
        violations.append(
            f"{relative(baseline_path)} is missing or unreadable — the exemption "
            "has no baseline, so nothing would notice it growing")
        return
    count_shell_markup_text()
    if production > baseline:
        violations.append(
            f"the accepted French in `frontend/src` GREW: {production} production "
            f"strings against a baseline of {baseline}. The exemption covers what "
            "is already there, never more — move the new copy out, or lower the "
            f"baseline in {relative(baseline_path)} deliberately.")


# The shell's markup: text nodes and the labels a reader hears, once the
# comments, scripts and styles are taken out.
SHELL_MARKUP = DESIGN / "index.html"
MARKUP_NOISE = re.compile(r"<!--.*?-->|<(script|style)\b.*?</\1>", re.S | re.I)
MARKUP_TEXT = re.compile(r">([^<>]*[^\s<>][^<>]*)<")
MARKUP_LABEL = re.compile(r'\s(?:aria-label|alt|title|placeholder)="([^"]+)"')


def shell_markup_strings(source: str) -> list[str]:
    """Returns what the shell's markup shows or says to a reader.

    Args:
        source: The text of `design/index.html`.

    Returns:
        Each text node and each spoken label, whitespace-trimmed.
    """
    body = MARKUP_NOISE.sub("", source)
    return [text.strip() for text in MARKUP_TEXT.findall(body) + MARKUP_LABEL.findall(body)]


def count_shell_markup_text() -> None:
    """Names, every run, the shell markup's text that no arm reads (B-390).

    THE MARKUP STAYS IN `index.html` BY DECISION (`app/entry.ts`): the splash
    must paint before the bundle runs, and `serve.py` extracts the sign-in gate
    as the design host's own page. Its copy is therefore outside `fr.json` and
    outside every arm — the Strings arm is rooted on `design/src`, the `data-*`
    arm reads attributes. A green run once stood as evidence that the file's
    French was allowed when no arm had read it; the count says which it is.
    """
    exempted["strings read by no arm / design/index.html (markup, app/entry.ts)"] = len(
        shell_markup_strings(read(SHELL_MARKUP)))


def check_test_prose(violations: list[str]) -> None:
    """Reads the French in `tests/`, counts it, and refuses it growing.

    UNREAD AND UNCOUNTED, which is the worst of the two states. CLAUDE.md is
    unambiguous that docstrings are English and that a tool's messages are
    English — and no arm opened `tests/` for strings at all, so 413 French
    literals sat there while the gate reported no violation and no counter
    named the scope. `personalscraper/`'s French has a documented carve-out
    (the CLI speaks to the operator, in French); `tests/` has none.

    Translating them is a separate piece of work — 159 docstrings and 110
    assertion messages, each of which has to be read to be moved. What must not
    wait is the invisibility: an unread scope reports « no violation » about a
    place it never opened, and that is how every hole this file has had began.

    So the scope is read, published, and RATCHETED: it may shrink, never grow.
    A new French docstring in a test is refused today; the existing ones are a
    declared debt with a number attached.

    Args:
        violations: The accumulator every arm appends to.
    """
    french = 0
    for path in sorted(walk((ROOT / "tests"), "*.py")):
        source = read(path)
        literals = python_string_literals(source)
        examined["string literals / tests"] += len(literals)
        french += sum(1 for _, body in literals if offending_string(body))
    exempted["french strings / tests"] = french

    baseline_path = ROOT / "scripts" / "french-exemption-baseline.json"
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["tests"]
    except (OSError, ValueError, KeyError):
        violations.append(
            f"{relative(baseline_path)} has no `tests` baseline — the scope "
            "would be read and counted, and still free to grow")
        return
    if french > baseline:
        violations.append(
            f"the French in `tests/` GREW: {french} strings against a baseline "
            f"of {baseline}. Docstrings and tool messages are English "
            f"(CLAUDE.md §Language) — write the new one in English, or lower "
            f"the baseline in {relative(baseline_path)} deliberately.")

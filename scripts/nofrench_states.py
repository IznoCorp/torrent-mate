#!/usr/bin/env python3
"""Arm 15 — a NAMED STATE's id is a name, and names are English.

B-036. `window.__states()` returned `system-panne` and `acq-follows-groupe`
until 2026-08-29, and no arm of `check-no-french.py` read the state table: the
count of French state ids went from 51 to 2 during L01 and then stopped moving,
with nothing to notice that it had stopped short. A rule with no arm is a
sentence in a file, and this is the sentence the register asked to have armed —
B-036's own text says its fix « should carry the missing arm rather than only
the two renames ».

A STATE ID IS A NAME AND NOT A VALUE, which is the distinction CLAUDE.md draws
after « data VALUES » was read as an escape hatch: a value is a datum the app
STORES or DISPLAYS, and if a human typed it to designate something, it is a
name. `window.__go("acq-now-idle")` designates a scenario. Fifty-one of the
eighty-two were French because « it is a value » was accepted as an answer.

THE CORPUS IS CROSS-CHECKED, AND THE DISAGREEMENT IS BLOCKING. A state id is
written in three shapes, and a reader that knows two of them reports « no
violation » about a third it never saw:

    [                              the ordinary entry, over three lines
      "acq-now-idle",
      "Acquisition · En cours — au repos",

    ["signin", "Connexion …", () => showSignIn(false)],      on ONE line

    ].map(([genre, what]) => [                               GENERATED
      `settings-field-${genre}`,

Ten of the eighty-seven are in the last two shapes — one single-line entry and
a family of nine built from a template — so a scan for a quoted literal at the
head of a bracket reads 77 and says nothing about the rest. The second oracle
is `oracle-reference.json`: it holds one entry per state the recorded oracle
actually drove, and **an id it measured that this arm could not parse is
refused**. That direction is the one that means blindness. The other direction
— an id parsed here and absent from the reference — is a state added and not
yet re-recorded, which the oracle reports itself, so it is printed and not
refused.

This is B-208's shape used deliberately: two independent readers of the same
fact, and the disagreement fails rather than prints.

WHAT IT DOES NOT READ:

  - THE DESCRIPTIONS. `"Acquisition · En cours — au repos"` is the label the
    harness dial shows a reader, so it is interface text and stays French; the
    engine is exempt from i18n extraction because it dies at L13.
  - THE SCENARIO BODIES. What a state DOES is ordinary code, read by the
    identifier arm like any other.
  - WHETHER A NAME IS GOOD. It asks the vocabulary's question — is this word one
    this codebase writes? — which is the only question a list of French words
    can answer honestly, because a list of French words always has holes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nofrench_lexicon import (  # noqa: E402
    MAQUETTE, VOCABULARY, examined, read, relative, split_identifier,
    vocabulary,
)

STATES = MAQUETTE / "design" / "src" / "engine" / "states.js"
ORACLE_REFERENCE = MAQUETTE / "oracle-reference.json"

# The three shapes, in the order they appear above. The generated one yields the
# literal PREFIX and the words the template interpolates from the table beside
# it; both halves are names someone chose.
ENTRY_OVER_LINES = re.compile(r'\[\s*\n\s*"([A-Za-z][\w-]*)",\s*\n\s*[`"]')
# The third argument is a FUNCTION, whatever shape it takes. Requiring the
# literal `, ()` read `["signin", "…", () => …]` and walked past
# `async () =>`, a named reference, and `function () {}` — none of which the
# over-lines reader sees either, so both spellings escaped both readers.
ENTRY_ON_ONE_LINE = re.compile(
    r'\[\s*"([A-Za-z][\w-]*)",\s*"[^"]*",\s*(?:async\s*)?(?:\(|function\b|\w)')
ENTRY_FROM_TEMPLATE = re.compile(r'`([A-Za-z][\w-]*)-\$\{(\w+)\}`')
TEMPLATE_MEMBER = re.compile(r'\["([A-Za-z][\w-]*)",\s*"')
# `].map((` — the end of the array a generated family is built from. The members
# are found by matching that bracket BACKWARDS rather than by sweeping the file:
# a sweep read every `["word", "` in `states.js` and invented
# `settings-field-signin` out of a single-line entry three hundred lines away.
# An expansion that over-generates is a corpus with names nobody wrote in it,
# and it fails on the ones it invented rather than on the ones that exist.
MAP_CALL = "].map(("

# What the arm must have read for its answer to mean anything. Set below the 87
# the oracle drives, never at it: a floor where the count already sits is
# pre-satisfied and can never fall.
STATE_FLOOR = 60


def declared_state_identifiers(source: str) -> set[str]:
    """Collects every state id the table declares, in all three shapes.

    Args:
        source: The whole of `engine/states.js`.

    Returns:
        The ids, with a generated family expanded into the names its template
        produces.
    """
    found = set(ENTRY_OVER_LINES.findall(source))
    found |= set(ENTRY_ON_ONE_LINE.findall(source))
    for start in _map_call_positions(source):
        body = source[start:]
        template = ENTRY_FROM_TEMPLATE.search(body[:400])
        if not template:
            continue
        members = TEMPLATE_MEMBER.findall(_receiver_array(source, start))
        found |= {f"{template.group(1)}-{member}" for member in members}
    return found


def _map_call_positions(source: str) -> list[int]:
    """Returns the offset of every `].map((` in the table.

    Returns:
        One offset per generated family, pointing at the closing bracket.
    """
    positions, at = [], source.find(MAP_CALL)
    while at != -1:
        positions.append(at)
        at = source.find(MAP_CALL, at + 1)
    return positions


def _receiver_array(source: str, closing: int) -> str:
    """Returns the array literal a `.map((` is called on.

    Matched by walking brackets BACKWARDS from the closing one, so the members
    of one family cannot be drawn from another part of the file.

    Args:
        source: The whole of `engine/states.js`.
        closing: The offset of the `]` that ends the receiver.

    Returns:
        The receiver's text, or an empty string where the brackets do not
        balance — which yields no member rather than every member.
    """
    depth = 0
    for at in range(closing, -1, -1):
        if source[at] == "]":
            depth += 1
        elif source[at] == "[":
            depth -= 1
            if depth == 0:
                return source[at:closing]
    return ""


def measured_state_identifiers() -> set[str]:
    """Returns the states the recorded oracle actually drove.

    Returns:
        The keys of the reference's `measurements`, or an empty set where the
        reference is absent — which the caller refuses rather than passes.
    """
    if not ORACLE_REFERENCE.is_file():
        return set()
    return set(json.loads(ORACLE_REFERENCE.read_text(encoding="utf-8"))
               .get("measurements", {}))


def check_state_identifiers(violations: list[str]) -> None:
    """Refuses a named-state id built from a word this codebase lacks.

    Args:
        violations: The accumulator every arm appends to.
    """
    # THE DEBT WORDS ARE EXCLUDED, and without this the arm could not catch the
    # very id it was written for. `vocabulary()` returns the WHOLE file, the
    # section banner-marked « THE ENGINE'S LAST FRENCH WORDS » included — and
    # that section holds `panne`. So `system-panne` would have passed in
    # silence, along with `repos`, `courant`, `masquer` and twenty more.
    #
    # THE MUTATION THAT « PROVED » THIS ARM WAS MEASURED IN THE WRONG WORLD.
    # Restoring `system-panne` did make the arm fall — on the CROSS-CHECK, which
    # named `system-outage`, because the oracle reference still carried the old
    # id. It never named `panne`. A mutation run against a stale second reader
    # proves the cross-check works and says nothing about the vocabulary; it is
    # the test agreeing with the fix, which this register refuses by name.
    #
    # The debt is owed to `legacy.js` alone (`check_french_debt`), and
    # `states.js` is not `legacy.js`. Excluding it costs nothing: no current id
    # fails.
    words = vocabulary() - vocabulary(debt_only=True)
    source = read(STATES)
    declared = declared_state_identifiers(source)
    measured = measured_state_identifiers()

    examined["state identifiers / engine"] += len(declared)

    if not measured:
        violations.append(
            f"{relative(ORACLE_REFERENCE)}: absent, so this arm has only ONE "
            "reader of the state table and cannot tell « no French id » from "
            "« a shape I do not parse ». The cross-check is the arm.")
    unparsed = sorted(measured - declared)
    if unparsed:
        violations.append(
            f"{relative(STATES)}: the recorded oracle measured "
            f"{len(unparsed)} state(s) this arm could not parse — "
            f"{', '.join(unparsed[:6])}"
            f"{' …' if len(unparsed) > 6 else ''}. A state written in a shape "
            "the reader does not know is a state read by nobody, and this arm "
            "would report « no violation » over it. Teach the shape.")
    added = sorted(declared - measured)
    if added:
        print(f"  note: {len(added)} state(s) declared and not in the recorded "
              f"oracle — {', '.join(added[:6])}"
              f"{' …' if len(added) > 6 else ''}. A new state is re-recorded by "
              "the oracle, which reports it itself; that direction is not this "
              "arm's to refuse.")

    if len(declared) < STATE_FLOOR:
        violations.append(
            f"{relative(STATES)}: {len(declared)} state id(s) read, under the "
            f"floor of {STATE_FLOOR}. This arm starts at zero violations, so a "
            "table it can no longer parse reports the same word as one it read "
            "entirely.")

    for name in sorted(declared):
        unknown = [word for word in split_identifier(name)
                   if len(word) > 1 and word.lower() not in words]
        if unknown:
            line = source.count("\n", 0, source.find(name)) + 1
            violations.append(
                f"{relative(STATES)}:{line}: the named state {name!r} is built "
                f"from {', '.join(repr(one) for one in unknown)}, which "
                f"{'is' if len(unknown) == 1 else 'are'} not in "
                f"{relative(VOCABULARY)}. A state id is a NAME someone chose — "
                "`window.__go(\"acq-now-idle\")` designates a scenario — so it "
                "is English like any other name. Rename it through "
                "`scripts/rename-identifiers.py`, and remember that its ends "
                "include the oracle's reference and the accessibility ledgers.")


__all__ = ["check_state_identifiers", "declared_state_identifiers",
           "measured_state_identifiers"]

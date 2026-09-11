#!/usr/bin/env python3
"""ARM 7 of the markup guard — a `data-*` verb a panel action emits and
nothing answers.

SPLIT OUT OF `check-markup-contracts.py` on the same rule the three arms
before it followed: the entry point stays the gate's ONE command, and an
arm with a corpus of its own lives beside it rather than inside it.

Corpus, emission side: every `.ts` and `.tsx` file under
`frontend/maquette/design/src`, read through the TypeScript parser by
`harness/panel_verbs.mjs`. Answering side: the same tree's
`registerVerb` declarations, and the dying engine `src/engine/legacy.js`.

THE DEFECT CLASS, and it is the reason `lib/verbs.ts` exists at all. A
panel action is `{ text, icone, target }` where `target` is a map of DATA
ATTRIBUTES; `ui/panel` draws them onto the button and attaches no handler
of its own, by contract. So the button ACTS only if something else,
somewhere else, reads that attribute:

    target: { "journey-requeue": title }      the panel emits
    registerVerb("journey-requeue", act)      a feature answers

Until this wave there was exactly one answerer — the dying engine's
document delegation — and a verb it had never heard of had NOBODY. The
button drew correctly, took the tap, and did nothing at all: no error, no
message, nothing in the console. Every gate stayed green over it, because
nothing anywhere compared the two ends.

That is the same three-ends failure the anchor and naming arms hold from
their own side, and the same silence: a name emitted by one file and read
by no other is invisible to a diff, to a type checker, and to a rule
suite that never happens to press that particular button.

WHAT COUNTS AS AN ANSWER, and there are exactly two:

  * `registerVerb("name", …)` — a feature declaring what the tap does.
  * A READ, anywhere in the tree: `closest.dataset.name`, `[data-name]`
    in a selector, or `getAttribute("data-name")`. The engine still
    answers most of these verbs and dies by subtraction (D5); when a
    branch of its delegation goes, the verb it answered must have arrived
    on the registry first, or this arm falls on it. That is the arm
    working, not the arm getting in the way.

AND THE READ IS NOT THE ENGINE'S ALONE, which this arm had to be taught
by the first move it governed. It accepted a read only in
`engine/legacy.js`, because on the day it was written the engine was the
only reader there was. Then `data-follow` moved onto the registry and its
branch was deleted — and the arm refused `data-sugidx`, which sits in the
SAME target map and is not a verb at all: it is the suggestion's POSITION,
a datum the act's own handler reads through `element.dataset.sugidx`. The
answer had moved with the verb, into a feature, and the arm was still
looking in the engine. « Does anything read this name » is the question;
where the reader lives is not part of it.

WHICH MAPS IT HOLDS, AND WHICH IT SETS ASIDE. A `DialogAction` carries a
`target` too, and the dialog is not the panel: it spreads those keys
verbatim — they are written `data-…` already — and attaches its OWN
`onClick`, which runs the action's `run` closure. Its verbs are answered
by the component that draws them, so holding them here would report
defects that are not ones. An action is the dialog's when it carries one
of the dialog's own property names (`run`, `dismiss`, `tone` — the panel
spells its own `ton`), and the number set aside for that reason is
PRINTED rather than described, so the exclusion is a figure someone can
watch move.

AND THE PREFIX IS ITS OWN REFUSAL. `ui/panel` writes `data-` in front of
each key itself, so a panel action asking for `data-x` renders
`data-data-x` — an attribute nothing reads, and a button that does
nothing, arrived at from the other direction. It is refused here because
this is the one arm that has already told the two surfaces apart; on the
dialog's side the same spelling is correct.

WHAT IT DOES NOT READ. A `data-*` written straight into JSX
(`data-grab-season={…}` on the seasons panel's button) is out of scope:
that element carries its own `onClick` a line below, so the emission and
the answer are the same expression and cannot drift apart. This arm holds
the maps whose contract is that NOBODY attaches a handler.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The shared text readers — see that module's header.
from markup_text import (  # noqa: E402
    COMMENT, HARNESS, ROOT, SOURCES, attribute_of,
)

# The extractor, and the file the size ledger is watching shrink. `ENGINE`
# is named rather than derived because the message below tells an author
# NOT to answer a verb there; the reading itself spans the whole tree.
VERB_EXTRACTOR = HARNESS / "panel_verbs.mjs"
ENGINE = SOURCES / "engine" / "legacy.js"

# What a read can be written in. The engine is JavaScript and everything
# that has left it is TypeScript, so the corpus is all three.
READING_SUFFIXES = (".ts", ".tsx", ".js")

# The floor beneath what the extractor reads. A parse that returned
# nothing agrees, word for word, with a tree whose panels offer no action
# at all — and this arm starts at zero violations, so the two readings
# would print the same line. Set well under what the tree holds: it is a
# floor, not a ratchet, and it exists to catch an extractor that stopped
# working, never to freeze a count.
VERB_FLOOR = 20

# The property names that belong to a `DialogAction` and to no panel
# action. `ton` is the panel's spelling and is deliberately absent.
DIALOG_ONLY = frozenset({"run", "dismiss", "tone"})

# `registerVerb("journey-requeue", …)` — a feature declaring an answer.
REGISTERED = re.compile(r"""registerVerb\(\s*["'](?P<name>[a-z][\w-]*)["']\s*,""")

# `registerVerb(` at all, whatever follows. The other half of the count:
# a call whose name is not a literal is a declaration this arm cannot
# read, and an arm that silently counted one fewer answer would refuse a
# verb that is in fact answered. The DECLARATION in `lib/verbs.ts` is not
# a call and is excluded by its `function` keyword — counting it made
# this arm report an unreadable registration on its very first run.
REGISTERED_CALL = re.compile(r"(?<!function )registerVerb\(")

# How the engine reads an attribute: through `dataset`, through a
# selector, or by name. All three are answers; the first is how its
# delegation is written throughout.
ENGINE_DATASET = re.compile(r"\.dataset\.(?P<name>[A-Za-z][A-Za-z0-9]*)")
ENGINE_SELECTED = re.compile(r"\[\s*data-(?P<name>[a-z][\w-]*)\s*[\]~^$*|=]")
ENGINE_NAMED = re.compile(
    r"""(?:get|has|remove)Attribute\(\s*["']data-(?P<name>[a-z][\w-]*)["']""")


def typescript_package() -> Path | None:
    """Finds a TypeScript installation the extractor can require.

    Returns:
        The package directory, or None where neither tree is installed.
    """
    for candidate in (ROOT / "frontend" / "maquette" / "design" / "node_modules",
                      ROOT / "frontend" / "node_modules"):
        package = candidate / "typescript"
        if package.is_dir():
            return package
    return None


def source_files() -> list[str]:
    """The emission corpus: every component and producer in the tree.

    The engine is not excluded by a rule of its own — it is written in
    JavaScript, and this list holds `.ts` and `.tsx`. Saying it that way
    rather than filtering by path means the day a piece of the engine
    arrives as TypeScript, its panels are read like everyone else's.

    Returns:
        The paths, sorted, as the extractor takes them.
    """
    return sorted(
        str(path) for path in SOURCES.rglob("*") if path.suffix in (".ts", ".tsx")
    )


def registered_verbs() -> tuple[set[str], int]:
    """Every verb a feature declares an answer for.

    Comments are stripped first: a `registerVerb` call a comment quotes
    answers no tap, and this file's own header quotes one. The stripping
    is `COMMENT`, the JavaScript reader ARM 1 uses — NOT
    `comment_masked`, which is tokenize-backed and therefore Python's;
    handed a `.ts` file it cannot tokenize, that one falls back to
    returning the text UNCHANGED, so a comment would have answered a tap.
    Measured, by the case that holds it.

    Returns:
        The attribute names registered, and how many `registerVerb` calls
        were seen in total — the second so a call this reader could not
        read is a difference someone can see.
    """
    names: set[str] = set()
    calls = 0
    for path in SOURCES.rglob("*"):
        if path.suffix not in (".ts", ".tsx"):
            continue
        text = COMMENT.sub(" ", path.read_text(encoding="utf-8"))
        calls += len(REGISTERED_CALL.findall(text))
        names.update(match.group("name") for match in REGISTERED.finditer(text))
    return names, calls


def read_attributes() -> set[str]:
    """Every attribute something in the tree READS.

    The engine included, and not the engine alone: a verb that has moved
    onto the registry takes its handler's own reads with it, and the data
    the handler reads beside the verb — a position, a kind — are in the
    same target map and are answered exactly there. Restricting this to
    `engine/legacy.js` made the arm refuse a datum on the first move it
    governed; see this module's header.

    Comments are stripped, by the JavaScript reader rather than the Python
    one — see `registered_verbs`. Prose names attributes nothing reads any
    more, and an answer a comment gives is no answer.

    Returns:
        The attribute names, in their markup spelling.
    """
    names: set[str] = set()
    for path in SOURCES.rglob("*"):
        if path.suffix not in READING_SUFFIXES:
            continue
        text = COMMENT.sub(" ", path.read_text(encoding="utf-8"))
        names.update(attribute_of(match.group("name"))
                     for match in ENGINE_DATASET.finditer(text))
        names.update(match.group("name") for match in ENGINE_SELECTED.finditer(text))
        names.update(match.group("name") for match in ENGINE_NAMED.finditer(text))
    return names


def emitted_maps() -> dict | None:
    """Runs the extractor over the emission corpus.

    Returns:
        Its reading, or None when it could not run — which the caller
        reports as « did not run », never as « no violation ».
    """
    package = typescript_package()
    if package is None:
        print("check-markup-contracts: no TypeScript installation under "
              "frontend/ — this arm parses TypeScript and cannot answer "
              "without one. Reporting « not installed » rather than « no "
              "violation », because the two are indistinguishable in a log.",
              file=sys.stderr)
        return None
    try:
        completed = subprocess.run(
            ["node", str(VERB_EXTRACTOR), str(package), *source_files()],
            capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as failure:
        print(f"check-markup-contracts: the panel-verb extractor could not run "
              f"({failure}). An arm that cannot run has not passed.",
              file=sys.stderr)
        return None
    if completed.returncode != 0:
        print("check-markup-contracts: the panel-verb extractor failed — "
              f"{completed.stderr.strip()[:400]}", file=sys.stderr)
        return None
    return json.loads(completed.stdout)


def check_panel_verbs() -> int:
    """ARM 7: refuses a panel verb the markup emits and nothing answers.

    The emission side is parsed, the two answering sides are read as
    masked text, and every emitted name must appear on one of them. The
    direction is ONE-WAY, as ARM 3's is: an answer nothing emits is not a
    defect — the engine reads attributes no panel emits, and will until
    it dies.

    Returns:
        1 when a verb is answered by nothing, when a panel action asks for
        an already-prefixed attribute, when a registration cannot be read,
        or when the extractor did not run; 0 otherwise.
    """
    reading = emitted_maps()
    if reading is None:
        return 1

    registered, calls = registered_verbs()
    answered = registered | read_attributes()

    violations = 0
    if len(reading["maps"]) < VERB_FLOOR:
        violations += 1
        print(f"  {SOURCES}: {len(reading['maps'])} action target(s) read, "
              f"under the floor of {VERB_FLOOR}. This arm starts at zero "
              "violations, so a parse that returned nothing prints the same "
              "line as one that read every panel in the interface.",
              file=sys.stderr)

    held = 0
    set_aside = 0
    for one in reading["maps"]:
        relative = str(Path(one["file"]).relative_to(SOURCES))
        if DIALOG_ONLY & set(one["siblings"]):
            set_aside += 1
            continue
        for verb in one["verbs"]:
            held += 1
            if verb.startswith("data-"):
                violations += 1
                print(f"  {relative}:{one['line']}: the panel action asks for "
                      f"« {verb} », and `ui/panel` writes `data-` in front of "
                      f"every key itself — this renders `data-{verb}`, which "
                      "nothing reads and no tap answers. Drop the prefix. On a "
                      "DIALOG action the same spelling is right, and this arm "
                      "sets those aside; this action is not one.",
                      file=sys.stderr)
                continue
            if verb in answered:
                continue
            violations += 1
            print(f"  {relative}:{one['line']}: nothing answers a tap on "
                  f"« data-{verb} ». `ui/panel` draws an action's target "
                  "attributes and attaches NO handler, by contract, so this "
                  "button takes the tap and does nothing — silently, with no "
                  "error anywhere. Declare it with `registerVerb(\"" + verb +
                  "\", …)` in the feature that owns it, which is what "
                  "`lib/verbs.ts` exists for. A branch in `engine/legacy.js` "
                  "is NOT the answer: the engine dies by subtraction (D5) and "
                  "the size ledger refuses it upward.", file=sys.stderr)

    unreadable = calls - len(registered)
    if unreadable > 0:
        violations += 1
        print(f"  {SOURCES}: {calls} `registerVerb` call(s) against "
              f"{len(registered)} whose name this arm could read. A "
              "registration whose name is not a string literal is an answer "
              "the arm cannot see, and a verb it answers would be refused "
              "above as answered by nothing. Spell the name as a literal.",
              file=sys.stderr)

    if violations:
        print(f"\ncheck-markup-contracts: {violations} panel-verb "
              "violation(s). A panel action's target is a map of data "
              "attributes with no handler behind it — the whole contract is "
              "that something else reads the name.", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {held} panel verb(s) over "
          f"{len(reading['maps'])} action target(s), every one answered — "
          f"{len(registered)} by a `registerVerb` declaration, the rest by a "
          f"read in the tree. {set_aside} dialog action(s) set aside (their keys "
          f"are spread verbatim and the dialog attaches its own handler), "
          f"{reading['computed']} computed key(s) and "
          f"{reading['unresolved']} unresolved target(s) skipped.")
    return 0

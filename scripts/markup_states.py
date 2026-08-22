#!/usr/bin/env python3
"""ARM 4 of the markup guard — a boolean state attribute written as a
bare value.

SPLIT OUT OF `check-markup-contracts.py`, the third arm to leave it: the
derived corpus took the entry point past the 800-line warn tier, and the
entry point stays the gate's ONE command.
Corpus: the components — every `.ts` and `.tsx` file under
`frontend/maquette/design/src`, read as text.

THE DEFECT CLASS, MEASURED, NOT BELIEVED. React renders the boolean
`false` into an attribute as the STRING "false": the attribute is
PRESENT, a presence selector such as `[data-open]` matches it ALWAYS,
and a hold built on that selector stays green while the state it claims
to read is never absent. harness/attrs.py demonstrated both halves in
the live document — the string "false" renders, and the presence
selector matches it. So a boolean state attribute must be written so a
false state omits it. The accepted spellings are
`data-open={x || undefined}`, or the equivalent `{x ? "" : undefined}` /
`{x ? true : undefined}`: each reaches `undefined` when the boolean is
false, and `undefined` is the value React omits from the markup. A bare
`data-open={x}` is refused; a literal `data-open` with no braces is a
constant attribute and fine.

WHICH ATTRIBUTES, AND IT IS DERIVED RATHER THAN LISTED. The arm's corpus
was a tuple of SEVEN names and the wave that wrote it coined TWELVE
boolean states: `data-edited`, `data-mono`, `data-solid`,
`data-read-only` and `data-skeleton` were selected by presence from five
rules and read here never. Nothing could tell, because the shortfall was
in neither the numerator nor the denominator of anything printed.
`boolean_state_attributes` asks the HARNESS instead: an attribute is a
boolean state when the rules ask whether it is THERE —
`[data-open]`, `hasAttribute('data-open')` — and never what it says, in
a selector (all six CSS comparison forms) or through
`element.dataset.x`. An attribute whose value something compares carries
data, and its presence is a different question.

WHAT IT EXAMINES, AND WHY BOTH COUNTS ARE PRINTED. The arm prints how
many attributes it DERIVED and how many writes it examined, because
either number alone is one nobody can tell is short: the arm was VACUOUS
for as long as no such attribute existed anywhere, and a green exit over
zero attributes proves nothing about the rule — only that the corpus was
empty. It is proven by probe-mutation besides. attrs.py's holds first
measured `aria-*` and `title` — the same passthrough, not the same
attribute — and the real `data-open` was owed its own demonstration on
the day it first existed; that gap is closed by re-measuring, never by
analogy.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The shared text readers — see that module's header.
from markup_text import (  # noqa: E402
    COMMENT, ROOT, SOURCES, attribute_of, braced_expression, comment_masked,
)
# The corpus this arm derives its question from is the harness, and the file
# list is the anchor arm's.
from markup_anchors import harness_files  # noqa: E402

# ---- ARM 4 constants ----------------------------------------------------

# THE CORPUS IS DERIVED, NEVER ENUMERATED. It was a tuple of seven names
# for one wave, and the wave that wrote it shipped TWELVE: `data-edited`,
# `data-mono`, `data-solid`, `data-read-only` and `data-skeleton` were
# coined, selected by presence from five rules, and read by this arm
# never. The shortfall was invisible by construction — the arm printed
# how many writes it had examined, and the ones it skipped were in
# neither the numerator nor the denominator.
#
# THE DERIVATION, and it is a question about the HARNESS, not a list:
# an attribute is a boolean STATE when the rules select it by PRESENCE —
# `[data-open]`, `hasAttribute('data-open')` — and never ask what its
# value is, in a selector (`[data-key^="mediaSheet:"]`, all six of CSS's
# comparison operators) or through `element.dataset.tone`. An attribute
# whose value anything compares carries data; presence is then a
# different question and this arm owes it nothing.
#
# So a state attribute coined tomorrow is covered the moment a rule
# selects it, which is the moment it starts to matter.

# `[data-open]` — the attribute NAMED inside an attribute block, with no
# comparison after it.
PRESENCE_SELECTED = re.compile(r"\[\s*data-(?P<attr>[a-z][\w-]*)\s*\]")

# `hasAttribute('data-open')` — the same question asked in JavaScript.
HAS_ATTRIBUTE = re.compile(
    r"""hasAttribute\(\s*['"]data-(?P<attr>[a-z][\w-]*)['"]\s*\)""")

# `[data-key^="mediaSheet:"]` — the VALUE compared. CSS has six
# comparison operators and every one of them says the same thing about
# the attribute: it carries a value somebody reads.
VALUE_SELECTED = re.compile(r"\[\s*data-(?P<attr>[a-z][\w-]*)\s*[~^$*|]?=")

# `badge.dataset.tone` — the value read in JavaScript rather than
# selected. `dataset` spells a `data-two-word` attribute `twoWord`, so
# the name is put back into its attribute spelling before comparison.
DATASET_READ = re.compile(r"\.dataset\.(?P<attr>[A-Za-z][A-Za-z0-9]*)")

# The three spellings that omit the attribute when the state is false, so
# a presence selector never matches a false value. `undefined` (like
# `null`) is the value React omits from the markup, and each tail reaches
# it exactly when the boolean is false — the bare `{x}` reaches it never.
OMITTING_TAILS = ("||undefined", "?\"\":undefined", "?true:undefined")


def boolean_state_attributes() -> set[str]:
    """Derives ARM 4's corpus from what the HARNESS selects by presence.

    An attribute is a boolean state when the rules ask whether it is
    THERE and never what it says: `[data-open]` or
    `hasAttribute('data-open')`, and no `[data-x=…]` in any of CSS's six
    comparison forms and no `element.dataset.x`. An attribute whose value
    something compares carries data, and its presence is a different
    question.

    Comments are masked first — a selection a COMMENT quotes is performed
    by nothing — with the reader that knows a `#` inside a string is not
    a comment.

    Returns:
        The attribute names, without the `data-` prefix. Empty when the
        harness selects nothing by presence, which the caller refuses
        loudly: a derived corpus that comes back empty is a scope that
        has silently emptied.
    """
    present: set[str] = set()
    compared: set[str] = set()
    for path in harness_files():
        text = comment_masked(path.read_text(encoding="utf-8"))
        for reader in (PRESENCE_SELECTED, HAS_ATTRIBUTE):
            present |= {m.group("attr") for m in reader.finditer(text)}
        compared |= {m.group("attr") for m in VALUE_SELECTED.finditer(text)}
        compared |= {attribute_of(m.group("attr"))
                     for m in DATASET_READ.finditer(text)}
    return present - compared


def state_attribute_writes(path: Path,
                           attributes: set[str]) -> list[tuple[int, str, str]]:
    """Extracts every braced boolean-state write in one component file.

    Comments are stripped before reading — a write a COMMENT describes
    was rejected, exactly like ARM 1's `prete`. The corpus is the
    components: the `.ts` / `.tsx` files under `design/src`.

    Args:
        path: A component file.
        attributes: The boolean state attributes, derived by
            `boolean_state_attributes` — never a list written here.

    Returns:
        `(line, attribute, expression)` tuples, in file order — the
        expression as written between the braces. A brace pair that never
        balances is skipped, not guessed at.
    """
    written = re.compile("data-(?P<attr>"
                         + "|".join(sorted(attributes, key=len, reverse=True))
                         + r")\s*=\s*\{")
    text = COMMENT.sub(" ", path.read_text(encoding="utf-8"))
    found: list[tuple[int, str, str]] = []
    for match in written.finditer(text):
        # The match ends past the `{`; the walk starts on it.
        braced = braced_expression(text, match.end() - 1)
        if braced is None:
            continue
        expression, _ = braced
        line = text.count("\n", 0, match.start()) + 1
        found.append((line, match.group("attr"), expression))
    return found


def omits_when_false(expression: str) -> bool:
    """True when the braced expression spells one of the omitting idioms.

    Whitespace is not meaning — `{x || undefined}` and `{x||undefined}`
    are the same spelling — so the expression is flattened before the
    comparison. Each accepted tail reaches `undefined` exactly when the
    boolean is false, and `undefined` is the value React omits from the
    markup; a bare `{x}` reaches it never.

    Args:
        expression: The braced expression, as written.

    Returns:
        True when the flattened expression ends with one of
        `OMITTING_TAILS`.
    """
    flat = re.sub(r"\s+", "", expression)
    return flat.endswith(OMITTING_TAILS)


def check_state_attributes() -> int:
    """Arm 4: refuses a boolean state attribute written as a bare value.

    React renders the boolean `false` as the STRING "false" — the
    attribute is PRESENT, `[data-open]` matches it ALWAYS, and a hold
    built on it stays green while the state is never absent
    (measured: harness/attrs.py). A write must therefore spell an
    omission: `data-open={x || undefined}`, or `{x ? "" : undefined}` /
    `{x ? true : undefined}`. A literal `data-open` with no braces is a
    constant attribute and fine.

    THE CORPUS IS DERIVED, and that is the arm's own repaired defect. It
    was a tuple of seven names, and the wave that wrote it coined twelve
    boolean states; the five it did not name were selected by presence
    from five rules and read here never, while the printed count said
    « 8 examined » and nothing said 8 of what. `boolean_state_attributes`
    now asks the harness: every `data-*` it selects by PRESENCE and never
    compares the value of. So an attribute coined tomorrow is covered the
    moment a rule selects it.

    It prints both numbers — how many attributes it derived and how many
    writes it examined — because either one alone is a number nobody can
    tell is short: the arm was VACUOUS for as long as no such attribute
    existed, and a green exit over an empty corpus proves nothing about
    the rule. It is proven by probe-mutation besides.

    Returns:
        1 when any state attribute is written without an omitting
        spelling, 0 otherwise.
    """
    files = [p for p in sorted(SOURCES.rglob("*"))
             if p.is_file() and p.suffix in {".ts", ".tsx"}]
    if not files:
        print(f"check-markup-contracts: no component files under {SOURCES} "
              "— the scope is empty, so « no violation » would mean "
              "nothing", file=sys.stderr)
        return 1
    attributes = boolean_state_attributes()
    if not attributes:
        print("check-markup-contracts: the harness selects no `data-*` by "
              "presence — this arm's corpus is DERIVED from that question, "
              "so an empty answer means the derivation is broken, not that "
              "there is no state to check", file=sys.stderr)
        return 1

    violations = 0
    checked = 0
    for path in files:
        rel = str(path.relative_to(ROOT))
        for line, attr, expression in state_attribute_writes(path, attributes):
            checked += 1
            if omits_when_false(expression):
                continue
            violations += 1
            print(f"  {rel}:{line}: `data-{attr}={{...}}` is written without "
                  "a spelling that omits the attribute when its state is "
                  f"false. React renders the boolean false as the STRING "
                  f"\"false\" — the attribute is PRESENT, and a "
                  f"`[data-{attr}]` selector matches it ALWAYS, so a hold "
                  "built on it stays green while the state is never absent "
                  "(measured: harness/attrs.py). Write `data-"
                  f"{attr}={{x || undefined}}` — or `{{x ? \"\" : undefined}}`"
                  f" / `{{x ? true : undefined}}`.", file=sys.stderr)

    if violations:
        print(f"\ncheck-markup-contracts: {violations} state attribute(s) "
              "written as a bare value. A boolean state attribute must be "
              "written so a false state OMITS it — the accepted spellings "
              "are the ones that reach `undefined`.", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {checked} state attribute write(s) "
          f"checked over {len(attributes)} boolean state attribute(s) "
          "DERIVED from what the harness selects by presence — "
          f"{', '.join('data-' + a for a in sorted(attributes))} — every one "
          "written with a spelling that omits the attribute when its state "
          "is false.")
    return 0

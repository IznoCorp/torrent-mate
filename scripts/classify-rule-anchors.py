#!/usr/bin/env python3
"""Classifies what each harness rule selection anchors on.

THE DEFECT CLASS. The harness rules select elements by their style class —
`querySelector('.card')`, `querySelector('.ctitle')` — and those names are the
stylesheet's. The day a surface converts to utility classes the names stop
existing, and every rule that reads them falls with no way to attribute the
failure: anchor, or style? A selection anchored on a `data-*` contract or a
structural id has exactly one possible cause of failure, which is why the
rules are migrated onto them — and this tool is the independent measurement of
how much class-anchored debt the harness still carries. Independent is the
whole point: the guard that refuses new class anchors is a second reader of
the same corpus, and a classification cross-checked only by the guard that
produced it proves nothing.

TWO QUESTIONS, TWO MODES — a file where a reader cannot tell which number
means what is the defect this tool exists to measure:

    --summary   « what does this anchor on » — one bucket per selection call,
                by the precedence rule below. It is NOT the lot's size: a
                class token behind a stronger anchor is invisible to it.
    --tokens    « what breaks when the stylesheet changes » — EVERY `.token`
                outside a [...] block, however the selector is anchored.

`#view .swipe` is id-anchored by precedence, and it still dies the day the
`.swipe` class is removed. Over the corpus as first measured, 151 class tokens
hide behind a stronger anchor this way — 432 selectors fall at the stylesheet
conversion, not the 281 `--summary` reports. And the unit of work is the token
OCCURRENCE, not the selector: one selector can carry tokens two different
migrations own, so only the occurrence has a single owner. That is why
`--baseline` emits one entry per occurrence, each naming the token that entry
is about — a listing now expected EMPTY, since the guard beside this tool
refuses the first class anchor it finds.

THE PRECEDENCE RULE — the rule IS the --summary measurement. Within ONE
selector string, classify by the strongest anchor present:

    data-*  (an attribute selector naming a data- attribute)
      > id  (a `#name` outside any [...] block)
      > class  (a `.name` outside any [...] block)
      > role  (a [role=...] attribute selector)
      > tag  (none of the above)

A naive "any `.token` outside [...]" classifier attributes `.tile[data-panel]`
to the class that merely styles the tile. Over the corpus as first measured it
counted 428 class anchors where this rule counts 281 — the difference is
exactly the selectors whose strongest anchor is an attribute. `--tokens` is
not that naive classifier: it counts every token AND reports the split, so a
token behind a stronger anchor is a count, never an anchor.

WHAT IT READS. Two passes, one corpus — `frontend/maquette/harness/*.py`,
read as text.

  * The CALL pass: the string argument of every `querySelector`,
    `querySelectorAll`, `locator` and `matches` call — both quoting
    styles and template literals. Three calls pass their selector in
    backticks with a `${...}` interpolation inside; the interpolation is
    unknown at rest and is stripped before classifying, so the literal
    text that remains decides the anchor.

  * The HELD pass: every OTHER selector-shaped string literal — a
    selector held in a variable, a table, a helper's argument, a
    comparison. A reader that sees only the call pass never sees
    `screen_port = ".screen.open .port"`, and the string dies at L07
    with no measurement — the second blind spot of the family D4's
    one-bucket rule was found to be. `--tokens` and `--baseline` count
    both passes; the two populations are told apart by the `held` field
    on each entry.

  * The READ pass: a class name taken from the class ATTRIBUTE rather
    than through a selector — `className.includes('in_library')`,
    `className.split(' ').includes('primary')`, `className.replace('ep
    ', '')`, `className === 'card'`, a regex of class names tested
    against `className`, a table matched against a SPREAD `classList`,
    and a CSS rule the harness injects. None of them is
    selector-shaped, so neither pass above sees one, and four of the six
    sat on lines a migration had just rewritten. They enter `--tokens`'s
    total and `--baseline` under `"kind": "read"`; the two shapes that
    quote no name carry a null token, because a name nobody writes down
    is a dependency all the same.

WHAT IT DOES NOT READ. A call whose argument is not a string literal — a
variable, an expression — is a CALL this tool cannot name; the string
that defines the variable is the held pass's business instead, if it is
selector-shaped. `classList.contains(...)` assertions are a second
population: they are reported by `--baseline` under `"kind":
"assertion"` — every one of them whose SITE is not a declared genre
exception — and never mixed into the selection table. Comments and
docstrings are read by nothing at runtime, so they are read by nothing
here: Python comments are blanked exactly, the JS comments of the
embedded-JS containers are blanked, and a triple-quoted docstring is
skipped whole. Nothing outside the harness directory is READ — the
design sources enter only as the emission side of the false-positive
rule below.

THE FALSE-POSITIVE RULE, AND IT IS A RULE, NOT A LIST. A candidate
string is a selector only if EVERY class token it carries is EMITTED by
at least one of the three design sites — `frontend/maquette/design/
index.html`, `design/src/engine/legacy.js` and the sources under
`design/src` — as a class= / className= token, OR the string carries
selector structure: a combinator, an attribute block, a comma list.
`.json5` fails both — nothing emits a class named json5, and the string
has no structure — while `.tile[data-panel]` passes on structure and
`.sact` passes on emission. A shape test runs first, `selector_shaped`:
the string starts with `.`, `#` or `[` — after any LEADING SPACE, since
a selector concatenated onto a variable begins with the descendant
combinator — holds only selector-alphabet characters once its BALANCED
`{...}` interpolations are removed, carries no `=` outside an attribute
block, and is not a method call (`.render(`). An interpolation is an
OPAQUE token: it does not end the selector, and it contributes no name,
because a computed class names no literal at rest. A candidate with no
class token is not recorded: the unit of the measurement is the class
token occurrence, and a string with none owes it nothing.

Usage:
    python3 scripts/classify-rule-anchors.py --summary [root]
    python3 scripts/classify-rule-anchors.py --tokens [root]
    python3 scripts/classify-rule-anchors.py --exceptions [root]
    python3 scripts/classify-rule-anchors.py --baseline [root]

The optional `root` replaces the harness directory; it exists so a mutation
test can measure a scratch copy without editing the real rules.
"""

from __future__ import annotations

import io
import json
import re
import sys
import tokenize
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = ROOT / "frontend" / "maquette" / "harness"

# `classList.contains('open')` — the assertion population, one class name per
# call.
CONTAINS = re.compile(r"classList\.contains\(\s*(['\"])([^'\"]*)\1\s*\)")

# The permanent genre assertions, keyed on the SITE and each carrying its own
# reason. The table is DECLARED next door, in the importable module, and read
# from here rather than copied: an exemption is a decision, and a decision with
# two copies is a decision that drifts. What is NOT shared is the extraction —
# this tool still walks the corpus with its own passes, which is the whole
# point of a second reader.
#
# A shared sentence used to cover five names; it read true of three sites and
# false of two, and a reason that covers everything distinguishes nothing.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from markup_anchors import GENRE_SITES  # noqa: E402
# This tool's OWN text readers — see that module's header for why they are a
# mirror of the guard's and not an import of them.
from anchor_readers import (  # noqa: E402
    CALL, class_attribute_reads, class_tokens, emission_tokens,
    held_selectors, read_literal, strip_interpolations,
)

# The anchors, printed in a fixed order so a diff of the report means
# something.
ANCHORS = ("class", "data-*", "id", "tag", "role")



def anchor_of(selector: str) -> str:
    """Classifies one selector by the precedence rule.

    The strongest anchor present decides, strongest first: `data-*` over
    `id` over `class` over `role` over `tag`. Attribute blocks `[...]` are
    read as a whole, so a `.token` or `#name` inside one — an attribute
    value, not a selector — does not count.

    Args:
        selector: One selector string, its interpolations already stripped.

    Returns:
        The anchor name: `data-*`, `id`, `class`, `role`, or `tag`.
    """
    has_data = False
    has_role = False
    has_id = False
    has_class = False
    i = 0
    while i < len(selector):
        ch = selector[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "[":
            end = selector.find("]", i)
            block = selector[i:end + 1] if end != -1 else selector[i:]
            if re.search(r"data-[\w-]+", block):
                has_data = True
            if re.search(r"role\s*=", block):
                has_role = True
            i = end + 1 if end != -1 else len(selector)
            continue
        if ch == "#":
            has_id = True
        elif ch == ".":
            has_class = True
        i += 1
    if has_data:
        return "data-*"
    if has_id:
        return "id"
    if has_class:
        return "class"
    if has_role:
        return "role"
    return "tag"



def selection_calls(path: Path) -> list[tuple[int, str, str]]:
    """Extracts every literal-argument selection call in one harness file.

    Args:
        path: A Python file under the measured root.

    Returns:
        `(line, method, selector)` tuples, in file order, one per call whose
        first argument is a string literal. A call given a variable or an
        expression is not named here and is not returned.
    """
    text = path.read_text(encoding="utf-8")
    found: list[tuple[int, str, str]] = []
    for match in CALL.finditer(text):
        pos = match.end()
        while pos < len(text) and text[pos] in " \t\n":
            pos += 1
        if pos >= len(text) or text[pos] not in ("'", '"', "`"):
            continue
        literal = read_literal(text, pos)
        if literal is None:
            continue
        content, _ = literal
        if text[pos] == "`":
            content = strip_interpolations(content)
        line = text.count("\n", 0, match.start()) + 1
        found.append((line, match.group(1), content))
    return found


def state_assertions(path: Path) -> list[tuple[int, str]]:
    """Extracts every quoted `classList.contains` assertion in one file.

    Args:
        path: A Python file under the measured root.

    Returns:
        `(line, class_name)` tuples, in file order.
    """
    text = path.read_text(encoding="utf-8")
    found: list[tuple[int, str]] = []
    for match in CONTAINS.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        found.append((line, match.group(2)))
    return found




def collect(root: Path) -> tuple[list[tuple[str, int, str, str]],
                                  list[tuple[str, int, str]],
                                  list[tuple[str, int, str]],
                                  list[tuple[str, int, str | None]]]:
    """Collects every selection call, assertion, held selector and read.

    Args:
        root: The directory whose `*.py` files are the corpus.

    Returns:
        Selections as `(file, line, method, selector)`, assertions as
        `(file, line, class_name)`, held selectors as
        `(file, line, content)` and class-attribute reads as
        `(file, line, class_name_or_None)`, each in file order.
    """
    selections: list[tuple[str, int, str, str]] = []
    assertions: list[tuple[str, int, str]] = []
    held: list[tuple[str, int, str]] = []
    reads: list[tuple[str, int, str | None]] = []
    emitted = emission_tokens()
    if not emitted:
        print("classify-rule-anchors: no class= / className= emission "
              "found in the design sources — the held pass cannot tell a "
              "selector from a word, so its count would mean nothing",
              file=sys.stderr)
    for path in sorted(p for p in root.glob("*.py") if p.is_file()):
        rel = (str(path.relative_to(ROOT))
               if path.is_relative_to(ROOT) else str(path))
        selections += [(rel, line, method, selector)
                       for line, method, selector in selection_calls(path)]
        assertions += [(rel, line, name)
                       for line, name in state_assertions(path)]
        text = path.read_text(encoding="utf-8")
        held += [(rel, text.count("\n", 0, start) + 1, content)
                 for start, content in held_selectors(text, emitted)]
        reads += [(rel, text.count("\n", 0, start) + 1, name)
                  for start, name in class_attribute_reads(text)]
    return selections, assertions, held, reads


def print_summary(selections: list[tuple[str, int, str, str]]) -> None:
    """Prints the per-anchor table and the total of selection calls.

    Args:
        selections: The corpus as `(file, line, method, selector)` tuples.
    """
    counts = Counter(anchor_of(selector)
                     for _, _, _, selector in selections)
    print(f"{'anchor':<8}{'calls':>6}")
    print(f"{'-' * 8}{'-' * 6:>7}")
    for anchor in ANCHORS:
        print(f"{anchor:<8}{counts[anchor]:>6}")
    print(f"{'-' * 8}{'-' * 6:>7}")
    print(f"{len(selections)} selection calls")


def print_tokens(selections: list[tuple[str, int, str, str]],
                 held: list[tuple[str, int, str]],
                 reads: list[tuple[str, int, str | None]]) -> None:
    """Prints every class token occurrence and the per-selector split.

    The total is the lot's real size: every `.token` outside a `[...]` block,
    however the selector is anchored, IN a selection call or HELD outside
    one. The split underneath it names the two populations — the class-only
    selectors `--summary` already sees, and the tokens hiding behind a
    stronger anchor that only this mode can see. A token is counted once
    per occurrence, so one selector carrying two class tokens counts
    twice.

    Args:
        selections: The corpus as `(file, line, method, selector)` tuples.
        held: The held selectors as `(file, line, content)` tuples.
        reads: The class-attribute reads as `(file, line, name)` tuples —
            a name read WITHOUT a selector is a dependency on the
            stylesheet exactly like one written in a selector, and
            leaving it out of the total would under-count the lot the way
            the one-bucket rule once did.
    """
    tokens: Counter[str] = Counter()
    carrying = 0
    class_only = 0
    for _, _, _, selector in selections:
        found = class_tokens(selector)
        if not found:
            continue
        carrying += 1
        if anchor_of(selector) == "class":
            class_only += 1
        tokens.update(found)
    behind = carrying - class_only
    held_tokens: Counter[str] = Counter()
    for _, _, content in held:
        held_tokens.update(class_tokens(content))
    print(f"{'token':<20}{'occurrences':>12}")
    print(f"{'-' * 20}{'-' * 12:>13}")
    for name, count in sorted(tokens.items()):
        print(f"{name:<20}{count:>12}")
    print(f"{'-' * 20}{'-' * 12:>13}")
    for name, count in sorted(held_tokens.items()):
        print(f"{name:<20}{count:>12}")
    print(f"{'-' * 20}{'-' * 12:>13}")
    print(f"{sum(tokens.values())} class token occurrences in selection calls")
    print(f"{carrying} selectors carry at least one class token")
    print(f"  {class_only} where the class is the only anchor")
    print(f"  {behind} where it hides behind a stronger anchor")
    print(f"{len(selections) - carrying} calls carry no class token at all")
    print(f"{sum(held_tokens.values())} class token occurrences held "
          "outside any selection call")
    print(f"{len(reads)} class name(s) read from the class attribute, "
          "outside any selector")
    print(f"{sum(tokens.values()) + sum(held_tokens.values()) + len(reads)} "
          "class token occurrences total")


def print_exceptions() -> None:
    """Prints the permanent genre assertions: one SITE, one reason.

    The exemption names `file:line class`, never the class alone. A
    name-keyed exemption exempts every line that name appears on: `flux`
    and `h2` were exempt as « the applied style » while `machine.py` used
    them to walk siblings and find the flux list, which is structure, and
    the written reason described a geometry rule two files over.
    """
    for (file, line, name), reason in sorted(GENRE_SITES.items()):
        print(f"{file}:{line} {name:<8} {reason}")


def print_baseline(selections: list[tuple[str, int, str, str]],
                   assertions: list[tuple[str, int, str]],
                   held: list[tuple[str, int, str]],
                   reads: list[tuple[str, int, str | None]]) -> None:
    """Prints the class-anchor listing as JSON: one entry per occurrence.

    THE LISTING IS EXPECTED EMPTY, and that is what it is for. The guard
    refuses the first class anchor it finds; this mode is the SECOND reader
    of the same corpus, by its own extraction, and `[]` from both is the
    measurement — one reader's zero is a claim.

    The listing is keyed on the token OCCURRENCE, not the selector — a selector
    carrying two class tokens owes two entries, each carrying the full selector
    AND the `token` it is about. An entry the held pass found carries
    `"held": true`; a call entry carries `"held": false` — the two populations
    must stay tellable apart. `assertion` entries carry the class name, and the
    five genre assertions are permanent exceptions, listed by `--exceptions`.

    Args:
        selections: The corpus as `(file, line, method, selector)` tuples.
        assertions: The corpus as `(file, line, class_name)` tuples.
        held: The held selectors as `(file, line, content)` tuples.
        reads: The class-attribute reads as `(file, line, name)` tuples;
            they enter under `"kind": "read"`, and the two shapes that
            quote no name carry `"token": null`.
    """
    entries: list[dict[str, object]] = []
    for rel, line, _, selector in selections:
        for token in class_tokens(selector):
            entries.append({"kind": "selection", "held": False, "file": rel,
                            "line": line, "selector": selector,
                            "token": token})
    for rel, line, content in held:
        for token in class_tokens(content):
            entries.append({"kind": "selection", "held": True, "file": rel,
                            "line": line, "selector": content,
                            "token": token})
    for rel, line, name in reads:
        entries.append({"kind": "read", "file": rel, "line": line,
                        "token": name})
    for rel, line, name in assertions:
        if (Path(rel).name, line, name) not in GENRE_SITES:
            entries.append({"kind": "assertion", "file": rel,
                            "line": line, "class": name})
    entries.sort(key=lambda e: (str(e["file"]), int(e["line"]), str(e["kind"]),
                                str(e.get("selector", e.get("class"))),
                                str(e.get("token", ""))))
    print(json.dumps(entries, indent=2))


def main() -> int:
    """Runs one mode over the harness corpus and prints its report.

    Returns:
        0 on success; 1 when the arguments are unknown, the root holds no
        Python files, or the root holds no selection call at all.
    """
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    positional = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(flags) > 1 or any(f not in ("--summary", "--tokens", "--exceptions",
                                       "--baseline") for f in flags):
        print("classify-rule-anchors: unknown arguments — "
              "--summary | --tokens | --exceptions | --baseline [root]",
              file=sys.stderr)
        return 1
    mode = flags[0] if flags else "--summary"
    root = Path(positional[0]) if positional else DEFAULT_ROOT

    files = sorted(p for p in root.glob("*.py") if p.is_file())
    if not files:
        print(f"classify-rule-anchors: no Python files under {root} — the "
              "scope is empty, so « no selection » would mean nothing",
              file=sys.stderr)
        return 1

    selections, assertions, held, reads = collect(root)
    if not selections:
        print(f"classify-rule-anchors: no selection call found under {root} — "
              "either the extraction broke or the root is wrong",
              file=sys.stderr)
        return 1

    if mode == "--summary":
        print_summary(selections)
    elif mode == "--tokens":
        print_tokens(selections, held, reads)
    elif mode == "--exceptions":
        print_exceptions()
    else:
        print_baseline(selections, assertions, held, reads)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

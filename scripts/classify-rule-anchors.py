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
OCCURRENCE, not the selector: one selector can carry tokens owned by two
different phases, so only the occurrence has a single owning phase. That is
why `--baseline` emits one entry per occurrence, each naming the token that
entry is about.

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

WHAT IT READS. The string argument of every `querySelector`,
`querySelectorAll`, `locator` and `matches` call across
`frontend/maquette/harness/*.py`, read as text — both quoting styles and
template literals. Three calls pass their selector in backticks with a
`${...}` interpolation inside; the interpolation is unknown at rest and is
stripped before classifying, so the literal text that remains decides the
anchor.

WHAT IT DOES NOT READ. A call whose argument is not a string literal — a
variable, an expression — is a selection this tool cannot name, and it is not
counted. `classList.contains(...)` assertions are a second population: they
are reported by `--baseline` under `"kind": "assertion"` and never mixed into
the selection table. Nothing outside the harness directory is read.

Usage:
    python3 scripts/classify-rule-anchors.py --summary [root]
    python3 scripts/classify-rule-anchors.py --tokens [root]
    python3 scripts/classify-rule-anchors.py --exceptions [root]
    python3 scripts/classify-rule-anchors.py --baseline [root]

The optional `root` replaces the harness directory; it exists so a mutation
test can measure a scratch copy without editing the real rules.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = ROOT / "frontend" / "maquette" / "harness"

# `querySelector(` et al. — every call whose first argument is the selection,
# whatever object the method hangs off (`document.`, `c.`, `s.`, ...).
CALL = re.compile(r"(querySelector|querySelectorAll|locator|matches)\s*\(")

# `classList.contains('open')` — the assertion population, one class name per
# call.
CONTAINS = re.compile(r"classList\.contains\(\s*(['\"])([^'\"]*)\1\s*\)")

# The seven state classes the lot migrates to the boolean data-* attributes.
# `classList.contains` on one of these is a state assertion and belongs in the
# baseline.
STATE_CLASSES = ("open", "noposter", "show", "in_library",
                 "fempty", "fblocked", "announced")

# The five permanent genre assertions, each with its reason for staying on the
# class. The reason is the same for every entry: the assertion's subject is
# the applied style, so a data-* would keep it true after the class is gone
# and the rule would measure less than it does today. A reason-less entry
# would itself be a violation, exactly as for a `french-ok` pragma — this list
# cannot produce one, because the reason is a single non-empty constant.
GENRE_CLASSES = ("h2", "flux", "ep", "radio", "note")
GENRE_REASON = ("the assertion's subject is the applied style — moving it to "
                "a `data-*` would keep it true even after the class is gone, "
                "and the rule would measure less than it does today")

# The anchors, printed in a fixed order so a diff of the report means
# something.
ANCHORS = ("class", "data-*", "id", "tag", "role")


def read_literal(text: str, start: int) -> tuple[str, int] | None:
    """Returns the string literal opening at `start` and the index past it.

    Backslash-escaped characters are skipped, so an escaped delimiter inside
    the literal does not end it early. A backtick template ends at its closing
    backtick the same way.

    Args:
        text: The file text being read.
        start: Index of the opening quote or backtick.

    Returns:
        The literal's content and the index just past the closing delimiter,
        or None when the literal never closes.
    """
    delimiter = text[start]
    i = start + 1
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == delimiter:
            return text[start + 1:i], i + 1
        i += 1
    return None


def strip_interpolations(selector: str) -> str:
    """Removes `${...}` spans from a template-literal selector.

    The interpolation's value is unknown at rest, so it is removed and the
    literal text that remains decides the anchor — a selector written as
    `[data-lmode="${m}"]` stays data-anchored, because the attribute NAME is
    literal while only its value is computed.

    Args:
        selector: A selector read from a backtick template literal.

    Returns:
        The selector with every balanced `${...}` span removed.
    """
    out: list[str] = []
    i = 0
    while i < len(selector):
        if selector.startswith("${", i):
            depth = 0
            j = i + 2
            while j < len(selector):
                if selector[j] == "{":
                    depth += 1
                elif selector[j] == "}":
                    if depth == 0:
                        break
                    depth -= 1
                j += 1
            i = j + 1
            continue
        out.append(selector[i])
        i += 1
    return "".join(out)


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


def class_tokens(selector: str) -> list[str]:
    """Returns every class token in one selector, in reading order.

    A class token is a `.` followed by name characters, outside any `[...]`
    block — an attribute block's contents are values, not selectors. Every
    token is returned, not only the strongest anchor's: `#view .swipe` yields
    `.swipe` even though the selector is id-anchored, because that token dies
    with the stylesheet exactly like a class-anchored one.

    Args:
        selector: One selector string, its interpolations already stripped.

    Returns:
        The `.name` tokens found, each with its leading dot, or an empty list.
    """
    tokens: list[str] = []
    i = 0
    while i < len(selector):
        ch = selector[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "[":
            end = selector.find("]", i)
            i = end + 1 if end != -1 else len(selector)
            continue
        if ch == ".":
            j = i + 1
            while j < len(selector) and (selector[j].isalnum()
                                         or selector[j] in "-_"):
                j += 1
            if j > i + 1:
                tokens.append(selector[i:j])
                i = j
                continue
        i += 1
    return tokens


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
                                  list[tuple[str, int, str]]]:
    """Collects every selection call and state assertion under `root`.

    Args:
        root: The directory whose `*.py` files are the corpus.

    Returns:
        Selections as `(file, line, method, selector)` and assertions as
        `(file, line, class_name)`, each in file order.
    """
    selections: list[tuple[str, int, str, str]] = []
    assertions: list[tuple[str, int, str]] = []
    for path in sorted(p for p in root.glob("*.py") if p.is_file()):
        rel = (str(path.relative_to(ROOT))
               if path.is_relative_to(ROOT) else str(path))
        selections += [(rel, line, method, selector)
                       for line, method, selector in selection_calls(path)]
        assertions += [(rel, line, name)
                       for line, name in state_assertions(path)]
    return selections, assertions


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


def print_tokens(selections: list[tuple[str, int, str, str]]) -> None:
    """Prints every class token occurrence and the per-selector split.

    The total is the lot's real size: every `.token` outside a `[...]` block,
    however the selector is anchored. The split underneath it names the two
    populations — the class-only selectors `--summary` already sees, and the
    tokens hiding behind a stronger anchor that only this mode can see. A
    token is counted once per occurrence, so one selector carrying two class
    tokens counts twice.

    Args:
        selections: The corpus as `(file, line, method, selector)` tuples.
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
    print(f"{'token':<20}{'occurrences':>12}")
    print(f"{'-' * 20}{'-' * 12:>13}")
    for name, count in sorted(tokens.items()):
        print(f"{name:<20}{count:>12}")
    print(f"{'-' * 20}{'-' * 12:>13}")
    print(f"{sum(tokens.values())} class token occurrences")
    print(f"{carrying} selectors carry at least one class token")
    print(f"  {class_only} where the class is the only anchor")
    print(f"  {behind} where it hides behind a stronger anchor")
    print(f"{len(selections) - carrying} calls carry no class token at all")


def print_exceptions() -> None:
    """Prints the five permanent genre assertions, each with its reason."""
    for name in GENRE_CLASSES:
        print(f"{name:<8} {GENRE_REASON}")


def print_baseline(selections: list[tuple[str, int, str, str]],
                   assertions: list[tuple[str, int, str]]) -> None:
    """Prints the baseline as JSON: one entry per class token occurrence.

    The burn-down is keyed on the token OCCURRENCE, not the selector — a
    selector carrying two class tokens owes work to two entries, because the
    tokens can be owned by different phases. Each `selection` entry therefore
    carries the full selector AND the `token` it is about; two tokens in one
    selector are two entries. `assertion` entries carry the class name, and
    the five genre assertions are permanent exceptions, not part of the
    baseline.

    Args:
        selections: The corpus as `(file, line, method, selector)` tuples.
        assertions: The corpus as `(file, line, class_name)` tuples.
    """
    entries: list[dict[str, object]] = []
    for rel, line, _, selector in selections:
        for token in class_tokens(selector):
            entries.append({"kind": "selection", "file": rel, "line": line,
                            "selector": selector, "token": token})
    for rel, line, name in assertions:
        if name in STATE_CLASSES:
            entries.append({"kind": "assertion", "file": rel,
                            "line": line, "class": name})
        elif name not in GENRE_CLASSES:
            print(f"classify-rule-anchors: {rel}:{line}: "
                  f"`classList.contains('{name}')` is neither a migrated state "
                  "nor a listed genre — it is counted in neither population",
                  file=sys.stderr)
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

    selections, assertions = collect(root)
    if not selections:
        print(f"classify-rule-anchors: no selection call found under {root} — "
              "either the extraction broke or the root is wrong",
              file=sys.stderr)
        return 1

    if mode == "--summary":
        print_summary(selections)
    elif mode == "--tokens":
        print_tokens(selections)
    elif mode == "--exceptions":
        print_exceptions()
    else:
        print_baseline(selections, assertions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

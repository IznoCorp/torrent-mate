#!/usr/bin/env python3
"""Refuses four defect classes — four arms, each naming the corpus it
reads. Read the arm whose scope you are touching.

ARM 1 — a `data-*` value the markup emits and no reader understands.
Corpus: `frontend/maquette/design/src`, every `.js`, `.ts` and `.tsx`
file, read as text.

THE DEFECT CLASS, and it cost eight contracts in one day. The prototype
drives itself by delegation: markup carries `data-X="value"`, a click
handler writes that value VERBATIM into a store field, and components
compare the field against the values they know.

    <button data-phase="ready">                     the markup emits
    store.write({ phase: closest.dataset.phase })   the handler writes, verbatim
    state.phase === "ready"                          the reader compares

Three ends, and nothing tied them together. So a rename that moved two of
them left the third behind, every time, and the control simply stopped
working while every gate stayed green:

  * `data-phase="prete"` on the « Réessayer » button of every error
    surface. No reader knows `prete`, so the retry wrote a phase nothing
    renders and the error screen never cleared.
  * `data-hscen="reel"` / `"charge"` on the harness's data-scenario dial,
    whose readers compare `real` / `loaded`. Clicking « État réel » landed
    on the loaded branch and both buttons showed unpressed.

Neither was found by reading the diff, by the 50-rule suite, or by a
sweep for French strings — they are not French-vs-English, they are
markup-vs-reader. This arm asks the only question that catches them:
**does anything understand what this button writes?**

WHAT ARM 1 READS. Handlers of the shape
`store.write({ field: …dataset.name })` give the `data-name` → `field`
map. Every `data-name="value"` in the maquette's sources is then checked
against the values any reader compares that field against —
`field === "v"`, `.field === "v"`, `field: "v"`, `["field"] == "v"`.

WHAT ARM 1 DOES NOT READ. A handler that TRANSLATES rather than forwards
(`dataset.x === "a" ? "b" : "c"`) is out of scope: the emitted value is
then an input to a decision, not a stored value, and holding it here
would report a defect that is not one.

ARM 2 — a rule selection anchored on a style class.
Corpus: `frontend/maquette/harness`, every `*.py` file, read as text.

THE DEFECT CLASS. The harness rules select elements by their style class
— `querySelector('.card')` — and those names are the stylesheet's. The
day a surface converts to utility classes the names stop existing, and
every rule that reads them falls with no way to attribute the failure:
anchor, or style? This arm refuses NEW class anchors, and holds the ones
already shipped in a burn-down baseline that later phases of the
maquette-l02 lot remove entry by entry until the file is empty and
deleted.

WHAT ARM 2 READS, AND THE TWO REFUSALS.

  1. A class TOKEN in a selection. The string argument of every
     `querySelector`, `querySelectorAll`, `locator` and `matches` call is
     read the way `classify-rule-anchors.py --tokens` reads it: `${...}`
     interpolations and every `[...]` block are stripped, then EVERY
     `.token` that remains is a finding — NOT the strongest anchor.
     `#view .swipe` is id-anchored by precedence and still dies the day
     the `.swipe` class is removed; a guard that refused only pure class
     anchors would reproduce the 54 % under-measurement D4's own method
     was found to make.

  2. `classList.contains('<state>')` for one of the seven migrated
     states: open, noposter, show, in_library, fempty, fblocked,
     announced. The five genre assertions — h2, flux, ep, radio, note —
     are NEVER refused: their subject IS the applied style, so moving
     them to a data-* attribute would make them true after the class is
     gone and the rule would measure less than it does today. They are
     permanent exceptions; each one's written reason lives in
     `scripts/classify-rule-anchors.py` (--exceptions).

THE BURN-DOWN IS A RATCHET, NOT A PROMISE.
`frontend/maquette/anchor-baseline.json` holds one entry per TOKEN
OCCURRENCE — a selector can carry tokens owned by two different phases,
and only the occurrence has a single owner. An occurrence's IDENTITY is
what it selects, not where it sits: the multiset of
(kind, file, selector, token), with the class name filling both last
slots for an assertion. The `line` stored in each entry is a DISPLAY
field, refreshed freely on every write. A finding whose identity the
baseline owns is tolerated and counted — multiplicity included, the same
identity twice is two entries and must stay two; one it does not exits 1
naming file, line, selector and token. Every later phase REMOVES entries
— a baseline that swallowed a NEW violation would ratchet the wrong way,
and this arm's whole reason to exist is to refuse that.

The baseline is GENERATED, never typed. `--write-baseline` consumes
`python3 scripts/classify-rule-anchors.py --baseline` — the independent
second reader, so the classification is cross-checked by something other
than the guard that enforces it — then holds the two readers against each
other and writes the file only when they agree on every occurrence.

AND IT REFUSES TO GROW. Before writing, the fresh entries are held
against the stored baseline on their line-free identities: any occurrence
the stored baseline does not already own REFUSES the write — exit 1,
naming each one — because a burn-down list does not grow. Removals pass
silently; that is the burn-down. A pure line shift still writes (nothing
added, only display lines moved), which phases 2 to 6 depend on: they
edit harness files in every commit. The deliberate escape hatch is
`--write-baseline --allow-additions` — bootstrap, a re-classification, a
corrupted baseline — which writes regardless and prints loudly what it
added. Nothing in phases 2 to 6 of maquette-l02 may use it.

ARM 3 — a `data-part` value the harness selects and no source emits.
Two corpora, one question each side answers. The selection side is the
harness (`frontend/maquette/harness/*.py`, the same set ARM 2 reads):
every `[data-part="value"]` in a rule's selector — the three quote
styles, a template literal's included. The emission side is the three
sites that emit the attribute: `frontend/maquette/design/index.html`
(the shell), `src/engine/legacy.js` (the engine) and every `.ts` /
`.tsx` component.

THE DEFECT CLASS. A rule selecting `[data-part="card/title"]` reads a
name the markup must emit. A value selected and emitted nowhere is a
rule selecting nothing — the three-ends contract, caught from the
markup end. The direction is ONE-WAY: every selected value must be
emitted somewhere; an emitted value no rule selects is fine, not every
part needs a rule. A computed value — a selection whose value is a
`${...}` interpolation — names no literal to compare, and is skipped
rather than half-read, exactly as ARM 1 skips computed emissions.
Comments are stripped on both sides: a value a COMMENT carries is
selected by nothing and emitted by nothing.

VACUOUS TODAY, BY DESIGN. No `data-part` exists anywhere yet — phase 2
writes the first ones. This arm therefore examines ZERO selections on
this tree, and a green exit proves nothing about it. The count it
prints is the point: a number nobody prints is a number nobody can
notice is zero. It is proven by probe-mutation instead, and becomes
load-bearing the day phase 2 lands.

ARM 4 — a boolean state attribute written as a bare value.
Corpus: the components — every `.ts` and `.tsx` file under
`frontend/maquette/design/src`, read as text.

THE DEFECT CLASS, MEASURED, NOT BELIEVED. React renders the boolean
`false` into an attribute as the STRING "false": the attribute is
PRESENT, a presence selector such as `[data-open]` matches it ALWAYS,
and a hold built on that selector stays green while the state it claims
to read is never absent. harness/attrs.py demonstrated both halves in
the live document — the string "false" renders, and the presence
selector matches it. So the seven state attributes — data-open,
data-no-poster, data-empty, data-blocked, data-announced,
data-in-library, data-shown — must be written so a false state omits
them. The accepted spellings are `data-open={x || undefined}`, or the
equivalent `{x ? "" : undefined}` / `{x ? true : undefined}`: each
reaches `undefined` when the boolean is false, and `undefined` is the
value React omits from the markup. A bare `data-open={x}` is refused; a
literal `data-open` with no braces is a constant attribute and fine.

VACUOUS TODAY, BY DESIGN. No boolean state attribute exists yet — phase
2 writes the first ones. This arm therefore examines ZERO attributes,
and its green exit proves nothing about it; the count it prints is the
point. attrs.py's holds measured `aria-*` and `title` — the same
passthrough, not the same attribute — and owe the real `data-open` a
second demonstration on the day it first exists; the gap is closed by
re-measuring, not by analogy. Until then the arm is proven by
probe-mutation.

Usage:
    python3 scripts/check-markup-contracts.py
    python3 scripts/check-markup-contracts.py --write-baseline
    python3 scripts/check-markup-contracts.py --write-baseline --allow-additions
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "frontend" / "maquette" / "design" / "src"

# `store.write({ pipe: closest.dataset.pipe })` — the handler that FORWARDS a
# markup value into a store field. The two names differ often enough
# (`data-hphase` → `phase`) that both are captured.
FORWARDER = re.compile(
    r"store\.write\(\{\s*(?P<field>\w+)\s*:\s*\w+\.dataset\.(?P<attr>\w+)\s*,?\s*\}\)")

# `data-name="value"` in emitted markup or JSX. A value carrying `${` is
# computed, and this rule cannot know what it evaluates to.
EMITTED = re.compile(r"""data-(?P<attr>[a-z][\w-]*)=["'](?P<value>[^"'${]+)["']""")

# Comments are stripped before anything is read. `library.tsx` carries a comment
# describing a REJECTED first version — « gated it on `phase === "prete"` » —
# and reading it as code made this rule believe `prete` was a value some reader
# understood, so it walked past the dead retry button it was written to catch.
# Reading CSS as text cost the token guard the same way, one file over.
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)

# ---- ARM 2 constants ----------------------------------------------------

# The anchor arm's corpus: the harness rules, the same `*.py` set
# `classify-rule-anchors.py` reads. The two readers must share the corpus
# or the cross-check they are held against each other in `--write-baseline`
# measures nothing.
HARNESS = ROOT / "frontend" / "maquette" / "harness"

# The burn-down baseline. Generated, never typed — `--write-baseline`
# regenerates it from the independent classifier.
BASELINE = ROOT / "frontend" / "maquette" / "anchor-baseline.json"

# The independent second reader, consumed as a subprocess rather than
# imported: a baseline the guard derives alone is a classification
# cross-checked by nothing.
CLASSIFIER = ROOT / "scripts" / "classify-rule-anchors.py"

# `querySelector(` et al. — every call whose first argument is the
# selection, whatever object the method hangs off (`document.`, `c.`,
# `s.`, ...). Same reading as the classifier: the method is pinned there
# and mirrored here on purpose.
CALL = re.compile(r"(querySelector|querySelectorAll|locator|matches)\s*\(")

# `classList.contains('open')` — the assertion population, one class name
# per call.
CONTAINS = re.compile(r"classList\.contains\(\s*(['\"])([^'\"]*)\1\s*\)")

# The seven state classes the maquette-l02 lot migrates to the boolean
# data-* attributes. `classList.contains` on one of these is a state
# assertion, refused unless the baseline owns the occurrence.
STATE_CLASSES = ("open", "noposter", "show", "in_library",
                 "fempty", "fblocked", "announced")

# The five permanent genre assertions, never refused. Their written
# reasons live in `classify-rule-anchors.py --exceptions`: the assertion's
# subject is the applied style, so a data-* would keep it true after the
# class is gone and the rule would measure less than it does today. They
# are listed here so a NEW contains() name is recognized as neither.
GENRE_CLASSES = ("h2", "flux", "ep", "radio", "note")

# ---- ARM 3 constants ----------------------------------------------------

# The shell, one of the three emission sites. Served and written outside
# the sources glob, so it is named on its own.
SHELL = SOURCES.parent / "index.html"

# HTML comments are the shell's comment shape; the JS-style COMMENT regex
# reads the sources. Same question, one stripper per corpus.
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

# `[data-part="card/title"]` in a rule's selector — the equality form in
# its three quote styles. Only the equality form is read: a presence
# selection `[data-part]` names no part, and this arm holds VALUES.
PART_SELECTED = re.compile(
    r"\[\s*data-part\s*=\s*(?:\"(?P<dq>[^\"]*)\"|"
    r"'(?P<sq>[^']*)'|`(?P<bk>[^`]*)`)\s*\]")

# ---- ARM 4 constants ----------------------------------------------------

# The seven boolean state attributes, the migration's destination for the
# seven state classes of ARM 2 (open → data-open, noposter →
# data-no-poster, fempty → data-empty, …). Class names and attribute
# names differ on purpose: each side keeps its own naming.
STATE_ATTRS = ("open", "no-poster", "empty", "blocked",
               "announced", "in-library", "shown")

# `data-open={` — a state attribute written from a braced JSX expression.
# The literal attribute (no braces) is a constant and fine; the
# expression is what the trap turns on.
STATE_WRITTEN = re.compile(
    "data-(?P<attr>" + "|".join(STATE_ATTRS) + r")\s*=\s*\{")

# The three spellings that omit the attribute when the state is false, so
# a presence selector never matches a false value. `undefined` (like
# `null`) is the value React omits from the markup, and each tail reaches
# it exactly when the boolean is false — the bare `{x}` reaches it never.
OMITTING_TAILS = ("||undefined", "?\"\":undefined", "?true:undefined")


def readers_of(field: str, sources: str) -> set[str]:
    """Returns every literal value some reader compares `field` against.

    Args:
        field: The store field's name.
        sources: All maquette source text, concatenated.

    Returns:
        The set of literal values, including the ones written as defaults.
    """
    patterns = [
        rf"""\b{field}\s*===?\s*["']([^"']+)["']""",
        rf"""\.{field}\s*===?\s*["']([^"']+)["']""",
        rf"""\[["']{field}["']\]\s*===?\s*["']([^"']+)["']""",
        rf"""\b{field}\s*:\s*["']([^"']+)["']""",
    ]
    found: set[str] = set()
    for pattern in patterns:
        found |= set(re.findall(pattern, sources))
    return found


def check_forwarded_values() -> int:
    """Arm 1: checks every forwarded `data-*` value against the readers
    of its field.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    files = [p for p in sorted(SOURCES.rglob("*"))
             if p.is_file() and p.suffix in {".js", ".ts", ".tsx"}]
    if not files:
        print(f"check-markup-contracts: no sources under {SOURCES} — the "
              "scope is empty, so « no violation » would mean nothing",
              file=sys.stderr)
        return 1
    text = {p: p.read_text(encoding="utf-8") for p in files}
    # Comments describe what was TRIED; only code says what is understood.
    joined = COMMENT.sub(" ", "\n".join(text.values()))

    forwarded = {m.group("attr"): m.group("field")
                 for m in FORWARDER.finditer(joined)}
    if not forwarded:
        print("check-markup-contracts: no `store.write({f: …dataset.x})` "
              "handler found — either the delegation changed shape or this "
              "rule is reading the wrong tree", file=sys.stderr)
        return 1

    violations = 0
    checked = 0
    for path, source in text.items():
        for match in EMITTED.finditer(source):
            attr, value = match.group("attr"), match.group("value").strip()
            field = forwarded.get(attr)
            if field is None:
                continue                      # not forwarded: not this rule's business
            checked += 1
            known = readers_of(field, joined)
            if value not in known:
                line = source.count("\n", 0, match.start()) + 1
                rel = path.relative_to(ROOT)
                print(f"  {rel}:{line}: `data-{attr}=\"{value}\"` is written "
                      f"verbatim into `{field}`, and no reader compares "
                      f"`{field}` against {value!r}. The control is dead: it "
                      f"writes a value nothing renders. Known: "
                      f"{sorted(known) or '(none)'}", file=sys.stderr)
                violations += 1

    if violations:
        print(f"\ncheck-markup-contracts: {violations} dead control(s). A "
              "`data-*` value, the handler that forwards it and the readers "
              "that compare it are ONE contract — they move together or the "
              "button stops working in silence.", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {len(forwarded)} forwarded attribute(s), "
          f"{checked} emitted value(s), every one understood by a reader.")
    return 0


def read_literal(text: str, start: int) -> tuple[str, int] | None:
    """Returns the string literal opening at `start` and the index past it.

    Args:
        text: The file text being read.
        start: Index of the opening quote or backtick.

    Returns:
        The literal's content and the index just past the closing
        delimiter, or None when the literal never closes.
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

    The interpolation's value is unknown at rest, so it is removed and
    the literal text that remains decides what the guard sees — a
    selector written as `[data-lmode="${m}"]` keeps its attribute NAME
    while only its value is computed.

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


def class_tokens(selector: str) -> list[str]:
    """Returns every class token in one selector, in reading order.

    Mirrors `classify-rule-anchors.py` deliberately: the two readers must
    agree or one of them is wrong. A token is a `.` followed by name
    characters, outside any `[...]` block — an attribute block's contents
    are values, not selectors. EVERY token is returned, not only the
    strongest anchor's: `#view .swipe` yields `.swipe` even though the
    selector is id-anchored, because that token dies with the stylesheet
    exactly like a class-anchored one.

    Args:
        selector: One selector string, its interpolations already
            stripped.

    Returns:
        The `.name` tokens found, each with its leading dot, or an empty
        list.
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


def selection_calls(path: Path, strip: bool = True) -> list[tuple[int, str, str]]:
    """Extracts every literal-argument selection call in one harness file.

    Args:
        path: A Python file under `HARNESS`.
        strip: True returns a backtick argument with its `${...}` spans
            removed — the anchor arm's reading, where the literal text
            that remains decides. False returns the literal untouched,
            which the part arm needs: a computed value is skipped whole,
            never half-read from the literal halves a strip leaves.

    Returns:
        `(line, method, selector)` tuples, in file order, one per call
        whose first argument is a string literal. A call given a variable
        or an expression is not named here and is not returned.
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
        if strip and text[pos] == "`":
            content = strip_interpolations(content)
        line = text.count("\n", 0, match.start()) + 1
        found.append((line, match.group(1), content))
    return found


def state_assertions(path: Path) -> list[tuple[int, str]]:
    """Extracts every quoted `classList.contains` assertion in one file.

    Args:
        path: A Python file under `HARNESS`.

    Returns:
        `(line, class_name)` tuples, in file order.
    """
    text = path.read_text(encoding="utf-8")
    found: list[tuple[int, str]] = []
    for match in CONTAINS.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        found.append((line, match.group(2)))
    return found


def harness_files() -> list[Path]:
    """Returns the anchor arm's corpus, in a fixed order.

    Returns:
        Every `*.py` file directly under `frontend/maquette/harness`,
        sorted — the same corpus the classifier reads.
    """
    return sorted(p for p in HARNESS.glob("*.py") if p.is_file())


def entry_identity(entry: dict[str, object]) -> tuple[str, str, str, str]:
    """Returns the line-free identity of one baseline entry.

    An occurrence's identity is what it selects, not where it sits:
    `(kind, file, selector, token)` for a selection entry. For an
    assertion the class name fills both slots — the asserted class is the
    assertion's only selector. The `line` field is deliberately absent:
    it is a DISPLAY field, refreshed freely on every write, and a pure
    line shift must not make every entry look new. Multiplicity is the
    callers' business: this tuple is what a Counter counts.

    Args:
        entry: One entry of the classifier's `--baseline` list.

    Returns:
        `(kind, file, selector, token)` — selector and token both set to
        the class name for an assertion entry.

    Raises:
        ValueError: The entry's kind is unknown, or a field is missing or
            of the wrong type.
    """
    kind = entry.get("kind")
    if kind not in ("selection", "assertion"):
        raise ValueError(f"unknown kind {kind!r}")
    name = entry.get("token") if kind == "selection" else entry.get("class")
    selector = entry.get("selector") if kind == "selection" else name
    if not isinstance(entry.get("file"), str) \
            or not isinstance(entry.get("line"), int) \
            or not isinstance(selector, str) \
            or not isinstance(name, str):
        raise ValueError(f"malformed entry {entry!r}")
    return (kind, entry["file"], selector, name)


def load_baseline() -> Counter[tuple[str, str, str, str]]:
    """Loads the burn-down baseline as a multiset of identities.

    A missing file is an EMPTY baseline: the last phase of the lot
    deletes it once every entry is burned, and the arm's floor becomes a
    hard zero.

    Returns:
        The identity → occurrence-count mapping, or an empty Counter when
        the file does not exist.

    Raises:
        ValueError: An entry is malformed.
    """
    if not BASELINE.is_file():
        return Counter()
    entries = json.loads(BASELINE.read_text(encoding="utf-8"))
    return Counter(entry_identity(entry) for entry in entries)


def collect_anchor_findings(
) -> list[tuple[tuple[str, str, str, str], str, str]]:
    """Collects every finding the anchor arm exists to refuse.

    Returns:
        `(identity, subject, where)` tuples, in file order — the
        line-free identity `(kind, file, selector, token)` (the class
        name fills both slots for an assertion), the full selector for a
        selection and the class name for an assertion, and the `file:line`
        it was found at for display.
    """
    findings: list[tuple[tuple[str, str, str, str], str, str]] = []
    for path in harness_files():
        rel = str(path.relative_to(ROOT))
        for line, _, selector in selection_calls(path):
            for token in class_tokens(selector):
                identity = ("selection", rel, selector, token)
                findings.append((identity, selector, f"{rel}:{line}"))
        for line, name in state_assertions(path):
            if name in STATE_CLASSES:
                identity = ("assertion", rel, name, name)
                findings.append((identity, name, f"{rel}:{line}"))
    return findings


def check_anchor_debt() -> int:
    """Arm 2: refuses every finding the burn-down baseline does not own.

    Each finding's identity is looked up in the baseline as a MULTISET —
    the same identity twice is two entries, and a third occurrence is a
    violation exactly like a new one. Owned findings are tolerated and
    counted, unowned ones are violations naming file, line, selector and
    token. A `classList.contains` name that is neither a migrated state
    nor a listed genre is warned about — exactly as the classifier warns
    — because it is measured by nothing.

    Returns:
        1 when any finding is not owned by the baseline, 0 otherwise.
    """
    files = harness_files()
    if not files:
        print(f"check-markup-contracts: no Python files under {HARNESS} — "
              "the scope is empty, so « no violation » would mean nothing",
              file=sys.stderr)
        return 1
    try:
        baseline = load_baseline()
    except (OSError, ValueError, KeyError, TypeError) as err:
        print(f"check-markup-contracts: {BASELINE.relative_to(ROOT)} cannot "
              f"be read as a burn-down baseline: {err}. Regenerate it with "
              "--write-baseline, never by hand (a corrupted baseline cannot "
              "prove the subset, so the regeneration needs "
              "--allow-additions).", file=sys.stderr)
        return 1

    seen: Counter[tuple[str, str, str, str]] = Counter()
    tolerated = {"selection": 0, "assertion": 0}
    exempt = 0
    violations = 0
    for identity, subject, where in collect_anchor_findings():
        kind = identity[0]
        if seen[identity] < baseline[identity]:
            seen[identity] += 1
            tolerated[kind] += 1
        elif kind == "selection":
            violations += 1
            print(f"  {where}: selector {subject!r} carries the class token "
                  f"{identity[3]!r}, and the baseline owns no such "
                  "occurrence. A class token in a rule selection dies the "
                  "day the class is removed. Migrate the occurrence — or if "
                  "a migration genuinely removed it, regenerate the baseline "
                  "with --write-baseline; the regeneration refuses to add "
                  "anything.", file=sys.stderr)
        else:
            violations += 1
            print(f"  {where}: classList.contains({identity[3]!r}) asserts a "
                  "migrated state, and the baseline owns no such occurrence. "
                  "Migrate the assertion — or if a migration genuinely "
                  "removed it, regenerate the baseline with --write-baseline; "
                  "the regeneration refuses to add anything.",
                  file=sys.stderr)
    for path in files:
        for line, name in state_assertions(path):
            if name in GENRE_CLASSES:
                exempt += 1
            elif name not in STATE_CLASSES:
                print(f"  {path.relative_to(ROOT)}:{line}: "
                      f"classList.contains({name!r}) is neither a migrated "
                      "state nor a listed genre — refused by nothing, "
                      "counted by nothing", file=sys.stderr)

    if violations:
        print(f"\ncheck-markup-contracts: {violations} anchor occurrence(s) "
              "the baseline does not own. The burn-down is a ratchet: "
              "phases remove entries, nothing adds them — a baseline that "
              "swallowed a new violation would protect the debt this arm "
              "exists to burn.", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {sum(tolerated.values())} anchor "
          f"occurrence(s) tolerated — {tolerated['selection']} selection "
          f"token(s) and {tolerated['assertion']} state assertion(s), every "
          f"one owned by {BASELINE.relative_to(ROOT)}. {exempt} genre "
          "assertion(s) exempt: permanent, each reason in "
          "scripts/classify-rule-anchors.py --exceptions.")
    return 0


def describe_entry(entry: dict[str, object]) -> str:
    """Formats one baseline entry for a human, without its display line.

    Args:
        entry: One entry of the classifier's `--baseline` list.

    Returns:
        `file: selector … carries the token …` for a selection entry,
        `file: classList.contains(…)` for an assertion entry.
    """
    if entry["kind"] == "selection":
        return (f"  {entry['file']}: selector {entry['selector']!r} carries "
                f"the token {entry['token']!r}")
    return f"  {entry['file']}: classList.contains({entry['class']!r})"


def write_baseline(allow_additions: bool = False) -> int:
    """Regenerates the burn-down baseline from the independent classifier.

    Consumes `python3 scripts/classify-rule-anchors.py --baseline` rather
    than deriving the entries here: a baseline the guard derives alone is
    a classification cross-checked by nothing. The two readers are then
    held against each other — this arm's own extraction must agree with
    the classifier's list on every occurrence identity — and the file is
    written only when they do, so the cross-check is a hard gate and not
    a step someone remembers to run.

    THE RATCHET. Before writing, the fresh entries are held against the
    stored baseline on their line-free identities. Removals pass
    silently: that is the burn-down. Any occurrence the stored baseline
    does not already own REFUSES the write — exit 1, naming each one —
    because a burn-down list does not grow. A pure line shift still
    writes: nothing was added, only display lines moved, which phases 2
    to 6 depend on as they edit harness files in every commit.
    `allow_additions` is the deliberate escape hatch (bootstrap, a
    re-classification, a corrupted baseline): it writes regardless and
    prints loudly what it added. Nothing in phases 2 to 6 of maquette-l02
    may use it.

    Args:
        allow_additions: True when the operator deliberately lets the
            baseline grow. Banned for phases 2 to 6 of maquette-l02.

    Returns:
        1 when the classifier fails, its output is not a baseline, the
        two readers disagree, or the write would add occurrences and
        `allow_additions` is False; 0 when the file was written.
    """
    run = subprocess.run([sys.executable, str(CLASSIFIER), "--baseline"],
                         capture_output=True, text=True)
    if run.returncode != 0:
        print(f"check-markup-contracts: {CLASSIFIER.name} --baseline "
              f"failed:\n{run.stderr}", file=sys.stderr)
        return 1
    try:
        entries = json.loads(run.stdout)
        if not isinstance(entries, list) or not entries:
            raise ValueError("expected a non-empty list of entries")
        by_classifier = Counter(entry_identity(entry) for entry in entries)
    except (ValueError, KeyError, TypeError) as err:
        print(f"check-markup-contracts: {CLASSIFIER.name} --baseline printed "
              f"something that is not a baseline ({err}) — "
              f"{BASELINE.name} was not written.", file=sys.stderr)
        return 1

    by_guard = Counter(identity for identity, _, _ in collect_anchor_findings())
    if by_classifier != by_guard:
        print("check-markup-contracts: the two readers disagree — "
              f"{CLASSIFIER.name} --baseline holds "
              f"{sum(by_classifier.values())} occurrence(s) and this arm's "
              f"own extraction finds {sum(by_guard.values())}.",
              file=sys.stderr)
        for key in list(by_classifier - by_guard)[:10]:
            print(f"  classifier only: {key}", file=sys.stderr)
        for key in list(by_guard - by_classifier)[:10]:
            print(f"  guard only: {key}", file=sys.stderr)
        return 1

    try:
        stored = load_baseline()
    except (OSError, ValueError, KeyError, TypeError) as err:
        if not allow_additions:
            print(f"check-markup-contracts: the stored baseline cannot be "
                  f"read ({err}), so nothing can prove the fresh entries are "
                  f"a subset of it. {BASELINE.name} was NOT written. Rerun "
                  "with --write-baseline --allow-additions only when you can "
                  "account for what it adds.", file=sys.stderr)
            return 1
        # Treated as empty: every occurrence is an addition, and the loud
        # listing below names them all.
        stored = Counter()

    added = by_classifier - stored
    removed = sum((stored - by_classifier).values())
    total = sum(by_classifier.values())

    if added and not allow_additions:
        sample = {entry_identity(entry): entry for entry in entries}
        for identity, count in sorted(added.items()):
            suffix = f"  (×{count})" if count > 1 else ""
            print(describe_entry(sample[identity]) + suffix,
                  file=sys.stderr)
        print(f"\ncheck-markup-contracts: refusing to write the baseline — "
              f"{sum(added.values())} occurrence(s) would be ADDED, and a "
              "burn-down list does not grow. Removals "
              f"({removed}, landing at {total} total) are the burn-down; "
              "additions are new debt, and a regeneration that absorbs them "
              "is a ratchet turning the wrong way. Migrate the occurrences "
              "above, or if this is a deliberate bootstrap / "
              "re-classification / corruption repair, rerun with "
              "--write-baseline --allow-additions — nothing in phases 2 to 6 "
              f"of maquette-l02 may use it. {BASELINE.name} was NOT written.",
              file=sys.stderr)
        return 1

    BASELINE.write_text(json.dumps(entries, indent=2) + "\n",
                        encoding="utf-8")
    selections = sum(count for (kind, *_), count in by_classifier.items()
                     if kind == "selection")
    assertions = total - selections
    if added:
        sample = {entry_identity(entry): entry for entry in entries}
        print("check-markup-contracts: --allow-additions granted — the "
              f"following {sum(added.values())} occurrence(s) were ADDED to "
              "a burn-down baseline:", file=sys.stderr)
        for identity, count in sorted(added.items()):
            suffix = f"  (×{count})" if count > 1 else ""
            print(describe_entry(sample[identity]) + suffix,
                  file=sys.stderr)
    print(f"check-markup-contracts: wrote "
          f"{BASELINE.relative_to(ROOT)} — {total} "
          f"occurrence(s): {selections} selection token(s) and {assertions} "
          f"state assertion(s), with {removed} removed since the stored "
          "baseline. The classifier's list and this arm's own extraction "
          "agree on every entry.")
    return 0


def part_selections(path: Path) -> list[tuple[int, str]]:
    """Extracts every literal `data-part` value one harness file selects.

    Reads the RAW selector — `selection_calls(..., strip=False)` — because
    a value built from a template interpolation is computed at run time:
    it names no literal to compare against the emissions, and the literal
    halves a strip leaves are not the value the rule selects.

    Args:
        path: A Python file under `HARNESS`.

    Returns:
        `(line, value)` tuples, in file order. A value carrying `${` is
        skipped, not half-read; a presence selection `[data-part]` names
        no value and is not returned.
    """
    found: list[tuple[int, str]] = []
    for line, _, selector in selection_calls(path, strip=False):
        for match in PART_SELECTED.finditer(selector):
            value = next(g for g in match.groups() if g is not None)
            if "${" in value:
                continue
            found.append((line, value))
    return found


def emission_files() -> list[Path]:
    """Returns the part arm's emission corpus, in a fixed order.

    Returns:
        The shell first, then every `.js`, `.ts` and `.tsx` source under
        `design/src` — the three emission sites: the shell's markup, the
        engine's, the components'.
    """
    files = [p for p in sorted(SOURCES.rglob("*"))
             if p.is_file() and p.suffix in {".js", ".ts", ".tsx"}]
    return [SHELL, *files]


def emitted_part_values(path: Path) -> set[str]:
    """Returns every literal `data-part` value one emission site emits.

    Comments are stripped before reading: a value a COMMENT carries is
    emitted by nothing, and accepting it would silence the arm over a
    rule that selects nothing. The JS-style stripper covers the sources;
    the shell's HTML comments get their own.

    Args:
        path: One emission site — `index.html` or a source file.

    Returns:
        The literal values emitted as `data-part="value"`. A computed
        value is not a literal and is not returned.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".html":
        text = HTML_COMMENT.sub(" ", text)
    else:
        text = COMMENT.sub(" ", text)
    return {match.group("value").strip() for match in EMITTED.finditer(text)
            if match.group("attr") == "part"}


def check_part_values() -> int:
    """Arm 3: refuses a selected `data-part` value no source emits.

    The direction is ONE-WAY: every value a harness rule selects must be
    emitted somewhere — a selection no emission satisfies is a rule
    selecting nothing, the three-ends contract caught from the markup
    end. An emitted value no rule selects is fine: not every part needs a
    rule.

    VACUOUS TODAY, BY DESIGN: no `data-part` exists yet — phase 2 writes
    the first ones — so this arm examines zero selections and a green
    exit proves nothing about it. The count it prints is the point: a
    number nobody prints is a number nobody can notice is zero. It is
    proven by probe-mutation instead, and becomes load-bearing the day
    phase 2 lands.

    Returns:
        1 when a selected value is emitted nowhere, 0 otherwise.
    """
    files = harness_files()
    if not files:
        print(f"check-markup-contracts: no Python files under {HARNESS} — "
              "the selection side is empty, so « no violation » would mean "
              "nothing", file=sys.stderr)
        return 1
    if not SHELL.is_file():
        print(f"check-markup-contracts: {SHELL.relative_to(ROOT)} is missing "
              "— the emission side is empty, so « no violation » would mean "
              "nothing", file=sys.stderr)
        return 1
    emission_paths = emission_files()
    if len(emission_paths) < 2:
        print(f"check-markup-contracts: no sources under {SOURCES} — "
              "the emission side is empty, so « no violation » would mean "
              "nothing", file=sys.stderr)
        return 1

    emitted: set[str] = set()
    for path in emission_paths:
        emitted |= emitted_part_values(path)

    violations = 0
    checked = 0
    for path in files:
        rel = str(path.relative_to(ROOT))
        for line, value in part_selections(path):
            checked += 1
            if value not in emitted:
                violations += 1
                print(f"  {rel}:{line}: the rule selects "
                      f"[data-part={value!r}], and no source emits it. A "
                      "value selected and emitted nowhere is a rule "
                      "selecting nothing — the three-ends contract, caught "
                      "from the markup end. Emit the value, or stop "
                      "selecting it.", file=sys.stderr)

    if violations:
        print(f"\ncheck-markup-contracts: {violations} data-part selection(s) "
              "no source emits. The value a rule selects and the markup "
              "that emits it are ONE contract — they move together or the "
              "rule measures nothing.", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {checked} data-part selection(s) checked "
          f"against {len(emitted)} emitted value(s) from "
          f"{len(emission_paths)} emission site(s) — every selected value "
          "is emitted. Emitted-but-unselected is fine: not every part "
          "needs a rule.")
    return 0


def braced_expression(text: str, open_idx: int) -> tuple[str, int] | None:
    """Returns the braced expression opening at `open_idx` and the index
    past its closing brace.

    Args:
        text: The file text being read.
        open_idx: Index of the opening `{`.

    Returns:
        The expression between the braces and the index just past the
        closing `}`, or None when the braces never balance.
    """
    depth = 0
    for i in range(open_idx, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i], i + 1
    return None


def state_attribute_writes(path: Path) -> list[tuple[int, str, str]]:
    """Extracts every braced boolean-state write in one component file.

    Comments are stripped before reading — a write a COMMENT describes
    was rejected, exactly like ARM 1's `prete`. The corpus is the
    components: the `.ts` / `.tsx` files under `design/src`.

    Args:
        path: A component file.

    Returns:
        `(line, attribute, expression)` tuples, in file order — the
        expression as written between the braces. A brace pair that never
        balances is skipped, not guessed at.
    """
    text = COMMENT.sub(" ", path.read_text(encoding="utf-8"))
    found: list[tuple[int, str, str]] = []
    for match in STATE_WRITTEN.finditer(text):
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

    VACUOUS TODAY, BY DESIGN: no boolean state attribute exists yet —
    phase 2 writes the first ones — so this arm examines zero attributes
    and a green exit proves nothing about it. The count it prints is the
    point. It is proven by probe-mutation instead.

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

    violations = 0
    checked = 0
    for path in files:
        rel = str(path.relative_to(ROOT))
        for line, attr, expression in state_attribute_writes(path):
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

    print(f"check-markup-contracts: {checked} state attribute(s) checked, "
          "every one written with a spelling that omits the attribute when "
          "its state is false.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Runs all four arms over their corpora, or regenerates the baseline.

    Args:
        argv: The arguments to read. `None` reads the process's own, which is
            what the entry point below passes; a caller IN-PROCESS — a test —
            passes its own list, because `sys.argv` under a test runner
            belongs to the runner.

    Returns:
        1 when anything was found or the arguments are unknown, 0
        otherwise.
    """
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        if argv == ["--write-baseline"]:
            return write_baseline()
        if argv == ["--write-baseline", "--allow-additions"]:
            return write_baseline(allow_additions=True)
        print("check-markup-contracts: unknown arguments — run with no "
              "argument to check; --write-baseline to regenerate "
              f"{BASELINE.relative_to(ROOT)}, which refuses to ADD anything "
              "to the burn-down; or --write-baseline --allow-additions as "
              "the deliberate escape hatch — nothing in phases 2 to 6 of "
              "maquette-l02 may use it.", file=sys.stderr)
        return 1
    rc = 0
    if check_forwarded_values():
        rc = 1
    if check_anchor_debt():
        rc = 1
    if check_part_values():
        rc = 1
    if check_state_attributes():
        rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

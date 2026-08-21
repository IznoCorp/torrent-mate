#!/usr/bin/env python3
"""ARM 2 of the markup guard — a rule selection anchored on a style class.

SPLIT OUT OF `check-markup-contracts.py`, which this arm took from 149 lines to
1 275 — past the 1 000-line hard ceiling `check-module-size.py` enforces over
`scripts/` as well as the package. The entry point keeps the four arms'
orchestration and stays the gate's ONE command; what this arm reads, refuses
and writes is all here: both extraction passes, the burn-down baseline, the
ratchet, and the cross-check against the independent classifier.

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

  1. A class TOKEN in a selection, read by TWO passes — a guard that
     reads only the call pass would reproduce the instrument's second
     blind spot, where a selector held in a variable or a table dies at
     L07 with no measurement at all.

     a. The CALL pass: the string argument of every `querySelector`,
        `querySelectorAll`, `locator` and `matches` call, read the way
        `classify-rule-anchors.py --tokens` reads it: `${...}`
        interpolations and every `[...]` block are stripped, then EVERY
        `.token` that remains is a finding — NOT the strongest anchor.
        `#view .swipe` is id-anchored by precedence and still dies the
        day the `.swipe` class is removed; a guard that refused only
        pure class anchors would reproduce the 54 % under-measurement
        D4's own method was found to make.

     b. The HELD pass: every OTHER selector-shaped string literal —
        `screen_port = ".screen.open .port"`, a row of a table, a
        helper's argument, a comparison. THE FALSE-POSITIVE RULE, AND
        IT IS A RULE, NOT A LIST: a candidate string is a selector only
        if EVERY class token it carries is EMITTED by at least one of
        the three design sites — `index.html`, `src/engine/legacy.js`
        and the sources under `design/src` — as a class= / className=
        token, OR the string carries selector structure: a combinator,
        an attribute block, a comma list. `.json5` fails both — nothing
        emits a class named json5, and the string has no structure —
        while `.tile[data-panel]` passes on structure and `.sact`
        passes on emission. A shape test runs first: the string starts
        with `.`, `#` or `[`, holds only selector-alphabet characters,
        and is not a method call (`.render(`). Comments and docstrings
        are read by nothing at runtime, so they are read by nothing
        here; a candidate carrying no class token owes the burn-down
        nothing and is not recorded. A held occurrence is a finding
        exactly like a call occurrence — the baseline entry differs
        only in its `held: true` field, never in its identity.

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
what it selects and where it is: the multiset of (kind, file, token),
with the class name filling the token slot for an assertion. The
`selector` and `line` stored in each entry are DISPLAY fields, refreshed
freely on every write and never compared: phase 2 rewrites the PREFIX of
dozens of selectors (`.screen.open .fback` becomes
`[data-part="screen"][data-open] .fback`) without moving a single token,
and an identity that included the selector string would see each
rewritten token as one removed and one added — a regeneration that
refuses itself on its own committed baseline. A finding whose identity
the baseline owns is tolerated and counted — multiplicity included, the
same identity twice is two entries and must stay two; one it does not
exits 1 naming file, line, selector and token. Every later phase REMOVES
entries — a baseline that swallowed a NEW violation would ratchet the
wrong way, and this arm's whole reason to exist is to refuse that.

The baseline is GENERATED, never typed. `--write-baseline` consumes
`python3 scripts/classify-rule-anchors.py --baseline` — the independent
second reader, so the classification is cross-checked by something other
than the guard that enforces it — then holds the two readers against each
other and writes the file only when they agree on every occurrence.

AND IT REFUSES TO GROW. Before writing, the fresh entries are held
against the stored baseline on their line-free, selector-free
identities: any occurrence the stored baseline does not already own
REFUSES the write — exit 1, naming each one — because a burn-down list
does not grow. Removals pass silently; that is the burn-down. A pure
display shift still writes (nothing added, only lines and selector
spellings refreshed), which phases 2 to 6 depend on: they rewrite
selector prefixes and edit harness files in every commit. The
deliberate escape hatch is
`--write-baseline --allow-additions` — bootstrap, a re-classification, a
corrupted baseline — which writes regardless and prints loudly what it
added. Nothing in phases 2 to 6 of maquette-l02 may use it.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The shared text readers — see that module's header.
from markup_text import (  # noqa: E402
    COMMENT, HARNESS, HTML_COMMENT, ROOT, SHELL, SOURCES, braced_expression,
    comment_masked, read_literal, strip_interpolations,
)

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

# ---- ARM 2 held pass -----------------------------------------------------

# The characters a selector can hold. A string carrying anything else —
# a Python f-string's braces, a `${...}` span, prose — is not
# selector-shaped and is read by neither pass. Mirrored deliberately
# from the classifier: the two readers must agree or one is wrong.
SELECTOR_ALPHABET = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789.#[]=\"'`~+>*,:()\\-_^$|/ ")

# A class token followed by a call parenthesis names a method, not a
# class — CSS class tokens take no arguments. `:has-text(` is fine: its
# parenthesis hangs off a pseudo-class, not off a class token.
METHOD_CALL = re.compile(r"^\.[-\w]+\s*\(")

# A quoted literal whose content starts with a selector character and
# holds, up to the closing quote, selector text: plain characters and
# attribute blocks — an attribute block may carry the delimiter
# (`'[data-x="y"]'` inside a single-quoted string), which is exactly why
# the pass cannot be a simple quote-pair scan. Stateless on purpose: a
# French apostrophe or a nested backtick that would desync a quote-pair
# walker simply fails to match here, and the literal after it is read on
# its own.
HELD_RE = re.compile(
    r"""(["'`])(?P<sel>[.#\[](?:(?!\1)[^\[\n])*(?:\[[^\[\]\n]*\]"""
    r"""(?:(?!\1)[^\[\n])*)*)\1""")

# `class=` / `className=` — every attribute spelling, whichever side of
# an assignment or a JSX tag it hangs on. `\b` keeps `subclass =` out.
CLASS_ATTR = re.compile(r"\bclass(?:Name)?\s*=\s*")


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


def call_argument_starts(text: str) -> set[int]:
    """Returns the opening-quote offset of every call argument.

    A selector that IS a selection call's argument belongs to the call
    pass; the held pass reads every OTHER literal.

    Args:
        text: The file text being read.

    Returns:
        The set of literal-start offsets the call pass owns.
    """
    starts: set[int] = set()
    for match in CALL.finditer(text):
        pos = match.end()
        while pos < len(text) and text[pos] in " \t\n":
            pos += 1
        if pos < len(text) and text[pos] in ("'", '"', "`"):
            starts.add(pos)
    return starts


def has_structure(content: str) -> bool:
    """True when a candidate carries selector structure.

    Structure is what lets a string qualify even when no design site
    emits its tokens: an attribute block, a comma list, or a combinator
    (`>`, `+`, `~`, or a space between two non-space parts). A single
    bare class name has none — which is what the emission half of the
    rule exists for.

    Args:
        content: One candidate string.

    Returns:
        True when the candidate carries at least one structural marker.
    """
    if "[" in content or "," in content:
        return True
    if ">" in content or "+" in content or "~" in content:
        return True
    return re.search(r"\S\s+\S", content) is not None


def emission_tokens() -> set[str]:
    """Returns every class token the three design sites emit.

    An emission is a whitespace-split token of a class= / className=
    value, read in each of the value's spellings: the plain quoted
    attribute, the JS assignment (`bar.className = "selbar"`), a
    backtick template (interpolations stripped, so the literal part
    decides), and a braced expression (its string and template literals
    are the class names). A value cut short by a `${...}` interpolation
    contributes its literal part, and the span's own string literals
    contribute theirs — `class="card${x ? " fresh" : ""}"` emits both
    card and fresh. Comments are stripped first: a token a COMMENT
    carries is emitted by nothing.

    Returns:
        The set of emitted class names — empty only when the emission
        corpus is unreadable, which the callers refuse loudly.
    """
    files = [p for p in sorted(SOURCES.rglob("*"))
             if p.is_file() and p.suffix in {".js", ".ts", ".tsx"}]
    emitted: set[str] = set()
    for path in [SHELL, *files]:
        text = path.read_text(encoding="utf-8")
        text = (HTML_COMMENT.sub(" ", text) if path.suffix == ".html"
                else COMMENT.sub(" ", text))
        for match in CLASS_ATTR.finditer(text):
            pos = match.end()
            if pos >= len(text):
                continue
            ch = text[pos]
            if ch in ("'", '"'):
                literal = read_literal(text, pos)
                if literal is None:
                    continue
                value, _ = literal
                split_at = value.find("${")
                emitted |= set(value[:split_at if split_at != -1
                                     else len(value)].split())
                if split_at == -1:
                    continue
                # the span of a template class attribute may itself hold
                # the computed class names, as string literals
                braced = braced_expression(text, pos + 1 + split_at + 1)
                if braced is None:
                    continue
                expr, _ = braced
                for piece in re.findall(r"""["']([^"']*)["']""", expr):
                    emitted |= set(piece.split())
            elif ch == "`":
                literal = read_literal(text, pos)
                if literal is None:
                    continue
                value, _ = literal
                emitted |= set(strip_interpolations(value).split())
            elif ch == "{":
                braced = braced_expression(text, pos)
                if braced is None:
                    continue
                expr, _ = braced
                for piece in re.findall(r"""["']([^"']*)["']""", expr):
                    emitted |= set(piece.split())
                for literal in re.findall(r"`([^`]*)`", expr):
                    emitted |= set(strip_interpolations(literal).split())
    return emitted


def held_occurrences(path: Path, emitted: set[str]) -> list[tuple[int, str]]:
    """Returns every held selector in one harness file, in file order.

    A held selector is a selector-shaped string literal OUTSIDE any
    selection call's argument position — a selector held in a variable,
    a table, a helper's argument, a comparison.

    Args:
        path: A Python file under `HARNESS`.
        emitted: The class tokens the three design sites emit — the
            false-positive rule's emission half is decided by this set.

    Returns:
        `(line, content)` pairs, one per candidate that carries at least
        one class token and passes the false-positive rule.
    """
    text = path.read_text(encoding="utf-8")
    masked = comment_masked(text)
    call_args = call_argument_starts(text)
    found: list[tuple[int, str]] = []
    for match in HELD_RE.finditer(masked):
        if match.start() in call_args:
            continue
        content = match.group("sel")
        if any(ch not in SELECTOR_ALPHABET for ch in content):
            continue
        if METHOD_CALL.match(content):
            continue
        tokens = class_tokens(content)
        if not tokens:
            continue
        if not (has_structure(content)
                or all(token[1:] in emitted for token in tokens)):
            continue
        line = text.count("\n", 0, match.start()) + 1
        found.append((line, content))
    return found


def harness_files() -> list[Path]:
    """Returns the anchor arm's corpus, in a fixed order.

    Returns:
        Every `*.py` file directly under `frontend/maquette/harness`,
        sorted — the same corpus the classifier reads.
    """
    return sorted(p for p in HARNESS.glob("*.py") if p.is_file())


def entry_identity(entry: dict[str, object]) -> tuple[str, str, str]:
    """Returns the line- and selector-free identity of one baseline entry.

    An occurrence's identity is WHAT it selects and WHERE it is:
    `(kind, file, token)` for a selection entry — the class name filling
    the token slot for an assertion. The `selector` and `line` fields are
    deliberately absent: they are DISPLAY fields, refreshed freely on
    every write, and a phase that rewrites a selector's prefix
    (`.screen.open .fback` → `[data-part="screen"][data-open] .fback`)
    must not make the occurrence it carries look new. Multiplicity is
    the callers' business: this tuple is what a Counter counts.

    Args:
        entry: One entry of the classifier's `--baseline` list.

    Returns:
        `(kind, file, token)` — the token slot filled by the class name
        for an assertion entry.

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
            or not isinstance(name, str) \
            or not isinstance(entry.get("held", False), bool):
        raise ValueError(f"malformed entry {entry!r}")
    return (kind, entry["file"], name)


def load_baseline() -> Counter[tuple[str, str, str]]:
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
) -> list[tuple[tuple[str, str, str], str, str, bool]]:
    """Collects every finding the anchor arm exists to refuse.

    Both passes feed it — the call pass reads the selection calls, the
    held pass reads the selector-shaped strings outside them, and each
    occurrence is one finding. The identity is the same key for both: a
    held occurrence of `.tile` and a call occurrence of `.tile` in the
    same file are two entries with one identity; the `held` flag is the
    annotation that tells them apart.

    Returns:
        `(identity, subject, where, held)` tuples, in file order — the
        line- and selector-free identity `(kind, file, token)` (the class
        name fills the token slot for an assertion), the full selector
        for a selection and the class name for an assertion — the
        DISPLAY subject, carried alongside the identity but never part
        of it — the `file:line` it was found at for display, and whether
        the held pass found it.
    """
    findings: list[tuple[tuple[str, str, str], str, str, bool]] = []
    emitted = emission_tokens()
    for path in harness_files():
        rel = str(path.relative_to(ROOT))
        for line, _, selector in selection_calls(path):
            for token in class_tokens(selector):
                identity = ("selection", rel, token)
                findings.append((identity, selector, f"{rel}:{line}", False))
        for line, content in held_occurrences(path, emitted):
            for token in class_tokens(content):
                identity = ("selection", rel, token)
                findings.append((identity, content, f"{rel}:{line}", True))
        for line, name in state_assertions(path):
            if name in STATE_CLASSES:
                identity = ("assertion", rel, name)
                findings.append((identity, name, f"{rel}:{line}", False))
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
    emitted = emission_tokens()
    if not emitted:
        print("check-markup-contracts: no class= / className= emission "
              "found in the design sources — the held pass cannot tell a "
              "selector from a word, so « no held selector » would mean "
              "nothing", file=sys.stderr)
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

    seen: Counter[tuple[str, str, str]] = Counter()
    # "held" is a SUBSET of "selection", not a third population: a held
    # occurrence is counted once under its kind and once again here so the
    # summary can say how many of the selection tokens sit outside a call.
    # The printed total must therefore never sum the three buckets.
    tolerated = {"selection": 0, "held": 0, "assertion": 0}
    exempt = 0
    violations = 0
    for identity, subject, where, held in collect_anchor_findings():
        kind = identity[0]
        if seen[identity] < baseline[identity]:
            seen[identity] += 1
            tolerated[kind] += 1
            if kind == "selection" and held:
                tolerated["held"] += 1
        elif kind == "selection" and held:
            violations += 1
            print(f"  {where}: the string {subject!r} held outside any "
                  f"selection call carries the class token {identity[2]!r}, "
                  "and the baseline owns no such occurrence. A selector "
                  "held in a variable or a table dies the day the class is "
                  "removed exactly like one written in a call. Migrate the "
                  "occurrence — or if a migration genuinely removed it, "
                  "regenerate the baseline with --write-baseline; the "
                  "regeneration refuses to add anything.", file=sys.stderr)
        elif kind == "selection":
            violations += 1
            print(f"  {where}: selector {subject!r} carries the class token "
                  f"{identity[2]!r}, and the baseline owns no such "
                  "occurrence. A class token in a rule selection dies the "
                  "day the class is removed. Migrate the occurrence — or if "
                  "a migration genuinely removed it, regenerate the baseline "
                  "with --write-baseline; the regeneration refuses to add "
                  "anything.", file=sys.stderr)
        else:
            violations += 1
            print(f"  {where}: classList.contains({identity[2]!r}) asserts a "
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

    total = tolerated["selection"] + tolerated["assertion"]
    print(f"check-markup-contracts: {total} anchor "
          f"occurrence(s) tolerated — {tolerated['selection']} selection "
          f"token(s), {tolerated['held']} of them held outside any "
          f"selection call, and {tolerated['assertion']} state "
          f"assertion(s), every one owned by "
          f"{BASELINE.relative_to(ROOT)}. {exempt} genre assertion(s) "
          "exempt: permanent, each reason in "
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
        if entry.get("held"):
            return (f"  {entry['file']}: the string {entry['selector']!r} "
                    f"held outside any selection call carries the token "
                    f"{entry['token']!r}")
        return (f"  {entry['file']}: selector {entry['selector']!r} carries "
                f"the token {entry['token']!r}")
    return f"  {entry['file']}: classList.contains({entry['class']!r})"


def write_baseline(allow_additions: bool = False) -> int:
    """Regenerates the burn-down baseline from the independent classifier.

    Consumes `python3 scripts/classify-rule-anchors.py --baseline` rather
    than deriving the entries here: a baseline the guard derives alone is
    a classification cross-checked by nothing. The two readers are then
    held against each other — this arm's own extraction must agree with
    the classifier's list on every occurrence identity AND on every held
    flag — and the file is written only when they do, so the cross-check
    is a hard gate and not a step someone remembers to run.

    THE RATCHET. Before writing, the fresh entries are held against the
    stored baseline on their line- and selector-free identities.
    Removals pass silently: that is the burn-down. Any occurrence the
    stored baseline does not already own REFUSES the write — exit 1,
    naming each one — because a burn-down list does not grow. A pure
    display shift still writes: nothing was added, only lines and
    selector spellings refreshed, which phases 2 to 6 depend on as they
    rewrite selector prefixes and edit harness files in every commit.
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
    emitted = emission_tokens()
    if not emitted:
        print("check-markup-contracts: no class= / className= emission "
              "found in the design sources — the held pass cannot tell a "
              "selector from a word, so a regeneration would silently "
              f"burn every held entry. {BASELINE.name} was NOT written.",
              file=sys.stderr)
        return 1
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

    findings = collect_anchor_findings()
    by_guard = Counter(identity for identity, _, _, _ in findings)
    # The two readers must agree on the held flags too: an occurrence one
    # side reads as held and the other as a call is a disagreement, even
    # though the identity is the same key for both.
    by_classifier_held = Counter(
        (entry_identity(entry), bool(entry.get("held"))) for entry in entries)
    by_guard_held = Counter((identity, held)
                            for identity, _, _, held in findings)
    if by_classifier != by_guard or by_classifier_held != by_guard_held:
        print("check-markup-contracts: the two readers disagree — "
              f"{CLASSIFIER.name} --baseline holds "
              f"{sum(by_classifier.values())} occurrence(s) and this arm's "
              f"own extraction finds {sum(by_guard.values())}.",
              file=sys.stderr)
        for key in list(by_classifier - by_guard)[:10]:
            print(f"  classifier only: {key}", file=sys.stderr)
        for key in list(by_guard - by_classifier)[:10]:
            print(f"  guard only: {key}", file=sys.stderr)
        for key in list(by_classifier_held - by_guard_held)[:10]:
            print(f"  held flag differs: {key}", file=sys.stderr)
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

#!/usr/bin/env python3
"""Refuses two defect classes — two arms, one corpus each. Read the arm
whose scope you are touching; each arm names the corpus it reads.

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
and only the occurrence has a single owner. A finding whose
(file, line, token) occurrence the baseline owns is tolerated and
counted; one it does not exits 1 naming file, line, selector and token.
Every later phase REMOVES entries — a baseline that swallowed a NEW
violation would ratchet the wrong way, and this arm's whole reason to
exist is to refuse that.

The baseline is GENERATED, never typed. `--write-baseline` consumes
`python3 scripts/classify-rule-anchors.py --baseline` — the independent
second reader, so the classification is cross-checked by something other
than the guard that enforces it — then holds the two readers against each
other and writes the file only when they agree on every occurrence.

Usage:
    python3 scripts/check-markup-contracts.py
    python3 scripts/check-markup-contracts.py --write-baseline
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


def selection_calls(path: Path) -> list[tuple[int, str, str]]:
    """Extracts every literal-argument selection call in one harness file.

    Args:
        path: A Python file under `HARNESS`.

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
        if text[pos] == "`":
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


def baseline_key(entry: dict[str, object]) -> tuple[str, str, int, str]:
    """Returns the occurrence key of one baseline entry.

    Args:
        entry: One entry of the classifier's `--baseline` list.

    Returns:
        `(kind, file, line, name)` — the token for a selection entry, the
        class name for an assertion entry.

    Raises:
        ValueError: The entry's kind is unknown, or a field is missing or
            of the wrong type.
    """
    kind = entry.get("kind")
    if kind not in ("selection", "assertion"):
        raise ValueError(f"unknown kind {kind!r}")
    name = entry.get("token") if kind == "selection" else entry.get("class")
    if not isinstance(entry.get("file"), str) \
            or not isinstance(entry.get("line"), int) \
            or not isinstance(name, str):
        raise ValueError(f"malformed entry {entry!r}")
    return (kind, entry["file"], entry["line"], name)


def load_baseline() -> dict[tuple[str, str, int, str], dict[str, object]]:
    """Loads the burn-down baseline, keyed on the token occurrence.

    A missing file is an EMPTY baseline: the last phase of the lot
    deletes it once every entry is burned, and the arm's floor becomes a
    hard zero.

    Returns:
        The `(kind, file, line, name)` → entry mapping, or an empty
        mapping when the file does not exist.
    """
    if not BASELINE.is_file():
        return {}
    entries = json.loads(BASELINE.read_text(encoding="utf-8"))
    baseline: dict[tuple[str, str, int, str], dict[str, object]] = {}
    for entry in entries:
        baseline[baseline_key(entry)] = entry
    return baseline


def collect_anchor_findings(
) -> list[tuple[tuple[str, str, int, str], str, str]]:
    """Collects every finding the anchor arm exists to refuse.

    Returns:
        `(key, subject, where)` tuples, in file order — the occurrence
        key `(kind, file, line, name)`, the full selector for a selection
        and the class name for an assertion, and the `file:line` it was
        found at.
    """
    findings: list[tuple[tuple[str, str, int, str], str, str]] = []
    for path in harness_files():
        rel = str(path.relative_to(ROOT))
        for line, _, selector in selection_calls(path):
            for token in class_tokens(selector):
                key = ("selection", rel, line, token)
                findings.append((key, selector, f"{rel}:{line}"))
        for line, name in state_assertions(path):
            if name in STATE_CLASSES:
                key = ("assertion", rel, line, name)
                findings.append((key, name, f"{rel}:{line}"))
    return findings


def check_anchor_debt() -> int:
    """Arm 2: refuses every finding the burn-down baseline does not own.

    Each finding's occurrence key is looked up in the baseline: owned
    findings are tolerated and counted, unowned ones are violations
    naming file, line, selector and token. A `classList.contains` name
    that is neither a migrated state nor a listed genre is warned about
    — exactly as the classifier warns — because it is measured by
    nothing.

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
              "--write-baseline, never by hand.", file=sys.stderr)
        return 1

    tolerated = {"selection": 0, "assertion": 0}
    exempt = 0
    violations = 0
    for key, subject, where in collect_anchor_findings():
        kind = key[0]
        if key in baseline:
            tolerated[kind] += 1
        elif kind == "selection":
            violations += 1
            print(f"  {where}: selector {subject!r} carries the class token "
                  f"{key[3]!r}, and no baseline entry owns that occurrence. "
                  "A class token in a rule selection dies the day the class "
                  "is removed. If a migration removed this occurrence, "
                  "regenerate the baseline with --write-baseline — never by "
                  "adding an entry by hand.", file=sys.stderr)
        else:
            violations += 1
            print(f"  {where}: classList.contains({key[3]!r}) asserts a "
                  "migrated state, and no baseline entry owns that "
                  "occurrence. If a migration removed this assertion, "
                  "regenerate the baseline with --write-baseline.",
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


def write_baseline() -> int:
    """Regenerates the burn-down baseline from the independent classifier.

    Consumes `python3 scripts/classify-rule-anchors.py --baseline` rather
    than deriving the entries here: a baseline the guard derives alone is
    a classification cross-checked by nothing. The two readers are then
    held against each other — this arm's own extraction must agree with
    the classifier's list on every occurrence key — and the file is
    written only when they do, so the cross-check is a hard gate and not
    a step someone remembers to run.

    Returns:
        1 when the classifier fails, its output is not a baseline, or the
        two readers disagree; 0 when the file was written.
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
        by_classifier = Counter(baseline_key(entry) for entry in entries)
    except (ValueError, KeyError, TypeError) as err:
        print(f"check-markup-contracts: {CLASSIFIER.name} --baseline printed "
              f"something that is not a baseline ({err}) — "
              f"{BASELINE.name} was not written.", file=sys.stderr)
        return 1

    by_guard = Counter(key for key, _, _ in collect_anchor_findings())
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

    BASELINE.write_text(json.dumps(entries, indent=2) + "\n",
                        encoding="utf-8")
    selections = sum(count for (kind, *_), count in by_classifier.items()
                     if kind == "selection")
    assertions = sum(by_classifier.values()) - selections
    print(f"check-markup-contracts: wrote "
          f"{BASELINE.relative_to(ROOT)} — {sum(by_classifier.values())} "
          f"occurrence(s): {selections} selection token(s) and {assertions} "
          "state assertion(s). The classifier's list and this arm's own "
          "extraction agree on every entry.")
    return 0


def main() -> int:
    """Runs both arms over their corpora, or regenerates the baseline.

    Returns:
        1 when anything was found or the arguments are unknown, 0
        otherwise.
    """
    args = sys.argv[1:]
    if args:
        if args == ["--write-baseline"]:
            return write_baseline()
        print("check-markup-contracts: unknown arguments — run with no "
              "argument to check, or --write-baseline to regenerate "
              f"{BASELINE.relative_to(ROOT)}.", file=sys.stderr)
        return 1
    rc = 0
    if check_forwarded_values():
        rc = 1
    if check_anchor_debt():
        rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

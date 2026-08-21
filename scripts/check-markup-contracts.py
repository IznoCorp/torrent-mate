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
The arm lives in `markup_anchors.py`, beside this file, and that file's
header describes what it reads and the two refusals it makes. Only the
orchestration is here: the arm moved out when this file passed the
1 000-line block, and the entry point stays the gate's ONE command.

ITS FLOOR IS A HARD ZERO. Any class token in any rule selector — passed
to a call or held in a variable, a table, a concatenation — is a
violation on its first occurrence. There is no baseline file, no budget
and no escape hatch: the burn-down that carried the shipped debt was
emptied, and the machinery that held it was deleted in the same move
rather than left behind as a tolerance someone could raise.

ARM 3 — a `data-part` value the harness selects and no source emits.
Two corpora, one question each side answers. The selection side is the
harness (`frontend/maquette/harness/*.py`, the same set ARM 2 reads):
every `[data-part="value"]` in a rule's selector — the three quote
styles, a template literal's included. The emission side is the three
sites that emit the attribute: `frontend/maquette/design/index.html`
(the shell), `src/engine/legacy.js` (the engine) and every `.ts` /
`.tsx` component.

AND THE SELECTION SIDE READS BOTH PLACES A SELECTOR LIVES. A selection
PASSED — the literal argument of `querySelector` et al. — was for a
while the only one this arm read, and the harness holds selectors as
readily as it passes them: in a variable a helper is handed, in a table
a loop walks, in a ternary whose result reaches a call one line later.
Those are the anchor arm's held pass, one attribute over, so they are
read through the SAME extraction (`held_literals`) rather than a second
reader that would drift from it. The printed count says how many of the
selections it checked were held, because a number that cannot be broken
down is a number nobody can tell is short.

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

AND THE SELECTION SIDE REFUSES WHAT IT CANNOT READ. It reads the
harness as RAW TEXT, so a selector hosted in a single-line
double-quoted Python string reaches it with its quotes ESCAPED —
`"…querySelector('[data-part=\\"screen\\"]')…"` — and `PART_SELECTED`
matches no backslash where it expects a quote. Ten of sub-phase 2.1's
63 selections were read by nothing until their host strings were
widened, and nothing refused the shape: the arm simply counted one
fewer, and a count nobody compares is a count nobody reads. So an
escaped quote on a line carrying a `data-part` selection is a
violation, whichever end the escape belongs to — the attribute value's
quotes or the call's own. The instruction is one sentence: host the
selector in `'…'` or in `\"\"\"…\"\"\"`, where nothing needs escaping.
The comment mask runs first, exactly as it does for the values: a shape
a COMMENT quotes is selected by nothing.

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

WHAT IT EXAMINES, AND WHY THE COUNT IS PRINTED. The arm reads every
`data-<state>={…}` expression the components write, and prints how many
it examined. That number is the point: the arm was VACUOUS for as long
as no such attribute existed anywhere, and a green exit over zero
attributes proves nothing about the rule — only that the corpus was
empty. So the count is what tells a reader whether the green means
anything, and the arm is proven by probe-mutation besides. attrs.py's
holds first measured `aria-*` and `title` — the same passthrough, not
the same attribute — and the real `data-open` was owed its own
demonstration on the day it first existed; that gap is closed by
re-measuring, never by analogy.

THE PRECONDITION, AND IT IS NOT A FIFTH ARM. Before any arm reads the
harness, every `frontend/maquette/harness/*.py` file is handed to the
Python parser, and one it refuses is a violation in its own right —
printed with its file, its line and the parser's own message, exit 1.
It is not an arm because it asks nothing about markup: it asks whether
the corpus can be READ at all, which is what every arm assumes and none
of them checks. Sub-phase 4.1 is why. A rewrite left a raw `"` inside a
`"…"` Python string in `inter.py` and `mouse.py`; both stopped parsing,
and every instrument — these four arms and
`classify-rule-anchors.py` — read them as text and reported no
violation. A guard that reports « no violation » over a file it cannot
read is the defect class this lot exists to end, so the guard refuses
it. The detection is `markup_text.parse_failures`, beside the readers
whose silence it explains.

AND THE ARMS STILL RUN. A parse failure does not end the run and does
not drop the file from any corpus: the author sees the parse error AND
everything the arms have to say, in one run. Dropping the broken file
would be the same silent short count in a new coat.

Usage:
    python3 scripts/check-markup-contracts.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The anchor arm, next door. `class_tokens` and `held_occurrences` are
# re-exported rather than used here: the arm is driven through this entry
# point, by the gate and by `tests/scripts/test_check_markup_contracts.py`
# alike.
from markup_anchors import (  # noqa: E402, F401
    check_anchor_debt, class_tokens, harness_files, held_literals,
    held_occurrences, selection_calls,
)
# The shared text readers — see that module's header.
from markup_text import (  # noqa: E402
    COMMENT, HARNESS, HTML_COMMENT, ROOT, SHELL, SOURCES, braced_expression,
    comment_masked, parse_failures,
)

# `store.write({ pipe: closest.dataset.pipe })` — the handler that FORWARDS a
# markup value into a store field. The two names differ often enough
# (`data-hphase` → `phase`) that both are captured.
FORWARDER = re.compile(
    r"store\.write\(\{\s*(?P<field>\w+)\s*:\s*\w+\.dataset\.(?P<attr>\w+)\s*,?\s*\}\)")

# `data-name="value"` in emitted markup or JSX. A value carrying `${` is
# computed, and this rule cannot know what it evaluates to.
EMITTED = re.compile(r"""data-(?P<attr>[a-z][\w-]*)=["'](?P<value>[^"'${]+)["']""")

# The same emission, written in script rather than in markup. A node the
# engine BUILDS carries no `data-part="…"` text anywhere: it is created,
# given its attributes by assignment, then appended. Both shapes read a
# string literal only — `el.dataset.part = kind` and
# `setAttribute("data-part", `p/${k}`)` name no literal, and are skipped
# whole exactly as `EMITTED` skips a computed markup value.
IMPERATIVE_DATASET = re.compile(
    r"""\.dataset\.(?P<attr>[a-z][A-Za-z0-9]*)\s*=\s*["'](?P<value>[^"'${]+)["']""")
IMPERATIVE_SET_ATTRIBUTE = re.compile(
    r"""\.setAttribute\(\s*["']data-(?P<attr>[a-z][\w-]*)["']\s*,\s*"""
    r"""["'](?P<value>[^"'${]+)["']\s*\)""")

# `[data-part="card/title"]` in a rule's selector — the equality form in
# its three quote styles. Only the equality form is read: a presence
# selection `[data-part]` names no part, and this arm holds VALUES.
PART_SELECTED = re.compile(
    r"\[\s*data-part\s*=\s*(?:\"(?P<dq>[^\"]*)\"|"
    r"'(?P<sq>[^']*)'|`(?P<bk>[^`]*)`)\s*\]")

# `[data-part=` — a selection read from the RAW line, whatever quotes
# follow. The point is to see the ones `PART_SELECTED` cannot: it is the
# other half of the count comparison, not a second reader of values.
PART_MENTION = re.compile(r"\[\s*data-part\s*=")

# `\"` or `\'` — a quote escaped because the string hosting it uses the
# same delimiter. On a line carrying a `data-part` selection, this is the
# shape the raw-text reader walks straight past.
ESCAPED_QUOTE = re.compile(r"\\[\"']")

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
        found.extend(part_values(line, selector))
    return found


def part_values(line: int, selector: str) -> list[tuple[int, str]]:
    """Returns the literal `data-part` values one selector selects.

    Args:
        line: The line the selector was read on, carried through so the
            caller keeps its position.
        selector: One selector string, read raw.

    Returns:
        `(line, value)` tuples, in reading order. A value carrying `${`
        is computed and is skipped whole, not half-read.
    """
    found: list[tuple[int, str]] = []
    for match in PART_SELECTED.finditer(selector):
        value = next(g for g in match.groups() if g is not None)
        if "${" in value:
            continue
        found.append((line, value))
    return found


def held_part_selections(path: Path) -> list[tuple[int, str]]:
    """Extracts every `data-part` value one harness file HOLDS.

    THE BLIND SPOT THIS CLOSES, and it is the anchor arm's, one attribute
    over. `part_selections` reads a selection only where it is the
    literal ARGUMENT of a selection call. The harness also holds
    selectors in variables (`screen_port = '[data-part="screen"]…'`), in
    tables a later helper walks (`R14_CASES`, the `layers` list), and in
    a ternary whose result a `querySelector` is handed. Those selections
    are selections; a value renamed in the markup would leave every one
    of them selecting nothing while this arm stayed silent about it.

    The extraction is `held_literals` — the SAME one the anchor arm uses,
    for the same blind spot — and the rule on top of it is this arm's:
    keep the candidate that carries a literal `data-part` selection.

    Args:
        path: A Python file under `HARNESS`.

    Returns:
        `(line, value)` tuples, in file order.
    """
    found: list[tuple[int, str]] = []
    for line, content in held_literals(path):
        found.extend(part_values(line, content))
    return found


def escaped_part_selections(path: Path) -> list[tuple[int, str]]:
    """Returns every `data-part` selection line an escaped quote hides.

    THE CHOICE, AND WHY IT IS A REFUSAL RATHER THAN A DECODE. Reading the
    escaped shape would mean DECODING the Python literal that hosts it,
    and no arm of this guard decodes anything today: `read_literal` walks
    to the closing delimiter and hands back the raw span, `comment_masked`
    tokenizes only to blank what is prose. So a decode is a NEW decoder,
    not a reuse — and it would still be partial, because the host string
    can escape the SELECTION CALL's own quotes too
    (`"…querySelector(\\'…\\')…"`), and `selection_calls` never returns
    such a call at all: its argument position holds a backslash, not a
    quote, so the call is dropped before any value is read. A refusal
    covers both ends with one question and cannot misread a literal it
    never parses. What it costs is one sentence of instruction to the
    author; what it buys is that no `data-part` selection can be unread in
    silence.

    Comments are masked first — with `comment_masked`, which tokenizes
    Python and so knows a `#` inside a string is not a comment — because a
    shape a COMMENT quotes is selected by nothing, exactly as a VALUE a
    comment carries is emitted by nothing.

    The escape is looked for on the LINE, not inside the selector: a
    selector split from its escapes by a parser is the parse this refusal
    exists to avoid. The consequence is stated rather than hidden — a line
    that carries a readable `data-part` selection AND an unrelated escaped
    quote is refused too, and the fix is the same sentence.

    Args:
        path: A Python file under `HARNESS`.

    Returns:
        `(line, text)` pairs, in file order — the line number and the
        stripped source line, for the message.
    """
    text = comment_masked(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if PART_MENTION.search(line) and ESCAPED_QUOTE.search(line):
            found.append((number, line.strip()))
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

    THREE SHAPES, because a node is not always written as markup. The
    attribute appears in markup or JSX as `data-part="value"`, and on an
    element the script BUILDS it can only be an assignment —
    `el.dataset.part = "value"` or `el.setAttribute("data-part",
    "value")`. Reading the markup shape alone called the episode
    popover's contract broken while both of its ends were in place: the
    engine creates that node, so no source text spells the attribute out.

    Comments are stripped before reading: a value a COMMENT carries is
    emitted by nothing, and accepting it would silence the arm over a
    rule that selects nothing. The JS-style stripper covers the sources;
    the shell's HTML comments get their own.

    Args:
        path: One emission site — `index.html` or a source file.

    Returns:
        The literal values emitted, in any of the three shapes. A
        computed value is not a literal and is not returned, whichever
        shape carries it.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".html":
        text = HTML_COMMENT.sub(" ", text)
    else:
        text = COMMENT.sub(" ", text)
    readers = (EMITTED, IMPERATIVE_DATASET, IMPERATIVE_SET_ATTRIBUTE)
    return {match.group("value").strip()
            for reader in readers for match in reader.finditer(text)
            if match.group("attr") == "part"}


def check_part_values() -> int:
    """Arm 3: refuses a selected `data-part` value no source emits, and a
    selection this arm cannot read.

    The direction is ONE-WAY: every value a harness rule selects must be
    emitted somewhere — a selection no emission satisfies is a rule
    selecting nothing, the three-ends contract caught from the markup
    end. An emitted value no rule selects is fine: not every part needs a
    rule.

    The second refusal guards the FIRST: a selection written with escaped
    quotes is invisible to a raw-text reader, so the arm would examine one
    fewer and print a number nobody could tell was short. See
    `escaped_part_selections` for the shape and for why it is refused
    rather than decoded.

    Returns:
        1 when a selected value is emitted nowhere or a selection is
        written in a shape this arm cannot read, 0 otherwise.
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
    held = 0
    for path in files:
        rel = str(path.relative_to(ROOT))
        for line, source in escaped_part_selections(path):
            violations += 1
            print(f"  {rel}:{line}: {source!r} writes a `data-part` selection "
                  "with an ESCAPED quote, and this arm reads the harness as "
                  "RAW TEXT — a backslash where a quote is expected makes the "
                  "selection invisible to it, so the arm would count one "
                  "fewer and say nothing. Host the selector in `'…'` or in a "
                  "triple-quoted string, where nothing needs escaping.",
                  file=sys.stderr)
        passed = part_selections(path)
        holds = held_part_selections(path)
        held += len(holds)
        for line, value in passed + holds:
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
              "no source emits, or written in a shape this arm cannot read. "
              "The value a rule selects and the markup that emits it are ONE "
              "contract — they move together or the rule measures nothing; "
              "and a selection the arm cannot read is one it cannot hold.",
              file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {checked} data-part selection(s) checked "
          f"({held} of them held) against {len(emitted)} emitted value(s) "
          f"from {len(emission_paths)} emission site(s) — every selected "
          "value is emitted. Emitted-but-unselected is fine: not every part "
          "needs a rule.")
    return 0


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

    It examines every `data-<state>={…}` expression the components write
    and prints the count, because that number is what tells a reader
    whether its green means anything: the arm was VACUOUS for as long as
    no such attribute existed, and a green exit over an empty corpus
    proves nothing about the rule. It is proven by probe-mutation
    besides.

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


def check_harness_parses() -> int:
    """The precondition: refuses a rule file the Python parser refuses.

    Not an arm — it asks nothing about markup. It asks whether the corpus
    can be READ, which every arm assumes and none of them checks: the
    arms read raw text, and text has no syntax to be wrong. See
    `markup_text.parse_failures` for the day two rule files stopped
    parsing and every instrument stayed green over them.

    The corpus is read through `harness_files()`, the same list ARM 2 and
    ARM 3 read, so a file that reaches an arm has been through this
    question first.

    Returns:
        1 when any harness file does not parse, 0 otherwise.
    """
    files = harness_files()
    if not files:
        print(f"check-markup-contracts: no Python files under {HARNESS} — "
              "the corpus is empty, so « parses » would mean nothing",
              file=sys.stderr)
        return 1

    failures = parse_failures(files)
    for path, line, message in failures:
        rel = str(path.relative_to(ROOT))
        print(f"  {rel}:{line}: Python cannot parse this file: {message}. "
              "Every arm of this guard reads the harness as raw text, and "
              "text has no syntax to be wrong — so an unparseable rule file "
              "is measured by nothing and reported by nothing, while the "
              "rules it holds are dead. That is sub-phase 4.1, where a raw "
              "`\"` inside a `\"…\"` string broke two rule files under a "
              "green gate.", file=sys.stderr)

    if failures:
        print(f"\ncheck-markup-contracts: {len(failures)} rule file(s) the "
              "Python parser refuses. A guard that reports « no violation » "
              "over a file it cannot read is the defect this refusal exists "
              "to end. Whatever runs after this refusal reads the corpus as "
              "it stands, so every count it prints is short by whatever the "
              "broken file(s) hold.", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: {len(files)} harness rule file(s), every "
          "one parsed by Python before any arm read it as text.")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Runs the precondition and all four arms.

    The precondition runs FIRST. A corpus one file short measures one file
    short, and 4.1 is the day that mattered: every instrument read
    `inter.py` and `mouse.py` as text while neither parsed, and every one
    of them reported no violation.

    A parse failure does not return early. Every arm still runs, over the
    corpus as it stands, so one broken file cannot hide what the arms had
    to say.

    The guard takes NO argument. It once took `--write-baseline` and
    `--write-baseline --allow-additions`, which regenerated the anchor
    arm's burn-down list; the burn-down reached zero and the list, the
    ratchet and the escape hatch went with it.

    Args:
        argv: The arguments to read. `None` reads the process's own, which is
            what the entry point below passes; a caller IN-PROCESS — a test —
            passes its own list, because `sys.argv` under a test runner
            belongs to the runner.

    Returns:
        1 when anything was found or an argument was given, 0 otherwise.
    """
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print("check-markup-contracts: unknown arguments — this guard takes "
              "none. Run it with no argument to check; the `--write-baseline` "
              "mode is gone, and so is the burn-down baseline it wrote: the "
              "anchor arm's floor is a hard zero.", file=sys.stderr)
        return 1
    rc = 0
    if check_harness_parses():
        rc = 1
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

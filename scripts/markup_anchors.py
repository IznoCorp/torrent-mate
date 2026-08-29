#!/usr/bin/env python3
"""ARM 2 of the markup guard — a rule selection anchored on a style class.

SPLIT OUT OF `check-markup-contracts.py`, which this arm took from 149 lines to
1 275 — past the 1 000-line hard ceiling `check-module-size.py` enforces over
`scripts/` as well as the package. The entry point keeps the four arms'
orchestration and stays the gate's ONE command; what this arm reads and
refuses is all here: both extraction passes and both refusals.

Corpus: `frontend/maquette/harness`, every `*.py` file, read as text.

THE DEFECT CLASS. The harness rules select elements by their style class
— `querySelector('.card')` — and those names are the stylesheet's. The
day a surface converts to utility classes the names stop existing, and
every rule that reads them falls with no way to attribute the failure:
anchor, or style?

THE FLOOR IS A HARD ZERO. Not a budget, not a burn-down: ANY class token
in ANY rule selector — passed to a call or held in a variable, a table, a
concatenation — is a violation, named with its file, its line, its
selector and its token. There is no list to consult and no tolerance to
raise, because an empty list is a floor someone can raise again. The debt
this arm was written against was migrated to `data-part` anchors, and
what carried it — a burn-down baseline, a ratchet, an
`--allow-additions` escape hatch — was deleted with it: machinery that
has lost its subject is machinery nobody dares delete later.

WHAT ARM 2 READS, AND THE THREE REFUSALS.

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
        passes on emission. A shape test runs first, `selector_shaped`,
        and it reads the two spellings a selector BUILT at run time
        takes: a `{...}` interpolation is an opaque token that does not
        end the selector, and a leading space is the descendant
        combinator a concatenation supplies (`querySelector(s +
        ' .fback')`). Comments and docstrings are read by nothing at
        runtime, so they are read by nothing here; a candidate carrying
        no class token is not recorded. A held occurrence is a finding
        exactly like a call occurrence — a selector held in a variable
        dies with the stylesheet exactly like one written in a call.

  2. `classList.contains('<class>')` — EVERY one of them, unless the SITE
     is declared in `GENRE_SITES` below with the reason that is true
     there. The genre assertions listed by
     `scripts/classify-rule-anchors.py --exceptions` are the whole
     exemption: their subject IS the applied style, so moving them to a
     data-* attribute would make them true after the class is gone and
     the rule would measure less than it does today.

     THE KEY IS THE SITE, NOT THE NAME, and a list of seven migrated
     state names is what it replaced. A name-keyed exemption exempted
     `flux` and `h2` wherever they appeared, and `machine.py` used both
     to walk siblings looking for the flux list — structure, not style,
     with `[data-part="flux"]` and `[data-part="heading"]` emitted and
     selected by that same file. A name list also said nothing at all
     about a `contains` on a name nobody had thought of: it warned, and a
     warning is not a floor.

  3. A class name READ from the class ATTRIBUTE — the fifth syntactic
     position, and the one the first three arms were blind to. A rule can
     select without ever writing a selector: `className.includes('x')`,
     `className.split(' ').includes('x')`, `className.replace('x ', '')`,
     `className === 'x'`, a regex of class names `.test`ed against
     `className`, a table of class names matched against a SPREAD
     `classList`, and a CSS rule the harness INJECTS into the document.
     Six shapes, every one of them selection work, none of them
     selector-shaped: `HELD_RE` wants a literal starting with `.`, `#` or
     `[`, and `'in_library'` starts with a letter. What made this the
     expensive kind of hole is that four of the six sat on lines the
     migration itself rewrote — the selector beside them moved to
     `data-part` while the class read stayed, inches away.

     A read that only REPORTS is not one: `map(el => el.className)`
     prints what an element wears and names no class of its own, and a
     rule that ADDS or REMOVES a class drives the document rather than
     selecting in it. A stylesheet read as TEXT (`".splashbar {" in
     gate`) is not an injection: nothing is assigned and nothing
     selects.

AND THE ZERO IS ONLY WORTH WHAT THE READERS SEE. A floor of zero over a
corpus a reader walks past is not a floor, which is why the two shapes
`selector_shaped` now reads were closed BEFORE the floor was declared,
and why the independent reader — `classify-rule-anchors.py --baseline`,
whose listing must print an empty list — reads the same corpus through
its own extraction. Two readers agreeing on zero is a measurement; one
reader's zero is a claim.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# The shared text readers — see that module's header.
from markup_text import (  # noqa: E402
    COMMENT, HARNESS, HTML_COMMENT, ROOT, SHELL, SOURCES, braced_expression,
    comment_masked, outside_attribute_blocks, read_literal,
    strip_braced_spans, strip_interpolations,
)

# `querySelector(` et al. — every call whose first argument is the
# selection, whatever object the method hangs off (`document.`, `c.`,
# `s.`, ...). Same reading as the classifier: the method is pinned there
# and mirrored here on purpose.
CALL = re.compile(r"(querySelector|querySelectorAll|locator|matches)\s*\(")

# `classList.contains('open')` — the assertion population, one class name
# per call.
CONTAINS = re.compile(r"classList\.contains\(\s*(['\"])([^'\"]*)\1\s*\)")

# The permanent genre assertions, never refused — keyed on the SITE, not
# on the class name. Their written reasons live in
# `classify-rule-anchors.py --exceptions`, and the reason is the whole
# exemption: the assertion's subject is the applied style THERE, so a
# data-* would keep it true after the class is gone and the rule would
# measure less than it does today.
#
# WHY THE SITE AND NOT THE NAME. A name-keyed exemption exempts every
# line that name appears on, whatever that line is doing: `flux` and `h2`
# were exempt as « the applied style » while `machine.py` used them to
# walk siblings and find which one is the flux list — a STRUCTURAL read,
# with `[data-part="flux"]` and `[data-part="heading"]` both emitted and
# both selected by that same file. The written reason did not describe
# that site, and nothing could tell, because the list held names.
#
# AND EACH SITE CARRIES ITS OWN REASON, because they are not the same
# reason. One shared sentence read true of three sites and false of two,
# and a sentence that covers everything distinguishes nothing.
#
# The key is `file:line`. A line that MOVES re-opens the question, which
# is the intended cost: an exemption is a claim about one assertion, and
# an assertion that has moved is one nobody has re-read. The table lives
# here because this module is importable; `classify-rule-anchors.py`
# reads it for `--exceptions` rather than keeping a second copy. That is
# a DECLARATION shared, never an extraction: the two readers still walk
# the corpus by their own passes.
GENRE_SITES = {
    ("audit.py", 101, "ep"): (
        "R3 measures the DRAWN size of the episode cell, and the declared "
        "31 x 27 exception is about that geometry: at 13 cells per row a "
        "44px target would demand 572px of width. The subject is the "
        "applied style, so a `data-*` would keep the rule true after the "
        "class is gone and it would measure less than it does today"),
    ("audit.py", 167, "radio"): (
        "R7 asks which SHAPE an option is drawn as — a radio or a "
        "checkbox — and the shape is what the class applies. Reading a "
        "`data-*` would answer what the option IS, which is the question "
        "the rule is not asking"),
    # ⚠ KEYED BY LINE, so a change ABOVE this one moves it. L10-bis's repair
    # of R12 (B-057) added lines to `audit2.py` and this exemption stopped
    # matching at 124; the guard said so immediately, which is the table
    # working as designed rather than a cost of it.
    ("audit2.py", 150, "note"): (
        "the media-sheet inventory skips the blocks drawn as a NOTE, "
        "which is a style genre and not a section of the sheet. A "
        "`data-*` would name the block; the rule needs to know how it is "
        "drawn"),
}

# ---- ARM 2, the fifth position: a class name read from the attribute ----

# `e.className.includes('in_library')`, and the same read with a
# transformation in the middle: `button.className.split(' ')
# .includes('primary')`. What the pattern pins is the METHOD and its
# quoted argument; between them and `className` sits a transformation,
# never a statement boundary. `split` is deliberately NOT in the method
# list: its argument is the separator, not a class name.
#
# The name must LOOK like a class token, and a trailing space is part of
# the read rather than of the name — `className.replace('ep ', '')`
# strips the token and the space that follows it.
CLASS_NAME_READ = re.compile(
    r"\.className\b[^;\n]{0,40}?\.(?:includes|startsWith|endsWith|indexOf"
    r"|replace|search|match)\(\s*(['\"])(?P<name>[A-Za-z_][\w-]*) ?\1")

# `x.className === 'card'` — the same read written as an equality. An
# EMPTY comparison names no class: `e.className === ''` asks whether the
# element is unclassed, which is a question about the attribute, not
# about a name.
CLASS_NAME_EQUALS = re.compile(
    r"\.className\s*===?\s*(['\"])(?P<name>[A-Za-z_][\w-]*)\1")

# `/searchclear|burger|fab/.test(x.className)` — a TABLE of class names in
# a regex literal, which is one of the two allowlists an R2-shaped rule
# carries. No reader opens a regex literal, and every alternation branch
# in one tested against `className` is a class name.
CLASS_NAME_REGEX = re.compile(
    r"/(?P<body>[^/\n]+)/\s*\.test\(\s*[^)\n]*\.className")

# `[...badge.classList].find((c) => TONS[c])` — the class list read as a
# COLLECTION and matched against a table whose KEYS are the class names.
# There is no literal to name, which is exactly why nothing saw it: what
# this shape refuses is the SITE. `add`, `remove` and `toggle` are not
# here — a rule that writes a class drives the document rather than
# selecting in it — and `contains` has its own refusal above.
CLASS_LIST_COLLECTION = re.compile(
    r"\.\.\.\s*[\w.$]*\.classList\s*\]"
    r"|\.classList\s*\.\s*(?:find|filter|some|every|includes|indexOf)\s*\(")

# `st.textContent = '.cov{-webkit-line-clamp:' + n + '}'` — a CSS rule the
# harness INJECTS. Its selector is a selector, and a class token in it
# dies with the stylesheet exactly like one handed to `querySelector`.
# The assignment is what tells it apart from a stylesheet read as TEXT
# (`".splashbar {" in gate`), where the subject IS the source and nothing
# selects.
INJECTED_RULE = re.compile(
    r"\.(?:textContent|innerHTML|innerText)\s*=\s*"
    r"(['\"])(?P<css>(?:(?!\1)[^\n])*)\1")

# ---- ARM 2 held pass -----------------------------------------------------

# The characters a selector can hold, once its `{...}` interpolations
# are removed. A string carrying anything else — prose, a stray operator
# — is not selector-shaped and is read by neither pass. Mirrored
# deliberately from the classifier: the two readers must agree or one is
# wrong.
SELECTOR_ALPHABET = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789.#[]=\"'`~+>*,:()\\-_^$|/ ")

# A class token followed by a call parenthesis names a method, not a
# class — CSS class tokens take no arguments. `:has-text(` is fine: its
# parenthesis hangs off a pseudo-class, not off a class token.
METHOD_CALL = re.compile(r"^\.[-\w]+\s*\(")

# A quoted literal whose content starts with a selector character —
# after any LEADING SPACE, because a selector concatenated onto a
# variable starts with the descendant combinator
# (`querySelector(s + ' .fback')`) — and holds, up to the closing quote,
# selector text: plain characters and attribute blocks. An attribute
# block may carry the delimiter (`'[data-x="y"]'` inside a single-quoted
# string), which is exactly why the pass cannot be a simple quote-pair
# scan. Stateless on purpose: a French apostrophe or a nested backtick
# that would desync a quote-pair walker simply fails to match here, and
# the literal after it is read on its own. The leading space sits
# OUTSIDE the captured group: what the readers then judge is the
# selector, not the concatenation that hosts it.
HELD_RE = re.compile(
    r"""(["'`]) *(?P<sel>[.#\[](?:(?!\1)[^\[\n])*(?:\[[^\[\]\n]*\]"""
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

    # A FOURTH EMISSION SITE, and it arrived with L07: a `cva(…)` factory. Its
    # argument IS the class attribute — `cva("fback flex items-center …")`
    # emits `fback` exactly as `className="fback"` did — and it wears no
    # `class=` for the three readers below to find. Left unread, the arm lost
    # every converted name from its vocabulary and stopped recognising them as
    # class anchors at all.
    for path in files:
        # `*.variants.ts` as a FAMILY: the vocabulary split into three subject
        # files behind a barrel when it passed the module ceiling, and a reader
        # matching one exact name would have gone quietly blind that day.
        if not (path.name.endswith("variants.ts") or path.parent.name == "variants"):
            continue
        text = COMMENT.sub(" ", path.read_text(encoding="utf-8"))
        # THE FIRST TOKEN OF A `cva(` BASE STRING, and only that one. This
        # wave's own convention keeps the identity class at the FRONT of every
        # variant — everything after it is a utility, and reading those as
        # emitted class names would put `flex` and `items-center` into a
        # vocabulary that decides what counts as a class anchor.
        for match in re.finditer(r'cva\(\s*"([^"\n]*)"', text):
            head = match.group(1).split()
            if head and re.fullmatch(r"[a-zA-Z][\w-]*", head[0]):
                emitted.add(head[0])

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


def selector_shaped(content: str) -> bool:
    """True when a held candidate is SHAPED like a selector.

    The shape test, and it is the half of the held pass that decides what
    is even a candidate. Three refusals, each paid for by a string the
    pass would otherwise have called an anchor:

      * a brace that never balances — `.cov{-webkit-line-clamp:`,
        `.splashbar {` — is stylesheet text, not an interpolation;
      * a character outside the selector alphabet, once the balanced
        interpolations are removed;
      * an `=` OUTSIDE an attribute block — `#splash.hidden = {…}` is a
        journal label about an element, not a selection of it. A
        selector's only `=` lives inside `[...]`.

    A method call (`.render(`) is refused last, on the text as written.

    Args:
        content: One candidate string, its leading space already trimmed
            by the pattern that found it.

    Returns:
        True when the candidate can be read as a selector.
    """
    probe = strip_braced_spans(content)
    if probe is None:
        return False
    if any(ch not in SELECTOR_ALPHABET for ch in probe):
        return False
    if "=" in outside_attribute_blocks(probe):
        return False
    return not METHOD_CALL.match(content)


def held_literals(path: Path) -> list[tuple[int, str]]:
    """Returns every selector-shaped literal one harness file HOLDS.

    A held literal is a selector-shaped string OUTSIDE any selection
    call's argument position — a selector held in a variable, a table, a
    helper's argument, a comparison. It is the extraction, not a rule:
    what a caller then keeps is the caller's question. ARM 2 keeps the
    ones carrying class tokens the design sites emit; ARM 3 keeps the
    ones carrying a `data-part` selection. Both blind spots are the SAME
    blind spot — a selector no call names — so they are read once here
    rather than twice, in two readers that would drift apart.

    Comments are masked first, `comment_masked` doing it: it knows a `#`
    inside a string is not a comment, and it blanks the JS comments
    inside the triple-quoted containers the harness embeds its page
    scripts in. Blanks preserve offsets, so a candidate found in the
    masked text still names its original line.

    The shape test is `selector_shaped`, in one function, so that the two
    shapes a run-time-built selector takes — a `{...}` interpolation, a
    leading space where a concatenation supplies the head — are read the
    same way by every arm that reads a held selector.

    Args:
        path: A Python file under `HARNESS`.

    Returns:
        `(line, content)` pairs, in file order — every literal that is
        selector-shaped and is not a selection call's own argument.
    """
    text = path.read_text(encoding="utf-8")
    masked = comment_masked(text)
    call_args = call_argument_starts(text)
    found: list[tuple[int, str]] = []
    for match in HELD_RE.finditer(masked):
        if match.start() in call_args:
            continue
        content = match.group("sel")
        if not selector_shaped(content):
            continue
        line = text.count("\n", 0, match.start()) + 1
        found.append((line, content))
    return found


def held_occurrences(path: Path, emitted: set[str]) -> list[tuple[int, str]]:
    """Returns every held ANCHOR selector in one harness file, in order.

    The extraction is `held_literals`; the rule below is ARM 2's own — a
    candidate must carry at least one class token, and must either show
    selector structure or have every one of its tokens emitted by a
    design site.

    Args:
        path: A Python file under `HARNESS`.
        emitted: The class tokens the three design sites emit — the
            false-positive rule's emission half is decided by this set.

    Returns:
        `(line, content)` pairs, one per candidate that carries at least
        one class token and passes the false-positive rule.
    """
    found: list[tuple[int, str]] = []
    for line, content in held_literals(path):
        tokens = class_tokens(content)
        if not tokens:
            continue
        if not (has_structure(content)
                or all(token[1:] in emitted for token in tokens)):
            continue
        found.append((line, content))
    return found


def class_name_reads(path: Path) -> list[tuple[int, str | None]]:
    """Extracts every class name one harness file READS from the attribute.

    The fifth syntactic position, in its six shapes — the module header
    names each one and what it costs. A shape that quotes the name yields
    it; the two that do not — a table matched against a spread
    `classList` — yield `None`, and the caller names the SITE instead. A
    name that is never written down is still a dependency on the
    stylesheet, and refusing only what is quoted would keep the hole
    exactly where the harness had put it.

    Comments are masked first, `comment_masked` doing it, for the reason
    every other pass masks them: a read a COMMENT describes is performed
    by nothing.

    Args:
        path: A Python file under `HARNESS`.

    Returns:
        `(line, name)` pairs, in file order — `name` is the class name, or
        None when the shape names no literal.
    """
    text = comment_masked(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str | None]] = []

    def line_of(offset: int) -> int:
        return text.count("\n", 0, offset) + 1

    for pattern in (CLASS_NAME_READ, CLASS_NAME_EQUALS):
        for match in pattern.finditer(text):
            found.append((line_of(match.start()), match.group("name")))
    for match in CLASS_NAME_REGEX.finditer(text):
        line = line_of(match.start())
        for branch in match.group("body").split("|"):
            name = re.match(r"[A-Za-z_][\w-]*", branch.strip())
            if name is not None:
                found.append((line, name.group(0)))
    for match in CLASS_LIST_COLLECTION.finditer(text):
        found.append((line_of(match.start()), None))
    for match in INJECTED_RULE.finditer(text):
        css = match.group("css")
        if "{" not in css:
            continue                  # not a rule: no selector, no braces
        for token in class_tokens(css.split("{", 1)[0]):
            found.append((line_of(match.start()), token[1:]))
    found.sort()
    return found


def collect_read_findings() -> list[tuple[str, str | None]]:
    """Collects every class-attribute read the fifth-position pass refuses.

    Returns:
        `(where, name)` pairs, in file order — the `file:line` and the
        class name, or None when the shape names no literal.
    """
    findings: list[tuple[str, str | None]] = []
    for path in harness_files():
        rel = str(path.relative_to(ROOT))
        for line, name in class_name_reads(path):
            findings.append((f"{rel}:{line}", name))
    return findings


def harness_files() -> list[Path]:
    """Returns the anchor arm's corpus, in a fixed order.

    Returns:
        Every `*.py` file directly under `frontend/maquette/harness`,
        sorted — the same corpus the classifier reads.
    """
    return sorted(p for p in HARNESS.glob("*.py") if p.is_file())


def collect_anchor_findings() -> list[tuple[str, str, str, str, bool]]:
    """Collects every finding the anchor arm exists to refuse.

    Both passes feed it — the call pass reads the selection calls, the
    held pass reads the selector-shaped strings outside them — and each
    token OCCURRENCE is one finding, because a selector carrying two
    class tokens carries two of them.

    Returns:
        `(kind, name, subject, where, held)` tuples, in file order: the
        kind (`selection` or `assertion`), the class name the finding is
        about, the full selector for a selection and the class name for
        an assertion — the DISPLAY subject — the `file:line` it was
        found at, and whether the held pass found it.
    """
    findings: list[tuple[str, str, str, str, bool]] = []
    emitted = emission_tokens()
    for path in harness_files():
        rel = str(path.relative_to(ROOT))
        for line, _, selector in selection_calls(path):
            for token in class_tokens(selector):
                findings.append(
                    ("selection", token, selector, f"{rel}:{line}", False))
        for line, content in held_occurrences(path, emitted):
            for token in class_tokens(content):
                findings.append(
                    ("selection", token, content, f"{rel}:{line}", True))
        for line, name in state_assertions(path):
            if (path.name, line, name) not in GENRE_SITES:
                findings.append(
                    ("assertion", name, name, f"{rel}:{line}", False))
    return findings


def check_anchor_debt() -> int:
    """Arm 2: refuses EVERY class anchor, held or called. The floor is zero.

    There is no list to consult: a class token in a rule selector is a
    violation on its first occurrence, named with its file, its line, its
    selector and its token, and so is a `classList.contains` on one of
    the seven migrated states. The two spellings are printed apart —
    passed to a call, or held in a variable, a table, a concatenation —
    because the held ones are the ones a reader forgets exist.

    A `classList.contains` name that is neither a migrated state nor a
    listed genre is warned about — exactly as the classifier warns —
    because it is measured by nothing.

    Returns:
        1 when any class anchor was found, 0 otherwise.
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

    exempt = 0
    violations = 0
    for where, name in collect_read_findings():
        violations += 1
        if name is None:
            print(f"  {where}: this rule reads the class ATTRIBUTE as a "
                  "collection and matches it against a table of class names. "
                  "The names are keys, so nothing quotes them and nothing "
                  "else in this guard can see them — and they die with the "
                  "stylesheet all the same. Read the element's `data-*` "
                  "instead: `element.dataset.tone`.", file=sys.stderr)
            continue
        print(f"  {where}: the rule decides on the class name {name!r}, read "
              "from the class ATTRIBUTE rather than through a selector. That "
              "is a selection: it dies the day the class is removed, and "
              "nothing can then say whether the read or the style was at "
              "fault. Read the element's `data-part` or its state attribute.",
              file=sys.stderr)
    for kind, name, subject, where, held in collect_anchor_findings():
        violations += 1
        if kind == "assertion":
            print(f"  {where}: classList.contains({name!r}) decides on a "
                  "style class at a site nothing exempts. If the state has a "
                  "boolean data-* attribute, assert THAT — "
                  "`hasAttribute('data-open')` — so the rule survives the "
                  "class; if the subject really is the applied style, declare "
                  "this SITE in `markup_anchors.GENRE_SITES` with the reason "
                  "that is true HERE.", file=sys.stderr)
        elif held:
            print(f"  {where}: the string {subject!r} held outside any "
                  f"selection call carries the class token {name!r}. A "
                  "selector held in a variable, a table or a concatenation "
                  "dies the day the class is removed exactly like one "
                  "written in a call. Anchor it on the element's "
                  "`data-part`.", file=sys.stderr)
        else:
            print(f"  {where}: selector {subject!r} carries the class token "
                  f"{name!r}. A class token in a rule selection dies the day "
                  "the class is removed, and nothing can then say whether "
                  "the anchor or the style was at fault. Anchor it on the "
                  "element's `data-part`.", file=sys.stderr)
    for path in files:
        for line, name in state_assertions(path):
            if (path.name, line, name) in GENRE_SITES:
                exempt += 1

    if violations:
        print(f"\ncheck-markup-contracts: {violations} anchor occurrence(s) "
              "on a style class. The floor is a hard ZERO — there is no "
              "baseline, no budget and no escape hatch, because a tolerance "
              "is a floor someone raises. Anchor the selection on a "
              "`data-part` value, or the assertion on the state's boolean "
              "attribute.", file=sys.stderr)
        return 1

    print(f"check-markup-contracts: 0 class-anchored selection call over "
          f"{len(files)} harness rule file(s), passed or held, 0 class name "
          "read from the class attribute, and 0 state assertion left on a "
          f"class. {exempt} genre assertion(s) exempt, by SITE: permanent, "
          "each reason in scripts/classify-rule-anchors.py --exceptions.")
    return 0

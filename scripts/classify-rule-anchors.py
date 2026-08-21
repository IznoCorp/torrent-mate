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

WHAT IT DOES NOT READ. A call whose argument is not a string literal — a
variable, an expression — is a CALL this tool cannot name; the string
that defines the variable is the held pass's business instead, if it is
selector-shaped. `classList.contains(...)` assertions are a second
population: they are reported by `--baseline` under `"kind":
"assertion"` and never mixed into the selection table. Comments and
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

# `querySelector(` et al. — every call whose first argument is the selection,
# whatever object the method hangs off (`document.`, `c.`, `s.`, ...).
CALL = re.compile(r"(querySelector|querySelectorAll|locator|matches)\s*\(")

# `classList.contains('open')` — the assertion population, one class name per
# call.
CONTAINS = re.compile(r"classList\.contains\(\s*(['\"])([^'\"]*)\1\s*\)")

# The seven state classes migrated to the boolean data-* attributes.
# `classList.contains` on one of these is a state assertion, and it is listed
# by `--baseline` rather than counted as a selection.
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

# ---- the held pass -------------------------------------------------------

# The design sources the false-positive rule reads as the EMISSION side:
# the shell, the engine and the sources under design/src. A class token
# is emitted when one of them writes it in a class= / className= value.
SHELL = ROOT / "frontend" / "maquette" / "design" / "index.html"
SOURCES = ROOT / "frontend" / "maquette" / "design" / "src"

# The characters a selector can hold, once its `{...}` interpolations
# are removed. A string carrying anything else — prose, a stray operator
# — is not selector-shaped and is read by neither pass.
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
# block may carry the delimiter (`a [data-x="y"]` inside a single-quoted
# string), which is exactly why the pass cannot be a simple quote-pair
# scan. The leading space sits OUTSIDE the captured group: what is
# judged is the selector, not the concatenation that hosts it.
HELD_RE = re.compile(
    r"""(["'`]) *(?P<sel>[.#\[](?:(?!\1)[^\[\n])*(?:\[[^\[\]\n]*\]"""
    r"""(?:(?!\1)[^\[\n])*)*)\1""")

# The JS comments of the embedded-JS containers — the same two shapes
# ARM 1 strips, applied to the content of a triple-quoted string.
JS_COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)

# HTML comments are the shell's shape.
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

# `class=` / `className=` — every attribute spelling, whichever side of
# an assignment or a JSX tag it hangs on. `\b` keeps `subclass =` out.
CLASS_ATTR = re.compile(r"\bclass(?:Name)?\s*=\s*")


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


def line_offsets(text: str) -> list[int]:
    """Returns the character offset of the start of every line.

    tokenize reports positions as `(line, column)`; the masking below
    needs character offsets, and this table converts between the two.

    Args:
        text: The file text being read.

    Returns:
        `offsets[i]` is the offset of line `i + 1`'s first character.
    """
    offsets = [0]
    for match in re.finditer("\n", text):
        offsets.append(match.end())
    return offsets


def comment_masked(text: str) -> str:
    """Returns `text` with every comment read by nothing blanked out.

    Python comments are blanked exactly — tokenize knows where a `#`
    starts a comment and where it does not, which a regex over raw text
    cannot tell (`#view` inside a string is not a comment). The embedded
    JS lives in triple-quoted strings: a triple-quoted DOCSTRING is
    prose and is blanked whole; a triple-quoted CONTAINER is code and
    its JS comments are blanked the way ARM 1 blanks them. Blanks
    replace characters and newlines stay, so a candidate found in the
    masked text still names the original line.

    Args:
        text: The file text being read.

    Returns:
        The comment-masked copy — or `text` itself when the file is not
        valid Python: tokenize then cannot delimit the strings either,
        and the reader falls back to reading raw, exactly as the call
        pass always has.
    """
    out = list(text)

    def blank(start: int, end: int) -> None:
        for i in range(start, end):
            if out[i] != "\n":
                out[i] = " "

    offsets = line_offsets(text)

    def position(line: int, col: int) -> int:
        return offsets[line - 1] + col

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError):
        return text
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            blank(position(tok.start[0], tok.start[1]),
                  position(tok.end[0], tok.end[1]))
    for i, tok in enumerate(tokens):
        if tok.type != tokenize.STRING or not (
                tok.string.startswith('"""') or tok.string.startswith("'''")):
            continue
        prev = tokens[i - 1] if i else None
        start = position(tok.start[0], tok.start[1])
        end = position(tok.end[0], tok.end[1])
        if prev is None or prev.type in (tokenize.NEWLINE, tokenize.NL,
                                         tokenize.INDENT, tokenize.DEDENT):
            blank(start, end)          # a docstring: prose, read by nothing
            continue
        content = text[start + 3:end - 3]
        for match in JS_COMMENT.finditer(content):
            blank(start + 3 + match.start(), start + 3 + match.end())
    return "".join(out)


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


def strip_braced_spans(selector: str) -> str | None:
    """Removes every `{...}` interpolation, `${...}` included.

    Mirrored from `markup_anchors.strip_braced_spans`, whose header carries
    the rationale: an interpolation is an OPAQUE token, and a brace that
    never balances says the string is stylesheet text, not a selection.

    Args:
        selector: One candidate string.

    Returns:
        The string with every balanced `{...}` span removed — and the `$`
        of a `${...}` with it — or None when a brace never balances.
    """
    out: list[str] = []
    i = 0
    while i < len(selector):
        ch = selector[i]
        if ch == "}":
            return None
        if ch != "{":
            out.append(ch)
            i += 1
            continue
        depth = 0
        j = i
        while j < len(selector):
            if selector[j] == "{":
                depth += 1
            elif selector[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= len(selector):
            return None
        if out and out[-1] == "$":
            out.pop()
        i = j + 1
    return "".join(out)


def outside_attribute_blocks(selector: str) -> str:
    """Returns `selector` with every `[...]` block removed.

    An attribute block's contents are values, not selector syntax, so a
    question about SYNTAX is asked of what sits outside them.

    Args:
        selector: One candidate string.

    Returns:
        The text outside every `[...]` block.
    """
    out: list[str] = []
    i = 0
    while i < len(selector):
        if selector[i] == "[":
            end = selector.find("]", i)
            i = end + 1 if end != -1 else len(selector)
            continue
        out.append(selector[i])
        i += 1
    return "".join(out)


def selector_shaped(content: str) -> bool:
    """True when a held candidate is SHAPED like a selector.

    Mirrored deliberately from `markup_anchors.selector_shaped`, which names
    the three refusals and the string each was paid for: the two readers must
    agree or one of them is wrong.

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
                else JS_COMMENT.sub(" ", text))
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


def held_selectors(text: str, emitted: set[str]) -> list[tuple[int, str]]:
    """Returns every held selector in one file's text, in file order.

    A held selector is a selector-shaped string literal OUTSIDE any
    selection call's argument position — a selector held in a variable,
    a table, a helper's argument, a comparison. The candidate regex is
    stateless on purpose: a French apostrophe or a nested backtick that
    would desync a quote-pair walker simply fails to match here, and
    the literal after it is read on its own.

    Args:
        text: The file text being read.
        emitted: The class tokens the three design sites emit.

    Returns:
        `(start, content)` pairs — the literal's opening-quote offset
        and its content — for every candidate that carries at least one
        class token and passes the false-positive rule.
    """
    masked = comment_masked(text)
    call_args = call_argument_starts(text)
    found: list[tuple[int, str]] = []
    for match in HELD_RE.finditer(masked):
        if match.start() in call_args:
            continue
        content = match.group("sel")
        if not selector_shaped(content):
            continue
        tokens = class_tokens(content)
        if not tokens:
            continue
        if not (has_structure(content)
                or all(token[1:] in emitted for token in tokens)):
            continue
        found.append((match.start(), content))
    return found


def collect(root: Path) -> tuple[list[tuple[str, int, str, str]],
                                  list[tuple[str, int, str]],
                                  list[tuple[str, int, str]]]:
    """Collects every selection call, state assertion and held selector.

    Args:
        root: The directory whose `*.py` files are the corpus.

    Returns:
        Selections as `(file, line, method, selector)`, assertions as
        `(file, line, class_name)` and held selectors as
        `(file, line, content)`, each in file order.
    """
    selections: list[tuple[str, int, str, str]] = []
    assertions: list[tuple[str, int, str]] = []
    held: list[tuple[str, int, str]] = []
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
    return selections, assertions, held


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
                 held: list[tuple[str, int, str]]) -> None:
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
    print(f"{sum(tokens.values()) + sum(held_tokens.values())} class token "
          "occurrences total")


def print_exceptions() -> None:
    """Prints the five permanent genre assertions, each with its reason."""
    for name in GENRE_CLASSES:
        print(f"{name:<8} {GENRE_REASON}")


def print_baseline(selections: list[tuple[str, int, str, str]],
                   assertions: list[tuple[str, int, str]],
                   held: list[tuple[str, int, str]]) -> None:
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

    selections, assertions, held = collect(root)
    if not selections:
        print(f"classify-rule-anchors: no selection call found under {root} — "
              "either the extraction broke or the root is wrong",
              file=sys.stderr)
        return 1

    if mode == "--summary":
        print_summary(selections)
    elif mode == "--tokens":
        print_tokens(selections, held)
    elif mode == "--exceptions":
        print_exceptions()
    else:
        print_baseline(selections, assertions, held)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

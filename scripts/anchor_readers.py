#!/usr/bin/env python3
"""The text readers `classify-rule-anchors.py` reads its corpus with.

SPLIT OUT OF IT, exactly as `markup_anchors.py` and `markup_text.py` were
split out of `check-markup-contracts.py`: the read pass of 6.6 took that file
from 798 non-blank lines to 880, past the 800-line warn tier
`check-module-size.py` holds `scripts/` to. What stays next door is the
QUESTIONS — the precedence rule, the four modes and what each one prints.
What lives here is WHERE the text is: which bytes are a string literal, a
comment, a selector, a class emission, a class read.

AND THIS IS A MIRROR, ON PURPOSE. Every reader below has a twin under
`markup_text.py` / `markup_anchors.py`, and the twin is not imported. The
guard beside this tool refuses the first class anchor it finds; this tool is
the SECOND reader of the same corpus, and a classification cross-checked only
by the guard that produced it proves nothing. Two extractions agreeing on
zero is a measurement — one extraction's zero is a claim. So a change to one
side is a change to be made on the other, deliberately, and the two must
agree or one of them is wrong.

What is NOT mirrored is `GENRE_SITES`: an exemption is a DECISION, and a
decision with two copies is a decision that drifts.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# `querySelector(` et al. — every call whose first argument is the selection,
# whatever object the method hangs off (`document.`, `c.`, `s.`, ...). Both
# passes need it: the call pass to read the argument, the held pass to know
# which literals the call pass already owns.
CALL = re.compile(r"(querySelector|querySelectorAll|locator|matches)\s*\(")

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

# ---- the read pass: a class name taken from the class ATTRIBUTE ---------
#
# Mirrored deliberately from `markup_anchors`, whose header names the six
# shapes and what each one cost: the two readers must agree, or one of them
# is wrong. A read is not a selector and lives in none of the positions the
# call and held passes know — which is how `className.includes('in_library')`
# survived a migration that rewrote the selector on the SAME line.
CLASS_NAME_READ = re.compile(
    r"\.className\b[^;\n]{0,40}?\.(?:includes|startsWith|endsWith|indexOf"
    r"|replace|search|match)\(\s*(['\"])(?P<name>[A-Za-z_][\w-]*) ?\1")
CLASS_NAME_EQUALS = re.compile(
    r"\.className\s*===?\s*(['\"])(?P<name>[A-Za-z_][\w-]*)\1")
CLASS_NAME_REGEX = re.compile(
    r"/(?P<body>[^/\n]+)/\s*\.test\(\s*[^)\n]*\.className")
CLASS_LIST_COLLECTION = re.compile(
    r"\.\.\.\s*[\w.$]*\.classList\s*\]"
    r"|\.classList\s*\.\s*(?:find|filter|some|every|includes|indexOf)\s*\(")
INJECTED_RULE = re.compile(
    r"\.(?:textContent|innerHTML|innerText)\s*=\s*"
    r"(['\"])(?P<css>(?:(?!\1)[^\n])*)\1")

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


def class_attribute_reads(text: str) -> list[tuple[int, str | None]]:
    """Returns every class name a file READS from the class attribute.

    The fifth syntactic position, read here by this tool's own pass — the
    guard next door refuses it, and a refusal cross-checked only by the
    reader that produced it proves nothing. Six shapes, named in
    `markup_anchors`'s header: a membership test, an equality, a
    `replace`, a regex of class names tested against `className`, a table
    matched against a SPREAD `classList`, and a CSS rule the harness
    injects. The two shapes that quote no name yield None; the site is
    still the finding.

    Args:
        text: The file text being read.

    Returns:
        `(offset, name)` pairs — the match's character offset and the
        class name, or None when the shape names no literal.
    """
    masked = comment_masked(text)
    found: list[tuple[int, str | None]] = []
    for pattern in (CLASS_NAME_READ, CLASS_NAME_EQUALS):
        found += [(m.start(), m.group("name")) for m in pattern.finditer(masked)]
    for match in CLASS_NAME_REGEX.finditer(masked):
        for branch in match.group("body").split("|"):
            name = re.match(r"[A-Za-z_][\w-]*", branch.strip())
            if name is not None:
                found.append((match.start(), name.group(0)))
    found += [(m.start(), None) for m in CLASS_LIST_COLLECTION.finditer(masked)]
    for match in INJECTED_RULE.finditer(masked):
        css = match.group("css")
        if "{" not in css:
            continue
        found += [(match.start(), token[1:])
                  for token in class_tokens(css.split("{", 1)[0])]
    return sorted(found)


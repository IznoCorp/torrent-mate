#!/usr/bin/env python3
"""The text readers the markup guard's arms share.

SPLIT OUT OF `check-markup-contracts.py` alongside the anchor arm: with both
moved, the entry point and each of its siblings sit under the 800-line warn
tier, where the one file had grown to 1 275 lines and blocked
`check-module-size.py --root scripts` outright.

These decide WHERE the text is — which bytes are a string literal, a braced
expression, a comment — and never what an arm makes of what they find. The
questions live with the arms. The corpus paths and the two comment strippers
live here for the same reason: every arm reads the same trees, and a second
copy of a path is a second thing to move.
"""

from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "frontend" / "maquette" / "design" / "src"

# The anchor arm's corpus: the harness rules, the same `*.py` set
# `classify-rule-anchors.py` reads. The two readers must share the corpus
# or the cross-check they are held against each other in `--write-baseline`
# measures nothing. The part arm reads the same set, from the other end.
HARNESS = ROOT / "frontend" / "maquette" / "harness"

# Comments are stripped before anything is read. `library.tsx` carries a comment
# describing a REJECTED first version — « gated it on `phase === "prete"` » —
# and reading it as code made this rule believe `prete` was a value some reader
# understood, so it walked past the dead retry button it was written to catch.
# Reading CSS as text cost the token guard the same way, one file over.
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)

# The shell, one of the three emission sites. Served and written outside
# the sources glob, so it is named on its own.
SHELL = SOURCES.parent / "index.html"

# HTML comments are the shell's comment shape; the JS-style COMMENT regex
# reads the sources. Same question, one stripper per corpus.
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


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
        for match in COMMENT.finditer(content):
            blank(start + 3 + match.start(), start + 3 + match.end())
    return "".join(out)

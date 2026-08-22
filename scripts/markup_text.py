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

`parse_failures` is the one JUDGMENT this module makes, and it belongs here
because it is a precondition on the READING, not a question about markup: see
its own docstring for the day every instrument in this repository read two
unparseable rule files as « no violation ».
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "frontend" / "maquette" / "design" / "src"

# The anchor arm's corpus: the harness rules, the same `*.py` set
# `classify-rule-anchors.py` reads. The two readers must share the corpus,
# or « both find zero class anchors » is two answers to two questions. The
# part arm reads the same set, from the other end.
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

# THE NAMING ATTRIBUTES — the `data-*` whose VALUES are names someone
# chose, not data the app stores or displays. `card/overview`,
# `library/body`, `primary`, `danger`, `left` are vocabulary; a page id, a
# route, a title and a folder are addresses.
#
# The list is HERE, in one place, because two guards ask two questions of
# exactly the same set and a second copy is a second thing to move: the
# markup guard holds « every value a rule selects is emitted somewhere »
# (ARM 3) and the French guard holds « every value is built from words
# this codebase speaks ». `data-tone` was coined by one wave, selected
# with a value at ten harness call sites, and was in neither list — so a
# renamed tone left ten rules selecting nothing with no static refusal,
# and a French tone value passed the French gate.
#
# THE SCOPE IS DELIBERATE AND IT WAS MEASURED. Widening ARM 3 to EVERY
# valued `data-*` reports 44 selections as unemitted, and every one of
# them is a false finding: `data-page`, `data-lens`, `data-acqtab` and
# their kind are emitted from a COMPUTED expression, which names no
# literal for the arm to compare. Those are addresses, and an address is
# not this list's business.
NAMING_ATTRIBUTES = ("data-part", "data-region", "data-tone",
                     "data-action", "data-side")


def parse_failures(paths: Iterable[Path]) -> list[tuple[Path, int, str]]:
    """Returns every file the Python parser refuses, with the parser's word.

    THE DEFECT CLASS, AND IT IS THIS GUARD'S OWN. A rewrite substituted
    `[data-part="suggestion/wrap"]` into selectors hosted in single-line
    DOUBLE-quoted Python strings: the raw `"` closed the literal, and
    `harness/inter.py` and `harness/mouse.py` STOPPED PARSING. Every
    instrument then read them and reported no violation — the four arms
    exited 0, the anchor arm's baseline regeneration (a mode since deleted)
    wrote happily, `classify-rule-anchors.py` counted. Only the
    sixteen-minute pass that RUNS the rules would have fallen.

    Nothing raised because nothing here parses. The arms read the harness as
    RAW TEXT, and text has no syntax to be wrong. `comment_masked` tokenizes,
    and `tokenize` does not raise on a stray quote either — it re-lexes what
    follows as if it were code, and its documented fallback swallows what
    little it does refuse. So a reader keeps going over a file the
    interpreter cannot load and reports a count one short, in silence. That
    is why the question is asked ONCE, ahead of the readers, by the only
    thing that answers it honestly: the parser.

    Args:
        paths: The files to parse — the harness corpus.

    Returns:
        `(path, line, message)` per refused file, in the order given. The
        line is the parser's, or 0 when it names none; the message is the
        `SyntaxError`'s own, never a rewording of it. A file that cannot be
        read at all is refused the same way, for the same reason: an
        unreadable file is one no arm measures.
    """
    found: list[tuple[Path, int, str]] = []
    for path in paths:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as err:
            found.append((path, err.lineno or 0, err.msg))
        except (OSError, UnicodeDecodeError, ValueError) as err:
            found.append((path, 0, str(err)))
    return found


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


def strip_braced_spans(selector: str) -> str | None:
    """Removes every `{...}` interpolation, `${...}` included.

    A selector the harness BUILDS at run time spells its computed parts as
    braces — a Python f-string's `{key}`, a JS template's `${key}` — and
    those braces are outside the selector alphabet, so a candidate
    carrying one used to be dropped whole. The span is an OPAQUE token
    instead: it does not end the selector, and it contributes no name
    either, because the readers judge the text that remains and a
    computed class is a name nothing knows at rest.

    AN INTERPOLATION IS BALANCED, and that is the refusal this returns
    None for. A lone `{` says the string is stylesheet text (`.cov{-webkit-
    line-clamp:`) or a rule opening (`.splashbar {`) — neither is a
    selection, and both carry class tokens that would otherwise be
    reported as anchors nobody can migrate.

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
    question about the SYNTAX is asked of what sits outside them.

    Args:
        selector: One candidate string.

    Returns:
        The text outside every `[...]` block, concatenated. An unclosed
        `[` swallows the rest, which is what an unclosed block does to a
        selector too.
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


def attribute_of(dataset_name: str) -> str:
    """Returns the attribute spelling of a `dataset` property name.

    `element.dataset.noPoster` is `data-no-poster`. The two spellings are
    the same name, and comparing them as written would have let a value
    READ in JavaScript pass for an attribute nothing reads.

    Args:
        dataset_name: The property name as written after `.dataset.`.

    Returns:
        The `data-` attribute's name, without its prefix.
    """
    return re.sub(r"([A-Z])", lambda m: "-" + m.group(1).lower(), dataset_name)

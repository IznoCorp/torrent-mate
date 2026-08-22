"""The scanners the no-French guard reads sources with.

SPLIT OUT OF `check-no-french.py` alongside the lexicon: with both moved, the
arms file sits under the 1 000-line hard ceiling that CLAUDE.md sets and that
`check-module-size.py` now enforces over `scripts/` as well as the package.

These decide WHERE the text is — which bytes are a string, a declaration, a
comment — and never whether it is French. The questions live with the arms.
"""

from __future__ import annotations

import ast
import io
import re
import token as token_kinds
import tokenize

def python_string_literals(source: str) -> list[tuple[int, str]]:
    """Returns every string literal a Python module holds, with its line.

    Args:
        source: The module's text.

    Returns:
        (line number, literal text) pairs, docstrings included — a docstring is
        documentation, which this repository writes in English too.
    """
    literals: list[tuple[int, str]] = []
    kinds = {token_kinds.STRING}
    # 3.12 tokenises an f-string into START / MIDDLE / END; MIDDLE carries the
    # literal halves, which is where a French sentence would sit.
    if hasattr(token_kinds, "FSTRING_MIDDLE"):
        kinds.add(token_kinds.FSTRING_MIDDLE)
    for found in tokenize.generate_tokens(io.StringIO(source).readline):
        if found.type in kinds:
            literals.append((found.start[0], found.string))
    return literals


def script_string_literals(source: str) -> list[tuple[int, str]]:
    """Returns every string or template literal a TS/JS source holds.

    Comments are skipped, and a template literal is taken whole (its `${…}`
    holes included) — conservative in the only direction that matters: a French
    sentence inside a template is still seen.

    Known limit, and its failure mode: a regular-expression literal carrying a
    quote character (`/['"]/`) would open a string this scanner never closes
    where it should. There is none in scope today (three regex literals, none
    with a quote), and the day one appears the scanner mis-reads a span and
    reports a violation nobody can explain — LOUD, not silent, which is the
    only acceptable way for a guardrail to be wrong.

    Args:
        source: The module's text.

    Returns:
        (line number, literal text) pairs.
    """
    literals: list[tuple[int, str]] = []
    index, line, length = 0, 1, len(source)
    while index < length:
        char = source[index]
        if char == "\n":
            line += 1
            index += 1
        elif source.startswith("//", index):
            index = source.find("\n", index)
            if index < 0:
                break
        elif source.startswith("/*", index):
            end = source.find("*/", index + 2)
            end = length if end < 0 else end + 2
            line += source.count("\n", index, end)
            index = end
        elif char in "'\"`":
            start, start_line, index = index, line, index + 1
            while index < length:
                if source[index] == "\\":
                    index += 2
                    continue
                if source[index] == "\n":
                    line += 1
                    # An unterminated quote is a syntax error the typecheck
                    # catches; here it must not swallow the rest of the file.
                    if char != "`":
                        break
                if source[index] == char:
                    index += 1
                    break
                index += 1
            literals.append((start_line, source[start:index]))
        else:
            index += 1
    return literals


# A TypeScript DECLARATION — the keyword that introduces a name, and the name.
# Two arms read it: arm 2 asks whether the name is a word this codebase speaks,
# arm 10 asks a dictionary whether it is French. One reader, so the two arms
# cannot end up reading two different populations.
TS_DECLARATION = re.compile(
    r"\b(?:const|let|var|function|class|interface|type|enum)\s+"
    # french-ok: a Latin-1 letter RANGE, not a word
    r"(?P<name>[A-Za-z_$][\w$À-ɏ]*)")


def python_declarations(source: str) -> list[tuple[str, int]]:
    """Returns every name a Python module DECLARES, with its line.

    Read through `ast` rather than by regex: a declaration is a syntactic fact,
    and the alternative flags every mention of a name in a comment or a string.
    """
    names: list[tuple[str, int]] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append((node.name, node.lineno))
            if not isinstance(node, ast.ClassDef):
                args = node.args
                for arg in (args.posonlyargs + args.args + args.kwonlyargs
                            + [a for a in (args.vararg, args.kwarg) if a]):
                    names.append((arg.arg, arg.lineno))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.append((node.id, node.lineno))
        elif isinstance(node, ast.arg):
            names.append((node.arg, node.lineno))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.asname:
                    names.append((alias.asname, node.lineno))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.append((node.name, node.lineno))
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            # `self.dossier = …` is how a French field name usually arrives.
            names.append((node.attr, node.lineno))
        elif isinstance(node, ast.keyword) and node.arg:
            names.append((node.arg, getattr(node, "lineno", 0) or 0))
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            names.append((node.name, node.lineno))
    return names


def code_only(source: str) -> str:
    """Returns the source with comments and string bodies blanked out.

    A name extractor that reads prose invents declarations: « the type this
    module exports » yields `this`, and eighty-four such phantoms buried the
    four real findings on the first run. Newlines are preserved so a line
    number still means what it says.

    Args:
        source: JavaScript or TypeScript.

    Returns:
        The same length of text, with everything that is not code replaced by
        spaces.
    """
    out, index, size = [], 0, len(source)
    in_line = in_block = in_string = False
    quote = ""
    while index < size:
        char = source[index]
        if in_line:
            if char == "\n":
                in_line = False
                out.append(char)
            else:
                out.append(" ")
            index += 1
        elif in_block:
            if source.startswith("*/", index):
                in_block = False
                out.append("  ")
                index += 2
            else:
                out.append("\n" if char == "\n" else " ")
                index += 1
        elif in_string:
            if char == "\\":
                out.append("  ")
                index += 2
                continue
            if char == quote:
                in_string = False
                out.append(char)
            else:
                out.append("\n" if char == "\n" else " ")
            index += 1
        elif source.startswith("//", index):
            in_line = True
            out.append("  ")
            index += 2
        elif source.startswith("/*", index):
            in_block = True
            out.append("  ")
            index += 2
        elif char in "\"'`":
            in_string = True
            quote = char
            out.append(char)
            index += 1
        else:
            out.append(char)
            index += 1
    return "".join(out)


def inside_quotes(line: str, index: int) -> bool:
    """Returns True when a position sits inside a quoted span of the line.

    Args:
        line: The source line.
        index: The position to judge.

    Returns:
        True when an odd number of unescaped quotes of some kind precedes it.
    """
    for quote in "\'\"`":
        opened, escaped = 0, False
        for char in line[:index]:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                opened += 1
        if opened % 2:
            return True
    return False

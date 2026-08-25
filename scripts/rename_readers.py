"""Who decides which byte of a file is CODE — the readers, and nothing else.

WHY IT IS A FILE. `rename-identifiers.py` reached 829 non-blank lines against a
soft ceiling of 800 and a hard one of 1 000 that exits 1 (B-070), and it is the
tool every rename in this repository goes through. The split follows a SUBJECT:
everything here answers one question — given a file, which spans are code, which
are strings, which are comments — and nothing here rewrites a single character.
The half that stayed behind is the half that APPLIES a mapping to the spans
this one hands it.

That question has its own history, and it is the tool's most expensive one. A
hand-written scanner is a list of the forms someone thought of, and the two it
had not thought of each rewrote INTERFACE COPY in silence — a regex literal
holding an apostrophe, and JSX text, which wears no quote at all. So for
everything TypeScript can parse the COMPILER answers, through
`source-spans.mjs`; `regions()` stays for Python, where the identifiers live
inside `page.evaluate` strings and no parser can help; and `quoted_spans()` is
the last resort for JSON, CSS and HTML, which have no parser here at all.

Imported by `rename-identifiers.py` and by nothing else.
"""
import bisect
import io
import pathlib
import re
import subprocess
import sys
import tokenize

SPAN_TOOL = pathlib.Path(__file__).with_name("source-spans.mjs")


def utf16_offsets(text):
    """Returns a function turning a UTF-16 offset into a Python index.

    JavaScript counts a string in UTF-16 CODE UNITS and Python in code points,
    so an emoji — two units, one character — shifts every offset after it by
    one. `design/src/engine/legacy.js` holds four of them, the first at
    character 88 847, and every span the parser reported past that point landed
    four characters late: a string literal was cut in half, `"en_attente"`
    arriving as `"en_` in one chunk and `attente"` in the next, so a rename
    matched neither. It MISSED, silently, which is the safe half of this bug —
    the other half, had the drift gone the other way, is renaming inside a
    string.

    Args:
        text: The file's contents, as Python sees them.

    Returns:
        A callable mapping a UTF-16 offset to a Python index.
    """
    wide = [index for index, char in enumerate(text) if ord(char) > 0xFFFF]
    if not wide:
        return lambda offset: offset
    # Where each wide character sits once the earlier ones have each taken an
    # extra unit of their own.
    starts = [index + rank for rank, index in enumerate(wide)]
    return lambda offset: offset - bisect.bisect_right(starts, offset)


def python_spans(text):
    """Returns the regions of a Python source, read by Python's tokeniser.

    `regions()` below is a JavaScript scanner: it knows `//` and `/* */` and
    nothing about `#`. A French comment holding an apostrophe — « l'ajout » —
    therefore opened a string that never closed, and every literal after it in
    the file read as code. It is the same failure the regex literal caused on
    the JavaScript side, in the other language, and it was found the same way:
    a value pass that changed nothing at all in a file full of the values.

    Args:
        text: The Python source.

    Returns:
        The (kind, start, end) covering the whole text, gaps filled with `code`.
    """
    reported = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type not in {tokenize.STRING, tokenize.COMMENT}:
                continue
            kind = "string" if token.type == tokenize.STRING else "comment"
            reported.append((kind, offset_of(text, *token.start),
                             offset_of(text, *token.end)))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # A file the tokeniser cannot read is left whole rather than guessed at.
        return [("code", 0, len(text))]
    out, cursor = [], 0
    for kind, first, last in reported:
        if first < cursor:
            continue
        if first > cursor:
            out.append(("code", cursor, first))
        out.append((kind, first, last))
        cursor = last
    if cursor < len(text):
        out.append(("code", cursor, len(text)))
    return out


def offset_of(text, line, column):
    """Turns a (1-based line, 0-based column) pair into a character index."""
    start = 0
    for _ in range(line - 1):
        start = text.index("\n", start) + 1
    return start + column


def compiler_spans(path, text):
    """Returns the regions of `path` as TypeScript's own parser sees them.

    `regions()` below is a hand-written scanner, and a hand-written scanner is
    a list of the forms someone thought of. Two it had not thought of each cost
    a corruption: a regex literal holding an apostrophe desynchronised it for
    the rest of the file, and JSX text — `<p>En attente de torrent</p>` — wears
    no quote at all, so it read as code and a rename rewrote interface copy.

    The compiler already ships with this frontend and has no such list. Its
    answer is used for everything it can parse; `regions()` stays for Python,
    where the identifiers live inside `page.evaluate` strings.

    Args:
        path: The file, used to pick the script kind and to read the spans.
        text: Its contents, already read.

    Returns:
        The same (kind, start, end) covering `regions()` returns, gaps filled
        with `code`.

    Raises:
        SystemExit: When the parser cannot be run — never a silent fallback,
            since the fallback IS the corruption this exists to stop.
    """
    done = subprocess.run(["node", str(SPAN_TOOL), str(path)],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"cannot parse {path}: {done.stderr.strip()}")
    into_index = utf16_offsets(text)
    reported = []
    for line in done.stdout.splitlines():
        if not line.strip():
            continue
        kind, a, b = line.split()
        reported.append(("string" if kind == "protected" else "comment",
                         into_index(int(a)), into_index(int(b))))
    out, cursor = [], 0
    for kind, a, b in reported:
        if a < cursor:          # a comment inside a template, already covered
            continue
        if a > cursor:
            out.append(("code", cursor, a))
        out.append((kind, a, b))
        cursor = b
    if cursor < len(text):
        out.append(("code", cursor, len(text)))
    return out


def protected_text_of(path, text):
    """Returns the contents of every span a rename must leave alone.

    The parser is chosen by the file's own language. Reading a `.py` back
    through the TypeScript parser was defect #2 resurrected inside the
    verifier: TS lexes `\"\"\"` as an empty string followed by a quote, and the
    apostrophe in `# l'apostrophe` as an opening quote, so every Python file
    disagreed with itself and the rename aborted — 52 harness files out of 52,
    mid-walk, leaving the tree half renamed.

    Args:
        path: The file, whose suffix names the language.
        text: The source to read back.

    Returns:
        The text of every span a rename must leave untouched.
    """
    spans = (python_spans(text) if path.suffix == ".py"
             else compiler_spans(path, text))
    return [text[s:e] for kind, s, e in spans if kind == "string"]


def _regex_starts_here(text, i):
    """Says whether the slash at `i` opens a regex literal rather than divides.

    JavaScript cannot be lexed without this question, and the answer is the
    standard one: a slash divides only when it follows something a VALUE can
    end with — a name, a number, a closing bracket. Everywhere else it opens a
    pattern. `//` and `/*` are handled before this is ever reached.

    Args:
        text: The whole source.
        i: Index of the slash.

    Returns:
        True when the slash opens a regex literal.
    """
    j = i - 1
    while j >= 0 and text[j] in " \t\n\r":
        j -= 1
    if j < 0:
        return True
    previous = text[j]
    if previous in ")]}" or previous.isalnum() or previous in "_$":
        # `return /x/` and `typeof /x/` end with a name yet still open a regex,
        # so the few keywords a pattern may follow are read back explicitly.
        k = j
        while k >= 0 and (text[k].isalnum() or text[k] in "_$"):
            k -= 1
        return text[k + 1 : j + 1] in {
            "return", "typeof", "case", "in", "of", "delete", "void",
            "instanceof", "new", "do", "else", "yield", "await",
        }
    return True


def regions(text):
    """Returns (kind, start, end) spans covering the whole text."""
    out, i, n, mark = [], 0, len(text), 0
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(("code", mark, i)); out.append(("comment", i, j)); mark = i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(("code", mark, i)); out.append(("comment", i, j)); mark = i = j
        elif c == "/" and _regex_starts_here(text, i):
            # A TENTH form, and the one that cost the most: a regex literal
            # holding a quote — `/n'est plus cherch/i`. The apostrophe opened
            # a string that never closed, and every string after it in the file
            # was read as CODE, so the renamer rewrote INTERFACE COPY silently:
            # « En attente de torrent » became « En pendingDecision de torrent »
            # and the file still parsed. A regex is scanned as its own span,
            # exactly as a string is, and its own quotes stay inert.
            j = i + 1
            in_class = False
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "[":
                    in_class = True
                elif text[j] == "]":
                    in_class = False
                elif text[j] == "\n":
                    break
                elif text[j] == "/" and not in_class:
                    break
                j += 1
            end = min(j + 1, n)
            out.append(("code", mark, i))
            out.append(("string", i, end))
            mark = i = end
        elif c in "\"'`":
            out.append(("code", mark, i))
            quote, j = c, i + 1
            piece = i
            while j < n:
                if text[j] == "\\": j += 2; continue
                if quote == "`" and text.startswith("${", j):
                    # An interpolation is CODE wearing a string's clothes, and
                    # it is where most of this engine's markup reads its state.
                    depth, k = 1, j + 2
                    while k < n and depth:
                        if text[k] == "{": depth += 1
                        elif text[k] == "}": depth -= 1
                        k += 1
                    # The delimiters belong to the STRING side, or reassembly
                    # silently eats them and the template stops interpolating.
                    # An interpolation is code — and code CONTAINS STRINGS.
                    # Emitting it flat renamed `mode === "clair"` to
                    # `mode === "light"`: a data value, silently, inside what
                    # looked like a safe code region. It is scanned in its own
                    # right, and its own strings are protected.
                    out.append(("string", piece, j + 2))
                    for kind, a, b in regions(text[j + 2 : k - 1]):
                        out.append((kind, j + 2 + a, j + 2 + b))
                    piece = k - 1
                    j = k
                    continue
                if text[j] == quote: break
                j += 1
            end = min(j + 1, n)
            out.append(("string", piece, end))
            mark = i = end
        else:
            i += 1
    out.append(("code", mark, n))
    return [(k, s, e) for k, s, e in out if e > s]


# `"…"` and, in JSON and CSS, `'…'` — escapes included. JSON, CSS and HTML have
# no parser here.
QUOTED_RUN = re.compile(r"""(?P<q>["'])(?:\\.|(?!(?P=q))[^\\])*(?P=q)""", re.S)
# HTML gets DOUBLE QUOTES ONLY. An apostrophe is ordinary text there — this
# interface is written in French, so its markup is full of them — and reading
# one as an opening quote swallowed everything up to the next apostrophe:
# `<p>L'ajout</p><div data-s="en_attente">C'est` became one 93 000-character
# "string" on `refonte.html`, and the attribute value inside it was silently
# skipped. The mode reported success having changed nothing, which is the
# no-op-reported-as-success this function was written to end.
QUOTED_RUN_HTML = re.compile(r'"(?:\\.|[^"\\])*"', re.S)


def quoted_spans(text, html=False):
    """Splits a file with no parser into its quoted runs and the rest.

    JSON, CSS and HTML reach the value pass without a parser. They used to be
    handed a single `("string", 0, len(text))` span covering the WHOLE file,
    which then failed the id test on its first brace or newline — so the mode
    was a guaranteed no-op on the three file types it was extended to cover,
    and reported success while touching nothing.

    Args:
        text: The source.
        html: True for HTML, where only DOUBLE quotes delimit a value and an
            apostrophe is ordinary text.

    Returns:
        The regions, as `(kind, start, end)` with kind `"string"` or `"code"`.
    """
    out, mark = [], 0
    for match in (QUOTED_RUN_HTML if html else QUOTED_RUN).finditer(text):
        if match.start() > mark:
            out.append(("code", mark, match.start()))
        out.append(("string", match.start(), match.end()))
        mark = match.end()
    out.append(("code", mark, len(text)))
    return [(kind, s, e) for kind, s, e in out if e > s]

"""Renames identifiers in JavaScript/TypeScript and in the harness, and touches
nothing else.

Three kinds of text look alike and are not alike, and each has cost a revert:

  CODE     — an identifier. Renamed.
  COMMENT  — prose that may QUOTE an identifier in backticks. The backticked
             mention is renamed; the prose word is not.
  STRING   — interface copy, a data value, a form field name, a selector. NEVER
             renamed here: `un identifiant` is what a reader sees, and
             `name="identifiant"` is a contract with a server that reads it.
             A `${…}` interpolation inside a template is CODE and is renamed.

Property keys are not identifiers either: `etat:` in a type and `.etat` on an
object are one contract with two ends, and moving one end alone is how a rename
becomes a defect. They are passed in separately, deliberately.

WHAT `--values` IS FOR, AND WHY IT IS NOT THE DEFAULT. Everything above
protects DATA from a rename. `--values` moves the data itself — the acquisition
state vocabulary was a set of French words that is a string in the backend, a
string over the API, a class name in the stylesheet and a key in the fixture,
and the operator ruled that the data's own words are English too. It renames a
WHOLE quoted value and the identifiers built on one, and it still never touches
prose.

WHAT MAKES IT SAFE over a tree full of French interface copy is the boundary
rule, not care: a state token carries an UNDERSCORE, and the sentence a reader
sees does not. The two cannot be confused, in either direction. A value that is
an ordinary French word on its own — with no underscore to be told apart by —
is passed through `--whole=`, and then only its whole quoted form may move: a
bare word inside a sentence is left exactly where it is.

This mode is also the one that steps around the read-back proof, because
changing a string is precisely what it is for. Its own proof is the boundary
rule above, exercised on every shape in `tests/scripts/`.

WHO DECIDES WHICH IS WHICH. For everything TypeScript can parse — `.ts`, `.tsx`,
`.js`, `.jsx`, `.mjs` — the compiler does, through `source-spans.mjs`. The
hand-written scanner below stays for Python, where the identifiers live inside
`page.evaluate` strings and no parser can help. That split is not a preference:
a hand-written scanner is a list of the forms someone thought of, and the two it
had not thought of each rewrote INTERFACE COPY in silence. A regex literal
holding an APOSTROPHE — this interface is written in French, so its patterns
are full of them — opened a string that never closed, so every literal after it
in the file read as code; and JSX text wears no quote at all, so the sentence
between a `<p>` and its closing tag read as code too.

And the proof of it is taken on what was WRITTEN, not on what was intended: the
file is read back through the parser and every string, template piece, regex and
JSX text must still say exactly what it said. The older proof — an empty table
must round-trip byte for byte — cannot show this, because a misclassified span
reassembles byte for byte as happily as a correct one.
"""
import bisect
import collections
import io
import json
import pathlib
import re
import subprocess
import sys
import tokenize

SPAN_TOOL = pathlib.Path(__file__).with_name("source-spans.mjs")
COMPILED = {".ts", ".tsx", ".js", ".jsx", ".mjs"}


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

# A template HEAD ends on its separator — `` `profil:${…}` `` — and a tail
# starts on one, so a dangling separator is part of the shape.
ID_TOKEN = re.compile(r"^[-_:.]?[a-z0-9]+(?:[-_:.][a-z0-9]+)*[-_:.]?$")

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


# A CSS custom property is not an identifier any parser here can see, and the
# word-boundary rule cannot reach one: `\b` before `--card` needs a word
# character to its left, and `-` is not one. So the rename tool renamed zero
# files when asked to move `--card`, silently — the shape of failure this
# repository has paid for twice, and the reason this mode exists rather than
# the ad-hoc regex CLAUDE.md forbids.
#
# THE BOUNDARY RULE IS THE FORM, NOT THE WORD. A custom property appears in
# exactly three shapes, and each is unmistakable:
#
#   --name:            a declaration
#   var(--name)        a use, with or without a fallback
#   "--name"           the whole of a quoted string, which is how JavaScript
#                      and the harness reach one (`setProperty`, `getPropertyValue`)
#
# Anything else — the name inside prose, inside a longer name, inside a
# sentence a reader sees — is left exactly where it is. That is a STRONGER
# guarantee than the word-boundary rule the identifier mode uses, not a weaker
# one: it moves a name only where the name is being used as a property.
#
# `(?![\w-])` on every form is what keeps `--card` out of `--card-x`.
def custom_property_forms(name):
    """Returns the three patterns a custom property may legitimately wear.

    Args:
        name: The property, leading dashes included.

    Returns:
        A list of compiled patterns, each with the property in group 1 and the
        surrounding form preserved in the rest of the match.
    """
    quoted = re.escape(name)
    return [
        # A declaration: the name, then optional space, then a colon.
        re.compile(rf"({quoted})(?![\w-])(\s*:)"),
        # A use: `var(` then optional space then the name.
        re.compile(rf"(var\(\s*)({quoted})(?![\w-])"),
        # A whole quoted string, in either quote, and nothing else inside it.
        re.compile(rf"([\"\'])({quoted})(?![\w-])(\1)"),
    ]


def apply_custom_properties(text, mapping):
    """Renames CSS custom properties, and only where one is being used as one.

    Args:
        text: The source.
        mapping: Old property name → new property name, dashes included.

    Returns:
        The source with the properties moved.
    """
    for source, target in mapping.items():
        if source == target:
            continue
        declaration, use, quoted = custom_property_forms(source)
        text = declaration.sub(lambda m: target + m.group(2), text)
        text = use.sub(lambda m: m.group(1) + target, text)
        text = quoted.sub(lambda m: m.group(1) + target + m.group(3), text)
    return text


def apply_values(text, mapping, spans=None, whole_only=(), inner_words=False):
    """Renames DATA values: whole quoted tokens, and identifiers built on them.

    Args:
        text: The source.
        mapping: French value → English value.
        spans: The parser's regions, when it could read the file.
        whole_only: Values that must move ONLY as a whole quoted string,
            because they are ordinary French words elsewhere.
        inner_words: Allow substitution INSIDE a multi-word string. Off by
            default: a multi-word body is prose until proven otherwise, and
            rewriting one word of a sentence is how « conforme au profil »
            became « conforme au profile » across 429 lines.

    Returns:
        The source with the values moved.
    """
    regions_ = spans if spans is not None else regions(text)
    pieces = []
    for kind, first, last in regions_:
        chunk = text[first:last]
        # ONLY strings, and only strings that are IDS. A value is a string
        # literal — never a bare word in code — and the thing it must never be
        # mistaken for is a bare word in a SENTENCE, which is also a string.
        #
        # The discriminator is the whole string rather than the word inside it:
        # « Aucune release conforme au profil depuis l'ajout. » and "profil" both
        # hold the word with spaces around it, and no rule reading the word's
        # surroundings can tell them apart. A capital, an apostrophe, a full
        # stop, an accent — copy has them and an id does not.
        if kind != "string":
            pieces.append(chunk)
            continue
        # A template piece wears `${` and `}` as well as its backtick, and the
        # id is what sits between them.
        head = re.match(r"^(['\"`]|\})", chunk)
        tail = re.search(r"(['\"`]|\$\{)$", chunk)
        opening = head.group(0) if head else ""
        closing = tail.group(0) if tail else ""
        body_ = chunk[len(opening):len(chunk) - len(closing)]
        if not body_ or not all(ID_TOKEN.match(piece) for piece in body_.split(" ")):
            pieces.append(chunk)
            continue
        # A body that holds a SPACE is several words, and several lowercase
        # unaccented words are as often a sentence as a class list: « page
        # suivante » and « trier par nom » pass the token test word by word.
        # So a multi-word body moves only as a WHOLE — `"card open"` renamed
        # to `"card open"` — and substituting inside one is opt-in
        # (`--inner-words`), never the default. This is the rule the docstring
        # above always claimed and the code never applied: the discriminator
        # is the whole string, not the word inside it.
        multiword = " " in body_
        for source_value, target in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
            # `whole_only` values are ordinary words elsewhere, so they move
            # only when they ARE the whole body.
            if source_value in whole_only or (multiword and not inner_words):
                if body_ == source_value:
                    body_ = target
                continue
            body_ = re.sub(
                rf"(?<![A-Za-z0-9]){re.escape(source_value)}(?![A-Za-z0-9])",
                target, body_)
        pieces.append(opening + body_ + closing)
    return "".join(pieces)


def apply(text, mapping, in_python=False, properties=False, spans=None):
    """Renames in code regions, and backticked mentions in comment regions.

    With `properties`, the name is renamed as a PROPERTY as well — member
    access, object key, type member, indexed access. That is all-or-nothing on
    purpose: a property and its accesses are one contract with several ends,
    and moving one end alone is how a rename becomes a defect. It stays off by
    default because most names are only ever bindings.
    """
    if in_python:
        # A rule drives the engine from inside a `page.evaluate` STRING, so for
        # Python the strings are where the identifiers live. Three shapes there
        # are NOT identifiers, and each cost a red suite:
        #
        #   reglages-modifie      a STATE ID — a hyphen on either side means the
        #                         word belongs to a name the engine looks up in
        #                         a table, not to a binding it evaluates.
        #   [name=identifiant]    a SELECTOR naming markup.
        #   window.PLANIFICATEURS a member, which the dot rule would skip —
        #                         except this one IS the published identifier,
        #                         and skipping it left the harness asking the
        #                         engine for a name it no longer publishes.
        #   "PLANIFICATEURS"      a whole quoted value — and here that IS an
        #                         identifier: R67 names the engine constant it
        #                         reads. A whole quoted value is otherwise DATA
        #                         (`"clair"` is a theme, `"maintenant"` a tab),
        #                         so the two are told apart by CASE: this app
        #                         writes its data values in lower case and its
        #                         constants in upper.
        # A BRACKETED SELECTOR IS DATA, all of it. `[data-go=profil]` names an
        # attribute and the VALUE it must carry — a page id — and renaming the
        # value made a rule look for a control the interface never emits. The
        # spans are lifted out, the rename runs, and they are put back.
        held = []
        def hold(match):
            inside = match.group(0)[1:-1]
            # A THIRTEENTH form, and the mirror of the twelfth: in Python the
            # brackets are also a LIST. Holding every one of them to protect
            # `[data-go=profil]` left `[center - radius, center + radius]`
            # standing with its French names — a rename half done, in the one
            # file nothing else watches. A selector carries no spaces and
            # names an attribute; a list is spelled out.
            if " " in inside or not (inside.startswith("data-") or "=" in inside):
                return match.group(0)
            held.append(match.group(0))
            return f"\x00{len(held) - 1}\x00"
        # PROSE IS HELD OUT FIRST, and the order is load-bearing: the
        # bracket pass below rewrites the text through `re.sub`, and the
        # spans were measured on the ORIGINAL source. Holding prose after
        # it sliced at stale offsets and destroyed the very sentences this
        # is meant to protect.
        #
        # And this was the hole it closes. The module docstring
        # above says a comment's prose word is never renamed — and the Python
        # path ignored the spans entirely and substituted over the whole file,
        # so "Le suivi est mis a jour ici" became "Le follow est mis a jour ici"
        # in a docstring, in a comment and in a sentence-shaped literal. That is
        # the exact defect this tool exists to prevent, in the one language
        # where nothing was watching. The spans the caller already computed say
        # where prose lives; they are lifted out the way a selector is, and put
        # back at the end.
        if spans is not None:
            for kind, first, last in reversed(spans):
                body = text[first:last]
                if kind == "comment" or (kind == "string" and is_prose(body)):
                    held.append(body)
                    text = text[:first] + chr(0) + str(len(held) - 1) + chr(0) + text[last:]

        text = re.sub(r"\[[^\[\]\n]*\]", hold, text)

        for fr, en in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
            text = re.sub(r"\bwindow\." + re.escape(fr) + r"\b", "window." + en, text)
            if fr.upper() == fr:
                text = re.sub(r"(['\"])" + re.escape(fr) + r"\1", r"\g<1>" + en + r"\1", text)
            #   "ajout:suivi"         a COMPOSED data key. A colon composes one
            #                         exactly as a hyphen does, and renaming the
            #                         half after it rewrote a rule's own EXPECTED
            #                         value — the hold then measured the app
            #                         against a key the app never produces.
            #   "/profil/{titre}"     a ROUTE PATH. A slash delimits an address
            #                         segment exactly as a hyphen and a colon
            #                         compose a key — and rewriting one changed
            #                         a rule's EXPECTED address, so the hold
            #                         waited for a URL the app never navigates to.
            lookbehind = (r"(?<![-:/\w$'\"])" if properties
                          else r"(?<![-:/.\w$'\"])")
            text = re.sub(lookbehind + re.escape(fr) + r"\b(?![-\w])", en, text)
        text = re.sub(r"\x00(\d+)\x00", lambda m: held[int(m.group(1))], text)
        return text
    pieces, count = [], 0

    for kind, s, e in (spans if spans is not None else regions(text)):
        chunk = text[s:e]
        if kind == "code":
            for fr, en in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
                if properties:
                    # `.name`, `name:`, and the binding itself — every end.
                    chunk = re.sub(rf"(?<![\w$]){re.escape(fr)}\b", en, chunk)
                else:
                    # A shorthand `{ etat }` is BOTH ends written once — the key
                    # the object emits and the binding it reads — so renaming it
                    # moves the wire contract while every `x.etat` stays.
                    #
                    # EXPANDING IT AUTOMATICALLY WAS WORSE. `{ etat }` and JSX's
                    # `{body}` are the same three characters to a regex, and the
                    # expansion rewrote a pre-existing `{body}` expression
                    # container into `{corps: body}` in a file that did not even
                    # contain the source name. Only a parser can tell an object
                    # shorthand from a JSX expression, and this pass has spans,
                    # not node kinds.
                    #
                    # So the UNAMBIGUOUS case — a shorthand inside a list, where
                    # a JSX container cannot appear — is REFUSED, and the caller
                    # is told which mode owns it. A lone `{etat}` keeps being
                    # renamed: in JSX that is exactly right, and in a one-key
                    # object `--properties` is the mode that moves both ends.
                    ambiguous = re.search(
                        rf"\{{[^{{}}\n]*,\s*{re.escape(fr)}\s*[,}}]"
                        rf"|\{{\s*{re.escape(fr)}\s*,[^{{}}\n]*\}}", chunk)
                    if ambiguous:
                        raise SystemExit(
                            f"{fr!r} appears as a SHORTHAND PROPERTY "
                            f"({ambiguous.group(0).strip()[:48]}) — that is one "
                            "name for the key an object emits AND the binding it "
                            "reads. Renaming it here would move the key while "
                            "every reader stayed. Use --properties, which moves "
                            "both ends. Nothing written, in any file.")
                    # A TWELFTH form: `...` is a SPREAD, not a member access,
                    # and the lookbehind that protects `x.name` read the last
                    # of its three dots the same way. `{ ...REGLEE }` was left
                    # standing while every other mention moved — a half-rename,
                    # silent, and only the type-checker downstream said so.
                    #
                    # A FOURTEENTH form, and the one this mode's own premise
                    # denies: `{ etat }` and `{ etat: 2 }` are PROPERTY
                    # positions. Renaming them without `--properties` moved the
                    # emitted key while every `x.etat` that reads it stayed —
                    # code that still parses, a read-back proof that only
                    # compares strings and so says nothing, and exit 0. A
                    # shorthand is both ends of the contract written once, so
                    # it is skipped here and belongs to `--properties`.
                    chunk = re.sub(
                        rf"(?:(?<=\.\.\.)|(?<![.\w$])){re.escape(fr)}\b"
                        # not `name:` — an object key or a type member
                        rf"(?!\s*:)",
                        en, chunk)
        elif kind == "comment":
            for fr, en in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
                chunk = re.sub(rf"`{re.escape(fr)}\b", "`" + en, chunk)
                chunk = re.sub(rf"`{re.escape(fr)}\(", "`" + en + "(", chunk)
        pieces.append(chunk)
    return "".join(pieces)


PROSE_WORD = re.compile(r"[A-Za-z\u00c0-\u00ff]{2,}")
CODE_MARK = re.compile(r"[(){}\[\]=><;]|=>|\$\{|\bwindow\b|\bdocument\b")


def is_prose(body):
    """Says whether a Python string literal is a SENTENCE rather than code.

    The harness drives the engine from inside `page.evaluate` strings, so a
    Python string there is usually JavaScript and its identifiers must move. A
    docstring, a comment and an ordinary message are the opposite: they are
    prose, and a rename inside one is the corruption this tool exists to stop.

    A triple-quoted literal is prose by construction here — the harness writes
    its evaluate strings on one line. Otherwise the discriminator is the one the
    rest of this file already uses: code wears punctuation a sentence does not.

    Args:
        body: The literal, quotes included.

    Returns:
        True when the literal reads as a sentence and must be left alone.
    """
    if body.lstrip("rbfuRBFU").startswith(('"""', "'''")):
        return True
    if CODE_MARK.search(body):
        return False
    return len(PROSE_WORD.findall(body)) >= 3


def ignored(path):
    """Says whether git ignores `path`, i.e. whether it is a build output.

    Answers False when there is no repository to ask, so the tool still runs
    over a bare directory — a temporary tree in a test, for instance.

    Args:
        path: The file to ask about.

    Returns:
        True when git ignores it.
    """
    try:
        return subprocess.run(
            ["git", "check-ignore", "-q", str(path)],
            capture_output=True, check=False).returncode == 0
    except OSError:
        return False


def validate_mapping(mapping):
    """Refuses a table whose entries interfere with each other.

    Every rename is a sequence of `re.sub` passes over the same text, so a
    target that is also a source is eaten by the later pass: `{a: b, b: c}`
    turns BOTH `a` and `b` into `c`, writes code that no longer parses, and
    exits 0 — the read-back proof sees no string change and says nothing.
    Two names collapsing into one is never what the caller meant, so it is
    refused here rather than discovered in the diff.

    Args:
        mapping: The rename table, source name → target name.

    Raises:
        SystemExit: If a target is also a source, or two sources share a target.
    """
    # An IDENTITY entry is a no-op, not a chain. `{"pris": "taken", "scrape":
    # "scrape"}` is the natural way to write a vocabulary whose members mostly
    # move and one deliberately does not — and it was refused, so the caller had
    # to remember to leave the unchanged member out entirely. It cannot collapse
    # two names onto one, which is the whole reason chains are refused.
    moving = {source: target for source, target in mapping.items() if source != target}
    chained = sorted(set(moving.values()) & set(moving))
    if chained:
        raise SystemExit(
            "refusing a chained table: " + ", ".join(
                f"{name!r} is both a target and a source" for name in chained)
            + ". Split it into two runs, or rename via a name nothing else uses.")
    merged = sorted(
        target for target, count in collections.Counter(moving.values()).items()
        if count > 1)
    if merged:
        raise SystemExit(
            "refusing a merging table: " + ", ".join(
                f"several names map onto {name!r}" for name in merged)
            + ". A merge is a lost distinction — prefer a longer name.")


if __name__ == "__main__":
    MAPPING_FILE = pathlib.Path(sys.argv[1]).resolve()
    mapping = json.load(open(sys.argv[1]))
    validate_mapping(mapping)
    PROPERTIES = "--properties" in sys.argv
    VALUES = "--values" in sys.argv
    # CSS custom properties. Their own mode because no parser here sees them
    # and the word-boundary rule cannot match one — see `apply_custom_properties`.
    CUSTOM_PROPERTIES = "--custom-properties" in sys.argv
    # Substituting one word of a multi-word string is how prose gets rewritten,
    # so it is asked for by name and never assumed.
    INNER_WORDS = "--inner-words" in sys.argv
    # Values that are ordinary French words, so only their whole quoted form
    # may move. Passed as `--whole=annonce,termine`.
    WHOLE_ONLY = tuple(
        word
        for argument in sys.argv[2:] if argument.startswith("--whole=")
        for word in argument.split("=", 1)[1].split(",") if word
    )
    changed = collections.Counter()
    # Corpus facts for the no-op refusal below.
    read_files = 0
    saw_source = False
    saw_target = False
    written = []
    # The tree to walk. It defaulted to the maquette, and every surface outside
    # it — the app under `frontend/src`, the icon tool under `frontend/scripts`
    # — was therefore renamed by hand or not at all. A root is an argument now,
    # so the same nine forms this file knows about protect every tree.
    roots = [pathlib.Path(a.split("=", 1)[1]) for a in sys.argv[2:]
             if a.startswith("--root=")]
    ROOT = roots[0] if roots else pathlib.Path("frontend/maquette")
    for path in sorted(ROOT.rglob("*")):
        kinds = ({".js", ".jsx", ".ts", ".tsx", ".py", ".mjs", ".css", ".json", ".html"}
                 if VALUES or CUSTOM_PROPERTIES
                 else {".js", ".jsx", ".ts", ".tsx", ".py", ".mjs"})
        if not path.is_file() or path.suffix not in kinds:
            continue
        # A symlink is someone else's file: following one rewrote a file
        # OUTSIDE the root, and listed the same inode twice when it pointed
        # back inside.
        if path.is_symlink():
            continue
        # A BUILD OUTPUT IS NOT SOURCE. `node_modules` and `dist` were named
        # here one at a time, which left every other generated tree exposed:
        # a value pass reached `personalscraper/web/static/`, the mirror of
        # `frontend/dist`, and rewrote the MINIFIED bundle — `unicode-range`
        # became `unicode-filed` and an `<input type="range">` became
        # `type="filed"`. Nothing caught it, because the tree is gitignored and
        # so a revert could not restore it either. Asking git what it ignores
        # covers every generated tree at once, including the ones nobody has
        # created yet.
        # The cheap tests first: `ignored()` shells out to git, ~7.5 ms a call,
        # and `frontend/node_modules` alone holds 17 657 matching files — two
        # minutes of pure subprocess for a tree the next test rejects for free.
        if "node_modules" in path.parts or "dist" in path.parts or ignored(path):
            continue
        # The TRANSLATIONS are the one place French belongs, and a value pass
        # walks JSON. Nothing may reach `i18n/`.
        if "i18n" in path.resolve().parts:
            continue
        if path.name in {"serve.py", "rename.py"}:
            continue
        # THE MAPPING FILE IS NOT A TARGET. It is JSON whose keys are whole
        # quoted strings equal to the names being moved, so a values pass or a
        # custom-property pass rewrites the instruction it is executing — and
        # then a second run of the same command is a no-op that looks like
        # success. Caught the first time the custom-property mode ran on a
        # scratch tree with the table inside it.
        if path.resolve() == MAPPING_FILE:
            continue
        # `newline=""` keeps CRLF as CRLF. `read_text` folds `\r\n` into `\n`
        # while `readFileSync(…, "utf8")` in the span tool does not, so Python
        # counted one character where node counted two and EVERY span past the
        # first line drifted by one per line. The read-back proof then saw
        # strings that had "moved" and refused a file that was perfectly fine.
        with path.open(encoding="utf-8", newline="") as handle:
            before = handle.read()
        # SUBSTRING ONLY, DELIBERATELY: it answers « is this name anywhere in
        # the corpus », not « would it match ». The precise question is what
        # the modes below are for, and this one must stay true when they are
        # wrong. It is what tells a finished rename from one that could never
        # have started.
        read_files += 1
        if any(name in before for name in mapping):
            saw_source = True
        if any(name in before for name in mapping.values()):
            saw_target = True
        spans = (compiler_spans(path, before) if path.suffix in COMPILED
                 else python_spans(before) if path.suffix == ".py"
                 else None)
        if VALUES and path.suffix in {".css", ".json", ".html"}:
            spans = quoted_spans(before, html=path.suffix == ".html")
        if CUSTOM_PROPERTIES:
            after = apply_custom_properties(before, mapping)
        elif VALUES:
            after = apply_values(before, mapping, spans=spans,
                                 whole_only=WHOLE_ONLY, inner_words=INNER_WORDS)
        else:
            after = apply(before, mapping, in_python=path.suffix == ".py",
                          properties=PROPERTIES, spans=spans)
        if after == before:
            continue
        # Written BEFORE the proof, because the proof runs the parser over the
        # FILE: `node source-spans.mjs <path>` reads from disk, so text held
        # only in memory would have it re-reading the previous contents and
        # refusing every change. The original is remembered so a later refusal
        # can put the whole tree back.
        written.append((path, before))
        with path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(after)
        # THE PROOF, taken on what the rename PRODUCED: the parser reads the
        # result back, and every string, template piece, regex and JSX text
        # must still say exactly what it said. An empty table round-trips byte
        # for byte even when every span is misclassified, so it can never show
        # this — and this is the failure that ships.
        #
        # Python is exempt on purpose, not by oversight: `in_python=True`
        # renames INSIDE strings, because that is where the harness keeps the
        # identifiers it drives the engine with. Its strings are SUPPOSED to
        # change, so a proof that they did not would refuse every Python rename
        # the tool exists to make.
        if (not VALUES and not CUSTOM_PROPERTIES
                and spans is not None and path.suffix != ".py"
                and protected_text_of(path, after) != [
                    text for kind, s, e in spans if kind == "string"
                    for text in [before[s:e]]]):
            # ALL OR NOTHING. Writing as the walk went used to leave a
            # refusal on the tenth file with the first nine renamed and the
            # rest untouched — a tree that LOOKS done, which is worse than one
            # never started, and which this very message called « Nothing
            # written ». Every file already written is put back first, so the
            # message is true of the tree and not only of this file.
            for done_path, original in reversed(written):
                with done_path.open("w", encoding="utf-8", newline="") as handle:
                    handle.write(original)
            raise SystemExit(
                f"{path}: the rename would have changed a STRING, a "
                "template piece, a regex or JSX text — never an "
                f"identifier here. Nothing written, in any file "
                f"({len(written)} restored).")
        changed[str(path.relative_to(ROOT))] = sum(
            1 for _ in re.finditer("|".join(re.escape(v) for v in mapping.values()), after))


    # « 0 file(s) touched » WAS THIS TOOL'S SUCCESS LINE while it was
    # structurally unable to match the name it was given — a word boundary
    # cannot precede `--`. Adding a mode closed that one name and not the
    # SHAPE: a typo, a wrong `--root` or a mode that does not match the KIND
    # of name all still print it.
    #
    # THE REFUSAL IS NARROW BECAUSE TWO NO-OPS ARE LEGITIMATE — re-running a
    # rename that has already landed (idempotence is held by a test), and a run
    # whose corpus was excluded whole (everything under `i18n/`, which another
    # hold asserts). So it refuses exactly « files were read, and neither the
    # names being moved nor the names they move to are in any of them »: the
    # subject is not in this tree. The tool still cannot say a rename was
    # CORRECT — CLAUDE.md requires an oracle outside it — only that nothing
    # happened.
    if not changed and read_files and not saw_source and not saw_target:
        raise SystemExit(
            f"0 file(s) touched, and neither the {len(mapping)} name(s) being "
            f"moved nor the names they move to appear in any of the "
            f"{read_files} file(s) read. That is not a rename that had nothing "
            "left to do — it is a rename whose subject is not in this tree. "
            "Looked for: "
            + ", ".join(sorted(mapping)[:8])
            + (" …" if len(mapping) > 8 else "")
            + f"; under {ROOT}. Check the source names, the --root, and the "
            "mode (--properties, --values, --custom-properties).")
    if not changed and not read_files:
        print(
            f"0 file(s) read under {ROOT} — every candidate was excluded. "
            "Nothing was renamed because there was nothing to read.")

    print(f"{len(changed)} file(s) touched")
    for name, _ in changed.most_common(10):
        print("  " + name)

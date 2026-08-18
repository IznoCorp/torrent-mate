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
import json, pathlib, re, subprocess, sys, collections

SPAN_TOOL = pathlib.Path(__file__).with_name("source-spans.mjs")
COMPILED = {".ts", ".tsx", ".js", ".jsx", ".mjs"}


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
    reported = []
    for line in done.stdout.splitlines():
        if not line.strip():
            continue
        kind, a, b = line.split()
        reported.append(("string" if kind == "protected" else "comment",
                         int(a), int(b)))
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


def protected_text(path, text):
    """Returns the contents of every span a rename must leave alone."""
    return [text[s:e] for kind, s, e in compiler_spans(path, text)
            if kind == "string"]


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
                    # A TWELFTH form: `...` is a SPREAD, not a member access,
                    # and the lookbehind that protects `x.name` read the last
                    # of its three dots the same way. `{ ...REGLEE }` was left
                    # standing while every other mention moved — a half-rename,
                    # silent, and only the type-checker downstream said so.
                    chunk = re.sub(
                        rf"(?:(?<=\.\.\.)|(?<![.\w$])){re.escape(fr)}\b",
                        en, chunk)
        elif kind == "comment":
            for fr, en in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
                chunk = re.sub(rf"`{re.escape(fr)}\b", "`" + en, chunk)
                chunk = re.sub(rf"`{re.escape(fr)}\(", "`" + en + "(", chunk)
        pieces.append(chunk)
    return "".join(pieces)


if __name__ == "__main__":
    mapping = json.load(open(sys.argv[1]))
    PROPERTIES = "--properties" in sys.argv
    changed = collections.Counter()
    # The tree to walk. It defaulted to the maquette, and every surface outside
    # it — the app under `frontend/src`, the icon tool under `frontend/scripts`
    # — was therefore renamed by hand or not at all. A root is an argument now,
    # so the same nine forms this file knows about protect every tree.
    roots = [pathlib.Path(a.split("=", 1)[1]) for a in sys.argv[2:]
             if a.startswith("--root=")]
    ROOT = roots[0] if roots else pathlib.Path("frontend/maquette")
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in {".js", ".ts", ".tsx", ".py", ".mjs"}:
            continue
        if "node_modules" in path.parts or "dist" in path.parts:
            continue
        if path.name in {"serve.py", "rename.py"}:
            continue
        before = path.read_text(encoding="utf-8")
        spans = (compiler_spans(path, before) if path.suffix in COMPILED
                 else None)
        after = apply(before, mapping, in_python=path.suffix == ".py",
                      properties=PROPERTIES, spans=spans)
        if after != before:
            path.write_text(after, encoding="utf-8")
            # THE PROOF, taken on what was actually written: the parser reads
            # the result back, and every string, template piece, regex and
            # JSX text must still say exactly what it said. An empty table
            # round-trips byte for byte even when every span is misclassified,
            # so it can never show this — and this is the failure that ships.
            if spans is not None and protected_text(path, after) != [
                    text for kind, s, e in spans if kind == "string"
                    for text in [before[s:e]]]:
                path.write_text(before, encoding="utf-8")
                raise SystemExit(
                    f"{path}: the rename would have changed a STRING, a "
                    "template piece, a regex or JSX text — never an "
                    "identifier here. Nothing written.")
            changed[str(path.relative_to(ROOT))] = sum(
                1 for _ in re.finditer("|".join(re.escape(v) for v in mapping.values()), after))
    print(f"{len(changed)} file(s) touched")
    for name, _ in changed.most_common(10):
        print("  " + name)

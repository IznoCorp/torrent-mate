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
"""
import json, pathlib, re, sys, collections

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

def apply(text, mapping, in_python=False, properties=False):
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
        for fr, en in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
            text = re.sub(r"\bwindow\." + re.escape(fr) + r"\b", "window." + en, text)
            if fr.upper() == fr:
                text = re.sub(r"(['\"])" + re.escape(fr) + r"\1", r"\g<1>" + en + r"\1", text)
            #   "ajout:suivi"         a COMPOSED data key. A colon composes one
            #                         exactly as a hyphen does, and renaming the
            #                         half after it rewrote a rule's own EXPECTED
            #                         value — the hold then measured the app
            #                         against a key the app never produces.
            lookbehind = r"(?<![-:\w$'\"])" if properties else r"(?<![-:.\w$'\"])"
            text = re.sub(lookbehind + re.escape(fr) + r"\b(?![-\w])", en, text)
        return text
    pieces, count = [], 0
    for kind, s, e in regions(text):
        chunk = text[s:e]
        if kind == "code":
            for fr, en in sorted(mapping.items(), key=lambda kv: -len(kv[0])):
                if properties:
                    # `.name`, `name:`, and the binding itself — every end.
                    chunk = re.sub(rf"(?<![\w$]){re.escape(fr)}\b", en, chunk)
                else:
                    chunk = re.sub(rf"(?<![.\w$]){re.escape(fr)}\b", en, chunk)
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
    ROOT = pathlib.Path("frontend/maquette")
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in {".js", ".ts", ".tsx", ".py", ".mjs"}:
            continue
        if "node_modules" in path.parts or "dist" in path.parts:
            continue
        if path.name in {"serve.py", "rename.py"}:
            continue
        before = path.read_text(encoding="utf-8")
        after = apply(before, mapping, in_python=path.suffix == ".py",
                      properties=PROPERTIES)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed[str(path.relative_to(ROOT))] = sum(
                1 for _ in re.finditer("|".join(re.escape(v) for v in mapping.values()), after))
    print(f"{len(changed)} file(s) touched")
    for name, _ in changed.most_common(10):
        print("  " + name)

#!/usr/bin/env python3
"""Forbid French in the code, and forbid interface text from living in the code.

The operator's rule (2026-08-16): **the code contains no French** — identifiers,
class names (code AND CSS), file names, tool messages — **and no interface string
lives in the code**: the French a reader of the interface sees lives in the i18n
resources. This script is the half of the rule that is enforced rather than
remembered; it runs in `make check` and in CI.

Four arms, each with its own scope, because "French" means a different thing in a
component than it does in a rule script that ASSERTS the French the app renders:

1. **Strings** — over the shell's own sources (`design/src`, minus `src/i18n`), the
   two servers and the harness's `.mjs` tools: a string literal carrying an
   accent, or two French function words, is interface text left in the code. Over
   the harness's RULE SCRIPTS, only the hold LABELS are read (`check("…")`,
   `Journal("…")`) — those are the tool's own messages. The French a hold COMPARES
   is the app's rendered output and must stay French; no arm may ask it to change.
2. **Identifiers** — declared names (Python read through `ast`, TypeScript through
   its declaration keywords) over the same sources plus the harness.
3. **File names** — every path SEGMENT, tracked or merely present, under
   `frontend/`, `scripts/`, `personalscraper/` and `tests/`. This is the arm that
   keeps the rule alive for files created later, anywhere. `docs/` is NOT read:
   dated records keep the names they were written with, and rewriting a record
   would falsify it.
4. **Class names** — `class X` declarations, and the CSS classes the maquette
   DECLARES (`design/refonte.html`) plus the stylesheet extracted from it
   (`frontend/src/styles/ps/*.css`). A class name is one name shared by four
   worlds, which is why it gets an arm of its own.

Each arm also reports how much it READ, and an arm that read nothing is itself a
violation: a scope that silently empties — a renamed directory, a glob that stops
matching — otherwise announces « no violation » with perfect confidence while
measuring nothing.

Every exception CITES its reason. The CSS-class exceptions are read from
`frontend/maquette/regions.json`'s `$vocabulary` — the maquette's own record, so
there is no second copy of those reasons to drift — and this script refuses to run
if an entry there carries no reason. The other exceptions are the dictionaries
below, each entry a token mapped to why it stays.

A line may also carry an inline pragma for the string arm:

    print("recherches: 3")  # french-ok: the prototype's own data key

The reason after the colon is mandatory: a pragma with nothing after it is itself
a violation, because a permission nobody justified is indistinguishable from an
oversight.
"""

from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import sys
import token as token_kinds
import tokenize
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAQUETTE = ROOT / "frontend" / "maquette"
SHELL = MAQUETTE / "design" / "src"
HARNESS = MAQUETTE / "harness"
REGIONS = MAQUETTE / "regions.json"
FRAGMENT = MAQUETTE / "design" / "refonte.html"
EXTRACTED_CSS = ROOT / "frontend" / "src" / "styles" / "ps"

# ── the lexicon ──────────────────────────────────────────────────────────────
#
# Measured, not decreed: these are the French tokens this repository actually
# used, collected from the renames the clean-code wave performed. A word that
# reads the same in both languages is NOT here — `decision`, `resolution`,
# `episode`, `series`, `palette`, `navigation`, `machine`, `image`, `surface`,
# `selection`, `profile`, `cadence`, `flux`, `verifier` (a thing that verifies)
# all stay, and putting them here would make the gate lie about them.
FRENCH_TOKENS = {
    # surfaces and objects of this application
    "acteur", "acteurs", "adresse", "adresses", "affiche", "affiches", "ajout",
    "arrivee", "arrivees", "bandeau", "bascule", "bouton", "boutons", "carte",
    "cartes", "champ", "champs", "chemin", "chemins", "composant", "composants",
    "connexion", "coquille", "deconnexion", "demarrage", "doigt", "donnees",
    "dossier", "dossiers", "ecran", "ecrans", "entree", "entrees", "feuille",
    "fiche", "fiches", "fichier", "fichiers", "filtre", "filtres", "galerie",
    "glisse", "grille", "heros", "installation", "jeton", "legende", "libelle",
    "libelles", "liste", "listes", "magasin", "manquant", "manquants",
    "maquette", "mediatheque", "nombre", "nombres", "panneau", "panneaux",
    "pied", "pont", "profil", "reglage", "reglages", "recherche", "refonte",
    "renommer", "resynchro", "saison", "saisons", "serveur", "socle", "souris",
    "sujet", "sujets", "suivi", "suivis", "systeme", "tiroir", "titre",
    "titres", "unite", "unites", "verrou",
    # verbs and states. `refuse` is NOT here and `refuser`/`refusee` are: the
    # bare stem is an English verb, and a gate that flags `refuseBlock` teaches
    # its reader to stop believing it.
    "ajuster", "ajustement", "ajustements", "attendu", "calcule", "chercher",
    "ecrire", "empreinte", "erreur", "erreurs", "etat", "etats", "identifiant",
    "introuvable", "introuvables", "lire", "motdepasse", "ouvrir", "ouvre",
    "refus", "refusee", "refuser", "toucher", "valeur", "valeurs",
    "verifier", "vider",
    # words a translation reaches for and gets wrong
    "balisage", "bloc", "blocs", "debut", "deploiement", "marque", "morceau",
    "morceaux", "objet", "objets", "parametre", "parametres", "precedent",
    "principal", "reel", "reels", "taille", "texte", "vide",
}
# `verifier` is in the lexicon for the SHELL and the HARNESS, where it was the
# French verb, and exempted for `personalscraper/` and `tests/`, where it is the
# English noun (the NFO verifier). Scope, not a word list, settles the ambiguity.
VERIFIER_IS_ENGLISH_UNDER = ("personalscraper/", "tests/", "frontend/src/")

# The string arm's second signal: French function words. Only words that are NOT
# English words, so that one of them in an English sentence cannot fire — and two
# distinct ones are required anyway, because a French SENTENCE always carries
# several while a stray token does not.
FRENCH_FUNCTION_WORDS = {
    "le", "la", "les", "une", "des", "du", "aux", "et", "est", "sont", "pas",
    "pour", "dans", "sur", "avec", "que", "qui", "quoi", "cette", "ces", "ses",
    "leur", "elle", "ils", "elles", "tout", "tous", "toute", "toutes", "aucun",
    "aucune", "chaque", "meme", "deja", "encore", "moins", "etre", "avoir",
    "fait", "faire", "vers", "chez", "mais", "donc", "alors", "ainsi", "comme",
    "quand", "lorsque", "depuis", "entre", "sous", "trop", "rien", "jamais",
    "toujours", "nest", "cest",
}

# ── the exceptions, each with its reason ─────────────────────────────────────

# Path segments that stay French. Read as data, not as names.
FROZEN_PATH_SEGMENTS = {
    "acteurs": (
        "An artwork directory of the embedded référentiel. The paths under it are "
        "DATA VALUES inside the prototype's own data (`assets/acteurs/<hash>.webp`) "
        "and ADDRESSES served over HTTP — the same class the recorded ruling "
        "freezes for `data-*` values and route paths. They settle when the artwork "
        "is bound to the backend, never in a naming pass."
    ),
    "affiches": (
        "Same family as `acteurs`: a poster path is a data value in the embedded "
        "référentiel and an address served over HTTP."
    ),
    "heros": (
        "Same family as `acteurs`: a hero-image path is a data value in the "
        "embedded référentiel and an address served over HTTP."
    ),
    "maquette": (
        "The design reference's own name, and the operator's word for the thing "
        "— it is named in the product constitution (§15), in CLAUDE.md and in "
        "every rule record. Renaming it renames the subject, not a file."
    ),
    "refonte": (
        "The legacy fragment (`refonte.html`), named verbatim by R72 and by "
        "every rule that reads it. It DIES at SP4-end; renaming a file on its "
        "way out buys nothing and costs every pointer at it."
    ),
}

# Declared names that stay French, over the shell and the harness. Empty, and
# that is the finding: the seam this wave froze is made of object-literal KEYS
# and `window.` properties, which no arm reads, so nothing had to be excused.
FROZEN_IDENTIFIERS: dict[str, str] = {}

# ── helpers ──────────────────────────────────────────────────────────────────

WORD = re.compile(r"[A-Za-zÀ-ɏ]+")
PRAGMA = re.compile(
    r"(?:#|//|/\*)\s*french-ok:\s*(?P<reason>[^*]*)")


def deaccent(text: str) -> str:
    """Returns the text with its accents stripped, for token comparison."""
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if not unicodedata.combining(c))


def has_accent(text: str) -> bool:
    """Returns True when the text carries a letter no English word carries."""
    return any(unicodedata.combining(c)
               for c in unicodedata.normalize("NFD", text))


def split_identifier(name: str) -> list[str]:
    """Returns an identifier's words: camelCase, snake_case and flat alike."""
    parts = re.split(r"[^A-Za-zÀ-ɏ]+", name)
    words: list[str] = []
    for part in parts:
        words.extend(re.findall(
            r"[A-Z]+(?![a-z])|[A-Z][a-zÀ-ɏ]*|[a-zÀ-ɏ]+", part))
    return [w for w in words if w]


def french_tokens_in(name: str, path: str = "") -> list[str]:
    """Returns the lexicon tokens a name is built out of.

    Args:
        name: The identifier, file segment or class name to read.
        path: The file it was found in, so a scope-dependent word (`verifier`)
            is judged where it is written.

    Returns:
        The matching lexicon tokens, lowercased and de-accented.
    """
    found = []
    for word in split_identifier(name):
        token = deaccent(word).lower()
        if token not in FRENCH_TOKENS:
            continue
        if token == "verifier" and any(s in path for s in VERIFIER_IS_ENGLISH_UNDER):
            continue
        found.append(token)
    return found


# A CSS class is read as one FLAT string, because that is how this vocabulary is
# written — `sheetacts`, `herowrap`, `mediaadd`, `fieldinput`, no separator (the
# convention is recorded in `regions.json`'s `$vocabulary`). Word-splitting sees
# `bandeaufiche` as one unknown word and lets it through, so the class arm
# matches lexicon tokens as SUBSTRINGS instead. The cost of that is below.
CSS_ENGLISH_DESPITE_A_TOKEN = {
    "blocked": (
        "English, and it CONTAINS `bloc` — the price of substring matching. The "
        "class marks a medium the pipeline could not move."
    ),
    "fblocked": (
        "The `f*` family's member of the same English word (follow-blocked)."
    ),
}


def french_tokens_in_flat(name: str) -> list[str]:
    """Returns the lexicon tokens a FLAT lowercase name is built out of.

    Args:
        name: A CSS class name, written without separators.

    Returns:
        The matching tokens, or nothing when the name is one of the English
        words that happen to carry a token inside them.
    """
    flat = deaccent(name).lower()
    if flat in CSS_ENGLISH_DESPITE_A_TOKEN:
        return []
    return sorted({token for token in FRENCH_TOKENS if token in flat})


def relative(path: Path) -> str:
    """Returns the path as the repository writes it."""
    return str(path.relative_to(ROOT))


# What each arm actually READ. A guardrail whose scope silently empties — a
# renamed directory, a glob that stops matching — reports « no violation » with
# perfect confidence and measures nothing, which is how a rule goes quiet
# instead of red. These counts are printed on success and asserted non-zero.
examined: dict[str, int] = {
    "string literals": 0,
    "hold labels": 0,
    "declared identifiers": 0,
    "path segments": 0,
    "class names": 0,
    "declared CSS classes": 0,
}


# ── arm 1: strings ───────────────────────────────────────────────────────────
#
# A string is read as a STRING, never as a span between two quote characters: an
# apostrophe inside a comment (« the panel's own vocabulary ») closes nothing,
# and a scanner that thinks it does reports the comment's prose as a literal.
# Python is read through `tokenize`, which is exact; TypeScript through the small
# scanner below, which tracks comments, strings and templates.

HOLD_LABEL = re.compile(
    r"""(?:\bcheck|\bJournal|\bjournal\.check)\(\s*(?P<q>'''|\"\"\"|'|")"""
    r"""(?P<body>(?:\\.|(?!(?P=q))[^\\])*)(?P=q)""", re.S)

# What the app RENDERS is quoted, in this repository's own convention, inside
# guillemets. A quotation is not a French name in the code — it is the code
# naming what the reader of the interface sees — so it is removed before judging.
QUOTED_UI = re.compile(r"«[^»]*»")


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


def offending_string(body: str, quoting_allowed: bool = False) -> str:
    """Returns why a literal counts as French, or an empty string.

    Args:
        body: The literal, quotes included.
        quoting_allowed: True for a tool message, which may NAME an interface
            surface (« Médiathèque », Système, SIMULÉE) — the English sentence
            says what is being read, and the French word is the thing read. A
            capitalised accented word is such a name; a lowercase one is prose.

    Returns:
        The reason, ready to print, or "" when the literal is not French.
    """
    body = QUOTED_UI.sub(" ", body)
    if quoting_allowed:
        body = " ".join(w for w in re.split(r"(\s+)", body)
                        if not (w[:1].isupper() and has_accent(w)))
    if has_accent(body):
        accents = sorted({c for c in body if has_accent(c)})
        return f"accented characters {accents}"
    words = {deaccent(w).lower() for w in WORD.findall(body)}
    hits = sorted(words & FRENCH_FUNCTION_WORDS)
    if len(hits) >= 2:
        return f"French function words {hits}"
    return ""


def pragma_on(lines: list[str], line_no: int) -> str | None:
    """Returns the reason a line's french-ok pragma cites, or None.

    Args:
        lines: The file's lines.
        line_no: The 1-based line the literal starts on.

    Returns:
        The cited reason, "" when the pragma cites nothing, or None when the
        line carries no pragma. The line ABOVE and the line BELOW count too: a
        JSX attribute has no room for a trailing comment, and a wrapped literal
        must not silently lose its permission to a line break.
    """
    for candidate in (line_no, line_no - 1, line_no + 1):
        if 1 <= candidate <= len(lines):
            found = PRAGMA.search(lines[candidate - 1])
            if found:
                return found.group("reason").strip()
    return None


def check_strings(violations: list[str]) -> None:
    """Runs the string arm over the shell, the servers and the hold labels."""
    strict: list[Path] = [p for p in SHELL.rglob("*") if p.is_file()
                          and p.suffix in {".ts", ".tsx"} and "i18n" not in p.parts]
    strict += [MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
    strict += sorted(HARNESS.glob("*.mjs"))
    for path in sorted(strict):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        literals = (python_string_literals(source) if path.suffix == ".py"
                    else script_string_literals(source))
        examined["string literals"] += len(literals)
        for line_no, body in literals:
            reason = offending_string(body)
            if not reason:
                continue
            cited = pragma_on(lines, line_no)
            if cited:
                continue
            if cited == "":
                violations.append(
                    f"{relative(path)}:{line_no}: a french-ok pragma citing no "
                    "reason permits nothing")
                continue
            violations.append(
                f"{relative(path)}:{line_no}: French string literal "
                f"({reason}) — interface text belongs in "
                f"design/src/i18n/fr.json: {body[:60]!r}")

    for path in sorted(HARNESS.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for match in HOLD_LABEL.finditer(source):
            examined["hold labels"] += 1
            line_no = source.count("\n", 0, match.start()) + 1
            reason = offending_string(match.group("body"), quoting_allowed=True)
            if not reason:
                continue
            if pragma_on(lines, line_no):
                continue
            violations.append(
                f"{relative(path)}:{line_no}: French hold label ({reason}) — a "
                f"hold's label is the tool's own message: "
                f"{match.group('body')[:60]!r}")


# ── arm 2: identifiers ───────────────────────────────────────────────────────

TS_DECLARATION = re.compile(
    r"\b(?:const|let|var|function|class|interface|type|enum)\s+"
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
    return names


def check_identifiers(violations: list[str]) -> None:
    """Runs the identifier arm over the shell, the servers and the harness."""
    python = ([MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
              + sorted(HARNESS.glob("*.py")))
    for path in python:
        source = path.read_text(encoding="utf-8")
        declarations = python_declarations(source)
        examined["declared identifiers"] += len(declarations)
        for name, line_no in declarations:
            if name in FROZEN_IDENTIFIERS:
                continue
            hits = french_tokens_in(name, relative(path))
            if hits or has_accent(name):
                violations.append(
                    f"{relative(path)}:{line_no}: French identifier {name!r} "
                    f"({', '.join(hits) or 'accented'})")

    web = [p for p in SHELL.rglob("*") if p.is_file() and p.suffix in {".ts", ".tsx"}]
    web += sorted(HARNESS.glob("*.mjs"))
    for path in sorted(web):
        if "i18n" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        for match in TS_DECLARATION.finditer(source):
            examined["declared identifiers"] += 1
            name = match.group("name")
            if name in FROZEN_IDENTIFIERS:
                continue
            hits = french_tokens_in(name, relative(path))
            if hits or has_accent(name):
                line_no = source.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{relative(path)}:{line_no}: French identifier {name!r} "
                    f"({', '.join(hits) or 'accented'})")


# ── arm 3: file names ────────────────────────────────────────────────────────

TRACKED_ROOTS = ("frontend", "scripts", "personalscraper", "tests")


def tracked_paths() -> list[str]:
    """Returns every path under the roots this arm watches.

    Untracked-but-not-ignored files are listed too (`--others
    --exclude-standard`): a file created five minutes ago is exactly the one
    this arm exists to catch, and it is not tracked until it is added — a gate
    that only reads the index says nothing until after the commit it should
    have blocked.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard",
         *TRACKED_ROOTS],
        cwd=ROOT, capture_output=True, text=True, check=True)
    return sorted({p for p in listed.stdout.split("\0") if p})


def check_file_names(violations: list[str]) -> None:
    """Runs the file-name arm over every tracked path segment."""
    seen: set[tuple[str, str]] = set()
    for path in tracked_paths():
        for segment in path.split("/"):
            examined["path segments"] += 1
            stem = segment.rsplit(".", 1)[0] if "." in segment else segment
            # Frozen TOKENS, not frozen segments: `maquette` stays wherever it
            # appears — the directory, `extract-maquette-css.py`, the extracted
            # stylesheets — and each of those would otherwise need its own
            # entry, which is how an allowlist grows without anyone deciding.
            hits = [h for h in french_tokens_in(stem, path)
                    if h not in FROZEN_PATH_SEGMENTS]
            if not (hits or has_accent(segment)):
                continue
            key = (segment, ", ".join(hits))
            if key in seen:
                continue
            seen.add(key)
            violations.append(
                f"{path}: French path segment {segment!r} "
                f"({', '.join(hits) or 'accented'})")


# ── arm 4: class names ───────────────────────────────────────────────────────

CSS_SELECTOR = re.compile(r"\.(?P<name>-?[A-Za-z_À-ɏ][\wÀ-ɏ-]*)")


def css_allowlist() -> dict[str, str]:
    """Returns the frozen CSS class names, each mapped to its recorded reason.

    Read from `regions.json`'s `$vocabulary` — the maquette's own record — so the
    reasons have exactly one home. An entry with no reason is itself a
    violation: a permission nobody justified is indistinguishable from an
    oversight.

    Raises:
        ValueError: When the record is missing or an entry carries no reason.
    """
    data = json.loads(REGIONS.read_text(encoding="utf-8"))

    def find(node: object) -> dict | None:
        if isinstance(node, dict):
            if "$vocabulary" in node:
                return node["$vocabulary"]
            for value in node.values():
                got = find(value)
                if got is not None:
                    return got
        return None

    vocabulary = find(data)
    if not isinstance(vocabulary, dict):
        raise ValueError(f"no $vocabulary record in {relative(REGIONS)}")
    allowed: dict[str, str] = {}
    frozen = vocabulary.get("frenchTokensFrozen", {})
    reason = frozen.get("$comment", "").strip()
    if not reason:
        raise ValueError("frenchTokensFrozen carries no reason")
    for token in frozen.get("tokens", []):
        allowed[token] = reason
    for token, why in vocabulary.get("abbreviationsKept", {}).items():
        if token.startswith("$"):
            continue
        if not str(why).strip():
            raise ValueError(f"abbreviationsKept[{token!r}] carries no reason")
        allowed[token] = str(why)
    return allowed


def allowed_class(name: str, allowed: dict[str, str]) -> bool:
    """Returns True when a class name is covered by a cited exception."""
    if name in allowed:
        return True
    return any(key.endswith("*") and name.startswith(key[:-1])
               for key in allowed)


def declared_css_classes(source: str) -> dict[str, int]:
    """Returns the class names a stylesheet DECLARES, with their first line."""
    found: dict[str, int] = {}
    for block in re.finditer(r"(?P<selectors>[^{}]+)\{[^{}]*\}", source):
        selectors = block.group("selectors")
        # A selector list only: anything after an `@media`/`@supports` prelude,
        # or a property line, carries no leading-dot class.
        for match in CSS_SELECTOR.finditer(selectors):
            name = match.group("name")
            line_no = source.count("\n", 0, block.start() + match.start()) + 1
            found.setdefault(name, line_no)
    return found


def check_class_names(violations: list[str]) -> None:
    """Runs the class-name arm over code classes and declared CSS classes."""
    allowed = css_allowlist()

    for path in ([MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
                 + sorted(HARNESS.glob("*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                examined["class names"] += 1
                hits = french_tokens_in(node.name, relative(path))
                if hits or has_accent(node.name):
                    violations.append(
                        f"{relative(path)}:{node.lineno}: French class name "
                        f"{node.name!r} ({', '.join(hits) or 'accented'})")

    code_class = re.compile(r"\bclass\s+(?P<name>[A-Za-z_$][\w$À-ɏ]*)")
    for path in sorted(p for p in SHELL.rglob("*")
                       if p.is_file() and p.suffix in {".ts", ".tsx"}):
        source = path.read_text(encoding="utf-8")
        for match in code_class.finditer(source):
            examined["class names"] += 1
            name = match.group("name")
            hits = french_tokens_in(name, relative(path))
            if hits or has_accent(name):
                line_no = source.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{relative(path)}:{line_no}: French class name {name!r} "
                    f"({', '.join(hits) or 'accented'})")

    sheets = [FRAGMENT] + sorted(EXTRACTED_CSS.glob("*.css"))
    for path in sheets:
        if not path.is_file():
            continue
        source = path.read_text(encoding="utf-8")
        if path is FRAGMENT:
            # The fragment is one document: only its <style> blocks declare CSS.
            source = "\n".join(
                m.group(1) for m in re.finditer(
                    r"<style[^>]*>(.*?)</style>", source, re.S))
        declared = declared_css_classes(source)
        examined["declared CSS classes"] += len(declared)
        for name, line_no in declared.items():
            if allowed_class(name, allowed):
                continue
            hits = french_tokens_in_flat(name)
            if hits or has_accent(name):
                violations.append(
                    f"{relative(path)}:{line_no}: French CSS class {name!r} "
                    f"({', '.join(hits) or 'accented'}) — a class name is one "
                    "name shared by four worlds")


def main() -> int:
    """Runs the four arms and reports every violation.

    Returns:
        1 when anything was found, 0 otherwise.
    """
    violations: list[str] = []
    check_strings(violations)
    check_identifiers(violations)
    check_file_names(violations)
    check_class_names(violations)
    for what, count in examined.items():
        if count == 0:
            violations.append(
                f"the arm reading {what} examined NOTHING — its scope is empty, "
                "so its « no violation » means nothing")
    if violations:
        print("no-French guardrail violations:", file=sys.stderr)
        for violation in violations:
            print(f"  {violation}", file=sys.stderr)
        print(f"\n{len(violations)} violation(s). The rule: the code is English "
              "(identifiers, class names, file names, tool messages); the French "
              "a reader of the interface sees lives in the i18n resources.",
              file=sys.stderr)
        return 1
    print("no-French guardrail: 4 arms, no violation — read "
          + ", ".join(f"{count} {what}" for what, count in examined.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

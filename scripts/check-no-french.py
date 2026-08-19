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
   its declaration keywords) over the same sources, the harness, `scripts/`,
   `personalscraper/` and `tests/` — the whole repository, in other words. A name
   that NAMES a frozen thing (`MAQUETTE`) inherits that thing's reason, and two
   tokens are read differently depending on where they sit (`TOKENS_BY_SCOPE`).
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
# The words this codebase's names are built from — see its own header.
VOCABULARY = ROOT / "scripts" / "code-vocabulary.txt"
# The line in that file below which the words are French on purpose, and the
# one file allowed to need them.
DEBT_BANNER = "# ── THE ENGINE'S LAST FRENCH WORDS"
DEBT_FILE = "frontend/maquette/design/src/engine/legacy.js"
SHELL = MAQUETTE / "design" / "src"
HARNESS = MAQUETTE / "harness"
REGIONS = MAQUETTE / "regions.json"
FRAGMENT = MAQUETTE / "design" / "refonte.html"
EXTRACTED_CSS = ROOT / "frontend" / "src" / "styles" / "ps"
SCRIPTS = ROOT / "scripts"

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
    "attribut", "attributs", "cartes", "champ", "champs", "chemin", "chemins",
    "composant", "composants",
    "connexion", "coquille", "deconnexion", "demarrage", "doigt", "donnees",
    "dossier", "dossiers", "ecran", "ecrans", "entree", "entrees", "feuille",
    "fiche", "fiches", "fichier", "fichiers", "filtre", "filtres", "galerie",
    "glisse", "grille", "heros", "jeton", "jetons", "legende", "libelle",
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
    "refus", "refusee", "refuser", "sans", "toucher", "valeur", "valeurs",
    "verifier", "vider",
    # words a translation reaches for and gets wrong
    "balisage", "bloc", "blocs", "debut", "deploiement", "marque", "morceau",
    "morceaux", "objet", "objets", "parametre", "parametres", "precedent",
    "principal", "reel", "reels", "taille", "texte", "vide",
    # the vocabulary of the repository's own tools, measured the same way — the
    # words `scripts/` actually used before this wave. `porter` is deliberately
    # absent: it is an English verb.
    "actuel", "ambigue", "ambigues", "construire", "contrat", "ecarte",
    "ecartees", "entete", "garde", "gardees", "harnais", "ordre", "parseur",
    "permis", "portee", "profondeur", "racine", "regle", "regles", "refusees",
    "selecteur", "sortie",
    # Measured the same way, and by the campaign that found them missing: every
    # word below named something in this repository while the gate read green.
    # `suivante`, `trier` and `fermer` were the first three; a hundred and
    # forty names sat under the rest. A word that reads the same in both
    # languages is still NOT here — `centre`, `cote`, `sortie` and `rayon` are
    # English too, and a gate that flagged them would teach its reader to stop
    # believing it.
    "actifs", "anneau", "apparence", "apparences", "bordees", "calque",
    "candidats", "cherche", "chercher", "circulaire", "combien", "controle",
    "coupables", "couverture", "denominateur", "depuis", "dessin", "faits",
    "frise", "lignes", "maintenant", "masquables", "masquer", "mots",
    "normaliser", "numerateur", "pilotage", "plages", "prendre", "reglee",
    "remis", "restants", "retirer", "risques", "rubrique", "traiter",
    "transparents", "tris", "trier", "trouve",
    # The two state words that had no underscore to be told apart by, so they
    # travelled as VALUES (`--whole=`) and no arm ever read them as NAMES —
    # which is how `test_annonce_state.py` and `test_termine_state.py` kept
    # their spelling through a wave that renamed everything around them.
    "annonce", "annoncee", "termine", "terminee",
}
# Two tokens mean different things in different halves of the repository, and
# scope — not a word list — is what settles them. Each entry names the reason.
TOKENS_BY_SCOPE = {
    "verifier": (
        ("personalscraper/", "tests/", "scripts/", "frontend/src/"),
        "The English NOUN — a thing that verifies, the NFO verifier. It is the "
        "French VERB only in the maquette's harness, where it was renamed to "
        "`check`.",
    ),
    "saison": (
        ("personalscraper/", "tests/"),
        "The LIBRARY's own folder convention: a season directory on disk is "
        "named « Saison XX ». A test or a pattern naming it names a DATA value, "
        "not a variable someone chose — renaming it would describe a layout the "
        "disk does not have.",
    ),
    "saisons": (
        ("personalscraper/", "tests/"),
        "Plural of the same folder convention.",
    ),
}

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
    "toujours", "nest", "cest", "un", "aucun", "notre", "votre",
}
# `du`, `est` and `et` are NOT here, though they are French: they are also
# `du -sh`, EST and « et al. » — and a guardrail that flags a shell command
# teaches its reader to stop believing it. The function-word signal also
# requires the words to be LOWERCASE in the source, for the same reason (`LA`,
# `DES`, `EST` are abbreviations; French prose is lowercase).

# Interface copy is rarely a sentence: it is one to three words, often with no
# accent at all — « Fermer », « Ajouter un dossier », « Aucun resultat ». Two
# function words never appear in those, so the label vocabulary is its own
# signal, and ONE of these is enough.
FRENCH_UI_WORDS = {
    "ajouter", "annuler", "chercher", "choisir", "confirmer", "continuer",
    "enregistrer", "fermer", "modifier", "ouvrir", "recommencer", "rechercher",
    "reessayer", "relancer", "retirer", "retour", "supprimer", "telecharger",
    "valider", "voir", "aucun", "aucune", "suivant", "precedent", "terminer",
}

# ── the exceptions, each with its reason ─────────────────────────────────────

# Path segments that stay French. Read as data, not as names.
FROZEN_PATH_SEGMENTS = {
    # `acteurs`, `affiches` and `heros` were frozen here as « data values and
    # addresses », and the operator overturned that: a directory is a NAME
    # someone chose, and the rule says file and directory names are English.
    # They are `cast`, `posters-hd` and `heroes` now, with all 528 paths and
    # the directories themselves moved in one step — and every one of the 925
    # references still resolves, which is what R70 checks.
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

# Declared NAMES that stay French. Kept apart from the path allowlist above on
# purpose: « this directory is an address » is a reason about paths, and letting
# it excuse a variable would make five French words legal as names everywhere on
# a justification that says nothing about names.
FROZEN_IDENTIFIERS = {
    "MAQUETTE": (
        "Names the maquette DIRECTORY, whose own name is frozen above — a "
        "constant holding a path inherits that path's reason and nothing more."
    ),
    # `ecrans`, `panneau`, `pont` and `fiche` were frozen here, and the
    # operator asked what the reason actually was. It did not survive the
    # question: « the fragment spells them that way » is circular — the
    # fragment, the engine and the harness are all in this repository, and a
    # hundred and forty names the fragment spelled had already moved. They are
    # `screens`, `panel`, `bridge` now, with their eleven methods, and the
    # media-sheet contract is `data-mediasheet` — a name of its own, because
    # `data-sheet` belongs to the panel opener and merging them broke the user
    # menu. A constraint on WHICH English name to pick was never a reason to
    # keep the French one.
}

# ── helpers ──────────────────────────────────────────────────────────────────

WORD = re.compile(r"[A-Za-zÀ-ɏ]+")
PRAGMA = re.compile(
    r"(?:#|//|/\*)\s*french-ok:\s*(?P<reason>[^*]*)")


def deaccent(text: str) -> str:
    """Returns the text with its accents stripped, for token comparison."""
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if not unicodedata.combining(c))


def has_accent(text: str) -> bool:
    """Returns True when the text carries a LETTER no English word carries.

    The letter part is not pedantry: `≠` decomposes to `=` plus a combining
    slash, so a test that only asks « does anything here combine? » reads a
    mathematical sign as French and says so with a straight face.
    """
    decomposed = unicodedata.normalize("NFD", text)
    return any(previous.isalpha() and unicodedata.combining(char)
               for previous, char in zip(decomposed, decomposed[1:]))


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
        scoped = TOKENS_BY_SCOPE.get(token)
        if scoped and path.startswith(scoped[0]):
            continue
        found.append(token)
    return found


# A CSS class is read as one FLAT string, because that is how this vocabulary is
# written — `sheetacts`, `herowrap`, `mediaadd`, `fieldinput`, no separator (the
# convention is recorded in `regions.json`'s `$vocabulary`). Word-splitting sees
# `bandeaufiche` as one unknown word and lets it through, so the class arm
# matches lexicon tokens as SUBSTRINGS instead. The cost of that is below.
# Tokens the FLAT pass does not read, because each one lives inside an ordinary
# English word and a flat name has no boundary to tell them apart: `vide`/`vider`
# in `video`/`provider`/`divider`, `permis` in `permissions`, `marque` in
# `marquee`, `liste` in `listen`, `bloc` in `block`, `pied` in `copied`. Excluded
# by TOKEN, once, rather than by NAME — an allowlist that grows one class at a
# time is an allowlist nobody decides. The identifier arm keeps the full lexicon:
# it reads camelCase and snake_case, which do have boundaries.
CSS_BLIND_TOKENS = {
    "bloc", "blocs", "carte", "cartes", "debut", "entree", "entrees", "garde",
    "gardees", "liste", "listes", "marque", "permis", "pied", "portee",
    "principal", "reel", "reels", "sortie", "suite", "vide", "vider",
}

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
    # ANCHORED, and only for tokens long enough to mean something. An unanchored
    # substring test read `video` as `vide`, `provider` as `vider`, `block` as
    # `bloc`, `copied` as `pied`, `marquee` as `marque` and `permissions` as
    # `permis` — eight English names out of eight, in a repository whose subject
    # is video providers. This vocabulary compounds by prefix and suffix
    # (`bandeaufiche`, `tiroirreglages`), which is what anchoring reads.
    return sorted({token for token in FRENCH_TOKENS - CSS_BLIND_TOKENS
                   if len(token) >= 5
                   and (flat.startswith(token) or flat.endswith(token))})


def relative(path: Path) -> str:
    """Returns the path as the repository writes it."""
    return str(path.relative_to(ROOT))


def read(path: Path) -> str:
    """Returns a source file's text, BOM included or not.

    `utf-8-sig`, because CPython strips a BOM when it RUNS a file and `ast`
    refuses one when it parses the same file — a gate must not reject what the
    project accepts.
    """
    return path.read_text(encoding="utf-8-sig")


# What each arm actually READ. A guardrail whose scope silently empties — a
# renamed directory, a glob that stops matching — reports « no violation » with
# perfect confidence and measures nothing, which is how a rule goes quiet
# instead of red. These counts are printed on success and asserted non-zero.
# Keyed by (what, WHERE). Per-counter was not enough: `personalscraper/` and
# `tests/` alone keep the identifier count near 125 000, so the maquette shell —
# arm 1's and arm 4's primary target — could vanish entirely and the total would
# barely move. A scope that empties must be visible as ITSELF.
examined: dict[str, int] = {
    "string literals / shell": 0,
    "string literals / servers": 0,
    "string literals / harness tools": 0,
    "string literals / repository tools": 0,
    "rendered text / shell": 0,
    "hold labels / harness": 0,
    "declared identifiers / shell": 0,
    "declared identifiers / servers": 0,
    "declared identifiers / harness": 0,
    "declared identifiers / harness tools": 0,
    "declared identifiers / repository tools": 0,
    "declared identifiers / package": 0,
    "declared identifiers / tests": 0,
    "declared identifiers / app": 0,
    "path segments / repository": 0,
    "class names / python": 0,
    "class names / typescript": 0,
    "declared CSS classes / fragment": 0,
    "declared CSS classes / extracted": 0,
    "unread javascript / shell": 0,
    "name words / shell": 0,
    "data-* names / markup": 0,
    "french debt words / vocabulary": 0,
    "lines / shell scripts": 0,
    "interface text / app (exempt)": 0,
}

# Counted, reported, and deliberately NOT refused. An exemption nobody counts
# is indistinguishable from an oversight, so each one carries its number.
exempted: dict[str, int] = {}


def scope_of(path: Path) -> str:
    """Returns the coverage key a file belongs to.

    Args:
        path: The file being read.

    Returns:
        The suffix of the `examined` key, so an empty scope is visible as
        itself rather than hidden inside a large total.
    """
    where = relative(path)
    if where.startswith("frontend/maquette/design/src"):
        return "shell"
    if where.startswith("frontend/maquette/harness"):
        return "harness tools" if path.suffix == ".mjs" else "harness"
    if where.startswith("frontend/maquette/"):
        return "servers"
    if where.startswith("frontend/src"):
        return "app"
    if where.startswith("scripts/"):
        return "repository tools"
    if where.startswith("tests/"):
        return "tests"
    return "package"


# ── arm 1: strings ───────────────────────────────────────────────────────────
#
# A string is read as a STRING, never as a span between two quote characters: an
# apostrophe inside a comment (« the panel's own vocabulary ») closes nothing,
# and a scanner that thinks it does reports the comment's prose as a literal.
# Python is read through `tokenize`, which is exact; TypeScript through the small
# scanner below, which tracks comments, strings and templates.

HOLD_LABEL = re.compile(
    r"""(?:\bcheck|\bJournal|\bjournal\.check)\(\s*[frbuFRBU]{0,2}"""
    r"""(?P<q>'''|\"\"\"|'|")"""
    r"""(?P<body>(?:\\.|(?!(?P=q))[^\\])*)(?P=q)""", re.S)

# What the app RENDERS is quoted, in this repository's own convention, inside
# guillemets. A quotation is not a French name in the code — it is the code
# naming what the reader of the interface sees — so it is removed before judging.
QUOTED_UI = re.compile(r"«[^»]*»")

# The text between two tags. Interface copy in JSX carries no quotes at all, so
# a scanner that only reads string literals walks straight past the very thing
# arm 1 exists to find: `<p>Réglages du système</p>` is not a literal.
JSX_TEXT = re.compile(r">([^<>{}]+)<")


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
    found = WORD.findall(body)
    # Lowercase in the SOURCE for the FUNCTION words only: French prose is
    # lowercase, and `LA`/`EST`/`DES` are abbreviations. An interface LABEL is
    # capitalised by nature — « Fermer » — so the label vocabulary reads every
    # case.
    words = {deaccent(word).lower() for word in found}
    lowercase = {deaccent(word).lower() for word in found if word.islower()}
    hits = sorted(lowercase & FRENCH_FUNCTION_WORDS)
    if len(hits) >= 2:
        return f"French function words {hits}"
    # A tool message may NAME the button it presses — « a Retour from the sheet
    # lands on … » — and that name is capitalised. Inside the application's own
    # code there is no such excuse, so there the label vocabulary reads every
    # case.
    labels = sorted((lowercase if quoting_allowed else words) & FRENCH_UI_WORDS)
    if labels:
        return f"French interface words {labels}"
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
        if not 1 <= candidate <= len(lines):
            continue
        line = lines[candidate - 1]
        found = PRAGMA.search(line)
        # A pragma written INSIDE a string is not a pragma. Without this, one
        # literal reading `"# french-ok: …"` licensed its neighbours.
        if found and not inside_quotes(line, found.start()):
            return found.group("reason").strip()
    return None


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


def remedy(path: Path) -> str:
    """Returns where this file's French is supposed to go instead.

    Args:
        path: The file the violation was found in.

    Returns:
        The sentence the violation ends with. A `scripts/` tool has no i18n
        bundle to be sent to, and telling its author to put a message in the
        front-end's resource file would be advice nobody can follow.
    """
    if scope_of(path) in {"repository tools", "harness tools", "harness"}:
        return "a developer tool speaks English"
    return "interface text belongs in design/src/i18n/fr.json"


def check_strings(violations: list[str]) -> None:
    """Runs the string arm over the shell, the servers and the hold labels."""
    strict: list[Path] = [p for p in SHELL.rglob("*") if p.is_file()
                          and p.suffix in {".ts", ".tsx"} and "i18n" not in p.parts]
    strict += [MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
    strict += sorted(HARNESS.glob("*.mjs"))
    # The repository's own tools speak to a DEVELOPER, so they speak English.
    # (The `personalscraper` CLI is a different case entirely: it speaks to the
    # OPERATOR, in French, and it is interface — no arm reads it.)
    # This file is the one exception the arm makes for itself: its French IS its
    # subject — the lexicon is a list of French words, and pragmas on a word list
    # would say nothing a reader does not already see.
    # `rglob`: `scripts/ops/` holds nine more tools one level down, and a glob
    # one level deep read none of them. A scope is checked the same way a name
    # is — `scripts/` is not `scripts/ops/`.
    strict += [p for p in sorted(SCRIPTS.rglob("*.py"))
               if p.name != Path(__file__).name]
    for path in sorted(strict):
        source = read(path)
        lines = source.splitlines()
        literals = (python_string_literals(source) if path.suffix == ".py"
                    else script_string_literals(source))
        examined[f"string literals / {scope_of(path)}"] += len(literals)
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
                f"({reason}) — {remedy(path)}: {body[:60]!r}")

        # The text BETWEEN two tags. Interface copy in JSX carries no quotes,
        # so the literal scan above walks straight past the commonest shape of
        # the very thing this arm exists to find.
        if path.suffix == ".tsx":
            for match in JSX_TEXT.finditer(source):
                text = match.group(1)
                if not text.strip():
                    continue
                examined["rendered text / shell"] += 1
                reason = offending_string(text)
                if not reason:
                    continue
                line_no = source.count("\n", 0, match.start()) + 1
                if pragma_on(lines, line_no):
                    continue
                violations.append(
                    f"{relative(path)}:{line_no}: French text rendered from the "
                    f"code ({reason}) — {remedy(path)}: {text.strip()[:60]!r}")

    for path in sorted(HARNESS.glob("*.py")):
        source = read(path)
        lines = source.splitlines()
        for match in HOLD_LABEL.finditer(source):
            examined["hold labels / harness"] += 1
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
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            # `self.dossier = …` is how a French field name usually arrives.
            names.append((node.attr, node.lineno))
        elif isinstance(node, ast.keyword) and node.arg:
            names.append((node.arg, getattr(node, "lineno", 0) or 0))
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            names.append((node.name, node.lineno))
    return names


def check_identifiers(violations: list[str]) -> None:
    """Runs the identifier arm over the shell, the servers, the harness, the tools."""
    python = ([MAQUETTE / "serve.py", MAQUETTE / "resync.py"]
              + sorted(HARNESS.glob("*.py"))
              + [p for p in sorted(SCRIPTS.rglob("*.py"))
                 if p.name != Path(__file__).name]
              # `frontend/scripts/` is not `scripts/`, and that one letter of
              # scope left an entire tool — 18 French names, `SORTIE`, `JAUNE`,
              # `anneau_depuis_staging` — outside every arm while the gate
              # reported no violation.
              + sorted((ROOT / "frontend" / "scripts").glob("*.py"))
              + sorted((ROOT / "personalscraper").rglob("*.py"))
              + sorted((ROOT / "tests").rglob("*.py")))
    for path in python:
        source = read(path)
        declarations = python_declarations(source)
        examined[f"declared identifiers / {scope_of(path)}"] += len(declarations)
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
    web += [p for p in (ROOT / "frontend" / "src").rglob("*")
            if p.is_file() and p.suffix in {".ts", ".tsx"}]
    for path in sorted(web):
        if "i18n" in path.parts:
            continue
        source = read(path)
        for match in TS_DECLARATION.finditer(source):
            examined[f"declared identifiers / {scope_of(path)}"] += 1
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

# `docs/` is the ONE tree this arm does not walk: dated records keep the names
# they were written with, and rewriting a record would falsify it.
UNWATCHED_ROOTS = ("docs/",)


def tracked_paths() -> list[str]:
    """Returns every path in the repository this arm watches.

    The WHOLE repository, minus `docs/` — four named roots used to be the scope,
    which left `hooks/`, `config.example/`, `.github/` and the root itself
    unwatched while the docstring said « anywhere ».

    Untracked-but-not-ignored files are listed too (`--others
    --exclude-standard`): a file created five minutes ago is exactly the one
    this arm exists to catch, and it is not tracked until it is added — a gate
    that only reads the index says nothing until after the commit it should
    have blocked.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True)
    return sorted({p for p in listed.stdout.split("\0")
                   if p and not p.startswith(UNWATCHED_ROOTS)})


def check_file_names(violations: list[str]) -> None:
    """Runs the file-name arm over every tracked path segment."""
    seen: set[tuple[str, str]] = set()
    for path in tracked_paths():
        for segment in path.split("/"):
            examined["path segments / repository"] += 1
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
        tree = ast.parse(read(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                examined["class names / python"] += 1
                hits = french_tokens_in(node.name, relative(path))
                if hits or has_accent(node.name):
                    violations.append(
                        f"{relative(path)}:{node.lineno}: French class name "
                        f"{node.name!r} ({', '.join(hits) or 'accented'})")

    code_class = re.compile(r"\bclass\s+(?P<name>[A-Za-z_$][\w$À-ɏ]*)")
    typescript = [p for p in SHELL.rglob("*")
                  if p.is_file() and p.suffix in {".ts", ".tsx"}]
    typescript += [p for p in (ROOT / "frontend" / "src").rglob("*")
                   if p.is_file() and p.suffix in {".ts", ".tsx"}]
    for path in sorted(typescript):
        source = read(path)
        for match in code_class.finditer(source):
            examined["class names / typescript"] += 1
            name = match.group("name")
            hits = french_tokens_in(name, relative(path))
            if hits or has_accent(name):
                line_no = source.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{relative(path)}:{line_no}: French class name {name!r} "
                    f"({', '.join(hits) or 'accented'})")

    # `rglob`, and the whole styles tree: `ps/tokens/` holds six real
    # stylesheets and `globals.css` sits beside `ps/`, all of them unread while
    # the arm globbed one directory one level deep.
    # Every stylesheet under `frontend/src`, not only those under `styles/`:
    # four sit beside the component they dress (`ds/LogLine.css`,
    # `ds/StatPanel.css`, `ds/StatusDot.css`, `pipeline/PipelineStepper.css`)
    # and declared 49 class names no arm read.
    sheets = [FRAGMENT] + sorted((ROOT / "frontend" / "src").rglob("*.css"))
    for path in sheets:
        if not path.is_file():
            continue
        source = read(path)
        if path is FRAGMENT:
            # The fragment is one document: only its <style> blocks declare CSS.
            source = "\n".join(
                m.group(1) for m in re.finditer(
                    r"<style[^>]*>(.*?)</style>", source, re.S))
        declared = declared_css_classes(source)
        examined["declared CSS classes / "
                 + ("fragment" if path == FRAGMENT else "extracted")] += len(declared)
        for name, line_no in declared.items():
            if allowed_class(name, allowed):
                continue
            hits = french_tokens_in_flat(name)
            if hits or has_accent(name):
                violations.append(
                    f"{relative(path)}:{line_no}: French CSS class {name!r} "
                    f"({', '.join(hits) or 'accented'}) — a class name is one "
                    "name shared by four worlds")


def vocabulary(debt_only: bool = False) -> set[str]:
    """Returns the words this codebase's names are built from.

    Args:
        debt_only: When true, returns only the words below the debt banner —
            French on purpose, and owed by one file.

    Returns:
        The set of words, lower-cased.
    """
    words, below = set(), False
    for line in VOCABULARY.read_text(encoding="utf-8").splitlines():
        if line.startswith(DEBT_BANNER):
            below = True
        if not line.strip() or line.startswith("#"):
            continue
        # Without the flag this is the WHOLE vocabulary, debt included: the
        # engine's names must still pass the arm that reads them. What the
        # flag isolates is who may BORROW those words, which is one file.
        if not debt_only or below:
            words.add(line.strip().lower())
    return words


def check_french_debt(violations: list[str]) -> None:
    """Refuses a debt word anywhere but the one file that owes it.

    The vocabulary was seeded FROM the codebase, so every French name still
    standing quietly contributed its own word and the arm reading that file
    certified them. Naming the debt is only half of it — the other half is
    that it must not grow: a new name built from `apparence` or `tris`
    outside the dying engine would inherit an exemption nobody granted it.

    Args:
        violations: The accumulator every arm appends to.
    """
    owed = vocabulary(debt_only=True)
    if not owed:
        # Deleting the BANNER alone would fold every French word back into the
        # general vocabulary and silence this arm without removing a thing —
        # the section and the file it exists for go together, or neither does.
        if (ROOT / DEBT_FILE).exists() and DEBT_BANNER not in VOCABULARY.read_text(
                encoding="utf-8"):
            violations.append(
                f"{relative(VOCABULARY)}: the debt banner is gone while "
                f"{DEBT_FILE} is still here — either the words below it moved "
                "back in unmarked, or the section was removed before the file "
                "it was written for")
        return
    examined["french debt words / vocabulary"] += len(owed)
    # The app is read too: a debt word borrowed in `frontend/src` would be no
    # less an exemption nobody granted, and it is not the engine's file.
    sources = [p for p in SHELL.rglob("*")
               if p.is_file() and p.suffix in {".ts", ".tsx", ".js"}
               and "i18n" not in p.parts and relative(p) != DEBT_FILE]
    sources += [p for p in (ROOT / "frontend" / "src").rglob("*")
                if p.is_file() and p.suffix in {".ts", ".tsx"}]
    for path in sorted(sources):
        raw = read(path)
        lines = raw.splitlines()
        source = code_only(raw)
        for match in re.finditer(
                r"(?:function|const|let|var|class|type|interface)\s+"
                r"([A-Za-z_$][\w$]*)", source):
            name = match.group(1)
            line_no = source[: match.start()].count("\n") + 1
            # Same as the vocabulary arm: an empty reason grants nothing.
            if pragma_on(lines, line_no):
                continue
            borrowed = [w for w in split_identifier(name) if w.lower() in owed]
            if borrowed:
                violations.append(
                    f"{relative(path)}:{line_no}: {name!r} borrows "
                    f"{', '.join(repr(w) for w in borrowed)} from the French "
                    f"words {DEBT_FILE} still owes — that exemption is the "
                    "engine's alone, and it dies with it")


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


def check_vocabulary(violations: list[str]) -> None:
    """Refuses a declared name built from a word this codebase does not use.

    THE OTHER ARMS ASK « IS THIS FRENCH? », and that question is only ever as
    good as the list of French words behind it. That list had holes — `suivante`,
    `trier`, `fermer`, `afficher`, `chargement`, `compte`, `monde` were all
    invisible to it — so « no violation » quietly meant « none among the words we
    thought of », and a hundred and forty French names sat under it unremarked.

    This arm asks the opposite: « is this word one we use? ». The vocabulary is
    a file in the repository, so it has no holes by construction — a name built
    from a word nobody wrote down is refused, whatever language it came from.

    It reads `.js` as well as `.ts`/`.tsx`, which is what finally puts the
    legacy engine under a guard: its identifiers are English now, so the words
    they are made of are simply in the list.

    Args:
        violations: The accumulator every arm appends to.
    """
    words = vocabulary()
    if not words:
        violations.append(f"{relative(VOCABULARY)} is empty — the arm reading it "
                          "would accept every name ever written")
        return
    sources = [p for p in SHELL.rglob("*")
               if p.is_file() and p.suffix in {".ts", ".tsx", ".js"}
               and "i18n" not in p.parts]
    for path in sorted(sources):
        raw = read(path)
        lines = raw.splitlines()
        # Comments and strings are blanked first: a name extractor that reads
        # prose invents declarations — « the type this module exports » yields
        # `this` — and eighty of those buried the four real findings.
        source = code_only(raw)
        for match in re.finditer(
                r"(?:function|const|let|var|class|type|interface)\s+"
                r"([A-Za-z_$][\w$]*)", source):
            name = match.group(1)
            if name in FROZEN_IDENTIFIERS:
                continue
            line_no = source[: match.start()].count("\n") + 1
            # A pragma citing NOTHING is not a grant (module docstring):
            # `is not None` accepted a bare `french-ok:` and silenced the arm.
            if pragma_on(lines, line_no):
                continue
            examined["name words / shell"] += 1
            unknown = [w for w in split_identifier(name)
                       if len(w) > 1 and w.lower() not in words]
            if unknown:
                violations.append(
                    f"{relative(path)}:{line_no}: {name!r} is built from "
                    f"{', '.join(repr(w) for w in unknown)}, which "
                    f"{'is' if len(unknown) == 1 else 'are'} not in "
                    f"{relative(VOCABULARY)} — rename it in English, or add the "
                    "word there if the codebase really speaks it")


def check_data_attributes(violations: list[str]) -> None:
    """Refuses a `data-*` attribute NAME built from a word this codebase lacks.

    CLAUDE.md brings these names under the rule — a `data-*` name is a name
    someone chose — and until now nothing read them. Nineteen were renamed by
    hand in the same wave that wrote the rule, and four were missed:
    `data-prendre`, `data-maintrub`, `data-qreg` and `data-apparence` stayed,
    green, because no arm looked. A rule with no arm is a sentence in a file.

    The VALUES are not read, and must not be: `data-go="profil"` names a page,
    and a page id is an address.

    It asks the vocabulary's question rather than « is this word French? »,
    because the names here are abbreviations — `rub` for « rubrique » is
    invisible to any list of French words, and `maintopic` is not.

    Args:
        violations: The accumulator every arm appends to.
    """
    words = vocabulary()
    sources = [p for p in SHELL.rglob("*")
               if p.is_file() and p.suffix in {".ts", ".tsx", ".js"}]
    # `design/index.html` is the application shell's markup since SP4-fin wave
    # 2, and it was read by no arm: `id="coquille"` — the React mount point —
    # sat there in French while every gate was green.
    # And `frontend/index.html` beside it: the maquette's twin was added when
    # `id="coquille"` was found in it, and the PRODUCTION app's own shell markup
    # — the one actually served — was left unread by the same arm.
    sources += [FRAGMENT, MAQUETTE / "design" / "index.html",
                ROOT / "frontend" / "index.html"]
    sources += [p for p in (ROOT / "frontend" / "src").rglob("*")
                if p.is_file() and p.suffix in {".ts", ".tsx", ".css"}]
    for path in sorted(sources):
        source = read(path)
        for match in re.finditer(
                r"\bdata-([a-zA-Z][\w-]*)"
                r"|\bid=\"([A-Za-z][\w-]*)\""
                # `id='coquille'` and `id={'coquille'}` name the same element as
                # `id="coquille"`; only the double-quoted spelling was read.
                r"|\bid='([A-Za-z][\w-]*)'"
                r"|\bid=\{\s*['\"]([A-Za-z][\w-]*)['\"]\s*\}", source):
            name = (match.group(1) or match.group(2)
                    or match.group(3) or match.group(4))
            examined["data-* names / markup"] += 1
            line_no = source.count("\n", 0, match.start()) + 1
            unknown = [w for w in split_identifier(name)
                       if len(w) > 1 and w.lower() not in words]
            if unknown:
                violations.append(
                    f"{relative(path)}:{line_no}: the markup name "
                    f"{name!r} is built from "
                    f"{', '.join(repr(w) for w in unknown)}, which "
                    f"{'is' if len(unknown) == 1 else 'are'} not in "
                    f"{relative(VOCABULARY)} — name it in English, or add the "
                    "word there if the codebase really speaks it")


def check_shell_scripts(violations: list[str]) -> None:
    """Refuses French in a `.sh` — every line of one is the tool speaking.

    NO ARM READ `.sh` AT ALL, and three of this repository's nine shell scripts
    were written in French throughout — the two deploy scripts and the poller,
    which between them are the only sanctioned way to put anything in front of
    the operator. The rule has always covered them: a message a tool prints is
    English. Nothing had ever looked.

    A shell script has no i18n bundle and renders nothing to a reader of the
    interface, so the distinction the other arms draw — code here, copy there —
    does not exist in one. Every line is read, comment and message alike.

    Args:
        violations: The accumulator every arm appends to.
    """
    for relative_path in tracked_paths():
        if not relative_path.endswith(".sh"):
            continue
        path = ROOT / relative_path
        if not path.is_file():
            continue
        lines = read(path).splitlines()
        for line_no, line in enumerate(lines, start=1):
            examined["lines / shell scripts"] += 1
            reason = offending_string(line)
            if not reason:
                continue
            if pragma_on(lines, line_no):
                continue
            violations.append(
                f"{relative_path}:{line_no}: French in a shell script "
                f"({reason}) — a developer tool speaks English: {line.strip()[:60]!r}")


def check_unread_javascript(violations: list[str]) -> None:
    """Refuses a `.js` under the shell that no arm reads, except the engine.

    Every arm above globs `.ts`/`.tsx`, so a JavaScript file under
    `design/src/` is examined by none of them. That is correct for exactly one
    file — the legacy engine, moved there byte for byte, whose French
    identifiers predate the rule and would be rewritten by a conversion, not by
    a rename. It is wrong for anything else: a NEW `.js` would be new code, in
    the one scope where nobody is looking.

    An implicit exclusion is what this file exists to distrust — it reports
    « no violation » about a scope it never opened. So the exclusion is written
    down, and it is a list of one.

    Args:
        violations: The accumulator every arm appends to.
    """
    # Each entry is here because it was MOVED, not written: its French
    # identifiers predate the rule and only a conversion — not a rename — will
    # reach them. `legacy.js` is the engine; `states.js` is the scenario table
    # lifted out of it, whose entries call the engine's own French names.
    allowed = {SHELL / "engine" / "legacy.js", SHELL / "states.js"}
    unread = {path for path in SHELL.rglob("*.js") if path.is_file()}
    for path in sorted(unread - allowed):
        violations.append(
            f"{relative(path)} is JavaScript under the shell, which no arm "
            "reads — write it in TypeScript, or name it here with the reason "
            "it is exempt")
    for path in sorted(allowed - unread):
        violations.append(
            f"{relative(path)} is named as exempt but does not exist — the "
            "exemption outlived its subject")
    examined["unread javascript / shell"] += len(unread)


def check_app_interface_text(violations: list[str]) -> None:
    """Measures the French interface text `frontend/src` carries, and says so.

    THIS ARM DOES NOT REFUSE. `frontend/src` is the React application the
    maquette shell is being built to replace, and it has no i18n layer at all —
    no `i18n/` directory, no `useTranslation`. Its French is written straight
    into the components. The operator ruled that this is an ACCEPTED state
    rather than a defect: moving that copy into resources would be work thrown
    away with the app that holds it. §Language names two i18n surfaces — the
    maquette shell and `serve.py`'s pages — and this is deliberately neither.

    So why an arm at all? Because the string arm walks the shell, the servers,
    the harness tools and the repository tools, and NOT this tree — and an
    unread scope reports « no violation » about a place it never opened. That
    is how 842 French strings sat under a green gate, and how `id="coquille"`
    and three all-French shell scripts sat under it before them. An exemption
    nobody counts is indistinguishable from an oversight.

    The count is therefore published in the ledger beside every other scope. It
    reads the whole tree, so it drops to zero only if the tree empties — and
    the ledger already refuses a scope that examined NOTHING.

    Args:
        violations: The accumulator every arm appends to. Nothing is added:
            this arm measures, and the measurement is its whole output.
    """
    del violations  # measured, never refused — see the docstring above.
    app = ROOT / "frontend" / "src"
    french = 0
    for path in sorted(app.rglob("*")):
        if not path.is_file() or path.suffix not in {".ts", ".tsx"}:
            continue
        source = read(path)
        literals = script_string_literals(source)
        examined["interface text / app (exempt)"] += len(literals)
        french += sum(1 for _, body in literals if offending_string(body))
    exempted["french interface strings / app"] = french


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
    check_unread_javascript(violations)
    check_vocabulary(violations)
    check_data_attributes(violations)
    check_french_debt(violations)
    check_shell_scripts(violations)
    check_app_interface_text(violations)
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
    print("no-French guardrail: 4 arms + the vocabulary + the markup names + "
          "the engine's declared debt + the shell scripts + the "
          "unread-JavaScript ledger, no violation — read "
          + ", ".join(f"{count} {what}" for what, count in examined.items()))
    # Named out loud, every run. The operator ACCEPTED this French; what must
    # never happen again is it being invisible.
    for what, count in exempted.items():
        print(f"  exempt, counted, not refused: {count} {what}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

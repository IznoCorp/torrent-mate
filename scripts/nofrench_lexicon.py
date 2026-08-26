"""The lexicon the no-French guard judges by, and the helpers that read it.

SPLIT OUT OF `check-no-french.py`, which had grown to 1 411 non-blank lines
against a HARD ceiling of 1 000 that CLAUDE.md sets and `check-module-size.py`
enforces — except that `make check` only ever pointed that script at
`personalscraper/`, so the guard was 411 lines over a limit it was itself
supposed to help keep. A rule the project applies everywhere but to its own
tools is a rule with a hole in it.

What lives here is DATA and the reading of it — word lists, frozen exceptions,
the dictionary's declared false positives, and the small functions that
decompose a name or read a file. What stays there is the ARMS: the questions
asked of that data. The split is along that line and no other, so a reader
looking for « what does the guard refuse? » still finds every arm in one file.
"""

from __future__ import annotations

import re
import subprocess
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAQUETTE = ROOT / "frontend" / "maquette"
VOCABULARY = ROOT / "scripts" / "code-vocabulary.txt"
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
    "mediatheque", "nombre", "nombres", "panneau", "panneaux",
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
    # `maquette` used to sit here, exempted as a path segment because it was
    # listed as a French word above. It is not one: `maquette` is a naturalised
    # loanword in English — a preliminary model, the ordinary term in design and
    # architecture — and the dictionaries carry it. The operator confirmed that
    # reading on 2026-08-20, and it is worth recording WHY the old entry was
    # wrong rather than merely gone: its reason invoked « the operator's word
    # for the thing » without anyone having asked them. An exemption that
    # borrows an authority it never obtained is indistinguishable from an
    # oversight. It is in `code-vocabulary.txt` now, like any other word we use.
    "refonte": (
        "The legacy fragment (`refonte.html`), named verbatim by R72 and by "
        "every rule that reads it. It DIES at SP4-end; renaming a file on its "
        "way out buys nothing and costs every pointer at it."
    ),
}

# Files NOBODY WRITES. The vocabulary arm asks « is this word one we use? »,
# and that question is about a name someone CHOSE. A generated file's names are
# the generator's — `paths`, `webhooks`, `components`, `operations`, `$defs` are
# the OpenAPI and JSON Schema specifications' own words, arriving through
# `openapi-typescript`.
#
# THE ALTERNATIVE WAS WORSE, and it is why this is a file exemption rather than
# five new words. Adding them to `code-vocabulary.txt` would license them as
# names EVERYWHERE — including `defs`, which is an abbreviation the naming rule
# refuses outright. A vocabulary widened to accommodate a generator is a
# vocabulary that has stopped describing what this codebase writes.
#
# NARROW ON PURPOSE: only this arm skips these files. The arms that ask « is
# this French? » keep reading them, so French arriving through the contract's
# own descriptions would still be caught.
#
# AND IT IS NOT A HOLE SOMEONE MAY WIDEN BY HAND: the value names the command
# that produces the file and the two checks that hold it. One regenerates it and
# refuses any difference — the strongest proof, and it needs the generator, so
# it runs where the generator is. The other holds it against the contract by
# structure, needs nothing, and runs wherever this guard does. Naming only the
# first left the exemption unproven on every machine that reads it.
GENERATED_SOURCES = {
    "mocks/contract-types.d.ts": (
        "npm run generate-contract-types — from frontend/maquette/contract/openapi.json. Held two ways: `make check-contract-types` regenerates it and refuses any difference, which needs the generator and runs only where it is installed; and `scripts/check-mock-seeds.py --arm generated` holds it against the contract by structure, needs neither node nor the generator, and runs wherever the guards do — which is where THIS exemption is read."
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

# What the app RENDERS is quoted, in this repository's own convention, inside
# guillemets. A quotation is not a French name in the code — it is the code
# naming what the reader of the interface sees — so it is removed before judging.
QUOTED_UI = re.compile(r"«[^»]*»")


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
    # The prototype's classes were declared in one fragment and are declared in
    # `src/styles/` now. ONE SCOPE COVERS BOTH, and it seeds at zero like every
    # other counter: this entry stood at 1 for a while, which meant the vacuity
    # check — the entire purpose of this table — could never fire on it. A
    # counter that cannot reach zero is a counter that says nothing, and it
    # printed 241 for 240 while it said so.
    "declared CSS classes / maquette": 0,
    "declared CSS classes / app": 0,
    "unread javascript / shell": 0,
    "name words / shell": 0,
    "data-* names / markup": 0,
    "french debt words / vocabulary": 0,
    "lines / shell scripts": 0,
    "interface text / app (exempt)": 0,
    "name words / dictionary": 0,
    "string literals / tests": 0,
    "custom-property names / css": 0,
    "arms / self-description": 0,
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



DICTIONARY_EXCEPTIONS: dict[str, str] = {
    "api": "the interface, everywhere",
    "apis": "plural of the above",
    "conf": "configuration, abbreviated",
    "dont": "the English contraction, in `dont_stop` / `errors_dont_stop`",
    "dur": "durability, abbreviated (SQLite pragma)",
    "env": "environment, everywhere",
    "environ": "Python's `os.environ`",
    "invariants": "English plural, used of the web-UI invariants",
    "latin": "the script name, in `non_latin_title`",
    "lin": "linear, in the colour-space tests",
    "lister": "one that lists — `TorrentLister`",
    "lucide": "the icon library",
    "maint": "maintenance, abbreviated",
    "mut": "mutable / mutation, abbreviated",
    "nones": "plural of Python's `None`",
    "nonne": "a typo for `none` in one test name, kept until that test is renamed",
    "reclasses": "English verb, in `enqueue_other_with_kind_reclasses`",
    "redis": "the datastore",
    "repos": "git repositories, in `cross_repos`",
    "sel": "selector, abbreviated",
    "sep": "separator, abbreviated",
    "sonner": "the toast library",
    "sortable": "English adjective",
    "typer": "the CLI framework",
    "vals": "values, abbreviated",
    "ver": "version, abbreviated",
    "vite": "the bundler",
    # DATA, not names: category ids and media titles that appear in fixtures.
    "autres": "a category id — data, not a name",
    "livres": "a category id — data, not a name",
    "gourou": "a media title in a scraper fixture",
    "sur": "a media title in a fixture (« Sur écoute »)",
    "maquette": "named by the constitution §15 and R72 — the design reference itself",
    "saison": "the on-disk folder name (« Saison XX »), a real path, not a name",
}


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


# `docs/` is the ONE tree the file-name arm does not walk: dated records keep
# the names they were written with, and rewriting a record would falsify it.
UNWATCHED_ROOTS = ("docs/",)


def tracked_paths() -> list[str]:
    """Returns every path in the repository the guard watches.

    The WHOLE repository, minus `docs/` — four named roots used to be the scope,
    which left `hooks/`, `config.example/`, `.github/` and the root itself
    unwatched while the docstring said « anywhere ».

    Untracked-but-not-ignored files are listed too (`--others
    --exclude-standard`): a file created five minutes ago is exactly the one
    the arm exists to catch, and it is not tracked until it is added — a gate
    that only reads the index says nothing until after the commit it should
    have blocked.

    It lives here, with the corpora, because TWO arms walk it: the file-name
    arm and the shell-script arm, which is the only one whose corpus is `.sh`.

    Returns:
        Every watched path, repository-relative, sorted.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True)
    return sorted({p for p in listed.stdout.split("\0")
                   if p and not p.startswith(UNWATCHED_ROOTS)})

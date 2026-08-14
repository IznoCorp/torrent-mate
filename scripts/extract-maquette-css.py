#!/usr/bin/env python3
"""Extract the prototype's application CSS into the stylesheet the app ships.

`frontend/maquette/refonte.html` is the product (product-intent §15). Its
`<style>` element is physically split in two, and only the second half ships:

- **BLOCK 1 — PROTOTYPE HARNESS**: the phone frame, the demo bars, the design
  notes, the scenario switch. Never extracted.
- **BLOCK 2 — APPLICATION CSS**: everything the app renders.

This script lifts BLOCK 2, scopes every rule under `.tm`, and writes
`frontend/src/styles/ps/app-surface.css`. The app imports that file; nobody
edits it. **Editing the generated file by hand is the defect, not a shortcut** —
`--check` re-runs the extraction and fails on any difference, which is the same
guard that protects `openapi.json` / `schema.d.ts`.

Extraction works from an ALLOWLIST, never a blocklist: `regions.json` →
`exportedSelectors` names what may ship, so a prototype-only helper can never
silently reach production by being forgotten. `frontend/maquette/harness/
export.py` is the other half of that contract — it fails on any BLOCK 2 class
that is neither on the allowlist nor classified as harness, so the two together
mean « listed and exported » and « exported and listed ».

Scoping under `.tm` rather than shipping bare selectors is what lets this
stylesheet coexist with the app's own: the prototype styles `.card`, and so
does half the web.

Usage:
    python3 scripts/extract-maquette-css.py            # write the stylesheet
    python3 scripts/extract-maquette-css.py --check    # fail on drift
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

RACINE = pathlib.Path(__file__).resolve().parent.parent
PROTOTYPE = RACINE / "frontend" / "maquette" / "refonte.html"
REGIONS = RACINE / "frontend" / "maquette" / "regions.json"
SORTIE = RACINE / "frontend" / "src" / "styles" / "ps" / "app-surface.css"

# The scope every rule is nested under. One class, on the app's own root.
PORTEE = ".tm"

ENTETE = """/* GENERATED — do not edit.
 *
 * Extracted from `frontend/maquette/refonte.html` (BLOCK 2 — APPLICATION CSS)
 * by `scripts/extract-maquette-css.py`, and scoped under `{portee}`.
 *
 * The prototype IS the product (product-intent §15). A pixel changes there and
 * is extracted here; a hand edit to this file is reverted by the drift guard in
 * `make check`, because a retyped value does not merely risk drifting — it
 * CONCEALS a defect in the reference, since the copy becomes the only place
 * anyone ever looks.
 *
 * {compte} rules, from {classes} allowlisted selectors.
 * {ecartees} rules were dropped as prototype harness.
 *
 * Declared BOTH exported and harness, and read as exported because extraction
 * only ever looks at BLOCK 2: {ambigues}.
 */
"""


def bloc_application(source: str) -> str:
    """Returns BLOCK 2 of the prototype's `<style>`, comments included.

    Args:
        source: The prototype's full text.

    Returns:
        The CSS text from BLOCK 2's header comment to the closing `</style>`.

    Raises:
        SystemExit: When the harness/app separation is not found — a prototype
            without it has nothing this script may safely ship.
    """
    i = source.find("BLOCK 2")
    if i < 0:
        sys.exit("BLOCK 2 introuvable : la maquette a perdu sa séparation "
                 "harnais / application, et rien ne peut être extrait sans elle.")
    # Back to the OPENER of the header comment: slicing on « BLOCK 2 » leaves an
    # orphan `*/` behind, and the header's own prose then parses as selectors.
    i = source.rfind("/*", 0, i)
    fin = source.find("</style>", i)
    if fin < 0:
        sys.exit("le `<style>` de la maquette ne se ferme pas.")
    return source[i:fin]


def contrat() -> tuple[set[str], set[str]]:
    """The two lists `regions.json` keeps, and they are not symmetric.

    `exportedSelectors` is the allowlist: what may ship. `harnessSelectors` is
    the prototype's own chrome — the phone frame, the demo bars, the design
    notes — listed so its exclusion is EXPLICIT rather than implied. Some of it
    lives inside BLOCK 2 because it dresses the same surfaces, so it has to be
    dropped by name rather than refused: a harness class is not a forgotten
    export, and treating it as one would stop the extraction on every run.

    Returns:
        A `(exported, harness)` pair of selector sets.
    """
    import json

    with REGIONS.open(encoding="utf-8") as f:
        donnees = json.load(f)
    return set(donnees["exportedSelectors"]), set(donnees.get("harnessSelectors", []))


def regles(css: str) -> list[tuple[str, str, str]]:
    """Splits CSS into its rules, keeping at-rules whole.

    Comments are dropped: they document the prototype's decisions and belong
    with it, not in a generated file nobody reads.

    Args:
        css: The CSS text of BLOCK 2.

    Returns:
        A list of `(at_rule, selector, body)` triples. `at_rule` is the
        enclosing `@media` / `@supports` condition, or `""` at the top level.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    sorties: list[tuple[str, str, str]] = []
    i = 0
    contexte = ""
    while i < len(css):
        ouvre = css.find("{", i)
        if ouvre < 0:
            break
        tete = css[i:ouvre].strip()
        # Find this block's matching close, counting nesting.
        profondeur = 0
        j = ouvre
        while j < len(css):
            if css[j] == "{":
                profondeur += 1
            elif css[j] == "}":
                profondeur -= 1
                if profondeur == 0:
                    break
            j += 1
        corps = css[ouvre + 1 : j]
        if tete.startswith("@") and not tete.startswith("@keyframes"):
            # A conditional group: recurse into it, carrying the condition.
            for _, sel, cps in regles(corps):
                sorties.append((tete, sel, cps))
        elif tete.startswith("@keyframes"):
            # Animations have no selector to allowlist and no scope to take.
            sorties.append(("", tete, corps))
        elif tete:
            sorties.append((contexte, tete, corps))
        i = j + 1
    return sorties


def porter(selecteur: str) -> str:
    """Scopes one selector list under {PORTEE}.

    `:root` becomes the scope itself rather than a descendant of it: custom
    properties declared on the document's root must land on the app's root, or
    every `var()` under it resolves to nothing.

    Args:
        selecteur: A comma-separated selector list.

    Returns:
        The same list, each part scoped.
    """
    parties = []
    for part in selecteur.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith(":root") or part == "html" or part == "body":
            parties.append(PORTEE + part[len(part.split()[0]):] if " " in part else PORTEE)
        elif part.startswith("@"):
            parties.append(part)
        else:
            parties.append(f"{PORTEE} {part}")
    return ", ".join(parties)


def classes_de(selecteur: str) -> set[str]:
    """The class names a selector list mentions."""
    return set(re.findall(r"\.([a-zA-Z][\w-]*)", selecteur))


def construire() -> str:
    """Builds the stylesheet the app ships.

    Returns:
        The full CSS text, header included.

    Raises:
        SystemExit: When a rule mentions a class the allowlist does not carry.
            That is the allowlist doing its job: a selector reaches production
            only by being listed, never by being forgotten.
    """
    source = PROTOTYPE.read_text(encoding="utf-8")
    permis, harnais = contrat()
    classes_permises = set()
    for s in permis:
        classes_permises |= classes_de(s)
    classes_harnais = set()
    for s in harnais:
        classes_harnais |= classes_de(s)
    # A class on BOTH lists is a genuine contradiction in the contract, and it
    # is not hypothetical: eight of them are, because the prototype's demo bars
    # and the app's own bars share their names — one set lives in BLOCK 1, the
    # other in BLOCK 2. Extraction only ever looks at BLOCK 2, so the reading
    # that fits is « exported ». It is REPORTED rather than resolved in
    # silence: a contradiction nobody is told about is how the wrong reading
    # survives for a year.
    ambigues = sorted(classes_harnais & classes_permises)
    classes_harnais -= classes_permises

    lignes: list[str] = []
    gardees = 0
    ecartees = 0
    refusees: dict[str, set[str]] = {}
    for condition, selecteur, corps in regles(bloc_application(source)):
        classes = classes_de(selecteur)
        if classes and classes <= classes_harnais:
            ecartees += 1
            continue
        inconnues = classes - classes_permises - classes_harnais
        if inconnues:
            refusees.setdefault(selecteur.strip(), set()).update(inconnues)
            continue
        corps = "\n".join(f"    {l.strip()}" for l in corps.strip().splitlines() if l.strip())
        if not corps:
            continue
        regle = f"{porter(selecteur)} {{\n{corps}\n}}"
        if condition:
            regle = f"{condition} {{\n" + "\n".join("  " + l for l in regle.splitlines()) + "\n}"
        lignes.append(regle)
        gardees += 1

    if refusees:
        detail = "\n".join(f"  {sel} → {', '.join(sorted(cls))}"
                           for sel, cls in sorted(refusees.items())[:20])
        sys.exit(
            "des règles nomment des classes que `regions.json` n'autorise pas.\n"
            "L'extraction part d'une LISTE BLANCHE : ajoutez-les à "
            "`exportedSelectors`, ou classez-les comme harnais.\n" + detail)

    entete = ENTETE.format(portee=PORTEE, compte=gardees, classes=len(permis),
                           ecartees=ecartees,
                           ambigues=", ".join(ambigues) or "aucune")
    return entete + "\n" + "\n\n".join(lignes) + "\n"


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--check", action="store_true",
                         help="ne rien écrire ; sortir en erreur si le fichier a dérivé")
    args = parseur.parse_args()

    attendu = construire()
    if args.check:
        if not SORTIE.is_file():
            print(f"extract-maquette-css: {SORTIE.relative_to(RACINE)} manque — "
                  "lancez `python3 scripts/extract-maquette-css.py`.", file=sys.stderr)
            return 1
        actuel = SORTIE.read_text(encoding="utf-8")
        if actuel != attendu:
            print("extract-maquette-css: la feuille de style a DÉRIVÉ de la maquette.\n"
                  "Une modification à la main de ce fichier généré est le défaut, "
                  "pas un raccourci : changez la maquette, puis relancez\n"
                  "  python3 scripts/extract-maquette-css.py", file=sys.stderr)
            return 1
        print(f"extract-maquette-css: à jour ({len(attendu.splitlines())} lignes).")
        return 0

    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(attendu, encoding="utf-8")
    print(f"extract-maquette-css: {SORTIE.relative_to(RACINE)} écrit "
          f"({len(attendu.splitlines())} lignes).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

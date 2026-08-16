"""R76 — the shell owns navigation through one door, and every call through
it is its own history entry.

`aller()` is the ONLY function in `design/src/` allowed to call
`routeur.navigate()` (Task 9's comment states the law: the router library
batches its commits into a microtask, so two writes issued in the same task
would merge into one entry unless something flushes between them — and the
legacy unwinding logic COUNTS entries). A second call site calling
`navigate()` on its own, without the same immediate `historique.flush()`,
would silently start losing history depth under exactly the condition that
matters most: two navigations decided in the same synchronous handler.

What this holds to:

1. `navigate(` appears in `design/src/` exactly once, comments blanked, and
   that one call sits inside `aller()`'s own body — a source-level count,
   the same discipline R74 already holds the legacy engine's raw
   `history.*` calls to.
2. A round trip through the single door — `__ecrans.profil(t)` (the bridge
   a legacy call site uses) onto the screen, then a navigation back to `/`
   — writes ONE entry per call and back walks them in reverse. `aller()`
   itself is not exposed to `window` (by design — it is a module export,
   not a debugging hook), so the return leg is driven on `window.__routeur`
   directly: the SAME router instance `aller()` closes over, given the
   SAME two-line body (`navigate()` then `history.flush()`) it runs.
   Walking back is judged by the screen's OWN observed state at each stop,
   never by `history.length` — a count that would still look right even if
   two pushes had merged into one and a third, unrelated entry happened to
   sit underneath.
3. Two `__ecrans.profil(...)` calls issued in the SAME task — no `await`
   between them — still produce TWO separate entries, walked back one at a
   time and judged the same way: by which title's screen the walk reveals,
   not by a length that a merge would not visibly change.
"""
import asyncio
import json
import pathlib
import re
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import RACINE, Journal, ouvrir

DESIGN_SRC = RACINE / "design" / "src"

TITRE = "Silo"
TITRE_AUTRE = "House of the Dragon"

ETAT_ECRAN = """() => {
  const ecran = document.querySelector('.screen.open');
  return {
    ouvert: !!ecran,
    cle: ecran?.dataset.cle ?? null,
    pathname: location.pathname,
  };
}"""


def sans_commentaires_legers(source):
    """Blanks `//` line comments in hand-written TypeScript source.

    `design/src/` is authored directly — no minifier, no dense regular
    expressions squeezed onto one line — so a per-line, quote-tracking scan
    telling a `//` that opens a comment from one sitting inside a string or
    template literal is enough here; R74's fuller lexer answers a question
    this smaller, human-written source never asks (a multi-line template
    literal spanning a `//` is not a shape any file below has today, and
    this function does not claim to survive one).

    Args:
        source: TypeScript, as text.

    Returns:
        The same text with every `//…` line-comment tail blanked.
    """
    lignes = []
    for ligne in source.splitlines():
        guillemet = None
        i = 0
        while i < len(ligne):
            c = ligne[i]
            if guillemet:
                if c == "\\" and i + 1 < len(ligne):
                    i += 2
                    continue
                if c == guillemet:
                    guillemet = None
                i += 1
                continue
            if c in "\"'`":
                guillemet = c
                i += 1
                continue
            if ligne[i : i + 2] == "//":
                ligne = ligne[:i]
                break
            i += 1
        lignes.append(ligne)
    return "\n".join(lignes)


def compter_navigate_hors_aller(design_src):
    """Counts `navigate(` calls under `design/src/`, and how many sit
    outside `aller()`'s own body in `coquille.tsx`.

    Args:
        design_src: The `design/src/` directory.

    Returns:
        `(total, hors_aller)` — the total call count after comments are
        blanked, and how many of those are NOT inside `export function
        aller(`'s body.
    """
    total = 0
    hors_aller = 0
    fichiers = sorted(design_src.rglob("*.ts")) + sorted(design_src.rglob("*.tsx"))
    for fichier in fichiers:
        nettoye = sans_commentaires_legers(fichier.read_text(encoding="utf-8"))
        positions = [m.start() for m in re.finditer(r"\bnavigate\(", nettoye)]
        total += len(positions)
        if fichier.name != "coquille.tsx":
            hors_aller += len(positions)
            continue
        debut, fin = bornes_corps_aller(nettoye)
        hors_aller += sum(1 for pos in positions if not (debut >= 0 and debut <= pos <= fin))
    return total, hors_aller


def bornes_corps_aller(nettoye):
    """Finds `aller()`'s own body span, braces balanced.

    The parameter list is itself an object type literal (`vers: {…}`) — its
    braces close and reopen before the function body's own `{` is reached,
    so the boundary cannot be the first `\n}` after the signature; that
    matches the PARAMETER type's closing brace, not the body's. This walks
    parens first to find where the parameter list ends, then walks braces
    from the function body's own opening brace to find where it ends.

    Args:
        nettoye: Comment-blanked TypeScript source.

    Returns:
        `(debut, fin)` character offsets spanning `aller()`'s body
        (inclusive of both braces), or `(-1, -1)` if not found.
    """
    debut = nettoye.find("export function aller(")
    if debut < 0:
        return -1, -1
    profondeur, i = 0, nettoye.index("(", debut)
    while i < len(nettoye):
        if nettoye[i] == "(":
            profondeur += 1
        elif nettoye[i] == ")":
            profondeur -= 1
            if profondeur == 0:
                break
        i += 1
    corps_debut = nettoye.index("{", i)
    profondeur, j = 0, corps_debut
    while j < len(nettoye):
        if nettoye[j] == "{":
            profondeur += 1
        elif nettoye[j] == "}":
            profondeur -= 1
            if profondeur == 0:
                return corps_debut, j
        j += 1
    return corps_debut, len(nettoye)


async def main():
    journal = Journal("R76 — la navigation encadrée")

    # ─── Hold 1: one door, source-checked ──────────────────────────────
    total, hors_aller = compter_navigate_hors_aller(DESIGN_SRC)
    journal.verifier(
        "navigate( n'apparaît que dans le corps d'aller()",
        total == 1 and hors_aller == 0,
        f"{total} appel(s) au total, {hors_aller} hors d'aller()")

    async with async_playwright() as p:
        navigateur = await p.chromium.launch(channel="chrome")

        # ─── Hold 2: one entry per call, walked back in reverse ────────
        ctx, pg = await ouvrir(navigateur)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        depart = await pg.evaluate(ETAT_ECRAN)
        journal.verifier("le point de départ n'a aucun écran ouvert",
                         not depart["ouvert"], depart["pathname"])

        await pg.evaluate(f"()=>window.__ecrans.profil({json.dumps(TITRE)})")
        await pg.wait_for_timeout(300)
        sur_profil = await pg.evaluate(ETAT_ECRAN)
        journal.verifier("__ecrans.profil() ouvre l'écran par la seule porte",
                         sur_profil["ouvert"] and sur_profil["cle"] == f"profil:{TITRE}",
                         sur_profil["pathname"])

        # aller() itself is not on window — its own two-line body (navigate,
        # then the SAME immediate flush) is run here on window.__routeur,
        # the instance aller() closes over.
        await pg.evaluate(
            "()=>{ window.__routeur.navigate({ to: '/' }); "
            "window.__routeur.history.flush(); }")
        await pg.wait_for_timeout(300)
        de_retour = await pg.evaluate(ETAT_ECRAN)
        journal.verifier("un aller() vers « / » ferme l'écran et écrit l'adresse",
                         not de_retour["ouvert"] and de_retour["pathname"] == "/",
                         de_retour["pathname"])

        await pg.go_back()
        await pg.wait_for_timeout(300)
        premier_retour = await pg.evaluate(ETAT_ECRAN)
        journal.verifier(
            "le premier retour retrouve l'écran du profil (compté par l'état observé)",
            premier_retour["ouvert"] and premier_retour["cle"] == f"profil:{TITRE}",
            premier_retour["pathname"])

        await pg.go_back()
        await pg.wait_for_timeout(300)
        second_retour = await pg.evaluate(ETAT_ECRAN)
        journal.verifier("le second retour quitte l'écran",
                         not second_retour["ouvert"], second_retour["pathname"])
        journal.verifier("aucune erreur JS pendant le voyage", not erreurs, str(erreurs))
        await ctx.close()

        # ─── Hold 3: two aller() calls in the SAME task, two entries ───
        ctx, pg = await ouvrir(navigateur)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        # No await between the two calls: exactly the same-task condition
        # the microtask-batching risk described above concerns.
        await pg.evaluate(
            f"()=>{{ window.__ecrans.profil({json.dumps(TITRE)}); "
            f"window.__ecrans.profil({json.dumps(TITRE_AUTRE)}); }}")
        await pg.wait_for_timeout(300)
        double = await pg.evaluate(ETAT_ECRAN)
        journal.verifier(
            "deux appels dans la même tâche retiennent le second",
            double["ouvert"] and double["cle"] == f"profil:{TITRE_AUTRE}",
            double["pathname"])

        await pg.go_back()
        await pg.wait_for_timeout(300)
        un_retour = await pg.evaluate(ETAT_ECRAN)
        journal.verifier(
            "un premier retour révèle l'entrée du PREMIER titre — deux entrées, pas une",
            un_retour["ouvert"] and un_retour["cle"] == f"profil:{TITRE}",
            un_retour["pathname"])

        await pg.go_back()
        await pg.wait_for_timeout(300)
        deux_retours = await pg.evaluate(ETAT_ECRAN)
        journal.verifier("un second retour quitte l'écran",
                         not deux_retours["ouvert"], deux_retours["pathname"])
        journal.verifier("aucune erreur JS pendant les deux appels", not erreurs, str(erreurs))
        await ctx.close()

        await navigateur.close()

    journal.bilan()


asyncio.run(main())

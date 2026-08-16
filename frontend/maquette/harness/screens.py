"""R71 — a screen above another one: back redraws the screen it covered.

The screen layer replaces its content in place, so a poster tapped on the add
screen draws the media sheet where the result list stood. The layer used to
hold ONE history entry however many screens succeeded each other inside it,
and a back from the sheet closed the whole layer — the operator lost the very
list they came from, query, filter and scroll included.

Each direct replacement now pushes its own entry and records how to redraw
the screen it covers. This rule walks the reported journey — results → sheet
→ back — through BOTH exits (the browser back and the « Retour » button) and
holds four things: the list is redrawn with its query, its scroll position
survives, one more back actually leaves the layer, and a result card carries
no inline action in its foot — the panel is the single path to the act, which
is what keeps the card the size of what it lists.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, ouvrir

_journal = None


def verifier(nom, condition, detail=""):
    return _journal.verifier(nom, condition, detail)


async def main():
    global _journal
    _journal = Journal("R71 — le retour redessine l'écran couvert")

    async with async_playwright() as p:
        navigateur = await p.chromium.launch(channel="chrome")
        ctx, pg = await ouvrir(navigateur)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        await pg.evaluate("()=>window.__go('acq-ajout-resultats')")
        await pg.wait_for_timeout(400)
        # The add screen left `#screen` for a real route (`/ajout`, rendered
        # inside `#coquille`): its results list is `.screen.open`, not
        # literally `#screen` — and so is the FICHE this journey opens further
        # down (`/fiche/$titre`). Each is named by its own `data-cle`.
        depart = await pg.evaluate("""()=>({
            ecran: !!document.querySelector('.screen.open'),
            cle: document.querySelector('.screen.open')?.dataset.cle,
            cartes: document.querySelectorAll('.reslist .card').length,
            pieds: document.querySelectorAll('.reslist .cfoot').length,
            requete: document.querySelector('#addq')?.value})""")
        verifier("l'écran de résultats est là", depart["ecran"] and depart["cartes"] >= 2,
                 f"{depart['cartes']} cartes · clé {depart['cle']}")
        verifier("une carte de résultat ne porte aucune action en pied",
                 depart["pieds"] == 0, f"{depart['pieds']} pied(s)")

        # The removal above is safe only because the act still has a home:
        # the result's panel must offer it.
        await pg.evaluate("()=>document.querySelector('.reslist .cbody').click()")
        await pg.wait_for_timeout(420)
        acte = await pg.evaluate(
            "()=>document.querySelector('#sheet .sact.primary')?.textContent.trim() ?? null")
        verifier("le panneau du résultat porte l'acte", bool(acte), f"« {acte} »")
        await pg.evaluate("()=>window.__close('sheet')")
        await pg.wait_for_timeout(300)

        # ── The reported journey, exit 1: the browser back ──────────────────
        await pg.evaluate("()=>{document.querySelector('.screen.open .port').scrollTop = 300;}")
        await pg.evaluate("()=>document.querySelector('.reslist .poster').click()")
        await pg.wait_for_timeout(450)
        # The poster's target is a MEDIA SHEET, and it left `#screen` for a
        # real route (`/fiche/$titre`, rendered inside `#coquille`) as the add
        # screen did before it. It is read by its own IDENTITY — the screen
        # carrying `data-cle="fiche:…"` — and not by a bare `.screen.open`:
        # two screens can carry `open` at once, and a selector that cannot
        # tell them apart is exactly the ambiguity the explicit reads below
        # exist to remove.
        fiche = await pg.evaluate("""()=>{
            const f = document.querySelector('.screen.open[data-cle^="fiche:"]');
            return {ecran: !!f, dessus: !!f?.querySelector('.herowrap'),
                    cle: f?.dataset.cle};}""")
        verifier("le poster ouvre la fiche sur le même calque",
                 fiche["ecran"] and fiche["dessus"], f"clé {fiche['cle']}")

        await pg.go_back()
        await pg.wait_for_timeout(500)
        # R-7: `.screen.open` alone is AMBIGUOUS once two screens can carry
        # `open` at the same time — the arrival is therefore identified by its
        # `data-cle` below, and the screen one is leaving is looked up by ITS
        # own key rather than by a class shared with everything else. A fiche
        # that failed to close is what a bare `.screen.open` would mask, so it
        # is read explicitly, by identity.
        retour = await pg.evaluate("""()=>({
            ecran: !!document.querySelector('.screen.open'),
            cle: document.querySelector('.screen.open')?.dataset.cle,
            cartes: document.querySelectorAll('.reslist .card').length,
            requete: document.querySelector('#addq')?.value,
            scroll: document.querySelector('.screen.open .port')?.scrollTop,
            ficheEncoreLa: !!document.querySelector('.screen.open[data-cle^="fiche:"]')})""")
        verifier("le retour redessine la liste de résultats",
                 retour["ecran"] and (retour["cle"] or "").startswith("ajout:")
                 and retour["cartes"] == depart["cartes"]
                 and retour["requete"] == depart["requete"],
                 f"{retour['cartes']} cartes · requête « {retour['requete']} »")
        verifier("avec sa position de défilement",
                 abs(retour["scroll"] - 300) <= 40, f"{retour['scroll']}px")
        verifier("et la fiche n'est plus là",
                 not retour["ficheEncoreLa"], f"fiche ouverte={retour['ficheEncoreLa']}")

        await pg.go_back()
        await pg.wait_for_timeout(450)
        sorti = await pg.evaluate("""()=>({
            ecran: !!document.querySelector('.screen.open'),
            page: state.page})""")
        verifier("et un retour de plus quitte l'écran",
                 not sorti["ecran"] and sorti["page"] == "acq",
                 f"page {sorti['page']}")

        # ── Exit 2: the « Retour » button on the sheet ──────────────────────
        await pg.evaluate("()=>window.__go('acq-ajout-resultats')")
        await pg.wait_for_timeout(400)
        await pg.evaluate("()=>document.querySelector('.reslist .poster').click()")
        await pg.wait_for_timeout(450)
        # Same fiche as exit 1, and its own « Retour » is clicked on the screen
        # identified as the fiche — never on whatever `.screen.open` happens to
        # resolve first.
        await pg.evaluate(
            """()=>document.querySelector('.screen.open[data-cle^="fiche:"] .fback').click()""")
        await pg.wait_for_timeout(500)
        # R-7: same read by identity as exit 1's `retour` — a fiche that failed
        # to close here is exactly what a bare `.screen.open` would miss.
        bouton = await pg.evaluate("""()=>({
            ecran: !!document.querySelector('.screen.open'),
            cle: document.querySelector('.screen.open')?.dataset.cle,
            cartes: document.querySelectorAll('.reslist .card').length,
            ficheEncoreLa: !!document.querySelector('.screen.open[data-cle^="fiche:"]')})""")
        verifier("le bouton « Retour » de la fiche fait de même",
                 bouton["ecran"] and (bouton["cle"] or "").startswith("ajout:")
                 and bouton["cartes"] == depart["cartes"],
                 f"{bouton['cartes']} cartes")
        verifier("et la fiche n'est plus là non plus",
                 not bouton["ficheEncoreLa"], f"fiche ouverte={bouton['ficheEncoreLa']}")

        await navigateur.close()
    _journal.bilan(erreurs)


asyncio.run(main())

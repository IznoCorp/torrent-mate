"""R69 — l'URL porte l'état, et un rechargement ramène où l'on était (DOIT-10).

« Chaque détail a son URL » is a rule of the constitution, and the prototype was
measurably not obeying it: `history.pushState` appeared four times and
`location` was read ZERO times. The interface told the browser where it was and
never once asked. That is not a debt to hand over with the binding mission — it
is a non-conformity, and one that shows: a reload landed on the opening page,
and no screen could be sent to anyone.

The state travels in the QUERY rather than in the path, which is a decision
rather than a shortcut: this file is opened from a static server, from a design
host and from `file://`, and a path-based route needs a server that rewrites
every unknown path onto the document — two of those three cannot. A query is
addressable everywhere, survives a reload and pastes into a message, which is
the whole of what DOIT-10 asks. The binding mission maps `?page=lib` onto
production's `/medias`; what is judged now is that the URL and the interface
never disagree.

What this holds to:

1. Only what DIFFERS from the opening state is written, so the common case has
   a clean address and a link carries only what it means to carry.
2. Walking the interface WRITES the address, one entry per arrival.
3. Reloading that address lands on the same screen — the finger's journey and
   the cold one end in the same place.
4. A wrong address is left ALONE. Rendering an unknown id moves the state onto
   the not-found surface, and deriving the address from it would rewrite a
   mistyped link into « ?page=404 » — the interface correcting the operator's
   address behind their back. A browser answering 404 leaves it as typed.
5. Back walks the addresses in reverse, not only the screens.
"""
import asyncio

from common import TELEPHONE
from playwright.async_api import async_playwright

PROTOTYPE = "http://127.0.0.1:8899/wrapped.html"

OU = """() => ({
  page: state.page,
  onglet: state.acqTab,
  lentille: state.libLens,
  mode: state.libMode,
  vide: (document.querySelector('#view .empty b') || {}).textContent || '',
  introuvable: state.introuvable || '',
})"""


async def ouvrir(b, url=PROTOTYPE):
    """Opens the prototype AT AN ADDRESS, past the startup screen."""
    ctx = await b.new_context(**TELEPHONE)
    pg = await ctx.new_page()
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    await pg.goto(url, wait_until="load")
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(280)
    return ctx, pg, erreurs


def requete(url):
    """The query part of an address, or '' when it carries none."""
    return url.split("?", 1)[1] if "?" in url else ""


async def main():
    from common import Journal

    journal = Journal("R69 — l'URL porte l'état, et un rechargement y ramène")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")

        # ── 1. the opening state writes nothing ────────────────────────────
        ctx, pg, erreurs = await ouvrir(b)
        journal.verifier("la page d'ouverture a une adresse propre",
                         requete(pg.url) == "", pg.url)

        # ── 2. walking writes the address ──────────────────────────────────
        await pg.tap('#nav button[data-page="lib"]')
        await pg.wait_for_timeout(360)
        apres_onglet = pg.url
        journal.verifier("changer d'onglet écrit l'adresse",
                         "page=lib" in requete(apres_onglet), apres_onglet)

        await pg.tap('[data-lens="inc"]')
        await pg.wait_for_timeout(360)
        adresse = pg.url
        journal.verifier("changer de lentille l'écrit aussi",
                         "lens=inc" in requete(adresse), adresse)
        journal.verifier("et l'adresse ne porte QUE ce qui diffère de l'ouverture",
                         set(requete(adresse).split("&")) == {"page=lib", "lens=inc"},
                         requete(adresse))
        marche = await pg.evaluate(OU)
        await ctx.close()

        # ── 3. the cold journey ends where the finger's did ────────────────
        ctx, pg, erreurs = await ouvrir(b, adresse)
        froid = await pg.evaluate(OU)
        journal.verifier("recharger cette adresse ramène au même écran",
                         (froid["page"], froid["lentille"]) == (marche["page"], marche["lentille"]),
                         f"{froid['page']}/{froid['lentille']} vs {marche['page']}/{marche['lentille']}")
        journal.verifier("et l'adresse n'a pas bougé en chemin",
                         requete(pg.url) == requete(adresse),
                         f"{requete(pg.url)} vs {requete(adresse)}")
        journal.verifier("aucune erreur JS au chargement à froid", not erreurs, str(erreurs))
        await ctx.close()

        # ── 4. a wrong address is left alone ───────────────────────────────
        faux = PROTOTYPE + "?page=nimportequoi"
        ctx, pg, erreurs = await ouvrir(b, faux)
        perdu = await pg.evaluate(OU)
        journal.verifier("une adresse inconnue rend la surface prévue pour ça",
                         perdu["page"] == "404", perdu["page"])
        journal.verifier("et l'interface NOMME ce qui a été demandé",
                         perdu["introuvable"] == "/nimportequoi", perdu["introuvable"])
        journal.verifier("et l'adresse reste celle qui a été tapée",
                         requete(pg.url) == "page=nimportequoi", pg.url)
        journal.verifier("aucune erreur JS sur une adresse inconnue", not erreurs, str(erreurs))
        await ctx.close()

        # ── 5. back walks the addresses in reverse ─────────────────────────
        ctx, pg, erreurs = await ouvrir(b)
        await pg.tap('#nav button[data-page="lib"]')
        await pg.wait_for_timeout(340)
        await pg.tap('#nav button[data-page="arr"]')
        await pg.wait_for_timeout(340)
        journal.verifier("après deux pas, l'adresse est celle du second",
                         "page=arr" in requete(pg.url), pg.url)
        await pg.go_back()
        await pg.wait_for_timeout(420)
        journal.verifier("un retour ramène à l'adresse du premier",
                         "page=lib" in requete(pg.url), pg.url)
        journal.verifier("et l'écran est celui de cette adresse",
                         (await pg.evaluate(OU))["page"] == "lib",
                         (await pg.evaluate(OU))["page"])
        await pg.go_back()
        await pg.wait_for_timeout(420)
        journal.verifier("un second retour ramène à l'adresse d'ouverture",
                         requete(pg.url) == "", pg.url)
        journal.verifier("aucune erreur JS pendant les retours", not erreurs, str(erreurs))
        await ctx.close()

        await b.close()

    journal.bilan()


asyncio.run(main())

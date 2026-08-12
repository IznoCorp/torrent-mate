"""R59 — the back gesture follows the path actually walked.

Only the LAYERS used to push history. A back closed a sheet, and then, with
nothing left to close, left the application — losing every page the operator
had walked through. A tab is a place one navigates to; it belongs in the
history exactly as a screen does.

At the bottom of the stack a guard entry sits, so a back at the root has
something to pop and the application is never left by surprise. Popping it says
so and puts it back; a second back within five seconds does not, and lets the
stack run out — which is what closes an installed app on Android. A page cannot
close itself; exhausting its history is the only honest thing it can do, and
this script checks that it does exactly that and nothing more.
"""
import asyncio

from playwright.async_api import async_playwright

BAR = "─" * 62

echecs = []
faits = 0


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict."""
    global faits
    faits += 1
    print(("  OK   " if condition else "  ECHEC") + f" {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


# Reading the interface AFTER a back that left the document raises instead of
# naming the defect. A crash is a failure nobody can read.
async def ou(pg):
    """Where the interface is, or None when the document is gone."""
    if pg.is_closed() or "wrapped.html" not in pg.url:
        return None
    try:
        return await pg.evaluate(OU)
    except Exception:  # noqa: BLE001 — the document left, which is the finding
        return None


OU = """() => ({
  page: state.page,
  onglet: state.acqTab,
  lentille: state.libLens,
  feuille: document.querySelector('#sheet').classList.contains('open'),
  ecran: document.querySelector('#screen').classList.contains('open'),
  tiroir: document.querySelector('#drawer').classList.contains('open'),
  message: (document.querySelector('#toast')||{}).textContent || '',
  toastVisible: (document.querySelector('#toast')||{classList:{contains:()=>false}})
                  .classList.contains('show'),
})"""


async def main():
    print(f"{BAR}\nR59 — le retour suit le chemin\n{BAR}")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await pg.evaluate("()=>document.querySelector('#toastx').click()")
        await pg.wait_for_timeout(300)

        # ── the path, walked forward by tapping ────────────────────────────
        chemin = [
            ('[data-acqtab="suivis"]', "acq", "suivis"),
            ('[data-page="lib"]', "lib", None),
            ('[data-lens="inc"]', "lib", None),
            ('[data-page="arr"]', "arr", None),
        ]
        for selecteur, _, _ in chemin:
            await pg.click(selecteur)
            await pg.wait_for_timeout(250)
        arrivee = await ou(pg)
        verifier("le chemin se parcourt", arrivee is not None and arrivee["page"] == "arr",
                 str(arrivee and arrivee["page"]))

        # ── and walked back, step by step, in reverse ──────────────────────
        attendus = [("lib", "inc"), ("lib", "cat"), ("acq", None), ("acq", None)]
        recu = []
        for _ in attendus:
            await pg.go_back()
            await pg.wait_for_timeout(300)
            etape = await ou(pg)
            recu.append((etape["page"], etape["lentille"]) if etape else (None, None))
        verifier("chaque retour défait un pas",
                 [r[0] for r in recu] == [a[0] for a in attendus],
                 f"{[r[0] for r in recu]} au lieu de {[a[0] for a in attendus]}")
        verifier("y compris le changement de lentille",
                 recu[0][1] == "inc" and recu[1][1] == "cat", str(recu[:2]))
        depart = await ou(pg)
        verifier("et le premier onglet est retrouvé",
                 depart is not None and depart["onglet"] == "maintenant",
                 str(depart and depart["onglet"]))

        # ── a layer is what a back closes first ────────────────────────────
        await pg.evaluate("()=>openFollowSheet('Silo')")
        await pg.wait_for_timeout(350)
        ouverte = await ou(pg)
        verifier("une feuille s'ouvre", bool(ouverte and ouverte["feuille"]))
        await pg.go_back()
        await pg.wait_for_timeout(300)
        apres = await ou(pg)
        verifier("le retour la referme sans changer de page",
                 apres is not None and not apres["feuille"] and apres["page"] == "acq",
                 str(apres and apres["page"]))

        # ── at the root: the application is not left by surprise ───────────
        avant = await ou(pg)
        await pg.go_back()
        await pg.wait_for_timeout(300)
        bas = await ou(pg)
        verifier("au bas du chemin, la route ne change pas",
                 bas is not None and avant is not None and bas["page"] == avant["page"],
                 f"{avant and avant['page']} → {bas and bas['page']}"
                 if bas else "le document a été quitté")
        verifier("et l'app prévient qu'un second retour la quitte",
                 bas is not None and "quitter" in bas["message"].lower() and bas["toastVisible"],
                 (bas["message"][:60] if bas else "le document a été quitté"))
        verifier("la page est toujours là", not pg.is_closed())

        # ── the offer expires: after the window, it warns again ────────────
        await pg.wait_for_timeout(5200)
        if await ou(pg):
            await pg.evaluate("()=>document.querySelector('#toastx').click()")
        await pg.go_back()
        await pg.wait_for_timeout(300)
        tard = await ou(pg)
        verifier("passé cinq secondes, l'avertissement recommence",
                 tard is not None and "quitter" in tard["message"].lower(),
                 (tard["message"][:60] if tard else "le document a été quitté"))

        # ── a second back inside the window exhausts the stack ─────────────
        # Nothing is put back, so the document is left. That is what closes an
        # installed app; here it lands on the blank page the context started on.
        await pg.go_back()
        await pg.wait_for_timeout(600)
        verifier("un second retour dans la fenêtre épuise l'historique",
                 "wrapped.html" not in pg.url, pg.url[:60])

        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await b.close()

    print()
    print(f"{BAR}\n{faits} règles EXÉCUTÉES — "
          + ("aucune violation" if not echecs else f"{len(echecs)} violation(s) : {', '.join(echecs)}"))
    if echecs:
        raise SystemExit(1)

asyncio.run(main())

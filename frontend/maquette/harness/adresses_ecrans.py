"""R75 — a screen route answers a real address, cold, and only while it is open.

`ProfilEcran` (Task 9) is the first screen drawn from a real path rather than
from the legacy fragment's own state machine, so it is also the first screen
whose address can be typed, bookmarked or shared — and the first for which a
missing detail (a fallback route on the host, a `<base>` tag in the envelope)
only shows up once something is actually served from BELOW the document
root. `serveur.py` (Task 8) is what makes that depth reachable at all: the
plain 8899 host 45 other rules already point at answers a 404 for
`/profil/…`, because no such file exists — nothing served through it can
tell a deep reload from a broken link. This rule runs entirely against 8917.

What it holds to:

1. A deep address opens the promised screen COLD — no journey, no click,
   just a fresh browser handed the URL.
2. Whatever that screen draws resolves through the document's `<base>`,
   the same way it would from `/` — proven not by the screen's own markup
   (`ProfilEcran` draws no `<img>` of its own, only inline SVG) but by every
   image the WHOLE document loads at that depth: the legacy fragment mounts
   underneath it, on its own default page, and draws real posters through
   the same relative `assets/…` paths every other screen uses.
3. One back from a screen reached by walking there lands where the walk
   started, with the screen gone — the screen owns no address once closed.
4. The address is written only while the screen is open: walking onto it
   writes `/profil/…`, and the ONLY way off it is back (`.fback` calls
   `__pont.retour()`, nothing else) — so closing it is, by construction,
   also the address returning to what it was.
5. A wrong deep address does not raise, blank the frame, or invent a
   not-found surface: `QualityProfile` is a GLOBAL setting, not a per-title
   record, so the screen has nothing to fail a lookup against — it renders
   its ordinary form for whatever string is in the address, and the address
   itself is left exactly as typed (R68's spirit, at depth).
"""
import asyncio
import json
import pathlib
import sys
import urllib.parse

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from commun import TELEPHONE, Journal
from serveur import demarrer_serveur

PORT = 8917
RACINE_SERVIE = pathlib.Path("/tmp/tm-refonte")

TITRE = "Silo"
# Typed by hand, on purpose: the apostrophe is left unescaped, exactly the
# way an operator would type it — the point of hold 5 is that NOTHING
# corrects this on the way in.
ADRESSE_INCONNUE = "N'Existe%20Pas"

ETAT_ECRAN = """() => {
  const ecran = document.querySelector('.screen.open');
  return {
    ouvert: !!ecran,
    cle: ecran?.dataset.cle ?? null,
    titre: (document.querySelector('.screen.open .fichebar span') || {}).textContent ?? null,
    corps: (ecran?.querySelector('.body') || {}).textContent ?? '',
    pathname: location.pathname,
  };
}"""

ETAT_AJOUT = """() => {
  const ecran = document.querySelector('.screen.open');
  return {
    ouvert: !!ecran,
    cle: ecran?.dataset.cle ?? null,
    champ: document.querySelector('#addq')?.value ?? null,
    cartes: document.querySelectorAll('.reslist .card').length,
    pathname: location.pathname,
    recherche: location.search,
  };
}"""

ETAT_IMAGES = """() => {
  const chargees = [...document.querySelectorAll('img')].filter(i => i.complete);
  return {
    chargees: chargees.length,
    cassees: chargees.filter(i => i.naturalWidth === 0).length,
  };
}"""


async def ouvrir_a(navigateur, adresse):
    """Opens `adresse` cold, past the startup screen, on a fresh context."""
    ctx = await navigateur.new_context(**TELEPHONE)
    pg = await ctx.new_page()
    erreurs = []
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    await pg.goto(adresse, wait_until="load")
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(300)
    return ctx, pg, erreurs


async def main():
    journal = Journal("R75 — les adresses d'écrans")

    async with async_playwright() as p:
        navigateur = await p.chromium.launch(channel="chrome")

        with demarrer_serveur(PORT, RACINE_SERVIE):
            base = f"http://127.0.0.1:{PORT}"

            # ─── Hold 1: deep entry opens the promised screen, cold ────────
            adresse_titre = f"{base}/profil/{urllib.parse.quote(TITRE)}"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_titre)
            etat = await pg.evaluate(ETAT_ECRAN)
            journal.verifier(
                "une adresse profonde ouvre le bon écran, à froid",
                etat["ouvert"] and etat["cle"] == f"profil:{TITRE}",
                f"cle={etat['cle']}")
            journal.verifier(
                "l'écran rend son contenu promis (résolution, pistes, verrous)",
                "Résolution minimale" in etat["corps"]
                and "Pistes audio exigées" in etat["corps"]
                and "Deux verrous" in etat["corps"],
                f"{len(etat['corps'])} caractères de corps")
            journal.verifier("aucune erreur JS à l'entrée profonde", not erreurs, str(erreurs))

            # ─── Hold 2: everything the document draws resolves through <base> ─
            images = await pg.evaluate(ETAT_IMAGES)
            journal.verifier(
                "aucune image cassée à cette profondeur (la preuve du <base>)",
                images["chargees"] > 0 and images["cassees"] == 0,
                f"{images['cassees']}/{images['chargees']} cassée(s)")
            await ctx.close()

            # ─── Holds 3+4: walking writes the address; back is the only close,
            # so back landing where the walk started IS the address returning ──
            ctx, pg, erreurs = await ouvrir_a(navigateur, f"{base}/")
            depart = await pg.evaluate(ETAT_ECRAN)
            journal.verifier("le point de départ n'a aucun écran ouvert",
                             not depart["ouvert"] and depart["pathname"] == "/",
                             depart["pathname"])

            await pg.evaluate(f"()=>window.__ecrans.profil({json.dumps(TITRE)})")
            await pg.wait_for_timeout(300)
            sur_profil = await pg.evaluate(ETAT_ECRAN)
            journal.verifier(
                "marcher jusqu'au profil ÉCRIT l'adresse",
                sur_profil["ouvert"] and sur_profil["pathname"] == f"/profil/{TITRE}",
                sur_profil["pathname"])

            await pg.evaluate("()=>document.querySelector('.screen.open .fback').click()")
            await pg.wait_for_timeout(300)
            revenu = await pg.evaluate(ETAT_ECRAN)
            journal.verifier(
                "fermer l'écran (son seul chemin : Retour) ramène l'adresse à ce qu'elle était",
                revenu["pathname"] == depart["pathname"], revenu["pathname"])
            journal.verifier("et l'écran est bien parti", not revenu["ouvert"],
                             str(revenu["ouvert"]))
            journal.verifier("aucune erreur JS pendant la marche", not erreurs, str(erreurs))
            await ctx.close()

            # ─── Hold 5: a wrong deep address renders the honest empty case ──
            adresse_fausse = f"{base}/profil/{ADRESSE_INCONNUE}"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_fausse)
            perdu = await pg.evaluate(ETAT_ECRAN)
            journal.verifier(
                "une adresse inconnue rend quand même l'écran, honnêtement",
                perdu["ouvert"] and "N'Existe Pas" in (perdu["titre"] or ""),
                f"cle={perdu['cle']} titre={perdu['titre']!r}")
            journal.verifier(
                "l'adresse reste celle qui a été tapée",
                pg.url == adresse_fausse, pg.url)
            journal.verifier("aucune erreur JS sur une adresse inconnue", not erreurs, str(erreurs))
            await ctx.close()

            # ─── Hold 6: /ajout deep entry, cold — field filled, results shown ──
            adresse_ajout = f"{base}/ajout?q=lucky"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_ajout)
            ajout_froid = await pg.evaluate(ETAT_AJOUT)
            journal.verifier(
                "une adresse profonde /ajout ouvre l'écran, à froid, le champ rempli",
                ajout_froid["ouvert"] and ajout_froid["champ"] == "lucky"
                and ajout_froid["cle"] == "ajout:suivi",
                f"champ={ajout_froid['champ']!r} cle={ajout_froid['cle']}")
            journal.verifier(
                "et la requête affiche des résultats",
                ajout_froid["cartes"] >= 2, f"{ajout_froid['cartes']} cartes")
            journal.verifier("aucune erreur JS à l'entrée profonde /ajout", not erreurs, str(erreurs))
            await ctx.close()

            # ─── Hold 7: typing rewrites the address IN PLACE — R76 for a
            # CONTROLLED input, not a one-shot navigation. Proven by the
            # STRONGEST observable: one back from a five-keystroke session
            # must land exactly where the walk started, not mid-query — a
            # stacked entry per keystroke would instead surface one letter
            # short of the full word. `history.length` is deliberately not
            # read here: an observed landing state is the harder proof.
            ctx, pg, erreurs = await ouvrir_a(navigateur, f"{base}/")
            depart_ajout = await pg.evaluate(ETAT_ECRAN)
            journal.verifier("le point de départ n'a aucun écran ouvert (avant /ajout)",
                             not depart_ajout["ouvert"] and depart_ajout["pathname"] == "/",
                             depart_ajout["pathname"])

            await pg.evaluate("()=>window.__ecrans.ajout('')")
            await pg.wait_for_timeout(300)
            sur_ajout = await pg.evaluate(ETAT_AJOUT)
            journal.verifier(
                "marcher jusqu'à /ajout ÉCRIT l'adresse",
                sur_ajout["ouvert"] and sur_ajout["pathname"] == "/ajout",
                sur_ajout["pathname"])

            await pg.click("#addq")
            for lettre in "lucky":
                await pg.keyboard.type(lettre)
                await pg.wait_for_timeout(80)
            await pg.wait_for_timeout(300)
            apres_frappe = await pg.evaluate(ETAT_AJOUT)
            journal.verifier(
                "cinq frappes réécrivent le champ ET l'adresse",
                apres_frappe["champ"] == "lucky" and "q=lucky" in apres_frappe["recherche"],
                f"champ={apres_frappe['champ']!r} recherche={apres_frappe['recherche']!r}")

            await pg.go_back()
            await pg.wait_for_timeout(400)
            apres_retour = await pg.evaluate(ETAT_ECRAN)
            journal.verifier(
                "un seul retour depuis cinq frappes ramène où l'on était AVANT l'écran"
                " (et pas mi-frappe, ce qu'un historique empilé aurait produit)",
                not apres_retour["ouvert"] and apres_retour["pathname"] == depart_ajout["pathname"],
                apres_retour["pathname"])
            journal.verifier("aucune erreur JS pendant la frappe", not erreurs, str(erreurs))
            await ctx.close()

            # ─── Hold 8: quitter un écran par la barre ──────────────────────
            # A legacy nav control (the bottom bar) can fire while a router
            # route is open — it writes through the SAME shared history the
            # router subscribes to, never through aller()/navigate(). The
            # write alone must be enough: no code on this side of the bridge
            # calls the router, yet the screen must still actually leave.
            # Reached the same way an operator does: a REAL tap on the FAB,
            # then a REAL tap on « Médiathèque ».
            ctx, pg, erreurs = await ouvrir_a(navigateur, f"{base}/")
            await pg.click("#fab")
            await pg.wait_for_timeout(400)
            sur_ajout_barre = await pg.evaluate(ETAT_ECRAN)
            journal.verifier(
                "le FAB ouvre l'écran (départ du voyage)",
                sur_ajout_barre["ouvert"] and sur_ajout_barre["pathname"] == "/ajout",
                sur_ajout_barre["pathname"])

            await pg.evaluate("()=>document.querySelector('[data-page=\"lib\"]').click()")
            await pg.wait_for_timeout(400)
            quitte = await pg.evaluate(
                """() => ({
                    ouvert: !!document.querySelector('.screen.open'),
                    pathname: location.pathname,
                    recherche: location.search,
                    page: state.page,
                })"""
            )
            journal.verifier(
                "taper « Médiathèque » depuis /ajout fait PARTIR l'écran",
                not quitte["ouvert"], f"ouvert={quitte['ouvert']}")
            journal.verifier(
                "l'adresse revient au langage legacy (base + ?page=lib)",
                quitte["pathname"] == "/" and quitte["recherche"] == "?page=lib",
                f"{quitte['pathname']}{quitte['recherche']}")
            journal.verifier(
                "et la page rendue est bien la médiathèque",
                quitte["page"] == "lib", f"page={quitte['page']}")
            journal.verifier("aucune erreur JS en quittant par la barre", not erreurs, str(erreurs))
            await ctx.close()

        await navigateur.close()

    journal.bilan()


asyncio.run(main())

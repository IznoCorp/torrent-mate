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

EXTENDED (SP4b) to `FicheEcran` — the media sheet, the one screen every
poster, tile, suggestion and panel act already led to, now also reachable
as `/fiche/$titre` on its own. Unlike `ProfilEcran`, this screen DOES draw
an image of its own (the hero/poster banner), so its own artwork is the
proof at this depth rather than a stand-in read off the legacy fragment
underneath. And unlike a `QualityProfile` name, a title here resolves
against a real per-title record (`sheetFor`) — so the unknown-title hold
is not "the screen has nothing to fail a lookup against" but "the legacy
template it was transplanted from never had a not-found branch either":
`openFiche(title)` (`refonte.html`, deleted when this screen became a real
route — recovered from the commit that deleted it) built the SAME markup
whether `sheetFor(title)` found a record or not, every field simply
printing "inconnu" in its place. What the harness holds for the fiche:
(f) a deep address opens it cold, `h2.ht` carrying the promised title;
(g) the hero/poster the screen draws ITSELF actually loads — proven on the
image the CSS background resolves to, not on a stand-in; (h) one Back
lands exactly where holds 3+4 already prove it does for `ProfilEcran`; (i)
an unknown title renders the SAME honest template, mirroring `openFiche`'s
own null path rather than inventing a not-found surface for it; (j) a
title the provider gave no trailer to renders `p.noinfo` in the
trailer's own place, never a silently missing section.
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

# The fiche titles below are picked straight from the embedded référentiel
# (`refonte.html`'s `FICHES_RAW`/`HEROS`/`trailerIds`), not invented:
# `Silo (2023)` carries both a hero image and a trailer (`sheetFor` resolves
# it directly, no `baseTitle` fallback needed), which is what makes holds
# (f)-(h) meaningful rather than vacuous. `Broadchurch` is the states
# table's own pick for "no trailer" (`fiche-sans-trailer`, refonte.html) —
# its `trailerIds` entry is absent and its sheet carries `trailer: null`
# explicitly, and its cast/seasons are otherwise fully populated so the
# ONLY `p.noinfo` the screen draws is the trailer's.
TITRE_FICHE = "Silo (2023)"
TITRE_SANS_TRAILER = "Broadchurch"

# `Backrooms.2026.MULTi.2160p.WEB-DL` is the embedded référentiel's own
# folder waiting to be resolved (`refonte.html`'s `arr-charge` state opens
# it as the default « Résoudre → » target — `ident.py` walks that exact
# path) — and the real regression case for `serveur.py`'s dotted-segment
# fallback fix: its deepest path segment carries dots of its own, which the
# fallback used to mistake for a file extension and 404 on before folding.
# Opening it through THIS deep-entry hold is what proves the fix reaches the
# SPA, not merely the raw HTTP response `serveur.py`'s own self-test covers.
DOSSIER_RESOLUTION = "Backrooms.2026.MULTi.2160p.WEB-DL"
# `Silo` is the states table's own pick for `ecran-releases`
# (`window.__ecrans.releases("Silo")`, refonte.html).
TITRE_RELEASES = "Silo"

ETAT_ECRAN = """() => {
  const ecran = document.querySelector('.screen.open');
  return {
    ouvert: !!ecran,
    cle: ecran?.dataset.cle ?? null,
    titre: (document.querySelector('.screen.open .screenbar span') || {}).textContent ?? null,
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

# `FicheEcran` draws its own artwork through a CSS `background-image`, not
# an `<img>` tag (`.herowrap .herobg`) — so `ETAT_IMAGES`'s generic
# `<img>` sweep, which is what proves hold 2 for `ProfilEcran` (a screen
# that draws no image of its own), does not see it at all. Proof here
# instead re-fetches the SAME url the computed style resolves through a
# real `Image()`, and reads `complete`/`naturalWidth` off THAT — the exact
# pair hold (g) is phrased against.
ETAT_HEROBG = """() => {
  const bg = document.querySelector('.screen.open .herowrap .herobg');
  const style = bg ? getComputedStyle(bg).backgroundImage : '';
  const trouve = /url\\(["']?(.*?)["']?\\)/.exec(style || '');
  const url = trouve ? trouve[1] : null;
  if (!url) return Promise.resolve({ url: null, dessine: false });
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve({ url, dessine: image.complete && image.naturalWidth > 0 });
    image.onerror = () => resolve({ url, dessine: false });
    image.src = url;
  });
}"""

ETAT_FICHE = """() => {
  const ecran = document.querySelector('.screen.open');
  return {
    ouvert: !!ecran,
    cle: ecran?.dataset.cle ?? null,
    titre: (ecran?.querySelector('h2.ht') || {}).textContent ?? null,
    corps: (ecran?.querySelector('.body') || {}).textContent ?? '',
    nofiches: [...document.querySelectorAll('.screen.open p.noinfo')].map(
      (p) => p.textContent),
    pathname: location.pathname,
  };
}"""

ETAT_RESOLUTION = """() => {
  const ecran = document.querySelector('.screen.open[data-cle^="resolution:"]');
  return {
    ouvert: !!ecran,
    cle: ecran?.dataset.cle ?? null,
    dossier: (ecran?.querySelector('h2.h2 code') || {}).textContent ?? null,
    corps: (ecran?.querySelector('.body') || {}).textContent ?? '',
    pathname: location.pathname,
  };
}"""

# `RELEASES` (the ranked candidates) is a FIXED référentiel, not looked up
# per title — unlike `sheetFor` for a fiche, there is nothing here for an
# unknown `titre` to fail against, so `candidats` stays what it is
# regardless of which title the bar shows.
ETAT_RELEASES = """() => {
  const ecran = document.querySelector('.screen.open[data-cle^="releases:"]');
  return {
    ouvert: !!ecran,
    cle: ecran?.dataset.cle ?? null,
    barre: (ecran?.querySelector('.screenbar span') || {}).textContent ?? null,
    candidats: ecran ? ecran.querySelectorAll('.rel').length : 0,
    pathname: location.pathname,
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

            # ─── Holds (f)-(h): the fiche's deep entry, its OWN artwork,
            # one Back — same server, same `ouvrir_a`, a second screen. ──
            adresse_fiche = f"{base}/fiche/{urllib.parse.quote(TITRE_FICHE)}"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_fiche)
            fiche_froide = await pg.evaluate(ETAT_FICHE)
            journal.verifier(
                "(f) une adresse profonde /fiche ouvre la fiche promise, à froid",
                fiche_froide["ouvert"]
                and fiche_froide["cle"] == f"fiche:{TITRE_FICHE}"
                and fiche_froide["titre"] == TITRE_FICHE.split(" (")[0],
                f"cle={fiche_froide['cle']} titre={fiche_froide['titre']!r}")
            artwork = await pg.evaluate(ETAT_HEROBG)
            journal.verifier(
                "(g) le hero/l'affiche que la fiche dessine ELLE-MÊME se charge réellement",
                artwork["url"] is not None and artwork["dessine"],
                f"url={artwork['url']!r} dessine={artwork['dessine']}")
            journal.verifier("aucune erreur JS à l'entrée profonde /fiche", not erreurs, str(erreurs))

            await pg.evaluate("()=>document.querySelector('.screen.open .fback').click()")
            await pg.wait_for_timeout(300)
            revenu_fiche = await pg.evaluate(ETAT_ECRAN)
            journal.verifier(
                "(h) un Retour depuis la fiche ramène sur la page par défaut, écran parti, adresse /",
                not revenu_fiche["ouvert"] and revenu_fiche["pathname"] == "/",
                revenu_fiche["pathname"])
            journal.verifier("aucune erreur JS pendant le retour depuis la fiche", not erreurs, str(erreurs))
            await ctx.close()

            # ─── Hold (i): an unknown title renders the SAME honest
            # template `openFiche` always did — no not-found branch to
            # mirror, only a gabarit whose fields say "inconnu" ──────────
            adresse_fiche_fausse = f"{base}/fiche/{ADRESSE_INCONNUE}"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_fiche_fausse)
            fiche_perdue = await pg.evaluate(ETAT_FICHE)
            journal.verifier(
                "(i) un titre inconnu rend quand même la fiche, honnêtement — le "
                "gabarit d'openFiche(title) n'avait pas de branche « non trouvé »",
                fiche_perdue["ouvert"]
                and fiche_perdue["titre"] == "N'Existe Pas"
                and "Métadonnées inconnues" in fiche_perdue["corps"]
                and "Genres inconnus" in fiche_perdue["corps"],
                f"cle={fiche_perdue['cle']} titre={fiche_perdue['titre']!r}")
            journal.verifier(
                "l'adresse reste celle qui a été tapée",
                pg.url == adresse_fiche_fausse, pg.url)
            journal.verifier("aucune erreur JS sur un titre de fiche inconnu", not erreurs, str(erreurs))
            await ctx.close()

            # ─── Hold (j): a title with no trailer renders p.noinfo in
            # the trailer's own place — Broadchurch's cast and seasons are
            # otherwise fully populated, so this is the ONLY p.noinfo the
            # screen draws; a stray match here would be a real regression,
            # not a coincidence from an unrelated missing field. ─────────
            adresse_sans_trailer = f"{base}/fiche/{urllib.parse.quote(TITRE_SANS_TRAILER)}"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_sans_trailer)
            fiche_sans_trailer = await pg.evaluate(ETAT_FICHE)
            journal.verifier(
                "(j) une fiche sans bande-annonce rend p.noinfo à sa place",
                fiche_sans_trailer["ouvert"]
                and len(fiche_sans_trailer["nofiches"]) == 1
                and "bande-annonce" in fiche_sans_trailer["nofiches"][0],
                f"nofiches={fiche_sans_trailer['nofiches']!r}")
            journal.verifier("aucune erreur JS sur une fiche sans bande-annonce", not erreurs, str(erreurs))
            await ctx.close()

            # ─── Holds (k)-(l): the arbitration screen's deep entry — the
            # SAME dossier that regresses `serveur.py`'s fallback (its
            # deepest segment carries dots, `Backrooms.2026.MULTi.2160p.
            # WEB-DL`), so reaching it here is also what proves the fix
            # holds all the way to the SPA, not merely the raw HTTP
            # response `serveur.py`'s own self-test already covers. ──────
            adresse_resolution = f"{base}/resolution/{urllib.parse.quote(DOSSIER_RESOLUTION)}"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_resolution)
            resolution_froide = await pg.evaluate(ETAT_RESOLUTION)
            journal.verifier(
                "(k) une adresse profonde /resolution ouvre l'écran promis, à froid — "
                "le dossier tapé, en chasse fixe",
                resolution_froide["ouvert"]
                and resolution_froide["cle"] == f"resolution:{DOSSIER_RESOLUTION}"
                and resolution_froide["dossier"] == DOSSIER_RESOLUTION,
                f"cle={resolution_froide['cle']} dossier={resolution_froide['dossier']!r}")
            journal.verifier("aucune erreur JS à l'entrée profonde /resolution", not erreurs, str(erreurs))

            await pg.evaluate("()=>document.querySelector('.screen.open .fback').click()")
            await pg.wait_for_timeout(300)
            revenu_resolution = await pg.evaluate(ETAT_ECRAN)
            journal.verifier(
                "(l) un Retour depuis la résolution ramène sur la page par défaut, "
                "écran parti, adresse /",
                not revenu_resolution["ouvert"] and revenu_resolution["pathname"] == "/",
                revenu_resolution["pathname"])
            journal.verifier("aucune erreur JS pendant le retour depuis la résolution",
                             not erreurs, str(erreurs))
            await ctx.close()

            # ─── Holds (m)-(n): the release picker's deep entry — its bar
            # carries the title, not a lookup: RELEASES is a fixed
            # référentiel, so there is nothing here to fail against a titre,
            # unlike the fiche's `sheetFor`. ──────────────────────────────
            adresse_releases = f"{base}/releases/{urllib.parse.quote(TITRE_RELEASES)}"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_releases)
            releases_froid = await pg.evaluate(ETAT_RELEASES)
            journal.verifier(
                "(m) une adresse profonde /releases ouvre l'écran promis, à froid — "
                "le titre dans la barre, des candidats dessinés",
                releases_froid["ouvert"]
                and releases_froid["cle"] == f"releases:{TITRE_RELEASES}"
                and releases_froid["barre"] == TITRE_RELEASES
                and releases_froid["candidats"] > 0,
                f"cle={releases_froid['cle']} barre={releases_froid['barre']!r} "
                f"candidats={releases_froid['candidats']}")
            journal.verifier("aucune erreur JS à l'entrée profonde /releases", not erreurs, str(erreurs))

            await pg.evaluate("()=>document.querySelector('.screen.open .fback').click()")
            await pg.wait_for_timeout(300)
            revenu_releases = await pg.evaluate(ETAT_ECRAN)
            journal.verifier(
                "(n) un Retour depuis les releases ramène sur la page par défaut, "
                "écran parti, adresse /",
                not revenu_releases["ouvert"] and revenu_releases["pathname"] == "/",
                revenu_releases["pathname"])
            journal.verifier("aucune erreur JS pendant le retour depuis les releases",
                             not erreurs, str(erreurs))
            await ctx.close()

            # ─── Hold (o): an unknown deep /resolution value renders the
            # screen's OWN honest empty case — `decisionEnAttente` finds no
            # pending decision for a name nobody scraped, so `ResolutionEcran`
            # takes the branch it already draws for that: no candidates
            # borrowed, the "aucun candidat" rulenote, and the two ways out
            # that do not depend on one still offered. ────────────────────
            adresse_resolution_fausse = f"{base}/resolution/{ADRESSE_INCONNUE}"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_resolution_fausse)
            resolution_perdue = await pg.evaluate(ETAT_RESOLUTION)
            corps_resolution_perdue = resolution_perdue["corps"].lower()
            journal.verifier(
                "(o) un dossier inconnu rend quand même l'écran, honnêtement — aucun "
                "candidat emprunté, la recherche manuelle et « laisser tel quel » restent offertes",
                resolution_perdue["ouvert"]
                and resolution_perdue["dossier"] == "N'Existe Pas"
                and "aucun candidat" in corps_resolution_perdue
                and "manuellement" in corps_resolution_perdue
                and "Laisser tel quel" in resolution_perdue["corps"],
                f"cle={resolution_perdue['cle']} dossier={resolution_perdue['dossier']!r}")
            journal.verifier(
                "l'adresse reste celle qui a été tapée",
                pg.url == adresse_resolution_fausse, pg.url)
            journal.verifier("aucune erreur JS sur un dossier de résolution inconnu",
                             not erreurs, str(erreurs))
            await ctx.close()

            # ─── Hold (p): an unknown deep /releases value renders the SAME
            # candidate list — RELEASES carries no per-title lookup to fail,
            # unlike a fiche's `sheetFor`, so the honest case here is simply
            # the ordinary screen, wearing whatever titre was typed. ───────
            adresse_releases_fausse = f"{base}/releases/{ADRESSE_INCONNUE}"
            ctx, pg, erreurs = await ouvrir_a(navigateur, adresse_releases_fausse)
            releases_perdu = await pg.evaluate(ETAT_RELEASES)
            journal.verifier(
                "(p) un titre inconnu rend quand même la liste des releases, "
                "avec ce titre dans la barre",
                releases_perdu["ouvert"]
                and releases_perdu["barre"] == "N'Existe Pas"
                and releases_perdu["candidats"] > 0,
                f"cle={releases_perdu['cle']} barre={releases_perdu['barre']!r}")
            journal.verifier(
                "l'adresse reste celle qui a été tapée",
                pg.url == adresse_releases_fausse, pg.url)
            journal.verifier("aucune erreur JS sur un titre de releases inconnu",
                             not erreurs, str(erreurs))
            await ctx.close()

        await navigateur.close()

    journal.bilan()


asyncio.run(main())

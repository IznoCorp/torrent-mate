"""R68 — une adresse inconnue ne casse rien, et un compte absent ne s'invente pas.

Two surfaces production serves that the prototype did not draw, and they share
one discipline: answer honestly what you do not have.

· **A wrong address.** It is the one input an interface never controls — a
  stale bookmark, a shared link, a renamed route. The prototype answered it by
  looking up a page table that did not carry the id and calling `.render()` on
  nothing: a TypeError, and the whole frame stopped. That is the worst possible
  answer to a bookmark. It now renders, names what was asked for, and offers a
  way out (DOIT-7 — never a dead end).

· **The account surface.** There is ONE account on this server. Drawing a list
  of colleagues to fill the screen is what §13 forbids: an interface showing
  data the system does not hold teaches its operator to distrust the rest of
  it. The place of the others is marked and EMPTY, and says why.

Everything the account surface claims about the session is compared against
`web.json5` — the real file, not a number written beside it.
"""
import asyncio
import os
import pathlib
import re

from common import Journal, ouvrir
from playwright.async_api import async_playwright

WEB = pathlib.Path(os.path.expanduser("~/.torrentmate/config/web.json5"))

LIRE = """() => ({
  debord: document.querySelector('#port').scrollWidth - document.querySelector('#port').clientWidth,
  page: state.page,
  texte: document.querySelector('#view').textContent.replace(/\\s+/g, ' ').trim(),
  vide: (document.querySelector('#view .empty b') || {}).textContent || '',
  sorties: [...document.querySelectorAll('#view button')].map((b) => ({
    texte: b.textContent.trim(),
    cible: Object.keys(b.dataset).join(','),
    inerte: b.disabled,
  })),
  faits: [...document.querySelectorAll('#view .flux .fx')].map((x) => ({
    l: x.querySelector('.fn').textContent.trim(),
    v: x.querySelector('.fr').textContent.trim(),
    k: (x.querySelector('.fk') || {}).textContent || '',
  })),
})"""


def config_web():
    """What `web.json5` really holds, or None when it is not on this machine."""
    if not WEB.is_file():
        return None
    brut = WEB.read_text()
    # JSON5 with comments — the two values this rule compares are read by name
    # rather than by parsing a dialect no standard library knows.
    def champ(nom):
        m = re.search(rf'\b{nom}\s*:\s*"?([^",\n]+)"?', brut)
        return m.group(1).strip() if m else None
    return {"username": champ("username"), "ttl": champ("session_ttl_hours")}


async def main():
    journal = Journal("R68 — une adresse inconnue, et un compte qui ne s'invente pas")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await ouvrir(b)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        # ── a wrong address ────────────────────────────────────────────────
        # Driving to it and reading the frame are guarded SEPARATELY: when the
        # interface throws, the drive throws with it and the probe dies on a
        # traceback — a crash is a failure nobody can read, and the mutation
        # that restores this very defect proved it by reporting nothing at all.
        try:
            await pg.evaluate(
                "()=>applyState({page: 'cette-page-n-existe-pas', phase: 'prete'})")
        except Exception as souci:  # noqa: BLE001 — the throw IS the finding
            erreurs.append(str(souci))
        await pg.wait_for_timeout(350)
        try:
            perdu = await pg.evaluate(LIRE)
        except Exception as souci:  # noqa: BLE001
            erreurs.append(str(souci))
            perdu = {"debord": 0, "page": None, "texte": "", "vide": "",
                     "sorties": [], "faits": []}
        journal.verifier("une adresse inconnue ne fait pas tomber l'interface",
                         not erreurs and len(perdu["texte"]) > 40,
                         f"{len(perdu['texte'])} caractères · erreurs {erreurs}")
        # Everything after this measures the surface, so what the drive raised
        # is not carried into those verdicts as well.
        erreurs.clear()
        journal.verifier("elle atterrit sur une surface faite pour ça",
                         perdu["page"] == "404", perdu["page"])
        journal.verifier("elle NOMME l'adresse demandée",
                         "cette-page-n-existe-pas" in perdu["texte"],
                         perdu["texte"][:90])
        journal.verifier("elle dit que rien n'est cassé",
                         "cassé" in perdu["texte"], perdu["texte"][:90])
        sorties = [s for s in perdu["sorties"] if s["cible"] and not s["inerte"]]
        journal.verifier("elle offre au moins une sortie, et aucune n'est inerte",
                         len(sorties) >= 2 and len(sorties) == len(perdu["sorties"]),
                         str([s["texte"] for s in perdu["sorties"]]))
        journal.verifier("rien ne déborde du cadre", perdu["debord"] <= 0,
                         f"{perdu['debord']}px")

        # ── the account surface, reached the way one reaches it ────────────
        await pg.evaluate("()=>applyState({page: 'acq', phase: 'prete'})")
        await pg.wait_for_timeout(250)
        await pg.tap('[data-sheet="utilisateur"]')
        await pg.wait_for_timeout(420)
        menu = await pg.evaluate(
            """()=>[...document.querySelectorAll('.sheetacts .sact')].map((b) => ({
                 texte: b.textContent.trim(), inerte: b.disabled,
                 cible: Object.entries(b.dataset).map(([k, v]) => k + '=' + v).join(',')}))""")
        profil = [m for m in menu if "Profil" in m["texte"]]
        journal.verifier("le menu utilisateur porte l'entrée du profil",
                         bool(profil), str([m["texte"] for m in menu]))
        journal.verifier("et elle mène quelque part",
                         profil and not profil[0]["inerte"] and profil[0]["cible"],
                         str(profil))

        await pg.tap('.sheetacts .sact:has-text("Profil")')
        await pg.wait_for_timeout(420)
        compte = await pg.evaluate(LIRE)
        journal.verifier("l'entrée du menu ouvre bien la surface du compte",
                         compte["page"] == "profil", compte["page"])
        journal.verifier("la place des autres comptes est marquée ET VIDE",
                         "pas encore" in compte["vide"].lower(), compte["vide"])
        journal.verifier("rien ne déborde du cadre du compte",
                         compte["debord"] <= 0, f"{compte['debord']}px")

        # ── what it claims is what `web.json5` holds ───────────────────────
        reel = config_web()
        if reel is None:
            journal.verifier("ce que le compte affirme vient de web.json5", False,
                             "web.json5 absent — la comparaison n'a pas pu être faite")
        else:
            identifiants = [f["v"] for f in compte["faits"] if f["k"] == "web.username"]
            journal.verifier("l'identifiant affiché est celui de la configuration",
                             identifiants == [reel["username"]],
                             f"{identifiants} vs {reel['username']}")
            durees = [f for f in compte["faits"] if f["k"] == "web.session_ttl_hours"]
            journal.verifier("la durée de session affichée est celle de la configuration",
                             durees and reel["ttl"] in " ".join(
                                 f"{d['v']} {d.get('s', '')}" for d in durees)
                             or (durees and reel["ttl"] == "720" and "30 jours" in durees[0]["v"]),
                             f"{[d['v'] for d in durees]} vs {reel['ttl']} heures")

        # No colleague is invented. What identifies an account here is an
        # address, so every address on the surface must be the real one — a
        # capitalised-words regex reads two adjacent headings as a person and
        # would have failed on « Vous Identifiant », which names nobody.
        adresses = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", compte["texte"]))
        vraie = await pg.evaluate("()=>COMPTE.mail")
        journal.verifier("aucun autre compte n'est inventé pour remplir l'écran",
                         adresses <= {vraie},
                         f"{len(adresses)} adresse(s) : {', '.join(sorted(adresses)) or 'aucune'}")

        journal.verifier("aucune erreur JS", not erreurs, str(erreurs))
        await ctx.close()
        await b.close()

    journal.bilan()


asyncio.run(main())

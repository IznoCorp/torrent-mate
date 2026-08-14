"""R67 — Système dit si la MACHINE va mal, Maintenance est ce qu'on lui fait.

The cut is the operator's: a medium in trouble is Arrivées, a machine in
trouble is Système, and a command run against the library is Maintenance. Two
surfaces, one rule, because the boundary between them is what the rule is
about — a panel on the wrong page is the defect, not a missing panel.

What this holds to:

1. **No blocked medium on Système.** Its business is processes, schedules,
   space, and code that raised. A medium the pipeline refused is a DECISION
   and belongs to Arrivées; drawn here it would be reported twice and answered
   nowhere.
2. **A scheduler between two runs is not stopped.** PM2 reports `stopped` and
   that is the literal truth about the process and a lie about the system: six
   red rows on a machine in perfect health. A service is judged on whether it
   is UP, a scheduler on whether it RAN, and the two lists never share a
   vocabulary.
3. **Every service and scheduler shown really exists**, checked against
   `pm2 jlist` rather than against a list written beside it.
4. **Maintenance is navigated by what one wants to DO**, and every command it
   draws is one the engine really registers — checked against the registry,
   count included, so a command cannot silently disappear from the drawing.
5. **A command that DELETES cannot be run for real before it has been run
   blank.** The second control is inert and says why. This is the one decision
   of the page: a dialog asks « are you sure », which is answered without
   reading; a blank run produces a list, which has to be looked at. A real
   deletion cannot be rehearsed on this machine — staging writes to the real
   disks — so what the interface owes is the look BEFORE, not a net after.
6. Nothing overflows a 390px frame on either surface.
"""
import asyncio
import json
import os
import pathlib
import subprocess
import sys

from commun import Journal, ouvrir
from playwright.async_api import async_playwright

RACINE = pathlib.Path(os.path.expanduser("~/dev/PersonalScraper"))

LIRE = """() => {
  const port = document.querySelector('#port');
  const bloc = (titre) => {
    const titres = [...document.querySelectorAll('#view .h2')];
    const t = titres.find((x) => x.textContent.trim() === titre);
    if (!t) return null;
    let n = t.nextElementSibling;
    while (n && !n.classList.contains('flux')) {
      if (n.classList.contains('h2')) return null;
      n = n.nextElementSibling;
    }
    return n
      ? [...n.querySelectorAll('.fx')].map((x) => {
          const pastille = x.querySelector('.fn .pip');
          return {
            l: x.querySelector('.fn').textContent.trim(),
            v: x.querySelector('.fr').textContent.trim(),
            s: x.querySelector('.fs').textContent.trim(),
            couleur: pastille
              ? pastille.classList.contains('success')
                ? 'vert'
                : 'rouge'
              : null,
          };
        })
      : null;
  };
  return {
    debord: port.scrollWidth - port.clientWidth,
    texte: document.querySelector('#view').textContent,
    simulee: document.querySelector('#view').textContent.includes('SIMULÉE'),
    titres: [...document.querySelectorAll('#view .h2')].map((x) => x.textContent.trim()),
    services: bloc('Services'),
    planificateurs: bloc('Planificateurs'),
    rubriques: [...document.querySelectorAll('#view .rub .rt')].map((x) => x.textContent.trim()),
    commandes: [...document.querySelectorAll('#view .flux .fx .fk')].map((x) => x.textContent.trim()),
  };
}"""

PANNEAU = """() => ({
  ouvert: document.querySelector('#sheet').classList.contains('open'),
  titre: (document.querySelector('.sheettitle') || {}).textContent || '',
  actions: [...document.querySelectorAll('.sheetacts .sact')].map((b) => ({
    texte: b.textContent.trim(),
    inerte: b.disabled,
    pourquoi: b.getAttribute('title') || '',
  })),
})"""


def processus_reels():
    """The process names PM2 really runs, or None when pm2 cannot be read."""
    try:
        sortie = subprocess.run(["pm2", "jlist"], capture_output=True, text=True,
                                timeout=25)
    except Exception:  # noqa: BLE001 — pm2 absent is a skip, not a verdict
        return None
    try:
        liste = json.loads(sortie.stdout)
    except Exception:  # noqa: BLE001
        return None
    return {p["name"]: p.get("pm2_env", {}) for p in liste}


def commandes_reelles():
    """The `library-*` commands the engine really registers, or None."""
    try:
        sys.path.insert(0, str(RACINE))
        from personalscraper.web.maintenance.registry import REGISTRY
    except Exception:  # noqa: BLE001 — the engine not importable is a skip
        return None
    return {a.id: a for a in REGISTRY}


async def surPage(pg, page, **patch):
    champs = ", ".join(f"{k}: {json.dumps(v)}" for k, v in patch.items())
    await pg.evaluate(
        f"()=>{{applyState({{page: '{page}', phase: 'prete'{', ' + champs if champs else ''}}});}}")
    await pg.wait_for_timeout(320)
    return await pg.evaluate(LIRE)


async def main():
    journal = Journal("R67 — Système est la machine, Maintenance est ce qu'on lui fait")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await ouvrir(b)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        # ── SYSTÈME ────────────────────────────────────────────────────────
        sys_vue = await surPage(pg, "sys")

        # 1. No blocked medium here. The two stuck folders are named on
        # Arrivées; finding either name on Système means a medium is being
        # reported twice and answered nowhere.
        bloques = await pg.evaluate("()=>window.__bloques ? window.__bloques() : null")
        journal.verifier("la liste des médias bloqués est atteignable",
                         bool(bloques),
                         f"{len(bloques or [])} : {', '.join(bloques or [])}")
        fuites = [t for t in (bloques or []) if t.split(" (")[0] in sys_vue["texte"]]
        journal.verifier("aucun média bloqué n'est dessiné sur Système",
                         bool(bloques) and not fuites,
                         str(fuites) if fuites else "aucun")

        # 2. A scheduler is never said to be stopped.
        mots_interdits = ["stopped", "arrêté", "arrêtée", "hors ligne"]
        trouves = [m for m in mots_interdits
                   if m in " ".join(f"{x['l']} {x['v']} {x['s']}"
                                    for x in (sys_vue["planificateurs"] or [])).lower()]
        journal.verifier("aucun planificateur n'est dit « arrêté » entre deux passages",
                         not trouves, str(trouves) if trouves else "aucun")
        journal.verifier("un planificateur se juge sur quand il a TOURNÉ",
                         all(x["v"] for x in (sys_vue["planificateurs"] or [])),
                         str([x["v"] for x in (sys_vue["planificateurs"] or [])]))
        journal.verifier("un service se juge sur le fait qu'il TOURNE",
                         all("ligne" in x["v"] for x in (sys_vue["services"] or [])),
                         str([x["v"] for x in (sys_vue["services"] or [])]))

        # 3. Everything shown really runs.
        pm2 = processus_reels()
        if pm2 is None:
            journal.verifier("les processus dessinés existent vraiment", False,
                             "pm2 illisible — la comparaison n'a pas pu être faite")
        else:
            services = len(sys_vue["services"] or [])
            planifs = len(sys_vue["planificateurs"] or [])
            vrais_services = [n for n, e in pm2.items()
                              if n.startswith(("torrentmate", "personalscraper"))
                              and not e.get("cron_restart")]
            vrais_planifs = [n for n, e in pm2.items()
                             if n.startswith(("torrentmate", "personalscraper"))
                             and e.get("cron_restart")]
            journal.verifier("autant de services dessinés que PM2 en fait tourner",
                             services == len(vrais_services),
                             f"{services} dessinés vs {len(vrais_services)} réels : "
                             + ", ".join(sorted(vrais_services)))
            journal.verifier("autant de planificateurs dessinés que PM2 en programme",
                             planifs == len(vrais_planifs),
                             f"{planifs} dessinés vs {len(vrais_planifs)} réels : "
                             + ", ".join(sorted(vrais_planifs)))

        # 3bis. Every service and scheduler carries a pastille, and the
        # pastille AGREES with the sentence beside it. Deriving the colour from
        # one field is what makes that true by construction; checking it is
        # what proves the derivation was not bypassed by a hand-written colour.
        # The colour is compared against the DECLARED state, never against the
        # wording. A first version of this matched the sentence with a pattern
        # and failed on « le 9 août », which says nothing wrong — it was
        # measuring the pattern rather than the interface. Reading `ok` off the
        # page's own data proves the derivation was not bypassed by a colour
        # written in by hand, which is the only way the two could disagree.
        for nom, lignes, source in (
            ("service", sys_vue["services"], "SERVICES"),
            ("planificateur", sys_vue["planificateurs"], "PLANIFICATEURS"),
        ):
            sans = [x["l"] for x in (lignes or []) if x["couleur"] is None]
            journal.verifier(f"chaque {nom} porte une pastille", not sans, str(sans) or "toutes")
            declare = await pg.evaluate(f"()=>{source}.map((x) => x.ok)")
            rendu = [x["couleur"] == "vert" for x in (lignes or [])]
            journal.verifier(f"la pastille d'un {nom} suit l'état déclaré, jamais une couleur écrite à la main",
                             rendu == declare, f"rendu {rendu} vs déclaré {declare}")

        journal.verifier("au repos, rien n'est rouge sur cette machine",
                         all(x["couleur"] == "vert"
                             for x in (sys_vue["services"] or []) + (sys_vue["planificateurs"] or [])),
                         "vert partout")
        journal.verifier("et l'état de repos ne se présente pas comme une simulation",
                         not sys_vue["simulee"])

        # 3ter. A screen that can only be green cannot be judged, so a named
        # state replays a fault — and SAYS it is simulated, or the operator
        # would read an invented outage as a real one (§13).
        panne = await surPage(pg, "sys", panne=True)
        rouges_s = [x for x in (panne["services"] or []) if x["couleur"] == "rouge"]
        rouges_p = [x for x in (panne["planificateurs"] or []) if x["couleur"] == "rouge"]
        journal.verifier("un état nommé montre ce que le rouge donne, côté services",
                         len(rouges_s) == 1, str([x["l"] for x in rouges_s]))
        journal.verifier("et côté planificateurs",
                         len(rouges_p) == 1, str([x["l"] for x in rouges_p]))
        journal.verifier("un service en panne est dit HORS LIGNE, pas en retard",
                         rouges_s and rouges_s[0]["v"] == "hors ligne",
                         str([x["v"] for x in rouges_s]))
        journal.verifier("un planificateur en retard est dit par une DURÉE, pas par un mot",
                         rouges_p and "il y a" in rouges_p[0]["v"],
                         str([x["v"] for x in rouges_p]))
        journal.verifier("et l'écran dit que cette panne est SIMULÉE", panne["simulee"])

        journal.verifier("rien ne déborde du cadre sur Système",
                         sys_vue["debord"] <= 0, f"{sys_vue['debord']}px")
        journal.verifier("rien ne déborde du cadre en panne",
                         panne["debord"] <= 0, f"{panne['debord']}px")

        # ── MAINTENANCE ────────────────────────────────────────────────────
        maint = await surPage(pg, "maint", maintRub=None)
        journal.verifier("Maintenance se navigue par ce qu'on veut FAIRE",
                         len(maint["rubriques"]) >= 5, str(maint["rubriques"]))
        journal.verifier("le journal des suppressions est sur Maintenance",
                         "Journal des suppressions" in maint["titres"],
                         str(maint["titres"]))

        registre = commandes_reelles()
        vues = set()
        for rubrique in ("query", "scan", "repair", "clean", "fix", "analyze"):
            page = await surPage(pg, "maint", maintRub=rubrique)
            vues.update(page["commandes"])
            journal.verifier(f"la rubrique « {rubrique} » dessine des commandes",
                             len(page["commandes"]) > 0, str(page["commandes"]))
            journal.verifier(f"rien ne déborde du cadre dans « {rubrique} »",
                             page["debord"] <= 0, f"{page['debord']}px")

        if registre is None:
            journal.verifier("les commandes dessinées existent dans le moteur", False,
                             "moteur non importable — la comparaison n'a pas pu être faite")
        else:
            inventees = sorted(vues - set(registre))
            oubliees = sorted(set(registre) - vues)
            journal.verifier("aucune commande dessinée n'est inventée",
                             not inventees, str(inventees) if inventees else "aucune")
            journal.verifier("aucune commande du moteur n'est oubliée",
                             not oubliees, str(oubliees) if oubliees else "aucune")

        # 5. The one decision: a command that deletes is blank-first.
        destructrices = ([a for a in registre.values() if a.risk == "destructive"]
                         if registre else [])
        journal.verifier("le moteur a bien des commandes qui suppriment",
                         len(destructrices) > 0, f"{len(destructrices)}")
        for action in destructrices:
            await surPage(pg, "maint", maintRub=action.category)
            await pg.evaluate(f"()=>ouvrirActionMaintenance({json.dumps(action.id)})")
            await pg.wait_for_timeout(320)
            panneau = await pg.evaluate(PANNEAU)
            reelle = [a for a in panneau["actions"] if "vrai" in a["texte"]]
            journal.verifier(
                f"« {action.title} » propose de la lancer à blanc D'ABORD",
                any("blanc" in a["texte"] for a in panneau["actions"]),
                str([a["texte"] for a in panneau["actions"]]))
            journal.verifier(
                f"« {action.title} » ne peut pas être lancée pour de vrai tout de suite",
                reelle and all(a["inerte"] for a in reelle),
                str([(a["texte"], a["inerte"]) for a in reelle]))
            journal.verifier(
                f"« {action.title} » DIT pourquoi elle est retenue",
                reelle and all(a["pourquoi"] for a in reelle),
                str([a["pourquoi"] for a in reelle]))
            await pg.evaluate("()=>closeSheet()")
            await pg.wait_for_timeout(180)

        journal.verifier("aucune erreur JS", not erreurs, str(erreurs))
        await ctx.close()
        await b.close()

    journal.bilan()


asyncio.run(main())

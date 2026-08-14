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

# THE VOCABULARY BELONGS TO THE RULE, not to the data.
#
# Comparing the rendered tone against the declared one proves the renderer
# follows the data and nothing else: mutate the data and both move together,
# so a nearly-full disk coloured as a critical alert changed nothing. That is a
# derivation reading back its own output. The mapping from a WORD to the tone
# it deserves is stated here instead, once, and a disagreement is a defect —
# whichever side wandered.
VOCABULAIRE = {
    "success": {"en ligne", "à l'heure", "réussi", "connecté", "joignable",
                "disponibles", "de la place", "aucune"},
    "alert": {"hors ligne", "en retard", "échoué", "des erreurs"},
    "warning": {"bientôt plein", "à nettoyer"},
}

# WCAG AA for body text. A badge that cannot be read is a badge that is not
# there, and the chip is a TINT of its own colour — exactly the shape that put
# a label on its own background once already (B-014).
PLANCHER_CONTRASTE = 4.5

# Colours are converted through a canvas, never parsed: `getComputedStyle`
# returns the space the author wrote — `oklch()` here — and three numbers pulled
# out of that string with a regex built for `rgb()` mean nothing. Drawing over
# white and again over black also recovers a tint's alpha, which compositing a
# translucent chip needs.
CONTRASTE = """() => {
  const cnv = document.createElement('canvas');
  cnv.width = cnv.height = 1;
  const ctx = cnv.getContext('2d', { willReadFrequently: true });
  const sur = (couleur, fond) => {
    ctx.fillStyle = fond;
    ctx.fillRect(0, 0, 1, 1);
    ctx.fillStyle = couleur;
    ctx.fillRect(0, 0, 1, 1);
    return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
  };
  const rgba = (couleur) => {
    const blanc = sur(couleur, '#fff');
    const noir = sur(couleur, '#000');
    const a = 1 - (blanc[0] - noir[0]) / 255;
    return { rgb: noir.map((v) => (a > 0 ? v / a : 0)), a };
  };
  const canal = (v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  const lum = (c) =>
    0.2126 * canal(c[0] / 255) + 0.7152 * canal(c[1] / 255) + 0.0722 * canal(c[2] / 255);
  const derriere = (el) => {
    const pile = [];
    let noeud = el.parentElement;
    while (noeud) {
      const { rgb, a } = rgba(getComputedStyle(noeud).backgroundColor);
      if (a > 0.001) pile.push([rgb, a]);
      if (a > 0.999) break;
      noeud = noeud.parentElement;
    }
    let sortie = [255, 255, 255];
    for (let i = pile.length - 1; i >= 0; i--) {
      const [c, a] = pile[i];
      sortie = sortie.map((v, k) => c[k] * a + v * (1 - a));
    }
    return sortie;
  };
  return [...document.querySelectorAll('#view .flux .fr .chip')].map((el) => {
    const s = getComputedStyle(el);
    const propre = rgba(s.backgroundColor);
    let fond = derriere(el);
    if (propre.a > 0.001) {
      fond = fond.map((v, k) => propre.rgb[k] * propre.a + v * (1 - propre.a));
    }
    const texte = rgba(s.color).rgb;
    const [l1, l2] = [lum(texte), lum(fond)].sort((x, y) => y - x);
    return {
      mot: el.textContent.trim(),
      contraste: Math.round(((l1 + 0.05) / (l2 + 0.05)) * 100) / 100,
    };
  });
}"""

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
          // The badge IS the value: a row whose value is a state wears it as
          // a chip. Reading a dot beside the label would measure a shape the
          // interface no longer draws.
          const badge = x.querySelector('.fr .chip');
          const TONS = { success: 'success', danger: 'alert',
                         warning: 'warning', info: 'info' };
          return {
            l: x.querySelector('.fn').textContent.trim(),
            v: x.querySelector('.fr').textContent.trim(),
            s: x.querySelector('.fs').textContent.trim(),
            // Reported in the operator's vocabulary, which is what the data is
            // written in: the stylesheet's `danger` is their `alert`.
            ton: badge
              ? TONS[[...badge.classList].find((c) => TONS[c])] || 'inconnu'
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
    disques: bloc('Disques'),
    index: bloc('Index de la médiathèque'),
    dependances: bloc('Dépendances'),
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
        # The badge carries the STATE; when it last ran is a detail and lives
        # in the sub-line. A badge reading « ce matin à 03 h 20 » would be a
        # date wearing a colour, which says nothing about whether that date is
        # late.
        journal.verifier("un planificateur se juge sur « à l'heure » ou « en retard »",
                         all(x["v"] in ("à l'heure", "en retard")
                             for x in (sys_vue["planificateurs"] or [])),
                         str([x["v"] for x in (sys_vue["planificateurs"] or [])]))
        journal.verifier("et DIT quand il a tourné, sous le badge",
                         all("dernier passage" in x["s"]
                             for x in (sys_vue["planificateurs"] or [])),
                         str([x["s"][:40] for x in (sys_vue["planificateurs"] or [])]))
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
        # EVERY list that carries a tone, not only the two the page opens with:
        # a mutation that coloured a nearly-full disk as an alert changed
        # nothing, because nothing looked at the disks. A guard that covers two
        # lists out of five is a guard for two lists.
        for nom, lignes, source in (
            ("service", sys_vue["services"], "SERVICES"),
            ("planificateur", sys_vue["planificateurs"], "PLANIFICATEURS"),
            ("disque", sys_vue["disques"], "DISQUES"),
            ("ligne d'index", sys_vue["index"], "INDEX"),
            ("dépendance", sys_vue["dependances"], "DEPENDANCES"),
        ):
            sans = [x["l"] for x in (lignes or []) if x["ton"] is None]
            journal.verifier(f"chaque {nom} porte un badge", not sans, str(sans) or "tous")
            declare = await pg.evaluate(f"()=>{source}.map((x) => x.ton)")
            rendu = [x["ton"] for x in (lignes or [])]
            journal.verifier(f"le badge d'un {nom} suit l'état déclaré, jamais une couleur écrite à la main",
                             rendu == declare, f"rendu {rendu} vs déclaré {declare}")
            # And the tone matches what the WORD means. This is the half that
            # a comparison against the data cannot do.
            mal_dites = [
                f"« {x['v']} » en {x['ton']}"
                for x in (lignes or [])
                for attendu, mots in VOCABULAIRE.items()
                if x["v"] in mots and x["ton"] != attendu
            ]
            journal.verifier(f"le ton d'un {nom} dit ce que son MOT veut dire",
                             not mal_dites, "; ".join(mal_dites) or "tous concordent")

        # A QUANTITY is not a state, and badging one is how a badge stops
        # meaning anything: « 1 863 titres » is neither good nor bad, it is how
        # big the library is. Read from the whole page rather than from the two
        # lists, because the temptation to badge a number lives everywhere.
        quantites = await pg.evaluate("""() => [...document.querySelectorAll('#view .flux .fx')]
          .map((x) => ({
            l: x.querySelector('.fn').textContent.trim(),
            v: x.querySelector('.fr').textContent.trim(),
            badge: !!x.querySelector('.fr .chip'),
            ton: (() => {
              const c = x.querySelector('.fr .chip');
              const T = { success: 'success', danger: 'alert',
                          warning: 'warning', info: 'info' };
              return c ? T[[...c.classList].find((k) => T[k])] || 'inconnu' : null;
            })(),
          }))
          .filter((r) => r.badge && /^[\\d\\s  ]+$/.test(r.v.replace(/titres|éléments/g, '')))""")
        mal_tonnees = [q for q in quantites if q["ton"] != "info"]
        journal.verifier("une quantité ne porte que le ton « info », jamais un succès ni une alerte",
                         not mal_tonnees, str(mal_tonnees) or f"{len(quantites)} quantité(s), toutes en info")

        # And a badge that cannot be read is a badge that is not there. This is
        # B-014's lesson applied before the defect: the chip is a TINT of its
        # own colour, and a tint is exactly where a label lands on its own
        # background.
        # BOTH themes, and the second is the one that was broken: on a white
        # card the same fills that read on near-black sat at 2.91 (success) and
        # 2.02 (warning), under AA — true of every chip in the interface long
        # before this page existed. A rule that measures one theme certifies
        # half a design.
        for theme, mise in (("sombre", "()=>document.documentElement.removeAttribute('data-theme')"),
                            ("clair", "()=>document.documentElement.setAttribute('data-theme','light')")):
            await pg.evaluate(mise)
            await pg.wait_for_timeout(220)
            for etat in (False, True):
                await surPage(pg, "sys", panne=etat)
                contrastes = await pg.evaluate(CONTRASTE)
                illisibles = [f"{c['mot']} ({c['contraste']})"
                              for c in contrastes if c["contraste"] < PLANCHER_CONTRASTE]
                journal.verifier(
                    f"chaque badge se lit sur son fond — thème {theme}"
                    + (", en panne" if etat else ""),
                    not illisibles,
                    f"{len(contrastes)} badges, plancher {PLANCHER_CONTRASTE}, le plus faible "
                    f"{min((c['contraste'] for c in contrastes), default='—')}"
                    + (f" — illisibles : {', '.join(illisibles)}" if illisibles else ""))
        await pg.evaluate("()=>document.documentElement.removeAttribute('data-theme')")
        await pg.wait_for_timeout(200)
        # `panne` is NAMED on the way back: a state driven without naming every
        # dial inherits whatever the previous one left, which is the defect R10
        # found in the interface and which this probe had just repeated.
        sys_vue = await surPage(pg, "sys", panne=False)

        journal.verifier("au repos, rien n'alerte sur cette machine",
                         all(x["ton"] == "success"
                             for x in (sys_vue["services"] or []) + (sys_vue["planificateurs"] or [])),
                         "success partout")
        journal.verifier("et l'état de repos ne se présente pas comme une simulation",
                         not sys_vue["simulee"])

        # 3ter. A screen that can only be green cannot be judged, so a named
        # state replays a fault — and SAYS it is simulated, or the operator
        # would read an invented outage as a real one (§13).
        panne = await surPage(pg, "sys", panne=True)
        rouges_s = [x for x in (panne["services"] or []) if x["ton"] == "alert"]
        rouges_p = [x for x in (panne["planificateurs"] or []) if x["ton"] == "alert"]
        journal.verifier("un état nommé montre ce qu'une alerte donne, côté services",
                         len(rouges_s) == 1, str([x["l"] for x in rouges_s]))
        journal.verifier("et côté planificateurs",
                         len(rouges_p) == 1, str([x["l"] for x in rouges_p]))
        journal.verifier("un service en panne est dit HORS LIGNE, pas en retard",
                         rouges_s and rouges_s[0]["v"] == "hors ligne",
                         str([x["v"] for x in rouges_s]))
        # The property has not changed, its PLACE has: the badge carries the
        # state and the sub-line carries how long. « il y a trois jours » on an
        # hourly job is still the whole of what one needs — a badge reading a
        # date would be a date wearing a colour, saying nothing about whether
        # that date is late.
        journal.verifier("un planificateur en retard le dit par un mot dans son badge",
                         rouges_p and rouges_p[0]["v"] == "en retard",
                         str([x["v"] for x in rouges_p]))
        journal.verifier("et DIT de combien, sous le badge",
                         rouges_p and "il y a" in rouges_p[0]["s"],
                         str([x["s"][:60] for x in rouges_p]))
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

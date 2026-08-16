"""R66 — Arrivées carries the PIPELINE's health, and says what really happened.

The cut this page obeys is by the nature of the trouble: a medium in trouble is
Arrivées, a machine in trouble is Système. That is what puts the run controls
here — DOIT-3, act where one observes — beside the stalled step they answer,
rather than one page away from it.

What this holds to:

1. The pilot's bar offers ONE control, and it is the right one for the state.
   Asked while a run is going, a run is QUEUED and says so (DOIT-4): « occupé,
   réessaie » is the answer this interface does not give.
2. All NINE steps the engine runs are drawn, in the engine's order, each named
   for what it does with the engine's own name beside it in the mono face
   (DOIT-1) — so a log can be read without a translation table.
3. A step that did nothing says so with an em dash, never « 0 ». And a step
   that did have something to look at never wears the em dash, or the row
   contradicts its own sub-line.
4. The step that BLOCKS points at what coince, on this page, rather than at a
   log.
5. **The run told here really happened.** Its counts are compared against
   `pipeline_run` in `library.db`, by run_uid — not against the last run, which
   would make this rule rot every time the pipeline fires (R63 rots exactly
   that way, and it is a seam rather than a defect). A past run does not
   change; inventing one is what this catches.
6. Nothing overflows a 390px frame in any of the three states.
"""
import asyncio
import json
import os
import pathlib
import sqlite3

from common import Journal, ouvrir
from playwright.async_api import async_playwright

LIBRARY = pathlib.Path(os.path.expanduser("~/dev/PersonalScraper/.data/library.db"))

# The engine's steps, in `DEFAULT_STEPS` execution order (docs/reference/
# commands.md § Pipeline). Written here rather than read from the prototype:
# a rule that takes its expectation from what it measures agrees with anything.
ETAPES_MOTEUR = ["ingest", "sort", "clean", "scrape", "cleanup",
                 "enforce", "verify", "trailers", "dispatch"]

LIRE = """() => {
  const port = document.querySelector('#port');
  return {
    debord: port.scrollWidth - port.clientWidth,
    etat: (document.querySelector('.pipeline .pt') || {}).textContent || '',
    boutons: [...document.querySelectorAll('.pipeline [data-pipe]')]
               .map((b) => b.dataset.pipe),
    file: !!document.querySelector('.pipeline .live'),
    uid: (window.PIPELINE_UID_POUR_LA_SONDE || null),
    etapes: [...document.querySelectorAll('.flux .fx')].map((x) => ({
      nom: x.querySelector('.fn').textContent.trim(),
      res: x.querySelector('.fr').textContent.trim(),
      sous: x.querySelector('.fs').textContent.trim(),
      cle: (x.querySelector('.fk') || {}).textContent || '',
      vide: x.classList.contains('fempty'),
      bloc: x.classList.contains('fblocked'),
    })),
    sections: [...document.querySelectorAll('.sechead .t')].map((x) => x.textContent.trim()),
  };
}"""


def run_reel(uid):
    """The run `library.db` really recorded under this uid, or None.

    Args:
        uid: The run_uid prefix the prototype prints.

    Returns:
        A dict step name → its recorded counts, or None when the database is
        absent or holds no such run.
    """
    if not LIBRARY.is_file():
        return None
    db = sqlite3.connect(f"file:{LIBRARY}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    ligne = db.execute(
        "SELECT run_uid, trigger, steps_json FROM pipeline_run "
        "WHERE run_uid LIKE ? AND kind = 'pipeline'", (uid + "%",)).fetchone()
    db.close()
    if ligne is None:
        return None
    etapes = {s["name"]: s for s in json.loads(ligne["steps_json"] or "[]")}
    return {"trigger": ligne["trigger"], "etapes": etapes}


async def surArrivees(pg, pipe="repos"):
    """Drives to Arrivées in one of the pipeline's three states."""
    await pg.evaluate(f"()=>{{state.page='arr';state.pipe='{pipe}';render();}}")
    await pg.wait_for_timeout(320)
    return await pg.evaluate(LIRE)


async def main():
    journal = Journal("R66 — Arrivées porte la santé du pipeline")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await ouvrir(b)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        # The uid and the counts the prototype claims, read from its own data
        # rather than scraped off the screen — the screen is what is being
        # judged against them.
        revendique = await pg.evaluate("()=>({uid: PIPELINE.dernier.uid,"
                                       " decl: PIPELINE.dernier.declencheur,"
                                       " faits: PIPELINE.dernier.faits})")

        vue = await surArrivees(pg, "repos")

        # ── 1. the pilot's bar ─────────────────────────────────────────────
        journal.verifier("au repos, une seule commande, et c'est « lancer »",
                         vue["boutons"] == ["lancer"], str(vue["boutons"]))
        journal.verifier("au repos, l'état est nommé", vue["etat"] == "Au repos",
                         vue["etat"])

        # The journey, not a named state. Both of the following are reached by
        # TAPPING, because a queue nobody can reach by a gesture is a branch no
        # gesture can enter — and driving `state.pipe` straight to it would
        # certify exactly that. The first version of this rule did.
        await pg.tap('.pipeline [data-pipe="lancer"]')
        await pg.wait_for_timeout(350)
        encours = await pg.evaluate(LIRE)
        journal.verifier("appuyer sur « lancer » met le pipeline en cours",
                         encours["etat"] == "En cours", encours["etat"])
        journal.verifier("en cours, on peut toujours DEMANDER un autre passage",
                         "lancer" in encours["boutons"] and "arreter" in encours["boutons"],
                         str(encours["boutons"]))
        journal.verifier("en cours, rien ne prétend qu'un passage est déjà en file",
                         not encours["file"])

        await pg.tap('.pipeline [data-pipe="lancer"]')
        await pg.wait_for_timeout(350)
        file = await pg.evaluate(LIRE)
        journal.verifier("un passage demandé PENDANT un autre est mis en file, et le dit",
                         file["file"], f"file={file['file']} boutons={file['boutons']}")
        journal.verifier("et il n'est pas refusé : le passage en cours continue",
                         file["etat"] == "En cours" and "arreter" in file["boutons"],
                         f"{file['etat']} · {file['boutons']}")

        await pg.tap('.pipeline [data-pipe="arreter"]')
        await pg.wait_for_timeout(350)
        arrete = await pg.evaluate(LIRE)
        journal.verifier("« arrêter » ramène au repos", arrete["etat"] == "Au repos",
                         arrete["etat"])

        # ── 2. the nine steps, in the engine's order ───────────────────────
        vue = await surArrivees(pg, "repos")
        cles = [e["cle"] for e in vue["etapes"]]
        journal.verifier("les neuf étapes du moteur sont dessinées, dans son ordre",
                         cles == ETAPES_MOTEUR, str(cles))
        journal.verifier("chaque étape porte un nom français en plus de celui du moteur",
                         all(e["nom"] and e["nom"] != e["cle"] for e in vue["etapes"]),
                         str([e["nom"] for e in vue["etapes"]]))

        # ── 3. nothing to do says so, and never with a zero ────────────────
        zeros = [e["nom"] for e in vue["etapes"] if e["res"] == "0"]
        journal.verifier("aucune étape ne répond « 0 »", not zeros, str(zeros))
        muettes = [e["nom"] for e in vue["etapes"] if e["res"] == "—"]
        journal.verifier("une étape sans rien à faire porte un tiret", muettes,
                         f"{len(muettes)} : {', '.join(muettes)}")
        # An em dash beside a sub-line that describes work is a row arguing
        # with itself. The engine name always sits in the sub-line, so what is
        # looked for is anything BEYOND it.
        contradictions = [
            e["nom"] for e in vue["etapes"]
            if e["res"] == "—" and e["sous"].replace(e["cle"], "").strip(" ·")
            not in ("", "rien à faire")]
        journal.verifier("aucune étape ne dit « rien » à côté de ce qu'elle a fait",
                         not contradictions, str(contradictions))

        # ── 4. what blocks points at what coince ───────────────────────────
        bloquantes = [e for e in vue["etapes"] if e["bloc"]]
        journal.verifier("l'étape qui bloque est signalée", len(bloquantes) == 1,
                         str([e["nom"] for e in bloquantes]))
        if bloquantes:
            journal.verifier("et elle renvoie à ce qui coince, sur cette page",
                             "coince" in bloquantes[0]["sous"], bloquantes[0]["sous"])
        journal.verifier("« Ça coince » est bien sur la page",
                         "Ça coince" in vue["sections"], str(vue["sections"]))
        journal.verifier("et « Arrivé dans les 24 h » aussi",
                         "Arrivé dans les 24 h" in vue["sections"], str(vue["sections"]))

        # ── 5. the run told here really happened ───────────────────────────
        reel = run_reel(revendique["uid"])
        if reel is None:
            journal.verifier("le run raconté existe dans library.db", False,
                             f"aucun run {revendique['uid']}… "
                             + ("(base absente)" if not LIBRARY.is_file() else ""))
        else:
            journal.verifier("le run raconté existe dans library.db", True,
                             f"{revendique['uid']}… · {reel['trigger']}")
            journal.verifier("le déclencheur est celui que la base a enregistré",
                             revendique["decl"] == reel["trigger"],
                             f"{revendique['decl']} vs {reel['trigger']}")
            # Every count the prototype prints is checked against the step the
            # engine recorded. Only the numbers are compared: the sentence is
            # the interface's business, the figure is the engine's.
            ecarts = []
            for fait in revendique["faits"]:
                etape = reel["etapes"].get(fait["n"])
                if etape is None:
                    ecarts.append(f"{fait['n']} absent de la base")
                    continue
                for texte in (fait.get("r") or "", fait.get("s") or ""):
                    for mot in texte.split():
                        if mot.isdigit():
                            n = int(mot)
                            if n not in (etape.get("success_count"),
                                         etape.get("skip_count"),
                                         etape.get("error_count")):
                                ecarts.append(f"{fait['n']} : {n} n'est aucun de "
                                              f"{etape.get('success_count')}/"
                                              f"{etape.get('skip_count')}/"
                                              f"{etape.get('error_count')}")
            journal.verifier("chaque chiffre affiché est un chiffre du run réel",
                             not ecarts, "; ".join(ecarts) or "tous concordent")

        # ── 6. nothing overflows, in any state ─────────────────────────────
        for nom, mesure in (("au repos", vue), ("en cours", encours), ("en file", file)):
            journal.verifier(f"rien ne déborde du cadre {nom}", mesure["debord"] <= 0,
                             f"{mesure['debord']}px")

        journal.verifier("aucune erreur JS", not erreurs, str(erreurs))
        await ctx.close()
        await b.close()

    journal.bilan()


asyncio.run(main())

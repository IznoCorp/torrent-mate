"""R63 — a card says what the engine knows, and two tabs say it the same way.

A followed medium's card was three short lines beside a poster and the rest of
it was empty — while every fact it was missing already sat in `acquire.db`, and
« En cours » was already printing most of them for the same media. The void was
not a lack of ideas; it was two tabs describing the same objects and saying
different amounts about them.

The library's rows had the mirror problem: the year and the fraction say what a
medium IS, and nothing said what it is ABOUT. The synopsis exists — in the
`<plot>` of each medium's own NFO — and is NOT in `library.db`, which is a gap
in the read-model this script records rather than hides.

What this holds to:

  · a follow's card carries its identity, what is happening and when, and what
    tells a healthy follow from a stalled one — all read from real rows;
  · the sentence about the next search is the SAME sentence on both tabs, and
    the hour comes from the same cron the cadence line prints;
  · a library row carries the synopsis, clamped with an ellipsis, and a medium
    whose NFO has no plot shows NOTHING rather than a filler;
  · the lenses read Médias, Récents, Incomplets — everything, then what just
    arrived, then the repair list.
"""
import asyncio
import os
import pathlib
import re
import sqlite3

from commun import Journal, ouvrir
from playwright.async_api import async_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
ACQUIRE = pathlib.Path(os.path.expanduser("~/dev/PersonalScraper/.data/acquire.db"))

_journal = None


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.verifier(nom, condition, detail)


def faits_reels():
    """Returns, per followed title, the numbers `acquire.db` really holds.

    Returns:
        A dict title → {searches}. Empty when the database is not present, in
        which case the comparison against it is skipped and SAID to be skipped.
    """
    if not ACQUIRE.is_file():
        return {}
    db = sqlite3.connect(f"file:{ACQUIRE}?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    out = {}
    for f in db.execute("SELECT title, media_ref_json, series_status FROM followed_series"):
        w = db.execute("SELECT sum(attempts) att FROM wanted WHERE media_ref_json = ?",
                       (f["media_ref_json"],)).fetchone()
        out[f["title"]] = {"recherches": w["att"] or 0, "serie": f["series_status"]}
    db.close()
    return out


async def main():
    global _journal
    _journal = Journal("R63 — ce qu'une carte dit")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await ouvrir(b)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        # ── a follow's card is not empty ────────────────────────────────────
        await pg.evaluate("()=>window.__go('acq-suivis-liste')")
        await pg.wait_for_timeout(420)
        suivis = await pg.evaluate("""()=>[...document.querySelectorAll('#view .card')].map(c => ({
          titre: (c.querySelector('.ctitle')||{}).textContent||'',
          sous: (c.querySelector('.csub')||{}).textContent||'',
          raison: (c.querySelector('.creason')||{}).textContent||'',
          faits: (c.querySelector('.caption')||{}).textContent||''}))""")
        verifier("la liste des suivis a des cartes", len(suivis) > 4, str(len(suivis)))
        muettes = [s["titre"] for s in suivis if not s["sous"].strip()]
        verifier("chaque suivi dit ce qu'il est", not muettes, str(muettes[:3]))
        verifier("et une série dit si elle continue",
                 any("série · " in s["sous"] for s in suivis),
                 str([s["sous"] for s in suivis if "série" in s["sous"]][:2]))
        sansfaits = [s["titre"] for s in suivis if "recherche" not in s["faits"]]
        verifier("et depuis quand on cherche, et combien de fois",
                 not sansfaits, str(sansfaits[:3]))

        # Compared against the DATABASE, not against itself: a card printing a
        # number the engine never held would otherwise pass.
        reels = faits_reels()
        if not reels:
            verifier("les nombres viennent de acquire.db",
                     False, f"base absente : {ACQUIRE}")
        else:
            faux = []
            for s in suivis:
                r = reels.get(s["titre"])
                if not r:
                    continue
                # Word-boundary match, not substring: « 1 recherche » must not
                # pass against a card actually printing « 11 recherches ».
                motif = rf"\b{r['recherches']}\s+recherche"
                if not re.search(motif, s["faits"]):
                    faux.append(f"{s['titre']} : « {s['faits']} » vs {r['recherches']}")
            verifier("les nombres viennent de acquire.db, pas de la maquette",
                     not faux, str(faux[:3]))

        # ── the two tabs say the same thing the same way ────────────────────
        # « En cours » already had the sentence; the follow tab had none, and
        # two tabs about the same media must not phrase the same fact twice.
        await pg.evaluate("()=>window.__go('acq-encours-charge')")
        await pg.wait_for_timeout(420)
        encours = await pg.evaluate("""()=>[...document.querySelectorAll('#view .creason')]
          .map(e => e.textContent)""")
        phrase = "Aucune release conforme"
        verifier("« En cours » explique une recherche infructueuse",
                 any(phrase in r for r in encours), str(encours[:1]))
        verifier("et « Suivis » l'explique de la MÊME façon",
                 any(phrase in s["raison"] for s in suivis),
                 str([s["raison"] for s in suivis][:1]))

        # The hour is derived from the cron the cadence line prints, so the two
        # can never disagree about when the next search happens.
        heure = await pg.evaluate(
            "()=>prochaineRechercheFR(CADENCE_CRON, new Date())")
        cadence = await pg.evaluate("()=>cadenceFR(CADENCE_CRON)")
        verifier("l'heure annoncée est celle de la cadence",
                 bool(heure) and heure in cadence, f"{heure} dans « {cadence} »")
        verifier("et les cartes l'annoncent",
                 any(heure in s["raison"] for s in suivis if s["raison"]),
                 heure or "aucune heure")

        # ── the library says what a medium is ABOUT ─────────────────────────
        for lentille, nom in (("cat", "Médias"), ("rec", "Récents")):
            await pg.evaluate("(l)=>{state.page='lib'; state.libLens=l; "
                              "state.libMode='list'; render();}", lentille)
            await pg.wait_for_timeout(650)
            vu = await pg.evaluate("""()=>{
              const cartes = [...document.querySelectorAll('#libitems .card')];
              return {
                n: cartes.length,
                avec: cartes.filter(c => c.querySelector('.cov')).length,
                coupes: cartes.filter(c => {
                  const e = c.querySelector('.cov');
                  return e && e.scrollHeight > e.clientHeight + 1;}).length,
                debordent: cartes.filter(c => {
                  const e = c.querySelector('.cov');
                  return e && e.getBoundingClientRect().bottom >
                              c.getBoundingClientRect().bottom + 1;}).length,
                inventes: cartes.filter(c => {
                  const e = c.querySelector('.cov');
                  return e && !SYNOPSIS[(c.querySelector('.ctitle')||{}).textContent];
                }).map(c => (c.querySelector('.ctitle')||{}).textContent)};}""")
            verifier(f"{nom} : les lignes portent le synopsis",
                     vu["n"] > 4 and vu["avec"] == vu["n"], f"{vu['avec']}/{vu['n']}")
            verifier(f"{nom} : un synopsis trop long est coupé, pas débordé",
                     vu["coupes"] > 0 and vu["debordent"] == 0,
                     f"{vu['coupes']} coupé(s), {vu['debordent']} débordant(s)")
            verifier(f"{nom} : aucun synopsis inventé",
                     not vu["inventes"], str(vu["inventes"][:3]))

        # The clamp uses the room the card HAS, and the number is not a taste:
        # it is the largest that keeps every card at its floor. Checked both
        # ways — this many fits, one more does not — so raising or lowering it
        # without re-measuring fails here. Two was inherited from a card that had
        # no floor, and left a third of the row empty.
        async def cartes_qui_grandissent(n):
            """Returns how many library cards exceed the floor at n clamped lines."""
            await pg.evaluate("""(n)=>{
              let st = document.querySelector('#essaiclamp');
              if (!st) { st = document.createElement('style'); st.id = 'essaiclamp';
                         document.head.appendChild(st); }
              st.textContent = '.cov{-webkit-line-clamp:' + n + ' !important}';}""", n)
            await pg.evaluate("()=>{state.page='lib'; state.libLens='cat'; "
                              "state.libMode='list'; render();}")
            await pg.wait_for_timeout(520)
            return await pg.evaluate(
                """()=>[...document.querySelectorAll('#libitems .card')]
                     .filter(c => c.getBoundingClientRect().height > 127).length""")

        lignes = await pg.evaluate(
            """()=>Number(getComputedStyle(document.querySelector('#libitems .cov'))
                 .webkitLineClamp)""")
        verifier("le synopsis prend plus de deux lignes", lignes > 2, str(lignes))
        verifier("et aucune carte ne grandit pour lui",
                 (await cartes_qui_grandissent(lignes)) == 0, f"à {lignes} lignes")
        verifier("une ligne de plus ne tiendrait pas",
                 (await cartes_qui_grandissent(lignes + 1)) > 0, f"à {lignes + 1} lignes")
        await pg.evaluate("""()=>{const st = document.querySelector('#essaiclamp');
                               if (st) st.remove();}""")
        await pg.evaluate("()=>{state.page='lib'; state.libLens='cat'; "
                          "state.libMode='list'; render();}")
        await pg.wait_for_timeout(520)

        # A clamped line must SAY it is clamped rather than stop mid-word.
        points = await pg.evaluate(
            "()=>getComputedStyle(document.querySelector('#libitems .cov')).textOverflow")
        verifier("et la coupure se voit — points de suspension",
                 points == "ellipsis", points)

        # A medium whose NFO carries no plot shows nothing rather than a filler.
        # Reading only the rows on screen proves nothing — the first two dozen
        # all have a plot — so the row is BUILT for a title known to lack one.
        manquants = await pg.evaluate(
            "()=>LIBRARY.filter(x => !(x.t in SYNOPSIS)).map(x => x.t)")
        verifier("un média sans synopsis existe dans la médiathèque",
                 len(manquants) > 0, f"{len(manquants)} sans plot : {manquants[:3]}")
        if manquants:
            vide = await pg.evaluate("""(t)=>{
              const item = LIBRARY.find(x => x.t === t);
              const d = document.createElement('div');
              d.innerHTML = libRowHTML(item, 0);
              const cov = d.querySelector('.cov');
              return cov ? cov.textContent : null;}""", manquants[0])
            verifier("et sa ligne n'affiche aucun texte de remplacement",
                     vide is None, str(vide))

        # ── the list starts at the same height on all three lenses ─────────
        # Each put its context line somewhere else — outside the body, inside
        # it, inside a section of its own — so switching tabs made the page
        # jump. Checked in both modes, because a grid and a list are two
        # different first elements and only one of them was ever looked at.
        for mode in ("list", "grid"):
            debuts = {}
            for lentille in ("cat", "rec", "inc"):
                await pg.evaluate("([l, m])=>{state.page='lib'; state.libLens=l; "
                                  "state.libMode=m; render();}", [lentille, mode])
                await pg.wait_for_timeout(620)
                debuts[lentille] = await pg.evaluate("""()=>{
                  const cadre = document.querySelector('#device').getBoundingClientRect();
                  const p = document.querySelector('#view .card, #view .tile');
                  return p ? Math.round(p.getBoundingClientRect().top - cadre.top) : null;}""")
            manquant = [k for k, v in debuts.items() if v is None]
            ecart = (max(debuts.values()) - min(debuts.values())) if not manquant else None
            verifier(f"en {mode}, chaque lentille dessine une liste", not manquant,
                     str(manquant))
            if not manquant:
                verifier(f"et en {mode} la liste démarre à la même hauteur",
                         ecart <= 1, f"{debuts} — écart {ecart}px")

        # ── the lenses, in the order one reaches for them ───────────────────
        onglets = await pg.evaluate(
            """()=>[...document.querySelectorAll('[data-lens]')]
                 .map(e => e.dataset.lens)""")
        verifier("les lentilles vont de tout à la liste de réparation",
                 onglets == ["cat", "rec", "inc"], str(onglets))

        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await b.close()

    _journal.bilan()

asyncio.run(main())

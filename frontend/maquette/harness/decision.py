"""R57 — the arbitration screen, and what a decision is.

A scrape decision is a FOLDER the scrape could not name. Everything on this
screen follows from that, and every check here is one of the ways the drawing
could quietly stop being true:

  · the card's subject is the folder, set in the mono face and never cleaned
    up — recognising what is on disk is the whole point;
  · a decision is not a medium, so it promises neither a sheet nor a panel,
    the same way a release candidate promises neither;
  · the reason it is waiting is said in words, never in the engine's token;
  · the score is printed only when it SEPARATES. « Lucky » is the case that
    settles it: four of its five candidates came back at exactly the same
    score, and printing it four times would suggest a ranking that does not
    exist — which is the opposite of what the screen is asking for;
  · there are always three ways out, and the third used to be missing: pick a
    candidate, search by hand, or leave the folder as it is. Without the last,
    one could only ever disagree with the machine, never agree with it;
  · a folder with no pending decision borrows nobody's candidates. Showing
    another folder's would be the worst possible lie on the one screen whose
    job is to name what is on disk;
  · and answering takes the folder out of the queue, on BOTH lists it appears
    on. « À traiter » on the acquisition side used to keep it forever.
"""
import asyncio

from playwright.async_api import async_playwright

BAR = "─" * 62

# The engine's own words. None of them may reach a screen.
JETONS = ["below_threshold", "mid_band", "ambiguous", "manual", "dismissed",
          "superseded", "resolved", "pending", "search_override", "staging_path"]

echecs = []
faits = 0


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict."""
    global faits
    faits += 1
    print(("  OK   " if condition else "  ECHEC") + f" {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


ECRAN = """() => {
  const s = document.querySelector('#screen');
  const cartes = [...s.querySelectorAll('.card')];
  const decisions = cartes.filter(c => c.dataset.nonmedia === 'decision');
  const candidats = cartes.filter(c => c.dataset.nonmedia === 'candidat');
  return {
    titre: (s.querySelector('.h2') || {}).textContent || '',
    titreMono: !!s.querySelector('.h2 code'),
    candidats: candidats.map(c => ({
      titre: (c.querySelector('.ctitle') || {}).textContent || '',
      confiance: (c.querySelector('.chip') || {}).textContent || null,
      posterBouton: (c.querySelector('.poster') || {}).tagName === 'BUTTON',
      panneau: (c.querySelector('.cbody') || {}).dataset?.panel || null,
      affiche: (c.querySelector('.poster img') || {}).src || null,
      sansAffiche: !!c.querySelector('.poster .pfall'),
    })),
    decisions: decisions.map(c => ({
      dossier: (c.querySelector('.ctitle') || {}).textContent || '',
      mono: !!c.querySelector('.ctitle code'),
      posterBouton: (c.querySelector('.poster') || {}).tagName === 'BUTTON',
      panneau: (c.querySelector('.cbody') || {}).dataset?.panel || null,
      puces: [...c.querySelectorAll('.chip')].map(x => x.textContent.trim()),
    })),
    sorties: [...s.querySelectorAll('.sact, .cfoot')].map(x => x.textContent.trim()),
    texte: (s.textContent || '').replace(/\\s+/g, ' '),
  };
}"""


async def main():
    print(f"{BAR}\nR57 — l'écran de résolution\n{BAR}")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await pg.evaluate("()=>window.__measure(true)")

        # ── with candidates: the tie, and what it forbids ──────────────────
        await pg.evaluate("()=>window.__go('arr-decision')")
        await pg.wait_for_timeout(420)
        avec = await pg.evaluate(ECRAN)

        verifier("le dossier est le sujet, en chasse fixe", avec["titreMono"], avec["titre"][:40])
        verifier("les cinq candidats réels sont là", len(avec["candidats"]) == 5,
                 str(len(avec["candidats"])))
        verifier("aucun candidat ne promet une fiche ni un panneau",
                 not any(c["posterBouton"] or c["panneau"] for c in avec["candidats"]))

        # The four that tie carry no percentage; the fifth, which differs, does.
        sans_score = [c for c in avec["candidats"] if not c["confiance"]]
        avec_score = [c for c in avec["candidats"] if c["confiance"]]
        verifier("les ex æquo n'affichent aucun score", len(sans_score) == 4,
                 f"{len(sans_score)} sans score")
        verifier("celui qui se détache affiche le sien", len(avec_score) == 1,
                 str([c["confiance"] for c in avec_score]))
        verifier("et l'écran dit pourquoi il ne classe pas",
                 "ne tranche pas" in avec["texte"])

        # A candidate wearing a neighbour's poster is the one mistake this
        # screen cannot make: four of these five are DIFFERENT series with
        # nearly the same name, and the picture is what tells them apart.
        # « Lucky (2006) » was showing « Lucky (2026) »'s poster while its own
        # line said the provider had none.
        affiches = [c["affiche"] for c in avec["candidats"] if c["affiche"]]
        verifier("aucun candidat ne porte l'affiche d'un autre",
                 len(affiches) == len(set(affiches)),
                 f"{len(affiches)} affiches, {len(set(affiches))} distinctes")
        verifier("celui que le provider n'illustre pas montre le substitut",
                 sum(1 for c in avec["candidats"] if c["sansAffiche"]) == 1,
                 str([c["titre"] for c in avec["candidats"] if c["sansAffiche"]]))

        # ── the three ways out ────────────────────────────────────────────
        verifier("on peut choisir un candidat",
                 sum(1 for x in avec["sorties"] if "celui-ci" in x) == 5)
        verifier("on peut chercher à la main",
                 any("manuellement" in x for x in avec["sorties"]))
        verifier("on peut laisser tel quel",
                 any("Laisser tel quel" in x for x in avec["sorties"]))

        # ── the settled ones, and what they are ───────────────────────────
        verifier("les décisions réglées sont rappelées", len(avec["decisions"]) >= 5,
                 str(len(avec["decisions"])))
        verifier("chacune montre le DOSSIER, en chasse fixe",
                 all(d["mono"] for d in avec["decisions"]))
        verifier("aucune ne promet une fiche ni un panneau",
                 not any(d["posterBouton"] or d["panneau"] for d in avec["decisions"]))
        verifier("chacune dit son motif ET ce qu'elle est devenue",
                 all(len(d["puces"]) >= 2 for d in avec["decisions"]),
                 str([d["puces"] for d in avec["decisions"]][:2]))

        # ── no engine token ever reaches a screen ─────────────────────────
        fuites = [j for j in JETONS if j in avec["texte"]]
        verifier("aucun jeton du moteur à l'écran", not fuites, ", ".join(fuites))

        # ── without candidates: nothing is borrowed ───────────────────────
        await pg.evaluate("()=>window.__go('arr-resolution')")
        await pg.wait_for_timeout(420)
        sans = await pg.evaluate(ECRAN)
        verifier("un dossier sans décision n'emprunte aucun candidat",
                 len(sans["candidats"]) == 0, str(len(sans["candidats"])))
        verifier("il dit que les providers n'ont rien renvoyé",
                 "aucun candidat" in sans["texte"].lower())
        verifier("et il garde ses deux autres sorties",
                 any("manuellement" in x for x in sans["sorties"])
                 and any("Laisser tel quel" in x for x in sans["sorties"]))

        # ── answering empties the queue, on BOTH lists ────────────────────
        for etat, liste, sortie in (
            ("arr-decision", "blocked", "[data-resolve]"),
            ("arr-repos", "stuck", "[data-laisser]"),
        ):
            await pg.evaluate("(s)=>window.__go(s)", etat)
            await pg.wait_for_timeout(420)
            if etat == "arr-repos":
                await pg.evaluate(
                    "()=>[...document.querySelectorAll('.cfoot')]"
                    ".find(x=>x.textContent.includes('Résoudre')).click()")
                await pg.wait_for_timeout(420)
            avant = await pg.evaluate(f"()=>derived.{liste}().length")
            # Without the way out there is nothing to click, and clicking
            # nothing raises instead of naming the defect. A crash is a
            # failure nobody can read.
            if not await pg.evaluate("(s)=>document.querySelector(s)!==null", sortie):
                verifier(f"répondre vide la file « {liste} »", False,
                         f"{sortie} absent de l'écran")
                continue
            await pg.evaluate("(s)=>document.querySelector(s).click()", sortie)
            await pg.wait_for_timeout(700)
            apres = await pg.evaluate(f"()=>derived.{liste}().length")
            verifier(f"répondre vide la file « {liste} »", apres == avant - 1,
                     f"{avant} → {apres}")

        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await b.close()

    print()
    print(f"{BAR}\n{faits} règles EXÉCUTÉES — "
          + ("aucune violation" if not echecs else f"{len(echecs)} violation(s) : {', '.join(echecs)}"))
    if echecs:
        raise SystemExit(1)

asyncio.run(main())

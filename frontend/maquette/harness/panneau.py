"""R56 — ONE bottom panel, and its shape follows the facts it is given.

The card and the tile were each reduced to a single builder taking a descriptor
of facts. The panel had not been: `openSheet` took ready-made markup, so every
surface assembled its own — three head shapes had grown that way, two of them
out of inline styles, which belong to no stylesheet and are therefore exported
nowhere. A second builder had also appeared for « whatever the first does not
recognise », and it offered six buttons of which three led nowhere at all. That
is what a fallback builder becomes: never the one being looked at, so never the
one being fixed.

An envelope guarantees nothing about what it carries. This script checks the
guarantees a builder CAN make:

  · no caller hands markup to `openSheet`;
  · nothing inside a panel is positioned by an inline style;
  · every panel has exactly one heading;
  · every action in a panel has a destination, or says why it has none;
  · a block type nobody declared is refused rather than drawn empty.
"""
import asyncio
import pathlib
import re

from playwright.async_api import async_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
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


# Every panel this interface can open, and how to reach it without knowing
# which screen draws which.
PANNEAUX = [
    ("suivi complet", "feuille-suivi-complet", None),
    ("suivi troué", "feuille-suivi-trous", None),
    ("parcours", "feuille-parcours", None),
    ("veille", "feuille-plus", None),
    ("menu utilisateur", "feuille-utilisateur", None),
    ("suggestion", "acq-decouvrir", '#view [data-panel^="sug:"]'),
    ("résultat de recherche", "acq-ajout-resultats", '#screen [data-panel^="add:"]'),
    ("tri de la médiathèque", "lib-grille", "[data-sort]"),
]

RELEVE = """() => {
  const p = document.querySelector('#sheetin');
  const enLigne = [...p.querySelectorAll('[style]')]
    .map(e => e.tagName + '.' + e.className);
  const actions = [...p.querySelectorAll('.sact')].map(b => ({
    texte: (b.textContent || '').trim().slice(0, 34),
    donnees: Object.keys(b.dataset).length,
    desactive: b.disabled}));
  return {vide: (p.textContent || '').trim().length < 8,
          titres: p.querySelectorAll('.sheettitle').length,
          enLigne, actions,
          inconnus: [...p.querySelectorAll('*')].filter(e =>
            e.tagName === 'DIV' && e.className === '').length};
}"""


async def main():
    print(f"{BAR}\nR56 — un seul panneau\n{BAR}")

    source = (RACINE / "refonte.html").read_text()

    # 1. No caller hands markup to the panel. Read on the SOURCE, because that
    #    is where an envelope is opened; the DOM only shows what came out.
    appels = re.findall(r"(?<!function )openSheet\(\s*(.{0,24})", source, re.S)
    hors_builder = [a.strip()[:24] for a in appels if not a.lstrip().startswith("panneauHTML(")]
    verifier("aucun appelant ne passe de balisage", not hors_builder,
             " · ".join(hors_builder))
    verifier("il y a bien des appelants", len(appels) >= 6, f"{len(appels)} appels")

    # 2. One builder, not two. A fallback builder is the one that rots.
    verifier("un seul constructeur de panneau",
             source.count("function panneauHTML(") == 1
             and "openDetailSheetLegacy" not in source,
             "openDetailSheetLegacy encore présent"
             if "openDetailSheetLegacy" in source else "")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        # The startup screen covers the frame for as long as the load it stands
        # for lasts. Nothing is being fetched here, so the harness closes that
        # wait through the same seam the app uses, rather than sleeping it out.
        await pg.evaluate("()=>window.__chargementTermine?.()")
        await pg.evaluate("()=>window.__measure(true)")

        vides, styles, titres, sans_destination = [], [], [], []
        for nom, etat, clic in PANNEAUX:
            await pg.evaluate("(s)=>window.__go(s)", etat)
            await pg.wait_for_timeout(320)
            if clic:
                await pg.evaluate("(s)=>document.querySelector(s).click()", clic)
                await pg.wait_for_timeout(320)
            r = await pg.evaluate(RELEVE)
            if r["vide"]:
                vides.append(nom)
            if r["enLigne"]:
                styles.append(f"{nom} : {', '.join(r['enLigne'][:3])}")
            if r["titres"] != 1:
                titres.append(f"{nom} ({r['titres']})")
            for action in r["actions"]:
                if action["donnees"] == 0 and not action["desactive"]:
                    sans_destination.append(f"{nom} : « {action['texte']} »")

        verifier(f"les {len(PANNEAUX)} panneaux s'ouvrent et portent du contenu",
                 not vides, ", ".join(vides))
        verifier("aucun style en ligne dans un panneau", not styles, " · ".join(styles))
        verifier("un seul titre par panneau", not titres, ", ".join(titres))
        # The exact defect the fallback builder shipped: a button that looks
        # like an action and answers nothing. A disabled one is allowed — it
        # says of itself that it does nothing yet.
        verifier("aucune action sans destination", not sans_destination,
                 " · ".join(sans_destination))

        # 3. A block the builder does not know is REFUSED. Silence here would
        #    draw an empty panel and blame the data.
        refus = await pg.evaluate("""()=>{try{
            window.__panneauInconnu();
            return "aucun refus";
          }catch(e){return String(e.message||e);}}""")
        verifier("un bloc non déclaré est refusé",
                 "bloc de panneau inconnu" in refus, refus)

        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await b.close()

    print()
    print(f"{BAR}\n{faits} règles EXÉCUTÉES — "
          + ("aucune violation" if not echecs else f"{len(echecs)} violation(s) : {', '.join(echecs)}"))
    if echecs:
        raise SystemExit(1)

asyncio.run(main())

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

  · no caller hands markup to the panel;
  · nothing inside a panel is positioned by an inline style;
  · every panel has exactly one heading;
  · every action in a panel has a destination, or says why it has none;
  · a block type nobody declared is refused rather than drawn empty.

The builder and the verb have MOVED: the constructor is the component
`design/src/composants/panneau.tsx`, and a producer opens a panel by calling
the shell's `window.__panneau.ouvrir(descripteur)` rather than the engine's own
`openSheet(panneauHTML({…}))`. The two source checks below follow them there.
What they hold is unchanged — one constructor, no second one, and every caller
handing FACTS rather than markup — and the behavioural checks that follow are
untouched: they read the panel as drawn, and a panel is a panel wherever it is
built.
"""
import asyncio
import pathlib
import re

from commun import Journal, ouvrir
from playwright.async_api import async_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent

_journal = None


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.verifier(nom, condition, detail)


# Every panel this interface can open, and how to reach it without knowing
# which screen draws which.
PANNEAUX = [
    ("suivi complet", "feuille-suivi-complet", None),
    ("suivi troué", "feuille-suivi-trous", None),
    ("parcours", "feuille-parcours", None),
    ("veille", "feuille-plus", None),
    ("menu utilisateur", "feuille-utilisateur", None),
    ("suggestion", "acq-decouvrir", '#view [data-panel^="sug:"]'),
    # The add screen left `#screen` for a real route (`/ajout`, rendered
    # inside `#coquille`) — its results live under `.screen.open` now.
    ("résultat de recherche", "acq-ajout-resultats", '.screen.open [data-panel^="add:"]'),
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
    global _journal
    _journal = Journal("R56 — un seul panneau")

    source = (RACINE / "design" / "refonte.html").read_text()
    composant = (RACINE / "design" / "src" / "composants" / "panneau.tsx").read_text()

    # 1. No caller hands markup to the panel. Read on the SOURCE, because that
    #    is where a panel is asked for; the DOM only shows what came out. A
    #    descriptor is an OBJECT — a call opening on anything else (a string, a
    #    template literal, a variable holding ready-made markup) is an envelope.
    appels = re.findall(r"window\.__panneau\.ouvrir\(\s*(.{0,24})", source, re.S)
    hors_builder = [a.strip()[:24] for a in appels if not a.lstrip().startswith("{")]
    verifier("aucun appelant ne passe de balisage", not hors_builder,
             " · ".join(hors_builder))
    verifier("il y a bien des appelants", len(appels) >= 6, f"{len(appels)} appels")

    # 2. One builder, not two. A fallback builder is the one that rots. The
    #    engine's own builder must not come back either: two constructors are
    #    two head shapes, whichever file they live in.
    verifier("un seul constructeur de panneau",
             composant.count("export function PanneauContenu(") == 1
             and "function panneauHTML(" not in source
             and "openDetailSheetLegacy" not in source,
             "openDetailSheetLegacy encore présent"
             if "openDetailSheetLegacy" in source else
             "panneauHTML est revenu dans refonte.html"
             if "function panneauHTML(" in source else
             f"{composant.count('export function PanneauContenu(')} PanneauContenu")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await ouvrir(b)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
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

    _journal.bilan()

asyncio.run(main())

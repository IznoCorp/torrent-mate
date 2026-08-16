"""R61 — every colour a rule names is a colour the document defines.

A `var(--name)` whose property is never defined, and which carries no fallback,
is invalid at computed-value time. It does not raise, it does not warn, and it
does not render as an obvious mistake: a `color` falls back to the inherited
one and a `background` disappears entirely. The screen keeps rendering, so it
keeps passing — it simply stops being the design.

That is how the palette was renamed to `--primary` while eleven declarations
kept the old `--accent` name. The wordmark lost its second colour, the sign-in
button lost its background, the install button lost its background, and the
startup bar's fill turned invisible. The host page hid it: it retyped
`--accent: #f5a524` into a block of its own, so the ONE place the screen was
ever looked at rendered correctly.

This script holds two things, because either one alone is escapable:

  · statically, no `var(--x)` without a fallback names a property the document
    never defines — this covers the surfaces no state ever visits;
  · on screen, the brand colour is ACTUALLY painted where the design puts it —
    a declaration can be present and still be overridden into nothing.
"""
import asyncio
import pathlib
import re

from common import Journal, open_page
from playwright.async_api import async_playwright

PROTOTYPE = pathlib.Path(__file__).resolve().parent.parent / "design" / "refonte.html"

_journal = None


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(nom, condition, detail)


def pendantes(source):
    """Returns every custom property referenced without a fallback and never defined.

    Args:
        source: The prototype's full source.

    Returns:
        A dict property name → number of references lacking a fallback.
    """
    definies = set(re.findall(r"(--[\w-]+)\s*:", source))
    manquantes = {}
    for m in re.finditer(r"var\(\s*(--[\w-]+)\s*(,)?", source):
        nom, repli = m.group(1), m.group(2)
        # A reference carrying a fallback degrades on purpose; only a bare one
        # is a promise the document does not keep.
        if not repli and nom not in definies:
            manquantes[nom] = manquantes.get(nom, 0) + 1
    return manquantes


# Where the brand colour must actually land. Each entry names a state, a
# selector, and which painted property has to carry it.
PEINTURES = [
    ("connexion", ".brandbig .mk", "color", "l'entonnoir de la marque"),
    ("connexion", ".brandbig em", "color", "le second mot de la marque"),
    ("connexion", ".loginsubmit", "backgroundColor", "le bouton de connexion"),
    ("demarrage", ".splashbar i", "backgroundColor", "le remplissage de la barre"),
]


async def main():
    global _journal
    _journal = Journal("R61 — la palette tient ses promesses")

    source = PROTOTYPE.read_text()
    manquantes = pendantes(source)
    verifier("aucune couleur référencée sans être définie",
             not manquantes,
             ", ".join(f"{k} ×{v}" for k, v in sorted(manquantes.items())))

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx, pg = await open_page(b)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        await pg.evaluate("()=>window.__measure(true)")

        marque = await pg.evaluate(
            "()=>getComputedStyle(document.documentElement).getPropertyValue('--primary').trim()")
        verifier("la couleur de marque est définie", bool(marque), marque)

        # The comparison is against the RESOLVED brand colour rather than a
        # literal, so changing the palette moves both sides together.
        reference = await pg.evaluate(
            """(c)=>{const d=document.createElement('div'); d.style.color=c;
                     document.body.appendChild(d);
                     const v=getComputedStyle(d).color; d.remove(); return v;}""",
            marque)

        for etat, selecteur, propriete, quoi in PEINTURES:
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(400)
            peint = await pg.evaluate(
                """([s, p])=>{const e=document.querySelector(s);
                              return e ? getComputedStyle(e)[p] : null;}""",
                [selecteur, propriete])
            verifier(f"{quoi} porte la couleur de marque",
                     peint == reference, f"{peint} au lieu de {reference}")

        # And nothing anywhere paints a background that resolved to nothing —
        # the visible symptom of a dangling property, on every named state.
        transparents = []
        for etat in await pg.evaluate("()=>window.__states()"):
            await pg.evaluate("(i)=>window.__go(i)", etat)
            await pg.wait_for_timeout(120)
            vus = await pg.evaluate("""()=>{
              const perdus = [];
              for (const e of document.querySelectorAll('.loginsubmit, .installgo, .splashbar i')) {
                const c = getComputedStyle(e);
                if (c.backgroundColor === 'rgba(0, 0, 0, 0)' && e.offsetParent !== null)
                  perdus.push(e.className);
              }
              return perdus;}""")
            transparents += [f"{etat}:{v}" for v in vus]
        verifier("aucun bouton de marque ne rend un fond transparent",
                 not transparents, str(transparents[:3]))

        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await b.close()

    _journal.summary()

asyncio.run(main())

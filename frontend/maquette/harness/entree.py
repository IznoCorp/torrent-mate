"""R62 — the sign-in screen is ONE screen, wherever one meets it.

It is met twice. Arriving at the design host, before any session exists, it is
the whole page and the host builds it. Signing out inside the prototype, it is
a layer over the phone frame. Two documents, one screen — and nothing compared
them, so they drifted: the host retyped a palette the prototype had renamed,
and the screen inherited a type scale from whatever it was dropped into,
rendering 16px in one place and 14px in the other.

Comparing renderings, not sources, is the point. A shared source proves
nothing on its own: the host legitimately adjusts what a page needs that a
layer does not, and an adjustment is exactly where a difference hides.

What this script holds to:

  · the two renderings agree on geometry, colour and type for every part of the
    screen — the wordmark, the card, the fields, the button;
  · they say the same words;
  · the host takes its palette from the prototype rather than carrying one.
"""
import asyncio
import pathlib
import re

from playwright.async_api import async_playwright

RACINE = pathlib.Path(__file__).resolve().parent.parent
HOTE = "https://tm-design.iznogoudatall.xyz/"
BAR = "─" * 62

# Position is compared as a LOCAL geometry — each part against the screen's own
# box — because the host page and the phone frame are not required to sit at
# the same place in the viewport, only to draw the same screen.
RELEVE = """() => {
  const cadre = document.querySelector('.loginscreen').getBoundingClientRect();
  const cibles = ['.brandbig .mk', '.brandbig .wm', '.brandbig em', '.logincard',
                  '.loginfield input', '.loginsubmit'];
  const out = {};
  for (const s of cibles) {
    const e = document.querySelector('.loginscreen ' + s);
    if (!e) { out[s] = 'ABSENT'; continue; }
    const r = e.getBoundingClientRect(), c = getComputedStyle(e);
    out[s] = {
      l: r.width, h: r.height, dx: r.x - cadre.x, dy: r.y - cadre.y,
      couleur: c.color, fond: c.backgroundColor,
      police: c.fontFamily.split(',')[0], taille: c.fontSize,
      graisse: c.fontWeight, rayon: c.borderRadius,
    };
  }
  out['__mots'] = document.querySelector('.loginscreen')
                    .textContent.replace(/\\s+/g, ' ').trim();
  return out;
}"""

echecs = []
faits = 0


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict."""
    global faits
    faits += 1
    print(("  OK   " if condition else "  ECHEC") + f" {nom}" + (f" — {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


async def main():
    print(f"{BAR}\nR62 — un seul écran d'entrée\n{BAR}")

    # The host must not carry a palette of its own: a retyped value renders
    # correctly here while the reference is broken, which is how the brand
    # colour stayed lost for as long as it did.
    hote = (RACINE / "serve.py").read_text()
    # Everything the host contributes on its own — as opposed to what it
    # extracts — is checked, not one named block: moving the copy into a
    # differently-named string would otherwise walk straight past the rule.
    propre = "\n".join(m.group(1) for m in
                       re.finditer(r'= \"\"\"(.*?)\"\"\"', hote, re.S))
    interdits = re.findall(r"(--[\w-]+)\s*:", propre)
    interdits += re.findall(r"\b(font-family|line-height|font-size|"
                            r"-webkit-font-smoothing|font-variant-numeric)\s*:", propre)
    verifier("l'hôte ne redéclare rien que la référence possède",
             not interdits, str(sorted(set(interdits))))

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        erreurs = []

        pg = await ctx.new_page()
        pg.on("pageerror", lambda e: erreurs.append(f"hôte: {e}"))
        await pg.goto(HOTE, wait_until="load")
        await pg.wait_for_timeout(500)
        arrivee = await pg.evaluate(RELEVE)

        pg2 = await ctx.new_page()
        pg2.on("pageerror", lambda e: erreurs.append(f"prototype: {e}"))
        await pg2.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await pg2.evaluate("()=>document.querySelector('#toastx').click()")
        await pg2.wait_for_timeout(250)
        await pg2.evaluate("()=>deconnecter()")
        await pg2.wait_for_timeout(700)
        sortie = await pg2.evaluate(RELEVE)
        await b.close()

    verifier("les deux rendus portent les mêmes parties",
             sorted(arrivee) == sorted(sortie)
             and not [k for k in arrivee if arrivee[k] == "ABSENT"],
             str([k for k in arrivee if arrivee[k] == "ABSENT"]))

    verifier("et ils disent les mêmes mots",
             arrivee["__mots"] == sortie["__mots"],
             f"{arrivee['__mots'][:44]!r} vs {sortie['__mots'][:44]!r}")

    # Colour, type and radius are compared EXACTLY: a difference there is always a
    # decision that drifted. Geometry allows one pixel, and only one: both boxes
    # measure 390x844 to the pixel, so what is left is a flex centring landing on
    # a half pixel and rounding two ways. Real drift is never one pixel.
    GEOMETRIE = {"l", "h", "dx", "dy"}
    for cle in [k for k in arrivee if not k.startswith("__")]:
        a, s = arrivee[cle], sortie.get(cle)
        if not (isinstance(a, dict) and isinstance(s, dict)):
            ecarts = {"tout": (a, s)}
        else:
            ecarts = {k: (a[k], s[k]) for k in a
                      if (abs(a[k] - s[k]) > 1 if k in GEOMETRIE else a[k] != s[k])}
        verifier(f"« {cle} » rend pareil des deux côtés", not ecarts,
                 "; ".join(f"{k}: hôte={va} prototype={vs}"
                           for k, (va, vs) in list(ecarts.items())[:3]))

    verifier("aucune erreur JS", not erreurs, str(erreurs))

    print()
    print(f"{BAR}\n{faits} règles EXÉCUTÉES — "
          + ("aucune violation" if not echecs else f"{len(echecs)} violation(s) : {', '.join(echecs)}"))
    if echecs:
        raise SystemExit(1)

asyncio.run(main())

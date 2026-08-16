"""R65 — the drawer is a place one passes through, not a route.

Three defects lived here at once, and every existing rule stayed green through
all of them, because each drove a named state instead of walking the journey.

· Every entry led nowhere. The close unwound the layer's own history entry with
  `history.back()`, which is asynchronous, so its pop landed AFTER the arrival
  had rendered — and the popstate handler read that pop as a navigation and
  applied the entry underneath, which describes where one already was. The page
  changed for one frame and was put back.
· One entry pointed at an id no page carries, and answered a tap with a message.
· The entry marking where one IS was painted in its own colour: the background
  fell back onto `--primary` because `--sidebar-accent` is defined nowhere, and
  the label is `--primary` too. Contrast 1.00 — a label in invisible ink.

What the drawer owes, and what this script holds it to:

1. Every entry names a page that exists, and reaching it ARRIVES — measured
   after the frame settles, not on the frame the tap produced.
2. The drawer leaves nothing behind. A back from the destination lands where
   one was BEFORE opening it, because the destination took the drawer's own
   history entry rather than sitting after it.
3. Closing the drawer without going anywhere leaves the history where it was.
4. Closing a layer leaves the page underneath alone — neither rebuilt, nor
   scrolled back to its top. This one was never reported: a mutation found it
   while proving the rule bites, and it is the same root cause seen from the
   other side. A bottom panel opened halfway down a list sent the list home.
5. Every entry is legible, the current one included, measured as PAINTED:
   the label's colour against the colours composited behind it.
"""
import asyncio

from common import Journal, open_page
from playwright.async_api import async_playwright

# WCAG AA for body text. The current entry sat at 1.00 — the floor exists so a
# number that low can never again be reported as a colour choice.
PLANCHER_CONTRASTE = 4.5

OU = """() => ({
  page: state.page,
  tiroir: document.querySelector('#drawer').classList.contains('open'),
  scrim: document.querySelector('#scrim').classList.contains('open'),
  couche: history.state && history.state.layer ? history.state.layer : null,
  nav: history.state && history.state.tm === 'nav' ? history.state.page : null,
})"""

# Colours are converted through a canvas, never parsed. `getComputedStyle`
# returns the colour space the author wrote — `oklch()` here — and three
# numbers pulled out of that string with a regex built for `rgb()` mean
# nothing. Drawing over white and again over black also recovers the alpha of
# a tint, which is what compositing a translucent surface needs.
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
  return [...document.querySelectorAll('#drawer a[data-navgo]')].map((a) => {
    const s = getComputedStyle(a);
    const propre = rgba(s.backgroundColor);
    let fond = derriere(a);
    if (propre.a > 0.001) {
      fond = fond.map((v, k) => propre.rgb[k] * propre.a + v * (1 - propre.a));
    }
    const texte = rgba(s.color).rgb;
    const [l1, l2] = [lum(texte), lum(fond)].sort((x, y) => y - x);
    return {
      id: a.dataset.navgo,
      courant: a.hasAttribute('aria-current'),
      contraste: Math.round(((l1 + 0.05) / (l2 + 0.05)) * 100) / 100,
    };
  });
}"""

# The ids the interface can actually render. An entry naming anything else is
# a dead end however carefully it is drawn.
PAGES = "() => window.__pages ? window.__pages() : null"


async def etat(pg):
    """What the interface shows and what its history holds."""
    return await pg.evaluate(OU)


async def ouvrirTiroir(pg):
    """Opens the drawer through its handle, the only way in."""
    await pg.tap("[data-drawer]")
    await pg.wait_for_timeout(320)


async def fermerParLeScrim(pg, x=370, y=700):
    """Closes a layer by tapping outside it, which is where a thumb goes.

    The scrim is tapped by COORDINATE: it lies under the panel, so a selector
    tap resolves to the element and then waits forever for the panel to stop
    intercepting it. Which coordinate is free depends on the layer — the drawer
    is anchored left and full height, a bottom panel is anchored to the bottom
    edge — and a point that lands ON the layer taps its content instead. That
    mistake reads as the rule failing, which is the worst kind of green.
    """
    await pg.touchscreen.tap(x, y)
    await pg.wait_for_timeout(320)


async def main():
    journal = Journal("R65 — le tiroir est un passage, pas une route")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")

        # ── 1. Every entry names a page that exists, and reaching it arrives ──
        ctx, pg = await open_page(b)
        await ouvrirTiroir(pg)
        entrees = await pg.eval_on_selector_all(
            "#drawer a[data-navgo]", "els => els.map((e) => e.dataset.navgo)")
        pages = await pg.evaluate(PAGES)
        journal.check("le tiroir porte des entrées", len(entrees) > 0,
                         f"{len(entrees)} entrées : {', '.join(entrees)}")
        if pages is not None:
            inconnues = [e for e in entrees if e not in pages]
            journal.check("chaque entrée nomme une page qui existe", not inconnues,
                             f"pages : {', '.join(pages)}"
                             + (f" — inconnues : {', '.join(inconnues)}" if inconnues else ""))
        await ctx.close()

        for cible in entrees:
            ctx, pg = await open_page(b)
            depart = (await etat(pg))["page"]
            await ouvrirTiroir(pg)
            await pg.tap(f'#drawer a[data-navgo="{cible}"]')
            # Long enough for an asynchronous pop to land: the defect showed a
            # correct frame first and was undone a tick later, so measuring
            # early would have certified it.
            await pg.wait_for_timeout(600)
            apres = await etat(pg)
            journal.check(
                f"« {cible} » arrive et y reste",
                apres["page"] == cible and not apres["tiroir"],
                f"page={apres['page']} tiroir={apres['tiroir']} (départ {depart})")

            # ── 2. The drawer leaves nothing behind ──
            if cible != depart:
                await pg.go_back()
                await pg.wait_for_timeout(500)
                retour = await etat(pg)
                journal.check(
                    f"depuis « {cible} », retour ramène au départ",
                    retour["page"] == depart and not retour["tiroir"],
                    f"page={retour['page']} tiroir={retour['tiroir']}")
            await ctx.close()

        # ── 3. Closing without going anywhere leaves history where it was ──
        ctx, pg = await open_page(b)
        avant = await etat(pg)
        await ouvrirTiroir(pg)
        ouvert = await etat(pg)
        journal.check("ouvrir le tiroir empile une couche, pas une page",
                         ouvert["tiroir"] and ouvert["couche"] == "drawer",
                         f"couche={ouvert['couche']}")
        await fermerParLeScrim(pg)
        ferme = await etat(pg)
        journal.check("refermer sans aller nulle part rend l'historique intact",
                         not ferme["tiroir"] and ferme["nav"] == avant["nav"]
                         and ferme["couche"] is None,
                         f"nav={ferme['nav']} couche={ferme['couche']}")

        # And back from there is the back of the page, not of the drawer: it
        # must not have to walk through an entry the drawer left behind.
        await pg.go_back()
        await pg.wait_for_timeout(500)
        apres_retour = await etat(pg)
        journal.check("après l'avoir refermé, retour ne rouvre pas le tiroir",
                         not apres_retour["tiroir"],
                         f"tiroir={apres_retour['tiroir']} page={apres_retour['page']}")
        await ctx.close()

        # ── 4. Closing a layer leaves the page underneath alone ──
        # The drawer is one of three layers that push an entry and pop it back.
        # When that pop is read as a navigation, the page underneath is rebuilt
        # from the entry describing where one already is — so a bottom panel
        # opened halfway down a list sent the list back to its top on closing.
        # Nobody reported it; a mutation found it. It is checked on the panel
        # rather than the drawer because a list is what one scrolls.
        for nom, ouvrirCouche, dehors in (
            # A bottom panel leaves the top of the frame free; the drawer leaves
            # its right.
            ("le panneau", lambda pg: pg.tap("#view .card [data-panel]"), (195, 60)),
            ("le tiroir", ouvrirTiroir, (370, 700)),
        ):
            ctx, pg = await open_page(b)
            await ouvrirCouche(pg)
            await pg.wait_for_timeout(450)
            await pg.evaluate("""() => {
              const marque = document.createElement('i');
              marque.id = 'marqueur-r65';
              document.querySelector('#view').appendChild(marque);
              document.querySelector('#port').scrollTop = 300;
            }""")
            await pg.wait_for_timeout(150)
            avant_scroll = await pg.evaluate(
                "() => Math.round(document.querySelector('#port').scrollTop)")
            await fermerParLeScrim(pg, *dehors)
            apres = await pg.evaluate("""() => ({
              marqueur: !!document.querySelector('#marqueur-r65'),
              scroll: Math.round(document.querySelector('#port').scrollTop),
            })""")
            journal.check(
                f"refermer {nom} ne reconstruit pas la page dessous",
                apres["marqueur"], f"marqueur présent={apres['marqueur']}")
            journal.check(
                f"refermer {nom} ne perd pas où la page était défilée",
                apres["scroll"] == avant_scroll,
                f"{avant_scroll} → {apres['scroll']}")
            await ctx.close()

        # ── 5. Every entry is legible, the current one included ──
        ctx, pg = await open_page(b)
        await ouvrirTiroir(pg)
        for ligne in await pg.evaluate(CONTRASTE):
            journal.check(
                f"« {ligne['id']} »"
                + (" (l'entrée courante)" if ligne["courant"] else "")
                + " se lit sur son fond",
                ligne["contraste"] >= PLANCHER_CONTRASTE,
                f"contraste {ligne['contraste']} (plancher {PLANCHER_CONTRASTE})")
        await ctx.close()

        await b.close()

    journal.summary()


asyncio.run(main())

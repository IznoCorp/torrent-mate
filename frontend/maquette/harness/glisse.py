"""R64 — a row's quick actions, in both directions, on both engines.

A card body opens the bottom panel on a tap, and the same card answers a
horizontal drag. Two gestures on one object is exactly where a scope conflict
lives: a drag that also fires the tap opens a panel over the drawer it just
revealed, and a tap read as a drag moves a row nobody meant to move.

Three things this holds to, each of which was broken:

  · the drag runs BOTH ways — the right drawer holds what one does TO a medium,
    the left holds the one thing the row is FOR — and only ONE row is open at a
    time, because two open drawers ask which one an action belongs to and the
    answer is never on screen;
  · a drag never fires the tap, and an action inside the drawer always does —
    swallowing every click after a drag would kill the buttons the gesture
    exists to reach;
  · it renders identically on Chromium AND WebKit. The drawer used an automatic
    margin and WebKit sized it without honouring its children's flex-basis:
    148px for two 84px buttons, so they spilled twenty pixels past the rounded
    card. Measured on one engine, that defect is invisible.

Driven with `Input.dispatchTouchEvent` on Chromium — a synthetic event is never
cancelled and cannot tell whether a gesture survives the compositor. WebKit has
no such endpoint here, so the geometry is what is compared there, which is
exactly what was wrong on it.
"""
import asyncio

from commun import Journal, ouvrir
from playwright.async_api import async_playwright


_journal = None


def verifier(nom, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.verifier(nom, condition, detail)


GEOMETRIE = """() => {
  const sw = document.querySelector('#view .swipe');
  if (!sw) return null;
  const rs = sw.getBoundingClientRect();
  const cote = (s) => {
    const e = sw.querySelector(s);
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return {l: Math.round(r.width * 10) / 10,
            actions: e.querySelectorAll('.act').length};
  };
  return {
    droite: cote('.side.right'), gauche: cote('.side.left'),
    // What spills past the row is what a rounded card cannot hide.
    debords: [...sw.querySelectorAll('.act')].map(x => {
      const r = x.getBoundingClientRect();
      return Math.round(Math.max(rs.left - r.left, r.right - rs.right) * 10) / 10;}),
  };
}"""


async def surLaListe(p, lance):
    """Opens the prototype past the startup screen, on the follows list."""
    b = await lance()
    ctx, pg = await ouvrir(b)
    await pg.wait_for_timeout(450)
    await pg.evaluate("()=>window.__go('acq-suivis-liste')")
    await pg.wait_for_timeout(550)
    return b, ctx, pg


async def main():
    global _journal
    _journal = Journal(f"R64 — le glissé d'une ligne")

    async with async_playwright() as p:
        # ── the geometry, on both engines ──────────────────────────────────
        mesures = {}
        for nom, lance in (("Chromium", lambda: p.chromium.launch(channel="chrome")),
                           ("WebKit", lambda: p.webkit.launch())):
            b, _, pg = await surLaListe(p, lance)
            mesures[nom] = await pg.evaluate(GEOMETRIE)
            await b.close()

        for nom, m in mesures.items():
            verifier(f"{nom} : la ligne a un tiroir de chaque côté",
                     m and m["droite"] and m["gauche"], str(m))
            if m and m["droite"]:
                verifier(f"{nom} : le tiroir droit mesure ses boutons",
                         abs(m["droite"]["l"] - m["droite"]["actions"] * 84) < 1,
                         f"{m['droite']['l']} pour {m['droite']['actions']} action(s)")
                verifier(f"{nom} : aucune action ne déborde de la ligne",
                         max(m["debords"]) <= 0.5, str(m["debords"]))

        chrome, webkit = mesures.get("Chromium"), mesures.get("WebKit")
        verifier("les deux moteurs dessinent le même tiroir",
                 chrome and webkit
                 and abs(chrome["droite"]["l"] - webkit["droite"]["l"]) < 1,
                 f"{chrome and chrome['droite']} vs {webkit and webkit['droite']}")

        # ── the behaviour, under a real finger ─────────────────────────────
        b, ctx, pg = await surLaListe(p, lambda: p.chromium.launch(channel="chrome"))
        cdp = await ctx.new_cdp_session(pg)
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))

        async def glisser(x, y, dx, pas=14):
            """Drags one finger horizontally, in steps a thumb really makes."""
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
            n = max(1, abs(int(dx)) // pas)
            for i in range(1, n + 1):
                await cdp.send("Input.dispatchTouchEvent",
                               {"type": "touchMove",
                                "touchPoints": [{"x": x + dx * i / n, "y": y, "id": 1}]})
                await asyncio.sleep(0.016)
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})
            await pg.wait_for_timeout(430)

        lignes = await pg.evaluate(
            """()=>[...document.querySelectorAll('#view .swipe')].slice(0, 2).map(s => {
                 const r = s.getBoundingClientRect();
                 return {x: r.x + r.width * 0.6, y: r.y + r.height / 2};})""")
        verifier("deux lignes au moins sont dessinées", len(lignes) >= 2, str(len(lignes)))

        async def poses():
            return await pg.evaluate(
                """()=>[...document.querySelectorAll('#view .swipe .card')].slice(0, 2)
                     .map(c => c.style.transform || '')""")

        await glisser(lignes[0]["x"], lignes[0]["y"], -140)
        p0 = await poses()
        verifier("un glissé vers la gauche ouvre le tiroir droit",
                 p0[0].startswith("translateX(-"), str(p0))
        verifier("et il n'ouvre PAS le panneau du bas",
                 not await pg.evaluate(
                     "()=>document.querySelector('#sheet').classList.contains('open')"))

        await glisser(lignes[1]["x"], lignes[1]["y"], -140)
        p1 = await poses()
        verifier("glisser une autre ligne remet la première en place",
                 p1[0] == "" and p1[1].startswith("translateX(-"), str(p1))

        await glisser(lignes[0]["x"], lignes[0]["y"], 140)
        p2 = await poses()
        verifier("un glissé vers la droite ouvre le tiroir gauche",
                 p2[0].startswith("translateX(") and "-" not in p2[0], str(p2))

        # A tap must still reach the panel: swallowing every click after a drag
        # would make the row unusable in the other direction. Tapped for REAL —
        # a programmatic click carries no pointerdown, so it never clears the
        # mark the previous drag left, and the probe would measure its own
        # shortcut rather than the interface.
        await pg.evaluate("()=>{document.querySelectorAll('#view .swipe .card')"
                          ".forEach(c => c.style.transform = '');}")
        await pg.wait_for_timeout(250)
        corps = await pg.evaluate(
            """()=>{const b = document.querySelector('#view .swipe .cbody');
                   const r = b.getBoundingClientRect();
                   return {x: r.x + r.width / 2, y: r.y + 12};}""")
        await cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchStart",
                        "touchPoints": [{"x": corps["x"], "y": corps["y"], "id": 1}]})
        await pg.wait_for_timeout(70)
        await cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
        await pg.wait_for_timeout(450)
        verifier("un simple tap ouvre toujours le panneau",
                 await pg.evaluate(
                     "()=>document.querySelector('#sheet').classList.contains('open')"))
        await pg.evaluate("()=>closeSheet()")
        await pg.wait_for_timeout(300)

        # And an action inside the drawer answers, which the click-swallowing
        # would otherwise have killed along with the tap. The row is measured
        # AGAIN: opening the panel re-renders the list, and a point read before
        # that lands on whatever replaced it.
        await pg.evaluate("()=>window.__go('acq-suivis-liste')")
        await pg.wait_for_timeout(550)
        lignes = await pg.evaluate(
            """()=>[...document.querySelectorAll('#view .swipe')].slice(0, 1).map(s => {
                 const r = s.getBoundingClientRect();
                 return {x: r.x + r.width * 0.6, y: r.y + r.height / 2};})""")
        verifier("la liste est de nouveau à l'écran", len(lignes) == 1, str(len(lignes)))
        await glisser(lignes[0]["x"], lignes[0]["y"], -140)
        atteignable = await pg.evaluate("""()=>{
          const a = document.querySelector('#view .swipe .side.right .act');
          if (!a) return null;
          const r = a.getBoundingClientRect();
          const dessus = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
          return !!(dessus && dessus.closest('.act'));}""")
        verifier("le bouton révélé est réellement sous le doigt",
                 atteignable is True, str(atteignable))

        # The scoping is proven with a MOUSE. After a touch drag the browser
        # suppresses the click itself, so a touch probe cannot tell a swallowed
        # click from a click that never happened — and a rule that cannot fail
        # proves nothing. A mouse drag really does fire one, in the same place,
        # which is exactly the case the swallowing exists for.
        await pg.evaluate("()=>window.__go('acq-suivis-liste')")
        await pg.wait_for_timeout(520)
        corps = await pg.evaluate(
            """()=>{const b = document.querySelector('#view .swipe .cbody');
                   const r = b.getBoundingClientRect();
                   return {x: r.x + r.width / 2, y: r.y + 14};}""")
        await pg.mouse.move(corps["x"], corps["y"])
        await pg.mouse.down()
        for i in range(1, 11):
            await pg.mouse.move(corps["x"] - 14 * i, corps["y"])
            await asyncio.sleep(0.016)
        await pg.mouse.up()
        await pg.wait_for_timeout(450)
        verifier("à la souris non plus, un glissé n'ouvre pas le panneau",
                 not await pg.evaluate(
                     "()=>document.querySelector('#sheet').classList.contains('open')"))
        verifier("et il a bien ouvert le tiroir",
                 (await poses())[0].startswith("translateX(-"), str(await poses()))

        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await b.close()

    _journal.bilan()

asyncio.run(main())

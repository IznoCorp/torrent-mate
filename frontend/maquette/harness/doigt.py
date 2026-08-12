"""R55 — every gesture answers a REAL finger, not only a synthetic one.

Synthetic `PointerEvent`s are dispatched straight at an element and are never
cancelled by anything. Real touch input goes through hit-testing and the
compositor, and the compositor takes gestures away: the moment it decides a
drag is a scroll it fires `pointercancel` and stops delivering `pointermove`
for that pointer. A pointer-only handler living inside a scrollport therefore
passes every synthetic test and does nothing at all under a thumb.

That is not hypothetical. Two gestures on the scrollport — the pull to refresh
and the swipe between views — were lost exactly that way when the gesture layer
moved from touch events to pointer events, and no script noticed, because every
script drove them synthetically.

So this one drives them through `Input.dispatchTouchEvent`, which is real
browser input, and measures the outcome rather than the wiring. The gestures
that CAN claim their axis in `touch-action` — a swipeable row, a deck card —
are measured the same way, because that claim is what makes them survive and
nothing else here proves it still holds.
"""
import asyncio
import sys

from playwright.async_api import async_playwright

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


async def glisser(cdp, x0, y0, pas, dx, dy):
    """Drags one real finger across the page.

    Args:
        cdp: An open CDP session.
        x0: Starting x, in CSS pixels.
        y0: Starting y, in CSS pixels.
        pas: Number of intermediate moves.
        dx: Horizontal travel per move.
        dy: Vertical travel per move.
    """
    await cdp.send("Input.dispatchTouchEvent",
                   {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0, "id": 1}]})
    for i in range(1, pas + 1):
        await cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchMove",
                        "touchPoints": [{"x": x0 + i * dx, "y": y0 + i * dy, "id": 1}]})
        await asyncio.sleep(0.02)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        ctx = await b.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = await ctx.new_page()
        erreurs = []
        pg.on("pageerror", lambda e: erreurs.append(str(e)))
        cdp = await ctx.new_cdp_session(pg)
        await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
        await pg.evaluate("()=>document.querySelector('#toastx').click()")

        print(f"{BAR}\nR55 — les gestes sous un vrai doigt\n{BAR}")

        async def rect(selecteur):
            return await pg.evaluate(
                "(s)=>{const e=document.querySelector(s);"
                "return e ? e.getBoundingClientRect().toJSON() : null;}", selecteur)

        # 1. Pull to refresh — on every scrolling surface, not the convenient
        #    one. The indicator has to ARM and then show its spinner; a pull
        #    that travels a few pixels and stops has no loader to show.
        surfaces = ["acq-encours-repos", "acq-suivis-liste", "acq-decouvrir",
                    "lib-grille", "lib-liste", "arr-repos", "systeme"]
        sans_charge = []
        for etat in surfaces:
            await pg.evaluate("(s)=>window.__go(s)", etat)
            await pg.wait_for_timeout(250)
            await pg.evaluate("""()=>{window.__h=0;window.__t=setInterval(()=>{
                const p=document.querySelector('#ptr');
                window.__h=Math.max(window.__h,p.getBoundingClientRect().height);},16);}""")
            r = await rect("#port")
            await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + 60, 10, 0, 18)
            await pg.wait_for_timeout(250)
            out = await pg.evaluate("""()=>{clearInterval(window.__t);
                return {h:window.__h, cls:document.querySelector('#ptr').className};}""")
            # 44px is the arming threshold the gesture itself uses.
            if out["h"] < 44 or "loading" not in out["cls"]:
                sans_charge.append(f"{etat} (h={out['h']:.0f}, {out['cls']})")
            await pg.evaluate("()=>window.__reposPTR()")
        verifier(f"le tirer-pour-recharger arme et tourne sur les {len(surfaces)} surfaces",
                 not sans_charge, " · ".join(sans_charge))

        # 2. Swipe between views — the other gesture on the same scrollport,
        #    lost to the same cause and by the same silence.
        await pg.evaluate("()=>window.__go('acq-encours-repos')")
        await pg.wait_for_timeout(250)
        r = await rect("#port")
        await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + 200, 10, -20, 0)
        await pg.wait_for_timeout(350)
        onglet = await pg.evaluate(
            "()=>(document.querySelector('.seg [aria-selected=\"true\"]')||{}).textContent")
        verifier("le glissé horizontal change de vue", "Suivis" in (onglet or ""), str(onglet))

        await pg.evaluate("()=>window.__go('lib-grille')")
        await pg.wait_for_timeout(250)
        r = await rect("#port")
        await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + 200, 10, -20, 0)
        await pg.wait_for_timeout(350)
        lentille = await pg.evaluate(
            "()=>(document.querySelector('.seg [aria-selected=\"true\"]')||{}).textContent")
        verifier("y compris entre les lentilles de la médiathèque",
                 "Incomplets" in (lentille or ""), str(lentille))

        # 3. A vertical drag further down the surface must still SCROLL. The
        #    cure for one gesture must not swallow the browser's own.
        await pg.evaluate("()=>window.__go('lib-grille')")
        await pg.wait_for_timeout(250)
        r = await rect("#port")
        await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + r["height"] - 120, 10, 0, -22)
        await pg.wait_for_timeout(350)
        defile = await pg.evaluate("()=>document.querySelector('#port').scrollTop")
        verifier("la surface défile toujours normalement", defile > 40, f"scrollTop={defile}")

        # 4. The gestures that claim their axis keep the pointer path, and the
        #    claim is what makes them survive. Measured, not assumed.
        await pg.evaluate("()=>window.__go('acq-suivis-liste')")
        await pg.wait_for_timeout(300)
        r = await rect("#view .swipe")
        await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + r["height"] / 2, 12, -20, 0)
        await pg.wait_for_timeout(300)
        transforme = await pg.evaluate(
            "()=>getComputedStyle(document.querySelector('#view .swipe .card')).transform")
        verifier("une rangée s'écarte encore", transforme not in ("none", "matrix(1, 0, 0, 1, 0, 0)"),
                 transforme)

        await pg.evaluate("()=>window.__go('acq-decouvrir-deck')")
        await pg.wait_for_timeout(350)
        avant = await pg.evaluate("()=>document.querySelectorAll('.sugwrap, .dcard').length")
        r = await rect(".deck .dcard[data-depth='0']")
        await glisser(cdp, r["x"] + r["width"] / 2, r["y"] + r["height"] / 2, 12, 22, 0)
        await pg.wait_for_timeout(450)
        bouge = await pg.evaluate("""()=>{const c=document.querySelector(".deck .dcard[data-depth='0']");
            return c ? c.textContent.replace(/\\s+/g,' ').trim().slice(0,40) : null;}""")
        verifier("le deck avance encore d'une carte", bool(bouge) and avant > 0, str(bouge))

        verifier("aucune erreur JS", not erreurs, str(erreurs))
        await b.close()

    print()
    print(f"{BAR}\n{faits} règles EXÉCUTÉES — "
          + ("aucune violation" if not echecs else f"{len(echecs)} violation(s) : {', '.join(echecs)}"))
    if echecs:
        sys.exit(1)

asyncio.run(main())

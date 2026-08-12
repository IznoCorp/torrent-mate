"""Every gesture must work with a mouse, not only with a thumb.

The interface is used from a desktop browser too — including at a phone width —
and a gesture that only answers a finger is a gesture half the sessions cannot
reach.
"""
import asyncio
from playwright.async_api import async_playwright

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(channel="chrome")
    # No touch at all: a plain desktop browser, at a phone width.
    ctx = await b.new_context(viewport={"width":390,"height":844}, has_touch=False, is_mobile=False)
    pg = await ctx.new_page(); errs = []; echecs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__measure(true)")

    async def glisser(selecteur, dx):
        box = await pg.locator(selecteur).first.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        await pg.mouse.move(x, y)
        await pg.mouse.down()
        for i in range(1, 9):
            await pg.mouse.move(x + dx * i / 8, y)
            await pg.wait_for_timeout(16)
        await pg.mouse.up()
        await pg.wait_for_timeout(700)

    # 1. Slide cards — the case the operator reported.
    await pg.evaluate("()=>{window.__reset(); set({page:'acq',acqTab:'decouvrir',phase:'prete'}); S.sugMode='deck'; render();}")
    await pg.wait_for_timeout(600)
    t0 = await pg.evaluate("()=>document.querySelector('.dcard[data-depth=\"0\"] .t').textContent")
    await glisser('.dcard[data-depth="0"]', -180)
    t1 = await pg.evaluate("()=>document.querySelector('.dcard[data-depth=\"0\"] .t').textContent")
    print(f"slide cards, mouse left : « {t0[:24]} » → « {t1[:24]} »  {'OK' if t1 != t0 else 'FAIL'}")
    if not (t1 != t0): echecs.append("slide cards, mouse left")
    # Reset between gestures: chaining two drags without one measures the
    # second against the state the first left, which is not what is being asked.
    await pg.evaluate("()=>{window.__reset(); set({page:'acq',acqTab:'decouvrir',phase:'prete'}); S.sugMode='deck'; render();}")
    await pg.wait_for_timeout(600)
    await glisser('.dcard[data-depth="0"]', 180)
    n = await pg.evaluate("()=>S.sugGone.size")
    print(f"slide cards, mouse right: dismissed {n}  {'OK' if n == 1 else 'FAIL'}")
    if not (n == 1): echecs.append("slide cards, mouse right")

    # 2. Card swipe in Suivis.
    await pg.evaluate("()=>window.__go('acq-suivis-liste')"); await pg.wait_for_timeout(500)
    await glisser(".swipe", -150)
    tr = await pg.evaluate("()=>{const c=document.querySelector('.swipe .card'); return getComputedStyle(c).transform;}")
    print(f"follow row, mouse swipe : {tr[:34]}  {'OK' if tr != 'none' else 'FAIL'}")
    if not (tr != 'none'): echecs.append("follow row, mouse swipe")

    # 3. Suggestion card swipe in the list format.
    await pg.evaluate("()=>{window.__reset(); set({page:'acq',acqTab:'decouvrir',phase:'prete'}); S.sugMode='list'; render();}")
    await pg.wait_for_timeout(600)
    avant = await pg.evaluate("()=>document.querySelectorAll('.sugwrap').length")
    await glisser(".sugwrap", 200)
    apres = await pg.evaluate("()=>document.querySelectorAll('.sugwrap').length")
    print(f"suggestion, mouse swipe : {avant} → {apres}  {'OK' if apres < avant else 'FAIL'}")
    if not (apres < avant): echecs.append("suggestion, mouse swipe")

    print("\nJS errors:", errs or "none")
    await b.close()

    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if echecs or errs: raise SystemExit(1)
asyncio.run(main())

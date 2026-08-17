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
    pg = await ctx.new_page(); errs = []; failures = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>window.__measure(true)")

    async def drag(selector, dx):
        box = await pg.locator(selector).first.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        await pg.mouse.move(x, y)
        await pg.mouse.down()
        for i in range(1, 9):
            await pg.mouse.move(x + dx * i / 8, y)
            await pg.wait_for_timeout(16)
        await pg.mouse.up()
        await pg.wait_for_timeout(700)

    # 1. Slide cards — the case the operator reported.
    await pg.evaluate("()=>{window.__reset(); applyState({page:'acq',acqTab:'decouvrir',phase:'prete'}); window.__magasin.ecrire({sugMode: 'deck'}); render();}")
    await pg.wait_for_timeout(600)
    t0 = await pg.evaluate("()=>document.querySelector('.dcard[data-depth=\"0\"] .t').textContent")
    await drag('.dcard[data-depth="0"]', -180)
    t1 = await pg.evaluate("()=>document.querySelector('.dcard[data-depth=\"0\"] .t').textContent")
    print(f"slide cards, mouse left : « {t0[:24]} » → « {t1[:24]} »  {'PASS' if t1 != t0 else 'FAIL'}")
    if not (t1 != t0): failures.append("slide cards, mouse left")
    # Reset between gestures: chaining two drags without one measures the
    # second against the state the first left, which is not what is being asked.
    await pg.evaluate("()=>{window.__reset(); applyState({page:'acq',acqTab:'decouvrir',phase:'prete'}); window.__magasin.ecrire({sugMode: 'deck'}); render();}")
    await pg.wait_for_timeout(600)
    await drag('.dcard[data-depth="0"]', 180)
    n = await pg.evaluate("()=>state.sugGone.size")
    print(f"slide cards, mouse right: dismissed {n}  {'PASS' if n == 1 else 'FAIL'}")
    if not (n == 1): failures.append("slide cards, mouse right")

    # 2. Card swipe in Suivis.
    await pg.evaluate("()=>window.__go('acq-suivis-liste')"); await pg.wait_for_timeout(500)
    await drag(".swipe", -150)
    tr = await pg.evaluate("()=>{const c=document.querySelector('.swipe .card'); return getComputedStyle(c).transform;}")
    print(f"follow row, mouse swipe : {tr[:34]}  {'PASS' if tr != 'none' else 'FAIL'}")
    if not (tr != 'none'): failures.append("follow row, mouse swipe")

    # 3. Suggestion card swipe in the list format.
    await pg.evaluate("()=>{window.__reset(); applyState({page:'acq',acqTab:'decouvrir',phase:'prete'}); window.__magasin.ecrire({sugMode: 'list'}); render();}")
    await pg.wait_for_timeout(600)
    before = await pg.evaluate("()=>document.querySelectorAll('.sugwrap').length")
    await drag(".sugwrap", 200)
    after = await pg.evaluate("()=>document.querySelectorAll('.sugwrap').length")
    print(f"suggestion, mouse swipe : {before} → {after}  {'PASS' if after < before else 'FAIL'}")
    if not (after < before): failures.append("suggestion, mouse swipe")

    # 4. A drag NEVER fires the tap, and the claim is that the click was
    #    actively SWALLOWED — not that no panel appeared. A panel that fails to
    #    appear can be an accident of where the release landed, and asserting
    #    the weaker thing is what let this hole live: a drag that moves the row
    #    zero pixels armed nothing, so the click went through and the bottom
    #    panel opened over the row.
    #
    #    Only a mouse can see it. After a touch drag the browser suppresses the
    #    click by itself, so every finger measurement was green over the hole.
    #
    #    Both lists are walked, because they differ where it matters: a follows
    #    row has a drawer on each side, a library row has none on the left — and
    #    a row with no drawer on the side being dragged towards REFUSES to move,
    #    which is exactly the case that armed nothing.
    await pg.evaluate("""()=>{window.__clicks = [];
      document.addEventListener('click',
        (e) => window.__clicks.push({swallowed: e.defaultPrevented}), true);}""")
    for state_, list_label in (("acq-suivis-liste", "a follow row"),
                         ("lib-liste", "a library row")):
        for direction, dx in (("right", 150), ("left", -150)):
            await pg.evaluate(f"()=>window.__go({state_!r})")
            await pg.wait_for_timeout(480)
            if not await pg.evaluate("()=>document.querySelectorAll('#view .swipe').length"):
                continue
            await pg.evaluate("()=>{window.__clicks = [];}")
            await drag("#view .swipe", dx)
            clicks = await pg.evaluate("()=>window.__clicks")
            passed = bool(clicks) and all(c["swallowed"] for c in clicks)
            position = await pg.evaluate(
                "()=>(document.querySelector('#view .swipe .card')||{}).style?.transform || 'at rest'")
            print(f"{list_label}, drag {direction:<7}: click swallowed {passed} · position {position}"
                  f"  {'PASS' if passed else 'FAIL'}")
            if not passed:
                failures.append(f"{list_label}, drag {direction}: the click is not swallowed ({clicks})")

    print("\nJS errors:", errs or "none")
    if failures:
        print("failures:", failures)
    await b.close()

    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if failures or errs: raise SystemExit(1)
asyncio.run(main())

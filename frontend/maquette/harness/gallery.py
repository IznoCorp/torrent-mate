"""One pattern for every poster gallery: tap opens the media sheet, long press
opens the bottom panel.

A gallery that answers a tap differently from its neighbours teaches two
vocabularies for the same picture.
"""
import asyncio

from playwright.async_api import async_playwright

GALLERIES = [
  ("Médiathèque · Médias",    "lib-grid",                '[data-part="tile"][data-panel]'),
  ("Médiathèque · Incomplets","lib-incomplete",            None),
  ("Médiathèque · Récents",   "lib-recent",               None),
  ("Suivis · grille",         "acq-follows-grid",         '[data-part="tile"][data-panel]'),
  ("Découvrir · affiches",    "acq-discover-posters",    '[data-part="tile"][data-panel]'),
]

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(channel="chrome")
    failures = []
    for touch in (True, False):
      ctx = await b.new_context(viewport={"width":390,"height":844},
                                device_scale_factor=2, is_mobile=touch, has_touch=touch)
      pg = await ctx.new_page(); errs = []
      pg.on("pageerror", lambda e: errs.append(str(e)))
      await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
      # The startup screen covers the frame for as long as the load it stands
      # for lasts. Nothing is being fetched here, so the harness closes that
      # wait through the same seam the app uses, rather than sleeping it out.
      await pg.evaluate("()=>window.__loadingDone?.()")
      await pg.evaluate("()=>window.__measure(true)")
      print(f"\n── {'finger' if touch else 'mouse'} ──")
      for name, state_, sel in GALLERIES:
        await pg.evaluate("(i)=>window.__go(i)", state_)
        await pg.wait_for_timeout(400)
        # The lens galleries need their grid layout switched on.
        if sel is None:
            # `data-vsw` and `data-libmode` NEVER EXISTED. The real attribute is
            # `data-lmode` (pages/library.tsx), so this click had been a no-op
            # since it was written — swallowed by its own `if(v)` guard, which
            # is why nothing ever said so. A control the harness cannot find is
            # now a failure: a guarded click that silently does nothing is how a
            # rule keeps passing while it stops driving the thing it measures.
            switched = await pg.evaluate(
                "()=>{const v=document.querySelector('[data-lmode=\"grid\"]');"
                " if(!v) return false; v.click(); return true;}")
            if not switched:
                failures.append(f"{name}: no [data-lmode=\"grid\"] control to switch layout")
                print(f"  {name:26} NO GRID CONTROL")
                continue
            await pg.wait_for_timeout(300)
            sel = '[data-part="tile"][data-panel]'
        n = await pg.locator(sel).count()
        if n == 0:
            failures.append(f"{name}: no tile declares a panel"); print(f"  {name:26} NO PANEL DECLARED"); continue

        # 1. A tap opens the media sheet. The sheet left `#screen` for a real
        # route (`/mediasheet/$title`, rendered inside `#coquille`), so it is read by
        # the identity it carries — `data-key="mediaSheet:…"` — and not by a bare
        # `[data-part="screen"][data-open]`, which cannot tell two stacked screens apart.
        await pg.locator(sel).first.click()
        await pg.wait_for_timeout(500)
        screen_ = await pg.evaluate(
            """()=>!!document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]')""")
        await pg.evaluate("()=>window.__go(arguments0)" if False else "(i)=>window.__go(i)", state_)
        await pg.wait_for_timeout(350)
        if sel == '[data-part="tile"][data-panel]' and not screen_:
            pass  # the lens galleries may need the mode click again; re-checked below

        # 2. A long press opens the bottom panel.
        if await pg.locator(sel).count() == 0:
            # Same dead pair as above, same real attribute.
            await pg.evaluate(
                "()=>{const v=document.querySelector('[data-lmode=\"grid\"]');"
                " if(v) v.click();}")
            await pg.wait_for_timeout(300)
        box = await pg.locator(sel).first.bounding_box()
        await pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await pg.mouse.down(); await pg.wait_for_timeout(640); await pg.mouse.up()
        await pg.wait_for_timeout(400)
        sheet = await pg.evaluate("()=>document.querySelector('#sheet').hasAttribute('data-open')")
        verdict = "PASS" if screen_ and sheet else "FAIL"
        if verdict == "FAIL":
            failures.append(f"{name}: tap→sheet {screen_}, long→panel {sheet}")
        print(f"  {name:26} tap→mediaSheet {str(screen_):5} · long→panel {str(sheet):5}  {verdict}")
        await pg.evaluate("()=>window.__reset()")
      if errs: failures.append(f"JS errors: {errs}")
      await ctx.close()

    # Every library lens offers the SAME two layouts. A lens that draws only
    # one teaches that its content is a different kind of thing, and it is not.
    ctx = await b.new_context(viewport={"width":390,"height":844},
                              device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__measure(true)")
    print()
    for lens in ("cat", "inc", "rec"):
        shapes = {}
        for mode in ("grid", "list"):
            await pg.evaluate("([l,m])=>{window.__reset(); applyState({page:'lib',libLens:l,libMode:m,phase:'ready'}); render();}", [lens, mode])
            await pg.wait_for_timeout(420)
            shapes[mode] = await pg.evaluate("""()=>({
                tiles:document.querySelectorAll('#view [data-part="tile"][data-panel]').length,
                cards:document.querySelectorAll('#view [data-part="card"]').length,
                toggle:!!document.querySelector('#view .vsw')})""")
        ok = (shapes["grid"]["tiles"] > 0 and shapes["list"]["cards"] > 0
              and shapes["grid"]["toggle"] and shapes["list"]["toggle"])
        print(f"  library lens « {lens} »        both layouts: {'OK' if ok else 'FAIL'}  {shapes}")
        if not ok:
            failures.append(f"lens {lens} does not offer both layouts: {shapes}")
    await ctx.close()

    print("\nVERDICT:", "one pattern in every gallery" if not failures else f"FAILED - {failures}")
    await b.close()
    if failures: raise SystemExit(1)

asyncio.run(main())

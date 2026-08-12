"""One pattern for every poster gallery: tap opens the media sheet, long press
opens the bottom panel.

A gallery that answers a tap differently from its neighbours teaches two
vocabularies for the same picture.
"""
import asyncio
from playwright.async_api import async_playwright

GALERIES = [
  ("Médiathèque · Médias",    "lib-grille",                ".tile[data-panel]"),
  # « Incomplets » is deliberately NOT a poster gallery: what one comes to read
  # there is a fraction, and a poster hides it. The pattern applies to galleries,
  # and this lens is a card list — asserted below so the exemption is a decision.
  ("Médiathèque · Récents",   "lib-recents",               None),
  ("Suivis · grille",         "acq-suivis-grille",         ".tile[data-panel]"),
  ("Découvrir · affiches",    "acq-decouvrir-affiches",    ".sugtile[data-panel]"),
]

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(channel="chrome")
    echecs = []
    for tactile in (True, False):
      ctx = await b.new_context(viewport={"width":390,"height":844},
                                device_scale_factor=2, is_mobile=tactile, has_touch=tactile)
      pg = await ctx.new_page(); errs = []
      pg.on("pageerror", lambda e: errs.append(str(e)))
      await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
      await pg.evaluate("()=>window.__measure(true)")
      print(f"\n── {'finger' if tactile else 'mouse'} ──")
      for nom, etat, sel in GALERIES:
        await pg.evaluate("(i)=>window.__go(i)", etat)
        await pg.wait_for_timeout(400)
        # The lens galleries need their grid layout switched on.
        if sel is None:
            await pg.evaluate("()=>{const v=document.querySelector('[data-vsw=\"grid\"],[data-libmode=\"grid\"]'); if(v) v.click();}")
            await pg.wait_for_timeout(300)
            sel = ".tile[data-panel]"
        n = await pg.locator(sel).count()
        if n == 0:
            echecs.append(f"{nom}: no tile declares a panel"); print(f"  {nom:26} NO PANEL DECLARED"); continue

        # 1. A tap opens the media sheet.
        await pg.locator(sel).first.click()
        await pg.wait_for_timeout(500)
        ecran = await pg.evaluate("()=>document.querySelector('#screen').classList.contains('open')")
        await pg.evaluate("()=>window.__go(arguments0)" if False else "(i)=>window.__go(i)", etat)
        await pg.wait_for_timeout(350)
        if sel == ".tile[data-panel]" and not ecran:
            pass  # the lens galleries may need the mode click again; re-checked below

        # 2. A long press opens the bottom panel.
        if await pg.locator(sel).count() == 0:
            await pg.evaluate("()=>{const v=document.querySelector('[data-vsw=\"grid\"],[data-libmode=\"grid\"]'); if(v) v.click();}")
            await pg.wait_for_timeout(300)
        box = await pg.locator(sel).first.bounding_box()
        await pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        await pg.mouse.down(); await pg.wait_for_timeout(640); await pg.mouse.up()
        await pg.wait_for_timeout(400)
        feuille = await pg.evaluate("()=>document.querySelector('#sheet').classList.contains('open')")
        verdict = "OK" if ecran and feuille else "FAIL"
        if verdict == "FAIL":
            echecs.append(f"{nom}: tap→sheet {ecran}, long→panel {feuille}")
        print(f"  {nom:26} tap→fiche {str(ecran):5} · long→panel {str(feuille):5}  {verdict}")
        await pg.evaluate("()=>window.__reset()")
      if errs: echecs.append(f"JS errors: {errs}")
      await ctx.close()

    # The card lenses must NOT sprout a gallery by accident.
    ctx = await b.new_context(viewport={"width":390,"height":844},
                              device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = await ctx.new_page()
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__measure(true)")
    await pg.evaluate("()=>window.__go('lib-incomplets')")
    await pg.wait_for_timeout(450)
    forme = await pg.evaluate("""()=>({tuiles:document.querySelectorAll('#view .tile').length,
                                      cartes:document.querySelectorAll('#view .card').length})""")
    print(f"\n  Médiathèque · Incomplets   card list, not a gallery: {forme}")
    if forme["tuiles"] or not forme["cartes"]:
        echecs.append(f"the incomplete lens changed shape: {forme}")
    await ctx.close()

    print("\nVERDICT:", "one pattern in every gallery" if not echecs else f"FAILED - {echecs}")
    await b.close()
    if echecs: raise SystemExit(1)

asyncio.run(main())

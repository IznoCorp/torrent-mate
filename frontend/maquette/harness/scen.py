"""Sweeps the 8 views in BOTH data scenarios, through the __go driver.

A view that renders nothing FAILS the pass: that is the guard that was missing
the day a page went blank because a constant had disappeared.
"""
import asyncio
from playwright.async_api import async_playwright

VUES = [("acq/encours", "acq-encours-{s}"), ("acq/suivis", "acq-suivis-liste"),
        ("acq/decouvrir", "acq-decouvrir"), ("lib/medias", "lib-grille"),
        ("lib/incomplets", "lib-incomplets"), ("lib/recents", "lib-recents"),
        ("arrivees", "arr-{s}"), ("systeme", "systeme")]

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(channel="chrome")
    ctx = await b.new_context(viewport={"width": 390, "height": 844},
                              device_scale_factor=2, is_mobile=True, has_touch=True)
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__chargementTermine?.()")
    total_bad = 0
    for scen, mot in (("reel", "repos"), ("charge", "charge")):
        print(f"\n=== scenario {scen} ===")
        await pg.evaluate("(s)=>{state.scen=s;render();}", scen)
        for nom, sid in VUES:
            await pg.evaluate("(i)=>window.__go(i)", sid.format(s=mot))
            await pg.evaluate("(s)=>{state.scen=s;render();}", scen)
            await pg.wait_for_timeout(320)
            r = await pg.evaluate("""()=>{const v=document.querySelector('#view');
              return {txt:v.textContent.replace(/\\s+/g,' ').trim().length,
                      cartes:v.querySelectorAll('.card,.tile,.kv').length,
                      vide:!!v.querySelector('.empty'),
                      doc:document.documentElement.scrollWidth,
                      deb:[...v.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>390.5&&!e.closest('.pillscroll')&&!e.closest('.cast')).length};}""")
            ok = r['txt'] > 100 and r['doc'] <= 390 and r['deb'] == 0 and (r['cartes'] > 0 or r['vide'])
            if not ok: total_bad += 1
            print(("  OK  " if ok else "  FAIL"), f"{nom:16}", r)
            await pg.screenshot(path=f"z_{scen}_{nom.replace('/','_')}.png")
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "16/16 renders conform" if total_bad == 0 and not errs else f"{total_bad} failec(s)")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if total_bad or errs: raise SystemExit(1)
asyncio.run(main())

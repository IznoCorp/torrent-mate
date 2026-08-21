"""Sweeps the 8 views in BOTH data scenarios, through the __go driver.

A view that renders nothing FAILS the pass: that is the guard that was missing
the day a page went blank because a constant had disappeared.
"""
import asyncio
from playwright.async_api import async_playwright

# The state ids here are TEMPLATES — `acq-now-{s}` is completed at run time —
# so a rename that replaces whole quoted strings walks straight past them. Two
# rules broke on exactly that when the 51 French state ids moved.
VIEWS = [("acq/now", "acq-now-{s}"), ("acq/follows", "acq-follows-list"),
        ("acq/discover", "acq-discover"), ("lib/media", "lib-grid"),
        ("lib/incomplete", "lib-incomplete"), ("lib/recent", "lib-recent"),
        ("arrivals", "arr-{s}"), ("system", "system")]

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
    await pg.evaluate("()=>window.__loadingDone?.()")
    total_bad = 0
    for scen, word in (("real", "idle"), ("loaded", "loaded")):
        print(f"\n=== scenario {scen} ===")
        await pg.evaluate("(s)=>{window.__store.write({scen: s}); render();}", scen)
        for name, sid in VIEWS:
            await pg.evaluate("(i)=>window.__go(i)", sid.format(s=word))
            await pg.evaluate("(s)=>{window.__store.write({scen: s}); render();}", scen)
            await pg.wait_for_timeout(320)
            r = await pg.evaluate("""()=>{const v=document.querySelector('#view');
              return {txt:v.textContent.replace(/\\s+/g,' ').trim().length,
                      // The shapes a view can be MADE of. `flux/row` joined the list
                      // when Système stopped being a wall of `key-value`: it is
                      // the same kind of object, so what this counts is
                      // unchanged — is there structure, or only prose.
                      cards:v.querySelectorAll('[data-part="card"],[data-part="tile"],[data-part="key-value"],[data-part="flux/row"]').length,
                      empty:!!v.querySelector('[data-part="empty-state"]'),
                      doc:document.documentElement.scrollWidth,
                      spills:[...v.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>390.5&&!e.closest('[data-part="pill/list"]')&&!e.closest('[data-part="cast"]')).length};}""")
            ok = r['txt'] > 100 and r['doc'] <= 390 and r['spills'] == 0 and (r['cards'] > 0 or r['empty'])
            if not ok: total_bad += 1
            print(("  PASS" if ok else "  FAIL"), f"{name:16}", r)
            await pg.screenshot(path=f"z_{scen}_{name.replace('/','_')}.png")
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "16/16 renders conform" if total_bad == 0 and not errs else f"{total_bad} failure(s)")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if total_bad or errs: raise SystemExit(1)
asyncio.run(main())

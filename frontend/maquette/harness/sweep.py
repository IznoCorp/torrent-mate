"""A sweep across every state, looking for what stopped rendering."""

import asyncio
from common import shot
from playwright.async_api import async_playwright

# The LABEL is a name this tool prints and now also writes as a capture's file
# name, so it is English like every other name here — and it is the same
# vocabulary `scen.py` sweeps the same eight views under, rather than a second
# set of words for one set of screens. The SELECTOR beside it is an address and
# is untouched.
VIEWS = [("acq/now",'[data-page="acq"]'), ("acq/follows",'[data-acqtab="follows"]'),
         ("acq/discover",'[data-acqtab="discover"]'), ("lib/categories",'[data-page="lib"]'),
         ("lib/incomplete",'[data-lens="inc"]'), ("lib/recent",'[data-lens="rec"]'),
         ("arrivals",'[data-page="arr"]'), ("system",'[data-page="sys"]')]

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    # The HOST-ROUTE surface: the measured document is the BUILD, whose
    # envelope names routes only serve.py answers — the worker script, the
    # manifest, the favicons (and Chrome asks for /favicon.ico uninvited).
    # A static server legitimately lacks them, and R52 already holds them
    # against the live host; excluding them keeps this guard sharp for every
    # URL the prototype itself references.
    # The worker-fetch miss is its own case: Chrome words it « A bad HTTP
    # response code (404) was received when fetching the script. » and gives
    # it NO url — the only script the envelope fetches that way is /sw.js.
    HOST_ROUTES = ("favicon", "sw.js", "manifest.webmanifest",
                   "when fetching the script")
    def _console(m):
        if m.type != "error":
            return
        url = (m.location or {}).get("url", "")
        if any(r in url or r in m.text for r in HOST_ROUTES):
            return
        errs.append("console:" + m.text + " ← " + url)
    pg.on("console", _console)
    await pg.goto("http://127.0.0.1:8899/", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")
    bad = 0
    for name, sel in VIEWS:
        await pg.click(sel); await pg.wait_for_timeout(420)
        r = await pg.evaluate("""()=>{
          const v=document.querySelector('#view');
          return {content: v.textContent.replace(/\\s+/g,' ').trim().length,
                  nodes: v.querySelectorAll('*').length,
                  // The shapes a view can be MADE of: a card, a gallery tile,
                  // a key/value row, a fact row. `flux/row` joined the list when
                  // Système stopped being a wall of `key-value` — it is the same
                  // kind of object, so what this counts is unchanged: is there
                  // structure, or only prose.
                  cards: v.querySelectorAll('[data-part="card"],[data-part="tile"],[data-part="key-value"],[data-part="flux/row"]').length,
                  doc: document.documentElement.scrollWidth,
                  device: Math.round(document.querySelector('[data-part="shell/device"]').getBoundingClientRect().width),
                  spills: [...v.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>390.5&&!e.closest('[data-part="pill/list"]')).length};}""")
        ok = r['cards'] > 0 and r['content'] > 120 and r['doc'] <= 390 and r['device'] == 390 and r['spills'] == 0
        if not ok: bad += 1
        print(("PASS" if ok else "FAIL"), f"{name:16}", r)
        await shot(pg, f"sweep-{name.replace('/','_')}")
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "all 8 views render content, with no overflow" if bad==0 and not errs else f"{bad} view(s) failed")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if bad or errs: raise SystemExit(1)
asyncio.run(main())

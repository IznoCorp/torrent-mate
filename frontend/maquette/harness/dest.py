"""R2, hardened: a button must have a DESTINATION, not merely a known class."""
import asyncio

from playwright.async_api import async_playwright


async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]
    # Driving every state without watching for a JS error walks past the
    # loudest evidence there is.
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")
    states=await pg.evaluate("()=>window.__states()")
    without=[]
    for e in states:
        await pg.evaluate("(i)=>window.__go(i)",e); await pg.wait_for_timeout(230)
        r=await pg.evaluate("""()=>{
          // Every screen migrated off `#screen` onto a real route takes its
          // place in this ladder through ONE generic rung — any OPEN screen
          // carries a `data-key`, so its presence is enough, never a
          // per-identity prefix — placed LAST so every other case resolves
          // exactly as before. Without it, a state opening one of those
          // routes would fall through to `#view` and the rule would clear
          // the underlying page's buttons without ever having looked at the
          // screen's own.
          const root=document.querySelector('#dlg').classList.contains('open')?document.querySelector('#dlg')
            :document.querySelector('#screen').classList.contains('open')?document.querySelector('#screen')
            :document.querySelector('#sheet').classList.contains('open')?document.querySelector('#sheet')
            :document.querySelector('[data-part="screen"][data-open][data-key]')
            ??document.querySelector('#view');
          return [...root.querySelectorAll('button, a')]
            .filter(x=>x.getBoundingClientRect().height>0 && !x.disabled
                       && !x.closest('.hbtn') && !x.closest('.hpanel')
                       && !x.closest('details:not([open])'))
            .filter(x=>Object.keys(x.dataset).length===0 && !x.id && !x.onclick
                       && !/searchclear|burger|avatar|fback|more\b|fab|sel\b|vsw|seg\b|pill|tile|ep\b/.test(x.className))
            .map(x=>x.textContent.trim().slice(0,32));}""",)
        for x in r: without.append((e,x))
    print(f"buttons WITHOUT a destination: {len(without)}")
    seen=set()
    for e,x in without:
        if x in seen: continue
        seen.add(x); print(f"   « {x} »   (e.g. {e})")
    print("JS errors:", errs or "none")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if without or errs: raise SystemExit(1)
asyncio.run(main())

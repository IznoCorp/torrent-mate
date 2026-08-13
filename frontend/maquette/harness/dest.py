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
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>window.__measure(true)")
    etats=await pg.evaluate("()=>window.__states()")
    sans=[]
    for e in etats:
        await pg.evaluate("(i)=>window.__go(i)",e); await pg.wait_for_timeout(230)
        r=await pg.evaluate("""()=>{
          const racine=document.querySelector('#dlg').classList.contains('open')?document.querySelector('#dlg')
            :document.querySelector('#screen').classList.contains('open')?document.querySelector('#screen')
            :document.querySelector('#sheet').classList.contains('open')?document.querySelector('#sheet')
            :document.querySelector('#view');
          return [...racine.querySelectorAll('button, a')]
            .filter(x=>x.getBoundingClientRect().height>0 && !x.disabled
                       && !x.closest('.hbtn') && !x.closest('.hpanel')
                       && !x.closest('details:not([open])'))
            .filter(x=>Object.keys(x.dataset).length===0 && !x.id && !x.onclick
                       && !/searchclear|burger|avatar|fback|more\b|fab|sel\b|vsw|seg\b|pill|tile|ep\b/.test(x.className))
            .map(x=>x.textContent.trim().slice(0,32));}""",)
        for x in r: sans.append((e,x))
    print(f"buttons WITHOUT a destination: {len(sans)}")
    vus=set()
    for e,x in sans:
        if x in vus: continue
        vus.add(x); print(f"   « {x} »   (ex. {e})")
    print("JS errors:", errs or "none")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if sans or errs: raise SystemExit(1)
asyncio.run(main())

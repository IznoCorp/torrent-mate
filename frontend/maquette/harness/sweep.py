import asyncio
from playwright.async_api import async_playwright

VIEWS = [("acq/maintenant",'[data-page="acq"]'), ("acq/suivis",'[data-acqtab="suivis"]'),
         ("acq/decouvrir",'[data-acqtab="decouvrir"]'), ("lib/categories",'[data-page="lib"]'),
         ("lib/incomplets",'[data-lens="inc"]'), ("lib/recents",'[data-lens="rec"]'),
         ("arrivees",'[data-page="arr"]'), ("systeme",'[data-page="sys"]')]

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append("console:"+m.text) if m.type=="error" and "favicon" not in m.text else None)
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")
    bad = 0
    for name, sel in VIEWS:
        await pg.click(sel); await pg.wait_for_timeout(420)
        r = await pg.evaluate("""()=>{
          const v=document.querySelector('#view');
          return {contenu: v.textContent.replace(/\\s+/g,' ').trim().length,
                  noeuds: v.querySelectorAll('*').length,
                  cartes: v.querySelectorAll('.card,.tile,.sug,.kv').length,
                  doc: document.documentElement.scrollWidth,
                  dev: Math.round(document.querySelector('.device').getBoundingClientRect().width),
                  deborde: [...v.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>390.5&&!e.closest('.pillscroll')).length};}""")
        ok = r['cartes'] > 0 and r['contenu'] > 120 and r['doc'] <= 390 and r['dev'] == 390 and r['deborde'] == 0
        if not ok: bad += 1
        print(("OK  " if ok else "FAIL"), f"{name:16}", r)
        await pg.screenshot(path=f"w_{name.replace('/','_')}.png")
    print("\nerreurs JS :", errs or "aucune")
    print("VERDICT :", "les 8 vues rendent du contenu, sans débordement" if bad==0 and not errs else f"{bad} vue(s) en échec")
    await b.close()
asyncio.run(main())

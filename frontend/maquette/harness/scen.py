import asyncio
from playwright.async_api import async_playwright
VIEWS=[("acq/encours",'[data-page="acq"]|[data-acqtab="maintenant"]'),("acq/suivis",'[data-acqtab="suivis"]'),
       ("acq/decouvrir",'[data-acqtab="decouvrir"]'),("lib/medias",'[data-page="lib"]|[data-lens="cat"]'),
       ("lib/incomplets",'[data-lens="inc"]'),("lib/recents",'[data-lens="rec"]'),
       ("arrivees",'[data-page="arr"]'),("systeme",'[data-page="sys"]')]
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")
    for scen in ("réel","charge"):
        if scen=="charge":
            await pg.click("#scenBtn"); await pg.wait_for_timeout(400)
            await pg.evaluate("()=>document.querySelector('#toastx').click()")
        print(f"\n═══ scénario {scen} ═══")
        print("  badges :", await pg.evaluate("()=>[...document.querySelectorAll('.navbadge')].map(e=>e.parentElement.textContent.replace(/\\d+$/,'').trim()+'='+e.textContent)"))
        bad=0
        for name,sel in VIEWS:
            for one in sel.split("|"):
                await pg.click(one); await pg.wait_for_timeout(260)
            r=await pg.evaluate("""()=>{const v=document.querySelector('#view');
              return {txt:v.textContent.replace(/\\s+/g,' ').trim().length,
                      cartes:v.querySelectorAll('.card,.tile,.sug,.kv').length,
                      vide:!!v.querySelector('.empty'),
                      img:v.querySelectorAll('img').length,
                      doc:document.documentElement.scrollWidth,
                      deb:[...v.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>390.5&&!e.closest('.pillscroll')).length};}""")
            ok = r['txt']>100 and r['doc']<=390 and r['deb']==0 and (r['cartes']>0 or r['vide'])
            if not ok: bad+=1
            print(("  OK  " if ok else "  FAIL"), f"{name:16}", r)
            await pg.screenshot(path=f"z_{scen}_{name.replace('/','_')}.png")
        print("  verdict :", "conforme" if bad==0 else f"{bad} échec(s)")
    print("\nerreurs JS :", errs or "aucune")
    await b.close()
asyncio.run(main())

import asyncio, json
from playwright.async_api import async_playwright
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")
    ids = await pg.evaluate("()=>window.__states()")
    print(f"{len(ids)} états déclarés\n")
    bad=[]
    for i in ids:
        try:
            await pg.evaluate("(id)=>window.__go(id)", i)
        except Exception as ex:
            bad.append((i,"__go a échoué: "+str(ex)[:60])); print(f"  FAIL {i:28} __go"); continue
        await pg.wait_for_timeout(320)
        r=await pg.evaluate("""()=>{const v=document.querySelector('#view');
          const sh=document.querySelector('#sheet'), sc=document.querySelector('#screen'), dg=document.querySelector('#dlg');
          const couche = sh.classList.contains('open')||sc.classList.contains('open')||dg.classList.contains('open');
          const cible = couche ? (dg.classList.contains('open')?dg:sc.classList.contains('open')?sc:sh) : v;
          return {sk:cible.querySelectorAll('.sk').length, txt:cible.textContent.replace(/\\s+/g,' ').trim().length,
                  doc:document.documentElement.scrollWidth,
                  deb:[...cible.querySelectorAll('*')].filter(e=>e.getBoundingClientRect().right>390.5&&!e.closest('.pillscroll')&&!e.closest('.eps')&&!e.closest('.cast')).length,
                  couche};}""")
        ok = (r['txt']>60 or r['sk']>0) and r['doc']<=390 and r['deb']==0
        if not ok: bad.append((i,r))
        print(("  OK  " if ok else "  FAIL"), f"{i:28}", r)
        await pg.screenshot(path=f"st_{i}.png")
    print("\nerreurs JS :", errs or "aucune")
    print("VERDICT :", f"{len(ids)-len(bad)}/{len(ids)} états conformes" + ("" if not bad else f" — échecs: {[x[0] for x in bad]}"))
    await b.close()
asyncio.run(main())

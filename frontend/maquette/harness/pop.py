import asyncio
from playwright.async_api import async_playwright
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__measure(true)")

    async def clic(js, label):
        await pg.evaluate(js); await pg.wait_for_timeout(320)
        txt = await pg.evaluate("()=>document.querySelector('.eppop')?.innerText.replace(/\\n/g,' | ')")
        print(f"  {label:24} {txt}")
        return txt

    print("── Tintin (possédés + manquants) ──")
    await pg.evaluate("()=>window.__go('feuille-suivi-trous')"); await pg.wait_for_timeout(450)
    a = await clic("()=>[...document.querySelectorAll('.ep')].find(e=>e.className.includes('en_mediatheque')).click()", "épisode possédé")
    b1 = await clic("()=>[...document.querySelectorAll('.ep')].find(e=>e.className.includes('a_recuperer')).click()", "épisode manquant")
    await pg.screenshot(path="m_popover.png")

    print("── Silo (dont épisodes annoncés) ──")
    await pg.evaluate("()=>{fermerPopEp();window.__go('acq-suivis-liste');}"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>openFollowSheet('Silo')"); await pg.wait_for_timeout(450)
    c1 = await clic("()=>{const l=[...document.querySelectorAll('.ep')];l[l.length-1].click();}", "dernier épisode")
    await pg.screenshot(path="m_popover_silo.png")

    print("── fermeture au clic extérieur ──")
    await pg.evaluate("()=>document.querySelector('#sheet').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))")
    await pg.wait_for_timeout(250)
    print("  popover fermé :", await pg.evaluate("()=>!document.querySelector('.eppop')"))
    ok = all(x and ("Diffusé le" in x or "Sortie prévue le" in x or "inconnue" in x) for x in (a,b1,c1))
    print("\nerreurs JS :", errs or "aucune")
    print("VERDICT :", "la date apparaît, en français, selon l'état" if ok and not errs else "à revoir")
    await b.close()
asyncio.run(main())

async def annonce():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__measure(true)")
    await pg.evaluate("()=>window.__go('acq-suivis-liste')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>openFollowSheet('Silo')"); await pg.wait_for_timeout(450)
    await pg.evaluate("()=>document.querySelector('.ep.annonce').click()"); await pg.wait_for_timeout(330)
    txt = await pg.evaluate("()=>document.querySelector('.eppop')?.innerText.replace(/\\n/g,' | ')")
    print("  popover sur un ANNONCÉ :", txt)
    await pg.screenshot(path="m_annonce.png")
    print("  erreurs :", errs or "aucune")
    print("  VERDICT :", "« Sortie prévue » sur un annoncé" if txt and "Sortie prévue" in txt else "à revoir")
    await b.close()
asyncio.run(annonce())

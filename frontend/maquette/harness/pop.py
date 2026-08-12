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

    print("── Tintin (owned + missing) ──")
    await pg.evaluate("()=>window.__go('feuille-suivi-trous')"); await pg.wait_for_timeout(450)
    a = await clic("()=>[...document.querySelectorAll('.ep')].find(e=>e.className.includes('en_mediatheque')).click()", "owned episode")
    b1 = await clic("()=>[...document.querySelectorAll('.ep')].find(e=>e.className.includes('a_recuperer')).click()", "missing episode")
    await pg.screenshot(path="m_popover.png")

    print("── Silo (including announced episodes) ──")
    await pg.evaluate("()=>{fermerPopEp();window.__go('acq-suivis-liste');}"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>openFollowSheet('Silo')"); await pg.wait_for_timeout(450)
    c1 = await clic("()=>{const l=[...document.querySelectorAll('.ep')];l[l.length-1].click();}", "last episode")
    await pg.screenshot(path="m_popover_silo.png")

    print("── closing on outside click ──")
    await pg.evaluate("()=>document.querySelector('#sheet').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))")
    await pg.wait_for_timeout(250)
    print("  popover closed:", await pg.evaluate("()=>!document.querySelector('.eppop')"))
    ok = all(x and ("Diffusé le" in x or "Sortie prévue le" in x or "inconnue" in x) for x in (a,b1,c1))
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "the date appears, in French, following the state" if ok and not errs else "needs review")
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
    print("  popover for an ANNOUNCED episode:", txt)
    await pg.screenshot(path="m_annonce.png")

    # ITS EDGES MUST BE FINDABLE. The popover floats over a matrix of dark
    # cells on a dark surface: a border in `--border` drew a near-black line on
    # a near-black background, and the thing read as text hovering in mid-air
    # rather than as an object with limits. The brand colour is the only one in
    # the palette that separates from everything the app draws behind it.
    contour = await pg.evaluate("""()=>{
      const el = document.querySelector('.eppop');
      const cs = getComputedStyle(el);
      const marque = getComputedStyle(document.documentElement)
        .getPropertyValue('--primary').trim();
      const sonde = document.createElement('span');
      sonde.style.color = marque; document.body.appendChild(sonde);
      const attendu = getComputedStyle(sonde).color;
      sonde.remove();
      return {bord: cs.borderTopColor, attendu,
              fond: cs.backgroundColor,
              cadre: getComputedStyle(document.querySelector('#device')).backgroundColor,
              epaisseur: cs.borderTopWidth};}""")
    distinct = (contour["bord"] == contour["attendu"]
                and contour["bord"] != contour["fond"]
                and contour["bord"] != contour["cadre"])
    print("  contour :", contour)
    print("  VERDICT :", "the date appears, following the episode state" if txt and "Sortie prévue" in txt else "needs review")
    if not distinct:
        print("  ECHEC le contour ne se distingue pas du fond de l'app")
    print("  erreurs :", errs or "none")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if errs or not (txt and "Sortie prévue" in txt) or not distinct: raise SystemExit(1)
asyncio.run(annonce())

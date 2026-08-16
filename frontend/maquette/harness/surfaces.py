import asyncio

from playwright.async_api import async_playwright


async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")

    print("── add screen ──")
    await pg.click("#fab"); await pg.wait_for_timeout(500)
    r=await pg.evaluate("""()=>{const s=document.querySelector('#screen');
      return {ouvert:s.classList.contains('open'),
              compte:(s.querySelector('.rescount')||{}).textContent?.trim(),
              resultats:s.querySelectorAll('.res').length,
              boutons:[...s.querySelectorAll('.resbtn')].map(x=>x.textContent.trim()),
              parId:!!s.querySelector('.byid')};}""")
    print(" ", r)
    await pg.screenshot(path="y_ajout.png")
    # The card wears no inline action: the act lives in the result's panel,
    # so the journey opens the panel first — the same path the finger takes.
    await pg.click("[data-panel='add:3']"); await pg.wait_for_timeout(450)
    await pg.click("#sheet [data-act='add:3']"); await pg.wait_for_timeout(450)
    print("  after adding an absent title:", await pg.evaluate("()=>document.querySelector('.addfoot')?.textContent.trim()"))
    await pg.click("[data-panel='add:0']"); await pg.wait_for_timeout(450)
    await pg.click("#sheet [data-act='add:0']"); await pg.wait_for_timeout(450)
    print("  adding an ALREADY owned title:", await pg.evaluate("()=>{const g=document.querySelector('#dlg');return {ouvert:g.classList.contains('open'),titre:g.querySelector('h3')?.textContent};}"))
    await pg.screenshot(path="y_remplacer.png")
    await pg.evaluate("()=>document.querySelector('#dlgcancel').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>__close('screen')"); await pg.wait_for_timeout(400)

    print("── matrice de saisons ──")
    await pg.click('[data-acqtab="suivis"]'); await pg.wait_for_timeout(350)
    # A card body addresses its panel; it no longer opens a sheet of its own.
    await pg.click('[data-panel="media:American Dad!"]'); await pg.wait_for_timeout(500)
    r=await pg.evaluate("""()=>{const s=document.querySelector('#sheet');
      const ss=[...s.querySelectorAll('.season')];
      return {saisons:ss.length, ordre:ss.slice(0,3).map(x=>x.querySelector('summary').textContent.replace(/\\s+/g,' ').trim()),
              toutesRepliees:ss.every(x=>!x.open), legende:s.querySelectorAll('.legend span').length,
              cellules:s.querySelectorAll('.ep').length};}""")
    print(" ", r)
    await pg.screenshot(path="y_matrice_complete.png")
    await pg.evaluate("()=>document.querySelector('#scrim').click()"); await pg.wait_for_timeout(350)

    await pg.click('[data-page="lib"]'); await pg.click('[data-lens="inc"]'); await pg.wait_for_timeout(400)
    # A library card leads to the media SHEET now, not to the acquisition
    # panel: the seasons are read on the screen it opens.
    await pg.click("[data-fiche='Les aventures de Tintin']"); await pg.wait_for_timeout(600)
    # The media sheet left `#screen` for a real route (`/fiche/$titre`, rendered
    # inside `#coquille`): it is read by the identity it carries,
    # `data-cle="fiche:…"`, never by a bare `.screen.open` — two screens can
    # carry `open` at once and the seasons must come from the fiche, not from
    # whatever sits under it.
    r=await pg.evaluate("""()=>{const s=document.querySelector('.screen.open[data-cle^="fiche:"]');
      if (!s) return {absente:true};
      const ss=[...s.querySelectorAll('.season')];
      return {saisons:ss.length, ouvertes:ss.filter(x=>x.open).length,
              manquants:[...s.querySelectorAll('.miss')].map(x=>x.textContent),
              fraction:s.querySelector('.sheetmeta')?.textContent.trim(),
              etats:[...new Set([...s.querySelectorAll('.ep')].map(x=>x.className.replace('ep ','')))],
              legende:[...s.querySelectorAll('.legend span')].map(x=>x.textContent.trim())};}""")
    print(" ", r)
    await pg.screenshot(path="y_matrice_trous.png")
    print("\nJS errors:", errs or "none")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if errs: raise SystemExit(1)
asyncio.run(main())

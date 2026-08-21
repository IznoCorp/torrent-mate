"""The surfaces a medium is shown on, walked one by one."""

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
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")

    print("── add screen ──")
    await pg.click("#fab"); await pg.wait_for_timeout(500)
    # The add screen left `#screen` for a real route (`/add`, rendered inside
    # `#coquille`), and is read by the identity it carries — `data-key="add:…"`
    # (the mode it was opened in) — never by a bare `[data-part="screen"][data-open]`, which two
    # stacked screens would both answer to. Read at the old layer id, this block
    # measured an empty node and printed zeros for a screen full of results.
    r=await pg.evaluate("""()=>{const s=document.querySelector('[data-part="screen"][data-open][data-key^="add:"]');
      if (!s) return {absent:true};
      // `.res` and `.resbtn` are dead class names — a result row is a
      // `[data-part="result/list"] [data-part="card"]` today, and its foot
      // action was removed on purpose (R71: the panel is the single path to
      // the act). Kept pointing at them, both lines printed zero forever,
      // which reads like « no results » next to a count that says six.
      return {open:s.hasAttribute('data-open'),
              count:(s.querySelector('.rescount')||{}).textContent?.trim(),
              results:s.querySelectorAll('[data-part="result/list"] [data-part="card"]').length,
              feet:[...s.querySelectorAll('[data-part="result/list"] [data-part="card/foot"]')].map(x=>x.textContent.trim()),
              byId:!!s.querySelector('.byid')};}""")
    print(" ", r)
    await pg.screenshot(path="y_ajout.png")
    # The card wears no inline action: the act lives in the result's panel,
    # so the journey opens the panel first — the same path the finger takes.
    await pg.click("[data-panel='add:3']"); await pg.wait_for_timeout(450)
    await pg.click("#sheet [data-act='add:3']"); await pg.wait_for_timeout(450)
    print("  after adding an absent title:", await pg.evaluate("()=>document.querySelector('.addfoot')?.textContent.trim()"))
    await pg.click("[data-panel='add:0']"); await pg.wait_for_timeout(450)
    await pg.click("#sheet [data-act='add:0']"); await pg.wait_for_timeout(450)
    print("  adding an ALREADY owned title:", await pg.evaluate("()=>{const g=document.querySelector('#dlg');return {open:g.hasAttribute('data-open'),title:g.querySelector('h3')?.textContent};}"))
    await pg.screenshot(path="y_remplacer.png")
    await pg.evaluate("()=>document.querySelector('#dlgcancel').click()"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>__close('screen')"); await pg.wait_for_timeout(400)

    print("── season matrix ──")
    await pg.click('[data-acqtab="follows"]'); await pg.wait_for_timeout(350)
    # A card body addresses its panel; it no longer opens a sheet of its own.
    await pg.click('[data-panel="media:American Dad!"]'); await pg.wait_for_timeout(500)
    r=await pg.evaluate("""()=>{const s=document.querySelector('#sheet');
      const ss=[...s.querySelectorAll('[data-part="season"]')];
      return {seasons:ss.length, order:ss.slice(0,3).map(x=>x.querySelector('summary').textContent.replace(/\\s+/g,' ').trim()),
              allCollapsed:ss.every(x=>!x.open), legend:s.querySelectorAll('.legend span').length,
              cells:s.querySelectorAll('[data-part="episode"]').length};}""")
    print(" ", r)
    await pg.screenshot(path="y_matrice_complete.png")
    await pg.evaluate("()=>document.querySelector('#scrim').click()"); await pg.wait_for_timeout(350)

    await pg.click('[data-page="lib"]'); await pg.click('[data-lens="inc"]'); await pg.wait_for_timeout(400)
    # A library card leads to the media SHEET now, not to the acquisition
    # panel: the seasons are read on the screen it opens.
    await pg.click("[data-mediasheet='Les aventures de Tintin']"); await pg.wait_for_timeout(600)
    # The media sheet left `#screen` for a real route (`/mediasheet/$title`, rendered
    # inside `#coquille`): it is read by the identity it carries,
    # `data-key="mediaSheet:…"`, never by a bare `[data-part="screen"][data-open]` — two screens can
    # carry `open` at once and the seasons must come from the mediaSheet, not from
    # whatever sits under it.
    r=await pg.evaluate("""()=>{const s=document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
      if (!s) return {missingScreen:true};
      const ss=[...s.querySelectorAll('[data-part="season"]')];
      return {seasons:ss.length, open:ss.filter(x=>x.open).length,
              missing:[...s.querySelectorAll('[data-part="season/missing"]')].map(x=>x.textContent),
              fraction:s.querySelector('.sheetmeta')?.textContent.trim(),
              states:[...new Set([...s.querySelectorAll('[data-part="episode"]')].map(x=>x.className.replace('ep ','')))],
              legend:[...s.querySelectorAll('.legend span')].map(x=>x.textContent.trim())};}""")
    print(" ", r)
    await pg.screenshot(path="y_matrice_trous.png")
    print("\nJS errors:", errs or "none")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if errs: raise SystemExit(1)
asyncio.run(main())

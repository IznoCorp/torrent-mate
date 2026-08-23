"""Multi-selection in the library, and what it enables."""

import asyncio
from common import shot
from playwright.async_api import async_playwright
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    failures = []
    await pg.goto("http://127.0.0.1:8899/", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")

    print("tab labels:", await pg.evaluate('''()=>[...document.querySelectorAll('[data-part="segment"] button')].map(b=>b.textContent.trim())'''))
    await pg.click('[data-page="lib"]'); await pg.wait_for_timeout(400)
    print("lenses            :", await pg.evaluate('''()=>[...document.querySelectorAll('[data-part="segment"] button')].map(b=>b.textContent.trim())'''))

    print("\n── grid at rest ──")
    print("  chips visible      :", await pg.evaluate("""()=>document.querySelectorAll('[data-part="tile"] [data-part="selection/check"]').length"""), "(expected 0)")
    print("  selection bar:", await pg.evaluate("""()=>!!document.querySelector('[data-part="selection/bar"]')"""), "(expected False)")
    print("  tap opens the sheet:", await pg.evaluate("()=>!!document.querySelector('[data-tile]').dataset.mediasheet"))
    await shot(pg, "selection-grid-rest")

    print("\n── long press ──")
    # A pointer event of type « touch »: the handlers serve finger, mouse and pen
    # through one path, and a raw TouchEvent no longer reaches them.
    await pg.evaluate("""()=>{const el=document.querySelector('[data-tile]'),r=el.getBoundingClientRect();
      const p={bubbles:true,cancelable:true,isPrimary:true,pointerId:1,pointerType:'touch',
               clientX:r.left+r.width/2,clientY:r.top+r.height/2};
      el.dispatchEvent(new PointerEvent('pointerdown',p));
      // The finger LIFTS. A press that never ends is not an input anyone can
      // make, and modelling one leaves the interface in a state real use never
      // reaches.
      window.setTimeout(()=>window.dispatchEvent(new PointerEvent('pointerup',p)), 600);}""")
    await pg.wait_for_timeout(900)
    press = await pg.evaluate("""()=>{const s=document.querySelector('#sheet');
        return {open:s.hasAttribute('data-open'), actions:[...s.querySelectorAll('[data-part="sheet/action"]')].map(x=>x.textContent.trim())};}""")
    print("  sheet open      :", press)
    if not press["open"]:
        failures.append("long press opens nothing")
    await shot(pg, "selection-long-press")
    await pg.evaluate("()=>document.querySelector('#scrim').click()"); await pg.wait_for_timeout(350)

    print("\n── selection mode ──")
    await pg.click('[data-selmode="1"]'); await pg.wait_for_timeout(350)
    print("  chips     :", await pg.evaluate("""()=>document.querySelectorAll('[data-part="tile"] [data-part="selection/check"]').length"""))
    print("  bar       :", (await pg.evaluate("""()=>document.querySelector('[data-part="selection/bar"]').textContent""")).strip()[:52])
    for i in (0,2,5):
        await pg.click(f"[data-tile='{i}']"); await pg.wait_for_timeout(120)
    print("  after 3 taps:", (await pg.evaluate("""()=>document.querySelector('[data-part="selection/bar"] [data-part="selection/caption"]').textContent""")).strip())
    await shot(pg, "selection-selected")
    await pg.click("[data-delsel]"); await pg.wait_for_timeout(400)
    print("  dialog   :", await pg.evaluate("""()=>{const g=document.querySelector('#dlg');
        return {title:g.querySelector('h1,h2,h3').textContent, rows:g.querySelectorAll('[data-part="dialog/manifest"] li').length,
                choices:[...g.querySelectorAll('[data-part="dialog/button"]')].map(x=>x.textContent.trim())};}"""))
    await shot(pg, "selection-delete-multiple")
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "both delete paths are reachable"
          if not failures and not errs else f"FAILED - {failures or errs}")
    await b.close()
    if failures or errs:
        raise SystemExit(1)
asyncio.run(main())

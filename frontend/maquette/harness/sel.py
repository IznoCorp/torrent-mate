import asyncio
from playwright.async_api import async_playwright
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    echecs = []
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")

    print("tab labels:", await pg.evaluate("()=>[...document.querySelectorAll('.seg button')].map(b=>b.textContent.trim())"))
    await pg.click('[data-page="lib"]'); await pg.wait_for_timeout(400)
    print("lentilles          :", await pg.evaluate("()=>[...document.querySelectorAll('.seg button')].map(b=>b.textContent.trim())"))

    print("\n── grille au repos ──")
    print("  pastilles visibles :", await pg.evaluate("()=>document.querySelectorAll('.tile .sel').length"), "(attendu 0)")
    print("  selection bar:", await pg.evaluate("()=>!!document.querySelector('.selbar')"), "(attendu False)")
    print("  tap ouvre la fiche :", await pg.evaluate("()=>!!document.querySelector('[data-tile]').dataset.fiche"))
    await pg.screenshot(path="x_grille_repos.png")

    print("\n── appui long ──")
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
    appui = await pg.evaluate("""()=>{const s=document.querySelector('#sheet');
        return {ouverte:s.classList.contains('open'), actions:[...s.querySelectorAll('.sact')].map(x=>x.textContent.trim())};}""")
    print("  feuille ouverte :", appui)
    if not appui["ouverte"]:
        echecs.append("long press opens nothing")
    await pg.screenshot(path="x_appuilong.png")
    await pg.evaluate("()=>document.querySelector('#scrim').click()"); await pg.wait_for_timeout(350)

    print("\n── selection mode ──")
    await pg.click('[data-selmode="1"]'); await pg.wait_for_timeout(350)
    print("  pastilles :", await pg.evaluate("()=>document.querySelectorAll('.tile .sel').length"))
    print("  barre     :", (await pg.evaluate("()=>document.querySelector('.selbar').textContent")).strip()[:52])
    for i in (0,2,5):
        await pg.click(f"[data-tile='{i}']"); await pg.wait_for_timeout(120)
    print("  after 3 taps:", (await pg.evaluate("()=>document.querySelector('.selbar .n').textContent")).strip())
    await pg.screenshot(path="x_selection.png")
    await pg.click("[data-delsel]"); await pg.wait_for_timeout(400)
    print("  dialogue :", await pg.evaluate("""()=>{const g=document.querySelector('#dlg');
        return {titre:g.querySelector('h3').textContent, lignes:g.querySelectorAll('.manifest li').length,
                choix:[...g.querySelectorAll('.dlgbtn')].map(x=>x.textContent.trim())};}"""))
    await pg.screenshot(path="x_supprmulti.png")
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "both delete paths are reachable"
          if not echecs and not errs else f"FAILED - {echecs or errs}")
    await b.close()
    if echecs or errs:
        raise SystemExit(1)
asyncio.run(main())

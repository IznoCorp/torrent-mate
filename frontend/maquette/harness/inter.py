import asyncio
from playwright.async_api import async_playwright

SW = """([sel,dir,n]) => new Promise(res => {
  const el=document.querySelector(sel), r=el.getBoundingClientRect();
  const x0=dir<0? r.left+r.width-30 : r.left+r.width/2, y0=r.top+r.height/2;
  const mk=(t,x,y)=>new TouchEvent(t,{bubbles:true,cancelable:true,
    touches:t==='touchend'?[]:[new Touch({identifier:1,target:el,clientX:x,clientY:y})],
    changedTouches:[new Touch({identifier:1,target:el,clientX:x,clientY:y})]});
  el.dispatchEvent(mk('touchstart',x0,y0)); let i=0;
  const step=()=>{i++;el.dispatchEvent(mk('touchmove',x0+dir*i*18,y0));
    if(i<n)requestAnimationFrame(step);
    else{el.dispatchEvent(mk('touchend',x0+dir*n*18,y0));setTimeout(()=>res(true),520);}};
  requestAnimationFrame(step);})"""

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")

    print("── Suivis: action swipe ──")
    await pg.click('[data-acqtab="suivis"]'); await pg.wait_for_timeout(300)
    await pg.evaluate(SW, ["#view .swipe", -1, 9])
    print("  transform :", await pg.evaluate("()=>getComputedStyle(document.querySelector('#view .swipe .card')).transform"))

    print("── Library: scrolling + error + end ──")
    await pg.click('[data-page="lib"]'); await pg.wait_for_timeout(400)
    print("  initial tiles:", await pg.evaluate("()=>document.querySelectorAll('#libitems .tile').length"),
          "|", (await pg.evaluate("()=>document.querySelector('#libcount').textContent")).strip())
    for _ in range(3):
        await pg.evaluate("()=>{const p=document.querySelector('#port');p.scrollTop=p.scrollHeight;}")
        await pg.wait_for_timeout(900)
    err = await pg.evaluate("()=>{const e=document.querySelector('.loaderr');return !!e;}")
    print("  error path shown:", err)
    if err:
        await pg.click("#libretry"); await pg.wait_for_timeout(900)
    print("  tiles after retry:", await pg.evaluate("()=>document.querySelectorAll('#libitems .tile').length"))

    print("── Médiathèque : suppression ──")
    await pg.click('[data-lmode="list"]'); await pg.wait_for_timeout(350)
    await pg.evaluate(SW, ["#libitems .swipe", -1, 8])
    await pg.evaluate("()=>document.querySelector('#libitems .swipe .act.remove').click()")
    await pg.wait_for_timeout(400)
    d = await pg.evaluate("""()=>{const g=document.querySelector('#dlg');
      return {ouvert:g.classList.contains('open'), titre:(g.querySelector('h3')||{}).textContent,
              dryrun:!!g.querySelector('.dryrun'), lignes:g.querySelectorAll('.manifest li').length,
              choix:[...g.querySelectorAll('.dlgbtn')].map(x=>x.textContent.trim())};}""")
    print(" ", d)
    await pg.screenshot(path="w_suppression.png")

    print("── Découvrir : lot, panneau, glissé, annuler ──")
    await pg.evaluate("()=>document.querySelector('#dlgcancel').click()"); await pg.wait_for_timeout(300)
    await pg.click('[data-page="acq"]'); await pg.click('[data-acqtab="decouvrir"]'); await pg.wait_for_timeout(450)
    print("  lot initial :", await pg.evaluate("()=>document.querySelectorAll('.sugwrap').length"))
    await pg.evaluate(SW, ["[data-sugwrap='0']", 1, 9])
    print("  after right swipe:", await pg.evaluate("()=>document.querySelectorAll('.sugwrap').length"))
    await pg.click("#toastundo"); await pg.wait_for_timeout(350)
    print("  après Annuler :", await pg.evaluate("()=>document.querySelectorAll('.sugwrap').length"))
    print("\nJS errors:", errs or "none")
    await b.close()
asyncio.run(main())

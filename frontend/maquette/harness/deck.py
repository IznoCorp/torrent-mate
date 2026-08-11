"""Both deck gestures, under real TouchEvents on the real surface.

Synthetic PointerEvents would never be cancelled by the browser, so they prove
nothing about a gesture that has to claim an axis.
"""
import asyncio
from playwright.async_api import async_playwright

SEL = '.dcard[data-depth="0"]'

async def main():
  async with async_playwright() as p:
    b = await p.chromium.launch(channel="chrome")
    ctx = await b.new_context(viewport={"width":390,"height":844}, device_scale_factor=2,
                              is_mobile=True, has_touch=True)
    pg = await ctx.new_page(); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__measure(true)")

    async def deck():
        await pg.evaluate('()=>{window.__reset(); set({page:"acq",acqTab:"decouvrir",phase:"prete"}); S.sugMode="deck"; render();}')
        await pg.wait_for_timeout(600)

    async def titre():
        return await pg.evaluate(f'()=>document.querySelector(\'{SEL} .t\').textContent')

    async def glisser(dx):
        await pg.evaluate("""(dx)=>{
          const c=document.querySelector('.dcard[data-depth="0"]');
          const r=c.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2;
          const mk=(cx)=>new Touch({identifier:1,target:c,clientX:cx,clientY:y});
          const T=(t,pts)=>new TouchEvent(t,{bubbles:true,cancelable:true,touches:pts,targetTouches:pts,changedTouches:pts});
          c.dispatchEvent(T('touchstart',[mk(x)]));
          for (let i=1;i<=6;i++) c.dispatchEvent(T('touchmove',[mk(x+dx*i/6)]));
          c.dispatchEvent(T('touchend',[mk(x+dx)]));
        }""", dx)
        await pg.wait_for_timeout(700)

    await deck()
    t0 = await titre(); n0 = await pg.evaluate("()=>S.sugGone.size")
    await glisser(-170)
    t1 = await titre(); n1 = await pg.evaluate("()=>S.sugGone.size")
    revient = await pg.evaluate("(t)=>deckOrdre().map(i=>SUGGESTIONS[i].t).includes(t)", t0)
    print(f"LEFT   « {t0[:26]} » → « {t1[:26]} »")
    print(f"       dismissed {n0} → {n1} · comes round again: {revient}")

    await deck()
    t2 = await titre()
    await glisser(170)
    t3 = await titre(); n3 = await pg.evaluate("()=>S.sugGone.size")
    annul = await pg.evaluate("()=>!!document.querySelector('#toastundo')")
    print(f"RIGHT  « {t2[:26]} » → « {t3[:26]} »")
    print(f"       dismissed {n3} · undo offered: {annul}")

    ok = (t1 != t0 and n1 == n0 and revient) and (t3 != t2 and n3 == 1 and annul)
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "left skips and comes back, right dismisses with an undo"
          if ok and not errs else "needs review")
    await b.close()

asyncio.run(main())

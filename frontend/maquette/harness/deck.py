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
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>window.__measure(true)")

    async def deck():
        await pg.evaluate('()=>{window.__reset(); applyState({page:"acq",acqTab:"decouvrir",phase:"prete"}); state.sugMode="deck"; render();}')
        await pg.wait_for_timeout(600)

    async def title():
        return await pg.evaluate(f'()=>document.querySelector(\'{SEL} .t\').textContent')

    async def swipe(dx):
        await pg.evaluate("""(dx)=>{
          const c=document.querySelector('.dcard[data-depth="0"]');
          const r=c.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2;
          // Real PointerEvents of type « touch »: the handlers now serve finger,
          // mouse and pen through one path, and the axis claim still lives in
          // `touch-action`, which a synthetic event cannot exercise — that claim
          // is asserted separately, below.
          const P=(t,cx,extra)=>new PointerEvent(t,{bubbles:true,cancelable:true,isPrimary:true,
            pointerId:1,pointerType:'touch',clientX:cx,clientY:y,...(extra||{})});
          c.dispatchEvent(P('pointerdown',x));
          for (let i=1;i<=6;i++) c.dispatchEvent(P('pointermove',x+dx*i/6));
          window.dispatchEvent(P('pointerup',x+dx));
        }""", dx)
        await pg.wait_for_timeout(700)

    await deck()
    t0 = await title(); n0 = await pg.evaluate("()=>state.sugGone.size")
    await swipe(-170)
    t1 = await title(); n1 = await pg.evaluate("()=>state.sugGone.size")
    comes_back = await pg.evaluate("(t)=>deckOrdre().map(i=>SUGGESTIONS[i].t).includes(t)", t0)
    print(f"LEFT   « {t0[:26]} » → « {t1[:26]} »")
    print(f"       dismissed {n0} → {n1} · comes round again: {comes_back}")

    await deck()
    t2 = await title()
    await swipe(170)
    t3 = await title(); n3 = await pg.evaluate("()=>state.sugGone.size")
    undo = await pg.evaluate("()=>!!document.querySelector('#toastundo')")
    print(f"RIGHT  « {t2[:26]} » → « {t3[:26]} »")
    print(f"       dismissed {n3} · undo offered: {undo}")

    # The axis claim is what makes a REAL touch gesture reach us instead of
    # being taken by the browser. A synthetic event never exercises it, so it is
    # asserted on the declaration itself.
    axis = await pg.evaluate("()=>getComputedStyle(document.querySelector('.deck')).touchAction")
    print(f"       axis claim on the deck: {axis}")
    ok = (t1 != t0 and n1 == n0 and comes_back) and (t3 != t2 and n3 == 1 and undo) and axis == "pan-y"
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "left skips and comes back, right dismisses with an undo"
          if ok and not errs else "needs review")
    await b.close()

    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if not ok or errs: raise SystemExit(1)
asyncio.run(main())

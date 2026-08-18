"""Proves that actions MUTATE the state, not merely the display."""
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
    await pg.evaluate("()=>window.__measure(true)")
    cnt = """()=>({takeable:derived.takeable().length, inflight:derived.inflight().length, stuck:derived.stuck().length, blocked:derived.blocked().length,
                   moving:derived.moving().length, follows:world.follows.length,
                   paused:world.follows.filter(f=>f.st==='disabled').length, lib:world.lib.length,
                   acqBadge:(document.querySelector('[data-page=acq] .navbadge')||{}).textContent||null})"""

    await pg.evaluate("()=>window.__go('acq-encours-charge')"); await pg.wait_for_timeout(300)
    a=await pg.evaluate(cnt); print("before grabbing      :", a)
    await pg.evaluate("()=>[...document.querySelectorAll('.cfoot')].find(x=>x.textContent.includes('Récupérer')).click()")
    await pg.wait_for_timeout(400)
    b1=await pg.evaluate(cnt); print("after grabbing       :", b1)
    assert b1["takeable"]==a["takeable"]-1 and b1["inflight"]==a["inflight"]+1, "the card did not move"
    print("  → card moved to En vol, badge", a["acqBadge"], "→", b1["acqBadge"])

    # A folder the providers answered nothing for has NO candidate to pick, and
    # that is the real state of both stuck folders in the calm scenario. The
    # way out is the one that used to be missing: agreeing with the machine.
    await pg.evaluate("()=>window.__go('arr-repos')"); await pg.wait_for_timeout(300)
    a=await pg.evaluate(cnt); print("\nbefore resolution    :", {k:a[k] for k in ('stuck','moving')})
    await pg.evaluate("()=>[...document.querySelectorAll('.cfoot')].find(x=>x.textContent.includes('Résoudre')).click()")
    await pg.wait_for_timeout(450)
    assert await pg.evaluate("()=>document.querySelectorAll('[data-nonmedia=candidat]').length")==0, \
        "a folder with no provider answer must offer no candidate"
    await pg.evaluate("()=>document.querySelector('[data-leave]').click()"); await pg.wait_for_timeout(700)
    b2=await pg.evaluate(cnt); print("after « laisser »    :", {k:b2[k] for k in ('stuck','moving')})
    assert b2["stuck"]==a["stuck"]-1, "the item stayed stuck"
    print("  → out of « Ça coince » with nothing re-scraped")

    # And a folder that DOES have candidates is settled by picking one.
    await pg.evaluate("()=>window.__go('arr-decision')"); await pg.wait_for_timeout(450)
    a=await pg.evaluate(cnt); print("\nbefore pick          :", {k:a[k] for k in ('stuck','moving')})
    nb=await pg.evaluate("()=>document.querySelectorAll('[data-nonmedia=candidat]').length")
    assert nb==5, f"expected the five real candidates, got {nb}"
    await pg.evaluate("()=>document.querySelector('[data-resolve]').click()"); await pg.wait_for_timeout(700)
    b2b=await pg.evaluate(cnt); print("after pick           :", {k:b2b[k] for k in ('stuck','moving')})
    # The folder was on « À traiter », the acquisition side of the same queue.
    # Answering there used to change nothing at all.
    assert b2b["blocked"]==a["blocked"]-1, "the arbitrated item stayed in the queue"
    print("  → candidate picked, and the item leaves « À traiter »")

    await pg.evaluate("()=>window.__go('acq-suivis-liste')"); await pg.wait_for_timeout(300)
    a=await pg.evaluate(cnt)
    await pg.evaluate("()=>{const w=document.querySelector('#view .swipe');w.querySelector('.act.pause').click();}")
    await pg.wait_for_timeout(400)
    b3=await pg.evaluate(cnt); print("\npause                :", a["paused"], "→", b3["paused"])
    assert b3["paused"]==a["paused"]+1
    await pg.evaluate("()=>document.querySelector('#toastundo').click()"); await pg.wait_for_timeout(350)
    b4=await pg.evaluate(cnt); print("  → Annuler restores  :", b4["paused"])
    assert b4["paused"]==a["paused"]

    await pg.evaluate("()=>{const w=document.querySelector('#view .swipe');w.querySelector('.act.remove').click();}")
    await pg.wait_for_timeout(400)
    b5=await pg.evaluate(cnt); print("\ndrop a follow        :", a["follows"], "→", b5["follows"])
    assert b5["follows"]==a["follows"]-1

    await pg.evaluate("()=>window.__go('acq-decouvrir')"); await pg.wait_for_timeout(350)
    a=await pg.evaluate(cnt)
    await pg.evaluate("()=>[...document.querySelectorAll('[data-panel]')].find(e=>e.dataset.panel.startsWith('sug:')).click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>document.querySelector('#sheet .sact.primary').click()"); await pg.wait_for_timeout(450)
    b6=await pg.evaluate(cnt); print("\nfollow a suggestion  :", a["follows"], "→", b6["follows"])
    assert b6["follows"]==a["follows"]+1
    await pg.evaluate("()=>window.__go('acq-suivis-liste',{keep:true})"); await pg.wait_for_timeout(350)
    print("  → at the head of Suivis :", await pg.evaluate("()=>document.querySelector('.ctitle').textContent"),
          "| chip Nouveau :", await pg.evaluate("()=>!!document.querySelector('.freshtag')"))

    await pg.evaluate("()=>window.__go('lib-selection')"); await pg.wait_for_timeout(350)
    a=await pg.evaluate(cnt)
    await pg.evaluate("()=>document.querySelector('[data-delsel]').click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>document.querySelector('.dlgbtn.danger').click()"); await pg.wait_for_timeout(450)
    b7=await pg.evaluate(cnt); print("\nmultiple deletion    :", a["lib"], "→", b7["lib"])
    assert b7["lib"]==a["lib"]-3

    print("\nJS errors:", errs or "none")
    print("VERDICT: all 6 behaviours really mutate the state")
    await b.close()
asyncio.run(main())

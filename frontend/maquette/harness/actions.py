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
    await pg.evaluate("()=>window.__measure(true)")
    cnt = """()=>({aRecup:derived.takeable().length, enVol:derived.inflight().length, coince:derived.stuck().length,
                   avance:derived.moving().length, suivis:world.follows.length,
                   pause:world.follows.filter(f=>f.st==='disabled').length, lib:world.lib.length,
                   badgeAcq:(document.querySelector('[data-page=acq] .navbadge')||{}).textContent||null})"""

    await pg.evaluate("()=>window.__go('acq-encours-charge')"); await pg.wait_for_timeout(300)
    a=await pg.evaluate(cnt); print("before grabbing      :", a)
    await pg.evaluate("()=>[...document.querySelectorAll('.cfoot')].find(x=>x.textContent.includes('Récupérer')).click()")
    await pg.wait_for_timeout(400)
    b1=await pg.evaluate(cnt); print("after grabbing       :", b1)
    assert b1["aRecup"]==a["aRecup"]-1 and b1["enVol"]==a["enVol"]+1, "the card did not move"
    print("  → card moved to En vol, badge", a["badgeAcq"], "→", b1["badgeAcq"])

    await pg.evaluate("()=>window.__go('arr-repos')"); await pg.wait_for_timeout(300)
    a=await pg.evaluate(cnt); print("\nbefore resolution    :", {k:a[k] for k in ('coince','avance')})
    await pg.evaluate("()=>[...document.querySelectorAll('.cfoot')].find(x=>x.textContent.includes('Résoudre')).click()")
    await pg.wait_for_timeout(450)
    await pg.evaluate("()=>document.querySelector('[data-resolve]').click()"); await pg.wait_for_timeout(700)
    b2=await pg.evaluate(cnt); print("after resolution     :", {k:b2[k] for k in ('coince','avance')})
    assert b2["coince"]==a["coince"]-1, "the item stayed stuck"
    print("  → sorti de « Ça coince »")

    await pg.evaluate("()=>window.__go('acq-suivis-liste')"); await pg.wait_for_timeout(300)
    a=await pg.evaluate(cnt)
    await pg.evaluate("()=>{const w=document.querySelector('#view .swipe');w.querySelector('.act.pause').click();}")
    await pg.wait_for_timeout(400)
    b3=await pg.evaluate(cnt); print("\npause                :", a["pause"], "→", b3["pause"])
    assert b3["pause"]==a["pause"]+1
    await pg.evaluate("()=>document.querySelector('#toastundo').click()"); await pg.wait_for_timeout(350)
    b4=await pg.evaluate(cnt); print("  → Annuler restaure  :", b4["pause"])
    assert b4["pause"]==a["pause"]

    await pg.evaluate("()=>{const w=document.querySelector('#view .swipe');w.querySelector('.act.remove').click();}")
    await pg.wait_for_timeout(400)
    b5=await pg.evaluate(cnt); print("\nretirer un suivi     :", a["suivis"], "→", b5["suivis"])
    assert b5["suivis"]==a["suivis"]-1

    await pg.evaluate("()=>window.__go('acq-decouvrir')"); await pg.wait_for_timeout(350)
    a=await pg.evaluate(cnt)
    await pg.evaluate("()=>[...document.querySelectorAll('[data-panel]')].find(e=>e.dataset.panel.startsWith('sug:')).click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>document.querySelector('#sheet .sact.primary').click()"); await pg.wait_for_timeout(450)
    b6=await pg.evaluate(cnt); print("\nsuivre une suggestion:", a["suivis"], "→", b6["suivis"])
    assert b6["suivis"]==a["suivis"]+1
    await pg.evaluate("()=>window.__go('acq-suivis-liste',{keep:true})"); await pg.wait_for_timeout(350)
    print("  → en tête de Suivis :", await pg.evaluate("()=>document.querySelector('.ctitle').textContent"),
          "| chip Nouveau :", await pg.evaluate("()=>!!document.querySelector('.freshtag')"))

    await pg.evaluate("()=>window.__go('lib-selection')"); await pg.wait_for_timeout(350)
    a=await pg.evaluate(cnt)
    await pg.evaluate("()=>document.querySelector('[data-delsel]').click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>document.querySelector('.dlgbtn.danger').click()"); await pg.wait_for_timeout(450)
    b7=await pg.evaluate(cnt); print("\nsuppression multiple :", a["lib"], "→", b7["lib"])
    assert b7["lib"]==a["lib"]-3

    print("\nJS errors:", errs or "none")
    print("VERDICT: all 6 behaviours really mutate the state")
    await b.close()
asyncio.run(main())

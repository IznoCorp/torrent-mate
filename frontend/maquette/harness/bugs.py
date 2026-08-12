"""Every reported defect has its test, written together with the fix."""
import asyncio
from playwright.async_api import async_playwright

async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]; ko=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__measure(true)")
    def chk(nom, cond, detail=""):
        print(("  OK   " if cond else "  ÉCHEC"), nom, detail)
        if not cond: ko.append(nom)

    # 1 — cadence translated into words
    await pg.evaluate("()=>window.__go('acq-suivis-liste')"); await pg.wait_for_timeout(300)
    cad = await pg.evaluate("()=>document.querySelector('.cadence').textContent.trim()")
    chk("1. cadence in words", "*" not in cad, f"→ « {cad} »")

    # 2 — « Voir la fiche » from a follow sheet
    await pg.evaluate("()=>window.__go('feuille-suivi-trous')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>[...document.querySelectorAll('#sheet .sact')].find(x=>x.textContent.includes('Voir la fiche')).click()")
    await pg.wait_for_timeout(700)
    r = await pg.evaluate("()=>({feuille:document.querySelector('#sheet').classList.contains('open'), ecran:document.querySelector('#screen').classList.contains('open')})")
    chk("2. fiche depuis une feuille", r["ecran"] and not r["feuille"], str(r))

    # 2b — from Découvrir
    await pg.evaluate("()=>window.__go('acq-decouvrir')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>[...document.querySelectorAll('[data-panel]')].find(e=>e.dataset.panel.startsWith('sug:')).click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>[...document.querySelectorAll('#sheet .sact')].find(x=>x.textContent.includes('Voir la fiche')).click()")
    await pg.wait_for_timeout(700)
    r = await pg.evaluate("()=>({feuille:document.querySelector('#sheet').classList.contains('open'), ecran:document.querySelector('#screen').classList.contains('open')})")
    chk("2b. idem depuis Découvrir", r["ecran"] and not r["feuille"], str(r))

    # 3 — changing page closes the media sheet
    await pg.evaluate("()=>window.__go('fiche-serie')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>document.querySelector('[data-page=lib]').click()"); await pg.wait_for_timeout(400)
    r = await pg.evaluate("()=>({ecran:document.querySelector('#screen').classList.contains('open'), page:state.page})")
    chk("3. navigation ferme la fiche", not r["ecran"] and r["page"]=="lib", str(r))

    # 4 — the cast carousel no longer blocks vertical scrolling
    await pg.evaluate("()=>window.__go('fiche-serie')"); await pg.wait_for_timeout(400)
    ta = await pg.evaluate("()=>getComputedStyle(document.querySelector('.cast')).touchAction")
    chk("4. carousel allows both axes", "pan-y" in ta, f"touch-action: {ta}")

    # 5 — cast portraits
    n = await pg.evaluate("()=>document.querySelectorAll('.cast .ca img').length")
    chk("5. portraits d'acteurs", n >= 4, f"{n} photos")

    # 6 — the last action is no longer glued to the bar
    r = await pg.evaluate("""()=>{const sc=document.querySelector('#screen .port');
      const btn=[...sc.querySelectorAll('.sact')].pop();
      const bar=document.querySelector('.bottombar').getBoundingClientRect();
      sc.scrollTop=sc.scrollHeight;
      return {ecart:Math.round(bar.top-btn.getBoundingClientRect().bottom)};}""")
    await pg.wait_for_timeout(200)
    r2 = await pg.evaluate("""()=>{const sc=document.querySelector('#screen .port');
      const btn=[...sc.querySelectorAll('.sact')].pop();
      return Math.round(document.querySelector('.bottombar').getBoundingClientRect().top - btn.getBoundingClientRect().bottom);}""")
    chk("6. gap under the last action", r2 >= 12, f"{r2}px at maximum scroll")
    await pg.screenshot(path="g_fiche_bas.png")

    # 7 — a search result leads to its media sheet
    await pg.evaluate("()=>window.__go('acq-ajout-resultats')"); await pg.wait_for_timeout(450)
    has = await pg.evaluate("()=>!!document.querySelector('.reslist .card .poster[data-fiche]')")
    await pg.evaluate("()=>document.querySelector('.reslist .card .poster[data-fiche]').click()"); await pg.wait_for_timeout(600)
    titre = await pg.evaluate("()=>document.querySelector('#screen .ht')?.textContent")
    chk("7. résultat → fiche", has and bool(titre), f"→ « {titre} »")

    # 8 — the resolution screen's way out exists
    await pg.evaluate("()=>window.__go('arr-resolution')"); await pg.wait_for_timeout(450)
    has = await pg.evaluate("()=>!!document.querySelector('[data-manual]')")
    await pg.evaluate("()=>document.querySelector('[data-manual]').click()"); await pg.wait_for_timeout(700)
    q = await pg.evaluate("()=>document.querySelector('#addq')?.value")
    chk("8. recherche manuelle pré-remplie", has and bool(q), f"→ « {q} »")
    await pg.screenshot(path="g_manuelle.png")

    print("\nJS errors:", errs or "none")
    print("VERDICT:", "all 8 defects are fixed" if not ko and not errs else f"remaining: {ko}")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if ko or errs: raise SystemExit(1)
asyncio.run(main())

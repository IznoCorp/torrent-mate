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
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__chargementTermine?.()")
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
    # The media sheet left `#screen` for a real route (`/fiche/$titre`, rendered
    # inside `#coquille`), so it is read by the identity it carries —
    # `data-cle="fiche:…"` — rather than by a layer id it no longer uses, or by
    # a bare `.screen.open` that cannot tell two stacked screens apart.
    r = await pg.evaluate("""()=>({feuille:document.querySelector('#sheet').classList.contains('open'),
      ecran:!!document.querySelector('.screen.open[data-cle^="fiche:"]')})""")
    chk("2. fiche depuis une feuille", r["ecran"] and not r["feuille"], str(r))

    # 2b — from Découvrir
    await pg.evaluate("()=>window.__go('acq-decouvrir')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>[...document.querySelectorAll('[data-panel]')].find(e=>e.dataset.panel.startsWith('sug:')).click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>[...document.querySelectorAll('#sheet .sact')].find(x=>x.textContent.includes('Voir la fiche')).click()")
    await pg.wait_for_timeout(700)
    r = await pg.evaluate("""()=>({feuille:document.querySelector('#sheet').classList.contains('open'),
      ecran:!!document.querySelector('.screen.open[data-cle^="fiche:"]')})""")
    chk("2b. idem depuis Découvrir", r["ecran"] and not r["feuille"], str(r))

    # 3 — changing page closes the media sheet
    await pg.evaluate("()=>window.__go('fiche-serie')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>document.querySelector('[data-page=lib]').click()"); await pg.wait_for_timeout(400)
    r = await pg.evaluate("""()=>({ecran:!!document.querySelector('.screen.open[data-cle^="fiche:"]'),
      page:state.page})""")
    chk("3. navigation ferme la fiche", not r["ecran"] and r["page"]=="lib", str(r))

    # 4 — the cast carousel no longer blocks vertical scrolling
    await pg.evaluate("()=>window.__go('fiche-serie')"); await pg.wait_for_timeout(400)
    ta = await pg.evaluate("()=>getComputedStyle(document.querySelector('.cast')).touchAction")
    chk("4. carousel allows both axes", "pan-y" in ta, f"touch-action: {ta}")

    # 5 — cast portraits
    n = await pg.evaluate("()=>document.querySelectorAll('.cast .ca img').length")
    chk("5. portraits d'acteurs", n >= 4, f"{n} photos")

    # 6 — the last action is no longer glued to the bar
    r = await pg.evaluate("""()=>{const sc=document.querySelector('.screen.open[data-cle^="fiche:"] .port');
      const btn=[...sc.querySelectorAll('.sact')].pop();
      const bar=document.querySelector('.bottombar').getBoundingClientRect();
      sc.scrollTop=sc.scrollHeight;
      return {ecart:Math.round(bar.top-btn.getBoundingClientRect().bottom)};}""")
    await pg.wait_for_timeout(200)
    r2 = await pg.evaluate("""()=>{const sc=document.querySelector('.screen.open[data-cle^="fiche:"] .port');
      const btn=[...sc.querySelectorAll('.sact')].pop();
      return Math.round(document.querySelector('.bottombar').getBoundingClientRect().top - btn.getBoundingClientRect().bottom);}""")
    chk("6. gap under the last action", r2 >= 12, f"{r2}px at maximum scroll")
    await pg.screenshot(path="g_fiche_bas.png")

    # 7 — a search result leads to its media sheet
    await pg.evaluate("()=>window.__go('acq-ajout-resultats')"); await pg.wait_for_timeout(450)
    has = await pg.evaluate("()=>!!document.querySelector('.reslist .card .poster[data-fiche]')")
    await pg.evaluate("()=>document.querySelector('.reslist .card .poster[data-fiche]').click()"); await pg.wait_for_timeout(600)
    titre = await pg.evaluate(
        """()=>document.querySelector('.screen.open[data-cle^="fiche:"] .ht')?.textContent""")
    chk("7. résultat → fiche", has and bool(titre), f"→ « {titre} »")

    # 8 — the resolution screen's way out exists
    await pg.evaluate("()=>window.__go('arr-resolution')"); await pg.wait_for_timeout(450)
    has = await pg.evaluate("()=>!!document.querySelector('[data-manual]')")
    await pg.evaluate("()=>document.querySelector('[data-manual]').click()"); await pg.wait_for_timeout(700)
    q = await pg.evaluate("()=>document.querySelector('#addq')?.value")
    chk("8. recherche manuelle pré-remplie", has and bool(q), f"→ « {q} »")
    await pg.screenshot(path="g_manuelle.png")

    # 9 — B-021: a nav control INSIDE a layer lands, and the layer leaves.
    # « Profil et préférences » in the user sheet navigates via data-go; the
    # sheet must close, the destination must take the layer's history entry,
    # and one back must reach the page one stood on before the sheet opened.
    # A fresh document: the journey starts at a real arrival, whose entry the
    # boot records — that entry is what the back below must land on. Driving
    # states over the previous checks' history would bury it.
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>window.__measure(true)")
    await pg.wait_for_timeout(300)
    await pg.evaluate("()=>document.querySelector('.avatar[data-sheet=utilisateur]').click()")
    await pg.wait_for_timeout(400)
    await pg.evaluate("()=>document.querySelector('#sheet [data-go=profil]').click()")
    await pg.wait_for_timeout(500)
    r = await pg.evaluate("""()=>({feuille:document.querySelector('#sheet').classList.contains('open'),
      page:state.page,
      dessus:(()=>{const e=document.elementFromPoint(195,700);
        return e && e.closest('#sheet') ? 'sheet' : 'page'})()})""")
    chk("9. profil depuis la feuille — la feuille part", not r["feuille"] and r["page"]=="profil" and r["dessus"]=="page", str(r))
    await pg.go_back(); await pg.wait_for_timeout(600)
    r = await pg.evaluate("()=>({page:state.page, feuille:document.querySelector('#sheet').classList.contains('open')})")
    chk("9b. un retour rejoint la page d'avant la feuille", r["page"]=="acq" and not r["feuille"], str(r))

    # 10 — B-022: « Voir mes suivis » in the add screen's footer LANDS: the
    # screen leaves and Acquisition renders. The footer only exists once a
    # media was really added, so the journey walks the real add first.
    # A fresh document: the journey above ends in the very history desync this
    # defect creates, and its late pops would close the screen mid-journey.
    await pg.goto("http://127.0.0.1:8899/wrapped.html", wait_until="load")
    await pg.evaluate("()=>window.__chargementTermine?.()")
    await pg.evaluate("()=>window.__measure(true)")
    await pg.evaluate("()=>window.__go('acq-ajout-resultats')"); await pg.wait_for_timeout(450)
    # The card body opens the result's panel; the panel carries the add act
    # (« Suivre » / « Ajouter »), which is what makes the footer exist.
    # The add screen left `#screen` for a real route (`/ajout`, rendered
    # inside `#coquille`): its results list is now `.screen.open`, not
    # literally `#screen`. This journey opens no fiche, so no key is matched
    # here — the one control on screen is the result's own panel trigger.
    await pg.evaluate("()=>document.querySelector('.screen.open [data-panel^=\"add:\"]').click()")
    await pg.wait_for_timeout(450)
    ajoute = await pg.evaluate("""()=>{
      const acte=document.querySelector('#sheet [data-act^="add:"]');
      if (acte){ acte.click(); return true; } return false;}""")
    await pg.wait_for_timeout(400)
    # An owned result answers with the replace dialog first; confirming it is
    # the same journey, one honest step longer.
    await pg.evaluate("()=>document.querySelector('#dlg [data-confirmadd]')?.click()")
    await pg.wait_for_timeout(500)
    # The footer's « Voir mes suivis » no longer carries `data-go`: it is a
    # React-owned control now (`AddScreen`'s own `toFollows`), not a site the
    # shared legacy `data-go` delegation should also fire on — `.addfoot` is
    # the stable hook the harness has instead.
    foot = await pg.evaluate("()=>!!document.querySelector('.addfoot button')")
    detail = await pg.evaluate("""()=>({added:state.added.size,
      dlg:document.querySelector('#dlg').classList.contains('open'),
      ecran:!!document.querySelector('.screen.open')})""")
    chk("10. l'ajout réel fait naître le pied d'écran", ajoute and foot, f"ajoute={ajoute} foot={foot} {detail}")
    if foot:
        await pg.evaluate("()=>document.querySelector('.addfoot button').click()")
        await pg.wait_for_timeout(600)
        r = await pg.evaluate("""()=>({ecran:!!document.querySelector('.screen.open'),
          page:state.page})""")
        chk("10b. « Voir mes suivis » atterrit", not r["ecran"] and r["page"]=="acq", str(r))
        # 10c — B-025: the entry-count half of the fix. `toFollows` REPLACES
        # the add screen's own entry (same "the layer's entry becomes the
        # arrival" semantics `data-go`'s comment describes — ajout.tsx's own
        # doc comment) instead of pushing beside it. A single real Back must
        # therefore leave `/ajout` in ONE step: no buried layer entry, no
        # stale `/ajout` still one hop under the landing. The comparison is
        # structural, not a literal address string — the harness serves the
        # document off `/wrapped.html`, a path outside the router's own
        # table, so the router's OWN first-navigation settle rewrites the
        # boot entry's address once, on its own schedule, before this
        # journey's first push; comparing against a pre-captured href would
        # be measuring that settle, not the fix.
        await pg.go_back(); await pg.wait_for_timeout(600)
        apres = await pg.evaluate("""()=>({surAjout:location.pathname.startsWith('/ajout'),
          couche:!!(history.state && history.state.layer), page:state.page})""")
        chk("10c. « …et un Back règle l'entrée »",
            not apres["surAjout"] and not apres["couche"] and apres["page"]=="acq", str(apres))

    print("\nJS errors:", errs or "none")
    print("VERDICT:", "all reported defects are fixed" if not ko and not errs else f"remaining: {ko}")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if ko or errs: raise SystemExit(1)
asyncio.run(main())

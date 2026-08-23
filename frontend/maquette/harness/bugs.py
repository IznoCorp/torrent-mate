"""Every reported defect has its test, written together with the fix."""
import asyncio

from common import shot
from playwright.async_api import async_playwright


async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]; ko=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")
    def chk(name, cond, detail=""):
        print(("  PASS" if cond else "  FAIL"), name, detail)
        if not cond: ko.append(name)

    # 1 — cadence translated into words
    await pg.evaluate("()=>window.__go('acq-follows-list')"); await pg.wait_for_timeout(300)
    cad = await pg.evaluate("""()=>document.querySelector('[data-part="cadence"]').textContent.trim()""")
    chk("1. cadence in words", "*" not in cad, f"→ « {cad} »")

    # 2 — « Voir la fiche » from a follow sheet
    await pg.evaluate("()=>window.__go('followsheet-gaps')"); await pg.wait_for_timeout(400)
    await pg.evaluate("""()=>[...document.querySelectorAll('#sheet [data-part="sheet/action"]')].find(x=>x.textContent.includes('Voir la fiche')).click()""")
    await pg.wait_for_timeout(700)
    # The media sheet left `#screen` for a real route (`/mediasheet/$title`, rendered
    # inside `#coquille`), so it is read by the identity it carries —
    # `data-key="mediaSheet:…"` — rather than by a layer id it no longer uses, or by
    # a bare `[data-part="screen"][data-open]` that cannot tell two stacked screens apart.
    r = await pg.evaluate("""()=>({sheet:document.querySelector('#sheet').hasAttribute('data-open'),
      screen:!!document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]')})""")
    chk("2. media sheet from a follow sheet", r["screen"] and not r["sheet"], str(r))

    # 2b — from Découvrir
    await pg.evaluate("()=>window.__go('acq-discover')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>[...document.querySelectorAll('[data-panel]')].find(e=>e.dataset.panel.startsWith('sug:')).click()"); await pg.wait_for_timeout(400)
    await pg.evaluate("""()=>[...document.querySelectorAll('#sheet [data-part="sheet/action"]')].find(x=>x.textContent.includes('Voir la fiche')).click()""")
    await pg.wait_for_timeout(700)
    r = await pg.evaluate("""()=>({sheet:document.querySelector('#sheet').hasAttribute('data-open'),
      screen:!!document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]')})""")
    chk("2b. the same from Découvrir", r["screen"] and not r["sheet"], str(r))

    # 3 — changing page closes the media sheet
    await pg.evaluate("()=>window.__go('mediasheet-series')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>document.querySelector('[data-page=lib]').click()"); await pg.wait_for_timeout(400)
    r = await pg.evaluate("""()=>({screen:!!document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]'),
      page:state.page})""")
    chk("3. navigating closes the media sheet", not r["screen"] and r["page"]=="lib", str(r))

    # 4 — the cast carousel no longer blocks vertical scrolling
    await pg.evaluate("()=>window.__go('mediasheet-series')"); await pg.wait_for_timeout(400)
    ta = await pg.evaluate("""()=>getComputedStyle(document.querySelector('[data-part="cast"]')).touchAction""")
    chk("4. carousel allows both axes", "pan-y" in ta, f"touch-action: {ta}")

    # 5 — cast portraits
    n = await pg.evaluate("""()=>document.querySelectorAll('[data-part="cast"] [data-part="cast/avatar"] img').length""")
    chk("5. cast portraits", n >= 4, f"{n} photos")

    # 6 — the last action is no longer glued to the bar
    r = await pg.evaluate("""()=>{const sc=document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"] [data-part="viewport"]');
      const btn=[...sc.querySelectorAll('[data-part="sheet/action"]')].pop();
      const bar=document.querySelector('[data-part="shell/tab-bar"]').getBoundingClientRect();
      sc.scrollTop=sc.scrollHeight;
      return {gap:Math.round(bar.top-btn.getBoundingClientRect().bottom)};}""")
    await pg.wait_for_timeout(200)
    r2 = await pg.evaluate("""()=>{const sc=document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"] [data-part="viewport"]');
      const btn=[...sc.querySelectorAll('[data-part="sheet/action"]')].pop();
      return Math.round(document.querySelector('[data-part="shell/tab-bar"]').getBoundingClientRect().top - btn.getBoundingClientRect().bottom);}""")
    chk("6. gap under the last action", r2 >= 12, f"{r2}px at maximum scroll")
    await shot(pg, "bugs-sheet-bottom")

    # 7 — a search result leads to its media sheet
    await pg.evaluate("()=>window.__go('acq-add-results')"); await pg.wait_for_timeout(450)
    has = await pg.evaluate("""()=>!!document.querySelector('[data-part="result/list"] [data-part="card"] [data-part="card/poster"][data-mediasheet]')""")
    await pg.evaluate("""()=>document.querySelector('[data-part="result/list"] [data-part="card"] [data-part="card/poster"][data-mediasheet]').click()"""); await pg.wait_for_timeout(600)
    title = await pg.evaluate(
        """()=>document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"] [data-part="hero/title"]')?.textContent""")
    chk("7. result → media sheet", has and bool(title), f"→ « {title} »")

    # 8 — the resolution screen's way out exists
    await pg.evaluate("()=>window.__go('arr-resolution')"); await pg.wait_for_timeout(450)
    has = await pg.evaluate("()=>!!document.querySelector('[data-manual]')")
    await pg.evaluate("()=>document.querySelector('[data-manual]').click()"); await pg.wait_for_timeout(700)
    q = await pg.evaluate("()=>document.querySelector('#addq')?.value")
    chk("8. manual search pre-filled", has and bool(q), f"→ « {q} »")
    await shot(pg, "bugs-manual-search")

    # 9 — B-021: a nav control INSIDE a layer lands, and the layer leaves.
    # « Profil et préférences » in the user sheet navigates via data-go; the
    # sheet must close, the destination must take the layer's history entry,
    # and one back must reach the page one stood on before the sheet opened.
    # A fresh document: the journey starts at a real arrival, whose entry the
    # boot records — that entry is what the back below must land on. Driving
    # states over the previous checks' history would bury it.
    await pg.goto("http://127.0.0.1:8899/", wait_until="load")
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")
    await pg.wait_for_timeout(300)
    await pg.evaluate("""()=>document.querySelector('[data-part="avatar"][data-sheet=utilisateur]').click()""")
    await pg.wait_for_timeout(400)
    await pg.evaluate("()=>document.querySelector('#sheet [data-go=profile]').click()")
    await pg.wait_for_timeout(500)
    r = await pg.evaluate("""()=>({sheet:document.querySelector('#sheet').hasAttribute('data-open'),
      page:state.page,
      onTop:(()=>{const e=document.elementFromPoint(195,700);
        return e && e.closest('#sheet') ? 'sheet' : 'page'})()})""")
    chk("9. profile from the sheet — the sheet leaves", not r["sheet"] and r["page"]=="profile" and r["onTop"]=="page", str(r))
    await pg.go_back(); await pg.wait_for_timeout(600)
    r = await pg.evaluate("()=>({page:state.page, sheet:document.querySelector('#sheet').hasAttribute('data-open')})")
    chk("9b. one back reaches the page held before the sheet", r["page"]=="acq" and not r["sheet"], str(r))

    # 10 — B-022: « Voir mes suivis » in the add screen's footer LANDS: the
    # screen leaves and Acquisition renders. The footer only exists once a
    # media was really added, so the journey walks the real add first.
    # A fresh document: the journey above ends in the very history desync this
    # defect creates, and its late pops would close the screen mid-journey.
    await pg.goto("http://127.0.0.1:8899/", wait_until="load")
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")
    await pg.evaluate("()=>window.__go('acq-add-results')"); await pg.wait_for_timeout(450)
    # The card body opens the result's panel; the panel carries the add act
    # (« Suivre » / « Ajouter »), which is what makes the footer exist.
    # The add screen left `#screen` for a real route (`/add`, rendered
    # inside `#coquille`): its results list is now `[data-part="screen"][data-open]`, not
    # literally `#screen`. This journey opens no mediaSheet, so no key is matched
    # here — the one control on screen is the result's own panel trigger.
    await pg.evaluate("""()=>document.querySelector('[data-part="screen"][data-open] [data-panel^="add:"]').click()""")
    await pg.wait_for_timeout(450)
    added = await pg.evaluate("""()=>{
      const act=document.querySelector('#sheet [data-act^="add:"]');
      if (act){ act.click(); return true; } return false;}""")
    await pg.wait_for_timeout(400)
    # An owned result answers with the replace dialog first; confirming it is
    # the same journey, one honest step longer.
    await pg.evaluate("()=>document.querySelector('#dlg [data-confirmadd]')?.click()")
    await pg.wait_for_timeout(500)
    # The footer's « Voir mes suivis » no longer carries `data-go`: it is a
    # React-owned control now (`AddScreen`'s own `toFollows`), not a site the
    # shared legacy `data-go` delegation should also fire on — `add/foot` is
    # the stable hook the harness has instead.
    foot = await pg.evaluate("""()=>!!document.querySelector('[data-part="add/foot"] button')""")
    detail = await pg.evaluate("""()=>({added:state.added.size,
      dlg:document.querySelector('#dlg').hasAttribute('data-open'),
      screen:!!document.querySelector('[data-part="screen"][data-open]')})""")
    chk("10. a real add brings the screen's footer into being", added and foot, f"added={added} foot={foot} {detail}")
    if foot:
        await pg.evaluate("""()=>document.querySelector('[data-part="add/foot"] button').click()""")
        await pg.wait_for_timeout(600)
        r = await pg.evaluate("""()=>({screen:!!document.querySelector('[data-part="screen"][data-open]'),
          page:state.page})""")
        chk("10b. « Voir mes suivis » lands", not r["screen"] and r["page"]=="acq", str(r))
        # 10c — B-025: the entry-count half of the fix. `toFollows` REPLACES
        # the add screen's own entry (same "the layer's entry becomes the
        # arrival" semantics `data-go`'s comment describes — add.tsx's own
        # doc comment) instead of pushing beside it. A single real Back must
        # therefore leave `/add` in ONE step: no buried layer entry, no
        # stale `/add` still one hop under the landing. The comparison is
        # structural, not a literal address string — the harness serves the
        # document off `/wrapped.html`, a path outside the router's own
        # table, so the router's OWN first-navigation settle rewrites the
        # boot entry's address once, on its own schedule, before this
        # journey's first push; comparing against a pre-captured href would
        # be measuring that settle, not the fix.
        await pg.go_back(); await pg.wait_for_timeout(600)
        after = await pg.evaluate("""()=>({onAdd:location.pathname.startsWith('/add'),
          layer:!!(history.state && history.state.layer), page:state.page})""")
        chk("10c. … and one Back settles the entry",
            not after["onAdd"] and not after["layer"] and after["page"]=="acq", str(after))

    print("\nJS errors:", errs or "none")
    print("VERDICT:", "all reported defects are fixed" if not ko and not errs else f"remaining: {ko}")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if ko or errs: raise SystemExit(1)
asyncio.run(main())

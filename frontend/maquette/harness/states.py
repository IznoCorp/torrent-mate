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
    await pg.evaluate("()=>document.querySelector('#toastx').click()")
    ids = await pg.evaluate("()=>window.__states()")
    print(f"{len(ids)} declared states\n")
    bad=[]
    for i in ids:
        try:
            await pg.evaluate("(id)=>window.__go(id)", i)
        except Exception as ex:
            bad.append((i,"__go failed: "+str(ex)[:60])); print(f"  FAIL {i:28} __go"); continue
        await pg.wait_for_timeout(320)
        r=await pg.evaluate("""()=>{const v=document.querySelector('#view');
          const sh=document.querySelector('#sheet'), sc=document.querySelector('#screen'), dg=document.querySelector('#dlg');
          // The media sheet left `#screen` for a real route (`/fiche/$titre`,
          // rendered inside `#coquille`) and is named by the identity it
          // carries. Without it, a state opening the fiche would count as
          // « no layer » and this rule would measure the page UNDERNEATH —
          // the overflow, the skeletons and the text of a surface the state
          // does not show.
          const fi = document.querySelector('.screen.open[data-cle^="fiche:"]');
          const couche = sh.classList.contains('open')||sc.classList.contains('open')||dg.classList.contains('open')||!!fi;
          // The fiche comes LAST in the precedence, so every pre-existing case
          // resolves to exactly what it resolved to before: a panel or a dialog
          // opened OVER the fiche is what one is looking at, and stays what is
          // measured.
          const cible = couche ? (dg.classList.contains('open')?dg
                                 :sc.classList.contains('open')?sc
                                 :sh.classList.contains('open')?sh:fi) : v;
          return {sk:cible.querySelectorAll('.sk').length, txt:cible.textContent.replace(/\\s+/g,' ').trim().length,
                  doc:document.documentElement.scrollWidth,
                  // An overflow clipped by an ancestor is not overflow:
                  // getBoundingClientRect measures BEFORE clipping. Verify the
                  // clipping instead of whitelisting the class — and the
                  // clipper must itself fit.
                  deb:[...cible.querySelectorAll('*')].filter(e=>{
                    if (e.getBoundingClientRect().right<=390.5) return false;
                    if (e.closest('.pillscroll')||e.closest('.eps')||e.closest('.cast')) return false;
                    for (let p=e.parentElement; p; p=p.parentElement) {
                      const ox=getComputedStyle(p).overflowX;
                      if (ox==='hidden'||ox==='clip') return p.getBoundingClientRect().right>390.5;
                    }
                    return true;
                  }).length,
                  couche};}""")
        ok = (r['txt']>60 or r['sk']>0) and r['doc']<=390 and r['deb']==0
        if not ok: bad.append((i,r))
        print(("  OK  " if ok else "  FAIL"), f"{i:28}", r)
        await pg.screenshot(path=f"st_{i}.png")
    print("\nJS errors:", errs or "none")
    print("VERDICT:", f"{len(ids)-len(bad)}/{len(ids)} states conform" + ("" if not bad else f" — failures: {[x[0] for x in bad]}"))
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if bad or errs: raise SystemExit(1)
asyncio.run(main())

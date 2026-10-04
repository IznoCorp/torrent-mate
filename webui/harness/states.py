"""Every named state is reachable and renders something — and says no design note.

A DESIGN NOTE IS NOT INTERFACE TEXT (B-613). The prototype's annotations live
in `.note` blocks, hidden until the reader asks for them; a sentence citing the
constitution (« — §8 », « (DOIT-7) ») drawn in the interface itself is a note
that leaked into the product. Every state's VISIBLE text (`innerText`, which
skips the hidden notes) cites no § and no DOIT / NE-DOIT-PAS.

NOR A NOTE'S JUSTIFICATION, which needs no § to be one (register train 2): a
sentence telling the DESIGNER why the interface says what it says — « jamais
un silence », « plutôt que d'afficher une liste vide », « sinon chaque lettre
coûte un appel aux providers », « la spine de provenance » — was drawn on four
named states after B-613's § sweep. The clauses met are refused by name
(`JUSTIFICATIONS`); each was read RED on its state before its string lost it.

THE ROOT LADDER HAS NO `#screen` RUNG. It had one, for a legacy node nothing
ever opened, so the rung was identically false; it was removed rather than
replaced, because the generic `[data-part="screen"][data-open][data-key]` rung
already present covers every screen. The hold count is unchanged.
"""

import asyncio

from common import shot, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

# THE NOTES' OWN MARKERS: a reference to the constitution, and the justification
# clauses a leaked note was met carrying. A JavaScript pattern, read on `innerText`.
JUSTIFICATIONS = ("plutôt que d'afficher|se lirait comme|jamais un silence|jamais une date reconstruite|"
                  "spine de provenance|sinon chaque lettre|lue par tout ce qui regarde")
DESIGN_NOTE = r"§\s?\d+|\b(?:NE-)?DOIT(?:-PAS)?-\d+|" + JUSTIFICATIONS


async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
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
        r=await pg.evaluate("""(pattern)=>{const v=document.querySelector('#view');
          const sh=document.querySelector('#sheet'), dg=document.querySelector('#dlg');
          // Every screen migrated off `#screen` onto a real route (the mediaSheet
          // at `/mediasheet/$title`, the add screen at `/add`, the arbitration
          // screen at `/resolution/$folder`, the release picker at
          // `/releases/$title`, the quality profile at `/quality/$name`) is
          // read through ONE generic rung — any OPEN screen carries a
          // `data-key`, so its presence is enough, never a per-identity
          // prefix. Without it, a state opening one of those routes would
          // count as « no layer » and this rule would measure the page
          // UNDERNEATH — the overflow, the skeletons and the text of a
          // surface the state does not show.
          const rt = document.querySelector('[data-part="screen"][data-open][data-key]');
          const layer = sh.hasAttribute('data-open')||dg.hasAttribute('data-open')||!!rt;
          // The route rung comes LAST in the precedence, so every
          // pre-existing case resolves to exactly what it resolved to
          // before: a panel or a dialog opened OVER a route is what one is
          // looking at, and stays what is measured.
          const target = layer ? (dg.hasAttribute('data-open')?dg
                                 :sh.hasAttribute('data-open')?sh:rt) : v;
          return {sk:target.querySelectorAll('[data-skeleton]').length, txt:target.textContent.replace(/\\s+/g,' ').trim().length,
                  notes:target.innerText.match(new RegExp(pattern, 'g'))||[],
                  doc:document.documentElement.scrollWidth,
                  // An overflow clipped by an ancestor is not overflow:
                  // getBoundingClientRect measures BEFORE clipping. Verify the
                  // clipping instead of whitelisting the class — and the
                  // clipper must itself fit. A clipper that does NOT fit
                  // hands the question to the next one, but only one INSIDE
                  // the surface — a card that clips its own poster, slid
                  // mid-swipe past the edge, is clipped by its row, which
                  // fits; the frame's port and device clip everything and
                  // excuse nothing (re-aimed 2026-09-30 — the walk stopped at
                  // the first clipper and read a swipe mid-travel as a spill).
                  spills:[...target.querySelectorAll('*')].filter(e=>{
                    if (e.getBoundingClientRect().right<=390.5) return false;
                    if (e.closest('[data-part="pill/list"]')||e.closest('[data-part="episode/set"]')||e.closest('[data-part="cast"]')) return false;
                    let first=true;
                    for (let p=e.parentElement; p; p=p.parentElement) {
                      if (!first && !target.contains(p)) return true;
                      const ox=getComputedStyle(p).overflowX;
                      if (ox==='hidden'||ox==='clip') {
                        if (p.getBoundingClientRect().right<=390.5) return false;
                        first=false;
                      }
                    }
                    return true;
                  }).length,
                  layer};}""", DESIGN_NOTE)
        ok = (r['txt']>60 or r['sk']>0) and r['doc']<=390 and r['spills']==0 and not r['notes']
        if not ok: bad.append((i,r))
        print(("  PASS" if ok else "  FAIL"), f"{i:28}", r)
        await shot(pg, f"states-{i}")
    print("\nJS errors:", errs or "none")
    print("VERDICT:", f"{len(ids)-len(bad)}/{len(ids)} states conform" + ("" if not bad else f" — failures: {[x[0] for x in bad]}"))
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if bad or errs: raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())

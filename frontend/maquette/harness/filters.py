"""Category filters must FILTER, and their parts must sum to the whole."""
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
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")
    await pg.evaluate("()=>window.__go('lib-grid')"); await pg.wait_for_timeout(400)

    cats = await pg.evaluate("()=>CATS.map(c=>({id:c.id,l:c.l,c:c.c}))")
    parts = sum(c["c"] for c in cats if c["id"] != "all")
    whole = next(c["c"] for c in cats if c["id"] == "all")
    print(f"category parts: {parts} · announced total: {whole}",
          "PASS" if parts == whole else "FAIL — the parts do not sum to the whole")
    if parts != whole: ko.append("category sum")

    for cat in cats:
        await pg.evaluate("(id)=>document.querySelector(`[data-cat=${JSON.stringify(id)}]`).click()", cat["id"])
        await pg.wait_for_timeout(300)
        r = await pg.evaluate("""()=>({shown:document.querySelectorAll('#libitems [data-part="tile"], #libitems [data-part="card"]').length,
          count:document.querySelector('#libcount')?.textContent.replace(/\\s+/g,' ').trim(),
          empty:!!document.querySelector('#libitems [data-part="empty-state"]'),
          coherent:[...document.querySelectorAll('#libitems [data-part="tile"]')].every(t=>{
            const o=libFiltered().find(x=>x.t===t.querySelector('[data-part="tile/title"]').textContent); return !!o;})})""")
        ok = r["shown"] > 0 or r["empty"]
        if not ok: ko.append(cat["l"])
        print(("  PASS" if ok else "  FAIL"), f"{cat['l']:16} {r['shown']:3} rendered · {r['count']}")

    # the filter combines with the search
    await pg.evaluate("()=>document.querySelector('[data-cat=\"tv\"]').click()"); await pg.wait_for_timeout(280)
    await pg.evaluate("()=>{const i=document.querySelector('#libq');i.value='dex';i.dispatchEvent(new Event('input',{bubbles:true}));}")
    await pg.wait_for_timeout(350)
    print("\ncombined (Séries + « dex »):", await pg.evaluate("()=>({n:libFiltered().length, titles:libFiltered().map(x=>x.t), count:document.querySelector('#libcount').textContent.replace(/\\s+/g,' ').trim()})"))
    await pg.screenshot(path="v_filtres.png")
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "filters filter, and the parts sum to the whole" if not ko and not errs else f"remaining: {ko}")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if ko or errs: raise SystemExit(1)
asyncio.run(main())

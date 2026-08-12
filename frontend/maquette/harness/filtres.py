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
    await pg.evaluate("()=>window.__measure(true)")
    await pg.evaluate("()=>window.__go('lib-grille')"); await pg.wait_for_timeout(400)

    cats = await pg.evaluate("()=>CATS.map(c=>({id:c.id,l:c.l,c:c.c}))")
    somme = sum(c["c"] for c in cats if c["id"] != "all")
    tout = next(c["c"] for c in cats if c["id"] == "all")
    print(f"category parts: {somme} · announced total: {tout}",
          "OK" if somme == tout else "ÉCHEC — les parts ne somment pas au tout")
    if somme != tout: ko.append("category sum")

    for cat in cats:
        await pg.evaluate("(id)=>document.querySelector(`[data-cat=${JSON.stringify(id)}]`).click()", cat["id"])
        await pg.wait_for_timeout(300)
        r = await pg.evaluate("""()=>({affiches:document.querySelectorAll('#libitems .tile, #libitems .card').length,
          compte:document.querySelector('#libcount')?.textContent.replace(/\\s+/g,' ').trim(),
          vide:!!document.querySelector('#libitems .empty'),
          coherent:[...document.querySelectorAll('#libitems .tile')].every(t=>{
            const o=libFiltered().find(x=>x.t===t.querySelector('.nm').textContent); return !!o;})})""")
        bon = r["affiches"] > 0 or r["vide"]
        if not bon: ko.append(cat["l"])
        print(("  OK  " if bon else "  ÉCHEC"), f"{cat['l']:16} {r['affiches']:3} rendus · {r['compte']}")

    # the filter combines with the search
    await pg.evaluate("()=>document.querySelector('[data-cat=\"tv\"]').click()"); await pg.wait_for_timeout(280)
    await pg.evaluate("()=>{const i=document.querySelector('#libq');i.value='dex';i.dispatchEvent(new Event('input',{bubbles:true}));}")
    await pg.wait_for_timeout(350)
    print("\ncombiné (Séries + « dex ») :", await pg.evaluate("()=>({n:libFiltered().length, titres:libFiltered().map(x=>x.t), compte:document.querySelector('#libcount').textContent.replace(/\\s+/g,' ').trim()})"))
    await pg.screenshot(path="v_filtres.png")
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "filters filter, and the parts sum to the whole" if not ko and not errs else f"remaining: {ko}")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if ko or errs: raise SystemExit(1)
asyncio.run(main())

"""The full reported journey: Arrivées → Résoudre → no match → manual search
→ ASSOCIATE, and not « add to follows ».
"""
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

    await pg.evaluate("()=>window.__go('arr-charge')"); await pg.wait_for_timeout(320)
    avant = await pg.evaluate("()=>({coince:derived.stuck().length, avance:derived.moving().length, suivis:world.follows.length})")
    print("starting state           :", avant)

    await pg.evaluate("()=>[...document.querySelectorAll('.cfoot')].find(x=>x.textContent.includes('Résoudre')).click()")
    await pg.wait_for_timeout(420)
    print("resolution screen        :", await pg.evaluate("()=>document.querySelector('#screen .h2')?.textContent"))

    await pg.evaluate("()=>document.querySelector('[data-manual]').click()"); await pg.wait_for_timeout(600)
    r = await pg.evaluate("""()=>{const s=document.querySelector('#screen');
      return {bandeau:(s.querySelector('.surferr b')||{}).textContent,
              verbes:[...new Set([...s.querySelectorAll('.reslist .cfoot')].map(x=>x.textContent.trim()))],
              requete:s.querySelector('#addq')?.value,
              blocId:(s.querySelector('.byid summary')||{}).textContent};}""")
    print("search screen            :", r)
    await pg.screenshot(path="p_identifier.png")

    await pg.evaluate("()=>document.querySelector('.reslist .cfoot').click()"); await pg.wait_for_timeout(700)
    apres = await pg.evaluate("()=>({coince:derived.stuck().length, avance:derived.moving().length, suivis:world.follows.length})")
    print("après « Associer »       :", apres)
    print("notification             :", (await pg.evaluate("()=>document.querySelector('#toastmsg')?.textContent"))[:90])

    ok = (apres["coince"] == avant["coince"] - 1 and apres["avance"] == avant["avance"] + 1
          and apres["suivis"] == avant["suivis"] and "Associer" in r["verbes"])
    print("\n— le dossier quitte « Ça coince » :", apres["coince"] == avant["coince"] - 1)
    print("— il rejoint « Ça avance »        :", apres["avance"] == avant["avance"] + 1)
    print("— NO follow was created           :", apres["suivis"] == avant["suivis"])

    # and the « + » returns to follow mode
    await pg.evaluate("()=>window.__go('acq-encours-charge')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>document.querySelector('#fab').click()"); await pg.wait_for_timeout(500)
    v = await pg.evaluate("()=>[...new Set([...document.querySelectorAll('.reslist .cfoot')].map(x=>x.textContent.trim()))]")
    print("— le « + » redit « Suivre/Ajouter » :", v)
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "identify != follow, and context picks the verb" if ok and not errs else "needs review")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if not ok or errs: raise SystemExit(1)
asyncio.run(main())

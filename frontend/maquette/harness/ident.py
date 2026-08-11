"""Le parcours complet signalé par l'opérateur : Arrivées → Résoudre → aucun
match → Chercher manuellement → ASSOCIER, et non « ajouter au suivi »."""
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
    avant = await pg.evaluate("()=>({coince:D.stuck().length, avance:D.moving().length, suivis:W.follows.length})")
    print("état de départ           :", avant)

    await pg.evaluate("()=>[...document.querySelectorAll('.cfoot')].find(x=>x.textContent.includes('Résoudre')).click()")
    await pg.wait_for_timeout(420)
    print("écran de résolution      :", await pg.evaluate("()=>document.querySelector('#screen .h2')?.textContent"))

    await pg.evaluate("()=>document.querySelector('[data-manual]').click()"); await pg.wait_for_timeout(600)
    r = await pg.evaluate("""()=>{const s=document.querySelector('#screen');
      return {bandeau:(s.querySelector('.surferr b')||{}).textContent,
              verbes:[...new Set([...s.querySelectorAll('.resbtn')].map(x=>x.textContent.trim()))],
              requete:s.querySelector('#addq')?.value,
              blocId:(s.querySelector('.byid summary')||{}).textContent};}""")
    print("écran de recherche       :", r)
    await pg.screenshot(path="p_identifier.png")

    await pg.evaluate("()=>document.querySelector('.resbtn').click()"); await pg.wait_for_timeout(700)
    apres = await pg.evaluate("()=>({coince:D.stuck().length, avance:D.moving().length, suivis:W.follows.length})")
    print("après « Associer »       :", apres)
    print("notification             :", (await pg.evaluate("()=>document.querySelector('#toastmsg')?.textContent"))[:90])

    ok = (apres["coince"] == avant["coince"] - 1 and apres["avance"] == avant["avance"] + 1
          and apres["suivis"] == avant["suivis"] and "Associer" in r["verbes"])
    print("\n— le dossier quitte « Ça coince » :", apres["coince"] == avant["coince"] - 1)
    print("— il rejoint « Ça avance »        :", apres["avance"] == avant["avance"] + 1)
    print("— AUCUN suivi n'a été créé        :", apres["suivis"] == avant["suivis"])

    # et le « + » revient bien au mode suivi
    await pg.evaluate("()=>window.__go('acq-encours-charge')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>document.querySelector('#fab').click()"); await pg.wait_for_timeout(500)
    v = await pg.evaluate("()=>[...new Set([...document.querySelectorAll('.resbtn')].map(x=>x.textContent.trim()))]")
    print("— le « + » redit « Suivre/Ajouter » :", v)
    print("\nerreurs JS :", errs or "aucune")
    print("VERDICT :", "identifier ≠ suivre, et le contexte choisit le verbe" if ok and not errs else "à revoir")
    await b.close()
asyncio.run(main())

"""Aucune interaction de formulaire ne doit déplacer le défilement."""
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

    async def essai(etat, sel, idx, label, port="#screen .port"):
        await pg.evaluate("(i)=>window.__go(i)", etat); await pg.wait_for_timeout(420)
        await pg.evaluate(f"(s)=>{{const p=document.querySelector(s); p.scrollTop=Math.min(400, p.scrollHeight-p.clientHeight);}}", port)
        await pg.wait_for_timeout(180)
        av = await pg.evaluate("(s)=>document.querySelector(s).scrollTop", port)
        if av < 20: print(f"  (page trop courte pour {label})"); return
        await pg.evaluate(f"([s,i])=>document.querySelectorAll(s)[i].click()", [sel, idx])
        await pg.wait_for_timeout(380)
        ap = await pg.evaluate("(s)=>document.querySelector(s)?.scrollTop ?? -1", port)
        # Après un filtrage, la page peut devenir plus COURTE que l'écran : il
        # n'y a alors nulle part où défiler, et exiger l'ancienne position
        # serait exiger l'impossible. On compare au maximum atteignable.
        maxi = await pg.evaluate("(s)=>{const p=document.querySelector(s);return Math.max(0,p.scrollHeight-p.clientHeight);}", port)
        attendu = min(av, maxi)
        bon = abs(attendu-ap) < 5
        if not bon: ko.append(label)
        print(("  OK  " if bon else "  ÉCHEC"), f"{label:34} {av} → {ap}" + (f"  (max atteignable {maxi})" if maxi < av else ""))

    print("── profil de qualité ──")
    await essai("ecran-profil", ".opt.check", 2, "case à cocher")
    await essai("ecran-profil", ".opt.radio", 3, "bouton radio")
    await essai("ecran-profil", ".switch", 0, "interrupteur")
    print("── écran d'ajout ──")
    await essai("acq-ajout-resultats", ".segmini button", 1, "segment de type")

    print("\n── saisie au clavier (valeur et curseur) ──")
    await pg.evaluate("()=>window.__go('lib-grille')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>{const i=document.querySelector('#libq'); i.focus(); i.value='dun'; i.dispatchEvent(new Event('input',{bubbles:true}));}")
    await pg.wait_for_timeout(300)
    r = await pg.evaluate("()=>({focus:document.activeElement?.id, val:document.querySelector('#libq')?.value})")
    print("  champ de recherche :", r, "OK" if r["focus"]=="libq" else "PERD LE FOCUS")
    if r["focus"] != "libq": ko.append("focus du champ")

    print("\nerreurs JS :", errs or "aucune")
    print("VERDICT :", "aucune interaction ne déplace le défilement" if not ko and not errs else f"restants : {ko}")
    await b.close()
asyncio.run(main())

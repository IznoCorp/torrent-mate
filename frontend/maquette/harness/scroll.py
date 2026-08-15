"""No form interaction may move the scroll position."""
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

    async def essai(etat, sel, idx, label, port="#screen .port"):
        await pg.evaluate("(i)=>window.__go(i)", etat); await pg.wait_for_timeout(420)
        await pg.evaluate("(s)=>{const p=document.querySelector(s); p.scrollTop=Math.min(400, p.scrollHeight-p.clientHeight);}", port)
        await pg.wait_for_timeout(180)
        av = await pg.evaluate("(s)=>document.querySelector(s).scrollTop", port)
        if av < 20: print(f"  (page trop courte pour {label})"); return
        await pg.evaluate("([s,i])=>document.querySelectorAll(s)[i].click()", [sel, idx])
        await pg.wait_for_timeout(380)
        ap = await pg.evaluate("(s)=>document.querySelector(s)?.scrollTop ?? -1", port)
        # After filtering, the page can become SHORTER than the viewport:
        # there is then nowhere to scroll, and demanding the old position
        # would demand the impossible. Compare against the reachable maximum.
        maxi = await pg.evaluate("(s)=>{const p=document.querySelector(s);return Math.max(0,p.scrollHeight-p.clientHeight);}", port)
        attendu = min(av, maxi)
        bon = abs(attendu-ap) < 5
        if not bon: ko.append(label)
        print(("  OK  " if bon else "  ÉCHEC"), f"{label:34} {av} → {ap}" + (f"  (max atteignable {maxi})" if maxi < av else ""))

    print("── quality profile ──")
    # These two screens left `#screen` for a real route, rendered inside
    # `#coquille` — their scrollport is now wherever `.screen.open .port`
    # resolves (the React section carries the same classes `#screen` did),
    # not literally inside the legacy container.
    ecran_port = ".screen.open .port"
    await essai("ecran-profil", ".opt.check", 2, "checkbox", port=ecran_port)
    await essai("ecran-profil", ".opt.radio", 3, "bouton radio", port=ecran_port)
    await essai("ecran-profil", ".switch", 0, "interrupteur", port=ecran_port)
    print("── add screen ──")
    await essai("acq-ajout-resultats", ".segmini button", 1, "segment de type", port=ecran_port)

    print("\n── saisie au clavier (valeur et curseur) ──")
    await pg.evaluate("()=>window.__go('lib-grille')"); await pg.wait_for_timeout(400)
    await pg.evaluate("()=>{const i=document.querySelector('#libq'); i.focus(); i.value='dun'; i.dispatchEvent(new Event('input',{bubbles:true}));}")
    await pg.wait_for_timeout(300)
    r = await pg.evaluate("()=>({focus:document.activeElement?.id, val:document.querySelector('#libq')?.value})")
    print("  champ de recherche :", r, "OK" if r["focus"]=="libq" else "PERD LE FOCUS")
    if r["focus"] != "libq": ko.append("focus du champ")

    print("\nJS errors:", errs or "none")
    print("VERDICT:", "no interaction moves the scroll position" if not ko and not errs else f"remaining: {ko}")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if ko or errs: raise SystemExit(1)
asyncio.run(main())

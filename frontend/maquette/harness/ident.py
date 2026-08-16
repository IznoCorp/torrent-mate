"""The full reported journey: Arrivées → Résoudre → no match → manual search
→ ASSOCIATE, and not « add to follows ».

The journey also SETTLES a history it stacked — the result's panel and the
`/ajout` address — and the second half of this script holds that settlement:
one announced operation, landing where the walk stood before `/ajout`, and the
next back still worth exactly one step.
"""
import asyncio

from playwright.async_api import async_playwright

# Every popstate the document receives, counted from the page itself: a
# settlement issuing two backs where it should issue one is invisible in the
# landing address (both spend the same two entries) and perfectly visible here.
COMPTEUR = """() => {
  window.__pops = [];
  window.addEventListener('popstate', () => window.__pops.push(
    location.pathname + location.search));
}"""

# Reading the interface after a back that LEFT the document raises instead of
# naming the defect, so the departure is tested first. The test is the origin,
# never the file name: a router-owned address (`/`, `/ajout`) is served by the
# same document and carries no « wrapped.html » anywhere in it.
async def ou(pg):
  """Where the interface is, or None when the document is gone."""
  if pg.is_closed() or not pg.url.startswith("http://127.0.0.1:8899"):
    return None
  try:
    return await pg.evaluate("""()=>({
      adresse: location.pathname + location.search,
      page: state.page,
      feuille: window.__panneau.ouverte(),
      ecran: document.querySelector('#screen').classList.contains('open'),
      message: (document.querySelector('#toastmsg')||{}).textContent || '',
      pops: window.__pops.length,
    })""")
  except Exception:  # noqa: BLE001 — the document left, which is the finding
    return None


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
    await pg.evaluate("()=>window.__measure(true)")
    await pg.evaluate(COMPTEUR)

    await pg.evaluate("()=>window.__go('arr-charge')"); await pg.wait_for_timeout(320)
    avant = await pg.evaluate("()=>({coince:derived.stuck().length, avance:derived.moving().length, suivis:world.follows.length})")
    print("starting state           :", avant)
    # Where the walk stands BEFORE `/ajout` — the manual search pops the
    # resolution entry before pushing its own, so this is the entry the add
    # screen was stacked on, and the one the settlement must land back on.
    depart = await ou(pg)

    await pg.evaluate("()=>[...document.querySelectorAll('.cfoot')].find(x=>x.textContent.includes('Résoudre')).click()")
    await pg.wait_for_timeout(420)
    # The arbitration screen left `#screen` for a real route
    # (`/resolution/$dossier`, rendered inside `#coquille`): it answers to its
    # own identity now, `.screen.open[data-cle^="resolution:"]`, never to the
    # legacy host it used to live in.
    print("resolution screen        :", await pg.evaluate(
        "()=>document.querySelector('.screen.open[data-cle^=\"resolution:\"] .h2')?.textContent"))

    await pg.evaluate("()=>document.querySelector('[data-manual]').click()"); await pg.wait_for_timeout(600)
    # The manual search reached from « Chercher manuellement » is the add
    # screen at `/ajout`, also a real route now — read by its own identity,
    # falling back to an empty node so a screen that failed to open reports
    # its own absence instead of a TypeError.
    r = await pg.evaluate("""()=>{const s=document.querySelector('.screen.open[data-cle^="ajout:"]')
        ?? document.createElement('div');
      return {bandeau:(s.querySelector('.surferr b')||{}).textContent,
              requete:s.querySelector('#addq')?.value,
              blocId:(s.querySelector('.byid summary')||{}).textContent};}""")
    # The card wears no inline action: the verb lives in the result's panel,
    # so the panel is where the rule reads it — same path the finger takes.
    await pg.evaluate("()=>document.querySelector('.reslist .cbody').click()"); await pg.wait_for_timeout(420)
    r["verbes"] = await pg.evaluate("()=>[...document.querySelectorAll('#sheet .sact.primary')].map(x=>x.textContent.trim())")
    print("search screen            :", r)
    await pg.screenshot(path="p_identifier.png")

    avant_assoc = await ou(pg)
    await pg.evaluate("()=>document.querySelector('#sheet .sact.primary').click()"); await pg.wait_for_timeout(700)
    apres = await pg.evaluate("()=>({coince:derived.stuck().length, avance:derived.moving().length, suivis:world.follows.length})")
    print("après « Associer »       :", apres)
    print("notification             :", (await pg.evaluate("()=>document.querySelector('#toastmsg')?.textContent"))[:90])

    ok = (apres["coince"] == avant["coince"] - 1 and apres["avance"] == avant["avance"] + 1
          and apres["suivis"] == avant["suivis"] and "Associer" in r["verbes"])
    print("\n— le dossier quitte « Ça coince » :", apres["coince"] == avant["coince"] - 1)
    print("— il rejoint « Ça avance »        :", apres["avance"] == avant["avance"] + 1)
    print("— NO follow was created           :", apres["suivis"] == avant["suivis"])

    # ── LA TENUE DE L'HISTORIQUE : un seul règlement, annoncé ─────────────
    # Associer settles TWO entries at once — the result's panel and `/ajout`
    # itself. Three things are held together, because no one of them alone
    # names the defect: the LANDING (both a correct settlement and two racing
    # backs spend the same two entries, so the address alone is silent), the
    # COUNT of history operations the settlement issued, and what the NEXT back
    # is still worth. An unannounced surplus pop is read by the engine as the
    # operator's own back gesture; an over-announced one swallows the next real
    # back in silence. One announced operation is the only shape that is
    # neither.
    regle = await ou(pg)
    pops = (regle["pops"] - avant_assoc["pops"]) if regle else None
    print("\n— on revient là où l'on était avant « /ajout » :",
          regle and regle["adresse"], f"(attendu {depart['adresse']})")
    print("— le règlement tient en UNE opération d'historique :", pops, "pop(s)")
    print("— aucune couche ne reste ouverte :",
          regle and not regle["feuille"] and not regle["ecran"])

    # And the entry underneath is still there to be walked: one more back is
    # worth exactly one step. Here that step is the guard at the bottom of the
    # path, which says so rather than leaving — a back the latch had swallowed
    # would say nothing at all, and the document would still be standing on an
    # entry nobody spent.
    await pg.go_back(); await pg.wait_for_timeout(400)
    ensuite = await ou(pg)
    print("— un retour de plus vaut exactement un pas :",
          ensuite and ensuite["message"][:46] or "le document a été quitté")

    tenue = (regle is not None and ensuite is not None
             and regle["adresse"] == depart["adresse"]
             and pops == 1
             and not regle["feuille"] and not regle["ecran"]
             and "quitter" in ensuite["message"].lower()
             and ensuite["page"] == depart["page"])

    # and the « + » returns to follow mode
    await pg.evaluate("()=>window.__go('acq-encours-charge')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>document.querySelector('#fab').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("()=>document.querySelector('[data-search]')?.click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("()=>document.querySelector('.reslist .cbody')?.click()"); await pg.wait_for_timeout(420)
    v = await pg.evaluate("()=>[...document.querySelectorAll('#sheet .sact.primary')].map(x=>x.textContent.trim())")
    print("— le « + » redit « Suivre/Ajouter » :", v)
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "identify != follow, and context picks the verb"
          if ok and tenue and not errs else "needs review")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if not ok or not tenue or errs: raise SystemExit(1)
asyncio.run(main())

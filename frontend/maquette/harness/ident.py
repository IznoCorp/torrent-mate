"""The full reported journey: Arrivées → Résoudre → no match → manual search
→ ASSOCIATE, and not « add to follows ».

The journey also SETTLES a history it stacked — the result's panel and the
`/add` address — and the second half of this script holds that settlement:
one announced operation, landing where the walk stood before `/add`, and the
next back still worth exactly one step.
"""
import asyncio

from playwright.async_api import async_playwright

# Every popstate the document receives, counted from the page itself: a
# settlement issuing two backs where it should issue one is invisible in the
# landing address (both spend the same two entries) and perfectly visible here.
COUNTER = """() => {
  window.__pops = [];
  window.addEventListener('popstate', () => window.__pops.push(
    location.pathname + location.search));
}"""

# Reading the interface after a back that LEFT the document raises instead of
# naming the defect, so the departure is tested first. The test is the origin,
# never the file name: a router-owned address (`/`, `/add`) is served by the
# same document and carries no « wrapped.html » anywhere in it.
async def where(pg):
  """Where the interface is, or None when the document is gone."""
  if pg.is_closed() or not pg.url.startswith("http://127.0.0.1:8899"):
    return None
  try:
    return await pg.evaluate("""()=>({
      address: location.pathname + location.search,
      page: state.page,
      sheet: window.__panel.isOpen(),
      screen: document.querySelector('#screen').classList.contains('open'),
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
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")
    await pg.evaluate(COUNTER)

    await pg.evaluate("()=>window.__go('arr-loaded')"); await pg.wait_for_timeout(320)
    before = await pg.evaluate("()=>({stuck:derived.stuck().length, moving:derived.moving().length, follows:world.follows.length})")
    print("starting state           :", before)
    # Where the walk stands BEFORE `/add` — the manual search pops the
    # resolution entry before pushing its own, so this is the entry the add
    # screen was stacked on, and the one the settlement must land back on.
    start = await where(pg)

    await pg.evaluate("()=>[...document.querySelectorAll('.cfoot')].find(x=>x.textContent.includes('Résoudre')).click()")
    await pg.wait_for_timeout(420)
    # The arbitration screen left `#screen` for a real route
    # (`/resolution/$folder`, rendered inside `#coquille`): it answers to its
    # own identity now, `.screen.open[data-key^="resolution:"]`, never to the
    # legacy host it used to live in.
    print("resolution screen        :", await pg.evaluate(
        "()=>document.querySelector('.screen.open[data-key^=\"resolution:\"] .h2')?.textContent"))

    await pg.evaluate("()=>document.querySelector('[data-manual]').click()"); await pg.wait_for_timeout(600)
    # The manual search reached from « Chercher manuellement » is the add
    # screen at `/add`, also a real route now — read by its own identity,
    # falling back to an empty node so a screen that failed to open reports
    # its own absence instead of a TypeError.
    r = await pg.evaluate("""()=>{const s=document.querySelector('.screen.open[data-key^="add:"]')
        ?? document.createElement('div');
      return {banner:(s.querySelector('.surferr b')||{}).textContent,
              query:s.querySelector('#addq')?.value,
              idBlock:(s.querySelector('.byid summary')||{}).textContent};}""")
    # The card wears no inline action: the verb lives in the result's panel,
    # so the panel is where the rule reads it — same path the finger takes.
    await pg.evaluate("()=>document.querySelector('.reslist .cbody').click()"); await pg.wait_for_timeout(420)
    r["verbs"] = await pg.evaluate("()=>[...document.querySelectorAll('#sheet .sact.primary')].map(x=>x.textContent.trim())")
    print("search screen            :", r)
    await pg.screenshot(path="p_identifier.png")

    before_assoc = await where(pg)
    await pg.evaluate("()=>document.querySelector('#sheet .sact.primary').click()"); await pg.wait_for_timeout(700)
    after = await pg.evaluate("()=>({stuck:derived.stuck().length, moving:derived.moving().length, follows:world.follows.length})")
    print("after « Associer »       :", after)
    print("notification             :", (await pg.evaluate("()=>document.querySelector('#toastmsg')?.textContent"))[:90])

    ok = (after["stuck"] == before["stuck"] - 1 and after["moving"] == before["moving"] + 1
          and after["follows"] == before["follows"] and "Associer" in r["verbs"])
    print("\n— the folder leaves « Ça coince » :", after["stuck"] == before["stuck"] - 1)
    print("— it joins « Ça avance »          :", after["moving"] == before["moving"] + 1)
    print("— NO follow was created           :", after["follows"] == before["follows"])

    # ── THE HISTORY IT HOLDS: one settlement, announced ───────────────────
    # Associer settles TWO entries at once — the result's panel and `/add`
    # itself. Three things are held together, because no one of them alone
    # names the defect: the LANDING (both a correct settlement and two racing
    # backs spend the same two entries, so the address alone is silent), the
    # COUNT of history operations the settlement issued, and what the NEXT back
    # is still worth. An unannounced surplus pop is read by the engine as the
    # operator's own back gesture; an over-announced one swallows the next real
    # back in silence. One announced operation is the only shape that is
    # neither.
    settled = await where(pg)
    pops = (settled["pops"] - before_assoc["pops"]) if settled else None
    print("\n— one lands where the walk stood before « /ajout » :",
          settled and settled["address"], f"(expected {start['address']})")
    print("— the settlement takes ONE history operation :", pops, "pop(s)")
    print("— no layer stays open :",
          settled and not settled["sheet"] and not settled["screen"])

    # And the entry underneath is still there to be walked: one more back is
    # worth exactly one step. Here that step is the guard at the bottom of the
    # path, which says so rather than leaving — a back the latch had swallowed
    # would say nothing at all, and the document would still be standing on an
    # entry nobody spent.
    await pg.go_back(); await pg.wait_for_timeout(400)
    next_ = await where(pg)
    print("— one more back is worth exactly one step :",
          next_ and next_["message"][:46] or "the document was left")

    held = (settled is not None and next_ is not None
            and settled["address"] == start["address"]
            and pops == 1
            and not settled["sheet"] and not settled["screen"]
            and "quitter" in next_["message"].lower()
            and next_["page"] == start["page"])

    # and the « + » returns to follow mode
    await pg.evaluate("()=>window.__go('acq-encours-loaded')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>document.querySelector('#fab').click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("()=>document.querySelector('[data-search]')?.click()"); await pg.wait_for_timeout(500)
    await pg.evaluate("()=>document.querySelector('.reslist .cbody')?.click()"); await pg.wait_for_timeout(420)
    v = await pg.evaluate("()=>[...document.querySelectorAll('#sheet .sact.primary')].map(x=>x.textContent.trim())")
    print("— the « + » says « Suivre/Ajouter » again :", v)
    print("\nJS errors:", errs or "none")
    print("VERDICT:", "identify != follow, and context picks the verb"
          if ok and held and not errs else "needs review")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if not ok or not held or errs: raise SystemExit(1)
asyncio.run(main())

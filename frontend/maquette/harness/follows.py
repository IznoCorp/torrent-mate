"""The follows tab: its list, its groups, and the states it reaches.

It PRINTS what it reads, and HOLDS one act: the search cross empties the filter and the
list is whole again — a FAIL line printed at once and exit 1 when it does not.

AND ONE DRAWING (B-498): a grid tile's status badge wears its tone's DECLARED
fill — the tone the follow's chip says — never the bare ring over the poster
it was drawn as while its fills named custom properties no stylesheet declared.

RE-AIMED by maquette-blocked phase 6 (DESIGN § 1.9): the « Tout », « Séries »,
« Films » pills became ONE filter pill whose panel offers them; the kind is
chosen there (the pill, then the choice), and the print reads the two pills.
"""

import asyncio
from common import shot, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright


async def choose(pg, kind):
  """Chooses a kind the way a finger does: the filter pill, then its panel's choice."""
  await pg.click('#view [data-part="pill/select"][data-follows-filter-pill]'); await pg.wait_for_timeout(500)
  await pg.click(f'#sheet[data-open] [data-part="option"][data-pill="{kind}"]'); await pg.wait_for_timeout(500)


async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
    ctx=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await ctx.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>document.querySelector('#toastx').click()")
    await pg.click('[data-acqtab="follows"]'); await pg.wait_for_timeout(350)

    print("modes offered     :", await pg.evaluate("""()=>[...document.querySelectorAll('[data-part="view/switch"] button')].map(b=>b.getAttribute('aria-label'))"""))
    print("pills             :", await pg.evaluate("""()=>[...document.querySelectorAll('#view [data-part="pill/select"]')].map(b=>b.textContent.trim())"""))
    print("list order        :", await pg.evaluate("""()=>[...document.querySelectorAll('[data-part="card/title"]')].map(e=>e.textContent).slice(0,6)"""))
    print("dot across a chip :", await pg.evaluate("""()=>{const c=document.querySelector('[data-part="chip"]');const s=getComputedStyle(c,'::before');return {w:s.width,h:s.height,radius:s.borderRadius};}"""))
    # « title alone » is held by R409 (`card_title_alone.py`) over every card of
    # every named state; the print that stood here read four and asserted nothing.
    await shot(pg, "follows-list")

    await pg.click('[data-fmode="group"]'); await pg.wait_for_timeout(350)
    print("groups rendered   :", await pg.evaluate('''()=>[...document.querySelectorAll('[data-part="section/head"] [data-part="section/title"]')].map(e=>e.textContent)'''))
    print("chip hidden in a homogeneous group:", await pg.evaluate("""()=>{
       const secs=[...document.querySelectorAll('[data-part="section"]')];
       const upToDate=secs.find(s=>(s.querySelector('[data-part="section/head"] [data-part="section/title"]')||{}).textContent==='À jour');
       return upToDate? upToDate.querySelectorAll('[data-part="chip"]').length===0 : 'group absent';}"""))
    print("chip kept in a heterogeneous group:", await pg.evaluate("""()=>{
       const secs=[...document.querySelectorAll('[data-part="section"]')];
       const d=secs.find(s=>(s.querySelector('[data-part="section/head"] [data-part="section/title"]')||{}).textContent==='Demandent quelque chose');
       return d? d.querySelectorAll('[data-part="chip"]').length>0 : 'group absent';}"""))
    await shot(pg, "follows-groups")

    failures = []
    await pg.click('[data-fmode="grid"]'); await pg.wait_for_timeout(350)
    print("tiles             :", await pg.evaluate("""()=>document.querySelectorAll('[data-part="tile"]').length"""),
          "| badges :", await pg.evaluate("""()=>[...document.querySelectorAll('[data-part="tile/badge"]')].map(e=>e.textContent)"""))
    await shot(pg, "follows-grid")
    # Each badge's fill against its tone's own token, resolved by the browser.
    painted = await pg.evaluate("""()=>{
      const resolve = (token) => { const probe = document.createElement('span');
        probe.style.background = `var(${token})`; document.body.appendChild(probe);
        const value = getComputedStyle(probe).backgroundColor; probe.remove(); return value; };
      return [...document.querySelectorAll('[data-part="tile/badge"]')].map((badge) => ({
        text: badge.textContent, tone: badge.dataset.tone || null,
        fill: getComputedStyle(badge).backgroundColor,
        wanted: badge.dataset.tone ? resolve(`--color-${badge.dataset.tone === 'neutral' ? 'neutral-signal' : badge.dataset.tone}`) : null}));
    }""")
    unpainted = [one for one in painted if not one["tone"] or one["fill"] != one["wanted"]]
    if not painted or unpainted:
        failures.append("every status badge wears its tone's declared fill (B-498)")
        print(f"  FAIL every status badge wears its tone's declared fill (B-498) — {unpainted[:3] or 'no badge'}")

    await pg.click('[data-fmode="list"]'); await choose(pg, "movies")
    print("Films filter      :", await pg.evaluate("""()=>[...document.querySelectorAll('[data-part="card/title"]')].map(e=>e.textContent)"""))
    print("film label        :", await pg.evaluate("""()=>document.querySelector('[data-part="chip"]').textContent"""))
    print("film actions      :", await pg.evaluate("""()=>[...document.querySelectorAll('[data-part="swipe"] [data-part="swipe/action"]')].slice(0,2).map(e=>e.textContent.trim())"""))

    # THE SEARCH CROSS EMPTIES THE FILTER, and the list is whole again. Read on
    # the store and on the rows, never on the field alone: a cross that only
    # blanked the input would leave the list filtered under an empty box.
    await choose(pg, "tout")  # french-ok: the « everything » kind's id, a data value the markup emits
    whole = await pg.evaluate("""()=>document.querySelectorAll('#view [data-part="card/title"]').length""")
    await pg.fill('#follq', 'zzz-no-such-follow'); await pg.wait_for_timeout(300)
    narrowed = await pg.evaluate("""()=>document.querySelectorAll('#view [data-part="card/title"]').length""")
    await pg.click('#view [data-clear-filter]'); await pg.wait_for_timeout(300)
    cleared = await pg.evaluate("""()=>({filter: window.__store.read().state.filter,
        rows: document.querySelectorAll('#view [data-part="card/title"]').length})""")
    if narrowed >= whole or cleared["filter"] != "" or cleared["rows"] != whole:
        failures.append("the search cross empties the filter and the list is whole again")
        print(f"  FAIL the search cross empties the filter and the list is whole again — "
              f"whole={whole} narrowed={narrowed} after={cleared}")
    print("\nJS errors:", errs or "none")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if errs or failures: raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())

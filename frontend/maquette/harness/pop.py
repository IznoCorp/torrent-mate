"""Popovers and their dismissal."""

import asyncio
from common import shot
from playwright.async_api import async_playwright
async def main():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/", wait_until="load")
    # The startup screen covers the frame for as long as the load it stands
    # for lasts. Nothing is being fetched here, so the harness closes that
    # wait through the same seam the app uses, rather than sleeping it out.
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>window.__measure(true)")

    async def click_(js, label):
        # WHICH EPISODE WAS TAPPED, read from the cell itself BEFORE it is
        # tapped. The popover says a sentence about an episode; a hold that
        # reads only the layer passes over a sentence about the WRONG one, and
        # that is the half this rule owed since the producer moved (L19).
        tapped = await pg.evaluate(js.replace(".click()", ".dataset.ep"))
        # AND WHAT THE CATALOGUE SAYS ABOUT THAT EPISODE — its own title and its
        # own air date, read from the référentiel rather than from the popover.
        # `SssEnn` is composed from the CELL, so it is right even when the
        # episode looked up is the wrong one: a mutation making the producer
        # answer the season's FIRST episode left every check green while the
        # date and the title belonged to another episode entirely.
        expected = await pg.evaluate("""(written)=>{
          if (!written) return null;
          const [title, season, number] = written.split('|');
          const sheet = window.__referentiel.sheetFor(title);
          const one = (sheet?.eps?.[season] || []).find(
            (e) => String(e.n) === number);
          return one ? {title: one.t || null,
                        air: one.air ? window.__referentiel.dateFR(one.air) : null}
                     : null;}""", tapped)
        await pg.evaluate(js); await pg.wait_for_timeout(320)
        txt = await pg.evaluate("""()=>document.querySelector('[data-part="episode/popover"]')?.innerText.replace(/\\n/g,' | ')""")
        print(f"  {label:24} {txt}")
        named.append((label, tapped, txt, expected))
        return txt

    # (label, the cell's own `data-ep`, what the popover said)
    named = []
    print("── Tintin (owned + missing) ──")
    await pg.evaluate("()=>window.__go('followsheet-gaps')"); await pg.wait_for_timeout(450)
    # The two episodes are picked by the STATE ATTRIBUTES the cell emits,
    # never by its class: `data-in-library` and `data-announced` are written
    # from the same expression as the class and survive it.
    #
    # « MISSING » IS THE ABSENCE OF BOTH, and that is wider than `to_grab` —
    # deliberately. The component's state can also be `pending` or
    # `acquiring`, and an episode in either is aired and not owned exactly
    # like a `to_grab` one, which is precisely what the hold below asks
    # about: that the popover gives its broadcast date. Picking the class
    # `to_grab` measured a narrower thing than the rule claims to.
    a = await click_("""()=>[...document.querySelectorAll('[data-part="episode"]')].find(e=>e.hasAttribute('data-in-library')).click()""", "owned episode")
    b1 = await click_("""()=>[...document.querySelectorAll('[data-part="episode"]')].find(e=>!e.hasAttribute('data-in-library') && !e.hasAttribute('data-announced')).click()""", "missing episode")
    await shot(pg, "pop-episode")

    print("── Silo (including announced episodes) ──")
    await pg.evaluate("()=>{closePopEp();window.__go('acq-follows-list');}"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>window.__panel.produce('follow', 'Silo')"); await pg.wait_for_timeout(450)
    # THE SAME SHAPE as the two above, so `click_` can read the cell's own
    # `data-ep` from it before tapping. It used to be a block statement, which
    # answered nothing when read as an expression — and the identity half then
    # had nothing to compare, which it said out loud rather than passing.
    c1 = await click_("""()=>[...document.querySelectorAll('[data-part="episode"]')].at(-1).click()""", "last episode")
    await shot(pg, "pop-last-episode")

    print("── closing on outside click ──")
    await pg.evaluate("()=>document.querySelector('#sheet').dispatchEvent(new PointerEvent('pointerdown',{bubbles:true}))")
    await pg.wait_for_timeout(250)
    print("  popover closed:", await pg.evaluate("""()=>!document.querySelector('[data-part="episode/popover"]')"""))
    ok = all(x and ("Diffusé le" in x or "Sortie prévue le" in x or "inconnue" in x) for x in (a,b1,c1))

    # ── AND IT IS ABOUT THE EPISODE THAT WAS TAPPED ────────────────────────
    # `title|season|episode|state` is what the cell writes; `SssEnn` is what the
    # popover's first line says. A popover that opened correctly and described
    # its neighbour would satisfy every check above.
    identity = True
    for label, written, said, expected in named:
        if not written or not said:
            identity = False
            print(f"  FAIL {label}: nothing to compare — cell {written!r}, said {said!r}")
            continue
        _, season, number, _ = written.split("|")
        number_name = f"S{int(season):02d}E{int(number):02d}"
        if not said.startswith(number_name):
            identity = False
            print(f"  FAIL {label}: tapped {number_name}, the popover says {said[:40]!r}")
            continue
        # THE FACTS, NOT ONLY THE NUMBER. The number is composed from the cell
        # and is right whichever episode was looked up; the title and the date
        # are the looked-up episode's, and they are what a wrong lookup shows.
        wrong = []
        if expected is None:
            wrong.append("the catalogue knows nothing of it")
        else:
            if expected["title"] and expected["title"] not in said:
                wrong.append(f"title {expected['title']!r}")
            if expected["air"] and expected["air"] not in said:
                wrong.append(f"air date {expected['air']!r}")
        if wrong:
            identity = False
            print(f"  FAIL {label}: {number_name} says {said[:60]!r} — missing "
                  f"{', '.join(wrong)}")
        else:
            print(f"  PASS {label} is about {number_name}, with its own facts")

    print("\nJS errors:", errs or "none")
    print("VERDICT:", "the date appears, in French, following the state, about "
          "the episode tapped" if ok and identity and not errs else "needs review")
    await b.close()
    # THE VERDICT REACHES THE EXIT CODE. It did not: `ok` was computed and
    # discarded, so this half of the rule could print « needs review » and pass
    # the suite. The other half already raised; this one does now.
    if errs or not ok or not identity:
        raise SystemExit(1)
asyncio.run(main())

async def announced():
  async with async_playwright() as p:
    b=await p.chromium.launch(channel="chrome")
    c=await b.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
    pg=await c.new_page(); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto("http://127.0.0.1:8899/", wait_until="load")
    await pg.evaluate("()=>window.__measure(true)")
    await pg.evaluate("()=>window.__go('acq-follows-list')"); await pg.wait_for_timeout(300)
    await pg.evaluate("()=>window.__panel.produce('follow', 'Silo')"); await pg.wait_for_timeout(450)
    await pg.evaluate("""()=>document.querySelector('[data-part="episode"][data-announced]').click()"""); await pg.wait_for_timeout(330)
    txt = await pg.evaluate("""()=>document.querySelector('[data-part="episode/popover"]')?.innerText.replace(/\\n/g,' | ')""")
    print("  popover for an ANNOUNCED episode:", txt)
    await shot(pg, "pop-announced-episode")

    # ITS EDGES MUST BE FINDABLE. The popover floats over a matrix of dark
    # cells on a dark surface: a border in `--border` drew a near-black line on
    # a near-black background, and the thing read as text hovering in mid-air
    # rather than as an object with limits. The brand colour is the only one in
    # the palette that separates from everything the app draws behind it.
    outline = await pg.evaluate("""()=>{
      const el = document.querySelector('[data-part="episode/popover"]');
      const cs = getComputedStyle(el);
      const brand = getComputedStyle(document.documentElement)
        .getPropertyValue('--color-primary').trim();
      const probe = document.createElement('span');
      probe.style.color = brand; document.body.appendChild(probe);
      const expected = getComputedStyle(probe).color;
      probe.remove();
      return {border: cs.borderTopColor, expected,
              background: cs.backgroundColor,
              frame: getComputedStyle(document.querySelector('#device')).backgroundColor,
              width: cs.borderTopWidth};}""")
    distinct = (outline["border"] == outline["expected"]
                and outline["border"] != outline["background"]
                and outline["border"] != outline["frame"])
    print("  outline :", outline)
    print("  VERDICT :", "the date appears, following the episode state" if txt and "Sortie prévue" in txt else "needs review")
    if not distinct:
        print("  FAIL the outline does not separate from the app's background")
    print("  errors  :", errs or "none")
    await b.close()
    # A script that only prints can never fail, and a script that cannot fail
    # proves nothing: the verdict has to reach the exit code.
    if errs or not (txt and "Sortie prévue" in txt) or not distinct: raise SystemExit(1)
asyncio.run(announced())

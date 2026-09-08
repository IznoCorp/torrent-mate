"""Popovers and their dismissal.

ITS VERDICTS GO THROUGH THE JOURNAL, and they used not to. This script printed
hand-rolled `PASS` / `FAIL` lines and ended without a summary, so the recorder
that keeps every rule's hold count could not read it: it was carried as
« unparseable » for as long as it has existed, and a rule whose count nobody
holds is a rule that can quietly stop holding anything. Two browsers are opened
one after the other and one journal spans both — the summary is what ends the
process, so it is called once, at the end of the second.
"""

import asyncio
from common import Journal, shot
from playwright.async_api import async_playwright
journal = Journal("the episode date popover, in all its states")


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
        # that is the half this rule owed once the producer moved.
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
    journal.check("a tap outside closes the popover",
                  await pg.evaluate("""()=>!document.querySelector('[data-part="episode/popover"]')"""))
    for label, said in (("owned episode", a), ("missing episode", b1),
                        ("last episode", c1)):
        journal.check(f"{label}: the popover dates the episode, in French",
                      bool(said) and ("Diffusé le" in said
                                      or "Sortie prévue le" in said
                                      or "inconnue" in said),  # french-ok: the app's own rendered words are what this reads
                      str(said)[:70])

    # ── AND IT IS ABOUT THE EPISODE THAT WAS TAPPED ────────────────────────
    # `title|season|episode|state` is what the cell writes; `SssEnn` is what the
    # popover's first line says. A popover that opened correctly and described
    # its neighbour would satisfy every check above.
    for label, written, said, expected in named:
        if not journal.check(f"{label}: there is something to compare",
                             bool(written) and bool(said),
                             f"cell {written!r}, said {said!r}"):
            continue
        _, season, number, _ = written.split("|")
        number_name = f"S{int(season):02d}E{int(number):02d}"
        if not journal.check(f"{label}: the popover is about the episode tapped",
                             said.startswith(number_name),
                             f"tapped {number_name}, said {said[:40]!r}"):
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
        journal.check(f"{label} carries {number_name}'s OWN facts", not wrong,
                      f"says {said[:60]!r}" + (f" — missing {', '.join(wrong)}"
                                               if wrong else ""))

    journal.check("no JS error along the walk", not errs, str(errs or "none"))
    await b.close()
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
    journal.check("an ANNOUNCED episode's popover gives its release date",
                  bool(txt) and "Sortie prévue" in txt,  # french-ok: the app's own rendered words are what this reads
                  str(txt)[:70])
    journal.check("the popover's outline separates it from what is behind it",
                  distinct, str(outline))
    journal.check("no JS error along the announced walk", not errs,
                  str(errs or "none"))
    await b.close()
    # THE SUMMARY IS WHAT ENDS THE PROCESS, and it is called once for the two
    # runs: it prints the executed count the recorder reads and raises on any
    # failure. Before it existed here, a verdict was printed and discarded.
    journal.summary()
asyncio.run(announced())

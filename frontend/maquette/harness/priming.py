"""R119 — priming draws what the tap knew, and a skeleton for the rest.

THE DEFECT (B-283). While a media sheet's read is in flight, the screen printed
its unknown parts as ANSWERS — « aucun synopsis », « aucune distribution »,
« pas de bande-annonce », seasons « inconnu » — assertions about data that has
not arrived, which the constitution refuses (§13). The decision that governs
the arrival — « A généralisée + amorçage » — says the screen opens with what
the tap already knew, in real content, and draws a SKELETON for the parts still
to come. Never an answer.

WHY NOTHING SAW IT, and why this rule cannot read the page as it is served.
The prototype's placeholder is the engine's COMPLETE sheet, so during priming
here no field is ever missing and no assertion is ever printed: a rule that
reads the full placeholder is green over the defect it is written for — the
species the register counts most. The real backend's projection carries
`{t, f}`, and THAT is the case driven here: the reference's `sheetFor` is
wrapped to answer the title, the kind and the year alone for the sheet under
test, and the read is held back through the mock layer's own knob.

HOW THE TWO SEAMS ARE REACHED BEFORE THE SCREEN FIRST RENDERS. A cold load
mounts the screen and issues the read at boot, so a wrapper installed after
`load` is installed after the placeholder was computed. Both seams are
published by assignment onto `window`, so an init script defines a SETTER for
each: the reference is wrapped the instant it is published, and the latency is
set the instant the layer is installed. The boot's own reads are slowed by the
same latency; the screen does not wait for them.

WHAT IT DOES NOT READ, said first:
  - The RENDERING of a skeleton line. No named state shows the priming at
    rest — the placeholder is complete — so the oracle never measures it; the
    line's drawing is its variant's, and what this rule holds is that a line
    STANDS where an assertion would, and stands down when the read lands.
  - Any sheet but Broadchurch's. It is the one title whose served sheet lacks
    exactly one part (the trailer) while the cast and the seasons are full, so
    the landed reading has ONE no-info to find and every other part to land.
  - The seasons' own placeholder: there is none, and their flight is read
    through the same skeleton count — three of the lines counted below stand
    in the library facts while the seasons are out.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal, open_page

TITLE = "Broadchurch"
# What the tap knows: the title, the kind and the year — the projection a list
# row carries, and what the screen may draw as content while the rest is out.
KEPT = ["t", "k", "y"]
# Long enough that every reading below is taken with the read still out under
# the suite's parallel load, and short enough that the rule stays cheap.
LATENCY_MILLISECONDS = 2000
# How long the screen is given to mount on a cold load before the in-flight
# reading is taken. Well under the latency, so the reading is in flight or the
# hold that says so falls.
MOUNT_DEADLINE_MILLISECONDS = 1500
# At least: the metadata line, the genres, the synopsis, the director, the cast
# strip, the trailer, the seasons, the aired count, the completeness, the
# identifiers — with a margin for the ones that land with the kept keys.
SKELETONS_AT_LEAST = 6

INTERCEPT = """({ title, kept, latency, thin }) => {
  let reference;
  Object.defineProperty(window, '__referentiel', {
    configurable: true,
    get() { return reference; },
    set(value) {
      reference = value;
      if (!thin || !value || typeof value.sheetFor !== 'function') return;
      const full = value.sheetFor.bind(value);
      window.__fullSheetFor = full;
      value.sheetFor = (asked) => {
        const sheet = full(asked);
        if (!sheet || asked !== title) return sheet;
        const thinned = {};
        for (const key of kept) if (key in sheet) thinned[key] = sheet[key];
        return thinned;
      };
    },
  });
  let mocks;
  Object.defineProperty(window, '__mocks', {
    configurable: true,
    get() { return mocks; },
    set(value) {
      mocks = value;
      if (value && typeof value.setDefaultLatency === 'function') value.setDefaultLatency(latency);
    },
  });
}"""

READ = """() => {
  const screen = document.querySelector('[data-part="screen"][data-open]');
  return {
    open: !!screen,
    title: ((screen && screen.querySelector('[data-part="hero/title"]')) || {}).textContent || '',
    skeletons: screen ? screen.querySelectorAll('[data-skeleton]').length : -1,
    noInfos: screen ? [...screen.querySelectorAll('[data-part="no-info"]')].map((p) => p.textContent) : [],
    bodyChildren: ((screen && screen.querySelector('[data-region="screen-media/body"]')) || { children: [] }).children.length,
    cast: !!(screen && screen.querySelector('[data-part="cast"]')),
    synopsis: (((screen && screen.querySelector('[data-part="heading"]')) || {}).nextElementSibling || {}).textContent || '',
    inFlight: window.__mocks ? window.__mocks.inFlight() : -1,
  };
}"""


async def address_of(browser):
    """Resolves the sheet's address through the reference, on a throwaway page."""
    context, page = await open_page(browser)
    ids = await page.evaluate("(title)=>window.addressIdsFor(title)", TITLE)
    await context.close()
    return f"{PROTOTYPE}media/{ids['provider']}/{ids['id']}"


async def cold_load(browser, address, thin):
    """Opens the sheet cold with the two seams intercepted from the first byte."""
    context = await browser.new_context(**PHONE)
    await context.add_init_script(
        f"({INTERCEPT})({{ title: {TITLE!r}, kept: {KEPT!r}, "
        f"latency: {LATENCY_MILLISECONDS}, thin: {'true' if thin else 'false'} }})")
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    await page.goto(address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    waited = 0
    while waited < MOUNT_DEADLINE_MILLISECONDS:
        if await page.evaluate("""()=>!!document.querySelector('[data-part="screen"][data-open]')"""):
            break
        await page.wait_for_timeout(50)
        waited += 50
    return context, page, errors


async def main():
    journal = Journal("R119 — priming draws what the tap knew, and a skeleton for the rest")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        address = await address_of(browser)

        # ─── The thinned walk: the case the real backend produces ─────────
        context, page, errors = await cold_load(browser, address, thin=True)
        thinned = await page.evaluate("""(title)=>{
          const full = window.__fullSheetFor ? window.__fullSheetFor(title) : null;
          const thin = window.__referentiel.sheetFor(title);
          return { fullKeys: full ? Object.keys(full).length : 0,
                   thinKeys: thin ? Object.keys(thin) : null };
        }""", TITLE)
        journal.check(
            "(a) the reference is wrapped and the placeholder is THINNED — the "
            "flight has a subject",
            thinned["fullKeys"] > 6 and thinned["thinKeys"] is not None
            and set(thinned["thinKeys"]) <= set(KEPT) and "k" in thinned["thinKeys"],
            f"full sheet {thinned['fullKeys']} key(s), placeholder {thinned['thinKeys']}")
        early = await page.evaluate(READ)
        journal.check(
            "(b) while the read is out, the screen draws the title it knew, a "
            "skeleton where each unknown part will go, and NO answer about it",
            early["open"] and early["inFlight"] > 0 and TITLE in early["title"]
            and early["skeletons"] >= SKELETONS_AT_LEAST and len(early["noInfos"]) == 0,
            f"read {early}")
        early_children = early["bodyChildren"]
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(300)
        late = await page.evaluate(READ)
        journal.check(
            "(c) once the read lands the skeletons stand down and the one part "
            "the served sheet lacks is said — the trailer",
            late["inFlight"] == 0 and late["skeletons"] == 0
            and len(late["noInfos"]) == 1 and "bande-annonce" in late["noInfos"][0],
            f"read {late}")
        journal.check(
            "the body keeps the same blocks at both instants — a line stands "
            "in, a block never appears late",
            early_children > 0 and early_children == late["bodyChildren"],
            f"{early_children} block(s) in flight, {late['bodyChildren']} landed")
        journal.check("no JS error on the thinned walk", not errors, str(errors))
        await context.close()

        # ─── The control: the prototype's own COMPLETE placeholder ────────
        # NOT « zero skeletons ». The seasons have no placeholder and this
        # sheet's served creator is absent, so a few lines stand here too —
        # measured at 4 against 11. What separates the two walks is that the
        # parts the placeholder CARRIES are real content while the read is out:
        # the cast strip is drawn and the synopsis is a sentence, not a line.
        # A control that asked for zero was green over nothing and red over the
        # design working exactly as written.
        context, page, errors = await cold_load(browser, address, thin=False)
        control = await page.evaluate(READ)
        journal.check(
            "(d) the control — the complete placeholder, same latency — draws "
            "FEWER skeletons, and the parts it carries are content while the "
            "read is out",
            control["open"] and control["inFlight"] > 0
            and control["skeletons"] < early["skeletons"]
            and control["cast"] and len(control["synopsis"]) > 40,
            f"read {control} against {early['skeletons']} skeleton(s) thinned")
        journal.check("no JS error on the control walk", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())

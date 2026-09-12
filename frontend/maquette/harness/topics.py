"""R165 — a rubric is a place one ENTERS, so it is a place one can LEAVE (B-332, B-361).

Reported of Configuration — « je rentre dans une section et je peux jamais
revenir en arrière » — and found again on Maintenance (B-361). Both pages carry
rubrics — a heading and the settings or the
commands underneath — and entering one wrote the rubric into the address with
`replacePath()`, the verb D1b reserves for an ADJUSTMENT: a filter, an inner
tab, a sort. A rubric is not an adjustment. It is a screen one enters and has to
leave, which D1b rule 1 calls a deliberate ARRIVAL, and an arrival PUSHES.

Replaced, it left no entry for Back to pop, so the system Back gesture popped the
PAGE and the reader landed on `/acquisition` — two levels from where they were,
having asked for one. And neither rubric view drew a back affordance, so the only
way out was the tab bar, which is not Back.

WHAT THIS RULE READS, AND WHY IT IS THREE THINGS AND NOT ONE. Asking one of them
passes over a build that gets the other two wrong:

  · `history.length` grew by one — a rubric that pushes. A hold on this alone is
    green over a rubric that pushes and draws nothing to tap;
  · `[data-part="screen/back"]` is drawn inside the rubric — the affordance every
    screen of this interface wears. A hold on this alone is green over a button
    that pops the wrong entry;
  · and the LANDING: `history.back()` — what the system gesture calls — puts the
    reader on the page's own LIST, with the rubric closed and the page still the
    page they were on.

IT DRIVES THE REAL PATH AND NEVER A NAMED STATE. The walk is a load of the
address and a real click on a rubric row — the two gestures the operator made.
A named state would re-seed the layer into the rubric and measure a screen
nobody navigated to, which is how this defect survived every green rule the
suite had.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal

from playwright.async_api import async_playwright

# The two pages that have rubrics, and how each spells one. The rubric's own id
# is READ off the page rather than written down here: a rubric list is the
# fixture's, not this rule's, and a literal would fall the day a seed is
# reworded instead of the day the behaviour breaks.
PAGES = (
    {"address": "settings", "verb": "topic"},
    {"address": "maintenance", "verb": "maintopic"},
)

# What the reader is standing in, read the way it is SEEN: the address, how deep
# the stack is, whether a back affordance is drawn, and the heading on screen.
STANDING = """(verb)=>({
  path: location.pathname,
  query: location.search,
  depth: history.length,
  back: !!document.querySelector('[data-part="screen/back"]'),
  heading: [...document.querySelectorAll('[data-part="heading"]')]
    .map((one) => one.textContent.trim()).join(' | '),
  rubrics: [...document.querySelectorAll(`[data-${verb}]`)]
    .map((one) => one.dataset[verb]).filter(Boolean)})"""


async def open_at(browser, address):
    """Opens the prototype AT an address, past the startup screen."""
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    await page.goto(PROTOTYPE + address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(320)
    return context, page, errors


async def main():
    journal = Journal("R165 — a rubric can be left")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        for page_under_test in PAGES:
            address, verb = page_under_test["address"], page_under_test["verb"]
            context, page, errors = await open_at(browser, address)

            at_list = await page.evaluate(STANDING, verb)
            # A page offering no rubric fells this hold and stops there: the
            # walk below is a walk THROUGH a rubric, and with none to take it
            # would report a fixture's silence as a broken contract.
            if journal.check(f"« {address} » offers a rubric to enter",
                             bool(at_list["rubrics"]), str(at_list["rubrics"])):
                rubric = at_list["rubrics"][0]
                # A REAL CLICK on the row, at its own place on the screen —
                # the gesture the operator made, not a dispatched event.
                await page.click(f'[data-{verb}="{rubric}"]')
                await page.wait_for_timeout(450)
                inside = await page.evaluate(STANDING, verb)

                journal.check(
                    f"entering a « {address} » rubric PUSHES an entry, because "
                    "it is an arrival and not an adjustment (D1b rule 1)",
                    inside["depth"] == at_list["depth"] + 1,
                    f"{at_list['depth']} → {inside['depth']}")
                journal.check(
                    "and the rubric DRAWS its way back, as every screen of this "
                    "interface does",
                    inside["back"],
                    f"heading={inside['heading']!r} back={inside['back']}")
                journal.check(
                    "and it is really the rubric that is open",
                    inside["heading"] != at_list["heading"],
                    f"{at_list['heading']!r} → {inside['heading']!r}")

                # THE SYSTEM GESTURE ITSELF. `history.back()` is what the
                # phone's back gesture and the browser's own control call, and
                # it is what read false on the operator's device.
                await page.evaluate("()=>history.back()")
                await page.wait_for_timeout(500)
                left = await page.evaluate(STANDING, verb)
                journal.check(
                    "and Back lands on the page's OWN list, not on another page",
                    left["path"] == "/" + address,
                    f"{left['path']}{left['query']}")
                journal.check(
                    "with the rubric closed and its list drawn again",
                    not left["back"] and bool(left["rubrics"])
                    and left["heading"] == at_list["heading"],
                    f"back={left['back']} rubrics={len(left['rubrics'])} "
                    f"heading={left['heading']!r}")

            await context.close()

            # AND THE DRAWN AFFORDANCE POPS THE SAME ENTRY. A back button that
            # navigated by address instead of popping would pass every hold
            # above and leave the stack one entry deeper on each visit.
            #
            # ON A FRESH CONTEXT, because the walk above ended wherever the
            # build under test decided to land: re-using it would measure the
            # repair from a starting point the defect chose.
            context, page, errors = await open_at(browser, address)
            fresh = await page.evaluate(STANDING, verb)
            if fresh["rubrics"]:
                await page.click(f'[data-{verb}="{fresh["rubrics"][0]}"]')
                await page.wait_for_timeout(450)
                entered = await page.evaluate(STANDING, verb)
                affordance = await page.query_selector('[data-part="screen/back"]')
                if affordance is not None:
                    await affordance.click()
                    await page.wait_for_timeout(500)
                by_affordance = await page.evaluate(STANDING, verb)
                # `history.length` NEVER SHRINKS — a back leaves the entries it
                # steps off reachable, which is what makes a forward possible —
                # so « did this POP » is not a smaller number. It is a number
                # that did not GROW, plus an entry still in front: a button that
                # navigated to the list would have pushed a sixth entry and
                # left nothing to step forward onto.
                await page.evaluate("()=>history.forward()")
                await page.wait_for_timeout(500)
                forward = await page.evaluate(STANDING, verb)
                journal.check(
                    "and the drawn back POPS rather than navigates — nothing is "
                    "stacked, and the rubric is still one step FORWARD",
                    affordance is not None
                    and by_affordance["depth"] == entered["depth"]
                    and by_affordance["path"] == "/" + address
                    and not by_affordance["back"]
                    and forward["back"],
                    f"depth {entered['depth']} → {by_affordance['depth']} at "
                    f"{by_affordance['path']} back={by_affordance['back']}, "
                    f"forward back={forward['back']}")

            journal.check(f"no JS error walking « {address} »'s rubrics",
                          not errors, str(errors))
            await context.close()

        await browser.close()
    journal.summary()


asyncio.run(main())

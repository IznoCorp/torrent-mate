"""R260 — « Trackers » is a page of the bottom bar, between Médiathèque and Découvrir.

Organisation ruling 20 gives the bar four places: Acquisition, Médiathèque,
Trackers, Découvrir — Trackers INSERTED before Découvrir, never appended after a
free slot. Its place and its address are read off the navigation table and the
address model, never written here; its body is its own oracle region,
`trackers/body`.

1. the table marks the page `inBar`, third of the bar, between `lib` and
   `discover`, and the address model declares its address;
2. walked by a finger from Médiathèque, a tap on its button lands on its
   address and draws its body — and REPLACES the entry rather than stacking one,
   as every change of bar page does (§ 16 point 2): `history.length` unchanged;
3. the bar then draws four buttons, each a quarter of its width;
4. the address opened cold lands on the same page;
5. its two tabs, « Torrents » then « Trackers », are DIALS of the page: « Trackers »
   is selected when the address names none; a finger's tap on the other ADJUSTS —
   the address says `?list=`, `history.length` unchanged — and a back then leaves
   the page for the one beneath it rather than stepping between tabs;
6. the address carries both dials: `?list=torrents&tracker=<name>` opened cold
   lands on that tab, filtered to that tracker.

Red before the move: no such page exists. RE-AIMED OUT LOUD: holds 5 and 6 came
with the page's tabs, red on the page that had none.
"""
import asyncio
import json
import pathlib
import re

from common import ACTED, HOME_PAGE, PAGE_PATHS, PHONE, PROTOTYPE, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TABLE = (SOURCE / "app/navigation.ts").read_text(encoding="utf-8")
IN_BAR = [identifier for identifier, flag
          in re.findall(r'\bid: "([^"]+)",.*?\binBar: (true|false)', TABLE, re.S) if flag == "true"]
PAGE = "trackers"
# The pages it stands between, by ruling 20.
BEFORE = "lib"
AFTER = "discover"
# The state the finger walk starts from: Médiathèque, drawn.
START = "lib-grid"
# A width a quarter may miss by: sub-pixel layout, never a missing button.
TOLERANCE = 1.5

DRAWN = """() => ({
  page: window.state?.page ?? null,
  where: location.pathname,
  body: !!document.querySelector('#view [data-part="trackers"]'),
  length: history.length,
})"""

TABS = """() => ({
  tabs: [...document.querySelectorAll('#view [role="tablist"] [data-trackers-tab]')]
    .map(tab => ({tab: tab.dataset.trackersTab, selected: tab.getAttribute('aria-selected') === 'true'})),
  dial: window.state?.trackersTab ?? null,
  filter: window.state?.trackersFilter ?? null,
  address: location.pathname + location.search,
  length: history.length,
})"""
# The tabs in the operator's order (organisation ruling 19), and the one a bare
# address opens (OPEN 4, ruled C).
ORDER = ["torrents", "trackers"]
FIRST = "trackers"
OTHER = "torrents"
# A tracker the configuration declares, read off the seed the page reads.
FILTERED = json.loads((SOURCE / "mocks/seeds/trackers.json").read_text(encoding="utf-8"))[0]["name"]

BAR = """() => [...document.querySelectorAll('#nav button[data-page]')]
  .map(button => ({page: button.dataset.page, width: button.getBoundingClientRect().width}))"""


async def main():
    journal = Journal("R260 — « Trackers » is a bar page between Médiathèque and Découvrir")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        placed = (PAGE in IN_BAR and BEFORE in IN_BAR and AFTER in IN_BAR
                  and IN_BAR.index(BEFORE) + 1 == IN_BAR.index(PAGE) == IN_BAR.index(AFTER) - 1)
        journal.check("the table puts « Trackers » in the bar, between Médiathèque and Découvrir",
                      placed, str(IN_BAR))
        journal.check("and the address model declares its address", PAGE in PAGE_PATHS, str(PAGE_PATHS))

        answer = await page.evaluate(
            f"()=>{{try{{window.__go('{START}');return null}}catch(error){{return String(error)}}}}")
        journal.check(f"the named state {START} exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        before = await page.evaluate(DRAWN)
        button = f'#nav button[data-page="{PAGE}"]'
        present = await page.locator(button).count() == 1
        journal.check("the bar carries its button", present, f"{await page.evaluate(BAR)}")
        if present:
            await page.tap(button)
            await page.wait_for_timeout(ACTED)
        after = await page.evaluate(DRAWN)
        journal.check("a finger's tap from Médiathèque lands on its address, its body drawn",
                      after["page"] == PAGE and after["where"] == PAGE_PATHS.get(PAGE) and after["body"],
                      str(after))
        journal.check("and the change of page REPLACES the entry — history.length unchanged",
                      present and after["length"] == before["length"],
                      f"history.length {before['length']} -> {after['length']}")

        strip = await page.evaluate(TABS)
        journal.check("its strip draws « Torrents » then « Trackers », « Trackers » selected on a bare address",
                      [entry["tab"] for entry in strip["tabs"]] == ORDER
                      and [entry["tab"] for entry in strip["tabs"] if entry["selected"]] == [FIRST]
                      and strip["dial"] == FIRST, str(strip))
        other = f'#view [data-trackers-tab="{OTHER}"]'
        if await page.locator(other).count() == 1:
            await page.tap(other)
            await page.wait_for_timeout(ACTED)
        switched = await page.evaluate(TABS)
        journal.check("a finger's tap on « Torrents » ADJUSTS: the address names it, history.length unchanged",
                      switched["dial"] == OTHER and switched["address"] == f"{PAGE_PATHS.get(PAGE)}?list={OTHER}"
                      and switched["length"] == strip["length"] and after["length"] == strip["length"],
                      f"{strip} -> {switched}")
        # FROM THE ENTRY PAGE the page is PUSHED, so what lies beneath it is
        # known: Acquisition. A back after the tabs moved must land there.
        for step in ("acq", PAGE):
            await page.tap(f'#nav button[data-page="{step}"]')
            await page.wait_for_timeout(ACTED)
        if await page.locator(other).count() == 1:
            await page.tap(other)
            await page.wait_for_timeout(ACTED)
        await page.go_back()
        await page.wait_for_timeout(ACTED)
        back = await page.evaluate(DRAWN)
        journal.check("and a back then leaves the page for the one beneath it, never a step between tabs",
                      back["page"] == HOME_PAGE, str(back))

        bar = await page.evaluate(BAR)
        total = sum(entry["width"] for entry in bar)
        quarters = len(bar) == 4 and all(abs(entry["width"] - total / 4) <= TOLERANCE for entry in bar)
        journal.check("the bar draws four buttons, each a quarter of it", quarters, str(bar))

        cold = await browser.new_context(**PHONE)
        fresh = await cold.new_page()
        fresh.on("pageerror", lambda error: errors.append(str(error)))
        await fresh.goto(PROTOTYPE.rstrip("/") + PAGE_PATHS.get(PAGE, "/trackers"), wait_until="load")
        await fresh.evaluate("()=>window.__loadingDone?.()")
        await fresh.wait_for_timeout(SETTLED)
        opened = await fresh.evaluate(DRAWN)
        journal.check("its address opened cold lands on the page",
                      opened["page"] == PAGE and opened["body"], str(opened))
        filtered_context = await browser.new_context(**PHONE)
        filtered = await filtered_context.new_page()
        filtered.on("pageerror", lambda error: errors.append(str(error)))
        address = f"{PAGE_PATHS.get(PAGE, '/trackers')}?list={OTHER}&tracker={FILTERED}"
        await filtered.goto(PROTOTYPE.rstrip("/") + address, wait_until="load")
        await filtered.evaluate("()=>window.__loadingDone?.()")
        await filtered.wait_for_timeout(SETTLED)
        dials = await filtered.evaluate(TABS)
        journal.check("the address carries both dials: its tab and its tracker, opened cold",
                      dials["dial"] == OTHER and dials["filter"] == FILTERED and dials["address"] == address,
                      str(dials))
        await filtered_context.close()
        await cold.close()

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

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
4. the address opened cold lands on the same page.

Red before the move: no such page exists.
"""
import asyncio
import pathlib
import re

from common import ACTED, PAGE_PATHS, PHONE, PROTOTYPE, SETTLED, Journal, open_page
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
        await cold.close()

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

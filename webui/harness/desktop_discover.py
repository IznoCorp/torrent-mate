"""R484 — Découvrir on a desktop: the deck a 2:3 poster, centred; the posters by the tile (phase 5).

The operator, 2026-10-01 — DECIDED 5 = B: « the deck card keeps a 2:3 poster, centred » and the gallery's
columns follow the tile's width. `docs/features/maquette-desktop/DESIGN.md` § 1.3: the deck drew ONE card
1 250 × 640 at 1280 — a portrait poster cropped into a landscape — and its swipe was a 1 250 px drag.

WHAT IS READ, out of the harness's phone frame, at 1024, 1280 and 1440:

  1. the deck's pile is a 2:3 portrait, centred in the page, as tall as the deck measures;
  2. the top card is swiped away by the mouse, as on a phone by the thumb;
  3. the posters' gallery has the columns its width asks;
  4. at 390 the pile keeps the phone's width (the page's), not a 2:3 box.
"""
import asyncio

from common import PHONE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from desktop_library import GRID, expected
from playwright.async_api import async_playwright

OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"
TOP = '[data-part="deck/card"][data-depth="0"]'


def desktop(width):
    """A desktop window of WIDTH, out of the frame, pointer only."""
    return {**PHONE, "viewport": {"width": width, "height": 800}, "is_mobile": False, "has_touch": False,
            "device_scale_factor": 1}


PILE = """() => {
  const pile = document.querySelector('#view .deck');
  if (!pile) return null;
  const p = pile.getBoundingClientRect(), port = document.querySelector('#port').getBoundingClientRect();
  return {ratio: +(p.width / p.height).toFixed(3), height: Math.round(p.height), width: Math.round(p.width),
          off: Math.round(Math.abs((p.left + p.right) / 2 - (port.left + port.right) / 2)), port: Math.round(port.width)};
}"""

TITLE = f"() => document.querySelector('{TOP} [data-part=\"deck/title\"]')?.textContent ?? ''"


async def swipe(page, dx):
    """Drags the top card DX px with the mouse; answers the top card's title after it."""
    box = await page.locator(TOP).first.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    await page.mouse.move(x, y)
    await page.mouse.down()
    for i in range(1, 9):
        await page.mouse.move(x + dx * i / 8, y)
        await page.wait_for_timeout(16)
    await page.mouse.up()
    await page.wait_for_timeout(700)
    return await page.evaluate(TITLE)


async def main():
    journal = Journal("R484 — Découvrir on a desktop: the deck a 2:3 poster, centred; the posters by the tile")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        for width in (1024, 1280, 1440):
            context, page = await open_page(browser, **desktop(width))
            await context.add_init_script(OUT_OF_FRAME)
            await page.reload(wait_until="load")
            await page.evaluate("()=>window.__loadingDone?.()")
            page.on("pageerror", lambda error: errors.append(str(error)))
            seen = await read_at(page, "discover-deck", PILE)
            journal.check(f"{width}: the deck a 2:3 portrait, centred, as tall as it measures",
                          seen is not None and abs(seen["ratio"] - 2 / 3) <= 0.02 and seen["off"] <= 2
                          and seen["height"] >= 340, f"{seen}")
            before = await page.evaluate(TITLE)
            after = await swipe(page, -min(220, seen["width"] // 2) if seen else -180)
            journal.check(f"{width}: the mouse swipes the top card away", before and after != before,
                          f"« {before[:24]} » → « {after[:24]} »")
            seen = await read_at(page, "discover-posters", GRID)
            journal.check(f"{width}: the posters have the columns their width asks",
                          seen is not None and seen["columns"] == expected(seen["port"]), f"{seen}")
            await context.close()

        context, page = await open_page(browser)
        seen = await read_at(page, "discover-deck", PILE)
        journal.check("390: the pile keeps the page's width, not a 2:3 box",
                      seen is not None and seen["width"] >= seen["port"] - 40, f"{seen}")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

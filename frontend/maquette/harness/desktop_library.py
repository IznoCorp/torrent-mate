"""R483 — the Médiathèque on a desktop: columns by the tile's width, the selection bar in the column (phase 4).

The operator, 2026-10-01 — DECIDED 5 = B: « gallery columns by tile width (7 at ≈ 1 100 px, 8 at ≈ 1 300) »;
DECIDED 7 = B: « + » and the selection bar bounded to the column. `docs/features/maquette-desktop/DESIGN.md`
§ 1.3: the grid stopped at six columns, its tiles grew to ≈ 227 px at 1440, and in a selection « Annuler »
sat at x 110 and « Supprimer » at x 1 180.

WHAT IS READ, out of the harness's phone frame:

  1. the library's grid and the follows' grid at 1024, 1280 and 1440, the menu open, and at 1440 the menu
     folded: as many columns as the gallery's width asks (5 from 620 px, 6 from 820, 7 from 1 100, 8 from
     1 300), never a tile wider than 200 px;
  2. in a selection, the bar no wider than the column and centred on the content, its two actions in it;
  3. at 390 the grid keeps its three columns and the bar the window's width.
"""
import asyncio

from common import PHONE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

COLUMN = 760
TILE_MAX = 200
OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"
FOLDED = "try{localStorage.setItem('tm-rail','collapsed')}catch(e){}"


def desktop(width):
    """A desktop window of WIDTH, out of the frame, pointer only."""
    return {**PHONE, "viewport": {"width": width, "height": 800}, "is_mobile": False, "has_touch": False,
            "device_scale_factor": 1}


GRID = """() => {
  const grid = document.querySelector('#view .gallery');
  if (!grid) return null;
  const tiles = [...grid.children].map((t) => t.getBoundingClientRect()).filter((r) => r.width > 0);
  const top = tiles.length ? tiles[0].top : 0;
  return {port: Math.round(document.querySelector('#port').getBoundingClientRect().width),
          columns: tiles.filter((r) => Math.abs(r.top - top) < 2).length,
          tile: Math.round(tiles[0]?.width ?? 0)};
}"""

BAR = """() => {
  const bar = document.querySelector('[data-part="selection/bar"]');
  if (!bar) return null;
  const b = bar.getBoundingClientRect(), menu = document.querySelector('#drawer').getBoundingClientRect();
  const content = getComputedStyle(document.documentElement).getPropertyValue('--tm-desk').trim() === '1' ? menu.right : 0;
  const centre = (content + innerWidth) / 2;
  const actions = [...bar.querySelectorAll('button')].map((x) => x.getBoundingClientRect()).filter((r) => r.width > 0);
  return {width: Math.round(b.width), off: Math.round(Math.abs((b.left + b.right) / 2 - centre)),
          inside: actions.length >= 2 && actions.every((r) => r.left >= b.left - 1 && r.right <= b.right + 1)};
}"""


def expected(port):
    """The columns the tile grid's container steps give a gallery PORT px wide."""
    return 8 if port >= 1300 else 7 if port >= 1100 else 6 if port >= 820 else 5 if port >= 620 else 4 if port >= 460 else 3


async def main():
    journal = Journal("R483 — the Médiathèque on a desktop: columns by the tile, the selection bar in the column")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        for width, folded in ((1024, False), (1280, False), (1440, False), (1440, True)):
            context, page = await open_page(browser, **desktop(width))
            await context.add_init_script(OUT_OF_FRAME + (FOLDED if folded else ""))
            await page.reload(wait_until="load")
            await page.evaluate("()=>window.__loadingDone?.()")
            page.on("pageerror", lambda error: errors.append(str(error)))
            label = f"{width}{' folded' if folded else ''}"
            for state in ("lib-grid", "acq-follows-grid"):
                seen = await read_at(page, state, GRID)
                journal.check(f"{label} {state}: the columns the gallery's width asks, no tile over {TILE_MAX} px",
                              seen is not None and seen["columns"] == expected(seen["port"]) and seen["tile"] <= TILE_MAX,
                              f"{seen} (expected {expected(seen['port']) if seen else '?'})")
            if not folded:
                seen = await read_at(page, "lib-selection", BAR)
                journal.check(f"{label}: the selection bar within the column, centred, its actions in it",
                              seen is not None and seen["width"] <= COLUMN + 1 and seen["off"] <= 2 and seen["inside"],
                              f"{seen}")
            await context.close()

        context, page = await open_page(browser)
        grid = await read_at(page, "lib-grid", GRID)
        bar = await read_at(page, "lib-selection", BAR)
        journal.check("390: three columns, and the selection bar the window's width",
                      grid["columns"] == 3 and bar["width"] == 390, f"{grid} {bar}")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

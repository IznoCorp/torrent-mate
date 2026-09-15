"""R198 — the library's kind chips scroll without showing a scrollbar (B-336).

WHAT THE OPERATOR SAW. The « Tout · Films · Séries … » strip of the library drew
a scrollbar under its chips on the phone. The chips are the affordance: a strip
of them is the one place a bar is hidden, and it must still scroll.

WHAT IT READS, at the phone width and at the operator's own 369 px:

  k1. THE STRIP OVERFLOWS AND SCROLLS: its content is wider than its box, and a
      horizontal wheel over it moves it — so every chip stays reachable, and
      the two holds below are not read on a strip with nothing to hide.
  k2. ITS COMPUTED `scrollbar-width` IS `none` — the computed value, because a
      declaration the cascade defeats is a declaration nobody sees: the
      stylesheet's global `* { scrollbar-width: thin }` is unlayered and beats
      any layered utility, whatever its specificity.

AND THE SHEET'S CAST STRIP, the one other strip that wears the same idiom and
was defeated by the same unlayered rule: at the phone width it overflows and
scrolls, and its computed `scrollbar-width` is `none` too.

NO HOLD READS A DRAWN BAR'S HEIGHT, and that is measured, not skipped. The
strip's `offsetHeight - clientHeight` read 0 over the defect at both widths and
on a desktop pointer too: the headless browser this harness runs paints overlay
bars, which take no height, so that hold could never fall. And the computed
`scrollbar-width` is the reading that decides: a browser that honours it
ignores `::-webkit-scrollbar` entirely once it is not `auto`.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

LIBRARY_STATE = "lib-grid"
# (label, context overrides): the phone at its width, then at the operator's.
READINGS = (
    ("at 390 px", {"viewport": {"width": 390, "height": PHONE["viewport"]["height"]}}),
    ("at 369 px", {"viewport": {"width": 369, "height": PHONE["viewport"]["height"]}}),
)
STRIP = '[data-part="pill/list"]'
SHEET_STATE = "mediasheet-movie"
CAST = '[data-part="cast"]'

READ = """(selector)=>{
  const strip = document.querySelector(selector);
  if (!strip) return null;
  const style = getComputedStyle(strip);
  const box = strip.getBoundingClientRect();
  return {
    scrollWidth: strip.scrollWidth, clientWidth: strip.clientWidth,
    scrollLeft: strip.scrollLeft,
    scrollbarWidth: style.scrollbarWidth,
    x: box.left + box.width / 2, y: box.top + box.height / 2,
    chips: strip.querySelectorAll('[data-cat]').length,
  };
}"""


async def main():
    """Reads the strip in each context."""
    journal = Journal("R198 — the kind chips scroll without showing a scrollbar")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        for label, options in READINGS:
            context, page = await open_page(browser, **options)
            await page.evaluate("(id)=>window.__go(id)", LIBRARY_STATE)
            await page.wait_for_timeout(SETTLED)
            before = await page.evaluate(READ, STRIP)
            moved = None
            if before is not None:
                await page.mouse.move(before["x"], before["y"])
                await page.mouse.wheel(120, 0)
                await page.wait_for_timeout(SETTLED)
                moved = await page.evaluate(READ, STRIP)
            journal.check(f"{label} the strip overflows and a horizontal wheel moves it",
                          before is not None and before["scrollWidth"] > before["clientWidth"]
                          and moved is not None and moved["scrollLeft"] > before["scrollLeft"],
                          f"before {before}, after {moved}")
            journal.check(f"{label} its scrollbar-width is none",
                          before is not None and before["scrollbarWidth"] == "none",
                          f"scrollbar-width {(before or {}).get('scrollbarWidth')}")
            await context.close()
        context, page = await open_page(browser)
        await page.evaluate("(id)=>window.__go(id)", SHEET_STATE)
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("(selector)=>document.querySelector(selector)?.scrollIntoView({block: 'center'})", CAST)
        await page.wait_for_timeout(SETTLED)
        cast = await page.evaluate(READ, CAST)
        moved = None
        if cast is not None:
            await page.mouse.move(cast["x"], cast["y"])
            await page.mouse.wheel(120, 0)
            await page.wait_for_timeout(SETTLED)
            moved = await page.evaluate(READ, CAST)
        journal.check("the sheet's cast strip overflows and a horizontal wheel moves it",
                      cast is not None and cast["scrollWidth"] > cast["clientWidth"]
                      and moved is not None and moved["scrollLeft"] > cast["scrollLeft"],
                      f"before {cast}, after {moved}")
        journal.check("the sheet's cast strip computes scrollbar-width none",
                      cast is not None and cast["scrollbarWidth"] == "none",
                      f"scrollbar-width {(cast or {}).get('scrollbarWidth')}")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

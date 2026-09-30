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

R-conformity-s — THE CATEGORY PILLS ON EVERY LENS (`hold_lens_pills`, in its own
context): « Récents » and « Incomplets » draw the pills, and a pressed pill
filters and counts what is drawn. On « Récents », EVERY pill counts the rows
the lens holds in its category, never the library (the reader of the train,
2026-09-30: « Tout 1861 · Films 717 … » over 24 drawn) — its list is windowed,
so the rows it holds are read from the window's own count, pill by pill.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, ROOT, SETTLED, Journal, open_page, read_at, chrome_launch_args

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
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
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
        await hold_lens_pills(browser, journal)
        await browser.close()
    journal.summary()


MOVIE_CATEGORY = "movies"
LENS = """()=>{
  const view = document.querySelector('#view');
  const pills = [...view.querySelectorAll('[data-part="pill"][data-cat]')];
  const pressed = pills.filter((pill) => pill.getAttribute('aria-pressed') === 'true');
  const body = view.querySelector('[data-part="surface/body"]');
  // A skeleton stands for a row still loading; it is not a row drawn.
  const rows = body ? [...body.querySelectorAll('[data-part="tile"], [data-part="card"]')]
    .filter((row) => !row.hasAttribute('data-skeleton')) : [];
  return {
    pills: pills.length,
    pressed: pressed.map((pill) => pill.dataset.cat),
    figure: pressed.length === 1 ? Number(pressed[0].lastElementChild?.textContent ?? NaN) : null,
    titles: rows.map((row) => (row.querySelector('[data-part="tile/title"], [data-part="card/title"]')
      ?.textContent ?? '').trim()),
    empty: !!body?.querySelector('[data-part="empty-state"]'),
    // A WINDOWED list draws only what is in view; the rows it holds are its count.
    held: Number(body?.querySelector('[data-virtualised]')?.dataset.virtualised ?? 0),
  };
}"""

# EVERY PILL'S FIGURE, then pressed one after the other with the rows the lens
# holds under it.
PILL_FIGURES = """()=>[...document.querySelectorAll('#view [data-part="pill"][data-cat]')]
  .map((pill) => ({cat: pill.dataset.cat, figure: Number(pill.lastElementChild?.textContent ?? NaN)}))"""


async def hold_lens_pills(browser, journal):
    """R-conformity-s — the category pills on every lens.

    « Récents » and « Incomplets » draw the pills with one pressed; « Films »
    pressed draws films only; the pressed pill counts the rows drawn, and a
    lens with nothing in its category says it is empty.

    Args:
        browser: The launched browser; the holds read a context of their own.
        journal: The rule's journal.
    """
    items = json.loads((ROOT / "design" / "src" / "mocks" / "seeds" / "library-items.json").read_text(encoding="utf-8"))
    movies = {item["title"] for item in items if item.get("category") == MOVIE_CATEGORY}
    context, page = await open_page(browser)
    for state in ("lib-recent", "lib-incomplete"):
        seen = await read_at(page, state, LENS)
        journal.check(f"{state}: the pills are drawn, one of them pressed",
                      seen["pills"] >= 2 and len(seen["pressed"]) == 1, f"{seen}")
    seen = await read_at(page, "lib-recent-movies", LENS)
    journal.check("lib-recent-movies: « Films » is pressed, and every title drawn is a film",
                  seen["pressed"] == [MOVIE_CATEGORY] and bool(seen["titles"])
                  and all(title in movies for title in seen["titles"]),
                  f"pressed {seen['pressed']}; not movies: "
                  f"{[title for title in seen['titles'] if title not in movies][:3]} of {len(seen['titles'])}")
    # THE FIGURE AND THE ROWS ARE READ IN ONE BREATH: a pill that leaves the
    # list short lets it ask for its next page, and both grow together.
    figures = await read_at(page, "lib-recent", PILL_FIGURES)
    unequal = []
    for one in figures:
        await page.evaluate(
            """(cat)=>document.querySelector(`#view [data-part="pill"][data-cat="${cat}"]`)?.click()""", one["cat"])
        await page.wait_for_timeout(SETTLED)
        seen = await page.evaluate(LENS)
        if seen["pressed"] != [one["cat"]] or seen["figure"] != seen["held"]:
            unequal.append({"cat": one["cat"], "figure": seen["figure"], "rows": seen["held"]})
    journal.check("lib-recent: every pill counts the rows the lens holds in its category",
                  len(figures) >= 2 and not unequal, f"{unequal[:3]} of {len(figures)} pills")
    for state, empty in (("lib-incomplete", False), ("lib-incomplete-movies", True)):
        seen = await read_at(page, state, LENS)
        journal.check(f"{state}: the pressed pill counts the rows drawn",
                      seen["figure"] == len(seen["titles"]) and bool(seen["titles"]) != empty,
                      f"figure {seen['figure']} for {len(seen['titles'])} rows")
        if empty:
            journal.check(f"{state}: and the lens says it is empty", seen["empty"], f"{seen}")
    await context.close()


if __name__ == "__main__":
    asyncio.run(main())

"""R413 — the desktop stays fully functional (L24, DOIT-9, OPEN 6 = A), on the desktop arrangements.

The operator, 2026-09-29: « A dans un premier temps, mais prévoir une phase
final d'adaptation des écrans pour une utilisation plus agréable sur desktop ».
L24 owed the PROOF only; the adaptation is the desktop milestone
(`docs/features/maquette-desktop/DESIGN.md`), and this rule is re-aimed at what
it drew (phase 10): the menu PINNED beside the content (DECIDED 2, 2026-10-01,
amending Q1 of 2026-08-30 « the drawer alone, at every width »), the burger
gone, the reading column, the side sheet.

WHAT IS READ, at 1024, 1280 and 1440 × 800 with a pointer and no touch, the
harness's phone frame taken off through its own switch (R140):

  1. every named state draws content (text, pictures, or a skeleton that says « not yet »),
     with no horizontal overflow of the document;
  2. no JS error across the walk;
  3. the gallery widens: the library grid is wider at 1280 than at 390;
  4. the burger is not drawn, and every page the pinned menu lists is reached by
     ONE pointer click on its entry — the menu open, then folded to its icons.
"""
import asyncio

from common import PHONE, SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import Error as PlaywrightError, async_playwright

WIDTHS = (1024, 1280, 1440)
SETTLE = 320


def desktop(width):
    """A desktop window of WIDTH, pointer only."""
    return {"viewport": {"width": width, "height": 800}, "is_mobile": False, "has_touch": False}


TOGGLE = "() => document.querySelector('[data-part=\"shell/rail-toggle\"]')?.click()"
BURGER = "() => { const b = document.querySelector('[data-part=\"shell/header\"] [data-drawer]'); return b ? b.getBoundingClientRect().width : 0; }"

UNFRAME = "() => { const box = document.querySelector('#desktop-switch'); if (box && !box.checked) box.click(); return !!box?.checked; }"

READ = """() => {
  const dialog = document.querySelector('#dlg[data-open]'), sheet = document.querySelector('#sheet[data-open]');
  const route = document.querySelector('[data-part="screen"][data-open][data-key]');
  const target = dialog ?? sheet ?? route ?? document.querySelector('#view');
  return {text: target?.textContent.replace(/\\s+/g, ' ').trim().length ?? 0,
          skeletons: target?.querySelectorAll('[data-skeleton]').length ?? 0,
          pictures: target?.querySelectorAll('img').length ?? 0,
          overflow: document.documentElement.scrollWidth - window.innerWidth};
}"""

GRID = "() => document.querySelector('#view [data-part=\"grid\"]')?.getBoundingClientRect().width ?? 0"


async def reach_every_page(page, journal, label):
    """Every entry of the pinned menu, clicked once with the pointer, lands on its page."""
    await read_at(page, "lib-grid", "() => true")
    journal.check(f"{label}: the burger is not drawn — the menu is pinned", await page.evaluate(BURGER) == 0)
    entries = await page.evaluate("() => [...document.querySelectorAll('#drawer [data-navgo]:not([data-reserved])')].map((one) => one.dataset.navgo)")
    missed = []
    for entry in entries:
        try:
            await page.click(f'#drawer [data-navgo="{entry}"]', timeout=2000)
        except PlaywrightError as error:
            missed.append(f"{entry}: no pointer reaches it ({str(error).splitlines()[0]})")
            continue
        await page.wait_for_timeout(SETTLED)
        landed = await page.evaluate("() => state.page")
        if landed != entry:
            missed.append(f"{entry} → {landed}")
    journal.check(f"{label}: every page the pinned menu lists is one pointer click away",
                  entries and missed == [], f"{len(entries)} entries; missed {missed}")


async def walk(browser, width, journal):
    """Every named state at WIDTH, then the menu's pages, open and folded."""
    context, page = await open_page(browser, **{**PHONE, **desktop(width)})
    errors = []
    page.on("pageerror", lambda error: errors.append(f"{width}: {error}"))
    journal.check(f"{width}: the phone frame is taken off through the harness's switch", await page.evaluate(UNFRAME))

    states = await page.evaluate("() => window.__states()")
    bad = []
    for state in states:
        await page.evaluate("(id) => window.__go(id)", state)
        await page.evaluate(UNFRAME)
        await page.wait_for_timeout(SETTLE)
        seen = await page.evaluate(READ)
        if not ((seen["text"] > 60 or seen["skeletons"] > 0 or seen["pictures"] > 0) and seen["overflow"] <= 0):
            bad.append(f"{state} {seen}")
    journal.check(f"every named state at {width}: content, no horizontal overflow ({len(states)} states)",
                  bad == [], "\n      ".join(bad[:15]))

    wide = await read_at(page, "lib-grid", GRID)
    await reach_every_page(page, journal, f"{width}, open")
    await page.evaluate(TOGGLE)
    await page.wait_for_timeout(SETTLED)
    await reach_every_page(page, journal, f"{width}, folded")
    await page.evaluate(TOGGLE)
    await context.close()
    return wide, errors


async def main():
    journal = Journal("R413 — the desktop stays fully functional, on the desktop arrangements")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        phone, small = await open_page(browser)
        narrow = await read_at(small, "lib-grid", GRID)
        await phone.close()

        # The three widths walk side by side: 319 states each, one after the other, would not fit
        # the run's per-rule bound.
        results = await asyncio.gather(*(walk(browser, width, journal) for width in WIDTHS))
        wide = dict(zip(WIDTHS, (r[0] for r in results)))[1280]
        journal.check("the library's gallery widens with the window", wide > narrow > 0,
                      f"390: {narrow:.0f}px, 1280: {wide:.0f}px")
        await browser.close()
    journal.summary([error for r in results for error in r[1]])


if __name__ == "__main__":
    asyncio.run(main())

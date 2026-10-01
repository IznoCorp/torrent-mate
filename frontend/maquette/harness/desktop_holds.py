"""R413 — the desktop stays fully functional (L24, DOIT-9, OPEN 6 = A).

The operator, 2026-09-29: « A dans un premier temps, mais prévoir une phase
final d'adaptation des écrans pour une utilisation plus agréable sur desktop ».
L24 owes the PROOF only — no desktop layout is drawn here; that adaptation is a
milestone after the drawn lots. Navigation stays the drawer alone, at every
width (Q1, 2026-08-30).

WHAT IS READ, at 1280 × 800 with a pointer and no touch, the harness's phone
frame taken off through its own switch (R140):

  1. every named state draws content (text, pictures, or a skeleton that says « not yet »),
     with no horizontal overflow of the document;
  2. no JS error across the walk;
  3. the gallery widens: the library grid is wider at 1280 than at 390;
  4. every page the drawer lists is reached through the drawer.
"""
import asyncio

from common import PHONE, SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

DESKTOP = {"viewport": {"width": 1280, "height": 800}, "is_mobile": False, "has_touch": False}
SETTLE = 320

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


async def main():
    journal = Journal("R413 — the desktop stays fully functional")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        phone, small = await open_page(browser)
        narrow = await read_at(small, "lib-grid", GRID)
        await phone.close()

        context, page = await open_page(browser, **{**PHONE, **DESKTOP})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        journal.check("the phone frame is taken off through the harness's switch", await page.evaluate(UNFRAME))

        states = await page.evaluate("() => window.__states()")
        bad = []
        for state in states:
            await page.evaluate("(id) => window.__go(id)", state)
            await page.evaluate(UNFRAME)
            await page.wait_for_timeout(SETTLE)
            seen = await page.evaluate(READ)
            if not ((seen["text"] > 60 or seen["skeletons"] > 0 or seen["pictures"] > 0) and seen["overflow"] <= 0):
                bad.append(f"{state} {seen}")
        journal.check(f"every named state at 1280: content, no horizontal overflow ({len(states)} states)",
                      bad == [], "\n      ".join(bad[:15]))

        wide = await read_at(page, "lib-grid", GRID)
        journal.check("the library's gallery widens with the window", wide > narrow > 0,
                      f"390: {narrow:.0f}px, 1280: {wide:.0f}px")

        await read_at(page, "lib-grid", "() => true")
        entries = await page.evaluate("() => [...document.querySelectorAll('#drawer [data-navgo]')].map((one) => one.dataset.navgo)")
        missed = []
        for entry in entries:
            await page.evaluate("() => document.querySelector('[data-drawer]')?.click()")
            await page.wait_for_timeout(SETTLED)
            await page.evaluate("(go) => document.querySelector(`#drawer [data-navgo=\"${go}\"]`)?.click()", entry)
            await page.wait_for_timeout(SETTLED)
            landed = await page.evaluate("() => state.page")
            if landed != entry:
                missed.append(f"{entry} → {landed}")
        journal.check("every page the drawer lists is reached through the drawer",
                      entries and missed == [], f"{len(entries)} entries; missed {missed}")

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

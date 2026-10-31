"""R481 — on a desktop the panel is a side sheet on the right (desktop milestone, phase 2).

The operator, 2026-10-01 — DECIDED 3 = C, with his precision « latérale droit du coup le panneau sur
desktop (pas gauche côté menu) »: the bottom sheet opens as a side sheet on the RIGHT edge, opposite
the menu, ≈ 440 px, full height; drag-to-close horizontal; Escape and the scrim unchanged.
`docs/features/maquette-desktop/DESIGN.md` § 3.

WHAT IS READ, out of the harness's phone frame, with a pointer and no touch:

  1. at 1280, every named state that opens the sheet, and at 1024 and 1440 a subset: the sheet against
     the window's right edge, top to bottom, no wider than 440 px, the page readable beside it (the
     port starts left of the sheet) and the menu on the other side;
  2. the mouse closes it by dragging its edge to the right; a short drag puts it back;
  3. Escape and the scrim close it, as on a phone;
  4. the phone is untouched: at 390 the same panel rises from the bottom edge, as wide as the window.
"""
import asyncio

from common import PANEL_IN, PHONE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

SIDE = 440
SETTLE = 320
SAMPLE = ("lib-film-panel", "sheet-journey", "followsheet-gaps", "torrent-panel", "sheet-more")
OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"


def desktop(width):
    """A desktop window of WIDTH, out of the frame, pointer only."""
    return {**PHONE, "viewport": {"width": width, "height": 800}, "is_mobile": False, "has_touch": False,
            "device_scale_factor": 1}


READ = """(side) => {
  const sheet = document.querySelector('#sheet[data-open]');
  if (!sheet) return null;
  const s = sheet.getBoundingClientRect(), port = document.querySelector('#port').getBoundingClientRect();
  const drawer = document.querySelector('#drawer').getBoundingClientRect();
  const out = [];
  if (Math.abs(s.right - innerWidth) > 1) out.push(`right edge at ${Math.round(s.right)}`);
  if (Math.abs(s.top) > 1 || Math.abs(s.bottom - innerHeight) > 1) out.push(`not full height (${Math.round(s.top)}–${Math.round(s.bottom)})`);
  if (s.width > side + 1) out.push(`${Math.round(s.width)} px wide`);
  if (!(port.left < s.left - 100)) out.push('no page beside it');
  if (drawer.right > s.left) out.push('over the menu');
  return out;
}"""

OPEN = "() => window.state?.panelOpen === true"


async def open_desktop(browser, width):
    """A page out of the frame at WIDTH."""
    context, page = await open_page(browser, **desktop(width))
    await context.add_init_script(OUT_OF_FRAME)
    await page.reload(wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    return context, page


async def drag(page, travel):
    """Drags the side sheet's grip TRAVEL px to the right with the mouse; answers whether it is still open."""
    await read_at(page, "lib-film-panel", "() => true", wait=PANEL_IN)
    grip = await page.evaluate("""() => { const g = document.querySelector('#sheetgrab').getBoundingClientRect();
                                         return [g.left + g.width / 2, g.top + g.height / 2]; }""")
    await page.mouse.move(*grip)
    await page.mouse.down()
    for step in range(1, 11):
        await page.mouse.move(grip[0] + travel * step / 10, grip[1])
    await page.mouse.up()
    await page.wait_for_timeout(PANEL_IN)
    return await page.evaluate(OPEN)


async def main():
    journal = Journal("R481 — on a desktop the panel is a side sheet on the right")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_desktop(browser, 1280)
        page.on("pageerror", lambda error: errors.append(str(error)))
        bad, sheets = [], 0
        for state in await page.evaluate("() => window.__states()"):
            await page.evaluate("(id) => window.__go(id)", state)
            await page.wait_for_timeout(SETTLE)
            if await page.evaluate("() => !document.querySelector('#sheet[data-open]')"):
                continue
            # The slide is --duration-4, and a sheet a state opens late (a read first) is still sliding.
            await page.wait_for_timeout(PANEL_IN)
            seen = await page.evaluate(READ, SIDE)
            sheets += 1
            if seen:
                bad.append(f"{state} {seen}")
        journal.check(f"1280: every sheet against the right edge, full height, ≤ {SIDE} px, the page beside it "
                      f"({sheets} sheet states)", sheets > 30 and bad == [], "\n      ".join(bad[:15]))

        journal.check("a mouse drag of the edge to the right closes it", await drag(page, 160) is False)
        journal.check("a short drag puts it back", await drag(page, 30) is True)
        await read_at(page, "lib-film-panel", "() => true", wait=PANEL_IN)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(PANEL_IN)
        journal.check("Escape closes it", await page.evaluate(OPEN) is False)
        await read_at(page, "lib-film-panel", "() => true", wait=PANEL_IN)
        await page.mouse.click(400, 400)
        await page.wait_for_timeout(PANEL_IN)
        journal.check("a click on the scrim beside it closes it", await page.evaluate(OPEN) is False)
        await context.close()

        for width in (1024, 1440):
            context, page = await open_desktop(browser, width)
            page.on("pageerror", lambda error: errors.append(str(error)))
            bad = []
            for state in SAMPLE:
                seen = await read_at(page, state, READ, SIDE, wait=PANEL_IN)
                if seen is None or seen:
                    bad.append(f"{state} {seen}")
            journal.check(f"{width}: the sheet at the right edge ({len(SAMPLE)} states)", bad == [], "; ".join(bad))
            await context.close()

        context, page = await open_page(browser)
        seen = await read_at(page, "lib-film-panel", """() => { const s = document.querySelector('#sheet[data-open]').getBoundingClientRect();
            return {bottom: Math.abs(s.bottom - innerHeight) <= 1, wide: Math.abs(s.width - innerWidth) <= 1, rises: s.top > 100}; }""",
                             wait=PANEL_IN)
        journal.check("390: the panel rises from the bottom edge, as wide as the window",
                      seen == {"bottom": True, "wide": True, "rises": True}, f"{seen}")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

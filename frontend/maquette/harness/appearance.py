"""R102 — the appearance survives a reload, and the status bar follows it.

TWO DEFECTS, ONE SURFACE, AND NEITHER WAS VISIBLE TO ANYTHING HERE.

  B-245  `index.html` carries an inline script whose whole job is to apply the
         saved appearance BEFORE the first paint, so a reload opens in the
         chosen theme without a flash. It tested « clair » and « systeme »,
         while the application had been writing « light » and « system » since
         the English rename — so NO value it could store matched either
         literal, and the flash it exists to prevent happened on every reload
         for every reader who had ever touched the control. The two ends are in
         different files and different languages, and the third end of the
         contract is `localStorage`.
  B-233  `theme-color` was the constant `#0b0b0d` while the document paints
         light under `data-theme="light"`, so an installed application in the
         light theme wore a dark status bar. P21.

WHY NOTHING SAW EITHER. The oracle runs under the default theme, so a
light-theme defect is outside it by construction; a `<meta>` has no rectangle
and no computed style, so it is outside it twice. The accessibility tier reads
the rendered markup and not the head. And the flash is a property of the FIRST
FRAMES of a reload — a state nothing here drives, because every rule opens a
page and then measures it.

SO THIS RULE RELOADS. The choice is made through the interface's own control,
the page is reloaded, and the attribute is read from an INIT SCRIPT — a script
that runs before the document's own — rather than after load: read afterwards,
the module's own `applyAppearance` has long since corrected whatever the
pre-paint script did, and the reading would be green over the defect.

WHAT IT DOES NOT READ. Whether the FLASH is visible to an eye — that is a
paint, and no assertion here can time one. What it holds is the fact the flash
is made of: the attribute's presence in the first frames.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PROTOTYPE, Journal, open_page

from playwright.async_api import async_playwright

# Run before the document's own scripts, so what it records is the state of the
# root element at the moment the pre-paint script has finished with it — and
# never what a module corrected afterwards.
BEFORE_ANY_MODULE = """
window.__firstFrameTheme = null;
document.addEventListener('readystatechange', () => {
  if (window.__firstFrameTheme === null && document.readyState !== 'loading')
    window.__firstFrameTheme =
      document.documentElement.getAttribute('data-theme');
}, true);
"""

# Colours are converted through a canvas and never parsed: `getComputedStyle`
# answers in the space the author wrote — `oklch()` here — and three numbers
# pulled out of that with a regex built for `rgb()` mean nothing.
SAME_COLOUR = """([left, right]) => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const context = canvas.getContext('2d', { willReadFrequently: true });
  const paint = (value) => {
    context.clearRect(0, 0, 1, 1);
    context.fillStyle = '#000';
    context.fillRect(0, 0, 1, 1);
    context.fillStyle = value;
    context.fillRect(0, 0, 1, 1);
    return [...context.getImageData(0, 0, 1, 1).data].slice(0, 3).join(',');
  };
  return {left: paint(left), right: paint(right)};
}"""


async def read(page):
    """What the head declares and what the body paints, right now."""
    return await page.evaluate("""()=>({
      theme: document.documentElement.getAttribute('data-theme'),
      meta: (document.querySelector('meta[name="theme-color"]') || {})
              .getAttribute?.('content') ?? null,
      ground: getComputedStyle(document.body).backgroundColor,
      firstFrame: window.__firstFrameTheme ?? null,
      stored: (() => { try { return localStorage.getItem('tm-apparence'); }
                       catch (error) { return null; } })(),
    })""")


async def main():
    journal = Journal("R102 — the appearance survives a reload, and the bar follows it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        await context.add_init_script(BEFORE_ANY_MODULE)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # (a) THE CONTROL IS THE INTERFACE'S OWN, driven the way an operator
        # drives it: the drawer's appearance segment. Reaching into
        # `localStorage` would prove the reload and nothing about the control.
        await page.evaluate("()=>window.__go('drawer-navigation')")
        await page.wait_for_timeout(400)
        offered = await page.evaluate(
            """()=>[...document.querySelectorAll('[data-appearance]')]
                 .map((control) => control.dataset.appearance)""")
        journal.check(
            "the drawer offers the three appearances, in English",
            offered == ["system", "light", "dark"],
            str(offered))

        await page.evaluate(
            """()=>document.querySelector('[data-appearance="light"]').click()""")
        await page.wait_for_timeout(300)
        chosen = await read(page)
        journal.check(
            "choosing « light » paints light and records what it painted",
            chosen["theme"] == "light" and chosen["stored"] == "light",
            str({k: chosen[k] for k in ("theme", "stored")}))

        # (b) AND IT SURVIVES A RELOAD BEFORE THE FIRST PAINT (B-245). Read
        # from the init script, not after load: after load the module has long
        # since corrected whatever the pre-paint script did.
        await page.reload(wait_until="load")
        await page.wait_for_timeout(300)
        reloaded = await read(page)
        journal.check(
            "and the reload opens light in its FIRST frames, not after the "
            "module runs (B-245)",
            reloaded["firstFrame"] == "light",
            f"first frame {reloaded['firstFrame']!r}, "
            f"after load {reloaded['theme']!r}, stored {reloaded['stored']!r}")

        # (c) THE STATUS BAR FOLLOWS (B-233): the two themes declare DIFFERENT
        # colours, and each is the one the document really paints.
        light = await read(page)
        light_match = await page.evaluate(
            SAME_COLOUR, [light["meta"], light["ground"]])
        journal.check(
            "in the light theme the status bar's colour is the ground the "
            "document paints (B-233)",
            light_match["left"] == light_match["right"],
            f"meta {light['meta']!r} against ground {light['ground']!r}")

        await page.evaluate(
            "()=>window.__go('drawer-navigation')")
        await page.wait_for_timeout(300)
        await page.evaluate(
            """()=>document.querySelector('[data-appearance="dark"]').click()""")
        await page.wait_for_timeout(300)
        dark = await read(page)
        dark_match = await page.evaluate(
            SAME_COLOUR, [dark["meta"], dark["ground"]])
        journal.check(
            "in the dark theme it is the dark ground",
            dark_match["left"] == dark_match["right"],
            f"meta {dark['meta']!r} against ground {dark['ground']!r}")
        journal.check(
            "and the two themes do not declare the SAME colour — which is the "
            "whole of B-233",
            light_match["left"] != dark_match["left"],
            f"light {light_match['left']} against dark {dark_match['left']}")

        await context.close()
        await browser.close()
    journal.summary(errors)


asyncio.run(main())

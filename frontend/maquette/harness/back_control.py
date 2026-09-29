"""R-conformity-j — one back control: an icon and a word.

THE DEFECT THIS ENDS. Seven screens drew « Retour » as `backAction` with the
left icon; Maintenance wrote its arrow into the copy (« ← Toutes les
commandes ») and Réglages drew none at all. One control, one drawing.

WHAT IT READS: on every state below, each drawn `screen/back` carries an icon
(an `svg`) and no arrow glyph in its text.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

STATES = ("maintenance-topic", "settings-edited", "settings-secrets", "screen-profile", "run-detail", "mediasheet-movie")
ARROWS = "←⟵⬅"

READ = """()=>[...document.querySelectorAll('[data-part="screen/back"]')]
  .filter((node) => node.getBoundingClientRect().width > 0)
  .map((node) => ({icon: !!node.querySelector('svg'), text: node.textContent.trim()}))"""


async def main():
    """Reads the back controls of each state."""
    journal = Journal("R-conformity-j — one back control")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state in STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            controls = await page.evaluate(READ)
            journal.check(f"{state}: a back control is drawn", bool(controls), f"{controls}")
            journal.check(f"{state}: each is an icon and a word, no arrow in the copy",
                          all(one["icon"] and not any(arrow in one["text"] for arrow in ARROWS) for one in controls),
                          f"{controls}")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

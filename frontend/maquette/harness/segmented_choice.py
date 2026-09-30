"""R-conformity-o — every segmented choice is the view switch's drawing.

THE DEFECT THIS ENDS. The add screen drew its kind and its provider choices with
a segmented control of its own (`segmentSmall`), beside the view switch the
lists already drew: two drawings for one need. A choice between a few values in
place is `viewSwitch` at its text size, wherever it is offered.

WHAT IT READS, on the add screen's states with the « by identifier » fold
opened: no segmented control of another drawing is on screen; every group of
pressed buttons sits in a `view/switch`; and every such button — the kinds and
the providers alike — reads one drawing.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

STATES = ("acq-add-empty", "acq-add-results", "acq-identify")

READ = """()=>{
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="add:"]');
  if (!screen) return null;
  screen.querySelectorAll('details').forEach((fold) => { fold.open = true; });
  const drawing = (button) => {
    const style = getComputedStyle(button);
    return [style.fontSize, style.fontWeight, style.paddingTop, style.paddingLeft, style.borderRadius].join(' ');
  };
  const pressed = [...screen.querySelectorAll('button[aria-pressed]')];
  return {
    others: screen.querySelectorAll('[data-part="segment-small"]').length,
    groups: pressed.length,
    outside: pressed.filter((button) => !button.closest('[data-part="view/switch"]')).length,
    drawings: [...new Set(pressed.map(drawing))],
  };
}"""


async def main():
    """Reads the segmented choices of the add screen's states."""
    journal = Journal("R-conformity-o — one segmented choice")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state in STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            # The folds open on the first read; the second reads them open.
            await page.evaluate(READ)
            await page.wait_for_timeout(SETTLED)
            read = await page.evaluate(READ)
            journal.check(f"{state}: the kinds and the providers are offered", bool(read) and read["groups"] >= 6,
                          f"{read}")
            journal.check(f"{state}: every choice sits in the view switch, and no other drawing is on screen",
                          bool(read) and read["others"] == 0 and read["outside"] == 0, f"{read}")
            journal.check(f"{state}: every choice reads one drawing", bool(read) and len(read["drawings"]) == 1,
                          f"{read}")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

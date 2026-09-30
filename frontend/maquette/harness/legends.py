"""R-conformity-l — every state a drawing of episodes colours is in its legend.

THE DEFECT THIS ENDS. The follow sheet's seasons carried a legend of their
dots; the media sheet's season list coloured the same six states with none —
an absent legend is a defect (order 57). One legend, drawn over each, naming
only the states present.

WHAT IT READS, on `mediasheet-series` and `followsheet-gaps`: every episode
state drawn (`data-state` on an episode's row or cell) has its entry in the
legend over it, and the legend names no state the drawing does not use.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

STATES = ("mediasheet-series", "followsheet-gaps")

READ = """()=>{
  const layer = document.querySelector('#sheet[data-open]')
    ?? document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
  if (!layer) return null;
  layer.querySelectorAll('details').forEach((fold) => { fold.open = true; });
  const drawn = [...layer.querySelectorAll('[data-part="episode"][data-state], [data-part="episode/row"][data-state]')]
    .map((episode) => episode.dataset.state);
  const legend = [...layer.querySelectorAll('[data-part="legend"] [data-state]')].map((entry) => entry.dataset.state);
  return {drawn: [...new Set(drawn)].sort(), legend: [...new Set(legend)].sort()};
}"""


async def main():
    """Reads the episode states and the legend of each state."""
    journal = Journal("R-conformity-l — every coloured state is in its legend")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state in STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            await page.evaluate(READ)
            await page.wait_for_timeout(SETTLED)
            read = await page.evaluate(READ)
            journal.check(f"{state}: episodes are drawn in states", bool(read) and bool(read["drawn"]), f"{read}")
            journal.check(f"{state}: the legend names exactly the states drawn",
                          bool(read) and read["drawn"] == read["legend"], f"{read}")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

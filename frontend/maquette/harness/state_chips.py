"""R-conformity-d — every state pill is the chip.

THE DEFECT THIS ENDS. A season's marks — queued, asked, missing — and the
trailer's source were pills of their own, each a rounded span in a tone,
beside the interface's one chip. One need, one component: a short state in a
tinted pill is `chip`, led by the dot its own colour draws.

WHAT IT READS, on each state below: every state mark (`season/queued`,
`season/asked`, `season/missing`) and every `chip` drawn is the chip's drawing —
a full round, and the leading dot its `::before` draws (6 px). The drawing is
read, never a class: a pill that merely looks round has no dot.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

STATES = ("followsheet-gaps", "mediasheet-series", "run-detail")
MARKS = ("season/queued", "season/asked", "season/missing", "chip")

READ = """(marks)=>[...document.querySelectorAll(marks.map((part) => `[data-part="${part}"]`).join(','))]
  .filter((mark) => mark.getBoundingClientRect().width > 0)
  .map((mark) => {
    const dot = getComputedStyle(mark, '::before');
    return {part: mark.dataset.part, text: mark.textContent.trim().slice(0, 24),
            round: parseFloat(getComputedStyle(mark).borderTopLeftRadius) >= 999,
            dot: dot.content !== 'none' && dot.width === '6px'};
  })"""


async def main():
    """Reads the state marks of each state."""
    journal = Journal("R-conformity-d — every state pill is the chip")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state in STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            marks = await page.evaluate(READ, list(MARKS))
            journal.check(f"{state}: state marks are drawn", bool(marks), "none")
            journal.check(f"{state}: every one is the chip — round, led by its dot",
                          bool(marks) and all(mark["round"] and mark["dot"] for mark in marks),
                          str([mark for mark in marks if not (mark["round"] and mark["dot"])][:3]))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""R-conformity-h — an empty place is the app's one empty note.

THE DEFECT THIS ENDS. « Nothing here » was drawn three ways: the shared empty
note, a dashed box the media sheet redrew, and a line of guidance on Système's
runs. One need, one drawing: the empty note (`emptyNote`, anchored `empty`).

WHAT IT READS: on each state below, the named empty place holds the empty
note (`empty-state`, the part every empty note carries), drawn and saying
something.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

# The state, and the empty part it draws.
PLACES = (("runs-empty", "runs/empty"),)

READ = """(part)=>{
  const node = document.querySelector(`[data-part="${part}"] [data-part="empty-state"]`);
  if (!node) return null;
  const box = node.getBoundingClientRect();
  return {note: true, drawn: box.width > 0 && box.height > 0, text: node.textContent.trim().length};
}"""


async def main():
    """Reads each empty place."""
    journal = Journal("R-conformity-h — an empty place is the one empty note")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state, part in PLACES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            read = await page.evaluate(READ, part)
            journal.check(f"{state}: « {part} » is the empty note, drawn and saying something",
                          bool(read) and read["note"] and read["drawn"] and read["text"] > 0, f"{read}")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

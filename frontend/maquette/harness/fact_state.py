"""R-conformity-g — a fact's state is the chip at its row's end.

THE DEFECT THIS ENDS. The media sheet said « ● oui / non » with a bare dot and
a word after a key-value row, where Système says a fact's state with the chip
at the row's end. One need, one drawing — and « actif / non suivi » joins the
app's one on/off pair, « actif / inactif ».

WHAT IT READS, on `mediasheet-movie` and `mediasheet-series`: in the sheet's
fact panels, every row whose value is a state — possession, follow,
completeness — ends on a chip, and no bare status dot is drawn in a fact row.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, chrome_launch_args, open_page
from playwright.async_api import async_playwright

FRENCH = json.loads((pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "i18n" / "fr.json")
                    .read_text(encoding="utf-8"))
MEDIA = FRENCH["screens"]["media"]
# The labels of the rows whose value is a state.
STATE_ROWS = [MEDIA[key] for key in ("inLibrary", "owned", "follow", "completeness")]
STATES = ("mediasheet-movie", "mediasheet-series")

READ = """(labels)=>{
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
  const rows = screen ? [...screen.querySelectorAll('[data-part="key-value"]')] : [];
  return {
    stated: rows.filter((row) => labels.includes(row.firstElementChild?.textContent.trim()))
      .map((row) => ({label: row.firstElementChild.textContent.trim(),
                      chip: !!row.lastElementChild?.querySelector('[data-part="chip"]')})),
    bareDots: rows.filter((row) => row.querySelector('[data-part="status-dot"]')).length,
  };
}"""


async def main():
    """Reads the state rows of each media sheet."""
    journal = Journal("R-conformity-g — a fact's state is the chip at its row's end")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        for state in STATES:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            read = await page.evaluate(READ, STATE_ROWS)
            journal.check(f"{state}: its state rows end on a chip", bool(read["stated"])
                          and all(row["chip"] for row in read["stated"]), f"{read['stated']}")
            journal.check(f"{state}: and no fact row draws a bare dot", read["bareDots"] == 0,
                          f"{read['bareDots']} row(s) with a bare dot")
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

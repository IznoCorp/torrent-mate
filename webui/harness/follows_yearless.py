"""A follow nothing dates draws no year — never the word « null ».

THE CONTRACT ADMITS IT: `Follow.year` is an integer, a string or `null`, and the server serves `null` for a medium
whose year nothing states. The row's second line and the tile's fallback subtitle wrote the year with
`String(follow.year)`, so an undated follow read « null · Film ». The named state `acq-follows-yearless` poses one
follow with no year through the mock layer's own dial.

WHAT IT READS, and each fails differently:

  1. THE LAYER SERVES THE FOLLOW WITH NO YEAR. Held first: every hold below is vacuous over a list whose follow
     still carries one.
  2. ITS ROW IS DRAWN, and carries its title — the follow is in the list.
  3. ITS ROW SAYS NO « null » (nor « undefined »): the subject.
  4. A DATED FOLLOW STILL SAYS ITS YEAR, so a build that dropped every year would not pass hold 3.
  5. NO ERROR IS RAISED, at either width.

The state is read at a phone's width and at a desktop's; the two captures the pull request carries are taken here,
once the holds are read.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, open_page, browser_channel, chrome_launch_args, shot

from playwright.async_api import async_playwright

STATE = "acq-follows-yearless"
# A media title: the seed's own follow, which the state's dial leaves with no year.
UNDATED = "L'Odyssée"  # french-ok: a media title, which is data

# WHAT THE LAYER HOLDS: each follow's title and year.
FOLLOWS = """()=>(window.__followActions?.all() || []).map((one) => ({title: one.title, year: one.year}))"""

# WHAT ONE ROW SAYS, found by the title its card carries: the visible text of that card.
ROW_OF = """(title)=>{
  const card = [...document.querySelectorAll('#view [data-part="card"]')].find(
    (one) => (one.querySelector('[data-part="card/title"]')?.textContent || '').trim() === title);
  return card ? (card.textContent || '').replace(/\\s+/g, ' ').trim() : null;}"""

# A DESKTOP WINDOW, OUT OF THE FRAME the phone mock-up draws on a wide window (as `desktop_library.py` reads it).
OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"
DESKTOP = {
    "viewport": {"width": 1280, "height": 800},
    "device_scale_factor": 1,
    "is_mobile": False,
    "has_touch": False,
}
# THE DESIGN NOTE'S TOAST covers the foot of the list on the host that serves the maquette: closed before a capture.
CLOSE_THE_NOTE = """()=>document.querySelector('#toastx')?.click()"""


async def read(browser, journal, label, capture, out_of_frame=False, **context_options):
    """Reads the state at one width, then captures it.

    Args:
        browser: A launched Playwright browser.
        journal: The rule's journal.
        label: The width's name, for the checks and the capture.
        capture: The capture's name.
        out_of_frame: Whether the window leaves the phone mock-up (a desktop's).
        **context_options: The browser context's overrides (the desktop's).
    """
    context, page = await open_page(browser, **context_options)
    if out_of_frame:
        await context.add_init_script(OUT_OF_FRAME)
        await page.reload(wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    await page.evaluate("(id)=>window.__go(id)", STATE)
    await page.wait_for_timeout(SETTLED)
    await page.wait_for_timeout(SETTLED)

    follows = await page.evaluate(FOLLOWS)
    undated = [one for one in follows if one["year"] is None]
    dated = [one for one in follows if one["year"] not in (None, "")]
    journal.check(
        f"{label}: the layer serves exactly the follow the state poses with no year, and the others dated",
        [one["title"] for one in undated] == [UNDATED] and bool(dated),
        f"undated={[one['title'] for one in undated]} dated={len(dated)}")

    row = await page.evaluate(ROW_OF, UNDATED)
    journal.check(f"{label}: the undated follow is drawn in the list", row is not None and UNDATED in row, str(row))
    said = (row or "").lower()
    journal.check(
        f"{label}: and its row says no « null » and no « undefined » in the year's place",
        row is not None and "null" not in said and "undefined" not in said, str(row))

    dated_row = await page.evaluate(ROW_OF, dated[0]["title"]) if dated else None
    journal.check(
        f"{label}: a dated follow still says its year",
        bool(dated) and dated_row is not None and str(dated[0]["year"]) in dated_row,
        f"{dated[0]['title'] if dated else None}: {dated_row}")

    journal.check(f"{label}: and drawing the list raises no error", not errors, str(errors))
    await page.evaluate(CLOSE_THE_NOTE)
    await page.wait_for_timeout(SETTLED)
    await shot(page, capture)
    await context.close()


async def main():
    journal = Journal("A follow with no year draws no year")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        await read(browser, journal, "phone", "follows-yearless-mobile")
        await read(browser, journal, "desktop", "follows-yearless-desktop", out_of_frame=True, **DESKTOP)
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

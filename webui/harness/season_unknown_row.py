"""R-season-unknown — a season refused as unknown stays said on its row, on both season surfaces.

DOIT-2, « chaque rien a sa raison affichée »: the ask of a one-off season whose show's episode list is
not known is refused (`acquisition.season_unknown`). The message is gone in a few seconds; the
season's row goes on saying why the ask took nothing.

WHAT IT HOLDS:

  1. The media sheet draws what a server can answer for such a show — the held seasons, no episode
     list and no shortfall — so nothing on the screen contradicts the note.
  2. After the refused ask, the season asked words the refusal on the SHEET's row, no other season
     does, and the act is still offered.
  3. The follow panel of the same show words it on the same season's row, readable once a finger
     has opened that row.
"""
import asyncio

from common import PANEL_IN, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

# The state's one-off, and the season it asks.
SHOW = "Les aventures de Tintin"  # french-ok: a media title, the fixture's own
SEASON = 3
WORDS_KEY = "refusals.acquisition.season_unknown"

# What one surface's season rows draw: each row's head, whether it words the refusal, and how.
ROWS = """(surface) => {
  const root = document.querySelector(surface);
  if (!root) return [];
  return [...root.querySelectorAll('[data-part="season"]')].map((row) => {
    const note = row.querySelector('[data-part="season/unknown"]');
    return {
      head: row.querySelector('summary').textContent.replace(/\\s+/g, ' ').trim(),
      note: note ? note.textContent.trim() : null,
      shown: !!note && note.getBoundingClientRect().height > 0,
      act: !!row.querySelector('[data-grab-season]'),
      listed: !!row.querySelector('[data-part="panel"]'),
      shortfall: !!row.querySelector('[data-part="season/missing"], [data-part="season/missing-list"]'),
    };
  });
}"""

SCREEN = '[data-part="screen"][data-open]'
PANEL = "#sheet"


def noted(rows):
    """The heads of the rows that word the refusal."""
    return [row["head"] for row in rows if row["note"] is not None]


def of_season(rows):
    """The row of the season asked, or an empty record."""
    word = f" {SEASON} "
    return next((row for row in rows if word in row["head"]), {})


async def main():
    """Runs the rule."""
    journal = Journal("R-season-unknown — a season refused as unknown says so on its row, sheet and follow panel")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("()=>window.__go('season-row-ask-unknown')")
        await page.wait_for_timeout(SETTLED * 4)
        words = await page.evaluate("(key)=>window.__i18n.t(key)", WORDS_KEY)
        journal.check("the refusal has words of its own", bool(words) and words != WORDS_KEY, repr(words))

        sheet = await page.evaluate(ROWS, SCREEN)
        journal.check("the sheet draws its season rows", bool(of_season(sheet)), str([row["head"] for row in sheet]))
        journal.check("no row of an uncatalogued show lists episodes or states a shortfall",
                      bool(sheet) and not any(row["listed"] or row["shortfall"] for row in sheet), str(sheet))
        asked = of_season(sheet)
        journal.check("sheet: the season asked words the refusal, visibly",
                      asked.get("note") == words and asked.get("shown"), str(asked))
        journal.check("sheet: no other season words it", noted(sheet) == [asked.get("head")], str(noted(sheet)))
        journal.check("sheet: the act is still offered on the season refused", asked.get("act"), str(asked))

        await page.evaluate("(title)=>window.__panel.produce('follow', title)", SHOW)
        await page.wait_for_timeout(PANEL_IN + SETTLED * 3)
        panel = await page.evaluate(ROWS, PANEL)
        asked = of_season(panel)
        journal.check("follow panel: the same season's row words the refusal, and only it",
                      asked.get("note") == words and noted(panel) == [asked.get("head")],
                      f"{noted(panel)} among {[row['head'] for row in panel]}")
        if asked and not asked.get("shown"):
            head = page.locator(f'{PANEL} [data-part="season"]:has([data-part="season/unknown"]) summary')
            if await head.count() == 1:
                await head.scroll_into_view_if_needed()
                await head.tap()
                await page.wait_for_timeout(SETTLED)
        journal.check("follow panel: the words are readable once the row is open",
                      of_season(await page.evaluate(ROWS, PANEL)).get("shown"), str(of_season(panel)))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

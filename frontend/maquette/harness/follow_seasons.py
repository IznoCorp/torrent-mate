"""R192 — the follow panel's seasons are the SHEET's seasons, never a second catalogue.

A follow panel about a series draws a season block: one row per season, the
episodes held over the episodes aired. The media sheet of the same series draws
the same rows. Until this rule the panel drew them from the dying engine's own
season table, and that table disagreed with the served sheet on most of the
followed series that draw a block — Silo among them, whose panel and sheet did
not even agree on how many seasons exist. The reader saw two answers to one
question depending on which surface he asked (§ 13).

WHAT IS READ: for every followed series the seed gives an identity, the sheet's
season rows (number, then « held/aired ») and the panel's, compared as sets.
Silo is read by name, apart, because it is the case a reader can check with his
eyes on a phone: the same season count on both surfaces.

WHAT IT DOES NOT HOLD: which episodes each row marks, the season grab, or the
queued mark — each has its own rule. It holds that the panel and the sheet ask
the same question of the same answer.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, Journal, open_page  # noqa: E402

from playwright.async_api import async_playwright  # noqa: E402

journal = Journal("R192 — the follow panel agrees with the sheet on seasons")

SEEDS = ROOT / "design" / "src" / "mocks" / "seeds"
NAMED = "Silo"

# One row per season: its number (the first figure of the summary) and its
# « held/aired » fraction, in a stable order.
ROWS = """(root)=>[...document.querySelectorAll(root + ' [data-part="season"] > summary')]
  .map((summary) => {
    const number = (summary.textContent.match(/\\d+/) || [''])[0];
    const fraction = (summary.querySelector('span')?.textContent || '').trim();
    return number + ' ' + fraction;
  }).sort()"""


async def seasons_on_the_sheet(page, title):
    """The season rows the media sheet of one series draws.

    Args:
        page: The Playwright page.
        title: The series.

    Returns:
        One « number held/aired » string per season, sorted.
    """
    await page.evaluate("()=>{window.__reset?.(); window.__go('acq-follows-list');}")
    await page.wait_for_timeout(400)
    await page.evaluate(
        "(t)=>window.__screens.mediaSheet(t, window.__carriedFor(t) ?? undefined)", title)
    await page.wait_for_timeout(1400)
    return await page.evaluate(ROWS, '[data-part="screen"][data-open]')


async def seasons_on_the_panel(page, title):
    """The season rows the follow panel about one series draws.

    Args:
        page: The Playwright page.
        title: The series.

    Returns:
        One « number held/aired » string per season, sorted.
    """
    await page.evaluate("()=>{window.__reset?.(); window.__go('acq-follows-list');}")
    await page.wait_for_timeout(400)
    await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
    await page.wait_for_timeout(1000)
    return await page.evaluate(ROWS, "#sheet[data-open]")


async def main():
    follows = json.loads((SEEDS / "follows.json").read_text())
    series = [one["title"] for one in follows if one["kind"] == "show" and one.get("ids")]

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        compared = 0
        for title in series:
            sheet = await seasons_on_the_sheet(page, title)
            panel = await seasons_on_the_panel(page, title)
            if not sheet and not panel:
                continue
            compared += 1
            label = f"« {title} »: the panel draws the sheet's seasons"
            if title == NAMED:
                label = f"« {NAMED} » — the named case: the panel draws as many seasons as its sheet, and the same ones"
            journal.check(label, sheet == panel, f"sheet {sheet} · panel {panel}")

        journal.check(f"« {NAMED} » is among the series compared",
                      NAMED in series, f"series with an identity: {series}")
        journal.check("several series draw a season block to compare",
                      compared >= 5, f"{compared} compared")
        journal.check("no error was raised", not errors, " · ".join(errors[:3]))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

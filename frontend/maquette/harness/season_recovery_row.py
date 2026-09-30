"""R-season-recovery-b and -g (the row) — « Demandée » on both sheets, until the library.

The operator's Q5 = A: the row of a season whose whole recovery is launched says « Demandée » on the
series sheet AND the follow sheet, followed or not, until the season reaches the library; Q17 = A: one
mark at a time — « En file — pipeline en cours » while the ask waits, then « Demandée »; Q19: an
automatic recovery is told apart lightly, « Demandée · auto » INSIDE the one chip.

WHAT IT HOLDS:

  R-season-recovery-b  Silo S03 (followed) reads « Demandée » on the media sheet AND the follow
                       panel, the act « Récupérer la saison 3 » withdrawn; the one-off (R158's subject,
                       not followed) the same on its sheet; still « Demandée » when the pack has
                       arrived in the staging area and when the card is stopped in « À traiter »; gone
                       once the season is shelved, the fraction then `7/7`; while the ask waits on
                       the pipeline, « En file » and no « Demandée » (one mark at a time).
  R-season-recovery-g  the row's half: on the two automatic subjects the row's ONE chip reads
                       « Demandée · auto » — never a second chip; on the manual subject no « auto ».
"""
import asyncio

from common import PANEL_IN, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

REQUESTED = "Demandée"  # french-ok: the row's mark, asserted as drawn
AUTOMATIC = "Demandée · auto"  # french-ok: the automatic recovery's mark, asserted as drawn
WAITING = "En file"  # french-ok: the queued mark's words, asserted as drawn

# The season row of one series' season, on whatever surface is up: its marks, its act, its fraction.
ROW = """([title, season]) => {
  // THE ROWS ON SCREEN: a panel closed by the next state leaves its rows in the tree, hidden.
  const rows = [...document.querySelectorAll('[data-part="season"]')].filter((row) => row.checkVisibility({
    visibilityProperty: true, opacityProperty: true})).filter((row) => {
    const act = row.querySelector('[data-grab-season], [data-asked-season]');
    const value = act ? (act.dataset.grabSeason || act.dataset.askedSeason) : '';
    if (value) return value === title + '|' + season;
    const figure = ((row.querySelector('summary') || {}).textContent || '').match(/\\d+/);
    return figure && Number(figure[0]) === season;
  });
  if (!rows.length) return {found: false};
  const row = rows[rows.length - 1];
  const summary = (row.querySelector('summary') || {}).textContent || '';
  const infoChips = [...row.querySelectorAll('[data-tone="info"]')].map((one) => one.textContent.trim());
  return {
    found: true,
    asked: [...row.querySelectorAll('[data-part="season/asked"]')].map((one) => one.textContent.trim()),
    queued: [...row.querySelectorAll('[data-part="season/queued"]')].map((one) => one.textContent.trim()),
    infoChips,
    act: !!row.querySelector(`[data-grab-season="${CSS.escape(title + '|' + season)}"]`),
    fraction: (summary.match(/\\d+\\/\\d+/) || [''])[0],
  };
}"""


async def at(page, state, title, season, panel=None):
    """Asks for a state (raising the follow panel over it when named) and reads the row."""
    await page.evaluate("(id)=>window.__go(id)", state)
    await page.wait_for_timeout(SETTLED * 2)
    if panel:
        await page.evaluate("(title)=>window.__panel.produce('follow', title)", panel)
        await page.wait_for_timeout(PANEL_IN + SETTLED)
    return await page.evaluate(ROW, [title, season])


async def main():
    """Runs the rule."""
    journal = Journal("R-season-recovery-b, -g — « Demandée » on both sheets, until the library")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state, where in (("season-row-requested-sheet", "the media sheet"),
                             ("season-row-requested-panel", "the follow panel")):
            row = await at(page, state, "Silo", 3)
            journal.check(f"R-b: Silo S03, followed, reads « Demandée » on {where}, the act withdrawn",
                          row.get("asked") == [REQUESTED] and not row.get("act"), str(row))
        row = await at(page, "season-row-requested-one-off", "Les aventures de Tintin", 3)
        journal.check("R-b: the one-off (not followed) reads « Demandée » on its sheet, the act withdrawn",
                      row.get("asked") == [REQUESTED] and not row.get("act"), str(row))
        for state in ("season-card-arrived", "season-card-blocked"):
            row = await at(page, state, "Silo", 3, panel="Silo")
            journal.check(f"R-b: at {state} the follow panel still reads « Demandée »",
                          row.get("asked") == [REQUESTED], str(row))
        for state in ("season-recovery-shelved-sheet", "season-recovery-shelved-panel"):
            row = await at(page, state, "Silo", 3)
            journal.check(f"R-b: at {state} the mark is gone and the row reads 7/7",
                          row.get("found") and not row.get("asked") and row.get("fraction") == "7/7", str(row))
        row = await at(page, "season-row-queued", "Silo", 3)
        journal.check("R-b: while the ask waits, « En file » and no « Demandée » — one mark at a time",
                      len(row.get("queued", [])) == 1 and WAITING in row["queued"][0] and not row.get("asked"),
                      str(row))

        for state in ("season-row-requested-automatic-sheet", "season-row-requested-automatic-panel"):
            row = await at(page, state, "Silo", 3)
            journal.check(f"R-g: at {state} the row's ONE chip reads « Demandée · auto »",
                          row.get("asked") == [AUTOMATIC] and row.get("infoChips") == [AUTOMATIC], str(row))
        row = await at(page, "season-row-requested-sheet", "Silo", 3)
        journal.check("R-g: a manual recovery's row carries no « auto »",
                      not any("auto" in chip for chip in row.get("infoChips", [])), str(row))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

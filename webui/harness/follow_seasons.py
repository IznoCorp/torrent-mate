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

AND HOW THE SHEET AND THE PANEL DRAW WHAT THEY SAY, each in its own context:
R-conformity-d, every state pill is the chip (`hold_state_chips`);
R-conformity-g, a fact's state is the chip at its row's end (`hold_fact_states`);
R-conformity-l, every coloured episode state is in its legend (`hold_legends`);
and a season's title is never broken (`hold_season_titles_whole`): on Silo's
sheet, whose season 3 is crowded with marks (« 6/7 », « 1 manquant », « 3 à
venir · dès le … »), « Saison N » sits on one line at 320 and 390 px — the
reader of the train saw « SAISON / 3 » (2026-09-30); the marks wrap instead.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, ROOT, SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args

from playwright.async_api import async_playwright

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
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        compared: list[str] = []
        for title in series:
            sheet = await seasons_on_the_sheet(page, title)
            panel = await seasons_on_the_panel(page, title)
            if not sheet and not panel:
                continue
            compared.append(title)
            label = f"« {title} »: the panel draws the sheet's seasons"
            if title == NAMED:
                label = f"« {NAMED} » — the named case: the panel draws as many seasons as its sheet, and the same ones"
            journal.check(label, sheet == panel, f"sheet {sheet} · panel {panel}")

        # READ ON THE COMPARISON, NOT THE SEED (B-516): a series drawing no row
        # on either surface is skipped above, so « Silo is in the seed » held
        # while Silo answered nothing on both.
        journal.check(f"« {NAMED} » draws its seasons on both surfaces and is compared",
                      NAMED in compared, f"compared: {compared}")
        journal.check("several series draw a season block to compare",
                      len(compared) >= 5, f"{len(compared)} compared of {len(series)}")
        journal.check("no error was raised", not errors, " · ".join(errors[:3]))
        await context.close()
        await hold_state_chips(browser)
        await hold_fact_states(browser)
        await hold_legends(browser)
        await hold_season_titles_whole(browser)
        await browser.close()
    journal.summary()


CHIP_STATES = ("followsheet-gaps", "mediasheet-series", "run-detail")
MARKS = ("season/queued", "season/asked", "season/missing", "chip")
MARK_DRAWINGS = """(marks)=>[...document.querySelectorAll(marks.map((part) => `[data-part="${part}"]`).join(','))]
  .filter((mark) => mark.getBoundingClientRect().width > 0)
  .map((mark) => {
    const dot = getComputedStyle(mark, '::before');
    return {part: mark.dataset.part, text: mark.textContent.trim().slice(0, 24),
            round: parseFloat(getComputedStyle(mark).borderTopLeftRadius) >= 999,
            dot: dot.content !== 'none' && dot.width === '6px'};
  })"""


async def hold_state_chips(browser):
    """R-conformity-d — every state pill is the chip: round, led by its dot.

    Args:
        browser: The launched browser; the holds read a context of their own.
    """
    context, page = await open_page(browser)
    for state in CHIP_STATES:
        marks = await read_at(page, state, MARK_DRAWINGS, list(MARKS))
        journal.check(f"{state}: state marks are drawn", bool(marks), "none")
        journal.check(f"{state}: every one is the chip — round, led by its dot",
                      bool(marks) and all(mark["round"] and mark["dot"] for mark in marks),
                      str([mark for mark in marks if not (mark["round"] and mark["dot"])][:3]))
    await context.close()


MEDIA_WORDS = json.loads((ROOT / "design" / "src" / "i18n" / "fr.json").read_text(encoding="utf-8"))["screens"]["media"]
# The labels of the rows whose value is a state.
STATE_ROWS = [MEDIA_WORDS[key] for key in ("inLibrary", "owned", "follow", "completeness")]
FACT_ROWS = """(labels)=>{
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
  const rows = screen ? [...screen.querySelectorAll('[data-part="key-value"]')] : [];
  return {
    stated: rows.filter((row) => labels.includes(row.firstElementChild?.textContent.trim()))
      .map((row) => ({label: row.firstElementChild.textContent.trim(),
                      chip: !!row.lastElementChild?.querySelector('[data-part="chip"]')})),
    bareDots: rows.filter((row) => row.querySelector('[data-part="status-dot"]')).length,
  };
}"""


async def hold_fact_states(browser):
    """R-conformity-g — on each media sheet, a fact's state is the chip at its row's end, never a bare dot.

    Args:
        browser: The launched browser; the holds read a context of their own.
    """
    context, page = await open_page(browser)
    for state in ("mediasheet-movie", "mediasheet-series"):
        read = await read_at(page, state, FACT_ROWS, STATE_ROWS)
        journal.check(f"{state}: its state rows end on a chip", bool(read["stated"])
                      and all(row["chip"] for row in read["stated"]), f"{read['stated']}")
        journal.check(f"{state}: and no fact row draws a bare dot", read["bareDots"] == 0,
                      f"{read['bareDots']} row(s) with a bare dot")
    await context.close()


EPISODE_STATES = """()=>{
  const layer = document.querySelector('#sheet[data-open]')
    ?? document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
  if (!layer) return null;
  layer.querySelectorAll('details').forEach((fold) => { fold.open = true; });
  const drawn = [...layer.querySelectorAll('[data-part="episode"][data-state], [data-part="episode/row"][data-state]')]
    .map((episode) => episode.dataset.state);
  const legend = [...layer.querySelectorAll('[data-part="legend"] [data-state]')].map((entry) => entry.dataset.state);
  return {drawn: [...new Set(drawn)].sort(), legend: [...new Set(legend)].sort()};
}"""


async def hold_legends(browser):
    """R-conformity-l — on the sheet and the panel, the legend names exactly the episode states drawn.

    Args:
        browser: The launched browser; the holds read a context of their own.
    """
    context, page = await open_page(browser)
    for state in ("mediasheet-series", "followsheet-gaps"):
        # The folds open on the first read; the second reads them open.
        await read_at(page, state, EPISODE_STATES)
        await page.wait_for_timeout(SETTLED)
        read = await page.evaluate(EPISODE_STATES)
        journal.check(f"{state}: episodes are drawn in states", bool(read) and bool(read["drawn"]), f"{read}")
        journal.check(f"{state}: the legend names exactly the states drawn",
                      bool(read) and read["drawn"] == read["legend"], f"{read}")
    await context.close()


# THE LINES « Saison N » TAKES: the summary's text from its start to its
# fraction, read as the line boxes a Range covers (a pseudo-element's chevron is
# not in it), one distinct top per line.
TITLE_LINES = """()=>[...document.querySelectorAll('[data-part="screen"][data-open] [data-part="season"] > summary')]
  .map((summary) => {
    const fraction = summary.querySelector('.sfr');
    const range = document.createRange();
    range.setStart(summary, 0);
    if (fraction) range.setEndBefore(fraction); else range.setEnd(summary, summary.childNodes.length);
    const tops = new Set([...range.getClientRects()].filter((box) => box.width > 0)
      .map((box) => Math.round(box.top)));
    return {title: range.toString().trim(), lines: tops.size};
  })"""

# THE WIDTHS A SEASON ROW IS READ AT: the narrowest phone and the reference.
TITLE_WIDTHS = (320, 390)


async def hold_season_titles_whole(browser):
    """A season's title never breaks inside « Saison N »; the marks wrap under it.

    Args:
        browser: The launched browser; the hold reads a context of its own per width.
    """
    for width in TITLE_WIDTHS:
        context, page = await open_page(browser, viewport={**PHONE["viewport"], "width": width})
        rows = await read_at(page, "mediasheet-series", TITLE_LINES)
        broken = [row for row in rows if row["lines"] != 1]
        journal.check(f"mediasheet-series at {width} px: every « Saison N » sits on one line",
                      len(rows) >= 3 and not broken, f"{broken[:3]} of {len(rows)} rows")
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())

"""R510 — a season says what it holds off the catalogue (B-475 = B, maquette-blocked § 1.10).

His ruling of 2026-10-01 (round 2 q1 = B): a season holding episode numbers the
catalogue does not list shows a line « hors catalogue (n) » under the season,
without judgement; the fraction stays at or below what aired (B-380). The
engine serves the held numbers above the catalogue per season (BK7).

What this holds:

1. `media-season-off-catalogue` — American Dad!'s media sheet: its season 16
   reads 20/20 and, under its row, one line « hors catalogue (4) », drawn while
   the row is folded, in the muted tone, with no tone and nothing to press;
2. on that sheet, a season with nothing off the catalogue draws no such line —
   season 16's is the only one;
3. Les Animaniacs' sheet: its season 2 holds `[1, 4, 7, 9, 76–82]` against a
   catalogue of 12 — 4/12 and « hors catalogue (7) »;
4. the follow panel of American Dad! draws the same, by the same row: 20/20 and
   « hors catalogue (4) » under season 16, and no other such line — the line
   drawn by ONE markup (DESIGN § 1.10 « by the one season-row markup »): one
   source file writes `season/off-catalogue`, and the line on the panel is
   the sheet's to its last attribute (r3 of the lot's reading: two markups
   drift apart the day one is changed alone);
5. on every surface read, no season's fraction exceeds what aired.

Red before the lot's phase 7: no line exists (B-475) — the state is not named
either.
"""
import asyncio
import json
import pathlib
import re

from common import DESIGN_SOURCES, PANEL_IN, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, without_comments
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
OFF = WORDS["surfaces"].get("season", {}).get("offCatalogue", "<no copy>")

STATE = "media-season-off-catalogue"
SHOW = "American Dad!"
SEASON, AIRED, OFF_COUNT = 16, 20, 4
OTHER_SHOW = "Les Animaniacs"
OTHER_SEASON, OTHER_FRACTION, OTHER_COUNT = 2, "4/12", 7

# Every season row of one surface — the panel, or the topmost media sheet: its
# number, its fraction, its off-catalogue line, and where the line sits against
# the row's head.
ROWS = """(scope) => {
  const root = scope === 'panel' ? document.querySelector('#sheet[data-open]')
    : [...document.querySelectorAll('[data-part="screen"][data-open][data-key^="mediaSheet:"]')].pop();
  const muted = (() => {
    const probe = document.createElement('span');
    probe.style.color = 'var(--color-muted-foreground)';
    document.body.appendChild(probe);
    const color = getComputedStyle(probe).color;
    probe.remove();
    return color;
  })();
  return [...(root?.querySelectorAll('[data-part="season"]') ?? [])].map((season) => {
    const summary = season.querySelector('summary');
    const fraction = summary?.querySelector('.sfr');
    const line = season.querySelector('[data-part="season/off-catalogue"]');
    const box = line?.getBoundingClientRect();
    const head = fraction?.getBoundingClientRect();
    const text = (summary?.textContent ?? '').replace(/\\s+/g, ' ').trim();
    return {
      number: Number((text.match(/(\\d+)/) ?? [])[1]),
      fraction: (fraction?.textContent ?? '').trim(),
      open: season.open,
      line: line ? {
        text: line.textContent.replace(/\\s+/g, ' ').trim(),
        shown: box.width > 0 && box.height > 0,
        under: head ? box.top >= head.bottom - 1 : false,
        muted: getComputedStyle(line).color === muted,
        tone: line.dataset.tone ?? null,
        presses: line.querySelectorAll('button, a, [role="button"]').length,
      } : null,
    };
  });
}"""

FRACTION = re.compile(r"^(\d+)/(\d+)$")

# The line's part name, as a source writes it.
LINE_PART = '"season/off-catalogue"'
# The line as drawn, its attributes and its words: the markup two surfaces share.
LINE_MARKUP = """(scope) => {
  const root = scope === 'panel' ? document.querySelector('#sheet[data-open]')
    : [...document.querySelectorAll('[data-part="screen"][data-open][data-key^="mediaSheet:"]')].pop();
  return root?.querySelector('[data-part="season/off-catalogue"]')?.outerHTML ?? null;
}"""


def writers_of_the_line():
    """The source files that write the line's markup — one, when one markup draws it."""
    return [path.name for path in DESIGN_SOURCES
            if LINE_PART in without_comments(path.read_text(encoding="utf-8"))]


def said(count):
    """The line's words for one count."""
    return OFF.replace("{{count}}", str(count))


def within_aired(rows):
    """The rows whose fraction claims more than aired — none, when the surface holds."""
    over = []
    for row in rows:
        match = FRACTION.match(row["fraction"])
        if match and int(match.group(1)) > int(match.group(2)):
            over.append(row)
    return over


def season(rows, number):
    """One season's row, or None."""
    return next((row for row in rows if row["number"] == number), None)


def holds_line(row, count, fraction):
    """Whether a row reads its fraction and, under it, the muted line of its count, folded or not."""
    line = row["line"] if row else None
    return (row is not None and row["fraction"] == fraction and line is not None
            and line["text"] == said(count) and line["shown"] and line["under"]
            and line["muted"] and line["tone"] is None and line["presses"] == 0)


def others_with_line(rows, number):
    """The seasons other than one that draw an off-catalogue line."""
    return [row["number"] for row in rows if row["number"] != number and row["line"] is not None]


async def main():
    journal = Journal("R510 — a season says what it holds off the catalogue")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── 1–2. the media sheet ───────────────────────────────────────────
        answer = await page.evaluate(
            "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", STATE)
        await page.wait_for_timeout(PANEL_IN + SETTLED + SETTLED)
        journal.check(f"the named state {STATE} exists", answer is None, answer or "")
        rows = await page.evaluate(ROWS, "screen")
        sheet_line = await page.evaluate(LINE_MARKUP, "screen")
        row = season(rows, SEASON)
        journal.check(f"{STATE}: {SHOW} S{SEASON} reads {AIRED}/{AIRED} and, under its row, « {said(OFF_COUNT)} » "
                      "— muted, no tone, nothing to press, drawn folded",
                      holds_line(row, OFF_COUNT, f"{AIRED}/{AIRED}") and row["open"] is False, str(row))
        journal.check(f"{STATE}: a season with nothing off the catalogue draws no such line",
                      len(rows) > 1 and not others_with_line(rows, SEASON),
                      str(others_with_line(rows, SEASON)))
        journal.check(f"{STATE}: no season's fraction exceeds what aired", bool(rows) and not within_aired(rows),
                      str(within_aired(rows)))

        # ── 3. another count, another show ─────────────────────────────────
        await page.evaluate("""(title) => {
          window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined);
        }""", OTHER_SHOW)
        await page.wait_for_timeout(PANEL_IN + SETTLED + SETTLED)
        other = await page.evaluate(ROWS, "screen")
        row = season(other, OTHER_SEASON)
        journal.check(f"{OTHER_SHOW} S{OTHER_SEASON} reads {OTHER_FRACTION} and « {said(OTHER_COUNT)} » under its row",
                      holds_line(row, OTHER_COUNT, OTHER_FRACTION), str(row))
        journal.check(f"{OTHER_SHOW}: no fraction exceeds what aired", bool(other) and not within_aired(other),
                      str(within_aired(other)))

        # ── 4. the follow panel, by the same row ───────────────────────────
        writers = writers_of_the_line()
        journal.check("one source file writes the off-catalogue line's markup — one markup for both surfaces",
                      len(writers) == 1, str(writers))
        await page.evaluate("(title) => window.__panel.produce('follow', title)", SHOW)
        await page.wait_for_timeout(PANEL_IN + SETTLED + SETTLED)
        panel = await page.evaluate(ROWS, "panel")
        row = season(panel, SEASON)
        journal.check(f"the follow panel of {SHOW}: S{SEASON} reads {AIRED}/{AIRED} and « {said(OFF_COUNT)} » "
                      "under its row, as the sheet does", holds_line(row, OFF_COUNT, f"{AIRED}/{AIRED}"), str(row))
        journal.check("the follow panel: no other season draws the line, no fraction exceeds what aired",
                      len(panel) > 1 and not others_with_line(panel, SEASON) and not within_aired(panel),
                      f"{others_with_line(panel, SEASON)} · {within_aired(panel)}")
        panel_line = await page.evaluate(LINE_MARKUP, "panel")
        journal.check("the panel's line is the sheet's, to its last attribute",
                      sheet_line is not None and panel_line == sheet_line, f"sheet {sheet_line} · panel {panel_line}")

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

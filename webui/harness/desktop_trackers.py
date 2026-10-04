"""R485 — Trackers on a desktop: the roster, the torrents and their panel within one glance (phase 6).

The operator, 2026-10-01 — DECIDED 1 = C (a reading column ≈ 760 px, dialogs ≈ 480 px) and DECIDED 3 = C
(the panel a side sheet on the right, ≈ 440 px). `docs/features/maquette-desktop/DESIGN.md` § 1.3: on the
roster the ratio sat at x 1 140 and the switch at x 1 230 while the facts sat at x 25; a torrent card was
80 % empty; the torrent panel's fact rows were 1 230 px wide, the label and its value an eye-sweep apart.

WHAT IS READ, out of the harness's phone frame, at 1024, 1280 and 1440:

  1. the roster: every switch inside the column, at most a column's width from its row's first fact;
  2. the torrents: every card within the column;
  3. the torrent panel and a tracker's panel: every row of the side sheet within its 440 px;
  4. a cross-seed confirmation within its 480 px card.
"""
import asyncio

from common import PANEL_IN, PHONE, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

COLUMN = 760
SIDE = 440
DIALOG = 480
OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"


def desktop(width):
    """A desktop window of WIDTH, out of the frame, pointer only."""
    return {**PHONE, "viewport": {"width": width, "height": 800}, "is_mobile": False, "has_touch": False,
            "device_scale_factor": 1}


ROSTER = """(cap) => {
  const view = document.querySelector('#view').getBoundingClientRect();
  const switches = [...document.querySelectorAll('#view [role="switch"]')].map((s) => s.getBoundingClientRect()).filter((r) => r.width > 0);
  return {switches: switches.length, view: Math.round(view.width),
          outside: switches.filter((r) => r.right > view.right + 1 || r.right - view.left > cap + 1).length};
}"""

CARDS = """(cap) => {
  const view = document.querySelector('#view').getBoundingClientRect();
  const cards = [...document.querySelectorAll('#view [data-part="torrents/row"]')].map((c) => c.getBoundingClientRect()).filter((r) => r.width > 0);
  return {cards: cards.length, wide: cards.filter((r) => r.width > cap + 1 || r.left < view.left - 1 || r.right > view.right + 1).length};
}"""

# Every box the sheet draws, against the sheet: a row wider than the sheet is a row the side sheet did not hold.
WITHIN = """([selector, cap]) => {
  const layer = document.querySelector(selector);
  if (!layer) return null;
  const box = layer.getBoundingClientRect();
  const out = [...layer.querySelectorAll('*')].map((e) => e.getBoundingClientRect())
    .filter((r) => r.width > 0 && (r.right > box.right + 1 || r.left < box.left - 1)).length;
  return {width: Math.round(box.width), out, within: box.width <= cap + 1};
}"""


async def main():
    journal = Journal("R485 — Trackers on a desktop: the roster, the torrents and their panel within one glance")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        for width in (1024, 1280, 1440):
            context, page = await open_page(browser, **desktop(width))
            await context.add_init_script(OUT_OF_FRAME)
            await page.reload(wait_until="load")
            await page.evaluate("()=>window.__loadingDone?.()")
            page.on("pageerror", lambda error: errors.append(str(error)))
            seen = await read_at(page, "trackers-page", CARDS, COLUMN, wait=PANEL_IN * 2)
            journal.check(f"{width}: every torrent card within the column", seen["cards"] >= 3 and seen["wide"] == 0, f"{seen}")
            seen = await read_at(page, "trackers-roster", ROSTER, COLUMN)
            journal.check(f"{width}: every roster switch inside the column", seen["switches"] >= 4 and seen["outside"] == 0,
                          f"{seen}")
            for state in ("torrent-panel", "trackers-entry-open"):
                seen = await read_at(page, state, WITHIN, ["#sheet[data-open]", SIDE], wait=PANEL_IN)
                journal.check(f"{width} {state}: every row of the side sheet within its {SIDE} px",
                              seen is not None and seen["within"] and seen["out"] == 0, f"{seen}")
            seen = await read_at(page, "tracker-cross-seed-switch-confirm", WITHIN, ["#dlg[data-open]", DIALOG], wait=PANEL_IN)
            journal.check(f"{width}: the cross-seed confirmation within its {DIALOG} px card",
                          seen is not None and seen["within"] and seen["out"] == 0, f"{seen}")
            await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

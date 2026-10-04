"""R482 — Acquisition on a desktop: the cards, the ladder and the « + » in the column (milestone, phase 3).

The operator, 2026-10-01 — DECIDED 1 = C (a reading column ≈ 760 px) and DECIDED 7 = B (« + » and the
selection bar bounded to the column). `docs/features/maquette-desktop/DESIGN.md` § 1.3 names what
Acquisition drew on a desktop: the eight-rung ladder stretched over 1 150 px so its dots no longer read as
one sequence, « Relancer » and « Abandonner » 580 px wide each, « Choisir » at a different x on every
candidate, « Prendre celle-ci à la place » a 1 230 px button, and the « + » at the window's far corner.

WHAT IS READ, out of the harness's phone frame, at 1024, 1280 and 1440:

  1. on « En cours » and « À traiter », every card and its ladder inside the column, every rung inside
     its card, and every action of a card no wider than the column;
  2. on a resolution, every « Choisir » at the same x, inside the column;
  3. on the releases screen and on « + »'s search, every candidate and button inside the column;
  4. the « + » at the column's bottom-right corner, not the window's;
  5. at 390 the « + » keeps its phone corner.
"""
import asyncio

from common import PHONE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

COLUMN = 760
OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"


def desktop(width):
    """A desktop window of WIDTH, out of the frame, pointer only."""
    return {**PHONE, "viewport": {"width": width, "height": 800}, "is_mobile": False, "has_touch": False,
            "device_scale_factor": 1}


# The reading box: the open screen's content, else the page.
BOX = """const screen = [...document.querySelectorAll('[data-part="screen"][data-open]')].pop();
  const root = screen ?? document.querySelector('#view');
  const port = screen ? screen.querySelector('.port') : null;
  const column = (port ? [...port.children].find((c) => c.getBoundingClientRect().width > 0) : root).getBoundingClientRect();"""

CARDS = """(cap) => { """ + BOX + """
  const out = [];
  const cards = [...root.querySelectorAll('[data-part="card"]')];
  for (const card of cards) {
    const c = card.getBoundingClientRect();
    if (c.width > cap + 1 || c.left < column.left - 1 || c.right > column.right + 1) out.push(`card ${Math.round(c.width)} px at ${Math.round(c.left)}`);
    for (const step of card.querySelectorAll('[data-part="card/step"]')) {
      const s = step.getBoundingClientRect();
      if (s.left < c.left - 1 || s.right > c.right + 1) { out.push('a rung outside its card'); break; }
    }
    for (const button of card.querySelectorAll('button')) {
      if (button.getBoundingClientRect().width > cap + 1) { out.push(`a ${Math.round(button.getBoundingClientRect().width)} px action`); break; }
    }
  }
  return {cards: cards.length, out};
}"""

CHOOSE = """(cap) => { """ + BOX + """
  const picks = [...root.querySelectorAll('[data-resolve]')].map((b) => b.getBoundingClientRect()).filter((r) => r.width > 0);
  const rights = [...new Set(picks.map((r) => Math.round(r.right)))];
  return {picks: picks.length, rights, inside: picks.every((r) => r.right <= column.right + 1 && column.width <= cap + 1)};
}"""

WIDE = """(cap) => { """ + BOX + """
  const wide = [...root.querySelectorAll('button, [data-part="card"]')].map((b) => b.getBoundingClientRect().width).filter((w) => w > cap + 1);
  return {count: root.querySelectorAll('button').length, wide: wide.map(Math.round).slice(0, 5)};
}"""

FAB = """() => {
  const fab = document.querySelector('[data-part="shell/add-action"]'), view = document.querySelector('#view').getBoundingClientRect();
  const f = fab.getBoundingClientRect();
  return {shown: f.width > 0, right: Math.round(f.right), viewRight: Math.round(view.right), window: innerWidth,
          bottom: Math.round(innerHeight - f.bottom)};
}"""

HUSH = "() => document.querySelector('.toast.show button')?.click()"


async def main():
    journal = Journal("R482 — Acquisition on a desktop: the cards, the ladder and the « + » in the column")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        for width in (1024, 1280, 1440):
            context, page = await open_page(browser, **desktop(width))
            await context.add_init_script(OUT_OF_FRAME)
            await page.reload(wait_until="load")
            await page.evaluate("()=>window.__loadingDone?.()")
            page.on("pageerror", lambda error: errors.append(str(error)))
            for state in ("acq-now-loaded", "acq-todo-loaded"):
                seen = await read_at(page, state, CARDS, COLUMN)
                journal.check(f"{width} {state}: every card, its ladder and its actions inside the column",
                              seen["cards"] >= 2 and seen["out"] == [], f"{seen['cards']} cards {seen['out'][:4]}")
            seen = await read_at(page, "acq-resolution-tie", CHOOSE, COLUMN)
            journal.check(f"{width}: every « Choisir » at the same x, inside the column",
                          seen["picks"] > 2 and len(seen["rights"]) == 1 and seen["inside"], f"{seen}")
            for state in ("screen-releases", "acq-add-results"):
                seen = await read_at(page, state, WIDE, COLUMN)
                journal.check(f"{width} {state}: no candidate nor button wider than the column",
                              seen["count"] > 2 and seen["wide"] == [], f"{seen}")
            await read_at(page, "acq-follows-list", "() => true")
            await page.evaluate(HUSH)
            await page.wait_for_timeout(SETTLED)
            fab = await page.evaluate(FAB)
            journal.check(f"{width}: the « + » at the column's bottom-right, not the window's",
                          fab["shown"] and abs(fab["right"] - (fab["viewRight"] - 16)) <= 2,
                          f"{fab}")
            await context.close()

        context, page = await open_page(browser)
        await read_at(page, "acq-follows-list", "() => true")
        await page.evaluate(HUSH)
        await page.wait_for_timeout(SETTLED)
        fab = await page.evaluate(FAB)
        journal.check("390: the « + » keeps its phone corner", fab["shown"] and fab["window"] - fab["right"] == 16, f"{fab}")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

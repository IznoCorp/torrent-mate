"""R231 — the bottom bar holds the places the table gives it, and Système is not one.

Ruling 15: Système LEAVES the bar and is reached from the drawer, at its right;
the menu button carries its badge. The bar draws exactly the rows the navigation
table marks `inBar` — read off the table's own source, never written here — and
each is a finger's size.

1. the bar's buttons are the table's `inBar` rows, in the table's order, each at
   least 44 px on both sides;
2. Système is NOT among them;
3. it IS in the drawer, in the « Système » group, and a tap on its entry lands
   on its own address.

Read on the three states that already draw the bar and the drawer (RULINGS 17):
`acq-todo-loaded`, `acq-todo-empty`, `drawer-navigation`.

Red before the move: `sys` is marked `inBar`, so Système is in the bar.
"""
import asyncio
import json
import pathlib
import re

from common import ACTED, PAGE_PATHS, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TABLE = (SOURCE / "app/navigation.ts").read_text(encoding="utf-8")
# Every row of the table, in its order: its id and whether it is in the bar.
ROWS = re.findall(r'\bid: "([^"]+)",.*?\binBar: (true|false)', TABLE, re.S)
IN_BAR = [identifier for identifier, flag in ROWS if flag == "true"]
SYSTEM = "sys"
SYSTEM_GROUP = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["navigation"]["groups"]["system"]
FINGER = 44

BAR = """() => [...document.querySelectorAll('#nav button[data-page]')].map(button => {
  const box = button.getBoundingClientRect();
  return { page: button.dataset.page, width: box.width, height: box.height };
})"""


async def go(page, journal, state):
    """Asks for a named state, and holds that it exists rather than crashing."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    journal.check(f"the named state {state} exists", answer is None, answer or "")
    await page.wait_for_timeout(SETTLED)


async def main():
    journal = Journal("R231 — the bar holds the table's places, and Système is not one")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        journal.check("the table is read: rows and their bar flags", len(ROWS) >= 4 and IN_BAR, str(ROWS))
        for state in ("acq-todo-loaded", "acq-todo-empty"):
            await go(page, journal, state)
            bar = await page.evaluate(BAR)
            pages = [one["page"] for one in bar]
            journal.check(f"{state}: the bar draws exactly the table's inBar rows, in order",
                          pages == IN_BAR, f"{pages} — table {IN_BAR}")
            small = [one for one in bar if one["width"] < FINGER or one["height"] < FINGER]
            journal.check(f"{state}: every place is a finger's size", not small, str(small))
            journal.check(f"{state}: Système is not in the bar", SYSTEM not in pages, str(pages))

        await go(page, journal, "drawer-navigation")
        entry = await page.evaluate("""(page)=>{const a=document.querySelector(`#drawer [data-navgo="${page}"]`);
            if(!a) return null; return (a.parentElement.querySelector('p')||{}).textContent||'';}""", SYSTEM)
        journal.check("Système is in the drawer, in its « Système » group",
                      entry == SYSTEM_GROUP, repr(entry))
        await page.evaluate("(page)=>document.querySelector(`#drawer [data-navgo=\"${page}\"]`)?.click()", SYSTEM)
        await page.wait_for_timeout(ACTED)
        where = await page.evaluate("()=>location.pathname")
        journal.check("and its drawer entry lands on its own address",
                      where == PAGE_PATHS[SYSTEM], f"{where} — wanted {PAGE_PATHS[SYSTEM]}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

"""R241 — the Arrivées page is gone, and its address is an unknown one.

Ruling 2 of the operator's organisation: arrivals are acquisition cards, the
page that listed them disappears, and its batch launch bar with it. Ruled on the
design's open questions: « Lancer » and « Arrêter » die with the bar and nothing
replaces them, and `/arrivals` becomes an unknown address like any other — the
not-found page, with no redirect.

WHAT IS READ:

  1. the navigation table declares no `arr` row, so neither the bar nor the
     drawer can offer one — read on the table's source and on the drawn frame;
  2. no control in the shipped source is addressed to it (`data-go="arr"`), and
     no module names its feature directory;
  3. the resources carry none of its screen's sentences;
  4. `/arrivals` loaded cold draws the not-found page, and the address stays as
     typed — no redirect;
  5. the bar draws exactly the pages the table puts in it — Acquisition, the
     Médiathèque, « Trackers » and « Découvrir » — and R232 holds each at a
     quarter.

RE-AIMED OUT LOUD: hold 5 read a bar of three, and « Trackers »
joins it between the Médiathèque and « Découvrir » (organisation ruling 20). What
this rule holds is unchanged — the bar is the table's, and Arrivées is in neither.
"""
import asyncio
import json
import pathlib
import re

from common import PROTOTYPE, SETTLED, Journal, open_page, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TABLE = (SOURCE / "app/navigation.ts").read_text(encoding="utf-8")
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
SHIPPED = [path for path in SOURCE.rglob("*") if path.suffix in {".ts", ".tsx"}
           and "node_modules" not in path.parts and not path.name.endswith(".test.ts")]
ROW_IDS = re.findall(r'\bid: "([^"]+)",', TABLE)
IN_BAR = [identifier for identifier, flag
          in re.findall(r'\bid: "([^"]+)",.*?\binBar: (true|false)', TABLE, re.S) if flag == "true"]
THE_BAR_WANTED = ["acq", "lib", "trackers", "discover"]

FRAME = """()=>({
  bar: [...document.querySelectorAll('#nav button[data-page]')].map((one) => one.dataset.page),
  drawer: [...document.querySelectorAll('#drawer [data-navgo]')].map((one) => one.dataset.navgo)})"""
LANDED = """()=>({page: state.page, path: location.pathname})"""


async def main():
    journal = Journal("R241 — the Arrivées page is gone")
    journal.check("the navigation table declares no « arr » row", "arr" not in ROW_IDS, str(ROW_IDS))
    addressed = [str(path.relative_to(SOURCE)) for path in SHIPPED
                 if re.search(r"""data-go=["']arr["']|features/arrivals""", path.read_text(encoding="utf-8"))]
    journal.check("no shipped module addresses a control to it or names its feature",
                  addressed == [], str(addressed))
    journal.check("the resources carry none of its screen's sentences",
                  "arrivals" not in WORDS.get("screens", {})
                  and "arr" not in WORDS.get("navigation", {}).get("pages", {}),
                  str(sorted(WORDS.get("screens", {}))))
    journal.check("the table puts Acquisition, the Médiathèque and « Découvrir » in the bar",
                  IN_BAR == THE_BAR_WANTED, str(IN_BAR))

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.evaluate("()=>document.querySelector('[data-drawer]')?.click()")
        await page.wait_for_timeout(SETTLED)
        frame = await page.evaluate(FRAME)
        journal.check("the bar offers no « arr » button, and draws exactly the table's four",
                      frame["bar"] == THE_BAR_WANTED, str(frame["bar"]))
        journal.check("the drawer offers no « arr » entry", "arr" not in frame["drawer"],
                      str(frame["drawer"]))

        cold = await context.new_page()
        cold.on("pageerror", lambda error: errors.append(str(error)))
        await cold.goto(f"{PROTOTYPE}arrivals", wait_until="load")
        await cold.evaluate("()=>window.__loadingDone?.()")
        await cold.wait_for_timeout(SETTLED)
        landed = await cold.evaluate(LANDED)
        journal.check("« /arrivals » loaded cold draws the not-found page",
                      landed["page"] == "404", str(landed))
        journal.check("and the address stays as typed — no redirect",
                      landed["path"] == "/arrivals", str(landed))
        await cold.close()

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

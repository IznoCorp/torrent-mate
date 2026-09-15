"""R196 — « + » opens a fresh add screen, and « Identifier » still seeds the folder (B-340).

WHAT THE OPERATOR SAW. After a resolution's manual search, « + » opened the add
screen with the release name still in the field — « 0 résultat affiché sur 0
trouvé » — and the strip « 2 médias ajoutés » left over from an earlier visit.
The button handed the last entry query back in, and what the screen had added
was cleared only by the named states and the initial store.

WHAT THE OPERATOR EXPECTS. « + » opens a FRESH screen: an empty query, the
follow mode, nothing added. « Identifier » from a resolution keeps seeding the
folder's name, as it does.

THE WALK is the one the screenshot came from — back from the resolution, over to
Acquisition by its tab, where « + » lives — taken by a finger from one
named state and never driven again in between — a named state resets the store,
and a reset in the middle would wipe the very leftovers this rule is about.

  i1. « IDENTIFIER » SEEDS THE FOLDER. From a resolution, the manual search
      opens the add screen in the identify mode with the folder's name in the
      field.
  f1. « + » AFTER IT OPENS EMPTY, in the follow mode — the screenshot itself.
  a1. A RESULT IS REALLY ADDED: the footer strip exists. Held before the second
      opening, or the three holds after it would prove nothing about leftovers.
  f2. « + » AGAIN: THE FIELD IS EMPTY, not the query just typed.
  f3. AND THE MODE IS FOLLOW.
  f4. AND NO STRIP SAYS WHAT A PREVIOUS VISIT ADDED.
  f5. AND THE SAME SEARCH TYPED AGAIN MARKS NO RESULT DONE — no row wears the
      check its earlier visit put on it. Held with the rows counted, so an
      answer that drew nothing cannot pass it.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# THE ARRIVALS WITH A FOLDER STUCK FOR A RESOLUTION.
START_STATE = "arr-loaded"
QUERY = "star wars"

# THE ADD SCREEN AS DRAWN: its mode is in its key, its query in its field.
SCREEN = """()=>{
  const screen = document.querySelector('[data-part="screen"][data-open][data-key^="add:"]');
  const field = document.querySelector('#addq');
  const rows = screen ? [...screen.querySelectorAll('[data-panel^="add:"]')] : [];
  return {
    open: !!screen,
    key: screen ? screen.dataset.key : null,
    query: field ? field.value : null,
    strip: !!document.querySelector('[data-part="add/foot"]'),
    rows: rows.length,
    done: rows.filter((row) => row.textContent.includes('\\u2713')).length,
  };
}"""

# THE FIRST CARD FOOT THAT OFFERS A RESOLUTION, aimed at by its own centre.
RESOLVE_AIM = """()=>{
  const foot = [...document.querySelectorAll('[data-part="card/foot"]')]
    .find((one) => one.textContent.includes('R\\u00e9soudre'));
  if (!foot) return {found: false};
  foot.scrollIntoView({block: 'center'});
  const box = foot.getBoundingClientRect();
  return {found: true, x: box.left + box.width / 2, y: box.top + box.height / 2};
}"""


async def tap(page, selector):
    """Taps the first element a selector finds, by a finger at its own centre."""
    await page.evaluate("""(selector)=>document.querySelector(selector)
      ?.scrollIntoView({block: 'center'})""", selector)
    await page.wait_for_timeout(SETTLED)
    aim = await page.evaluate("""(selector) => {
      const one = document.querySelector(selector);
      if (!one) return {found: false};
      const box = one.getBoundingClientRect();
      const x = box.left + box.width / 2;
      const y = box.top + box.height / 2;
      const hit = document.elementFromPoint(x, y);
      return {found: true, x, y,
              reachable: !!hit && (hit === one || one.contains(hit)),
              covering: hit === null ? 'nothing' : hit.tagName};
    }""", selector)
    aim["tapped"] = bool(aim.get("found") and aim.get("reachable"))
    if aim["tapped"]:
        await page.touchscreen.tap(aim["x"], aim["y"])
        await page.wait_for_timeout(ACTED)
    return aim


async def tap_the_add_button(page):
    """Goes to Acquisition by its tab, waits for « + » to be drawn, then taps it.

    « + » is Acquisition's alone, so the walk takes the tab a finger takes; and
    a message hides it for as long as it is shown.
    """
    await tap(page, '[data-part="shell/tab-bar"] [data-page="acq"]')
    for _ in range(20):
        if await page.evaluate("()=>{const fab=document.querySelector('#fab');"
                               "return !!fab && !fab.hidden;}"):
            break
        await page.wait_for_timeout(250)
    return await tap(page, "#fab")


async def type_query(page, query):
    """Types a query into the add screen's field and waits for the answer."""
    await page.fill("#addq", query)
    await page.wait_for_timeout(ACTED + SETTLED)


async def main():
    """Walks the screenshot's journey and reads the add screen at each opening."""
    journal = Journal("R196 — « + » opens a fresh add screen, « Identifier » still seeds")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", START_STATE)
        await page.wait_for_timeout(SETTLED)
        aim = await page.evaluate(RESOLVE_AIM)
        if aim["found"]:
            await page.touchscreen.tap(aim["x"], aim["y"])
            await page.wait_for_timeout(ACTED)
        manual = await tap(page, "[data-manual]")
        identify = await page.evaluate(SCREEN)
        journal.check("« Identifier » opens the identify mode with the folder's name seeded",
                      manual["tapped"] and identify["key"] == "add:identify"
                      and bool(identify["query"]),
                      f"resolution {aim.get('found')}, manual {manual}, screen {identify}")

        back = await tap(page, '[data-part="screen/back"]')
        opened = await tap_the_add_button(page)
        first = await page.evaluate(SCREEN)
        journal.check("« + » after it opens empty, in the follow mode",
                      back["tapped"] and opened["tapped"] and first["key"] == "add:follow"
                      and first["query"] == "",
                      f"back {back.get('tapped')}, + {opened}, screen {first}")

        await type_query(page, QUERY)
        panel = await tap(page, '[data-part="screen"][data-open] [data-panel^="add:"]')
        await page.wait_for_timeout(PANEL_IN)
        act = await tap(page, "#sheet [data-add]")
        confirm = await page.evaluate("()=>!!document.querySelector('#dlg[data-open] [data-confirmadd]')")
        if confirm:
            await tap(page, "#dlg [data-confirmadd]")
        added = await page.evaluate(SCREEN)
        journal.check("a result is really added: the footer strip exists",
                      panel["tapped"] and act["tapped"] and added["strip"],
                      f"panel {panel.get('tapped')}, act {act}, confirm {confirm}, screen {added}")

        back = await tap(page, '[data-part="screen/back"]')
        opened = await tap_the_add_button(page)
        again = await page.evaluate(SCREEN)
        journal.check("« + » again: the field is empty, not the query just typed",
                      back["tapped"] and opened["tapped"] and again["open"] and again["query"] == "",
                      f"back {back.get('tapped')}, + {opened.get('tapped')}, query {again['query']!r}")
        journal.check("and the mode is follow",
                      again["key"] == "add:follow", f"key {again['key']}")
        journal.check("and no strip says what a previous visit added",
                      again["open"] and not again["strip"], f"screen {again}")

        await type_query(page, QUERY)
        retyped = await page.evaluate(SCREEN)
        journal.check("and the same search typed again marks no result done",
                      retyped["rows"] > 0 and retyped["done"] == 0,
                      f"{retyped['rows']} row(s), {retyped['done']} marked done")

        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

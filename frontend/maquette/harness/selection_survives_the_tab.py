"""R164 — the library's selection survives a tab change, and its bar does not follow (B-395).

WHAT THE OPERATOR SAW. « N sélectionnés · Annuler · Supprimer » drawn over
Acquisition › Suivis — a page that holds no selection and offers no deletion.
`app/bottom-slot.tsx` draws the bar with no condition, and the bar's own reads
`selMode` alone: the page is named nowhere in it.

WHAT WAS RULED, and it is two halves. The selection SURVIVES the tab change —
nothing is cleared by navigating — and the BAR does not follow: it hides off the
Médiathèque and comes back, with the same titles, when the tab is back. Only
« Annuler » empties it.

AND THE WAY BACK IS PART OF THE SUBJECT. The tab bar is hidden while `selMode` is
true, which is right on the library, where the selection bar takes its place, and
wrong on a page that has no selection bar to show: the operator would stand on
Acquisition with neither. So this rule holds the tab bar as drawn there, and it
is why the walk below changes page through the DRAWER (`a[data-navgo]`) — the
path a finger really has in selection mode.

WHAT IT READS, and each hold fails differently:

  s1. THE LIBRARY DRAWS THE BAR, and the selection is what the named state put
      there. Held first: the three titles are read from the store, and a walk
      that started with nothing selected would prove nothing after it.
  s2. OFF THE MÉDIATHÈQUE THE BAR IS NOT PAINTED, and no « Supprimer » is under
      a finger. Painted, not merely absent from the tree: read with any
      inertness lifted, because `inert` takes an element out of hit-testing
      without changing what is drawn (B-381, and B-394 met it on its own
      subject).
  s3. THE TAB BAR IS DRAWN THERE. Without it the selection would survive at the
      price of the navigation, which is a worse defect than the one repaired.
  s4. BACK ON THE MÉDIATHÈQUE THE BAR IS BACK, with the SAME titles — not a
      count, the titles themselves: a selection that survived as a number and
      lost what it pointed at would pass a count and delete the wrong media.
  s5. « ANNULER » ON RETURN EMPTIES IT, which is the only thing that may.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# THE LIBRARY IN SELECTION MODE, with three titles already ticked.
SELECTION_STATE = "lib-selection"

# WHERE THE WALK GOES AND COMES BACK FROM, by the page ids the drawer carries.
AWAY = "acq"
HOME = "lib"

# WHAT IS SELECTED, read where the selection lives rather than off the caption:
# a caption is a sentence about the selection and can be right about nothing.
SELECTED = """()=>[...(window.__store?.read().state.selected || [])]"""

# WHAT IS DRAWN AND WHAT A FINGER REACHES. The bar and the deletion are read as
# PAINT — inertness lifted and put back, since `inert` hides an element from the
# hit test and not from the eye.
DRAWN = """() => {
  const lifted = [];
  for (const node of document.querySelectorAll('[inert]')) {
    node.removeAttribute('inert');
    lifted.push(node);
  }
  const bar = document.querySelector('[data-part="selection/bar"]');
  const deletion = document.querySelector('[data-delsel]');
  const tabs = document.querySelector('[data-part="shell/tab-bar"]');
  const onTop = (element) => {
    if (!element) return null;
    const box = element.getBoundingClientRect();
    if (box.width === 0 || box.height === 0) return 'no box';
    const hit = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2);
    return hit === null ? 'nothing' : element.contains(hit) ? 'itself' : hit.tagName;
  };
  const answer = {
    page: window.__store?.read().state.page,
    bar: !!bar, barOnTop: onTop(bar),
    deletion: !!deletion, deletionOnTop: onTop(deletion),
    tabs: !!tabs, tabsOnTop: onTop(tabs),
    lifted: lifted.length,
  };
  for (const node of lifted) node.setAttribute('inert', '');
  return answer;
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


async def walk_to(page, identifier):
    """Changes page through the drawer, which is the path a finger has here."""
    opened = await tap(page, '[data-drawer="1"]')
    await page.wait_for_timeout(PANEL_IN)
    walked = await tap(page, f'a[data-navgo="{identifier}"]')
    await page.wait_for_timeout(ACTED)
    return {"drawer": opened, "entry": walked}


async def main():
    """Walks the library's selection to another tab and back."""
    journal = Journal("R164 — the selection survives the tab, its bar does not follow")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", SELECTION_STATE)
        await page.wait_for_timeout(SETTLED)
        selected = await page.evaluate(SELECTED)
        home = await page.evaluate(DRAWN)
        journal.check("the Médiathèque draws the bar over a real selection",
                      home["bar"] and home["barOnTop"] == "itself" and len(selected) >= 2,
                      f"{len(selected)} title(s): {selected}, bar {home['barOnTop']}")

        away = await walk_to(page, AWAY)
        there = await page.evaluate(DRAWN)
        journal.check("the walk to the other tab is taken by a finger",
                      away["drawer"]["tapped"] and away["entry"]["tapped"],
                      str({key: value.get("covering") for key, value in away.items()
                           if not value.get("tapped")}))
        journal.check("off the Médiathèque the bar is not painted",
                      there["page"] == AWAY and not there["bar"],
                      f"page {there['page']}, bar {there['bar']} ({there['barOnTop']}), "
                      f"inertness lifted on {there['lifted']}")
        journal.check("and no « Supprimer » is under a finger there",
                      not there["deletion"] or there["deletionOnTop"] not in ("itself",),
                      f"deletion {there['deletion']} ({there['deletionOnTop']})")
        journal.check("the tab bar is drawn there, so the way back exists",
                      there["tabs"] and there["tabsOnTop"] == "itself",
                      f"tabs {there['tabs']} ({there['tabsOnTop']})")

        back = await walk_to(page, HOME)
        again = await page.evaluate(DRAWN)
        kept = await page.evaluate(SELECTED)
        journal.check("the walk back is taken by a finger",
                      back["drawer"]["tapped"] and back["entry"]["tapped"],
                      str({key: value.get("covering") for key, value in back.items()
                           if not value.get("tapped")}))
        journal.check("back on the Médiathèque the bar is back, with the same titles",
                      again["page"] == HOME and again["bar"] and again["barOnTop"] == "itself"
                      and sorted(kept) == sorted(selected),
                      f"bar {again['bar']} ({again['barOnTop']}), {kept}")

        await tap(page, '[data-selmode="0"]')
        emptied = await page.evaluate(SELECTED)
        after = await page.evaluate(DRAWN)
        journal.check("and « Annuler » is what empties it",
                      emptied == [] and not after["bar"], f"{emptied}, bar {after['bar']}")

        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

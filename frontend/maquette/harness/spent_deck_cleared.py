"""R155 — a spent pile does not outlive the mode that drew it.

The operator saw the Découvrir list drawn BELOW the « charger plus » action,
once. This is the walk that reproduces it, and the mechanism is a stale node
rather than an ordering bug.

WHAT HAPPENS. The deck's body is filled imperatively — the pile is animated in
place, and a node React re-renders cannot animate — so the fragment writes into
a container React draws empty. When the mode leaves the deck, React reuses that
same container element and appends its own children to it, and anything the
fragment left there stays FIRST. The sweep that exists for this knew about the
pile (`.deck`) and not about the SPENT pile, which is a different shape: the end
mark, carrying the offer to load more. So a deck spent before the mode changed
left that offer standing at the top of the surface, with the whole feed drawn
under it.

WHAT THIS RULE READS, and each says something different:

  1. THE PILE IS REALLY SPENT and the offer is really drawn — otherwise every
     hold below is green about a state the walk never reached.
  2. LEAVING THE DECK TAKES THE OFFER WITH IT. This is the defect, and it is
     read as the operator saw it: is the action still on the page?
  3. AND NOTHING THE FRAGMENT WROTE IS LEFT ABOVE THE FEED. The stronger form
     of the same question, because a repair that removed the button and left
     its container would still draw the feed too low.

IT MEASURES BOTH MODES the surface can leave the deck for, because the sweep is
one line and a repair that covered one of them would look complete.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE DECK IS DRAWN.
DISCOVER_STATE = "acq-discover"

# THE MODES THE SURFACE LEAVES THE DECK FOR.
OTHER_MODES = ("list", "poster")

# SPENDING THE PILE, which no named state reaches: every position is dismissed
# and the deck redraws as its end mark.
SPEND = """()=>{
  const total = (window.__suggestions?.() || []).length;
  const gone = new Set();
  for (let at = 0; at < total; at += 1) gone.add(at);
  window.__store.write({sugMode: 'deck', sugGone: gone, sugOrder: null});
  return {total};}"""

SET_MODE = """(mode)=>window.__store.write({sugMode: mode})"""

# WHAT IS ON THE PAGE, and where. The feed's own container is read beside the
# action so a failure says whether the action merely survived or is actually
# sitting above the list — which is what the operator described.
THE_SURFACE = """()=>{
  const action = document.querySelector('[data-sugmore]');
  const feed = document.querySelector('#sugitems');
  const top = (node) => node ? Math.round(node.getBoundingClientRect().top) : null;
  return {action: !!action, actionTop: top(action), feedTop: top(feed),
          leftovers: [...document.querySelectorAll(
                       '[data-part="surface/body"] > [data-part="deck"], '
                       + '[data-part="surface/body"] > [data-part="empty-state"]')]
                     .map((node) => node.dataset.part)};}"""


async def main():
    journal = Journal("R155 — a spent pile does not outlive its mode")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for mode in OTHER_MODES:
            await page.evaluate("(id)=>window.__go(id)", DISCOVER_STATE)
            await page.wait_for_timeout(SETTLED)
            # LEFT AND RE-ENTERED, so the pile is rebuilt before it is spent:
            # the deck branch refuses to rewrite a pile that is already drawn.
            await page.evaluate(SET_MODE, "poster")
            await page.wait_for_timeout(SETTLED)
            spent = await page.evaluate(SPEND)
            await page.wait_for_timeout(SETTLED)
            standing = await page.evaluate(THE_SURFACE)
            journal.check(
                f"the pile is spent and its offer to load more is drawn, "
                f"before the mode becomes « {mode} » — without this the holds "
                "below are green about a state that never happened",
                spent["total"] > 0 and standing["action"], str(standing))

            await page.evaluate(SET_MODE, mode)
            await page.wait_for_timeout(SETTLED)
            after = await page.evaluate(THE_SURFACE)
            journal.check(
                f"leaving the deck for « {mode} » takes the spent pile's "
                "offer with it — it used to stay, and the feed was drawn under "
                "it",
                not after["action"],
                f"action at {after['actionTop']}, the feed at {after['feedTop']}")
            journal.check(
                f"and « {mode} » is left with nothing the fragment wrote above "
                "its feed",
                not after["leftovers"], str(after["leftovers"]))

        journal.check("and none of it raised an error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())

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
  2. LEAVING THE DECK LEAVES NO OFFER ABOVE THE FEED. This is the defect, read
     as the operator saw it — except that « is the action still on the page? »
     is NOT the question, and holding it that way was wrong for one commit. An
     emptied LIST draws an offer of its own, inside the feed, and it should:
     it is the same words for the same fact whichever way one was browsing.
     What must never happen again is an offer OUTSIDE the feed's own container,
     with the feed drawn under it. So the hold reads containment, not presence.
  3. AND NOTHING THE FRAGMENT WROTE IS LEFT ABOVE THE FEED. The stronger form
     of the same question, because a repair that removed the button and left
     its container would still draw the feed too low.

IT MEASURES BOTH MODES the surface can leave the deck for, because the sweep is
one line and a repair that covered one of them would look complete.

AND THE LIST'S END MARK SAYS WHAT IS TRUE, in its words (review round two, B7).
The emptied list drew the deck's own « … La réserve en garde d'autres » under a
footer saying the loaded reserve had ended, and went on saying it after the
load had answered « Réserve épuisée ». Three states, three chosen sentences:

  4. THE LIST EMPTIED under « Fin de la réserve chargée … » — its mark is the
     list's sentence, which does not contradict the footer, with its offer.
  5. THE RESERVE EXHAUSTED — the load pressed until it answered nothing and
     said so — the mark is the exhausted sentence, with nothing to load.

Both are read in the resource the interface reads. The load is pressed with
`element.click()`: what is held is the words after the press, not the press.
"""
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, SETTLED, open_page

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
          actionInsideFeed: !!(action && feed && feed.contains(action)),
          leftovers: [...document.querySelectorAll(
                       '[data-part="surface/body"] > [data-part="deck"], '
                       + '[data-part="surface/body"] > [data-part="empty-state"]')]
                     .map((node) => node.dataset.part)};}"""


# THE WORDS, from the resource the interface reads.
RESOURCE = json.loads(
    (pathlib.Path(__file__).resolve().parent.parent / "design" / "src" / "i18n"
     / "fr.json").read_text(encoding="utf-8"))
DISCOVER = RESOURCE["discover"]
DECK = RESOURCE["verbs"]["deck"]

# EVERY LOADED SUGGESTION DISMISSED, IN THE LIST, and every loaded one listed —
# so the footer below the list is the one that says the loaded reserve ended.
EMPTY_THE_LIST = """()=>{
  const total = (window.__suggestions?.() || []).length;
  const gone = new Set();
  for (let at = 0; at < total; at += 1) gone.add(at);
  window.__store.write({sugMode: 'list', sugGone: gone, sugCount: total});
  return total;}"""

THE_END = """()=>{
  const text = (node) => node ? (node.textContent || '').replace(/\\s+/g, ' ').trim() : '';
  const held = window.__toast?.read?.();
  return {mark: text(document.querySelector('#sugitems [data-part="empty-state"]')),
          footer: text(document.querySelector('#sugload')),
          offer: !!document.querySelector('#sugitems [data-sugmore]'),
          total: (window.__suggestions?.() || []).length,
          said: held && held.message ? held.message.message || '' : ''};}"""

PRESS_THE_OFFER = """()=>{
  const offer = document.querySelector('#sugitems [data-sugmore]');
  if (!offer) return false;
  offer.click();
  return true;}"""

# At most this many loads to exhaust the fixture's reserve.
LOADS = 6


async def hold_the_end_mark(page, journal):
    """Holds the list's end mark to the footer and to an exhausted reserve.

    Args:
        page: The page under test.
        journal: Where the holds are recorded.
    """
    await page.evaluate("(id)=>window.__go(id)", DISCOVER_STATE)
    await page.wait_for_timeout(SETTLED)
    await page.evaluate(SET_MODE, "list")
    await page.wait_for_timeout(SETTLED)
    await page.evaluate(EMPTY_THE_LIST)
    await page.wait_for_timeout(SETTLED)
    end = await page.evaluate(THE_END)
    footer = DISCOVER["endOfReserve"].replace("{{loaded}}", str(end["total"]))
    journal.check(
        "the emptied list sits under the footer saying the loaded reserve ended "
        "— else the next hold reads nothing",
        end["footer"] == footer, repr(end["footer"]))
    listed = DISCOVER["allSeenRestList"].replace("{{count}}", str(end["total"])) \
        if "allSeenRestList" in DISCOVER else None
    journal.check(
        "and its mark does not contradict that footer: the LIST's sentence, not "
        "the deck's « … La réserve en garde d'autres », with its offer to load",
        listed is not None and listed in end["mark"] and end["offer"],
        f"mark {end['mark']!r}, offer {end['offer']}")

    for _ in range(LOADS):
        if end["said"] == DECK["spent"].replace("{{total}}", str(end["total"])):
            break
        if not await page.evaluate(PRESS_THE_OFFER):
            break
        await page.wait_for_timeout(ACTED)
        await page.evaluate(EMPTY_THE_LIST)
        await page.wait_for_timeout(SETTLED)
        end = await page.evaluate(THE_END)
    spent = DECK["spent"].replace("{{total}}", str(end["total"]))
    journal.check(
        "the load was pressed until it answered nothing and said « Réserve "
        "épuisée » — else the next hold reads nothing",
        end["said"] == spent, repr(end["said"]))
    exhausted = DISCOVER["allSeenRestExhausted"].replace("{{count}}", str(end["total"])) \
        if "allSeenRestExhausted" in DISCOVER else None
    journal.check(
        "and the emptied list's mark now says the reserve is EXHAUSTED, and "
        "offers nothing to load — it used to go on saying « La réserve en garde "
        "d'autres » with « Charger 30 de plus »",
        exhausted is not None and exhausted in end["mark"] and not end["offer"],
        f"mark {end['mark']!r}, offer {end['offer']}")


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
                f"leaving the deck for « {mode} » leaves no offer ABOVE the "
                "feed — the spent pile's own used to stay there, with the whole "
                "feed drawn under it",
                not after["action"] or after["actionInsideFeed"],
                f"action at {after['actionTop']}, the feed at "
                f"{after['feedTop']}, inside it: {after['actionInsideFeed']}")
            journal.check(
                f"and « {mode} » is left with nothing the fragment wrote above "
                "its feed",
                not after["leftovers"], str(after["leftovers"]))

        await hold_the_end_mark(page, journal)

        journal.check("and none of it raised an error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())

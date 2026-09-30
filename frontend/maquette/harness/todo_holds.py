"""R209 — « À traiter » holds only what the operator's hand unblocks.

Ruling 7: the tab holds what only his hand unblocks — a medium to resolve, a
tunnel error awaiting relaunch or abandon, a Plex match to confirm —
and nothing else. What waits behind a maintenance run reads on its own card in
« En cours », with its reason; what he set aside is folded at the end of the
tab, outside its count (R226). The section a card sits
in is a function of its state, never of its origin.

What this holds:

1. every card in « À traiter » is BLOCKED on its ladder, and none in « En cours »
   is — the blocked section left « En cours » for the tab;
2. a card to resolve offers « Résoudre → », the candidates screen;
3. the tunnel error — derived from Top Chef's real stuck row, whose reason is a
   step that cannot finish — offers « Relancer », its reason in full, and NEVER
   « Résoudre »: no identity pick unblocks a step;
4. a card WAITING behind a maintenance run is in « En cours » with its reason,
   and not in « À traiter ».
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
TUNNEL_ERROR = next(row for row in json.loads((SEEDS / "stuck.json").read_text(encoding="utf-8"))
                    if row["title"].startswith("Top Chef"))

# EVERY FOOT IS READ, never the first alone: a card of « À traiter » carries two
# since its two feet stand side by side (ruling 10), and a « Résoudre » on the
# second is the same broken promise as one on the first.
CARDS = """() => [...document.querySelectorAll('#view [data-part="card"]')].map(card => {
  const feet = [...card.querySelectorAll('[data-part="card/foot"]')];
  const carried = (name) => feet.map(foot => foot.getAttribute(name)).find(value => value !== null) ?? null;
  return {
    title: card.querySelector('[data-part="card/title"]').textContent,
    states: [...card.querySelectorAll('[data-part="card/step"]')].map(cell => cell.dataset.state),
    resolve: carried('data-resolution') !== null,
    requeue: carried('data-journey-requeue'),
    plex: carried('data-plex-confirm') !== null,
    reason: (card.querySelector('[data-part="card/reason"]') || {}).textContent || null,
  };
})"""


async def go(page, journal, state):
    """Asks for a named state, and holds that it exists rather than crashing."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    journal.check(f"the named state {state} exists", answer is None, answer or "")
    await page.wait_for_timeout(SETTLED)


async def tab(page, value):
    """Taps one of Acquisition's tabs and reads the cards it draws."""
    await page.evaluate(f"()=>document.querySelector('[data-acqtab=\"{value}\"]')?.click()")
    await page.wait_for_timeout(ACTED)
    return await page.evaluate(CARDS)


async def main():
    journal = Journal("R209 — « À traiter » holds only what his hand unblocks")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await go(page, journal, "acq-todo-loaded")
        todo = await page.evaluate(CARDS)
        journal.check("« À traiter » draws cards, every one blocked on its ladder",
                      bool(todo) and all("blocked" in card["states"] for card in todo),
                      str([(card["title"], card["states"]) for card in todo]))
        # RE-READ WITH THE THIRD KIND: a Plex match to confirm is blocked in the tab
        # too, answered on the match and never by « Résoudre ».
        to_resolve = [card for card in todo if card["title"] != TUNNEL_ERROR["title"] and not card["plex"]]
        matches = [card for card in todo if card["plex"]]
        # RE-AIMED OUT LOUD: only a DISAGREEING match waits, and no real row
        # carries one — the match is read on the state that poses it.
        await go(page, journal, "acq-card-plex-disagrees")
        matches = [card for card in await page.evaluate(CARDS) if card["plex"]]
        journal.check("a Plex match to confirm is in the tab, and never offers « Résoudre »",
                      bool(matches) and not any(card["resolve"] for card in matches),
                      str([(card["title"], card["resolve"]) for card in matches]))
        journal.check("a card to resolve offers « Résoudre → »",
                      bool(to_resolve) and all(card["resolve"] for card in to_resolve),
                      str([(card["title"], card["resolve"]) for card in to_resolve]))
        error = next((card for card in todo if card["title"] == TUNNEL_ERROR["title"]), None)
        journal.check(
            "the tunnel error offers « Relancer », its reason in full, and never « Résoudre »",
            error is not None and error["requeue"] == TUNNEL_ERROR["title"]
            and not error["resolve"] and error["reason"] == TUNNEL_ERROR["reason"],
            str(error))
        # RE-AIMED OUT LOUD: « En cours » is read in the loaded world, where
        # something is in flight — the real world's holds nothing moving — on
        # the state that has a maintenance run holding, read FIRST in that
        # world: a queue answer cached before the maintenance began would draw
        # the cards still moving. The waiting hold used to pass on the cards
        # « Cherché, rien trouvé » drew (waiting, with a reason), not on the
        # ones a maintenance holds; that section left « En cours ».
        await go(page, journal, "acq-card-waiting")
        now = await page.evaluate(CARDS)
        journal.check("« En cours » holds no blocked card",
                      bool(now) and not any("blocked" in card["states"] for card in now),
                      str([(card["title"], card["states"]) for card in now if "blocked" in card["states"]]))
        waiting = [card for card in now if "waiting" in card["states"]
                   and card["reason"]]
        journal.check("a card waiting behind a maintenance run is in « En cours », with its reason",
                      bool(waiting), str(len(waiting)))
        todo = await tab(page, "todo")
        journal.check("and it is not in « À traiter »",
                      bool(waiting) and not {card["title"] for card in waiting}
                      & {card["title"] for card in todo},
                      str([card["title"] for card in todo]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

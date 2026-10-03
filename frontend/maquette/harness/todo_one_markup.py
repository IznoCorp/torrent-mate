"""R507 — every card of « À traiter » is the one acquisition card; nothing is drawn for blocks alone.

The operator's principles of 09-29: « on crée pas de nouveau composant on
adapte » and « Il faut uniformiser les comportements » (maquette-blocked § 1.8:
every element drawn by the one component that already draws it). DECIDED 2: no
« × » on a closure card.

What this holds, on « À traiter » holding every kind of card — the list whole,
qBittorrent down, a vanished medium, a superseded episode and film:

1. every card of the list is a `card` part of the ONE markup — the class the
   cards of « En cours » wear, its body, its title, its strip, its reason line;
2. a card draws no button but its poster or folder, its body and its feet: no
   « × », no close of its own;
3. every door is a `card/foot` carrying `data-go`, and every card of an external
   block offers one;
4. a closure card is drawn there, to be read (red until one exists);
5. no `features/*/variants.ts` exports a variant named for blocks or closures.

Red before the lot's phase 5: no closure card exists to read (DESIGN § 4).
"""
import asyncio
import pathlib
import re

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"

# The states whose « À traiter » holds every kind of card, and the closure each poses, if any.
STATES = [
    ("acq-todo-every-cause", None),
    ("acq-block-client-unreachable", None),
    ("acq-closure-torrent-removed", "This City Is Ours"),
    ("acq-superseded-episode", "Silo|S03E07"),
    ("acq-superseded-film", "Conclave"),
]
CARD_BUTTONS = {"card/poster", "card/folder", "card/body", "card/foot"}
# A name that would say a variant was drawn for blocks or closures alone.
NAMED_FOR_BLOCKS = re.compile(r"export\s+const\s+(\w*(?:block|closure|closed|supersed)\w*)", re.I)

REFERENCE = """() => {
  const card = document.querySelector('#view [data-region="acquisition/body"] [data-part="card"]');
  return card ? card.className.split(/\\s+/).filter(name => name && name !== 'fresh').sort().join(' ') : null;
}"""
CARDS = """() => {
  const queue = window.__queries?.getQueryData(['/api/v1/acquisition/to-handle', 'loaded']) || {};
  const pad = (value) => String(value).padStart(2, '0');
  const keyOf = (one) => one.season == null ? one.title
    : `${one.title}|S${pad(one.season)}${one.episode == null ? '' : 'E' + pad(one.episode)}`;
  const rows = [...(queue.inFlight || []), ...(queue.arrivals || []), ...(queue.blocked || [])];
  return [...document.querySelectorAll('#view [data-region="acquisition/body"] [data-part="card"]')]
    .filter(card => !card.closest('[data-part="section/set-aside"]'))
    .map(card => {
      const served = rows.filter(one => keyOf(one) === card.dataset.acquisition);
      return {
        key: card.dataset.acquisition,
        markup: card.className.split(/\\s+/).filter(name => name && name !== 'fresh').sort().join(' '),
        parts: ['card/body', 'card/title', 'card/strip', 'card/reason'].every(part => card.querySelector(`[data-part="${part}"]`)),
        buttons: [...card.querySelectorAll('button')].map(button => button.dataset.part),
        doors: [...card.querySelectorAll('[data-go]')].map(door => door.dataset.part),
        stopped: served.some(one => one.closure == null && (one.ladder || []).some(rung => rung.resumes === 'auto')),
        closed: served.some(one => one.closure != null),
      };
    });
}"""


async def go(page, journal, state):
    """Asks for a named state and holds that it exists."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    await page.wait_for_timeout(SETTLED)
    journal.check(f"the named state {state} exists", answer is None, answer or "")


async def main():
    journal = Journal("R507 — every card of « À traiter » is the one acquisition card")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # The one markup, as « En cours » draws it.
        await go(page, journal, "acq-now-loaded")
        reference = await page.evaluate(REFERENCE)
        journal.check("« En cours » draws its cards, the markup every list reads", reference is not None, repr(reference))

        for state, closure in STATES:
            await go(page, journal, state)
            await page.wait_for_timeout(ACTED)
            cards = await page.evaluate(CARDS)
            odd = [card["key"] for card in cards if card["markup"] != reference or not card["parts"]]
            journal.check(f"{state}: every card is the one acquisition card — its class, body, title, strip, reason",
                          cards and not odd, f"{len(cards)} cards · not the one markup: {odd}")
            extra = [(card["key"], sorted(set(card["buttons"]) - CARD_BUTTONS)) for card in cards
                     if not set(card["buttons"]) <= CARD_BUTTONS]
            journal.check(f"{state}: no card draws a button but its poster, body and feet — no « × »",
                          not extra, str(extra))
            loose = [card["key"] for card in cards if any(part != "card/foot" for part in card["doors"])]
            doorless = [card["key"] for card in cards if card["stopped"] and "card/foot" not in card["doors"]]
            journal.check(f"{state}: every door is a card foot with data-go; every external block offers one",
                          not loose and not doorless, f"door off the foot: {loose} · block with no door: {doorless}")
            if closure is not None:
                drawn = [card["key"] for card in cards if card["closed"]]
                journal.check(f"{state}: the closure card « {closure} » is drawn, to be read",
                              closure in drawn, str(drawn))

        named = [f"{path.relative_to(SOURCE)}: {name}" for path in sorted(SOURCE.glob("features/*/variants.ts"))
                 for name in NAMED_FOR_BLOCKS.findall(path.read_text(encoding="utf-8"))]
        journal.check("no features/*/variants.ts exports a variant named for blocks or closures", not named, str(named))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

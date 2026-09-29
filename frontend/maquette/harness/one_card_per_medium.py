"""R238 — one medium, one acquisition card.

A folder a follow asked for, once it is in the staging area, is the same
acquisition as the follow's card in flight: it JOINS that card — never two
cards, never a second take. « President Curtis » and « Furious », two real
follows of the dense world, were drawn twice: once as the queue's card in flight,
once as a staging arrival.

What it holds, in the dense world:

1. the queue's answer names every medium once, across its families;
2. « En vol » draws each of those two follows once;
3. the rapprochement is by ITEM, never by title: the same series at another
   episode stays another card. The pair is built HERE from President Curtis's
   real card, its line moved from S01E02 to S01E03 — a derivation, and the only
   one: no real row is a second episode of these series.

THE EPISODE IS READ OFF THE CARD'S LINE (`secondaryLine`), the only place a
queue card carries it — fragile, and said: a reworded line would lose it. The
backend is asked for the field (DESIGN § 6.2).

THE INTERFACE KEEPS ITS OWN JOIN (`inFlightCards`), and it is not dead code: the
real backend may still answer one item twice until the matching it is asked for
is served.

THE HALF NOT HELD, and said: a folder added BY HAND that matches a follow once
identified would join the same way; no real row is one, and none is posed — the
matching is a demand on the backend (RULINGS 27).
"""
import asyncio
import collections
import json

from common import SETTLED, Journal, open_page, chrome_launch_args
from playwright.async_api import async_playwright

FOLLOWED = ("President Curtis", "Furious")
QUEUE = """async () => {
  const answer = await (await fetch('/api/acquisition/to-handle?scenario=loaded')).json();
  return Object.entries(answer).flatMap(([family, cards]) => Array.isArray(cards)
    ? cards.map((card) => ({ family, title: card.title })) : []);
}"""
DRAWN = """() => [...document.querySelectorAll('#view [data-part="card"] [data-part="card/title"]')]
  .map((one) => one.textContent)"""
STAGED = """async () => (await (await fetch('/api/staging/media?scenario=loaded')).json()).moving
  .map((card) => ({ title: card.title, strip: card.strip }))"""


async def main():
    journal = Journal("R238 — one medium, one acquisition card")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        answer = await page.evaluate("(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}",
                                     "acq-now-loaded")
        journal.check("the named state acq-now-loaded exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)

        cards = await page.evaluate(QUEUE)
        counted = collections.Counter(card["title"] for card in cards)
        twice = {title: [card["family"] for card in cards if card["title"] == title]
                 for title, count in counted.items() if count > 1}
        journal.check("the queue's answer names every medium once", not twice, json.dumps(twice, ensure_ascii=False))
        drawn = collections.Counter(await page.evaluate(DRAWN))
        journal.check("« En vol » draws each of the two follows once",
                      all(drawn[title] == 1 for title in FOLLOWED), str({title: drawn[title] for title in FOLLOWED}))
        staged = {card["title"] for card in await page.evaluate(STAGED)}
        journal.check("both are in the staging area, so the card kept is the joined one",
                      all(title in staged for title in FOLLOWED), str(staged))

        matched = await page.evaluate("""async () => {
          const answer = await (await fetch('/api/acquisition/to-handle?scenario=loaded')).json();
          const real = [...answer.arrivals, ...answer.inFlight].find((card) => card.title === 'President Curtis');
          if (!real) return null;
          const next = { ...real, secondaryLine: real.secondaryLine.replace('S01E02', 'S01E03') };
          return { itself: window.__mocks.sameItem(real, { ...real }), another: window.__mocks.sameItem(real, next),
                   moved: next.secondaryLine !== real.secondaryLine };
        }""")
        journal.check("the same item is one — and the same series at another episode is another card",
                      matched is not None and matched["moved"] and matched["itself"] and not matched["another"],
                      str(matched))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

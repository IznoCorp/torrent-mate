"""R221 — « Confirmer » and « Corriger » act on the Plex match itself.

A medium the pipeline shelved is not done until Plex shows it under the right
identity (§4). When the match is to be confirmed, « À traiter » holds the card
(ruling 7) and it offers two verbs ON THAT MATCH — « Confirmer », the match is
the medium; « Corriger », it is not — rather than sending the operator through
the candidates screen for a match he can already judge.

Read on the one card the seeds hold for it, a derivation from Star Trek's real
settled row whose last rung waits for its confirmation:

1. the card is blocked on its ladder, in « À traiter », and names the match;
2. « Confirmer » is ANSWERED on the network by the match's own operation, and
   the card leaves « À traiter »;
3. « Corriger » is answered by the same operation, the card leaves, and the
   candidates screen opens on that medium.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
MATCHED = next((row for row in json.loads((SEEDS / "settled.json").read_text(encoding="utf-8"))
                if row.get("plexMatch")), {"title": "", "plexMatch": {"title": ""}})
OPERATION = "resolvePlexMatch"

CARD = """(title) => {
  const card = [...document.querySelectorAll('#view [data-part="card"]')]
    .find(one => one.querySelector('[data-part="card/title"]')?.textContent === title);
  if (!card) return null;
  return {
    states: [...card.querySelectorAll('[data-part="card/step"]')].map(cell => cell.dataset.state),
    reason: (card.querySelector('[data-part="card/reason"]') || {}).textContent || '',
    confirm: [...card.querySelectorAll('[data-part="card/foot"]')].some(foot => foot.getAttribute('data-plex-confirm') === title),
    correct: [...card.querySelectorAll('[data-part="card/foot"]')].some(foot => foot.getAttribute('data-plex-correct') === title),
    tab: state.acqTab,
  };
}"""

ANSWERED = f"""() => (window.__mocks?.answered() || [])
  .filter(call => call.operationId === {json.dumps(OPERATION)} && call.status === 200).length"""


async def go(page, journal, state):
    """Asks for a named state, and holds that it exists rather than crashing."""
    answer = await page.evaluate(
        "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
    journal.check(f"the named state {state} exists", answer is None, answer or "")
    await page.wait_for_timeout(SETTLED)


async def tap(page, attribute, title):
    """Taps a card foot by its verb and its medium."""
    await page.evaluate(f"""(title)=>[...document.querySelectorAll('#view [data-part="card/foot"]')]
        .find(foot => foot.getAttribute('{attribute}') === title)?.click()""", title)
    await page.wait_for_timeout(ACTED)


async def main():
    journal = Journal("R221 — « Confirmer » and « Corriger » on the Plex match")
    title = MATCHED["title"]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await go(page, journal, "acq-todo-loaded")
        card = await page.evaluate(CARD, title)
        journal.check("the Plex-match card is in « À traiter », blocked, naming the match",
                      card is not None and card["tab"] == "todo" and "blocked" in card["states"]
                      and bool(MATCHED["plexMatch"]["title"])
                      and MATCHED["plexMatch"]["title"] in card["reason"], str(card))
        journal.check("it offers « Confirmer » and « Corriger » on that match",
                      card is not None and card["confirm"] and card["correct"], str(card))

        before = await page.evaluate(ANSWERED)
        await tap(page, "data-plex-confirm", title)
        journal.check("« Confirmer » is answered by the match's own operation",
                      await page.evaluate(ANSWERED) == before + 1, OPERATION)
        journal.check("and the card leaves « À traiter »",
                      await page.evaluate(CARD, title) is None, "")

        await go(page, journal, "acq-todo-loaded")
        before = await page.evaluate(ANSWERED)
        await tap(page, "data-plex-correct", title)
        journal.check("« Corriger » is answered by the same operation",
                      await page.evaluate(ANSWERED) == before + 1, OPERATION)
        opened = await page.evaluate(
            """()=>document.querySelector('[data-part="screen"][data-open]')?.dataset.key ?? null""")
        journal.check("the candidates screen opens on that medium",
                      opened == f"resolution:{title}", repr(opened))
        await page.evaluate("()=>window.__bridge?.back?.() ?? history.back()")
        await page.wait_for_timeout(ACTED)
        await page.evaluate("""()=>document.querySelector('[data-acqtab="todo"]')?.click()""")
        await page.wait_for_timeout(ACTED)
        journal.check("and the card has left « À traiter »",
                      await page.evaluate(CARD, title) is None, "")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

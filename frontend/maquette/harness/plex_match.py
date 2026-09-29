"""R221 — only a disagreement waits; « Confirmer » and « Corriger » act on the Plex match itself.

A medium the pipeline shelved is not done until Plex shows it under the right
identity (§4). When Plex's match DISAGREES with the identity held, « À traiter »
holds the card (ruling 7) and it offers two verbs ON THAT MATCH (OPEN 9 = B):
« Confirmer », the match is the medium; « Corriger », match it to what we hold.

The disagreement is POSED (RULINGS 24): Star Trek's real settled row carries the
identity held, so the named state poses Plex's match to another real series of
the franchise; the backend compares Plex's real match with the identity held.

1. AN AGREEING MATCH NEVER WAITS: on the real row, Star Trek is not in
   « À traiter »;
2. posed, the card is blocked in « À traiter » and names BOTH sides — Plex's
   match in its sentence, beside the card's own title, which is the identity
   held; its current rung is NOT drawn done;
3. it offers « Confirmer » and « Corriger »;
4. « Corriger » sends the correction on the match's own operation, carrying
   the identity HELD, and opens no candidates screen; left and come back to,
   the card is still in « À traiter », its rung not done — until Plex's
   corrected match is checked;
5. « Confirmer » is answered by that operation, the card leaves « À traiter »,
   and « vérifié dans Plex » is DONE on its ladder.

RE-AIMED OUT LOUD (RULINGS 24): holds 3 and 4 of the first drawing read
« Corriger » opening the candidates screen and a pick sending the correction;
the operator's OPEN 9 = B puts the correction on the match itself, with the
identity held. Hold 1 is new: the card used to wait on any match.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page, chrome_launch_args
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
MATCHED = next((row for row in json.loads((SEEDS / "settled.json").read_text(encoding="utf-8"))
                if row.get("plexMatch")), {"title": "", "plexMatch": {"title": ""}})
OPERATION = "resolvePlexMatch"
# The named state that poses the disagreement, and the match it poses (RULINGS 24).
DISAGREES = "acq-card-plex-disagrees"
POSED = "Star Trek: Discovery"
# The last rung of the medium's ladder, as the layer holds it once answered.
LAST_RUNG = """(title) => {
  const queue = window.__queries?.getQueryData(["/api/acquisition/to-handle", ""]) || {};
  const card = [...(queue.arrivals || []), ...(queue.blocked || [])].find(one => one.title === title);
  const ladder = card?.ladder || [];
  return ladder.length ? ladder[ladder.length - 1].state : null;
}"""

CARD = """(title) => {
  const card = [...document.querySelectorAll('#view [data-part="card"]')]
    .find(one => one.querySelector('[data-part="card/title"]')?.textContent === title);
  if (!card) return null;
  return {
    states: [...card.querySelectorAll('[data-part="card/step"]')].map(cell => cell.dataset.state),
    reason: (card.querySelector('[data-part="card/reason"]') || {}).textContent || '',
    rung: card.querySelector('[data-part="card/meta"] [data-part="chip"]')?.textContent ?? null,
    confirm: [...card.querySelectorAll('[data-part="card/foot"]')].some(foot => foot.getAttribute('data-plex-confirm') === title),
    correct: [...card.querySelectorAll('[data-part="card/foot"]')].some(foot => foot.getAttribute('data-plex-correct') === title),
    tab: state.acqTab,
  };
}"""

# The words the current rung is drawn with while the match waits for his answer.
WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))
TO_CONFIRM = WORDS["surfaces"]["ladder"].get("toConfirm", "").replace(
    "{{rung}}", WORDS["surfaces"]["ladder"]["rungs"]["verified"])

# Every body the page sends to the match's operation, recorded where it is sent.
RECORD_SENT = """() => { if (window.__plexSent) return; window.__plexSent = [];
  const original = window.fetch;
  window.fetch = (input, init) => {
    const address = String(input?.url ?? input);
    if (address.includes('/plex-match')) window.__plexSent.push(init?.body ?? null);
    return original(input, init);
  };
}"""

SCREEN = """() => { const screen = document.querySelector('[data-part="screen"][data-open]');
  return screen ? { key: screen.dataset.key, text: screen.innerText,
    candidates: [...screen.querySelectorAll('[data-resolve]')].map(one => one.dataset.resolve) } : null; }"""

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
    journal = Journal("R221 — only a disagreement waits; « Confirmer » and « Corriger » on the Plex match")
    title = MATCHED["title"]
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── 1. the real row agrees, and an agreeing match never waits ────────
        await go(page, journal, "acq-todo-loaded")
        journal.check("an agreeing match never waits: on its real row, the medium is not in « À traiter »",
                      await page.evaluate(CARD, title) is None, title)

        # ── 2-3. the disagreement, posed ─────────────────────────────────────
        await go(page, journal, DISAGREES)
        card = await page.evaluate(CARD, title)
        journal.check("the disagreeing card is in « À traiter », blocked, naming Plex's match AND the identity held",
                      card is not None and card["tab"] == "todo" and "blocked" in card["states"]
                      and POSED in card["reason"], str(card))
        journal.check("it offers « Confirmer » and « Corriger » on that match",
                      card is not None and card["confirm"] and card["correct"], str(card))
        journal.check("its current rung is not drawn done: it waits for his answer",
                      card is not None and card["states"][-1:] != ["done"]
                      and bool(TO_CONFIRM) and card["rung"] == TO_CONFIRM,
                      f"{card and card['states'][-1:]} rung={card and card['rung']!r}")

        # ── 4. « Corriger », then away and back ──────────────────────────────
        await page.evaluate(RECORD_SENT)
        before = await page.evaluate(ANSWERED)
        await tap(page, "data-plex-correct", title)
        sent = [json.loads(body) for body in await page.evaluate("()=>window.__plexSent") if body]
        journal.check("« Corriger » is answered by the match's own operation",
                      await page.evaluate(ANSWERED) == before + 1, OPERATION)
        journal.check("and the correction carries the identity HELD",
                      len(sent) == 1 and sent[0].get("outcome") == "correct"
                      and (sent[0].get("identity") or {}).get("title") == title, str(sent))
        journal.check("and no candidates screen opens", await page.evaluate(SCREEN) is None, "")
        await page.evaluate("""()=>document.querySelector('[data-acqtab="now"]')?.click()""")
        await page.wait_for_timeout(ACTED)
        await page.evaluate("""()=>document.querySelector('[data-acqtab="todo"]')?.click()""")
        await page.wait_for_timeout(SETTLED)
        back = await page.evaluate(CARD, title)
        journal.check("left and come back to, the card is still in « À traiter », its rung not done",
                      back is not None and back["states"][-1:] != ["done"], str(back))

        # ── 5. « Confirmer » ─────────────────────────────────────────────────
        await go(page, journal, DISAGREES)
        before = await page.evaluate(ANSWERED)
        await tap(page, "data-plex-confirm", title)
        journal.check("« Confirmer » is answered by the match's own operation",
                      await page.evaluate(ANSWERED) == before + 1, OPERATION)
        journal.check("and the card leaves « À traiter »", await page.evaluate(CARD, title) is None, "")
        last = await page.evaluate(LAST_RUNG, title)
        journal.check("and « vérifié dans Plex » is done on its ladder", last == "done", str(last))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

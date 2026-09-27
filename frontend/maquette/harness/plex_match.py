"""R221 — « Confirmer » and « Corriger » act on the Plex match itself.

A medium the pipeline shelved is not done until Plex shows it under the right
identity (§4). When the match is to be confirmed, « À traiter » holds the card
(ruling 7) and it offers two verbs ON THAT MATCH — « Confirmer », the match is
the medium; « Corriger », it is not — rather than sending the operator through
the candidates screen for a match he can already judge.

Read on the one card the seeds hold for it, a derivation from Star Trek's real
settled row whose last rung waits for its confirmation:

1. the card is blocked on its ladder, in « À traiter », and names the match;
   its current rung, « vérifié dans Plex », is NOT drawn done: its word says it
   waits for his answer (ruling 30);
2. « Confirmer » is ANSWERED on the network by the match's own operation, and
   the card leaves « À traiter »;
3. « Corriger » SENDS NOTHING: the candidates screen opens on that medium,
   starting from the identity held — never « Aucun média identifié » — and
   « Retour » without a pick leaves the card in « À traiter », its match still
   to confirm;
4. « Corriger » then a pick: the answer is sent BY THE PICK, a correction
   carrying the identity picked, and the card leaves.

RE-AIMED OUT LOUD (round one, A1): hold 3 read « Corriger » answered on the tap
and the card gone — it certified the card consumed before anything was
corrected. It reads now that nothing is sent until a pick.
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
# What the screen says when no medium is identified — never on a Plex match.
NO_MEDIUM = WORDS["screens"]["resolution"]["noMediaIdentified"]

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
        journal.check("its current rung is not drawn done: it waits for his answer",
                      card is not None and card["states"][-1:] != ["done"]
                      and bool(TO_CONFIRM) and card["rung"] == TO_CONFIRM,
                      f"{card and card['states'][-1:]} rung={card and card['rung']!r}")

        before = await page.evaluate(ANSWERED)
        await tap(page, "data-plex-confirm", title)
        journal.check("« Confirmer » is answered by the match's own operation",
                      await page.evaluate(ANSWERED) == before + 1, OPERATION)
        journal.check("and the card leaves « À traiter »",
                      await page.evaluate(CARD, title) is None, "")

        # « CORRIGER », THEN « RETOUR »: nothing is sent, the card stays.
        await go(page, journal, "acq-todo-loaded")
        await page.evaluate(RECORD_SENT)
        before = await page.evaluate(ANSWERED)
        await tap(page, "data-plex-correct", title)
        screen = await page.evaluate(SCREEN)
        journal.check("« Corriger » sends nothing",
                      await page.evaluate(ANSWERED) == before, OPERATION)
        journal.check("the candidates screen opens on that medium, from the identity held",
                      screen is not None and screen["key"] == f"resolution:{title}"
                      and NO_MEDIUM not in screen["text"]
                      and MATCHED["plexMatch"]["title"] in screen["candidates"],
                      str(screen and (screen["key"], screen["candidates"], NO_MEDIUM in screen["text"])))
        await page.evaluate("""()=>document.querySelector('[data-part="screen/back"]')?.click()""")
        await page.wait_for_timeout(ACTED)
        back = await page.evaluate(CARD, title)
        journal.check("« Retour » without a pick leaves the card in « À traiter », its match to confirm",
                      back is not None and back["tab"] == "todo" and back["correct"]
                      and await page.evaluate(ANSWERED) == before, str(back))

        # « CORRIGER », THEN A PICK: the answer is sent by the pick, with it.
        picked = MATCHED["plexMatch"]["title"]
        await tap(page, "data-plex-correct", title)
        await page.evaluate(
            """(picked)=>[...document.querySelectorAll('[data-part="screen"][data-open] [data-resolve]')]
                 .find(one => one.dataset.resolve === picked)?.click()""", picked)
        await page.wait_for_timeout(ACTED)
        sent = [json.loads(body) for body in await page.evaluate("()=>window.__plexSent") if body]
        journal.check("the pick sends the correction, answered by the match's operation",
                      await page.evaluate(ANSWERED) == before + 1, OPERATION)
        journal.check("and the correction carries the identity picked",
                      len(sent) == 1 and sent[0].get("outcome") == "correct"
                      and (sent[0].get("identity") or {}).get("title") == picked, str(sent))
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

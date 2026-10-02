"""R404 — after a choice, the continuation is seen (L24, DOIT-5).

After « Choisir », the message says « le pipeline reprend jusqu'à la
médiathèque » — and nothing read the CARD going on afterwards. DOIT-5's owed
half is that progress, read where the operator looks, within the visit.

WHAT IS READ, once the pick's undo window has closed and its send has left:

  From « À traiter » (`acq-card-blocked`, « Lucky » stopped at « identifié »):
    1. the card has left « À traiter »;
    2. on « En cours », the card of the medium chosen stands PAST « identifié » —
       its rung word is one the ladder orders after it;
    3. and it no longer says why it was stopped — the blocked card's reason is
       not carried onto the card that goes on;
    4. the decision it waited on is no longer pending — it is settled, with the
       candidate chosen;
    4b. its journey sheet's « identifié » carries the time the choice was made
       — never « — » nor a word in its place (orchestrator, 2026-10-01: the act
       « Choisir » writes that rung's time).

  From « Corriger » (`acq-resolution-enqueued`, the engine's « Furious »):
    5. the decision « Corriger » created is no longer pending;
    6. the medium's journey sheet reads the NEW settled decision — the operator's
       choice, among the candidates « Corriger » filed.
"""
import asyncio
import json
import pathlib
import re

from common import ACTED, PANEL_IN, SETTLED, Journal, open_page, read_at, screen_arrives, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
RUNGS = WORDS["surfaces"]["ladder"]["rungs"]
ORDER = [stage["rung"] for stage in json.loads((SOURCE / "mocks/seeds/journey-stages.json").read_text(encoding="utf-8"))]
PAST_IDENTIFIED = {RUNGS[rung] for rung in ORDER[ORDER.index("identified") + 1:]}
BY_OPERATOR = WORDS["surfaces"]["decision"]["byOperator"].split("{{")[0]

# The pick waits out its undo window before it is sent (`lib/queue.ts`).
UNDO_WINDOW = 7000

PICK = """() => {
  const pick = document.querySelector('[data-part="screen"][data-open][data-key^="resolution:"] [data-part="card/pick"]');
  const choice = pick?.dataset.resolve ?? null;
  pick?.click();
  return choice;
}"""

CARDS = """() => [...document.querySelectorAll('#view [data-part="card"]')].map((card) => ({
  title: card.querySelector('[data-part="card/title"]')?.textContent.trim() ?? '',
  text: card.textContent.replace(/\\s+/g, ' '),
  chips: [...card.querySelectorAll('[data-part="chip"]')].map((chip) => chip.textContent.trim())}))"""

BLOCKED_REASON = next(card["reason"] for card in json.loads((SOURCE / "mocks/seeds/blocked.json").read_text(encoding="utf-8"))
                      if card["title"] == "Lucky")

# Re-read from the layer: no surface on « En cours » observes the decisions read.
PENDING = """async () => {
  await window.__queries.refetchQueries({queryKey: ['/api/decisions/'], type: 'all'});
  return (window.__queries.getQueryData(['/api/decisions/'])?.pending ?? []).map((one) => one.folder);
}"""

BLOCK = """() => {
  const block = document.querySelector('#sheet[data-open] [data-part="decision"]');
  const author = block?.querySelector('[data-decision-part="author"] > span:last-child')?.textContent.trim() ?? null;
  return {block: !!block, author};
}"""


async def after_the_undo(page):
    """Waits out the pick's undo window, its send, and the redraw.

    Args:
        page: The Playwright page.
    """
    await page.wait_for_timeout(UNDO_WINDOW + ACTED + SETTLED)
    await page.evaluate("() => window.__queries.invalidateQueries()")
    await page.wait_for_timeout(ACTED)


async def main():
    journal = Journal("R404 — after a choice, the continuation is seen")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await read_at(page, "acq-card-blocked", "() => true")
        await page.evaluate("() => window.__screens.resolution('Lucky')")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        choice = await page.evaluate(PICK)
        journal.check("« À traiter »: the screen of « Lucky » offers a candidate to choose", bool(choice), str(choice))
        await after_the_undo(page)
        todo = await page.evaluate(CARDS)
        journal.check("« À traiter »: the card has left « À traiter »",
                      not any(card["title"] in ("Lucky", choice) for card in todo), str([c["title"] for c in todo]))
        await page.locator("[data-acqtab=now]").first.click()
        await page.wait_for_timeout(ACTED + SETTLED)
        now = await page.evaluate(CARDS)
        card = next((card for card in now if card["title"] == choice), None)
        journal.check("« En cours »: the card of the medium chosen is there", card is not None,
                      str([c["title"] for c in now]))
        journal.check("« En cours »: it stands past « identifié »",
                      card is not None and any(chip in PAST_IDENTIFIED for chip in card["chips"]),
                      str(card and card["chips"]))
        journal.check("« En cours »: it no longer says why it was stopped",
                      card is not None and BLOCKED_REASON not in card["text"], str(card and card["text"][:160]))
        pending = await page.evaluate(PENDING)
        journal.check("the decision « Lucky » waited on is no longer pending", "Lucky" not in pending, str(pending))
        await page.evaluate("(title) => window.__panel.produce('journey', title)", choice)
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        identified = await page.evaluate("""(name) => {
          const row = [...document.querySelectorAll('#sheet[data-open] [data-part="key-value"]')]
            .find((one) => one.querySelector('span')?.textContent.trim() === name);
          return row ? row.querySelectorAll(':scope > span')[1]?.textContent.trim() ?? null : null;
        }""", RUNGS["identified"])
        journal.check("the journey's « identifié » carries the time of the choice",
                      bool(re.search(r"\d{1,2} h \d{2}", identified or "")), repr(identified))
        await page.evaluate("() => window.__panel.close()")
        await page.wait_for_timeout(ACTED)

        await read_at(page, "acq-resolution-enqueued", "() => true", wait=PANEL_IN + ACTED + SETTLED + SETTLED)
        await screen_arrives(page, "resolution:")
        folder = await page.evaluate("() => document.querySelector('[data-part=\"screen\"][data-open][data-key^=\"resolution:\"]')?.dataset.key.slice(11) ?? null")
        choice = await page.evaluate(PICK)
        journal.check("« Corriger »: the screen offers a candidate to choose", bool(choice), str(choice))
        await after_the_undo(page)
        pending = await page.evaluate(PENDING)
        journal.check("« Corriger »: the decision it created is no longer pending",
                      folder is not None and folder not in pending, str({"folder": folder, "pending": pending}))
        await page.evaluate("() => window.__panel.produce('journey', 'Furious')")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        block = await page.evaluate(BLOCK)
        journal.check("« Corriger »: the journey sheet reads the operator's new choice",
                      block["block"] and (block["author"] or "").startswith(BY_OPERATOR), str(block))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

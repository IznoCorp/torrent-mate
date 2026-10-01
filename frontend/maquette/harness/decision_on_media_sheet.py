"""R402 — one block, two sheets: the Médiathèque sheet says the decision in the same words (L24 S1, § 13).

Once a medium leaves Acquisition, the decision that identified it is read on its
Médiathèque sheet — THE SAME block as the journey sheet's, from the same
derivation, never a second module retyping its words (« une seule dérivation
par question »). On the Médiathèque the decision is found by the medium's
provider ids, which the sheet carries.

WHAT IS READ:

  1. `media-sheet-decision` (« The Bombing of Pan Am 103 », shelved, settled by
     the operator through a manual search): the block drawn, each row the words
     R401 derives from the settled read and `fr.json`;
  2. the journey sheet of the same medium draws the SAME rows, word for word;
  3. a sheet whose medium has no settled decision (`mediasheet-series`) draws
     no block.
"""
import asyncio

from common import Journal, open_page, read_at, browser_channel, chrome_launch_args, PANEL_IN, SETTLED
from decision_on_journey import expected
from playwright.async_api import async_playwright

SUBJECT = "The Bombing of Pan Am 103"

READ = """(root) => {
  const scope = root === 'sheet' ? document.querySelector('#sheet[data-open]')
                                 : document.querySelector('[data-part="screen"][data-open][data-key^="mediaSheet:"]');
  const block = scope?.querySelector('[data-part="decision"]');
  const rows = {};
  block?.querySelectorAll('[data-decision-part]').forEach((row) => {
    const spans = row.querySelectorAll(':scope > span');
    rows[row.dataset.decisionPart] = spans.length ? spans[spans.length - 1].textContent.trim() : row.textContent.trim();
  });
  const id = block?.dataset.decisionId;
  const settled = window.__queries.getQueryData(['/api/decisions/'])?.settled.find((one) => one.id === id) ?? null;
  return {open: !!scope, block: !!block, rows, settled};
}"""


async def main():
    journal = Journal("R402 — one block, two sheets")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        shelved = await read_at(page, "media-sheet-decision", READ, "screen", wait=PANEL_IN + SETTLED)
        journal.check("media-sheet-decision: the Médiathèque sheet draws the decision block",
                      shelved["open"] and shelved["block"], str({k: shelved[k] for k in ("open", "block")}))
        wanted = expected(shelved["settled"]) if shelved["settled"] else {}
        journal.check("the block names a decision the settled read holds", bool(wanted), str(shelved["settled"]))
        for part, words in wanted.items():
            journal.check(f"media-sheet-decision: « {part} » reads « {words} »", shelved["rows"].get(part) == words,
                          repr(shelved["rows"].get(part)))
        journal.check("nothing drawn beyond what the decision says",
                      bool(wanted) and set(shelved["rows"]) == set(wanted), str(sorted(shelved["rows"])))

        await page.evaluate("""(subject) => { window.__mocks.reset(); window.__mocks.placeAtPlexCheck(subject);
                                             window.__panel.produce('journey', subject); }""", SUBJECT)
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        journey = await page.evaluate(READ, "sheet")
        journal.check("the journey sheet of the same medium says the same rows, word for word",
                      journey["block"] and journey["rows"] == shelved["rows"],
                      str({"journey": journey["rows"], "media": shelved["rows"]}))

        none = await read_at(page, "mediasheet-series", READ, "screen", wait=PANEL_IN + SETTLED)
        journal.check("mediasheet-series: a medium with no settled decision draws no block",
                      none["open"] and not none["block"], str({k: none[k] for k in ("open", "block")}))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

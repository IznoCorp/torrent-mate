"""R212 — an arrival card says who asked for it, from the answer.

Every acquisition has a requester (§17). A card born of a direct add in
qBittorrent reads « ajouté par <name>, dans qBittorrent », the name being the
account that owns the Plex server (ruling 9); a card a follow asked for reads
its requester's name. The line is the card's LAST text line, so it never
competes with the title, the figure or the reason (§12).

THE NAME IS READ FROM THE ANSWER, never printed: the rule renames the seeded
account at runtime and reads every line follow it. A line composed from a
constant would read the old name after the rename, and this is where it falls.

The gesture that REASSIGNS a request is not drawn here: it is an act of the
rights model, and is born with it.

RE-AIMED OUT LOUD: `acq-card-requester` stood on « En cours », where the
arrival nobody followed was shelved today; that section left « En cours ». The
state stands on « À traiter », where the real world's arrivals nobody followed
wait for the operator's hand, and the holds read them there.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
ACCOUNT = json.loads((SEEDS / "account.json").read_text(encoding="utf-8"))["name"]
WORDS = json.loads((pathlib.Path(__file__).resolve().parents[1]
                    / "design/src/i18n/fr.json").read_text(encoding="utf-8"))
LINES = WORDS["surfaces"]["card"].get("requester", {})
# Another name, for the rename the rule reads the line follow.
RENAMED = "Nadia"

READ = """() => [...document.querySelectorAll('#view [data-part="card"]')]
  .map(card => {
    const texts = [...card.querySelectorAll('[data-part="card/body"] > span')]
      .map(span => span.textContent);
    const line = card.querySelector('[data-part="card/requester"]');
    return {
      title: card.querySelector('[data-part="card/title"]').textContent,
      line: line ? line.textContent : null,
      last: texts.length ? texts[texts.length - 1] === (line ? line.textContent : undefined) : false,
    };
  })
  .filter(card => card.line !== null)"""


def line_for(name, via):
    """The line a requester is drawn with."""
    return LINES.get(via, "").replace("{{name}}", name)


async def main():
    journal = Journal("R212 — an arrival card says who asked, from the answer")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('acq-card-requester');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-card-requester exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        cards = await page.evaluate(READ)
        direct = [card for card in cards if card["line"] == line_for(ACCOUNT, "qbittorrent")]
        journal.check("an arrival nobody followed reads « ajouté par <the account>, dans qBittorrent »",
                      bool(direct), str(cards))
        journal.check("every requester line is one of the two the answer can say",
                      bool(cards) and all(card["line"] in (line_for(ACCOUNT, "qbittorrent"),
                                                           line_for(ACCOUNT, "follow"))
                                          for card in cards), str(cards))
        journal.check("the requester line is the card's last text line",
                      bool(cards) and all(card["last"] for card in cards), str(cards))

        # THE SEED CHANGED TO ANOTHER NAME: every line follows it.
        renamed = await page.evaluate(
            """(name)=>{ if (!window.__mocks?.renameAccount) return false;
                window.__mocks.renameAccount(name);
                void window.__queries?.invalidateQueries({queryKey: ['/api/acquisition/to-handle']});
                return true; }""", RENAMED)
        await page.wait_for_timeout(ACTED)
        after = await page.evaluate(READ)
        journal.check("the account renamed, every line names the new name",
                      renamed and bool(after) and all(RENAMED in card["line"] and ACCOUNT not in card["line"]
                                                      for card in after),
                      str(after))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

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

EVERY ACQUISITION CARD SAYS ITS ORIGIN (round one, A9), and the rule reads every
card, not only those that drew a line. Said out loud: it FILTERED OUT the cards
without a line before reading, so the queue's three in-flight cards, which drew
none, could never make it fall. Now a card carries its requester's line, or
« origine inconnue » where the row names nobody; a folder DROPPED BY HAND —
the seeds say which — asked nobody, draws no line, and its subtitle says so.
Read on « À traiter » in the real world and on « En vol » in the loaded one,
where the queue's cards and the direct adds are.

THE LAST TEXT LINE, RE-READ OUT LOUD (ruling 32): a card of « À traiter » with
one foot lays its line beside that foot, so « last » is the body's last text OR
the line sharing the foot's row — below the reason either way, never competing
with the title, the figure or the reason.

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
# The rows the seeds say were dropped in the staging area by hand.
DROPPED = {row["title"] for name in ("stuck.json", "stuck-loaded.json")
           for row in json.loads((SEEDS / name).read_text(encoding="utf-8"))
           if row.get("droppedByHand")}
# The two states read: « À traiter » in the real world, « En vol » in the loaded one.
STATES = ("acq-card-requester", "acq-now-loaded")

READ = """() => [...document.querySelectorAll('#view [data-part="card"]')]
  .map(card => {
    const texts = [...card.querySelectorAll('[data-part="card/body"] > span')]
      .map(span => span.textContent);
    const line = card.querySelector('[data-part="card/requester"]');
    return {
      title: card.querySelector('[data-part="card/title"]').textContent,
      line: line ? line.textContent : null,
      // THE LAST TEXT LINE, in its body or beside its one foot (ruling 32).
      last: line !== null && (line.parentElement.querySelector('[data-part="card/foot"]') !== null
        || (texts.length ? texts[texts.length - 1] === line.textContent : false)),
    };
  })"""


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

        cards = []
        for state in STATES:
            answer = await page.evaluate(
                "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
            journal.check(f"the named state {state} exists", answer is None, answer or "")
            await page.wait_for_timeout(SETTLED)
            cards += await page.evaluate(READ)
        lined = [card for card in cards if card["title"] not in DROPPED]
        dropped = [card for card in cards if card["title"] in DROPPED]
        journal.check("every acquisition card says its origin, a folder dropped by hand aside",
                      len(lined) >= 6 and all(card["line"] is not None for card in lined),
                      str([card["title"] for card in lined if card["line"] is None]))
        journal.check("a folder dropped by hand draws no requester line",
                      len(dropped) >= 2 and all(card["line"] is None for card in dropped),
                      str([(card["title"], card["line"]) for card in dropped]))
        direct = [card for card in lined if card["line"] == line_for(ACCOUNT, "qbittorrent")]
        journal.check("an arrival nobody followed reads « ajouté par <the account>, dans qBittorrent »",
                      bool(direct), str(cards))
        journal.check("every line is one the answer can say, or « origine inconnue »",
                      all(card["line"] in (line_for(ACCOUNT, "qbittorrent"), line_for(ACCOUNT, "follow"),
                                           LINES.get("unknown"))
                          for card in lined), str(lined))
        journal.check("the requester line is the card's last text line",
                      all(card["last"] for card in lined), str(lined))

        # THE SEED CHANGED TO ANOTHER NAME: every line follows it.
        renamed = await page.evaluate(
            """(name)=>{ if (!window.__mocks?.renameAccount) return false;
                window.__mocks.renameAccount(name);
                void window.__queries?.invalidateQueries({queryKey: ['/api/acquisition/to-handle']});
                return true; }""", RENAMED)
        await page.wait_for_timeout(ACTED)
        after = [card for card in await page.evaluate(READ)
                 if card["line"] is not None and card["line"] != LINES.get("unknown")]
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

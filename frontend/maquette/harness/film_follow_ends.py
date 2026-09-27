"""R230 — a film's follow ends alone, when Plex confirms it; a series' never does.

Ruling 3: a film's follow ends by itself when the film is CONFIRMED in the
library — its last rung, « vérifié dans Plex », done — and it leaves « Suivis »
without a trace there. A series' follow never ends by itself.

The subject is Wicker, the one followed film in a live list (« à récupérer »):
its ladder laid one event away from the last rung is a DERIVATION from that real
row, shown as one (RULINGS 14). The event is the rung's move to done, which the
layer carries on `ItemProgressed` — the engine's per-item, per-step event; the
engine's own timing (it deletes a film's follow at detection) is a demand owed
(DESIGN § 6.2), and the maquette draws the ruling.

1. while its last rung is pending, the film is in « Suivis » — not ended one
   rung early;
2. the rung done, the film has left « Suivis »;
3. a followed series whose last rung is done is still there.

Red before the move: a followed film stays in « Suivis » for ever.

NO NAMED STATE (RULINGS 16): the one planned, a followed film one event away,
redrew « Suivis » and added three more instances of the `waiting` chip's light
contrast debt; it comes back with that tone's text token. The rule lays the
ladder itself, through the layer's own door, over « Suivis » as its list state
draws it.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
FOLLOWS = json.loads((SEEDS / "follows.json").read_text(encoding="utf-8"))
TAKEABLE = {row["title"] for row in json.loads((SEEDS / "takeable.json").read_text(encoding="utf-8"))}
FILM = next(one["title"] for one in FOLLOWS if one["kind"] == "movie" and one["title"] in TAKEABLE)
SERIES = next(one["title"] for one in FOLLOWS if one["kind"] == "show" and one.get("status") != "disabled")

TITLES = """() => [...document.querySelectorAll('#view [data-part="card/title"]')].map(one => one.textContent)"""


async def main():
    journal = Journal("R230 — a film's follow ends when Plex confirms it")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('acq-follows-list');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-follows-list exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        placed = await page.evaluate(
            "(title)=>{if(typeof window.__mocks?.placeAtPlexCheck!=='function') return false;"
            "window.__mocks.placeAtPlexCheck(title);"
            "window.__queries?.invalidateQueries({queryKey:['/api/acquisition/followed']}); return true;}", FILM)
        await page.wait_for_timeout(SETTLED)
        journal.check(f"« {FILM} »'s ladder is laid one event away from the last rung", placed, "")
        before = await page.evaluate(TITLES)
        journal.check(f"while its last rung is pending, « {FILM} » is in « Suivis »",
                      FILM in before and SERIES in before, str(before))

        confirmed = await page.evaluate(
            "(title)=>typeof window.__mocks?.confirmInPlex === 'function' && window.__mocks.confirmInPlex(title)", FILM)
        await page.wait_for_timeout(SETTLED)
        after = await page.evaluate(TITLES)
        journal.check("the rung done, the film has left « Suivis »",
                      confirmed and FILM not in after and SERIES in after, f"confirmed {confirmed}, {after}")

        confirmed = await page.evaluate(
            "(title)=>typeof window.__mocks?.confirmInPlex === 'function' && window.__mocks.confirmInPlex(title)", SERIES)
        await page.wait_for_timeout(SETTLED)
        series = await page.evaluate(TITLES)
        journal.check(f"a followed series confirmed in Plex, « {SERIES} », is still there",
                      confirmed and SERIES in series, f"confirmed {confirmed}, {series}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

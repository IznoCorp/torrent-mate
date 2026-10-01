"""R429 — the media sheet's cross-seed block, on the model (§ 19; § 17; DOIT-14).

DESIGN maquette-l18 § 3.6, § 5 (R-L18-w), F25; L17's R-L17-b and R-L17-k, carried.

1. R-L18-w — SHOWN TO WHOEVER SEES THE TRACKERS: on the owner's sheet of a medium whose
   origin torrent cross-seeds, the block is drawn, one row per (origin, tracker) pair, each
   in one of the operator's six words.
2. R-L17-b, CARRIED — ONE DERIVATION: the block's rows are the route's own answer, and that
   answer is the same pairs the downloads read carries on the origin's row (the Torrents
   tab's mark) — never a state computed here.
3. R-L17-k, CARRIED — ONE READ PER VISIT: opening the sheet asks `readMediaCrossSeed` once,
   and a wait on the sheet asks it again never.
4. R-L18-w — ABSENT FOR EVERY OTHER IDENTITY: signed in as each of the six seed identities
   (§ 2.2), none of which holds `trackers.view`, the same sheet draws no block and asks no
   read; the route forced by hand answers 403.
5. `media-cross-seed-hidden` is that absence as a named state.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
SEEDS = json.loads((SOURCE / "mocks/seeds/accounts.json").read_text(encoding="utf-8"))
IDENTITIES = [one["id"] for one in SEEDS["accounts"]]
OPERATION = "readMediaCrossSeed"
TITLE = "American Dad!"
STATES = ("active", "stopped", "trackerWithout", "error", "noMatch", "notSearched")

READ = """() => {
  const block = document.querySelector('[data-part="media/cross-seed"]');
  return {
    block: block !== null,
    rows: [...document.querySelectorAll('[data-part="media/cross-seed-pair"]')].map((row) => ({
      origin: row.dataset.origin, tracker: row.dataset.tracker, state: row.dataset.state,
      word: row.querySelector('[data-part="media/cross-seed-state"]')?.textContent || '' })),
    asked: window.__mocks.answered().filter((call) => call.operationId === 'readMediaCrossSeed').length,
    address: location.pathname,
  };
}"""

# The route's own answer and the downloads read's, asked once the sheet's own reads are counted.
ANSWERS = """async (address) => {
  const answer = await (await fetch(`/api${address}/cross-seed`)).json();
  const downloads = await (await fetch('/api/acquisition/downloads')).json();
  return { answer, downloads: downloads.downloads };
}"""

# One identity signed in AWAY from the sheet, its reads dropped: what was asked so far is counted.
AS = """async (identity) => {
  window.__go('profile');
  window.__mocks.setIdentity(identity);
  await window.__queries.resetQueries();
  return window.__mocks.answered().filter((call) => call.operationId === 'readMediaCrossSeed').length;
}"""

# The same sheet, opened again under that identity.
OPEN = "(title) => window.__screens.mediaSheet(title, window.__carriedFor(title) ?? undefined)"


async def main():
    journal = Journal("R429 — the media sheet's cross-seed block, on the model")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        words = {state: await page.evaluate("(k)=>window.__i18n.t(k)", f"screens.crossSeed.states.{state}")
                 for state in STATES}

        await page.evaluate("()=>window.__go('media-cross-seed')")
        await page.wait_for_timeout(SETTLED)
        owner = await page.evaluate(READ)
        journal.check("R-L18-w: the owner's sheet draws the cross-seed block", owner["block"], owner["address"])
        journal.check("R-L18-w: one row per pair", len(owner["rows"]) > 0, str(len(owner["rows"])))
        unworded = [row for row in owner["rows"] if row["state"] not in words or row["word"] != words[row["state"]]]
        journal.check("R-L18-w: every row reads one of the operator's six words", not unworded, str(unworded[:2]))

        await page.wait_for_timeout(2 * SETTLED)
        waited = await page.evaluate(READ)
        journal.check("R-L17-k: the sheet asks the block's read once per visit, and never again on a wait",
                      owner["asked"] == 1 and waited["asked"] == 1, f"{owner['asked']} then {waited['asked']}")

        answers = await page.evaluate(ANSWERS, owner["address"])
        served = sorted((origin["infoHash"], pair["tracker"], pair["state"])
                        for origin in answers["answer"].get("torrents", []) for pair in origin["pairs"])
        drawn = sorted((row["origin"], row["tracker"], row["state"]) for row in owner["rows"])
        journal.check("R-L17-b: the rows are the route's own answer", served and drawn == served,
                      f"{len(drawn)} drawn, {len(served)} served")
        marked = sorted((entry["infoHash"], pair["tracker"], pair["state"])
                        for entry in answers["downloads"] if entry.get("crossSeed")
                        and entry["infoHash"] in {origin for origin, _, _ in served}
                        for pair in entry["crossSeed"]["pairs"])
        journal.check("R-L17-b: the route's pairs are the Torrents tab's own for the same origins",
                      served == marked, f"{len(served)} / {len(marked)}")

        for identity in IDENTITIES:
            await page.evaluate("()=>window.__go('media-cross-seed')")
            await page.wait_for_timeout(SETTLED)
            before = await page.evaluate(AS, identity)
            await page.wait_for_timeout(SETTLED)
            await page.evaluate(OPEN, TITLE)
            await page.wait_for_timeout(SETTLED)
            read = await page.evaluate(READ)
            journal.check(f"R-L18-w: {identity} sees no block on the same sheet", not read["block"] and not read["rows"],
                          read["address"])
            journal.check(f"R-L18-w: {identity}'s sheet asks no cross-seed read", read["asked"] == before,
                          f"{read['asked'] - before} asked")
            status = await page.evaluate("async (a)=>(await fetch(`/api${a}/cross-seed`)).status", owner["address"])
            journal.check(f"R-L18-w: {identity} forcing the read is refused 403", status == 403, str(status))

        await page.evaluate("()=>window.__go('media-cross-seed-hidden')")
        await page.wait_for_timeout(SETTLED)
        hidden = await page.evaluate(READ)
        journal.check("media-cross-seed-hidden: the same sheet, no block", not hidden["block"], hidden["address"])

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

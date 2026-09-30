"""R-L17-i — « Chercher un cross-seed » is bounded, answered, visible, and offered only where the engine acts.

OPEN 3 = A: « une recherche bornée par les limites du moteur (quota quotidien,
délai) … une opération demandée au back-end »; round 9 Q10: the button is
« Chercher un cross-seed »; DOIT-4 / NE-DOIT-PAS-3: one ask, a visible « en
file », never « occupé »; § 17 point 1: nothing offered the engine would refuse;
F59: a queued search is seen to end in the same visit. L16-bis § 1.6: the
card's left drawer is the row's one « for » action — the manual cross-seed.
L17 DESIGN § 3.3.

1. the act is offered ONLY on a pair with no match, in error, not yet searched or
   stopped, not excluded, its original complete — never on « actif », « tracker
   sans cross-seed », an excluded pair, nor while the original still downloads
   (the pair's line says why, and says the TRUE reason);
1b. a cut pair, its exclusion undone, offers the search, and the search resolves
   it like a fresh one (§ 3.3: resuming IS « Chercher un cross-seed »); a title
   shared again offers the card's drawer;
2. `torrents-cross-seed-search`: a double tap on one pair asks ONCE; the pair
   reads « en file », never « occupé »; the engine's quota is drawn;
3. the search ends within the same visit: its outcome moves the pair on its own;
4. the card's left drawer is drawn on an origin with a pair to search, never on
   one without; its tap asks ONE search over every such pair;
5. `torrents-cross-seed-search-queued`: the quota spent, a search still reads
   « en file », and says it waits for tomorrow.

Red before the move: no pair offers a search, no card a left drawer.
"""
import asyncio

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

CROSS_SEEDING = "66e23ab395c438b7db4f7c855bd451d8bb1f0046"
REFUSED = "8d51568b1a4f46e1fb7e7b535b52a5203312fc28"
UNSEARCHED = "c44e8cd75bec37a8337175c6580e85d4e2079da3"
EXCLUDED = "e1af6819d9e3159e0aa191b534b6a66af4344788"
SWITCHED = "e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb"
COPY = "7c1e0b2f95c438b7db4f7c855bd451d8bb1f0046"
SEARCHABLE = {"noMatch", "error", "notSearched", "stopped"}
# The wait a pair still downloading says, in the interface's words.
DOWNLOADING_WAIT = "l'original est encore en téléchargement"  # french-ok: the rendered line this hold asserts
# How long the second finger of a double tap may wait for its button.
QUICK = 500
# Long enough for the engine's queued search to end (the layer's SEARCH_MILLISECONDS, 4 s).
SEARCH_ENDS = 6000

OFFERS = """() => {
  const origin = document.querySelector('#sheet[data-open] [data-part="torrents/cross-seed"]')?.dataset.entry;
  const entry = (window.__queries?.getQueryData(['/api/acquisition/downloads'])?.downloads || [])
    .find(one => one.infoHash === origin);
  return [...document.querySelectorAll('#sheet[data-open] [data-part="torrents/cross-seed-row"]')].map(row => ({
    tracker: row.dataset.tracker, state: row.dataset.state, excluded: row.dataset.excluded === 'true',
    downloading: !!entry && entry.progress < 1,
    offered: !!row.querySelector('[data-part="torrents/cross-seed-search"]'),
    queued: row.querySelector('[data-part="torrents/cross-seed-queued"]')?.textContent.trim() ?? null,
    wait: row.querySelector('[data-part="torrents/cross-seed-wait"]')?.textContent.trim() ?? null,
  }));
}"""
QUOTA = """() => document.querySelector('#sheet[data-open] [data-part="torrents/cross-seed-quota"]')?.textContent.trim() ?? null"""
SEARCHES = """() => (window.__mocks?.answered() || []).filter(call => call.operationId === 'searchCrossSeed').length"""
DRAWER = """(hash) => !!document.querySelector(
  `#view [data-part="torrents/row"][data-entry="${hash}"] [data-part="swipe/side"][data-side="left"] [data-cross-seed-search-all]`)"""
CONFIRM = '[data-part="dialog"][data-open] [data-part="dialog/button"][data-tone="danger"]'
TOAST = """() => document.getElementById('toast')?.textContent.trim() ?? ''"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def panel(page, entry):
    """Opens one entry's panel over the Torrents tab."""
    await page.evaluate("(entry) => window.__panel.produce('torrent', entry)", entry)
    await page.wait_for_timeout(ACTED)


async def tap(page, selector):
    """A finger on the first element a selector names; False when there is none to touch."""
    target = page.locator(selector)
    if not await target.count():
        return False
    await target.first.tap()
    await page.wait_for_timeout(ACTED)
    return True


async def main():
    journal = Journal("R-L17-i — « Chercher un cross-seed »: bounded, answered, visible, offered where the engine acts")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        rows = []
        await enter(page, "torrents-cross-seed")
        for entry in (f"{CROSS_SEEDING}:c411", f"{REFUSED}:c411", f"{UNSEARCHED}:c411", f"{EXCLUDED}:c411",
                      f"{SWITCHED}:c411"):
            await panel(page, entry)
            rows += await page.evaluate(OFFERS)
        wrong = [row for row in rows
                 if row["offered"] != (row["state"] in SEARCHABLE and not row["excluded"] and not row["downloading"])]
        journal.check("offered only on a pair with no match, in error, not yet searched or stopped, not excluded, "
                      "its original complete",
                      bool(rows) and any(row["offered"] for row in rows)
                      and any(row["state"] == "stopped" and row["offered"] for row in rows) and not wrong,
                      repr(wrong or [(row["tracker"], row["state"], row["offered"]) for row in rows]))
        await panel(page, f"{UNSEARCHED}:c411")
        waiting = await page.evaluate(OFFERS)
        journal.check("the original still downloading: nothing offered, each line says so, the TRUE reason",
                      len(waiting) == 2 and all(not row["offered"] and row["wait"] and DOWNLOADING_WAIT in row["wait"]
                                                for row in waiting)
                      and not await page.evaluate(DRAWER, UNSEARCHED),
                      repr(waiting))

        # ── 1b: resuming a cut pair IS « Chercher un cross-seed » ──────────
        await panel(page, f"{REFUSED}:c411")
        await tap(page, '#sheet[data-open] [data-cross-seed-include$=":tr4ker"]')
        included = {row["tracker"]: row for row in await page.evaluate(OFFERS)}
        journal.check("a cut pair, its exclusion undone, still reads « stoppé » and offers the search",
                      included.get("tr4ker", {}).get("state") == "stopped" and included["tr4ker"]["offered"],
                      repr(included.get("tr4ker")))
        searched = await tap(page, '#sheet[data-open] [data-cross-seed-search$=":tr4ker"]')
        await page.wait_for_timeout(SEARCH_ENDS)
        resumed = {row["tracker"]: row for row in await page.evaluate(OFFERS)}
        journal.check("the search resolves it like a fresh one",
                      searched and resumed.get("tr4ker", {}).get("state") == "active" and resumed["tr4ker"]["queued"] is None,
                      repr(resumed.get("tr4ker")))
        await enter(page, "torrents-cross-seed")
        await tap(page, '#sheet[data-open] [data-cross-seed-exclude-title]')
        await tap(page, CONFIRM)
        await tap(page, '#sheet[data-open] [data-cross-seed-include-title]')
        shared = await page.evaluate(OFFERS)
        await page.evaluate("() => window.__panel.close?.()")
        await page.wait_for_timeout(ACTED)
        journal.check("a title shared again: its stopped pairs offer the search, its card the drawer",
                      any(row["state"] == "stopped" and row["offered"] for row in shared)
                      and await page.evaluate(DRAWER, CROSS_SEEDING), repr(shared))

        await enter(page, "torrents-cross-seed-search")
        before = await page.evaluate(SEARCHES)
        button = page.locator('#sheet[data-open] [data-cross-seed-search$=":tr4ker"]')
        if await button.count():
            await button.first.tap()
        # THE SECOND FINGER, at once: the button may already have given way to « en file ».
        try:
            await button.first.tap(timeout=QUICK)
        except Exception:  # noqa: BLE001 — gone is the answer this hold wants
            pass
        await page.wait_for_timeout(ACTED)
        asked = await page.evaluate(SEARCHES) - before
        drawn = {row["tracker"]: row for row in await page.evaluate(OFFERS)}
        text = await page.evaluate("() => document.body.textContent")
        quota = await page.evaluate(QUOTA)
        journal.check("a double tap asks once; the pair reads « en file », never « occupé »",
                      asked == 1 and drawn.get("tr4ker", {}).get("queued") and "occupé" not in text,
                      f"asked {asked} · {drawn.get('tr4ker')}")
        journal.check("the engine's quota is drawn", quota is not None and "sur 20" in quota, repr(quota))
        await page.wait_for_timeout(SEARCH_ENDS)
        ended = {row["tracker"]: row for row in await page.evaluate(OFFERS)}
        journal.check("the search ends within the same visit: its outcome moves the pair on its own",
                      ended.get("tr4ker", {}).get("queued") is None and ended.get("tr4ker", {}).get("state") != "notSearched",
                      repr(ended.get("tr4ker")))

        await enter(page, "torrents-cross-seed-search")
        await page.evaluate("() => window.__panel.close?.()")
        await page.wait_for_timeout(ACTED)
        present = {hash_: await page.evaluate(DRAWER, hash_) for hash_ in (UNSEARCHED, EXCLUDED, COPY, CROSS_SEEDING)}
        journal.check("the card's left drawer is drawn on an origin with a pair to search, never on one without",
                      present[UNSEARCHED] and not present[EXCLUDED] and not present[COPY] and not present[CROSS_SEEDING],
                      repr(present))
        before = await page.evaluate(SEARCHES)
        await page.evaluate("(hash) => document.querySelector(`#view [data-part=\"torrents/row\"][data-entry=\"${hash}\"] "
                            "[data-cross-seed-search-all]`)?.click()", UNSEARCHED)
        await page.wait_for_timeout(ACTED)
        searches = await page.evaluate("() => window.__mocks?.crossSeedSearches()")
        journal.check("its tap asks ONE search, over every pair the engine would act on",
                      await page.evaluate(SEARCHES) - before == 1 and searches and searches[-1]["tracker"] is None,
                      repr(searches))

        await enter(page, "torrents-cross-seed-search-queued")
        drawn = {row["tracker"]: row for row in await page.evaluate(OFFERS)}
        await tap(page, '#sheet[data-open] [data-cross-seed-search$=":v3x.club"]')
        toast = await page.evaluate(TOAST)
        journal.check("the quota spent: a search still reads « en file », and says it waits for tomorrow",
                      drawn.get("tr4ker", {}).get("queued") and "demain" in toast and "occupé" not in toast,
                      f"{drawn.get('tr4ker')} · {toast!r}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

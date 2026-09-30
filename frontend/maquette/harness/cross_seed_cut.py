"""R-L17-f, R-L17-j — a torrent's cross-seed on one tracker is cut cleanly, and the cut is remembered.

Round 9 Q5, Q8: « on coupe le cross-seed d'un tracker depuis le torrent ; couper
retire l'entrée de qBittorrent sans ses fichiers »; M4: a cut confirmed in the
app closes its obligation « libérée », and the confirmation names it; round 9
Q11: « chaque coupure est mémorisée et exclut le titre des passages suivants »,
« Ne plus partager ce titre » cuts every tracker, and an exclusion undoes.
L17 DESIGN § 3.3 (the cut, S3-bis).

R-L17-f — the cut:
1. a finger on « Couper le cross-seed sur ce tracker » (President Curtis, tr4ker)
   asks first: without its files, the original keeps seeding on c411, the running
   obligation on tr4ker named;
2. confirmed: `cutCrossSeed` answered ONCE; the tr4ker entry gone from the
   Torrents tab; the pair « stoppé », by removal, dated; its obligation closed
   « libérée », never in breach; the original's own entry untouched.

R-L17-j — the memory:
3. the cut pair is excluded in that SAME call, and offers its undo;
4. the undo asks nothing: one `undoCrossSeedExclusion`, the pair searchable again;
5. « Ne plus partager ce titre » asks first, naming every running tracker and
   obligation; confirmed, ONE write: every pair excluded, every running one
   stopped, the title excluded — the original still seeding;
6. `torrents-cross-seed-exclude`: a title excluded whole offers its undo, which
   asks nothing and lifts it.

Red before the move: no pair offers a cut, no title an exclusion.
"""
import asyncio

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ORIGIN = "66e23ab395c438b7db4f7c855bd451d8bb1f0046"
COPY = "7c1e0b2f95c438b7db4f7c855bd451d8bb1f0046"
EXCLUDED = "e1af6819d9e3159e0aa191b534b6a66af4344788"

READ = """([origin, copy]) => {
  const downloads = window.__queries?.getQueryData(['/api/acquisition/downloads'])?.downloads || [];
  const entry = downloads.find(one => one.infoHash === origin);
  const obligation = (window.__queries?.getQueryData(['/api/acquisition/obligations'])?.items || [])
    .find(one => one.infoHash === copy);
  return {
    pairs: entry?.crossSeed?.pairs ?? null, titleExcluded: entry?.crossSeed?.titleExcluded ?? null,
    origin: !!entry, copyHeld: downloads.some(one => one.infoHash === copy),
    copyDrawn: !!document.querySelector(`#view [data-part="torrents/row"][data-entry="${copy}"]`),
    originDrawn: !!document.querySelector(`#view [data-part="torrents/row"][data-entry="${origin}"]`),
    obligation: obligation ? {released: obligation.releasedAt, breached: obligation.breachedAt} : null,
    undo: [...document.querySelectorAll('#sheet[data-open] [data-part="torrents/cross-seed-exclude"][data-undo]')]
      .map(node => node.dataset.crossSeedInclude ?? 'title'),
  };
}"""
DIALOG = """() => document.querySelector('[data-part="dialog"][data-open]')?.textContent ?? null"""
CALLS = """() => (window.__mocks?.answered() || []).map(call => call.operationId).filter(op => !op.startsWith('read'))"""
CONFIRM = '[data-part="dialog"][data-open] [data-part="dialog/button"][data-tone="danger"]'


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def tap(page, selector):
    """A finger on the first element a selector names; True when there was one."""
    target = page.locator(selector)
    if not await target.count():
        return False
    await target.first.tap()
    await page.wait_for_timeout(ACTED)
    return True


def pair(reading, tracker):
    """One pair of a reading, by its tracker."""
    return next((one for one in reading["pairs"] or [] if one["tracker"] == tracker), None)


async def main():
    journal = Journal("R-L17-f/j — a cross-seed is cut cleanly on one tracker, and the cut is remembered")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        argument = [ORIGIN, COPY]

        # ── f: the cut ──────────────────────────────────────────────────────
        await enter(page, "torrents-cross-seed")
        tapped = await tap(page, f'#sheet[data-open] [data-cross-seed-cut="{ORIGIN}:tr4ker"]')
        text = await page.evaluate(DIALOG)
        journal.check("a finger on the cut asks first: without its files, the original keeps seeding, the obligation named",
                      tapped and text is not None and "sans ses fichiers" in text and "c411" in text
                      and "President Curtis S01E10" in text and "tr4ker" in text, repr(text))
        calls = len(await page.evaluate(CALLS))
        await tap(page, CONFIRM)
        made = (await page.evaluate(CALLS))[calls:]
        after = await page.evaluate(READ, argument)
        cut = pair(after, "tr4ker")
        journal.check("confirmed: `cutCrossSeed` answered once, and nothing else", made == ["cutCrossSeed"], repr(made))
        journal.check("the tr4ker entry is gone from the Torrents tab; the original's own entry stays",
                      not after["copyHeld"] and not after["copyDrawn"] and after["origin"] and after["originDrawn"],
                      repr({k: after[k] for k in ("copyHeld", "copyDrawn", "origin", "originDrawn")}))
        journal.check("the pair reads « stoppé », by removal, dated",
                      cut is not None and cut["state"] == "stopped" and cut["stopCause"] == "removed"
                      and bool(cut["stoppedAt"]), repr(cut))
        journal.check("its obligation is closed « libérée », never left in breach",
                      after["obligation"] is not None and bool(after["obligation"]["released"])
                      and after["obligation"]["breached"] is None, repr(after["obligation"]))

        # ── j: the memory ───────────────────────────────────────────────────
        journal.check("the cut pair is excluded in that same call, and offers its undo",
                      cut is not None and cut["excluded"] is True and f"{ORIGIN}:tr4ker" in after["undo"], repr(after["undo"]))
        calls = len(await page.evaluate(CALLS))
        await tap(page, f'#sheet[data-open] [data-cross-seed-include="{ORIGIN}:tr4ker"]')
        made = (await page.evaluate(CALLS))[calls:]
        lifted = pair(await page.evaluate(READ, argument), "tr4ker")
        journal.check("the undo asks nothing: one `undoCrossSeedExclusion`, the pair no longer excluded",
                      await page.evaluate(DIALOG) is None and made == ["undoCrossSeedExclusion"]
                      and lifted is not None and lifted["excluded"] is False, repr((made, lifted)))

        await enter(page, "torrents-cross-seed")
        await tap(page, f'#sheet[data-open] [data-cross-seed-exclude-title="{ORIGIN}"]')
        text = await page.evaluate(DIALOG)
        journal.check("« Ne plus partager ce titre » asks first, naming every running tracker, its obligations, the original",
                      text is not None and "tr4ker" in text and "v3x.club" in text and "President Curtis S01E10" in text
                      and "c411" in text, repr(text))
        calls = len(await page.evaluate(CALLS))
        await tap(page, CONFIRM)
        made = (await page.evaluate(CALLS))[calls:]
        after = await page.evaluate(READ, argument)
        journal.check("confirmed: one write — every pair excluded, none running, the title excluded, the original seeding",
                      made == ["writeCrossSeedExclusion"] and after["titleExcluded"] is True
                      and all(one["excluded"] and one["state"] != "active" for one in after["pairs"])
                      and after["origin"] and not after["copyHeld"], repr((made, after["pairs"])))

        await enter(page, "torrents-cross-seed-exclude")
        before = await page.evaluate(READ, [EXCLUDED, COPY])
        calls = len(await page.evaluate(CALLS))
        await tap(page, f'#sheet[data-open] [data-cross-seed-include-title="{EXCLUDED}"]')
        made = (await page.evaluate(CALLS))[calls:]
        after = await page.evaluate(READ, [EXCLUDED, COPY])
        journal.check("torrents-cross-seed-exclude: a title excluded whole offers its undo, which asks nothing and lifts it",
                      before["titleExcluded"] is True and "title" in before["undo"] and await page.evaluate(DIALOG) is None
                      and made == ["undoCrossSeedExclusion"] and after["titleExcluded"] is False,
                      repr((before["undo"], made, after["titleExcluded"])))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

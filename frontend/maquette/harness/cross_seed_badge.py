"""R-L17-g, R-L17-h — the Trackers badge counts the cross-seed's failures, and its events move the page.

Organisation ruling 12: « chaque chose parle là où elle vit, et l'onglet de la
barre qui la porte prend un badge »; OPEN 8 = A: failures only — an ordinary
mismatch and « sans correspondance » never count; M5: a failure is a STATE,
leaving the count the moment its pair stops reading failed, with no « seen »
gesture. F59 and demand I: `CrossSeedInjected`, `CrossSeedRejected` and a
search's outcome (`CrossSeedSearched`) reach the page without a hand on it.
L17 DESIGN § 3.6 (S6).

R-L17-g — the badge's fifth term:
1. `bar-trackers-refused`: off its page, the Trackers tab counts exactly the five
   terms the server's answers carry, and the cross-seed's failures alone justify it;
2. a failure turned into an ordinary mismatch leaves the count, no gesture made;
3. a pair that ends « sans correspondance » never enters it; a transport
   failure enters it;
3b. an origin torrent removed from the client takes its pairs out of every
   count: its tracker's failures, its active torrents and the badge.

R-L17-h — the events are claimed:
4. each of the three events moves the open torrent panel's pair and the badge on
   its own, no finger on the page;
5. none of the three names is left in an exemption: the relay claims them.

Red before the move: the badge counts four terms and the three events move nothing.
"""
import asyncio
import pathlib

from common import SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

REFUSED = "8d51568b1a4f46e1fb7e7b535b52a5203312fc28"
DOWNLOADING = "c44e8cd75bec37a8337175c6580e85d4e2079da3"
LANTERNS = "0ff265e478d97d9eae4d1cabd13748e23b9e6cba"
CURTIS = "66e23ab395c438b7db4f7c855bd451d8bb1f0046"
ACQUISITION_LIVE = pathlib.Path(__file__).resolve().parents[1] / "design/src/features/acquisition/live.ts"
EVENTS = ("CrossSeedInjected", "CrossSeedRejected", "CrossSeedSearched")

BADGE = """() => document.querySelector('[data-part="shell/tab-bar"] [data-page="trackers"] [data-part="shell/tab-badge"]')
  ?.textContent.trim() ?? ''"""
SUM = """() => {
  const get = (address) => window.__queries?.getQueryData([address]);
  const trackers = get("/api/v1/trackers") ?? [];
  const downloads = get("/api/v1/acquisition/downloads")?.downloads ?? [];
  const obligations = get("/api/v1/acquisition/obligations")?.items ?? [];
  const active = new Set(downloads.map((entry) => `${entry.infoHash}:${entry.tracker}`));
  const under = trackers.filter((one) => one.alertThreshold !== null && one.ratio !== null
    && one.ratio < one.alertThreshold).length;
  const failed = trackers.filter((one) => one.disabled?.by === "failure").length;
  const breached = obligations.filter((one) => one.breachedAt !== null && one.satisfiedAt === null
    && one.releasedAt === null && active.has(`${one.infoHash}:${one.sourceTracker}`)).length;
  const unseen = trackers.reduce((total, one) => total + one.brokenObligations.filter((row) => !row.seen).length, 0);
  const crossSeed = trackers.reduce((total, one) => total + one.crossSeed.failed, 0);
  return { under, failed, breached, unseen, crossSeed, total: under + failed + breached + unseen + crossSeed };
}"""
CONFIRM = '[data-part="dialog"][data-open] [data-part="dialog/button"][data-tone="danger"]'
TR4KER = """() => (window.__queries?.getQueryData(['/api/v1/trackers']) || []).find(one => one.name === 'tr4ker')?.crossSeed ?? null"""
LINE = """() => document.querySelector('#view [data-tracker="tr4ker"] [data-part="trackers/cross-seed"]')?.textContent.trim() ?? null"""
ROW = """([hash, tracker]) => document.querySelector(
  `#sheet[data-open] [data-entry="${hash}"] [data-part="torrents/cross-seed-row"][data-tracker="${tracker}"]`)?.dataset.state ?? null"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def pose(page, infoHash, tracker, fields, event):
    """Moves one pair on the server, then emits the event that announces it; no finger on the page."""
    await page.evaluate("([hash, tracker, fields]) => window.__mocks?.poseCrossSeedPair(hash, tracker, fields)",
                        [infoHash, tracker, fields])
    await page.evaluate("([type, data]) => window.__mocks?.stream.emit(type, data)",
                        [event, {"info_hash": infoHash, "tracker": tracker}])
    await page.wait_for_timeout(SETTLED)


async def main():
    journal = Journal("R-L17-g/h — the Trackers badge counts the cross-seed's failures, and its events move the page")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await enter(page, "bar-trackers-refused")
        wanted = await page.evaluate(SUM)
        badge = await page.evaluate(BADGE)
        journal.check("bar-trackers-refused: off its page, the tab counts the five terms, the cross-seed's failures alone",
                      answer is None and wanted["crossSeed"] > 0 and wanted["total"] == wanted["crossSeed"]
                      and badge == str(wanted["total"]), f"{answer or ''} badge {badge!r} · served {wanted}")

        await enter(page, "torrents-cross-seed-refused")
        start = int(await page.evaluate(BADGE) or 0)
        await pose(page, REFUSED, "v3x.club", {"reason": "file_list_mismatch"}, "CrossSeedRejected")
        moved = await page.evaluate(BADGE)
        journal.check("a failure turned into an ordinary mismatch leaves the count, no gesture made, the row moved",
                      moved == str(start - 1) and await page.evaluate(ROW, [REFUSED, "v3x.club"]) == "error",
                      f"{start} → {moved!r}")
        await pose(page, DOWNLOADING, "tr4ker", {"state": "noMatch", "waitReason": None, "at": 1790600000},
                   "CrossSeedSearched")
        after = await page.evaluate(BADGE)
        journal.check("a pair ending « sans correspondance » never enters the count", after == moved, f"{moved!r} → {after!r}")
        await pose(page, LANTERNS, "v3x.club", {"reason": "fetch_failed"}, "CrossSeedRejected")
        after = await page.evaluate(BADGE)
        journal.check("a transport failure enters it", after == str(start), f"→ {after!r}")

        # ── 3b: a failure whose origin left the client is no longer counted ──
        await enter(page, "torrents-list")
        start = int(await page.evaluate(BADGE) or 0)
        before = await page.evaluate(TR4KER)
        await page.evaluate("(hash) => document.querySelector(`#view [data-torrent-remove^=\"${hash}:\"]`)?.click()",
                            LANTERNS)
        await page.wait_for_timeout(SETTLED)
        await page.locator(CONFIRM).first.tap()
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("() => window.__queries?.invalidateQueries()")
        await page.wait_for_timeout(SETTLED)
        after = await page.evaluate(TR4KER)
        badge = await page.evaluate(BADGE)
        journal.check("Lanterns removed: its tr4ker failure leaves tr4ker's count and the badge",
                      before and before["failed"] == 1 and after and after["failed"] == 0 and badge == str(start - 1),
                      f"{before} → {after} · badge {start} → {badge!r}")
        await enter(page, "torrents-list")
        await page.evaluate("(hash) => document.querySelector(`#view [data-torrent-remove^=\"${hash}:\"]`)?.click()",
                            CURTIS)
        await page.wait_for_timeout(SETTLED)
        await page.locator(CONFIRM).first.tap()
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("() => window.__queries?.invalidateQueries()")
        await page.wait_for_timeout(SETTLED)
        gone = await page.evaluate(TR4KER)
        journal.check("President Curtis removed: its active pair on tr4ker leaves the « N torrents »",
                      gone is not None and gone["active"] == 0, repr(gone))

        # ── h: each event moves the open panel's pair on its own ─────────────
        for event, fields, state in (
            ("CrossSeedInjected", {"state": "active", "reason": None, "at": 1790600000}, "active"),
            ("CrossSeedRejected", {"state": "error", "reason": "parse_failed", "at": 1790600000}, "error"),
            ("CrossSeedSearched", {"state": "noMatch", "reason": None, "at": 1790600000}, "noMatch"),
        ):
            await enter(page, "torrents-cross-seed-refused")
            await pose(page, REFUSED, "lacale", fields, event)
            drawn = await page.evaluate(ROW, [REFUSED, "lacale"])
            journal.check(f"{event} moves the open panel's pair on its own, to « {state} »", drawn == state, repr(drawn))

        exemptions = ACQUISITION_LIVE.read_text(encoding="utf-8").split("acquisitionLiveExemptions")[1].split("keys:")[0]
        journal.check("none of the three names is left in an exemption",
                      not any(f'"{name}"' in exemptions for name in EVENTS), exemptions.strip()[:120])

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

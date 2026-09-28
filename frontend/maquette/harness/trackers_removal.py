"""R263 — « Retirer de qBittorrent »: one entry leaves the client, its obligation closed.

Ruling 18 replaces a release of the obligation with the operator's own gesture
on a TORRENT's entry: it leaves qBittorrent, its files deleted by default, and a
running obligation it owed is CLOSED — `releasedAt` set, never left reading in
breach (round 10 M4). Nothing is destroyed without consent (NE-DOIT-PAS-6): only
the confirmation calls the operation.

1. `torrent-remove-confirm-obligation` opens a confirmation naming the torrent
   and its tracker, and nothing is sent before it is confirmed;
2. « Annuler » sends nothing and the row stays;
3. a finger on a row's « Retirer de qBittorrent », then the confirmation: the
   removal is answered on the network for THAT entry, its files deleted;
4. the row has left the tab — and the same files' other entry, on its other
   tracker, is still there (the grouped removal is not this rule's);
5. the obligation that entry owed reads `releasedAt` set, never `breachedAt`
   alone.

Red before the move: no row carries the gesture.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
DOWNLOADS = json.loads((SOURCE / "mocks/seeds/downloads.json").read_text(encoding="utf-8"))
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"].get("torrents", {})
OPERATION = "removeDownload"
# The entry removed: the first, which owes a running obligation and whose files
# a second entry seeds on another tracker.
REMOVED = DOWNLOADS[0]
SIBLING = next(entry for entry in DOWNLOADS[1:] if entry["name"] == REMOVED["name"])

ROWS = """() => [...document.querySelectorAll('#view [data-part="torrents/row"]')]
  .map(row => `${row.dataset.entry}:${row.dataset.tracker}`)"""
DIALOG = """() => {
  const open = document.querySelector('[data-part="dialog"][data-open]');
  return open ? open.textContent : null;
}"""
ANSWERED = """(operation) => (window.__mocks?.answered() || [])
  .filter(call => call.operationId === operation && call.status === 200)
  .map(call => decodeURIComponent(call.path))"""
PRESS = """(danger) => {
  const buttons = [...document.querySelectorAll('[data-part="dialog"][data-open] [data-part="dialog/button"]')];
  const button = buttons.find(one => (one.dataset.tone === 'danger') === danger);
  if (!button) return false; button.click(); return true;
}"""
OBLIGATION = """(hash) => (window.__queries?.getQueryData(["/api/acquisition/obligations"])?.items || [])
  .find(item => item.infoHash === hash) ?? null"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def main():
    journal = Journal("R263 — « Retirer de qBittorrent »: one entry leaves, its obligation closed")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        key = f"{REMOVED['infoHash']}:{REMOVED['tracker']}"
        sibling = f"{SIBLING['infoHash']}:{SIBLING['tracker']}"

        answer = await enter(page, "torrent-remove-confirm-obligation")
        journal.check("the named state torrent-remove-confirm-obligation exists", answer is None, answer or "")
        text = await page.evaluate(DIALOG)
        journal.check(f"the confirmation names « {REMOVED['title']} » and its tracker {REMOVED['tracker']}",
                      text is not None and REMOVED["title"] in text and REMOVED["tracker"] in text, repr(text))
        journal.check("nothing is sent before it is confirmed", not await page.evaluate(ANSWERED, OPERATION), "")
        cancelled = await page.evaluate(PRESS, False)
        await page.wait_for_timeout(ACTED)
        journal.check("« Annuler » sends nothing, and the row stays",
                      cancelled and not await page.evaluate(ANSWERED, OPERATION)
                      and key in await page.evaluate(ROWS) and await page.evaluate(DIALOG) is None,
                      f"cancelled {cancelled}")

        # A FINGER on the row's own gesture, then the confirmation.
        answer = await enter(page, "torrents-list")
        gesture = page.locator(
            f'#view [data-part="torrents/row"][data-entry="{REMOVED["infoHash"]}"]'
            f'[data-tracker="{REMOVED["tracker"]}"] [data-part="torrents/remove"]')
        journal.check("the row carries « Retirer de qBittorrent »",
                      await gesture.count() == 1 and WORDS.get("remove", "<no copy>") in (
                          await gesture.first.text_content() if await gesture.count() else ""), "")
        if await gesture.count():
            await gesture.first.tap()
            await page.wait_for_timeout(ACTED)
        confirmed = await page.evaluate(PRESS, True)
        await page.wait_for_timeout(SETTLED)
        answered = await page.evaluate(ANSWERED, OPERATION)
        removals = await page.evaluate("()=>window.__mocks?.trackerRemovals?.() ?? []")
        journal.check("confirmed, the removal of THAT entry is answered, its files deleted",
                      confirmed and any(path.endswith("/" + REMOVED["infoHash"]) for path in answered)
                      and {"infoHash": REMOVED["infoHash"], "deleteFiles": True} in removals,
                      f"confirmed {confirmed}, answered {answered}, removals {removals}")
        rows = await page.evaluate(ROWS)
        journal.check("the row has left the tab", key not in rows, str(rows))
        journal.check(f"the same files on {SIBLING['tracker']} are another entry, still there", sibling in rows,
                      str(rows))
        owed = await page.evaluate(OBLIGATION, REMOVED["infoHash"])
        journal.check("its obligation is closed: releasedAt set, never breachedAt alone",
                      owed is not None and owed.get("releasedAt") is not None, repr(owed))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

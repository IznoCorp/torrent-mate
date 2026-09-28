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
6. `torrent-remove-confirm` — an entry owing no running obligation — carries
   « Supprimer les fichiers », CHECKED by default, and names no obligation;
7. unchecked by a finger, then confirmed, the removal is answered with the files
   KEPT;
8. with a running obligation, the box unchecked, the confirmation still names
   the obligation and its tracker (round 10 M4 — whatever the box reads).

Red before the move: no row carries the gesture.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
DOWNLOADS = json.loads((SOURCE / "mocks/seeds/downloads.json").read_text(encoding="utf-8"))
ALL_WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
WORDS = ALL_WORDS["screens"].get("torrents", {})
WORDS_REMOVE = ALL_WORDS["verbs"].get("trackers", {}).get("remove", {})
OPERATION = "removeDownload"
# The entry removed: the first, which owes a running obligation and whose files
# a second entry seeds on another tracker.
REMOVED = DOWNLOADS[0]
# The entry whose obligation is met: it owes nothing running.
FREE = DOWNLOADS[1]
SIBLING = next(entry for entry in DOWNLOADS[1:] if entry["name"] == REMOVED["name"])

ROWS = """() => [...document.querySelectorAll('#view [data-part="torrents/row"]')]
  .map(row => `${row.dataset.entry}:${row.dataset.tracker}`)"""
BOX = """() => {
  const box = document.querySelector('[data-part="dialog"][data-open] [data-part="dialog/check"]');
  return box === null ? null : { checked: box.getAttribute('aria-checked'), text: box.textContent.trim() };
}"""
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

        # ── the files: kept, when the box is unchecked ───────────────────────
        answer = await enter(page, "torrent-remove-confirm")
        journal.check("the named state torrent-remove-confirm exists", answer is None, answer or "")
        box = await page.evaluate(BOX)
        text = await page.evaluate(DIALOG) or ""
        obligation = WORDS_REMOVE.get("obligation", "<no copy>").split("{{")[0].strip()
        journal.check("« Supprimer les fichiers » is offered, CHECKED by default",
                      box is not None and box["checked"] == "true"
                      and WORDS_REMOVE.get("deleteFiles", "<no copy>") in box["text"], repr(box))
        journal.check(f"{FREE['title']} owes no running obligation, and none is named",
                      FREE["title"] in text and obligation not in text, repr(text))
        check = page.locator('[data-part="dialog"][data-open] [data-part="dialog/check"]')
        if await check.count():
            await check.first.tap()
            await page.wait_for_timeout(ACTED)
        box = await page.evaluate(BOX)
        confirmed = await page.evaluate(PRESS, True)
        await page.wait_for_timeout(SETTLED)
        removals = await page.evaluate("()=>window.__mocks?.trackerRemovals?.() ?? []")
        journal.check("unchecked by a finger, then confirmed: the removal keeps the files",
                      box is not None and box["checked"] == "false" and confirmed
                      and {"infoHash": FREE["infoHash"], "deleteFiles": False} in removals,
                      f"box {box!r}, removals {removals}")

        # ── M4: a running obligation is named whatever the box reads ─────────
        await enter(page, "torrent-remove-confirm-obligation")
        check = page.locator('[data-part="dialog"][data-open] [data-part="dialog/check"]')
        if await check.count():
            await check.first.tap()
            await page.wait_for_timeout(ACTED)
        box = await page.evaluate(BOX)
        text = await page.evaluate(DIALOG) or ""
        journal.check(f"the box unchecked, the running obligation on {REMOVED['tracker']} is still named",
                      box is not None and box["checked"] == "false"
                      and obligation in text and REMOVED["tracker"] in text, f"box {box!r} · {text!r}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

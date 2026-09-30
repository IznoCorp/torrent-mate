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
   tracker, has left it in the SAME render: a removal takes every entry sharing
   its files, never one left behind;
5. the obligation that entry owed reads `releasedAt` set, never `breachedAt`
   alone.
6. `torrent-remove-confirm` — an entry owing no running obligation — carries
   « Supprimer les fichiers », CHECKED by default, and names no obligation;
7. unchecked by a finger, then confirmed, the removal is answered with the files
   KEPT;
8. with a running obligation, the box unchecked, the confirmation still names
   the obligation ON ITS OWN tracker, in the obligation's own sentence (round 10
   M4 — whatever the box reads);
8 bis. an obligation already BROKEN is never announced as running: the
   confirmation on its entry names no « Obligation en cours »;
8 ter. a removal the network cannot take is HELD, and never said done: no
   « a quitté qBittorrent », the row still there.
9. `torrent-remove-confirm-shared` — an entry owing nothing, whose files another
   entry seeds on another tracker under a running obligation — names the
   consequence (that other tracker's share ends too) and that tracker's running
   obligation.
10. `torrents-external-removal` — an entry removed BY HAND in qBittorrent, its
    obligation released cleanly — reads as simply GONE: no row, no word of it
    on the tab, its obligation `releasedAt` set, and no removal ever asked by
    the interface. The subject is POSED by `poseExternalRemoval`, a derivation
    shown as one: no real obligation has been released.

RE-AIMED OUT LOUD (L16-bis, the torrent card): the gesture was a text button
« Retirer de qBittorrent » on the row (`torrents/remove`); the row is a media card
now, and the gesture is its PANEL's action — a finger on the card's body, then on
the action. The swipe's drawer is its second door, held by R-L16bis-f
(`trackers_card.py`).

RE-AIMED OUT LOUD: hold 4 read « the same files' other entry is still there »,
the grouped removal being left for later. It is now this rule's — round 9 Q7:
the gesture takes every entry sharing the files with it, both gone from the tab
in the same render the operation answers, never one left behind in error.

RE-AIMED OUT LOUD (correction round C16): hold 8 found the tracker's name
anywhere in the dialog — the first paragraph already names it, so a sentence
« Obligation en cours sur . » stayed green; it now reads the obligation's own
sentence. Holds 8 bis and 8 ter are new, red while `hasRunningObligation`
ignored `breachedAt` and the removal ignored `HELD`.

Red before the move: no row carries the gesture.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
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
# The entry an external removal is posed on: its files shared with no other.
EXTERNAL = next(entry for entry in DOWNLOADS if entry["title"] == "Ted Lasso")
# The entry whose obligation is met: it owes nothing running.
FREE = DOWNLOADS[1]
BREACHED = next(entry for entry in DOWNLOADS if entry["title"] == "Star Trek: Strange New Worlds")
HELD_SUBJECT = next(entry for entry in DOWNLOADS if entry["title"] == "Lanterns")
# What the done toast says after the title it names.
DONE_WORDS = WORDS_REMOVE.get("done", "<no copy>").split("}}")[-1].strip(" »")
# EVERY toast shown, kept as it is shown: a later one replacing it must not hide it.
WATCH_TOASTS = """() => { window.__seenToasts = [];
  const toast = document.getElementById('toast');
  if (toast) new MutationObserver(() => window.__seenToasts.push(toast.textContent.trim()))
    .observe(toast, {childList: true, subtree: true, characterData: true}); }"""
TOASTS = """() => (window.__seenToasts || []).join(' | ')"""
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


async def open_removal(page, entry):
    """A finger on an entry's card body, then on its panel's « Retirer de qBittorrent »; True when both were there."""
    body = page.locator(f'#view [data-part="torrents/row"][data-entry="{entry["infoHash"]}"]'
                        f'[data-tracker="{entry["tracker"]}"] [data-part="card/body"]')
    if not await body.count():
        return False
    await body.first.tap()
    await page.wait_for_timeout(ACTED)
    action = page.locator(f'#sheet[data-open] [data-part="sheet/action"]'
                          f'[data-torrent-remove="{entry["infoHash"]}:{entry["tracker"]}"]')
    if not await action.count():
        return False
    words = await action.first.text_content()
    await action.first.tap()
    await page.wait_for_timeout(ACTED)
    return WORDS.get("remove", "<no copy>") in (words or "")


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def main():
    journal = Journal("R263 — « Retirer de qBittorrent »: one entry leaves, its obligation closed")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
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

        # A FINGER on the card, then on its panel's action, then the confirmation.
        answer = await enter(page, "torrents-list")
        journal.check("the card's panel carries « Retirer de qBittorrent »", await open_removal(page, REMOVED), "")
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
        journal.check(f"the same files on {SIBLING['tracker']} left with it, in the same render", sibling not in rows,
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
        journal.check(f"the box unchecked, the running obligation on {REMOVED['tracker']} is still named, in its own sentence",
                      box is not None and box["checked"] == "false"
                      and f"{obligation} {REMOVED['tracker']}" in text.replace("\xa0", " "), f"box {box!r} · {text!r}")

        # ── a BROKEN obligation is not a running one ─────────────────────────
        await enter(page, "torrent-obligation-breached")
        await open_removal(page, BREACHED)
        text = await page.evaluate(DIALOG) or ""
        journal.check(f"« {BREACHED['title']} », its obligation broken, is never announced « {obligation} … »",
                      BREACHED["title"] in text and obligation not in text, repr(text))
        await page.evaluate(PRESS, False)

        # ── a removal HELD offline is never said done ────────────────────────
        await enter(page, "torrents-list")
        await page.evaluate("()=>window.__mocks.setOffline(true)")
        await open_removal(page, HELD_SUBJECT)
        await page.evaluate(WATCH_TOASTS)
        confirmed = await page.evaluate(PRESS, True)
        await page.wait_for_timeout(SETTLED)
        toasts = await page.evaluate(TOASTS)
        rows = await page.evaluate(ROWS)
        await page.evaluate("()=>window.__mocks.setOffline(false)")
        journal.check(f"offline, « {HELD_SUBJECT['title']} »'s removal is held and never said « {DONE_WORDS} », "
                      "its row still there",
                      confirmed and DONE_WORDS not in toasts
                      and f"{HELD_SUBJECT['infoHash']}:{HELD_SUBJECT['tracker']}" in rows,
                      f"confirmed {confirmed} · toasts {toasts!r} · {len(rows)} row(s)")

        # ── shared files: the consequence, and the other tracker's obligation ─
        answer = await enter(page, "torrent-remove-confirm-shared")
        journal.check("the named state torrent-remove-confirm-shared exists", answer is None, answer or "")
        text = await page.evaluate(DIALOG) or ""
        consequence = WORDS_REMOVE.get("shared", "<no copy>").split("{{")[0].strip()
        journal.check(f"removing it from {SIBLING['tracker']} says the share on {REMOVED['tracker']} ends too",
                      SIBLING["title"] in text and consequence in text and REMOVED["tracker"] in text, repr(text))
        journal.check(f"and names the running obligation on {REMOVED['tracker']}",
                      obligation in text and f"{obligation} {REMOVED['tracker']}" in text.replace("\xa0", " "),
                      repr(text))

        # ── an external removal reads as gone ────────────────────────────────
        answer = await enter(page, "torrents-external-removal")
        journal.check("the named state torrents-external-removal exists", answer is None, answer or "")
        rows = await page.evaluate(ROWS)
        tab = await page.evaluate("()=>document.querySelector('#view')?.textContent ?? ''")
        owed = await page.evaluate(OBLIGATION, EXTERNAL["infoHash"])
        journal.check(f"« {EXTERNAL['title']} », removed by hand, is simply gone: no row, no word of it",
                      f"{EXTERNAL['infoHash']}:{EXTERNAL['tracker']}" not in rows and EXTERNAL["title"] not in tab,
                      f"{len(rows)} row(s)")
        journal.check("its obligation reads releasedAt set, and the interface asked no removal",
                      owed is not None and owed.get("releasedAt") is not None
                      and not await page.evaluate(ANSWERED, OPERATION)
                      and not await page.evaluate("()=>window.__mocks?.trackerRemovals?.() ?? []"),
                      repr(owed))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

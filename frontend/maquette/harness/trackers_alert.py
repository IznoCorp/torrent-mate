"""R264 — the ratio alert on the page: one derivation, three components, every reader agrees.

§ 18 alerts where the ratio lives, and nowhere else. Three of the alert's
components are read on the « Trackers » page: a tracker's ratio under its OWN
alert threshold, and a tracker whose identifier is refused, on its entry; an
obligation in breach on a torrent still active, on its « Torrents » row. Each
is read from the answers the layer serves, never from a copy: what every reader
draws is compared here against those answers.

1. `tracker-alert-active` — a threshold set above a tracker's ratio — marks THAT
   tracker's entry, and no entry whose ratio is at or above its own threshold,
   or that has none;
2. every entry's alert agrees with the summary served: under its threshold,
   marked; otherwise, not;
3. moving the threshold in its own source moves the mark in the render that
   follows — set under the ratio, the mark goes; set above again, it returns;
4. `tracker-identifier-refused` marks the refused tracker's entry, ONCE: the
   cause lives on the tracker, so no « Torrents » row of that tracker carries
   it — one unit for its tracker, never one per torrent (round 10 M5);
5. `torrent-obligation-breached` marks the row whose obligation is broken while
   its torrent is still active, never as running, and no other row;
6. every row's breach mark agrees with the obligations served.

RE-AIMED OUT LOUD — the alert's FOURTH component (round 10 Q4): an obligation
the engine broke whose torrent has already left the client is kept on its
tracker's entry until the operator marks it seen, and seen is not gone.

7. `tracker-broken-obligations` — its entry counts the UNSEEN broken obligations
   the summary serves for it, and no entry without one carries a count;
8. `tracker-broken-obligations-open` unfolds one row per broken obligation, its
   title and its date, each with « Vu »;
9. a finger on « Vu » asks the write ONCE for that obligation; the row STAYS,
   saying « Vue », and the count drops by one in the render that follows.

The threshold is the operator's own setting, posed by the same settings write
the entry makes. The refused identifier and the breach are DERIVATIONS, POSED
and shown as such (`poseIdentifierRefused`, `setObligationBreached`): no real
tracker refuses its identifier, and no real obligation has been broken — nor one broken whose torrent is gone
(`poseBrokenObligation`).

Red before the move: no entry and no row carries an alert.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TRACKERS = json.loads((SOURCE / "mocks/seeds/trackers.json").read_text(encoding="utf-8"))
DOWNLOADS = json.loads((SOURCE / "mocks/seeds/downloads.json").read_text(encoding="utf-8"))
SCREENS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]

# The subjects the states pose on: the first tracker under a threshold above its
# ratio, the last one refusing its identifier, and one entry's broken obligation.
ALERTED = TRACKERS[0]["name"]
REFUSED = TRACKERS[-1]["name"]
BREACHED = next(entry for entry in DOWNLOADS if entry["title"] == "Star Trek: Strange New Worlds")
SEEN_OPERATION = "markBrokenObligationSeen"
BROKEN_WORDS = SCREENS["trackers"]

ENTRIES = """() => [...document.querySelectorAll('#view [data-part="trackers/entry"]')].map(entry => ({
  name: entry.dataset.tracker,
  alert: entry.querySelectorAll('[data-part="trackers/alert"]').length,
  refused: entry.querySelectorAll('[data-part="trackers/identifier-refused"]').length,
}))"""
ROWS = """() => [...document.querySelectorAll('#view [data-part="torrents/row"]')].map(row => ({
  key: `${row.dataset.entry}:${row.dataset.tracker}`,
  tracker: row.dataset.tracker,
  breached: row.querySelectorAll('[data-part="torrents/obligation-breached"]').length,
  open: row.querySelector('[data-part="torrents/obligation-open"]') !== null,
  refused: row.querySelectorAll('[data-part="trackers/identifier-refused"]').length,
}))"""
COUNTS = """() => Object.fromEntries([...document.querySelectorAll('#view [data-part="trackers/entry"]')]
  .map(entry => [entry.dataset.tracker,
    entry.querySelector('[data-part="trackers/broken-obligations"]')?.textContent.trim() ?? null]))"""
BROKEN_ROWS = """(tracker) => [...document.querySelectorAll(
    `#view [data-part="trackers/entry"][data-tracker="${tracker}"] [data-part="trackers/broken-obligation-row"]`)]
  .map(row => ({
    hash: row.dataset.entry ?? null,
    title: row.querySelector('[data-part="trackers/broken-obligation-title"]')?.textContent.trim() ?? '',
    date: row.querySelector('[data-part="trackers/broken-obligation-date"]')?.textContent.trim() ?? '',
    control: row.querySelector('[data-part="trackers/broken-obligation-seen"]') !== null,
    seen: row.querySelector('[data-part="trackers/broken-obligation-seen-mark"]') !== null,
  }))"""
ANSWERED = """(operation) => (window.__mocks?.answered() || [])
  .filter(call => call.operationId === operation && call.status === 200)
  .map(call => decodeURIComponent(call.path))"""
SERVED = """(address) => window.__queries?.getQueryData([address]) ?? null"""
REFRESH = """async (address) => { await window.__queries?.invalidateQueries({queryKey: [address]}); }"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


def under(tracker):
    """Whether a served tracker is under its own alert threshold."""
    threshold, ratio = tracker.get("alertThreshold"), tracker.get("ratio")
    return threshold is not None and ratio is not None and ratio < threshold


async def entries_agree(page, journal, label):
    """Every entry's alert mark against the summary served; returns the entries drawn."""
    served = await page.evaluate(SERVED, "/api/trackers") or []
    drawn = {entry["name"]: entry for entry in await page.evaluate(ENTRIES)}
    wanted = {tracker["name"]: under(tracker) for tracker in served}
    journal.check(f"{label}: every entry's alert agrees with the summary served",
                  bool(wanted) and all((drawn.get(name, {}).get("alert") == 1) is marked
                                       for name, marked in wanted.items()),
                  f"served {wanted} · drawn {drawn}")
    return drawn


async def main():
    journal = Journal("R264 — the ratio alert on the page: one derivation, three components")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── the threshold ─────────────────────────────────────────────────
        answer = await enter(page, "tracker-alert-active")
        journal.check("the named state tracker-alert-active exists", answer is None, answer or "")
        drawn = await entries_agree(page, journal, "tracker-alert-active")
        others = [name for name, entry in drawn.items() if name != ALERTED and entry["alert"]]
        journal.check(f"{ALERTED}, under its own threshold, is marked, and no other tracker",
                      drawn.get(ALERTED, {}).get("alert") == 1 and not others, str(drawn))
        word = SCREENS["trackers"].get("alertBelowThreshold", "<no copy>").split("{{")[0].strip()
        text = await page.evaluate(
            f"""()=>document.querySelector('#view [data-part="trackers/entry"][data-tracker="{ALERTED}"] [data-part="trackers/alert"]')?.textContent ?? ''""")
        journal.check(f"the mark says it, « {word} … »", word in text, repr(text))

        ratio = next(tracker["ratio"] for tracker in TRACKERS if tracker["name"] == ALERTED)
        await page.evaluate(f"()=>window.__mocks?.poseAlertThreshold?.('{ALERTED}', {ratio / 2})")
        await page.evaluate(REFRESH, "/api/trackers")
        await page.wait_for_timeout(SETTLED)
        lowered = await entries_agree(page, journal, "threshold set under the ratio")
        await page.evaluate(f"()=>window.__mocks?.poseAlertThreshold?.('{ALERTED}', {ratio * 2})")
        await page.evaluate(REFRESH, "/api/trackers")
        await page.wait_for_timeout(SETTLED)
        raised = await entries_agree(page, journal, "threshold set above it again")
        journal.check("the mark moves with the threshold's own source, in the render that follows",
                      lowered.get(ALERTED, {}).get("alert") == 0 and raised.get(ALERTED, {}).get("alert") == 1,
                      f"under: {lowered.get(ALERTED)} · above: {raised.get(ALERTED)}")

        # ── the refused identifier: one unit, on its tracker ──────────────
        answer = await enter(page, "tracker-identifier-refused")
        journal.check("the named state tracker-identifier-refused exists", answer is None, answer or "")
        drawn = {entry["name"]: entry for entry in await page.evaluate(ENTRIES)}
        journal.check(f"{REFUSED}'s entry says its identifier is refused, once, and no other entry does",
                      drawn.get(REFUSED, {}).get("refused") == 1
                      and all(entry["refused"] == 0 for name, entry in drawn.items() if name != REFUSED),
                      str(drawn))
        await page.evaluate("()=>document.querySelector('[data-trackers-tab=\"torrents\"]')?.click()")
        await page.wait_for_timeout(SETTLED)
        rows = await page.evaluate(ROWS)
        journal.check(f"no « Torrents » row of {REFUSED} carries the refusal — one unit for its tracker",
                      any(row["tracker"] == REFUSED for row in rows) and all(row["refused"] == 0 for row in rows),
                      f"{[(row['key'][:6], row['tracker'], row['refused']) for row in rows]}")

        # ── the breach, on its row ─────────────────────────────────────────
        answer = await enter(page, "torrent-obligation-breached")
        journal.check("the named state torrent-obligation-breached exists", answer is None, answer or "")
        rows = {row["key"]: row for row in await page.evaluate(ROWS)}
        key = f"{BREACHED['infoHash']}:{BREACHED['tracker']}"
        journal.check(f"« {BREACHED['title']} »'s broken obligation is marked on its row, never as running",
                      rows.get(key, {}).get("breached") == 1 and rows.get(key, {}).get("open") is False,
                      repr(rows.get(key)))
        served = (await page.evaluate(SERVED, "/api/acquisition/obligations") or {}).get("items", [])
        broken = {f"{item['infoHash']}:{item['sourceTracker']}" for item in served
                  if item.get("breachedAt") is not None and item.get("satisfiedAt") is None
                  and item.get("releasedAt") is None}
        journal.check("every row's breach mark agrees with the obligations served",
                      bool(broken) and all((row["breached"] == 1) is (row_key in broken) for row_key, row in rows.items()),
                      f"broken {sorted(broken)} · marked {[k for k, row in rows.items() if row['breached']]}")

        # ── the broken obligations, unseen then seen ───────────────────────
        answer = await enter(page, "tracker-broken-obligations")
        journal.check("the named state tracker-broken-obligations exists", answer is None, answer or "")
        served = await page.evaluate(SERVED, "/api/trackers") or []
        unseen = {tracker["name"]: sum(1 for row in tracker.get("brokenObligations", []) if not row["seen"])
                  for tracker in served}
        counts = await page.evaluate(COUNTS)
        journal.check("each entry counts the UNSEEN broken obligations served for it, and none without one",
                      any(unseen.values()) and all(
                          (counts.get(name) is None) if number == 0 else (str(number) in (counts.get(name) or ""))
                          for name, number in unseen.items()),
                      f"served {unseen} · drawn {counts}")

        answer = await enter(page, "tracker-broken-obligations-open")
        journal.check("the named state tracker-broken-obligations-open exists", answer is None, answer or "")
        owner = next((tracker for tracker in served if tracker.get("brokenObligations")), {"name": "", "brokenObligations": []})
        rows = await page.evaluate(BROKEN_ROWS, owner["name"])
        journal.check(f"{owner['name']}'s list unfolds one row per broken obligation, its title and its date, each with « Vu »",
                      len(rows) == len(owner["brokenObligations"]) > 0
                      and all(row["title"] and row["date"] and row["control"] for row in rows),
                      str(rows))
        before = (await page.evaluate(COUNTS)).get(owner["name"]) or ""
        first = owner["brokenObligations"][0]["infoHash"] if owner["brokenObligations"] else ""
        control = page.locator(f'#view [data-part="trackers/broken-obligation-seen"][data-obligation-seen="{owner["name"]}:{first}"]')
        if await control.count():
            await control.first.tap()
            await page.wait_for_timeout(SETTLED)
        asked = [path for path in await page.evaluate(ANSWERED, SEEN_OPERATION) if first and first in path]
        rows = await page.evaluate(BROKEN_ROWS, owner["name"])
        after = (await page.evaluate(COUNTS)).get(owner["name"]) or ""
        left = len(owner["brokenObligations"]) - 1
        journal.check("« Vu » asks the write once for that obligation", len(asked) == 1, str(asked))
        journal.check("the row seen STAYS, and says it", any(row["hash"] == first and row["seen"] for row in rows)
                      and len(rows) == len(owner["brokenObligations"]), str(rows))
        journal.check("the count of the unseen drops by one in the render that follows",
                      str(left + 1) in before and (str(left) in after if left else after == ""),
                      f"{before!r} -> {after!r}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

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
3. a threshold typed in Réglages — the setting's OTHER door — and saved moves
   the mark and the bar's badge in the render that follows: the save refreshes
   what it moved, the rule refreshes nothing;
4. `tracker-identifier-refused` marks the refused tracker's entry, ONCE, and
   says since when: the cause lives on the tracker, so no « Torrents » row of
   that tracker carries it — one unit for its tracker, never one per torrent
   (round 10 M5), held on a tracker with SEVERAL entries;
5. `torrent-obligation-breached` marks the row whose obligation is broken while
   its torrent is still active, never as running, and no other row — « en
   infraction depuis le … », never S2's word « rompue », which names a
   different fact (the torrent gone);
6. every row's breach mark agrees with the obligations served.

RE-AIMED OUT LOUD — the alert's FOURTH component (round 10 Q4): an obligation
the engine broke whose torrent has already left the client is kept on its
tracker's entry until the operator marks it seen, and seen is not gone.

7. `tracker-broken-obligations` — its entry counts the UNSEEN broken obligations
   the summary serves for it, and no entry without one carries a count;
8. `tracker-broken-obligations-open` unfolds one row per broken obligation, its
   title and its date, each with « Vu »;
9. a finger on « Vu » asks the write ONCE for that obligation; the row STAYS,
   saying « Vue », and the count drops by one in the render that follows;
   « Vu » is a finger's target, 44 × 44 px at least.

RE-AIMED OUT LOUD — the alert's FOURTH READER, the bar (ruling 12: the tab that
carries a thing takes its badge):

10. on every state that poses a component, and on `bar-trackers-alert` away from
    the page, the bar's Trackers tab counts exactly the sum of the components
    the served answers hold — trackers under their threshold, refused
    identifiers, breaches on active entries, unseen broken obligations;
11. the ratio measured anew above the threshold, a `RatioMeasured` event moves
    the badge in the render that follows — the stream is claimed;
12. an obligation broken while nothing is open, a `SeedObligationBreached` event
    moves the tracker's summary and the badge with it.

RE-AIMED OUT LOUD (correction round C16): hold 3 posed the threshold and then
refreshed `/api/trackers` itself — the harness did the refresh the product never
did, and a saved threshold left the alert stale. It now saves through the
product, from Réglages, and refreshes nothing. Hold 4's single-unit reading
stood on a tracker with ONE entry, where per-tracker and per-torrent agree; it
now also reads a tracker with several. Hold 12 is new: the event's summary
refresh was held by no rule.

The threshold is the operator's own setting — a DEMAND: the engine's
`TrackerEconomyConfig` has no `alert_threshold` key yet
(`docs/reference/backend-demands-architecture.md`); the state that poses it says so. The refused identifier and the breach are DERIVATIONS, POSED
and shown as such (`poseIdentifierRefused`, `setObligationBreached`): no real
tracker refuses its identifier, and no real obligation has been broken — nor one broken whose torrent is gone
(`poseBrokenObligation`).

Red before the move: no entry and no row carries an alert.
"""
import asyncio
import datetime
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page
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
BADGE = """() => document.querySelector('[data-part="shell/tab-bar"] [data-page="trackers"] [data-part="shell/tab-badge"]')
  ?.textContent.trim() ?? null"""
# The sum the badge must draw, computed here from the three answers the layer serves.
SUM = """() => {
  const get = (address) => window.__queries?.getQueryData([address]);
  const trackers = get("/api/trackers") ?? [];
  const downloads = get("/api/acquisition/downloads")?.downloads ?? [];
  const obligations = get("/api/acquisition/obligations")?.items ?? [];
  const active = new Set(downloads.map((entry) => `${entry.infoHash}:${entry.tracker}`));
  const under = trackers.filter((one) => one.alertThreshold !== null && one.ratio !== null
    && one.ratio < one.alertThreshold).length;
  const refused = trackers.filter((one) => one.identifierRefusedSince !== null).length;
  const breached = obligations.filter((one) => one.breachedAt !== null && one.satisfiedAt === null
    && one.releasedAt === null && active.has(`${one.infoHash}:${one.sourceTracker}`)).length;
  const unseen = trackers.reduce((total, one) => total + one.brokenObligations.filter((row) => !row.seen).length, 0);
  return { under, refused, breached, unseen, total: under + refused + breached + unseen };
}"""
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
FINGER = 44
ALERT_SETTING = f"tracker:tracker.providers.{ALERTED}.economy.alert_threshold"
# A threshold far above any seeded ratio.
THRESHOLD = "9"
LANTERNS = next(entry for entry in DOWNLOADS if entry["title"] == "Lanterns")
TORRENT_WORDS = SCREENS["torrents"]
# The months as the interface writes a date, « 18 octobre ».
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",  # french-ok: the rendered date
          "août", "septembre", "octobre", "novembre", "décembre")  # french-ok: the rendered date
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


def day_of(epoch):
    """A moment as the interface's sentences write it: the day and the month."""
    moment = datetime.datetime.fromtimestamp(epoch)
    return f"{moment.day} {MONTHS[moment.month - 1]}"


async def tapped(page, selector):
    """A finger's tap on the one element the selector names; False when it cannot land."""
    target = page.locator(selector)
    if await target.count() != 1:
        return False
    await target.tap()
    await page.wait_for_timeout(ACTED)
    return True


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

        # THE OTHER DOOR: the threshold typed in Réglages and saved there. The
        # rule refreshes nothing — what moves, the save moved.
        await enter(page, "trackers-roster")
        before = {"sum": await page.evaluate(SUM), "badge": await page.evaluate(BADGE)}
        await enter(page, "settings-topic")
        await page.evaluate(f"()=>window.__panel.produce('setting', '{ALERT_SETTING}')")
        await page.wait_for_timeout(ACTED)
        walked = {"field": await tapped(page, '#sheetin [data-part="field/input"]')}
        if walked["field"]:
            await page.keyboard.press("Meta+A")
            await page.keyboard.type(THRESHOLD)
        walked["commit"] = await tapped(page, "#sheetin [data-commitsetting]")
        await page.go_back()
        await page.wait_for_timeout(ACTED)
        walked["save"] = await tapped(page, "#savebar [data-save]")
        await page.wait_for_timeout(SETTLED)
        after = {"sum": await page.evaluate(SUM), "badge": await page.evaluate(BADGE)}
        walked["bar"] = await tapped(page, '#nav button[data-page="trackers"]')
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("()=>document.querySelector('[data-trackers-tab=\"trackers\"]')?.click()")
        await page.wait_for_timeout(SETTLED)
        drawn = {entry["name"]: entry for entry in await page.evaluate(ENTRIES)}
        journal.check(f"a threshold of {THRESHOLD} saved in Réglages moves {ALERTED}'s mark and the bar's badge "
                      "in the render that follows — the rule refreshing nothing",
                      before["sum"]["under"] == 0 and after["sum"]["under"] == 1
                      and after["badge"] == str(after["sum"]["total"]) and drawn.get(ALERTED, {}).get("alert") == 1,
                      f"walked {walked}: before {before} · after {after} · {ALERTED} {drawn.get(ALERTED)}")

        # ── the refused identifier: one unit, on its tracker ──────────────
        answer = await enter(page, "tracker-identifier-refused")
        journal.check("the named state tracker-identifier-refused exists", answer is None, answer or "")
        drawn = {entry["name"]: entry for entry in await page.evaluate(ENTRIES)}
        journal.check(f"{REFUSED}'s entry says its identifier is refused, once, and no other entry does",
                      drawn.get(REFUSED, {}).get("refused") == 1
                      and all(entry["refused"] == 0 for name, entry in drawn.items() if name != REFUSED),
                      str(drawn))
        since = next((tracker.get("identifierRefusedSince") for tracker in await page.evaluate(SERVED, "/api/trackers") or []
                      if tracker["name"] == REFUSED), None)
        said = await page.evaluate(
            f"""()=>document.querySelector('#view [data-part="trackers/entry"][data-tracker="{REFUSED}"] [data-part="trackers/identifier-refused"]')
                ?.textContent.trim() ?? ''""")
        journal.check(f"and says since when, « … depuis le {day_of(since) if since else '?'} »",
                      since is not None and f"depuis le {day_of(since)}" in said, repr(said))
        # SEVERAL ENTRIES under one refused identifier: still one unit. POSED on
        # the tracker holding the most entries, the summary asked again — a
        # server fact the interface has no write for.
        many = max(TRACKERS, key=lambda tracker: sum(1 for entry in DOWNLOADS if entry["tracker"] == tracker["name"]))["name"]
        await page.evaluate(f"()=>window.__mocks?.poseIdentifierRefused?.('{many}')")
        await page.evaluate(REFRESH, "/api/trackers")
        await page.wait_for_timeout(SETTLED)
        wanted = await page.evaluate(SUM)
        badge = await page.evaluate(BADGE)
        entries = sum(1 for entry in DOWNLOADS if entry["tracker"] == many)
        journal.check(f"{many}, refusing too with {entries} entries, is ONE more unit: the badge counts "
                      "the refused trackers, never their torrents",
                      entries >= 2 and wanted["refused"] == 2 and badge == str(wanted["total"]),
                      f"badge {badge!r} · served {wanted}")
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
        broken_at = next((item.get("breachedAt") for item in
                          (await page.evaluate(SERVED, "/api/acquisition/obligations") or {}).get("items", [])
                          if item["infoHash"] == BREACHED["infoHash"]), None)
        chip = await page.evaluate(
            f"""()=>document.querySelector('#view [data-part="torrents/row"][data-entry="{BREACHED['infoHash']}"] [data-part="torrents/obligation-breached"]')
                ?.textContent.trim() ?? ''""")
        opening = TORRENT_WORDS.get("obligationBreached", "<no copy>").split("{{")[0].strip()
        journal.check(f"its chip says « {opening} {day_of(broken_at) if broken_at else '?'} », never « rompue »",
                      broken_at is not None and chip.startswith(opening) and day_of(broken_at) in chip
                      and "rompue" not in chip.lower(), repr(chip))
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
        box = await page.evaluate(
            """()=>{const box=document.querySelector('#view [data-part="trackers/broken-obligation-seen"]')?.getBoundingClientRect();
                 return box ? [Math.round(box.width), Math.round(box.height)] : null;}""")
        journal.check(f"« Vu » is a finger's target, {FINGER} × {FINGER} px at least",
                      box is not None and min(box) >= FINGER, str(box))
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

        # ── the fourth reader: the bar ──────────────────────────────────────
        for state in ("tracker-alert-active", "tracker-identifier-refused", "torrent-obligation-breached",
                      "tracker-broken-obligations", "bar-trackers-alert"):
            answer = await enter(page, state)
            wanted = await page.evaluate(SUM)
            badge = await page.evaluate(BADGE)
            journal.check(f"{state}: the bar's Trackers tab counts the sum of the components, {wanted['total']}",
                          answer is None and wanted["total"] > 0 and badge == str(wanted["total"]),
                          f"{answer or ''} badge {badge!r} · served {wanted}")
        ratio = next(tracker["ratio"] for tracker in TRACKERS if tracker["name"] == ALERTED)
        await page.evaluate(f"()=>window.__mocks?.poseTrackerRatio?.('{ALERTED}', {ratio * 4})")
        await page.evaluate("()=>window.__mocks?.stream.emit('RatioMeasured', {})")
        await page.wait_for_timeout(SETTLED)
        wanted = await page.evaluate(SUM)
        badge = await page.evaluate(BADGE)
        journal.check("a RatioMeasured event above the threshold moves the badge in the render that follows",
                      wanted["under"] == 0 and badge == (str(wanted["total"]) if wanted["total"] else None),
                      f"badge {badge!r} · served {wanted}")

        # ── SeedObligationBreached moves the summary ─────────────────────
        await enter(page, "torrents-list")
        quiet = await page.evaluate(SUM)
        await page.evaluate(f"()=>window.__mocks?.poseBrokenObligation?.('{LANTERNS['infoHash']}')")
        await page.evaluate("()=>window.__mocks?.stream.emit('SeedObligationBreached', {})")
        await page.wait_for_timeout(SETTLED)
        moved = await page.evaluate(SUM)
        badge = await page.evaluate(BADGE)
        journal.check("a SeedObligationBreached event moves the tracker's summary — the broken obligation "
                      "counted — and the badge with it",
                      quiet["unseen"] == 0 and moved["unseen"] >= 1 and badge == str(moved["total"]),
                      f"before {quiet} · after {moved} · badge {badge!r}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

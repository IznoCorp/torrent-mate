"""R261 — the « Trackers » tab: one entry per tracker, its own ratio, never averaged.

§ 18 reads the ratio PER TRACKER and never folds the trackers into one figure
(NE-DOIT-PAS-1: a number drawn is the number the server said). The tab draws one
collapsed entry per configured tracker, in the configuration's order, each with
the ratio, the trend in words and the Download / Upload volumes its OWN answer
carries — compared here against the very seed the layer serves.

1. `trackers-roster` draws one entry per tracker, in the answer's order;
2. each entry's ratio is its own tracker's, and the mean of all of them is drawn
   on no entry whose own ratio differs from it;
3. each entry's trend is said in words, its own tracker's;
4. each entry's volumes are its own tracker's, Download and Upload;
5. `trackers-roster-empty` — no tracker configured — draws no entry and says so;
5 bis. each entry's ratio sits on its name's own line, inside its own row —
   never floating under it, where it reads as the next tracker's.

RE-AIMED OUT LOUD (the « Torrents » tab): the same clause, read on the other
tab. A torrent's ratio is ITS OWN on the tracker the entry runs on, computed on
the torrent's own size — never on the tracker's download volume, which is the
division a cross-seed would make by zero. So, on `torrents-list`:

6. one row per download entry, in the answer's order — a torrent on two
   trackers is two rows;
7. each row names its own tracker, and draws its own ratio, never one computed
   on the tracker's volume;
8. each row's deadline is its own — its day AND its month — or says there is
   none;
9. each row's origin mark says origin grab or cross-seed, as its entry does,
   and is DRAWN — a box a finger's eye can see, never 0×0 — and its ratio sits
   on its title's own line, inside its own row;
10. an open obligation is a MARK on its own row, never on a row that owes none;
11. a finger on a row's title lands on its medium's sheet, by provider id.
12. `torrents-list-filtered` draws the named tracker's rows alone, and SAYS the
    filter: « Filtré sur <tracker> », with « Tout voir »;
13. a finger on « Tout voir », landed cold on a filtered address, draws every
    row again, drops `tracker` from the address and pushes nothing;
14. `torrents-empty` — nothing active anywhere — draws no row, says so, and
    shows no filter;
15. `torrents-empty-filtered` — nothing on the filtered tracker — says a
    DIFFERENT sentence, and still shows the filter it can be lifted from;
16. `torrents-obligation-done` — an obligation met, the torrent still seeding —
    marks it « terminée » on its row, never « en cours ».

A direct add is a card of Acquisition only once it has arrived: until then,
the download client's entry is where it is read — here, like any other active
entry. The subject is read off the seeds, never named: the
entry the client is still downloading.

17. the downloading entry is a row of `torrents-list`, under its own title, and
    a finger on that title lands on its medium's sheet, by provider id.

RE-AIMED OUT LOUD (hold 9, correction round C16): it read the mark's
`data-origin` alone, and stayed green over a mark drawn at 0×0 px and a ratio
floating between two rows; it now reads the mark's box and the ratio's line.
Hold 8 read the day alone, and a deadline a month late kept it green; it now
reads the month too.

`torrents-obligation-done` and `torrent-remove-confirm` read an obligation MET
that the real data does not hold (`acquire.db` has no satisfied row): it is
POSED by `setObligationSatisfied`, a derivation shown as one in both states;
the backend reads `seed_obligation.satisfied_at`.

Red before the move: the tab draws no entry.
"""
import asyncio
import datetime
import json
import pathlib

from common import ACTED, PAGE_PATHS, PROTOTYPE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TRACKERS = json.loads((SOURCE / "mocks/seeds/trackers.json").read_text(encoding="utf-8"))
DOWNLOADS = json.loads((SOURCE / "mocks/seeds/downloads.json").read_text(encoding="utf-8"))
OBLIGATIONS = json.loads((SOURCE / "mocks/seeds/obligations.json").read_text(encoding="utf-8"))
SCREENS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]
WORDS = SCREENS["trackers"]
TORRENT_WORDS = SCREENS.get("torrents", {})
# A billion bytes, the « Go » the interface writes volumes in.
GIGABYTE = 1_000_000_000
# The months as the interface writes a date, « 18 octobre ».
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",  # french-ok: the rendered date
          "août", "septembre", "octobre", "novembre", "décembre")  # french-ok: the rendered date

# Whether one box sits on another's line: their vertical extents overlap, and it
# lies to the right of it — the name and its value on one line.
ON_LINE = """(value, name) => {
  if (!value || !name) return false;
  const v = value.getBoundingClientRect(), n = name.getBoundingClientRect();
  return v.width > 0 && v.top < n.bottom && v.bottom > n.top && v.left >= n.right - 1;
}"""
ENTRIES = """() => [...document.querySelectorAll('#view [data-part="trackers/entry"]')].map(entry => ({
  name: entry.dataset.tracker,
  onLine: (%s)(entry.querySelector('[data-part="trackers/ratio"]'), entry.querySelector('[data-part="trackers/name"]')),
  ratio: entry.querySelector('[data-part="trackers/ratio"]')?.textContent.trim() ?? null,
  trend: entry.querySelector('[data-part="trackers/trend"]')?.textContent.trim() ?? null,
  volumes: entry.querySelector('[data-part="trackers/volumes"]')?.textContent.trim() ?? null,
}))""" % ON_LINE
ROWS = """() => [...document.querySelectorAll('#view [data-part="torrents/row"]')].map(row => {
  const text = (part) => row.querySelector(`[data-part="${part}"]`)?.textContent.trim() ?? null;
  return {
    hash: row.dataset.entry ?? null,
    tracker: text("torrents/tracker"),
    ratio: text("torrents/ratio"),
    deadline: text("torrents/deadline"),
    origin: row.querySelector('[data-part="torrents/origin"]')?.dataset.origin ?? null,
    mark: (() => { const box = row.querySelector('[data-part="torrents/origin"]')?.getBoundingClientRect();
      return box ? [Math.round(box.width), Math.round(box.height)] : null; })(),
    onLine: (%s)(row.querySelector('[data-part="torrents/ratio"]'), row.querySelector('[data-part="torrents/title"]')),
    open: row.querySelector('[data-part="torrents/obligation-open"]') !== null,
    done: row.querySelector('[data-part="torrents/obligation-done"]') !== null,
  };
})""" % ON_LINE
FILTER = """() => {
  const line = document.querySelector('#view [data-part="torrents/filter"]');
  return line === null ? null : {
    text: line.textContent.trim(),
    clear: line.querySelector('[data-part="torrents/filter-clear"]') !== null,
  };
}"""
EMPTY = """() => document.querySelector('#view [data-part="empty-state"]')?.textContent.trim() ?? null"""


def french(number, decimals):
    """The number as the interface writes it: a decimal comma, fixed decimals."""
    return f"{number:.{decimals}f}".replace(".", ",")


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


def owed(download):
    """The obligation this entry owes on its own tracker, or None."""
    return next((obligation for obligation in OBLIGATIONS
                 if obligation["infoHash"] == download["infoHash"]
                 and obligation["sourceTracker"] == download["tracker"]), None)


async def torrents(page, journal):
    """Holds 6 to 11, on the « Torrents » tab."""
    answer = await enter(page, "torrents-list")
    journal.check("the named state torrents-list exists", answer is None, answer or "")
    drawn = await page.evaluate(ROWS)
    journal.check("one row per download entry, in the answer's order",
                  [(row["hash"], row["tracker"]) for row in drawn]
                  == [(entry["infoHash"], entry["tracker"]) for entry in DOWNLOADS],
                  f"{len(drawn)} row(s) against {len(DOWNLOADS)} entries")
    volumes = {tracker["name"]: tracker["downloadedBytes"] for tracker in TRACKERS}
    prefix = TORRENT_WORDS.get("deadline", "<no copy>").split("{{")[0].strip()
    for index, entry in enumerate(DOWNLOADS):
        row = drawn[index] if index < len(drawn) else {}
        name = f"{entry['title']} on {entry['tracker']}"
        own = french(entry["ratio"], 2)
        # WHAT THE TRACKER'S VOLUME WOULD GIVE: the entry's uploaded bytes (its
        # ratio on its own size) divided by the tracker's download volume.
        on_volume = french(entry["ratio"] * entry["sizeBytes"] / volumes[entry["tracker"]], 2)
        ratio = row.get("ratio") or ""
        journal.check(f"{name}: its tracker is its own", row.get("tracker") == entry["tracker"],
                      repr(row.get("tracker")))
        journal.check(f"{name}: its ratio is its own, {own}, on its own size — never {on_volume} on the tracker's volume",
                      own in ratio and (on_volume == own or on_volume not in ratio), repr(ratio))
        deadline = row.get("deadline") or ""
        if entry["deadline"] is None:
            journal.check(f"{name}: it owes no deadline, and says so",
                          TORRENT_WORDS.get("noDeadline", "<no copy>") in deadline, repr(deadline))
        else:
            moment = datetime.datetime.fromtimestamp(entry["deadline"])
            day = f"{moment.day} {MONTHS[moment.month - 1]}"
            journal.check(f"{name}: its deadline is its own, the {day} — day and month",
                          prefix in deadline and day in deadline, repr(deadline))
        journal.check(f"{name}: its origin mark says {'origin grab' if entry['origin'] else 'cross-seed'}, "
                      "drawn with a box, and its ratio sits on its title's own line",
                      row.get("origin") == ("origin" if entry["origin"] else "cross")
                      and bool(row.get("mark")) and min(row["mark"]) > 0 and row.get("onLine") is True,
                      f"{row.get('origin')!r} · mark {row.get('mark')} · on its line {row.get('onLine')}")
        obligation = owed(entry)
        running = obligation is not None and not any(
            obligation[field] for field in ("breachedAt", "satisfiedAt", "releasedAt"))
        journal.check(f"{name}: {'an open obligation is marked on it' if running else 'it wears no open obligation'}",
                      row.get("open") is running and not row.get("done"), f"open {row.get('open')} · done {row.get('done')}")

    # A FINGER, not a posed screen: the title is a path, read on the address.
    first = DOWNLOADS[0]["ids"]
    wanted = f"/media/tvdb/{first['tvdb']}" if first.get("tvdb") else f"/media/tmdb/{first.get('tmdb')}"
    title = page.locator('#view [data-part="torrents/row"] [data-part="torrents/title"]').first
    if await title.count():
        await title.tap()
        await page.wait_for_timeout(ACTED)
    where = await page.evaluate("()=>location.pathname")
    journal.check(f"a finger on the first row's title lands on its sheet, {wanted}", where == wanted, where)


async def filtered(page, journal):
    """Holds 12 to 16: the tracker filter, the empty tab, the met obligation."""
    words = TORRENT_WORDS
    named = TRACKERS[0]["name"]
    answer = await enter(page, "torrents-list-filtered")
    journal.check("the named state torrents-list-filtered exists", answer is None, answer or "")
    drawn = await page.evaluate(ROWS)
    wanted = [entry["infoHash"] for entry in DOWNLOADS if entry["tracker"] == named]
    journal.check(f"filtered to {named}: its rows alone",
                  [row["hash"] for row in drawn] == wanted and all(row["tracker"] == named for row in drawn),
                  f"{[(row['hash'][:6], row['tracker']) for row in drawn]}")
    line = await page.evaluate(FILTER)
    said = words.get("filtered", "<no copy>").replace("{{tracker}}", named)
    journal.check(f"the filter is said, « {said} », with « Tout voir »",
                  line is not None and said in line["text"] and line["clear"], repr(line))

    # A FINGER on « Tout voir », from a cold filtered address: every row back,
    # the filter gone from the address, and the entry adjusted, never pushed.
    address = f"{PROTOTYPE.rstrip('/')}{PAGE_PATHS.get('trackers', '/trackers')}?list=torrents&tracker={named}"
    await page.goto(address, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.wait_for_timeout(SETTLED)
    before = await page.evaluate("()=>history.length")
    clear = page.locator('#view [data-part="torrents/filter-clear"]')
    if await clear.count():
        await clear.first.tap()
        await page.wait_for_timeout(ACTED)
    drawn = await page.evaluate(ROWS)
    where = await page.evaluate("()=>({search: location.search, length: history.length})")
    journal.check("a finger on « Tout voir » draws every row again",
                  len(drawn) == len(DOWNLOADS) and await page.evaluate(FILTER) is None,
                  f"{len(drawn)} row(s) of {len(DOWNLOADS)}")
    journal.check("« Tout voir » drops the tracker from the address and pushes nothing",
                  "tracker=" not in where["search"] and where["length"] == before,
                  f"{where['search']!r} · history.length {before} -> {where['length']}")

    answer = await enter(page, "torrents-empty")
    journal.check("the named state torrents-empty exists", answer is None, answer or "")
    note = await page.evaluate(EMPTY)
    journal.check("nothing active anywhere: no row, the tab says so, no filter shown",
                  await page.evaluate(ROWS) == [] and note is not None
                  and words.get("empty", "<no copy>") in note and await page.evaluate(FILTER) is None,
                  repr(note))

    idle = TRACKERS[-1]["name"]
    answer = await enter(page, "torrents-empty-filtered")
    journal.check("the named state torrents-empty-filtered exists", answer is None, answer or "")
    note = await page.evaluate(EMPTY)
    line = await page.evaluate(FILTER)
    journal.check(f"nothing on {idle}: a different sentence from the unfiltered empty",
                  await page.evaluate(ROWS) == [] and note is not None
                  and words.get("emptyFiltered", "<no copy>") in note
                  and words.get("empty", "<no copy>") not in note, repr(note))
    journal.check(f"nothing on {idle}: the filter is still said, and can be lifted",
                  line is not None and idle in line["text"] and line["clear"], repr(line))

    answer = await enter(page, "torrents-obligation-done")
    journal.check("the named state torrents-obligation-done exists", answer is None, answer or "")
    drawn = {row["hash"]: row for row in await page.evaluate(ROWS)}
    met = DOWNLOADS[1]
    row = drawn.get(met["infoHash"], {})
    journal.check(f"{met['title']}: its met obligation is marked done, never open",
                  row.get("done") is True and row.get("open") is False,
                  f"open {row.get('open')} · done {row.get('done')}")


async def downloading(page, journal):
    """Hold 17: the entry still downloading is read in « Torrents »."""
    entry = next((one for one in DOWNLOADS if one["state"] == "downloading"), None)
    journal.check("the seeds hold an entry the client is still downloading", entry is not None,
                  str(sorted({one["state"] for one in DOWNLOADS})))
    if entry is None:
        return
    await enter(page, "torrents-list")
    hash_value = entry["infoHash"]
    row = page.locator(f'#view [data-part="torrents/row"][data-entry="{hash_value}"]')
    title = row.locator('[data-part="torrents/title"]')
    drawn = (await title.first.text_content()).strip() if await title.count() else None
    journal.check(f"« {entry['title']} », downloading, is a row of « Torrents » under its own title",
                  drawn is not None and drawn.startswith(entry["title"]), repr(drawn))
    ids = entry["ids"]
    wanted = f"/media/tvdb/{ids['tvdb']}" if ids.get("tvdb") else f"/media/tmdb/{ids.get('tmdb')}"
    if drawn is not None:
        await title.first.tap()
        await page.wait_for_timeout(ACTED)
    where = await page.evaluate("()=>location.pathname")
    journal.check(f"a finger on « {entry['title']} » lands on its sheet, {wanted}", where == wanted, where)


async def main():
    journal = Journal("R261 — the « Trackers » tab: one entry per tracker, never averaged")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await enter(page, "trackers-roster")
        journal.check("the named state trackers-roster exists", answer is None, answer or "")
        drawn = await page.evaluate(ENTRIES)
        journal.check("one entry per tracker, in the answer's order",
                      [entry["name"] for entry in drawn] == [tracker["name"] for tracker in TRACKERS],
                      f"{[entry['name'] for entry in drawn]} against {[t['name'] for t in TRACKERS]}")
        mean = french(sum(t["ratio"] for t in TRACKERS) / len(TRACKERS), 2) if TRACKERS else None
        by_name = {entry["name"]: entry for entry in drawn}
        for tracker in TRACKERS:
            entry = by_name.get(tracker["name"], {})
            own = french(tracker["ratio"], 2)
            ratio = entry.get("ratio") or ""
            journal.check(f"{tracker['name']}: its ratio is its own, {own}, never the mean {mean}",
                          own in ratio and (mean == own or mean not in ratio), repr(ratio))
            journal.check(f"{tracker['name']}: its ratio sits on its name's own line, inside its row",
                          entry.get("onLine") is True, repr(entry.get("onLine")))
            word = WORDS.get("trends", {}).get(tracker["trend"], "<no word>")
            journal.check(f"{tracker['name']}: its trend is said in words, « {word} »",
                          word in (entry.get("trend") or ""), repr(entry.get("trend")))
            down = french(tracker["downloadedBytes"] / GIGABYTE, 1)
            up = french(tracker["uploadedBytes"] / GIGABYTE, 1)
            volumes = entry.get("volumes") or ""
            journal.check(f"{tracker['name']}: its volumes are its own, {down} Go down and {up} Go up",
                          down in volumes and up in volumes and volumes.index(down) < volumes.index(up),
                          repr(volumes))

        await torrents(page, journal)
        await filtered(page, journal)
        await downloading(page, journal)

        answer = await enter(page, "trackers-roster-empty")
        journal.check("the named state trackers-roster-empty exists", answer is None, answer or "")
        drawn = await page.evaluate(ENTRIES)
        note = await page.evaluate(EMPTY)
        journal.check("no tracker configured: no entry, and the tab says so",
                      drawn == [] and note is not None and WORDS.get("empty", "<no copy>") in note,
                      f"{drawn} · {note!r}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

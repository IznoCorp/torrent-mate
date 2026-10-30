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
9. each row's origin mark says origin grab, cross-seed or published by you, as
   its entry's provenance does (L23, round 11 OPEN 5 = B),
   and is DRAWN — a box a finger's eye can see, never 0×0 — and its ratio sits
   on its state's own line, inside its own card;
10. an open obligation is a MARK on its own row, never on a row that owes none;
11. a finger on a card's poster lands on its medium's sheet, by provider id.
12. `torrents-list-filtered` draws the named tracker's rows alone, and SAYS the
    filter: the selector's pill names it, pressed;
13. (moved: lifting the filter is R-L16bis-b's, `trackers_selector_legend.py`);
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

RE-AIMED OUT LOUD (L16-bis, the roster grows — successor R-L16bis-g/h in
`trackers_switch.py`): the roster holds six trackers, one with nothing measured
(its ratio said unknown, never counted in the mean) and three switched off, which
say so under their name in place of their trend and volumes.

RE-AIMED OUT LOUD (L16-bis, the selector — successor R-L16bis-b in
`trackers_selector_legend.py`): holds 12 to 15 read RULINGS 3's line « Filtré sur
<tracker> · Tout voir »; the operator's selector replaces it, its pill SAYS the
filter, so these holds read the pill, and hold 13's « Tout voir » is the
selector's « Tous les trackers », held there.

RE-AIMED OUT LOUD (L16-bis, the torrent card — successor R-L16bis-e in
`trackers_card.py`): holds 9, 11 and 17 read the old row's title, a text button
to the sheet (`torrents/title`). The row is a media card now: its name is the
card's title, the path to the sheet is its POSTER, and the ratio sits on the
state line, after the state's chip.

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
# RE-AIMED OUT LOUD (L17): the obligations the layer answers are the real ones AND
# the invented ones a cross-seed created (`mocks/seeds/cross-seed.json`).
OBLIGATIONS = (json.loads((SOURCE / "mocks/seeds/obligations.json").read_text(encoding="utf-8"))
               + json.loads((SOURCE / "mocks/seeds/cross-seed.json").read_text(encoding="utf-8"))["obligations"])
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
    onLine: (%s)(row.querySelector('[data-part="torrents/ratio"]'), row.querySelector('[data-part="card/meta"] [data-part="chip"]')),
    open: row.querySelector('[data-part="torrents/obligation-open"]') !== null,
    done: row.querySelector('[data-part="torrents/obligation-done"]') !== null,
  };
})""" % ON_LINE
# THE FILTER, AS THE SELECTOR SAYS IT: its pill pressed, naming the tracker —
# null when the list is whole.
FILTER = """() => {
  const pill = document.querySelector('#view [data-part="pill/select"][data-trackers-selector]');
  return pill === null || pill.getAttribute('aria-pressed') !== 'true' ? null : {
    text: pill.firstChild?.textContent.trim() ?? '',
    clear: true,
  };
}"""
EMPTY = """() => document.querySelector('#view [data-part="empty-state"]')?.textContent.trim() ?? null"""


def french(number, decimals):
    """The number as the interface writes it: a decimal comma, fixed decimals."""
    return f"{number:.{decimals}f}".replace(".", ",")

# The value each provenance's mark carries on the card (`ORIGIN_MARK` of torrent-card.ts).
ORIGIN_MARK = {"downloaded": "origin", "crossSeed": "cross", "published": "published"}

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
        journal.check(f"{name}: its origin mark says its provenance, {entry['provenance']!r}, "
                      "drawn with a box, and its ratio sits on its state's own line",
                      row.get("origin") == ORIGIN_MARK[entry["provenance"]]
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
    poster = page.locator('#view [data-part="torrents/row"] [data-part="card/poster"]').first
    if await poster.count():
        await poster.tap()
        await page.wait_for_timeout(ACTED)
    where = await page.evaluate("()=>location.pathname")
    journal.check(f"a finger on the first card's poster lands on its sheet, {wanted}", where == wanted, where)


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
    journal.check(f"the filter is said: the selector's pill names {named}, pressed",
                  line is not None and line["text"] == named, repr(line))

    answer = await enter(page, "torrents-empty")
    journal.check("the named state torrents-empty exists", answer is None, answer or "")
    note = await page.evaluate(EMPTY)
    journal.check("nothing active anywhere: no row, the tab says so, no filter shown",
                  await page.evaluate(ROWS) == [] and note is not None
                  and words.get("empty", "<no copy>") in note and await page.evaluate(FILTER) is None,
                  repr(note))

    # THE TRACKER `torrents-empty-filtered` EMPTIES: the second of the seeds, the
    # last one entries run on — the roster's later rows run nothing at all.
    idle = TRACKERS[1]["name"]
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
    title = row.locator('[data-part="card/title"]')
    poster = row.locator('[data-part="card/poster"]')
    drawn = (await title.first.text_content()).strip() if await title.count() else None
    journal.check(f"« {entry['title']} », downloading, is a card of « Torrents » under its own name",
                  drawn == entry["name"], repr(drawn))
    ids = entry["ids"]
    wanted = f"/media/tvdb/{ids['tvdb']}" if ids.get("tvdb") else f"/media/tmdb/{ids.get('tmdb')}"
    if drawn is not None and await poster.count():
        await poster.first.tap()
        await page.wait_for_timeout(ACTED)
    where = await page.evaluate("()=>location.pathname")
    journal.check(f"a finger on « {entry['title']} »'s poster lands on its sheet, {wanted}", where == wanted, where)


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
        measured = [t["ratio"] for t in TRACKERS if t["ratio"] is not None]
        mean = french(sum(measured) / len(measured), 2) if measured else None
        by_name = {entry["name"]: entry for entry in drawn}
        for tracker in TRACKERS:
            entry = by_name.get(tracker["name"], {})
            ratio = entry.get("ratio") or ""
            if tracker["ratio"] is None:
                journal.check(f"{tracker['name']}: nothing measured, its ratio is said unknown, never a mean",
                              ratio == WORDS.get("ratioUnknown") and (mean is None or mean not in ratio), repr(ratio))
            else:
                own = french(tracker["ratio"], 2)
                journal.check(f"{tracker['name']}: its ratio is its own, {own}, never the mean {mean}",
                              own in ratio and (mean == own or mean not in ratio), repr(ratio))
            journal.check(f"{tracker['name']}: its ratio sits on its name's own line, inside its row",
                          entry.get("onLine") is True, repr(entry.get("onLine")))
            if not tracker["enabled"]:
                # AN OFF TRACKER SAYS IT IS OFF under its name, in place of its facts.
                journal.check(f"{tracker['name']}: off, it says so under its name in place of its trend and volumes",
                              entry.get("trend") is None and entry.get("volumes") is None, repr(entry))
                continue
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

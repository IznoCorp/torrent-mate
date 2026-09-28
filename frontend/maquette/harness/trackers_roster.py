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
5. `trackers-roster-empty` — no tracker configured — draws no entry and says so.

RE-AIMED OUT LOUD (the « Torrents » tab): the same clause, read on the other
tab. A torrent's ratio is ITS OWN on the tracker the entry runs on, computed on
the torrent's own size — never on the tracker's download volume, which is the
division a cross-seed would make by zero. So, on `torrents-list`:

6. one row per download entry, in the answer's order — a torrent on two
   trackers is two rows;
7. each row names its own tracker, and draws its own ratio, never one computed
   on the tracker's volume;
8. each row's deadline is its own, or says there is none;
9. each row's origin mark says origin grab or cross-seed, as its entry does;
10. an open obligation is a MARK on its own row, never on a row that owes none;
11. a finger on a row's title lands on its medium's sheet, by provider id.

Red before the move: the tab draws no entry.
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
OBLIGATIONS = json.loads((SOURCE / "mocks/seeds/obligations.json").read_text(encoding="utf-8"))
SCREENS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]
WORDS = SCREENS["trackers"]
TORRENT_WORDS = SCREENS.get("torrents", {})
# A billion bytes, the « Go » the interface writes volumes in.
GIGABYTE = 1_000_000_000

ENTRIES = """() => [...document.querySelectorAll('#view [data-part="trackers/entry"]')].map(entry => ({
  name: entry.dataset.tracker,
  ratio: entry.querySelector('[data-part="trackers/ratio"]')?.textContent.trim() ?? null,
  trend: entry.querySelector('[data-part="trackers/trend"]')?.textContent.trim() ?? null,
  volumes: entry.querySelector('[data-part="trackers/volumes"]')?.textContent.trim() ?? null,
}))"""
ROWS = """() => [...document.querySelectorAll('#view [data-part="torrents/row"]')].map(row => {
  const text = (part) => row.querySelector(`[data-part="${part}"]`)?.textContent.trim() ?? null;
  return {
    hash: row.dataset.entry ?? null,
    tracker: text("torrents/tracker"),
    ratio: text("torrents/ratio"),
    deadline: text("torrents/deadline"),
    origin: row.querySelector('[data-part="torrents/origin"]')?.dataset.origin ?? null,
    open: row.querySelector('[data-part="torrents/obligation-open"]') !== null,
    done: row.querySelector('[data-part="torrents/obligation-done"]') !== null,
  };
})"""
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
            day = str(datetime.datetime.fromtimestamp(entry["deadline"]).day)
            journal.check(f"{name}: its deadline is its own, the {day}",
                          prefix in deadline and day in deadline, repr(deadline))
        journal.check(f"{name}: its origin mark says {'origin grab' if entry['origin'] else 'cross-seed'}",
                      row.get("origin") == ("origin" if entry["origin"] else "cross"), repr(row.get("origin")))
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


async def main():
    journal = Journal("R261 — the « Trackers » tab: one entry per tracker, never averaged")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
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

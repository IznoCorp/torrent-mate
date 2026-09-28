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

Red before the move: the tab draws no entry.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
TRACKERS = json.loads((SOURCE / "mocks/seeds/trackers.json").read_text(encoding="utf-8"))
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["trackers"]
# A billion bytes, the « Go » the interface writes volumes in.
GIGABYTE = 1_000_000_000

ENTRIES = """() => [...document.querySelectorAll('#view [data-part="trackers/entry"]')].map(entry => ({
  name: entry.dataset.tracker,
  ratio: entry.querySelector('[data-part="trackers/ratio"]')?.textContent.trim() ?? null,
  trend: entry.querySelector('[data-part="trackers/trend"]')?.textContent.trim() ?? null,
  volumes: entry.querySelector('[data-part="trackers/volumes"]')?.textContent.trim() ?? null,
}))"""
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

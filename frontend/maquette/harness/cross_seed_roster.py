"""R-L17-a, R-L17-b — each tracker's entry says where its cross-seed stands, in the server's own figures.

§ 19: « l'état par tracker vit dans la page Trackers ». L17 DESIGN § 3.1 (S1): one
line under the ratio, on its own row of the entry's grid; M6: when the engine's
own switch is off, the line says so FIRST and the tracker's own switch SECOND.

R-L17-b — one derivation (§ 13, NE-DOIT-PAS-1):
1. `trackers-cross-seed`: every tracker's entry carries its line;
2. the count the line says is the summary's own `crossSeed.active`, and equals
   the pairs the downloads read answers for that tracker in state `active`,
   summed across every torrent — never a local count;
3. its failures are the summary's `crossSeed.failed`, said when there are any;
4. `trackers-cross-seed-engine-off`: every line names the engine off FIRST, then
   the tracker's own switch; no pair reads « stoppé » from the engine alone —
   the pairs the downloads read answers are the default scenario's, unchanged.

R-L17-a — no bare code (NE-DOIT-PAS-4):
5. no line draws an engine code or an English state identifier.

Red before the move: no entry carries a cross-seed line.
"""
import asyncio
import json
import pathlib
import re

from common import SETTLED, Journal, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1] / "design/src"
LINE = json.loads((ROOT / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["crossSeed"]["line"]
ENGINE_OFF = LINE["engineOff"]
# The codes a surface must never draw: the engine's snake_case reasons, the contract's state identifiers.
BARE = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b|\b(trackerWithout|noMatch|notSearched|stopped|active)\b")

READ = """() => {
  const served = window.__queries?.getQueryData(['/api/trackers']) || [];
  const downloads = window.__queries?.getQueryData(['/api/acquisition/downloads'])?.downloads || [];
  const pairs = downloads.flatMap(entry => entry.crossSeed?.pairs || []);
  return served.map(tracker => {
    const line = document.querySelector(`#view [data-part="trackers/entry"][data-tracker="${tracker.name}"] [data-part="trackers/cross-seed"]`);
    return {
      name: tracker.name, summary: tracker.crossSeed, text: line?.textContent.trim() ?? null,
      active: pairs.filter(pair => pair.tracker === tracker.name && pair.state === 'active').length,
    };
  });
}"""
PAIRS = """() => (window.__queries?.getQueryData(['/api/acquisition/downloads'])?.downloads || [])
  .flatMap(entry => (entry.crossSeed?.pairs || []).map(pair => `${entry.infoHash}:${pair.tracker}:${pair.state}`)).sort()"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


async def main():
    journal = Journal("R-L17-a/b — each tracker's entry says where its cross-seed stands")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await enter(page, "trackers-cross-seed")
        rows = await page.evaluate(READ)
        default_pairs = await page.evaluate(PAIRS)
        journal.check("trackers-cross-seed: every tracker's entry carries its cross-seed line",
                      answer is None and bool(rows) and all(row["text"] for row in rows), answer or repr(rows))
        journal.check("the line's count is the summary's own, and equals the active pairs summed across torrents",
                      bool(rows) and all(row["summary"]["active"] == row["active"]
                                         and (row["active"] == 0 or f"{row['active']} torrent" in (row["text"] or ""))
                                         for row in rows)
                      and any(row["active"] > 0 for row in rows),
                      repr([(row["name"], row["summary"]["active"], row["active"], row["text"]) for row in rows]))
        journal.check("its failures are the summary's own, said when there are any",
                      all((row["summary"]["failed"] == 0) == ("échec" not in (row["text"] or "")) for row in rows)
                      and any(row["summary"]["failed"] > 0 for row in rows),
                      repr([(row["name"], row["summary"]["failed"]) for row in rows]))
        journal.check("no line draws an engine code or a state identifier",
                      all(row["text"] and not BARE.search(row["text"]) for row in rows),
                      repr([row["text"] for row in rows if row["text"] and BARE.search(row["text"])]))

        answer = await enter(page, "trackers-cross-seed-engine-off")
        rows = await page.evaluate(READ)
        journal.check("engine off: every line names the engine FIRST, the tracker's own switch SECOND (M6)",
                      answer is None and bool(rows)
                      and all((row["text"] or "").startswith(ENGINE_OFF) and "ce tracker" in row["text"] for row in rows),
                      answer or repr([row["text"] for row in rows]))
        journal.check("engine off: no pair reads « stoppé » from the engine alone — every pair as by default",
                      await page.evaluate(PAIRS) == default_pairs and bool(default_pairs), f"{len(default_pairs)} pairs")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

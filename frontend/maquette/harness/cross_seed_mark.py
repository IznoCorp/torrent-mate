"""R-L17-k, R-L17-a/b, R-L17-c, R-L17-d — a torrent says where it cross-seeds, tracker by tracker.

§ 19: « pour chaque torrent, l'état tracker par tracker » in the operator's six
words; point 1, a refusal explained; point 2, an obligation says its origin.
L17 DESIGN § 3.3 (S3), re-homed by L16-bis § 1.5 onto the torrent's PANEL; § 3.4 (S4).

R-L17-k — one read per visit (NE-DOIT-PAS-8):
1. a finger on « Trackers » then on an origin's card opens its cross-seed with the
   page's three reads asked ONCE each, no operation of its own, and a wait asks nothing.

R-L17-a/b — the mark's rows are the server's, in the six words:
2. `torrents-cross-seed`: one row per pair the downloads read answers for that
   origin, each row's state the pair's own, its chip one of the six words;
3. the rows read in F64's order: counted failures, ordinary refusals, « actif »,
   « stoppé », « tracker sans cross-seed », « sans correspondance » / « pas
   encore cherché » — the newest first within a state;
4. an « actif » row says its injection date; a « stoppé » one its stop's date.

R-L17-c — a refusal is readable (§ 19 point 1, DOIT-2):
5. `torrents-cross-seed-refused`: each « erreur » row draws ITS code's sentence,
   its kind of trouble, the candidate on its tracker and the source — never the code;
6. a transport failure and a layout mismatch read different families.

R-L17-d — an obligation says where it came from (§ 19 point 2):
7. the cross-seed's own card (President Curtis on tr4ker) wears « cross-seed de
   President Curtis », and its panel names the original and leads to its sheet;
8. an obligation no cross-seed created carries no such mark.

Red before the move: no panel carries a cross-seed block, no obligation an origin.
"""
import asyncio
import json
import pathlib
import re

from common import ACTED, SETTLED, Journal, chrome_launch_args, open_page
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((ROOT / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["crossSeed"]
SIX = set(WORDS["states"].values())
CROSS_SEEDING = "66e23ab395c438b7db4f7c855bd451d8bb1f0046"
REFUSED = "8d51568b1a4f46e1fb7e7b535b52a5203312fc28"
COPY = "7c1e0b2f95c438b7db4f7c855bd451d8bb1f0046"
FAILURES = {"fetch_failed", "verify_timeout", "recheck_failed", "magnet_not_supported", "parse_failed",
            "inject_failed", "obligation_write_failed", "upload_failed"}
FAMILY = {"root_name_mismatch": "files", "fetch_failed": "attempt", "verify_timeout": "attempt"}
RANK = {"error": 1, "active": 2, "stopped": 3, "trackerWithout": 4, "noMatch": 5, "notSearched": 5}
BARE = re.compile(r"\b[a-z0-9]+_[a-z0-9_]+\b")

ROWS = """(hash) => {
  const pairs = (window.__queries?.getQueryData(['/api/acquisition/downloads'])?.downloads || [])
    .find(entry => entry.infoHash === hash)?.crossSeed?.pairs ?? null;
  const rows = [...document.querySelectorAll('#sheet[data-open] [data-part="torrents/cross-seed-row"]')].map(row => ({
    tracker: row.dataset.tracker, state: row.dataset.state,
    chip: row.querySelector('[data-part="torrents/cross-seed-state"] [data-part="chip"]')?.textContent.trim() ?? null,
    date: row.querySelector('[data-part="torrents/cross-seed-date"]')?.textContent.trim() ?? null,
    reason: row.querySelector('[data-part="torrents/cross-seed-reason"]')?.textContent.trim() ?? null,
    code: row.querySelector('[data-part="torrents/cross-seed-reason"]')?.dataset.reason ?? null,
    text: row.textContent,
  }));
  return {pairs, rows, region: !!document.querySelector('#sheet[data-open] [data-region="torrents/cross-seed"]')};
}"""
CALLS = """() => (window.__mocks?.answered() || []).map(call => call.operationId)"""
CARD = """(hash) => {
  const row = document.querySelector(`#view [data-part="torrents/row"][data-entry="${hash}"]`);
  return row ? (row.querySelector('[data-part="torrents/obligation-origin"]')?.textContent.trim() ?? '') : null;
}"""
SHEET = """() => ({
  text: document.querySelector('#sheet[data-open]')?.textContent ?? '',
  toOrigin: [...document.querySelectorAll('#sheet[data-open] [data-mediasheet]')].map(node => node.dataset.mediasheet),
})"""


async def enter(page, state):
    """Drives a named state; returns the error it raised, or None."""
    answer = await page.evaluate(
        f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
    await page.wait_for_timeout(SETTLED)
    return answer


def ordered(pairs):
    """The pairs in F64's reading order."""
    def rank(pair):
        return 0 if pair["state"] == "error" and pair["reason"] in FAILURES else RANK[pair["state"]]
    return [pair["tracker"] for pair in sorted(
        pairs, key=lambda pair: (rank(pair), -((pair["stoppedAt"] or pair["at"]) or 0)))]


async def main():
    journal = Journal("R-L17-k/a/b/c/d — a torrent says where it cross-seeds, tracker by tracker")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── k: one read per visit, by finger ─────────────────────────────────
        await page.evaluate("()=>{window.__mocks?.reset(); window.__queries?.clear(); window.__mocks?.clearAnswered?.()}")
        await page.locator('[data-part="shell/tab-bar"] [data-page="trackers"]').first.tap()
        await page.wait_for_timeout(ACTED)
        tab = page.locator('[data-trackers-tab="torrents"]')
        if await tab.count():
            await tab.first.tap()
            await page.wait_for_timeout(ACTED)
        await page.locator(f'#view [data-part="torrents/row"][data-entry="{CROSS_SEEDING}"] [data-panel]').first.tap()
        await page.wait_for_timeout(ACTED)
        before = await page.evaluate(CALLS)
        await page.wait_for_timeout(3000)
        after = await page.evaluate(CALLS)
        mark = await page.evaluate(ROWS, CROSS_SEEDING)
        reads = {name: before.count(name) for name in ("readTrackers", "readDownloads", "readObligations")}
        journal.check("a finger opens an origin's cross-seed: each page read asked once, none of its own, none on a wait",
                      mark["region"] and all(count == 1 for count in reads.values())
                      and not any("CrossSeed" in name for name in before) and after == before,
                      f"{reads} · cross-seed calls {[n for n in before if 'CrossSeed' in n]} · waited +{len(after) - len(before)}")

        # ── a/b: the rows are the server's, in the six words ────────────────
        answer = await enter(page, "torrents-cross-seed")
        mark = await page.evaluate(ROWS, CROSS_SEEDING)
        pairs = mark["pairs"] or []
        journal.check("torrents-cross-seed: one row per pair the server answers, each in the pair's own state",
                      answer is None and bool(pairs) and len(mark["rows"]) == len(pairs)
                      and all(any(p["tracker"] == r["tracker"] and p["state"] == r["state"] for p in pairs)
                              for r in mark["rows"]), answer or repr([(r["tracker"], r["state"]) for r in mark["rows"]]))
        journal.check("every chip reads one of the operator's six words, never a code",
                      all(row["chip"] in SIX for row in mark["rows"]) and not any(BARE.search(r["text"]) for r in mark["rows"]),
                      repr([row["chip"] for row in mark["rows"]]))
        journal.check("the rows read in F64's order", [r["tracker"] for r in mark["rows"]] == ordered(pairs),
                      f"{[r['tracker'] for r in mark['rows']]} vs {ordered(pairs)}")
        journal.check("an « actif » row says its injection date",
                      all(row["date"] and "injecté le" in row["date"] for row in mark["rows"] if row["state"] == "active"),
                      repr([row["date"] for row in mark["rows"]]))

        # ── c: a refusal is readable ────────────────────────────────────────
        answer = await enter(page, "torrents-cross-seed-refused")
        mark = await page.evaluate(ROWS, REFUSED)
        refusals = [row for row in mark["rows"] if row["state"] == "error"]
        name = next((entry["name"] for entry in json.loads((ROOT / "mocks/seeds/downloads.json").read_text())
                     if entry["infoHash"] == REFUSED), "")
        journal.check("torrents-cross-seed-refused: each refusal says its sentence, its trouble, its candidate and source",
                      answer is None and len(refusals) >= 2 and all(
                          row["reason"] and WORDS["reasons"][row["code"]] in row["reason"]
                          and WORDS["families"][FAMILY.get(row["code"], "attempt")] in row["reason"]
                          and "Candidat" in row["reason"] and name in row["reason"] and row["code"] not in row["text"]
                          for row in refusals), answer or repr(refusals))
        stopped = [row for row in mark["rows"] if row["state"] == "stopped"]
        journal.check("a « stoppé » row says its stop's date", bool(stopped) and all(
            row["date"] and "stoppé le" in row["date"] for row in stopped), repr(stopped))
        await enter(page, "torrents-cross-seed")
        await page.evaluate(f"()=>window.__panel.produce('torrent', '{'e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb'}:c411')")
        await page.wait_for_timeout(ACTED)
        mismatch = await page.evaluate(ROWS, "e5c6f4e9bc5d619c15aa476ec0e278f2267bf0bb")
        layout = next((row for row in mismatch["rows"] if row["code"] == "root_name_mismatch"), None)
        transport = next((row for row in refusals if row["code"] == "fetch_failed"), None)
        journal.check("a transport failure and a layout mismatch read different kinds of trouble",
                      layout is not None and transport is not None
                      and WORDS["families"]["files"] in layout["reason"] and WORDS["families"]["attempt"] in transport["reason"]
                      and WORDS["families"]["files"] not in transport["reason"], f"{layout!r} · {transport!r}")

        # ── d: an obligation says where it came from ───────────────────────
        answer = await enter(page, "torrents-obligation-cross-seed")
        copy = await page.evaluate(CARD, COPY)
        origin = await page.evaluate(CARD, CROSS_SEEDING)
        sheet = await page.evaluate(SHEET)
        journal.check("the cross-seed's card wears « cross-seed de President Curtis »; the origin's card no such mark",
                      answer is None and copy == "cross-seed de President Curtis" and origin == "",
                      f"copy {copy!r} · origin {origin!r}")
        journal.check("its panel names the original and leads to its sheet",
                      "Cross-seed dePresident Curtis" in sheet["text"] and "Voir la fiche de l'original" in sheet["text"]
                      and "President Curtis" in sheet["toOrigin"], repr(sheet["toOrigin"]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

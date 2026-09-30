"""R267 — the ranking editor previews its ranking live, and never drops a row.

§ 18: the ranking follows the ratio, and the operator sees what an edit does
before saving it. The editor asks the preview operation to score the fixed
sample set under the ranking AS TYPED, and draws its answer: every sample, in
the answer's order, the excluded ones sunk last, flagged — and still visible,
since a live preview that silently drops a row hides what the ranking discards.

1. `ranking-editor` draws the preview: one row per sample the operation answers
   for the file's ranking, in that order, each with its score;
2. a typed weight re-scores it — the rows drawn are the operation's answer for
   the ranking AS TYPED, the scores moved, and nothing was written;
3. with a minimum of seeders the samples do not all meet, every sample is still
   a row, the excluded ones last, each flagged;
4. a file that sets no `min_seeders` is previewed under the ENGINE's own
   default, 1 (`personalscraper/conf/models/_ranking.py`) — never 0.

THE MINIMUM IS POSED, a derivation the real file does not hold: the operator's
`ranking.json5` sets `min_seeders` at 1 and every sample has more. The hold
raises it through the file's own write — the operation the editor saves by,
under the digest the read answered — then the screen reads the file again.

Hold 4 came with correction round C16, red while the preview defaulted to 0.
The key is REMOVED through the same write, under the digest the read answered.

Red before the move: no preview is drawn.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
FILE = next(file for file in json.loads((SOURCE / "mocks/seeds/configuration-files.json").read_text(encoding="utf-8"))
            if file["name"] == "ranking.json5")
RANKING = FILE["values"]["ranking"]
SAMPLES = json.loads((SOURCE / "mocks/seeds/ranking-samples.json").read_text(encoding="utf-8"))
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]["ranking"]
POSED_MINIMUM = 10
# The engine's default when the file sets no minimum.
ENGINE_DEFAULT_MINIMUM = 1
DROP_MINIMUM = """async () => {
  const read = await (await fetch('/api/config/files/ranking.json5')).json();
  const {min_seeders: _dropped, ...ranking} = read.values.ranking;
  return (await (await fetch('/api/config/files/ranking.json5', {method: 'PUT',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({values: {...read.values, ranking},
    digest: read.digest})})).json());
}"""
# The minimum the screen's LAST preview asked the operation for, read off its own query key.
ASKED_MINIMUM = """() => {
  const queries = window.__queries?.getQueryCache().findAll({queryKey: ['/api/acquisition/ranking/preview']}) ?? [];
  const last = queries.sort((a, b) => b.state.dataUpdatedAt - a.state.dataUpdatedAt)[0];
  return last ? last.queryKey[1]?.minSeeders ?? null : null;
}"""

ROWS = """() => [...document.querySelectorAll('[data-part="ranking/preview"] [data-part="ranking/preview-row"]')]
  .map(row => ({title: row.dataset.title, score: row.querySelector('[data-part="ranking/preview-score"]')
    ?.textContent.trim() ?? '', excluded: row.dataset.excluded === 'true', text: row.textContent}))"""
PREVIEW = """async (config) => (await (await fetch('/api/acquisition/ranking/preview', {method: 'POST',
  headers: {'Content-Type': 'application/json'}, body: JSON.stringify(config)})).json()).ranked"""
CALLS = """(n) => window.__mocks.answered().slice(n).map((one) => one.operationId)"""
# THE SCREEN READS THE FILE AGAIN where it stands: its read is marked stale, and
# the mounted screen asks the layer anew.
REREAD = """()=>window.__queries?.invalidateQueries({queryKey: ['/api/config/files/ranking.json5']})"""
RAISE_MINIMUM = """async (minimum) => {
  const read = await (await fetch('/api/config/files/ranking.json5')).json();
  const values = {...read.values, ranking: {...read.values.ranking, min_seeders: minimum}};
  return (await (await fetch('/api/config/files/ranking.json5', {method: 'PUT',
    headers: {'Content-Type': 'application/json'}, body: JSON.stringify({values, digest: read.digest})})).json());
}"""


def config(weights=None, minimum=None):
    """The ranking the editor asks the preview for: the file's, with typed weights and a minimum."""
    criteria = [dict(criterion, weight=(weights or {}).get(criterion["field"], criterion["weight"]))
                for criterion in RANKING["criteria"]]
    return {"criteria": criteria, "minSeeders": RANKING["min_seeders"] if minimum is None else minimum,
            "bonuses": RANKING["bonuses"]}


def agrees(drawn, answered):
    """Whether the rows drawn are the answer: the same titles in the same order, each with its score."""
    return ([row["title"] for row in drawn] == [one["title"] for one in answered]
            and all(str(one["score"]) in row["score"] for row, one in zip(drawn, answered)))


async def main():
    journal = Journal("R267 — the ranking editor previews its ranking live")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        calls = await page.evaluate("()=>window.__mocks.answered().length")
        answer = await page.evaluate(
            "()=>{try{window.__go('ranking-editor');return null}catch(error){return String(error)}}")
        await page.wait_for_timeout(SETTLED)
        drawn = await page.evaluate(ROWS)
        # THE SCREEN'S OWN CALLS, read before the rule asks the operation itself.
        asked = await page.evaluate(CALLS, calls)
        answered = await page.evaluate(PREVIEW, config())
        journal.check(f"ranking-editor draws the preview the operation answers for the file's ranking, "
                      f"{len(SAMPLES)} rows in its order, each with its score",
                      answer is None and "previewRanking" in asked and len(drawn) == len(SAMPLES)
                      and agrees(drawn, answered),
                      f"{answer or ''} asked {sorted(set(asked))} · drawn {[(row['title'][:24], row['score']) for row in drawn[:4]]}"
                      f" against {[(one['title'][:24], one['score']) for one in answered[:4]]}")

        target = RANKING["criteria"][0]
        typed = target["weight"] * 10
        calls = await page.evaluate("()=>window.__mocks.answered().length")
        weight = f'[data-part="ranking/criterion"][data-field="{target["field"]}"] [data-part="ranking/weight"]'
        if await page.locator(weight).count():
            await page.locator(weight).first.tap()
            await page.keyboard.press("ControlOrMeta+A")
            await page.keyboard.type(str(typed))
            await page.wait_for_timeout(SETTLED)
        retyped = await page.evaluate(ROWS)
        asked = await page.evaluate(CALLS, calls)
        wanted = await page.evaluate(PREVIEW, config({target["field"]: typed}))
        journal.check(f"{target['field']} typed at {typed}: the rows are the answer for the ranking AS TYPED, "
                      "the scores moved, and nothing was written",
                      agrees(retyped, wanted) and [row["score"] for row in retyped] != [row["score"] for row in drawn]
                      and "previewRanking" in asked and "updateConfigurationFile" not in asked,
                      f"asked {asked} · drawn {[(row['title'][:24], row['score']) for row in retyped[:4]]}"
                      f" against {[(one['title'][:24], one['score']) for one in wanted[:4]]}")

        # LEFT AND ENTERED AGAIN, so the typed weight goes with the screen.
        await page.evaluate("()=>{window.__go('settings')}")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("()=>{window.__go('ranking-editor')}")
        await page.wait_for_timeout(SETTLED)
        raised = await page.evaluate(RAISE_MINIMUM, POSED_MINIMUM)
        await page.evaluate(REREAD)
        await page.wait_for_timeout(SETTLED)
        drawn = await page.evaluate(ROWS)
        answered = await page.evaluate(PREVIEW, config(minimum=POSED_MINIMUM))
        excluded = sorted(sample["title"] for sample in SAMPLES if sample["seeders"] < POSED_MINIMUM)
        flagged = [row for row in drawn if row["excluded"]]
        tail = drawn[len(drawn) - len(excluded):] if excluded else []
        journal.check(f"under a minimum of {POSED_MINIMUM} seeders, every sample is still a row, the "
                      f"{len(excluded)} excluded ones last, each flagged « {WORDS['previewExcluded']} »",
                      raised.get("conflict") is False and len(drawn) == len(SAMPLES) and agrees(drawn, answered)
                      and bool(excluded) and sorted(row["title"] for row in flagged) == excluded
                      and sorted(row["title"] for row in tail) == excluded
                      and all(WORDS["previewExcluded"] in row["text"] for row in flagged),
                      f"write {raised} · {len(drawn)} rows · flagged {[row['title'][:24] for row in flagged]}"
                      f" against {[title[:24] for title in excluded]}")

        # ── no minimum in the file: the engine's own default ──────────────
        await page.evaluate("()=>{window.__go('ranking-editor')}")
        await page.wait_for_timeout(SETTLED)
        dropped = await page.evaluate(DROP_MINIMUM)
        await page.evaluate(REREAD)
        await page.wait_for_timeout(SETTLED)
        asked = await page.evaluate(ASKED_MINIMUM)
        journal.check(f"a file setting no min_seeders is previewed under the engine's default {ENGINE_DEFAULT_MINIMUM}, never 0",
                      dropped.get("conflict") is False and asked == ENGINE_DEFAULT_MINIMUM,
                      f"write {dropped} · asked minSeeders {asked!r}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

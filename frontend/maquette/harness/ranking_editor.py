"""R266 — the ranking editor lists what `ranking.json5` holds, never a constant.

§ 18: the ranking follows the ratio, and the operator edits it where it is
written. The editor opens on the file's own content, read through the file's
own operation: every criterion the file holds, in its order, with its weight
and its scoring — a score per value, or its thresholds. Read here against the
very seed the layer answers from, so a list drawn from anywhere else falls.

1. `ranking-editor` draws one row per criterion of the file, in the file's order;
2. each row's weight is the file's;
3. each row's scoring names every value the file scores, or every threshold;
4. from Réglages, a finger on « Classement des releases » opens the GLOBAL
   quality profile, and there a finger on « Poids du classement » lands on the
   editor, as an arrival;
5. from a quality screen, a finger on « Poids du classement » lands on the
   editor, and says no promise in a toast (B-298);
6. `ranking-editor-loading` draws no criterion while the file is read, and
   `ranking-editor-error` says the read failed rather than an empty list.

RE-AIMED OUT LOUD: hold 4 first read « the rubric lands on the editor ». The
rubric opens the global quality profile — a route of its own, held by
`page_host.py` — and the promise B-298 names was that profile's weights button,
a toast. The rubric keeps its route; the path to the editor runs through it.

Red before the move: no screen answers `/settings/ranking`.
"""
import asyncio
import json
import pathlib

from common import SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
FILES = json.loads((SOURCE / "mocks/seeds/configuration-files.json").read_text(encoding="utf-8"))
RANKING = next(file for file in FILES if file["name"] == "ranking.json5")["values"]["ranking"]

SETTINGS_WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["screens"]
RUBRIC = SETTINGS_WORDS["settings"]["rankingTitle"]
WEIGHTS = SETTINGS_WORDS["profile"]["rankingWeights"]
ROWS = """() => [...document.querySelectorAll('[data-part="ranking/criterion"]')].map(row => ({
  field: row.dataset.field,
  weight: row.querySelector('[data-part="ranking/weight"]')?.textContent.trim() ?? '',
  scoring: row.querySelector('[data-part="ranking/scoring"]')?.textContent.trim() ?? '',
}))"""


def number(value):
    """A weight or a threshold as the interface writes it: a decimal comma, no trailing zero.

    A threshold the file writes as words (« 1GB ») is written as the file wrote it.
    """
    return value if isinstance(value, str) else f"{value:g}".replace(".", ",")


async def main():
    journal = Journal("R266 — the ranking editor lists what ranking.json5 holds")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        answer = await page.evaluate(
            "()=>{try{window.__go('ranking-editor');return null}catch(error){return String(error)}}")
        await page.wait_for_timeout(SETTLED)
        journal.check("the named state ranking-editor exists", answer is None, answer or "")
        where = await page.evaluate("()=>location.pathname")
        journal.check("it stands at /settings/ranking", where.endswith("/settings/ranking"), where)
        drawn = await page.evaluate(ROWS)
        criteria = RANKING["criteria"]
        journal.check("one row per criterion of the file, in the file's order",
                      [row["field"] for row in drawn] == [criterion["field"] for criterion in criteria],
                      f"{[row['field'] for row in drawn]} against {[criterion['field'] for criterion in criteria]}")
        by_field = {row["field"]: row for row in drawn}
        for criterion in criteria:
            row = by_field.get(criterion["field"], {"weight": "", "scoring": ""})
            journal.check(f"{criterion['field']}: its weight is the file's, {number(criterion['weight'])}",
                          number(criterion["weight"]) in row["weight"], repr(row["weight"]))
            wanted = ([f"{value} {score}" for value, score in (criterion.get("values") or {}).items()]
                      or [f"{number(threshold['at'])}" for threshold in criterion.get("thresholds") or []])
            journal.check(f"{criterion['field']}: its scoring names every one of the file's {len(wanted)}",
                          bool(wanted) and all(one in row["scoring"] for one in wanted), repr(row["scoring"][:120]))

        # ── the two ways in, by a finger (B-298) ─────────────────────────
        async def lands(start, locator, label):
            await page.evaluate(f"()=>window.__go('{start}')")
            await page.wait_for_timeout(SETTLED)
            before = await page.evaluate("()=>history.length")
            target = page.locator(locator, has_text=label)
            if await target.count():
                await target.first.tap()
                await page.wait_for_timeout(SETTLED)
            return await page.evaluate("""()=>({path: location.pathname, length: history.length,
                rows: document.querySelectorAll('[data-part="ranking/criterion"]').length,
                toast: document.querySelector('#toast[data-shown]')?.textContent.trim() || null})"""), before
        where, before = await lands("settings", '#view [data-part="topic"]', RUBRIC)
        journal.check(f"from Réglages, « {RUBRIC} » opens the global quality profile",
                      where["path"].endswith("/quality/global"), str(where))
        weights = page.locator('[data-part="card/foot"]', has_text=WEIGHTS)
        if await weights.count():
            await weights.first.tap()
            await page.wait_for_timeout(SETTLED)
        where = await page.evaluate("""()=>({path: location.pathname, length: history.length,
            rows: document.querySelectorAll('[data-part="ranking/criterion"]').length})""")
        journal.check(f"and there « {WEIGHTS} » lands on the editor, as an arrival",
                      where["path"].endswith("/settings/ranking") and where["rows"] == len(criteria)
                      and where["length"] == before + 2, f"{where} · history.length {before}")
        where, before = await lands("screen-profile", '[data-part="card/foot"]', WEIGHTS)
        journal.check(f"from a quality screen, « {WEIGHTS} » lands on the editor, with no promise in a toast",
                      where["path"].endswith("/settings/ranking") and where["rows"] == len(criteria)
                      and not where["toast"], str(where))

        # ── while the file is read, and when the read fails ─────────────
        for state, wanted in (("ranking-editor-loading", "loading"), ("ranking-editor-error", "error")):
            answer = await page.evaluate(
                f"()=>{{try{{window.__go('{state}');return null}}catch(error){{return String(error)}}}}")
            await page.wait_for_timeout(SETTLED)
            seen = await page.evaluate("""()=>({rows: document.querySelectorAll('[data-part="ranking/criterion"]').length,
                skeleton: document.querySelector('[data-part="screen"] [data-skeleton]') !== null,
                error: document.querySelector('[data-part="screen"] [data-part="surface-error"]') !== null})""")
            journal.check(f"{state}: no criterion, and {'the read is shown under way' if wanted == 'loading' else 'the failure is said'}",
                          answer is None and seen["rows"] == 0 and (seen["skeleton"] if wanted == "loading" else seen["error"]),
                          f"{answer or ''} {seen}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

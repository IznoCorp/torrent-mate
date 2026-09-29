"""R266 — the ranking editor lists what `ranking.json5` holds, never a constant.

§ 18: the ranking follows the ratio, and the operator edits it where it is
written. The editor opens on the file's own content, read through the file's
own operation: every criterion the file holds, in its order, with its weight
and its scoring — a score per value, or its thresholds. Read here against the
very seed the layer answers from, so a list drawn from anywhere else falls.

1. `ranking-editor` draws one row per criterion of the file, in the file's order;
2. each row's weight is the file's;
3. each row's scoring names every value the file scores, or every threshold.

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

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

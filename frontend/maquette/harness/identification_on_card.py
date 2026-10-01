"""R407 — identification in progress is read on the card (L24 S3, OPEN 3 = A).

The operator, 2026-09-29, « A »: no global « en ce moment » for the scrape
activity — production's « Scrapes en cours » panel is not redrawn; what is being
identified now reads on EACH medium's card, from its own journey.

WHAT IS READ, on « En cours » (`acq-card-rungs`), for the card the layer lays at
« identifié » running (« Furious »):

  1. the medium's own journey read (`/api/acquisition/journeys/{subject}`) holds
     the rung « identifié » in the state `now`;
  2. its card's chip names that rung, in the running tone — never done, never
     blocked;
  3. its journey sheet draws the same rung running, with the running rung's
     words (« en cours depuis … »);
  4. nothing asks a global activity: no call to `/api/decisions/activity`, and
     no shipped module names it.
"""
import asyncio
import json
import pathlib

from common import ACTED, PANEL_IN, SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
WORDS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))
IDENTIFIED = WORDS["surfaces"]["ladder"]["rungs"]["identified"]
SUBJECT = "Furious"
SHIPPED = [path for path in SOURCE.rglob("*") if path.suffix in {".ts", ".tsx"}
           and "node_modules" not in path.parts]

CARD = """(subject) => {
  const card = [...document.querySelectorAll('#view [data-part="card"]')]
    .find((one) => one.querySelector('[data-part="card/title"]')?.textContent.trim() === subject);
  const chips = [...(card?.querySelectorAll('[data-part="chip"]') ?? [])]
    .map((chip) => ({label: chip.textContent.trim(), tone: chip.dataset.tone}));
  const stages = window.__queries.getQueryData(['/api/acquisition/journeys', subject]) ?? null;
  return {card: !!card, chips, stages};
}"""

SHEET = """(rung) => {
  const row = [...document.querySelectorAll('#sheet[data-open] [data-part="key-value"]')]
    .find((one) => one.querySelector('span')?.textContent.trim() === rung);
  return row ? {tone: row.querySelector('[data-part="status-dot"]')?.dataset.tone,
                value: row.querySelectorAll(':scope > span')[1]?.textContent.trim()} : null;
}"""


async def main():
    journal = Journal("R407 — identification in progress is read on the card")
    named = [str(path.relative_to(SOURCE)) for path in SHIPPED
             if "decisions/activity" in path.read_text(encoding="utf-8")]
    journal.check("no shipped module asks a global identification activity", named == [], str(named))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await read_at(page, "acq-card-rungs", "() => true")
        await page.evaluate("(subject) => window.__queries.fetchQuery({queryKey: ['/api/acquisition/journeys', subject], "
                            "queryFn: () => fetch('/api/acquisition/journeys/' + encodeURIComponent(subject))"
                            ".then((answer) => answer.json())})", SUBJECT)
        await page.wait_for_timeout(ACTED)
        seen = await page.evaluate(CARD, SUBJECT)
        journal.check(f"« {SUBJECT} »'s card is on « En cours »", seen["card"], str(seen["card"]))
        rung = next((stage for stage in seen["stages"] or [] if stage["rung"] == "identified"), None)
        journal.check("its own journey holds « identifié » running", rung is not None and rung["state"] == "now",
                      str(rung))
        journal.check("its card's chip names « identifié », in the running tone",
                      any(chip["label"] == IDENTIFIED and chip["tone"] == "info" for chip in seen["chips"]),
                      str(seen["chips"]))

        await page.evaluate("(subject) => window.__panel.produce('journey', subject)", SUBJECT)
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        row = await page.evaluate(SHEET, IDENTIFIED)
        journal.check("its journey sheet draws « identifié » running, with the journey's own words",
                      row is not None and rung is not None and row["tone"] == "info" and row["value"] == rung["when"],
                      str({"row": row, "journey": rung}))

        calls = await page.evaluate("() => window.__mocks.answered().map((call) => call.path)")
        journal.check("no call asks a global activity", not any("activity" in path for path in calls),
                      str([path for path in calls if "decision" in path]))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

"""R224 — « En cours » holds « En vol » alone, and says « rien en cours » when nothing moves.

« En cours » is what is moving and nothing else. What waits to be taken is taken
from the follow's sheet; what reached the library reads in the Médiathèque's
« Récents »; what was looked for and not found reads on the follow; what waits
for the operator's hand is « À traiter ». So the tab draws ONE section, « En
vol » — the queue's in-flight cards and the arrivals on their way — and none
titled « À récupérer », « Rangé aujourd'hui » or « Cherché, rien trouvé ».

WHAT IT HOLDS:

  something moves  on `acq-now-loaded`, the body draws exactly one section,
                   titled « En vol », none of the three that left, and the
                   « En cours » tab counts what « En vol » draws.
  nothing moves    on `acq-now-idle` — the real world, where nothing is in
                   flight while three releases wait to be taken — the tab reads
                   « rien en cours », draws no section, and carries no count:
                   what waits to be taken is not counted as moving.

WHAT IT DOES NOT READ: which card sits on which rung (R207's), or the take on the
follow's sheet (R123's).
"""
import asyncio

from common import SETTLED, Journal, open_page
from playwright.async_api import async_playwright

GONE = ("À récupérer", "Rangé aujourd'hui", "Cherché, rien trouvé")  # french-ok: the three section titles, asserted absent
IN_FLIGHT = "En vol"  # french-ok: the one section title, asserted present
EMPTY = "rien en cours"  # french-ok: the empty tab's own words, asserted present

BODY = """() => {
  const body = document.querySelector('[data-region="acquisition/body"]');
  const sections = body ? [...body.querySelectorAll('[data-part="section"]')] : [];
  const tab = document.querySelector('[data-acqtab="now"] [data-part="segment/count"]');
  return {
    body: !!body,
    titles: sections.map((one) => one.querySelector('[data-part="section/title"]')?.textContent.trim() ?? ''),
    cards: sections.map((one) => one.querySelectorAll('[data-part="card"]').length),
    count: tab ? Number(tab.textContent.trim()) : 0,
    text: body ? body.innerText : '',
  };
}"""


async def main():
    """Runs the rule."""
    journal = Journal("R224 — « En cours » holds « En vol » alone")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("()=>window.__go('acq-now-loaded')")
        await page.wait_for_timeout(SETTLED)
        read = await page.evaluate(BODY)
        journal.check("acq-now-loaded: the body draws exactly one section, « En vol »",
                      read["titles"] == [IN_FLIGHT], str(read["titles"]))
        journal.check("acq-now-loaded: none of the three sections that left is drawn",
                      not any(title in read["titles"] for title in GONE), str(read["titles"]))
        journal.check("acq-now-loaded: the tab counts what « En vol » draws",
                      bool(read["cards"]) and read["count"] == read["cards"][0],
                      f"count {read['count']}, cards {read['cards']}")

        await page.evaluate("()=>window.__go('acq-now-idle')")
        await page.wait_for_timeout(SETTLED)
        read = await page.evaluate(BODY)
        journal.check("acq-now-idle, nothing moving: the tab reads « rien en cours »",
                      EMPTY in read["text"].lower(), repr(read["text"][:160]))
        journal.check("acq-now-idle, nothing moving: no section is drawn",
                      read["titles"] == [], str(read["titles"]))
        journal.check("acq-now-idle, nothing moving: the tab carries no count",
                      read["count"] == 0, f"count {read['count']}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

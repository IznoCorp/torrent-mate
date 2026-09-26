"""R222 — « Abandonner » quarantines the folder, after a confirmation naming it.

A tunnel error awaits the operator's decision: relaunch it, or abandon it
(ruling 7). Abandoning QUARANTINES the folder — journaled, with the place it was
put — and destroys nothing without consent (NE-DOIT-PAS-6): a confirmation that
NAMES the medium comes first, and nothing is sent until he confirms.

Walked by finger on the tunnel-error card of « À traiter »:

1. a tap on « Abandonner » opens the confirmation, its text naming the card's
   medium, and the network has not been asked anything yet;
2. confirming is ANSWERED by the discard operation, the answer carrying the
   place the folder was put, which the confirmation's message says; the card
   leaves « À traiter »;
3. cancelling sends nothing, and the card stays.
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
TUNNEL_ERROR = next(row for row in json.loads((SEEDS / "stuck.json").read_text(encoding="utf-8"))
                    if row.get("failedStep"))["title"]
OPERATION = "discardStagedMedia"

DISCARDS = f"""() => (window.__mocks?.answered() || [])
  .filter(call => call.operationId === {json.dumps(OPERATION)} && call.status === 200).length"""
DIALOG = """() => {
  const dialog = document.querySelector('[data-part="dialog"][data-open]');
  return dialog ? dialog.textContent : null;
}"""
ON_TAB = """(title) => [...document.querySelectorAll('#view [data-part="card/title"]')]
  .some(one => one.textContent === title)"""
TOAST = """() => (document.querySelector('#toast') || {}).textContent || ''"""


async def open_confirmation(page, journal):
    """Opens « À traiter » and taps « Abandonner » on the tunnel error."""
    answer = await page.evaluate(
        "()=>{try{window.__go('acq-todo-loaded');return null}catch(error){return String(error)}}")
    journal.check("the named state acq-todo-loaded exists", answer is None, answer or "")
    await page.wait_for_timeout(SETTLED)
    before = await page.evaluate(DISCARDS)
    tapped = await page.evaluate("""(title)=>{
        const foot = [...document.querySelectorAll('#view [data-part="card/foot"]')]
          .find(one => one.getAttribute('data-journey-abandon') === title);
        if (!foot) return false; foot.click(); return true; }""", TUNNEL_ERROR)
    await page.wait_for_timeout(ACTED)
    return before, tapped


async def main():
    journal = Journal("R222 — « Abandonner » quarantines, after a confirmation naming the medium")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        before, tapped = await open_confirmation(page, journal)
        text = await page.evaluate(DIALOG)
        journal.check("« Abandonner » opens a confirmation naming the medium",
                      tapped and text is not None and TUNNEL_ERROR in text, repr(text))
        journal.check("and nothing is sent yet", await page.evaluate(DISCARDS) == before,
                      OPERATION)
        await page.evaluate("""()=>document.querySelector('[data-part="dialog"][data-open] [data-part="dialog/button"][data-tone="danger"]')?.click()""")
        await page.wait_for_timeout(ACTED)
        journal.check("confirming is answered by the discard operation",
                      await page.evaluate(DISCARDS) == before + 1, OPERATION)
        toast = await page.evaluate(TOAST)
        journal.check("and its message says where the folder was put",
                      TUNNEL_ERROR in toast and "/" in toast, repr(toast))
        journal.check("and the card leaves « À traiter »",
                      not await page.evaluate(ON_TAB, TUNNEL_ERROR), "")

        before, tapped = await open_confirmation(page, journal)
        # THE OTHER BUTTON of the confirmation, whatever it wears: the way out is
        # read as « not the dangerous one », so a cancel that lost its dismiss
        # and gained an act is still the button tapped.
        await page.evaluate("""()=>document.querySelector('[data-part="dialog"][data-open] [data-part="dialog/button"]:not([data-tone="danger"])')?.click()""")
        await page.wait_for_timeout(ACTED)
        journal.check("cancelling sends nothing, and the card stays",
                      tapped and await page.evaluate(DISCARDS) == before
                      and await page.evaluate(ON_TAB, TUNNEL_ERROR), "")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

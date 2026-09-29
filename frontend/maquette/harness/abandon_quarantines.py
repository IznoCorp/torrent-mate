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

ON A FOLLOW'S CARD the follow goes on (a series' follow never ends alone; §14.1
« récupéré ? non → changement de release »), on `acq-card-follow-error`: a
tunnel error POSED on « Furious », a real follow in flight — a derivation shown
as one (RULINGS 26); the backend reads the follow's own failed step instead.

4. the confirmation says another release will be searched;
5. confirming quarantines the folder, and the abandoned release is no longer
   offered for that title;
6. the card is back in « En vol » on « cherché », and the follow is still there.

« Top Chef », an arrival nobody followed, keeps the one-off behaviour: its card
closes (holds 1–3).
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, open_page, chrome_launch_args
from playwright.async_api import async_playwright

SEEDS = pathlib.Path(__file__).resolve().parents[1] / "design/src/mocks/seeds"
FOLLOWED = "Furious"
WORDS = json.loads((SEEDS.parents[1] / "i18n/fr.json").read_text(encoding="utf-8"))
SEARCHED = WORDS["surfaces"]["ladder"]["figure"].replace("{{position}}", "2").replace(
    "{{count}}", str(len(WORDS["surfaces"]["ladder"]["rungs"])))
ANOTHER = WORDS["verbs"]["acquisition"]["abandon"].get("bodyFollow", "(no such sentence)")
RELEASES = """async (title) => (await (await fetch('/api/acquisition/releases?title='
  + encodeURIComponent(title))).json()).map((release) => release.name)"""
FOLLOWS = """async () => (await (await fetch('/api/acquisition/followed')).json()).map((one) => one.title)"""
FIGURE = """(title) => { const card = [...document.querySelectorAll('#view [data-part="card"]')]
  .find(one => one.querySelector('[data-part="card/title"]')?.textContent === title);
  return card ? (card.querySelector('[data-part="card/meta"] > span:first-child') || {}).textContent ?? null : null; }"""
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
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
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
        # THE CANCEL IS FOUND, AND ITS EFFECT IS READ (round one, A12): a
        # `?.click()` on nothing passed, and the dialog was never read closing.
        cancelled = await page.evaluate("""()=>{const button = document.querySelector('[data-part="dialog"][data-open] [data-part="dialog/button"]:not([data-tone="danger"])');
            if (!button) return false; button.click(); return true;}""")
        await page.wait_for_timeout(ACTED)
        journal.check("cancelling closes the confirmation",
                      cancelled and await page.evaluate(DIALOG) is None, f"cancel found: {cancelled}")
        journal.check("cancelling sends nothing, and the card stays",
                      tapped and cancelled and await page.evaluate(DISCARDS) == before
                      and await page.evaluate(ON_TAB, TUNNEL_ERROR), "")

        # ON A FOLLOW'S CARD: another release is searched, the follow goes on.
        answer = await page.evaluate(
            "()=>{try{window.__go('acq-card-follow-error');return null}catch(error){return String(error)}}")
        journal.check("the named state acq-card-follow-error exists", answer is None, answer or "")
        await page.wait_for_timeout(SETTLED)
        offered = await page.evaluate(RELEASES, FOLLOWED)
        tapped = await page.evaluate("""(title)=>{
            const foot = [...document.querySelectorAll('#view [data-part="card/foot"]')]
              .find(one => one.getAttribute('data-journey-abandon') === title);
            if (!foot) return false; foot.click(); return true; }""", FOLLOWED)
        await page.wait_for_timeout(ACTED)
        text = await page.evaluate(DIALOG)
        journal.check("on a follow's card, the confirmation says another release will be searched",
                      tapped and text is not None and ANOTHER.strip() in text, repr(text))
        await page.evaluate("""()=>document.querySelector('[data-part="dialog"][data-open] [data-part="dialog/button"][data-tone="danger"]')?.click()""")
        await page.wait_for_timeout(ACTED)
        await page.evaluate("()=>window.__mocks.quiet()")
        after = await page.evaluate(RELEASES, FOLLOWED)
        journal.check("the abandoned release is no longer offered for that title",
                      bool(offered) and offered[0] not in after, f"{offered} → {after}")
        await page.evaluate("()=>window.__store.write({ acqTab: 'now' })")
        await page.wait_for_timeout(SETTLED)
        figure = await page.evaluate(FIGURE, FOLLOWED)
        journal.check("the card is back in « En vol », on « cherché »", figure == SEARCHED, repr(figure))
        journal.check("and the follow goes on", FOLLOWED in await page.evaluate(FOLLOWS), "")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

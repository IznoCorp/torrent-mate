"""R225 — a found release is taken from its follow's sheet, which says when it will be taken anyway.

What waits to be taken leaves « En cours »; the act stays on the follow's sheet,
and the sheet says what the machine will do without it: « trouvé, récupéré à la
prochaine passe, à <heure> » — the hour the scheduler's cadence names next.

WHAT IT HOLDS, on the real world at rest, for the first release the queue holds
to be taken of a medium the operator follows:

  the sentence  the follow's sheet reads « trouvé, récupéré à la prochaine passe,
                à <heure> », the hour computed here from the cadence the
                scheduler answers — its next slot after the page's own clock.
  the act       the same sheet offers « Récupérer maintenant » for that title.
  the take      a tap sends THAT FOLLOW's grab — `grabForFollow`, at the
                follow's own address, the backend's « claim now » — and the
                sheet opened again on that title no longer carries the sentence.
                RE-AIMED OUT LOUD: it counted `takeQueued`, an operation the
                backend never served; the per-follow grab is the one it does.

WHAT IT DOES NOT READ: the queue's optimistic move on the tap (R123's), or the
panel's other actions.
"""
import asyncio
import json
import pathlib

from common import ACTED, PANEL_IN, SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

LOCALE = pathlib.Path(__file__).resolve().parents[1] / "design/src/i18n/fr.json"
HOUR = json.loads(LOCALE.read_text(encoding="utf-8"))["screens"]["acquisition"]["cadence"]["hour"]
SENTENCE = "récupéré à la prochaine passe, à "  # french-ok: the sheet's own words, asserted present

# The next slot of a daily cron « M H1,H2 * * * » after the page's clock, read
# independently of the interface's own derivation.
NEXT_SLOT = """() => {
  const status = window.__queries.getQueryData(["/api/acquisition/status"]);
  const matched = /^(\\d+)\\s+([\\d,]+)\\s+\\*\\s+\\*\\s+\\*$/.exec(String(status?.cadence ?? "").trim());
  if (!matched) return null;
  const minute = Number(matched[1]);
  const hours = matched[2].split(",").map(Number).sort((a, b) => a - b);
  const now = new Date();
  const hour = hours.find((one) => one > now.getHours()
    || (one === now.getHours() && minute > now.getMinutes())) ?? hours[0];
  return { hour, minute: String(minute).padStart(2, "0") };
}"""

SHEET = """() => {
  const sheet = document.querySelector('#sheetin');
  const take = [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
    .find((one) => 'take' in one.dataset);
  return { text: sheet ? sheet.innerText.replace(/\\s+/g, ' ') : '', take: take ? take.dataset.take : null };
}"""

SENT = """(title) => (window.__mocks?.answered?.() || [])
  .filter((call) => call.operationId === "grabForFollow" && call.method === "POST"
    && decodeURIComponent(call.path) === `/api/acquisition/followed/${title}/grab`).length"""


async def open_follow(page, title):
    """Raises the follow's sheet about a title, and reads it."""
    await page.evaluate("()=>window.__panel?.close?.()")
    await page.wait_for_timeout(SETTLED)
    await page.evaluate("(title)=>window.__panel.produce('follow', title)", title)
    await page.wait_for_timeout(PANEL_IN + SETTLED)
    return await page.evaluate(SHEET)


async def main():
    """Runs the rule."""
    journal = Journal("R225 — a found release is taken from its follow's sheet")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.evaluate("()=>window.__go('acq-follows-list')")
        await page.wait_for_timeout(SETTLED)

        takeable = await page.evaluate("""()=>{
          const followed = (window.__followActions?.all() || []).map((one) => one.title);
          return (window.__queue?.().takeable || []).map((one) => one.title)
            .filter((title) => followed.includes(title));}""")
        journal.check("the queue holds a release of a followed medium to be taken, so the walk has a subject",
                      bool(takeable), str(takeable))
        title = takeable[0] if takeable else ""
        slot = await page.evaluate(NEXT_SLOT)
        journal.check("the scheduler's cadence is read", slot is not None, str(slot))
        hour = HOUR.replace("{{hour}}", str(slot["hour"])).replace("{{minute}}", slot["minute"]) if slot else "?"

        read = await open_follow(page, title)
        journal.check(f"« {title} »'s sheet says it will be taken at the next pass, at {hour}",
                      SENTENCE + hour in read["text"], read["text"][:240])
        journal.check(f"« {title} »'s sheet offers « Récupérer maintenant »",
                      read["take"] == title, str(read["take"]))

        before = await page.evaluate(SENT, title)
        await page.evaluate("""()=>[...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
          .find((one) => 'take' in one.dataset)?.click()""")
        await page.wait_for_timeout(ACTED + SETTLED)
        after = await page.evaluate(SENT, title)
        journal.check("the tap sends that follow's grab", after == before + 1, f"{before} → {after}")
        again = await open_follow(page, title)
        journal.check("the sheet opened again no longer says it waits for the next pass",
                      SENTENCE not in again["text"], again["text"][:240])

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

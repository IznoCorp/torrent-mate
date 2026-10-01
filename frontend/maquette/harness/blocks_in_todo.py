"""R500 — « À traiter » holds every block; « En cours » none (Q7).

The operator's Q7 of 2026-10-01: ONE list « À traiter » carries EVERYTHING that
is blocked and asks for an intervention, in the app or elsewhere — a disk full,
a ratio too low, a tracker that does not answer — and the deferred card moves
from « En cours » to « À traiter ». What merely waits in a visible queue behind a
maintenance run lifts with nobody's intervention: it stays in « En cours ».

What this holds:

1. on each moved deferral (`acq-card-deferred-ratio`, `-space`, `-missing`), the
   subject card is drawn in « À traiter », its reason line saying its cause;
2. on the same states, « En cours » does not draw it, and its count is the
   cards it draws;
3. on `acq-card-waiting`, the « En file » cards a maintenance run holds are in
   « En cours » and not in « À traiter ».

Red before the move: the deferred card is drawn in « En vol », not in « À
traiter » (maquette-blocked DESIGN § 0.1: « En cours » 6 on every deferral).
"""
import asyncio
import json
import pathlib

from common import ACTED, SETTLED, Journal, browser_channel, chrome_launch_args, open_page
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
REASONS = json.loads((SOURCE / "i18n/fr.json").read_text(encoding="utf-8"))["surfaces"]["ladder"]["reasons"]
SUBJECT = "This City Is Ours"
MOVED = [
    ("acq-card-deferred-ratio", "ratio_below_threshold"),
    ("acq-card-deferred-space", "insufficient_space"),
    ("acq-card-deferred-missing", "content_missing"),
]
CARDS = """() => [...document.querySelectorAll('#view [data-region="acquisition/body"] [data-part="card"]')]
  .filter(card => !card.closest('[data-part="section/set-aside"]'))
  .map(card => ({
    title: card.querySelector('[data-part="card/title"]')?.textContent.trim() ?? '',
    reason: card.querySelector('[data-part="card/reason"]')?.textContent.trim() ?? '',
    states: [...card.querySelectorAll('[data-part="card/step"]')].map(cell => cell.dataset.state),
  }))"""
COUNT = """(tab) => {
  const count = document.querySelector(`[data-acqtab="${tab}"] [data-part="segment/count"]`);
  return count ? Number(count.textContent.trim()) : null;
}"""


def opening(token):
    """The words a cause's sentence opens with, before any value it names."""
    return REASONS.get(token, "<no copy>").split("{{")[0].strip()


async def tab(page, value):
    """Taps one of Acquisition's tabs and reads the cards it draws."""
    await page.evaluate(f"()=>document.querySelector('[data-acqtab=\"{value}\"]')?.click()")
    await page.wait_for_timeout(ACTED)
    return await page.evaluate(CARDS)


async def main():
    journal = Journal("R500 — « À traiter » holds every block; « En cours » none")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state, token in MOVED:
            answer = await page.evaluate(
                "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
            await page.wait_for_timeout(SETTLED)
            journal.check(f"the named state {state} exists", answer is None, answer or "")
            todo = await tab(page, "todo")
            card = next((one for one in todo if one["title"] == SUBJECT), None)
            journal.check(f"{state}: « {SUBJECT} » is drawn in « À traiter », saying « {opening(token)} … »",
                          card is not None and opening(token) in card["reason"],
                          str(card) if card else str([one["title"] for one in todo]))
            now = await tab(page, "now")
            count = await page.evaluate(COUNT, "now")
            journal.check(f"{state}: « En cours » does not draw it",
                          SUBJECT not in [one["title"] for one in now], str([one["title"] for one in now]))
            journal.check(f"{state}: « En cours » counts the cards it draws",
                          count == len(now), f"count {count}, cards {len(now)}")

        await page.evaluate("()=>window.__go('acq-card-waiting')")
        await page.wait_for_timeout(SETTLED)
        now = await tab(page, "now")
        queued = [one["title"] for one in now if "waiting" in one["states"] and one["reason"]]
        todo = await tab(page, "todo")
        journal.check("acq-card-waiting: the cards a maintenance run holds stay in « En cours »",
                      bool(queued), str(len(queued)))
        journal.check("and none of them is in « À traiter »",
                      bool(queued) and not set(queued) & {one["title"] for one in todo},
                      str([one["title"] for one in todo]))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

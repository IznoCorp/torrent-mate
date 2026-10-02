"""A named state's own « Corriger » tap reaches that state alone (B-673).

Found by the harness on PR #681: `correct_arrives_with_candidates.py` fell one
run in two with the screen of the PREVIOUS state's folder. Two ways a state's
tap reached a decision it never asked for, each made deterministic here:

  1. `media-sheet-decision-corrected` tapped the first `decision/correct` in
     the DOCUMENT, and the previous state's sheet is still mounted for a frame
     or more after the reset. The decoy below stands for it, laid first in the
     document: a tap on it names a decision that is not in the cache and
     opens nothing, so the screen of the state's own folder never arrives.
  2. `acq-resolution-enqueued` taps its journey sheet 700 ms after it is asked
     and nothing stopped that timer. Driven away inside the 700 ms, the next
     state's own « Corriger » took the tap and opened a screen the state never
     showed.
"""
import asyncio

from common import Journal, open_page, read_at, screen_arrives, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

DECOY = """() => {
  const decoy = document.createElement('div');
  decoy.id = 'decoy';
  decoy.innerHTML = '<button data-part="decision/correct" data-decision-correct="decoy">decoy</button>';
  document.body.prepend(decoy);
}"""

OPEN_RESOLUTION = """() => document.querySelector('[data-part="screen"][data-open][data-key^="resolution:"]')?.dataset.key ?? null"""

# Longer than the tap's 700 ms, with the sheet's own entrance and the call's round trip.
PAST_THE_TAP = 1800


async def main():
    journal = Journal("A state's « Corriger » tap reaches that state alone")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate(DECOY)
        await page.evaluate("(id) => window.__go(id)", "media-sheet-decision-corrected")
        arrived = await screen_arrives(page, "resolution:The Bombing of Pan Am 103")
        journal.check("the tap of a state goes to the act of its own sheet: the screen of ITS folder opens", arrived,
                      str(await page.evaluate(OPEN_RESOLUTION)))

        await page.evaluate("(id) => window.__go(id)", "acq-resolution-enqueued")
        await page.evaluate("(id) => window.__go(id)", "sheet-journey-decision-operator")
        await page.wait_for_timeout(PAST_THE_TAP)
        journal.check("a state driven away before its tap fires never taps",
                      await page.evaluate(OPEN_RESOLUTION) is None, str(await page.evaluate(OPEN_RESOLUTION)))
        journal.check("and the next state's sheet stands, with its own « Corriger »",
                      await page.evaluate("() => !!document.querySelector('#sheet[data-open] [data-part=\"decision/correct\"]')"))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

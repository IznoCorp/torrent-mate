"""R514 — the Médiathèque does what it says: its search acts on « Incomplets », and a removal that stops the follow stops it (B-688, B-689).

B-688. « Incomplets » drew the search field and never read it: typing a title
left all twelve incomplete series on screen. WHAT IS READ: on `lib-incomplete`,
a title typed in `#libq` the way a finger types it leaves exactly the series
whose title holds it, and emptying the field brings every one back.

B-689. « Supprimer et arrêter le suivi » on Silo's sheet said « Le suivi est
arrêté » and stopped nothing: the two confirmations removed the same titles and
differed only in their sentence, so Suivis, the follow panel and the sheet went
on reading the follow. WHAT IS READ: on `mediasheet-series` (« Silo (2023) »,
followed as « Silo »), the sheet's « Supprimer », then the confirmation —
  1. « Supprimer et arrêter le suivi »: the layer is asked to remove the follow
     « Silo » and answers 200, and the follows the surfaces read hold no « Silo »;
  2. « Supprimer, garder le suivi », on a fresh layer: no follow is removed, and
     « Silo » is still followed.
"""
import asyncio
import json

from common import SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

# The words of the two confirmations, read from the one place they live.
WORDS = json.loads(
    (__import__("pathlib").Path(__file__).resolve().parents[1] / "design/src/i18n/fr.json").read_text())
DELETE = WORDS["verbs"]["library"]["delete"]

# The titles « Incomplets » draws: every card's or tile's sheet, in the lens' body.
DRAWN = """() => [...document.querySelectorAll('[data-region="library/body"] [data-mediasheet]')]
  .map((element) => element.getAttribute('data-mediasheet'))"""

# Types into the search field the way a finger does: the value, then `input`.
TYPE = """(text) => { const field = document.querySelector('#libq');
  field.value = text; field.dispatchEvent(new Event('input', {bubbles: true})); }"""

# What the follows the surfaces read hold, and the follow removals the layer answered.
FOLLOWS = """() => ({
  titles: (window.__queries.getQueryCache().getAll()
    .find((query) => query.queryKey[0] === '/api/acquisition/followed' && query.queryKey.length <= 2)
    ?.state.data ?? []).map((follow) => follow.title),
  removals: window.__mocks.answered()
    .filter((call) => call.operationId === 'deleteFollow').map((call) => call.path + ' ' + call.status),
})"""


async def settles(page, condition):
    """Waits until the page says `condition`, and answers whether it ever did.

    A wait that raises ends the rule at its first broken promise; this one lets
    each promise be READ, so a red run names every defect it finds.

    Args:
        page: The Playwright page.
        condition: A JavaScript expression, true once the page has settled.

    Returns:
        True once the condition held, False when it never did.
    """
    try:
        await page.wait_for_function(f"() => {condition}", timeout=5000)
        return True
    except Exception:  # noqa: BLE001 — Playwright's timeout, read as a verdict
        return False


async def confirm(page, words):
    """Opens the sheet's removal and presses the confirmation that says `words`.

    Args:
        page: The Playwright page, on Silo's sheet.
        words: The confirmation's text.
    """
    await page.click('[data-part="screen"][data-open] [data-del]')
    button = page.locator('#dlg[data-open] [data-part="dialog/button"]', has_text=words)
    await button.wait_for(state="visible")
    await button.click()
    await page.wait_for_function("() => window.__mocks.inFlight() === 0")


async def main():
    journal = Journal("R514 — the Médiathèque does what it says")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # --- B-688: the search acts on « Incomplets » ------------------------
        every = await read_at(page, "lib-incomplete", DRAWN)
        journal.check("lib-incomplete: the lens draws its series", len(every) > 1, str(len(every)))
        await page.evaluate(TYPE, "fri")
        await settles(page, f"({DRAWN})().length < {len(every)}")
        searched = await page.evaluate(DRAWN)
        wanted = [title for title in every if "fri" in title.lower()]
        journal.check("« fri » typed: the lens draws exactly the series whose title holds it",
                      bool(wanted) and searched == wanted, str({"drawn": searched, "wanted": wanted}))
        await page.evaluate(TYPE, "")
        await settles(page, f"({DRAWN})().length === {len(every)}")
        journal.check("the field emptied: every series is back", await page.evaluate(DRAWN) == every)

        # --- B-689: « Supprimer et arrêter le suivi » stops the follow --------
        before = await read_at(page, "mediasheet-series", FOLLOWS, wait=SETTLED)
        journal.check("mediasheet-series: « Silo » is followed before the removal",
                      "Silo" in before["titles"], str(before["titles"]))
        await confirm(page, DELETE["deleteAndStop"])
        after = await page.evaluate(FOLLOWS)
        journal.check("« Supprimer et arrêter le suivi »: the layer removed the follow « Silo »",
                      any(call.endswith("/Silo 200") for call in after["removals"]), str(after["removals"]))
        journal.check("« Supprimer et arrêter le suivi »: no surface reads « Silo » followed",
                      "Silo" not in after["titles"], str(after["titles"]))

        await page.evaluate("() => window.__mocks.reset()")
        await read_at(page, "mediasheet-series", FOLLOWS, wait=SETTLED)
        await confirm(page, DELETE["deleteAndKeep"])
        kept = await page.evaluate(FOLLOWS)
        journal.check("« Supprimer, garder le suivi »: no follow is removed", kept["removals"] == [],
                      str(kept["removals"]))
        journal.check("« Supprimer, garder le suivi »: « Silo » is still followed",
                      "Silo" in kept["titles"], str(kept["titles"]))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

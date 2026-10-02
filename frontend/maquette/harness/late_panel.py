"""R513 — a panel asked for before its read landed does not open after the interface moved on.

Found while diagnosing B-675. A producer reads the query cache, and when what it
needs has not landed the panel host asks for it and opens the panel when the
answer comes (`producePanel`'s deferred open). That open was applied whatever
had happened meanwhile: a finger that tapped a card, then the bar, saw the
card's panel slide up a beat later over the page it had gone to — a sheet nobody
asked for on that page, its entry pushed over the landing.

What this holds, by finger, with the read held back by the mock layer's latency:

1. a deferred open still opens when nothing moved — the account menu on a cold
   account, a follow's panel on a title asked about for the first time;
2. a follow's panel asked for, then the bar tapped: the panel never opens over
   the page landed on;
3. the account menu asked for, then Retour: the menu never opens over the page
   Retour gave back;
4. a follow's panel asked for, then the account menu opened and closed: the
   follow's panel does not open after the menu was closed.

Red before the repair: holds 2, 3 and 4 — the late answer opened its panel.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, Journal, browser_channel, chrome_launch_args, open_page

# How long the held read takes: long enough that every move below is made while
# it is out, short enough to keep the rule quick.
LATENCY = 1500
# Waited after a move: the held read lands, and the panel would have risen.
LANDED = LATENCY + PANEL_IN + 400

AVATAR = "[data-account]"
BAR = '[data-part="shell/tab-bar"]'
FOLLOW_CARD = '#view [data-region="acquisition/body"] [data-part="card"] .cbody'

WHERE = """() => ({ page: window.__store?.read?.().state.page ?? null, path: location.pathname,
  sheetOpen: document.querySelector('#sheet')?.dataset.open === 'true',
  title: document.querySelector('#sheet')?.getAttribute('aria-label') ?? null })"""

HOLD_ACCOUNT = """(latency) => {
  window.__mocks.setOperationOutcome('readAccount', { latencyMilliseconds: latency });
  window.__queries.removeQueries({ queryKey: ['/api/auth/me'] });
}"""

HOLD_MEMBERSHIP = """(latency) => {
  window.__mocks.setOperationOutcome('readLibraryMembership', { latencyMilliseconds: latency });
  window.__queries.removeQueries({ queryKey: ['/api/library/membership'] });
}"""


async def fresh(browser):
    """Opens the prototype on the acquisition page, past the startup screen."""
    context, page = await open_page(browser)
    await page.wait_for_timeout(ACTED)
    return context, page


async def hold(journal):
    """Moves the interface while a panel's read is out, and reads what rises."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel=browser_channel(), args=chrome_launch_args())

        # 1. Nothing moves: the deferred opens still open.
        context, page = await fresh(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.evaluate(HOLD_ACCOUNT, LATENCY)
        await page.tap(AVATAR)
        await page.wait_for_timeout(LANDED)
        still = await page.evaluate(WHERE)
        journal.check("a cold account menu opens once its read lands, nothing having moved",
                      still["sheetOpen"], f"after {LANDED} ms: {still}")
        await context.close()

        context, page = await fresh(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.evaluate(HOLD_MEMBERSHIP, LATENCY)
        await page.tap(FOLLOW_CARD)
        await page.wait_for_timeout(LANDED)
        still = await page.evaluate(WHERE)
        journal.check("a follow's panel asked for the first time opens once its read lands",
                      still["sheetOpen"], f"after {LANDED} ms: {still}")
        await context.close()

        # 2. A follow's panel asked for, then the bar.
        context, page = await fresh(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.evaluate(HOLD_MEMBERSHIP, LATENCY)
        await page.tap(FOLLOW_CARD)
        asked = await page.evaluate(WHERE)
        await page.tap(f'{BAR} [data-page="lib"]')
        await page.wait_for_timeout(LANDED)
        moved = await page.evaluate(WHERE)
        journal.check("the read was still out when the bar was tapped",
                      not asked["sheetOpen"], f"right after the tap on the card: {asked}")
        journal.check("a follow's panel asked for, then the bar: it never opens over the page landed on",
                      moved["page"] == "lib" and not moved["sheetOpen"],
                      f"after {LANDED} ms: {moved}")
        await context.close()

        # 3. The account menu asked for, then Retour.
        context, page = await fresh(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.tap(f'{BAR} [data-page="lib"]')
        await page.wait_for_timeout(ACTED)
        await page.evaluate(HOLD_ACCOUNT, LATENCY)
        await page.tap(AVATAR)
        asked = await page.evaluate(WHERE)
        await page.go_back()
        await page.wait_for_timeout(LANDED)
        moved = await page.evaluate(WHERE)
        journal.check("the account's read was still out when Retour was made",
                      not asked["sheetOpen"], f"right after the tap on the avatar: {asked}")
        journal.check("the account menu asked for, then Retour: it never opens over the page given back",
                      moved["page"] == "acq" and not moved["sheetOpen"],
                      f"after {LANDED} ms: {moved}")
        await context.close()

        # 4. A follow's panel asked for, then another sheet opened and closed.
        context, page = await fresh(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.evaluate(HOLD_MEMBERSHIP, LATENCY)
        await page.tap(FOLLOW_CARD)
        await page.tap(AVATAR)
        await page.wait_for_timeout(PANEL_IN)
        menu = await page.evaluate(WHERE)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(LANDED)
        moved = await page.evaluate(WHERE)
        journal.check("the account menu opened over the card's pending panel",
                      menu["sheetOpen"], f"after the tap on the avatar: {menu}")
        journal.check("a follow's panel asked for, then a sheet opened and closed: it does not rise after",
                      not moved["sheetOpen"], f"after {LANDED} ms: {moved}")
        await context.close()

        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R513 — a panel asked for before its read landed does not open after the interface moved on")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()

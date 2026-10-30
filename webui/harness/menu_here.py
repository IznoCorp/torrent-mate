"""R511 — the account sheet says which of its places one is already on (B-675).

B-675, the TM Bugs report of 2026-10-02: « Quand je clique sur profils et
préférences, ça n'ouvre pas d'autre page, ça ne mène à rien ». Its screenshot is
the account sheet open over the profile page, at the top of that page. Measured
before the repair, in WebKit and Chromium, on the served copy and on tm-design:
from any other page the entry lands on the profile and closes the sheet; ON the
profile page it closes the sheet and nothing else moves (`switchPageFromLayer`:
the page one is on is no arrival). So the sheet offered, on the profile, an
entry to the profile, drawn exactly like an entry that leads elsewhere — a tap
that « leads nowhere ».

The side menu has said « you are here » since L13 (`aria-current="page"`, the
brand colour on a tint of it). A menu's entry in a SHEET — an action carrying
`data-destination` — now says it the same way.

What this holds, by finger:

1. off the profile page, the sheet's « Profil et préférences » carries no
   `aria-current`, and a tap lands on the profile with the sheet closed;
2. on the profile page, the same entry carries `aria-current="page"`, and it is
   PAINTED as the side menu paints its current entry — the same colour, the
   same surface — so the mark is the menu's and not a new drawing;
3. a tap on it there closes the sheet, stays on the profile, and writes no
   history entry.

Red before the repair: hold 2 — no entry of a sheet ever carried the mark.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, PANEL_IN, Journal, browser_channel, chrome_launch_args, open_page

AVATAR = "[data-account]"
ENTRY = '#sheet [data-go="profile"]'
# The side menu's own mark, read on the entry of the page it is opened over.
MENU_CURRENT = '[data-navgo][aria-current="page"]'

READ_ENTRY = """(selector) => {
  const entry = document.querySelector(selector);
  if (!entry) return null;
  const style = getComputedStyle(entry);
  return { current: entry.getAttribute("aria-current"), color: style.color,
           background: style.backgroundColor };
}"""

WHERE = """() => ({ page: window.__store?.read?.().state.page ?? null,
  path: location.pathname, length: history.length,
  sheetOpen: document.querySelector('#sheet')?.dataset.open === 'true' })"""


async def open_sheet(page):
    """Opens the account sheet by the header's avatar, as a finger does."""
    await page.tap(AVATAR)
    await page.wait_for_timeout(PANEL_IN)


async def hold(journal):
    """Walks the account sheet off and on the profile page."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))

        # The side menu's current entry, painted: the reference the sheet must match.
        await page.tap('[data-part="shell/header"] [data-drawer]')
        await page.wait_for_timeout(PANEL_IN)
        menu = await page.evaluate(READ_ENTRY, MENU_CURRENT)
        journal.check("the side menu marks the page it is opened over", menu is not None,
                      "no `aria-current` entry in the drawer — the reference this rule compares with is gone")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(PANEL_IN)

        await open_sheet(page)
        away = await page.evaluate(READ_ENTRY, ENTRY)
        journal.check("off the profile, the sheet offers « Profil et préférences »", away is not None,
                      "no profile entry in the open account sheet")
        journal.check("off the profile, the entry says no « you are here »",
                      away is not None and away["current"] is None,
                      f"aria-current reads {away and away['current']!r} on a page that is not the profile")
        await page.tap(ENTRY)
        await page.wait_for_timeout(ACTED)
        landed = await page.evaluate(WHERE)
        journal.check("the entry lands on the profile with the sheet closed",
                      landed["path"] == "/account" and not landed["sheetOpen"],
                      f"after the tap: {landed}")

        await open_sheet(page)
        here = await page.evaluate(READ_ENTRY, ENTRY)
        journal.check("on the profile, the entry says « you are here » (aria-current=page)",
                      here is not None and here["current"] == "page",
                      f"aria-current reads {here and here['current']!r} — the sheet offers the page one is on "
                      "as if it led elsewhere, and its tap « ne mène à rien » (B-675)")
        if menu is not None and here is not None:
            journal.check("on the profile, the entry is painted with the side menu's mark",
                          here["color"] == menu["color"] and here["background"] == menu["background"],
                          f"sheet entry {here['color']} on {here['background']}, menu's current entry "
                          f"{menu['color']} on {menu['background']}")
        before = await page.evaluate(WHERE)
        await page.tap(ENTRY)
        await page.wait_for_timeout(ACTED)
        after = await page.evaluate(WHERE)
        journal.check("a tap on it closes the sheet and stays on the profile",
                      not after["sheetOpen"] and after["path"] == "/account",
                      f"before {before}, after {after}")
        journal.check("and writes no history entry",
                      after["length"] == before["length"],
                      f"history.length {before['length']} → {after['length']}")

        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R511 — the account sheet says which of its places one is already on (B-675)")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()

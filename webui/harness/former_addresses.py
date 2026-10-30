"""R406 — a former production address answers not-found (L24 S4, OPEN 4 = A, OPEN 9 = A).

The operator, 2026-09-29: « A, pas de gestion de rétro-compatibilité ! » — the
new version handles NO backward compatibility of former addresses or links: no
alias, no redirect (precedents `/arrivals`, the French addresses). Every dead
production path answers the not-found page, and no successor is named anywhere.

WHAT IS READ, each address loaded COLD:

  1. every dead production path — `/control`, `/pipeline`, `/pipeline?run=…`,
     `/config`, `/scraping`, `/registry`, and the French `/medias`, `/systeme`,
     `/controle` — draws the not-found page, and the address stays as typed;
  2. a LIVE page reached with a dial production had and the maquette does not —
     `/media?media=…`, `/media?decision=…`, `/system?tab=…`,
     `/maintenance?run=…` — lands on that page, never on an error: an unknown
     dial is ignored (D1). `/maintenance` exists, so its production `?run=` is
     one of these, not a dead address.
"""
import asyncio
from common import PROTOTYPE, SETTLED, Journal, open_page, browser_channel, chrome_launch_args, PAGE_PATHS
from playwright.async_api import async_playwright

DEAD = ("/control", "/pipeline", "/pipeline?run=2b598104071b470fb27ea0dd2c357a0f", "/config", "/scraping",
        "/registry", "/medias", "/systeme", "/controle")
LIVE = (("/media?media=42", "lib"), ("/media?decision=7", "lib"), ("/system?tab=health", "sys"),
        ("/maintenance?run=2b598104071b470fb27ea0dd2c357a0f", "maint"))

LANDED = """() => ({page: state.page, path: location.pathname})"""


async def cold(context, address, errors):
    """Loads one address cold and reads where it landed.

    Args:
        context: The browser context.
        address: The address, with its query.
        errors: Where JS errors are collected.

    Returns:
        The page and the path the frame shows.
    """
    page = await context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    await page.goto(f"{PROTOTYPE}{address.lstrip('/')}", wait_until="load")
    await page.evaluate("() => window.__loadingDone?.()")
    await page.wait_for_timeout(SETTLED)
    landed = await page.evaluate(LANDED)
    await page.close()
    return landed


async def main():
    journal = Journal("R406 — a former production address answers not-found")
    journal.check("the live pages the dials land on exist",
                  all(page in PAGE_PATHS for _, page in LIVE), str(sorted(PAGE_PATHS)))
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, _ = await open_page(browser)
        errors = []
        for address in DEAD:
            landed = await cold(context, address, errors)
            path = address.split("?")[0]
            journal.check(f"« {address} » draws the not-found page, the address as typed",
                          landed["page"] == "404" and landed["path"] == path, str(landed))
        for address, page in LIVE:
            landed = await cold(context, address, errors)
            journal.check(f"« {address} » lands on its live page, the dial ignored",
                          landed["page"] == page and landed["path"] == PAGE_PATHS[page], str(landed))
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

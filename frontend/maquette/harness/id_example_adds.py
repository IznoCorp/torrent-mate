"""R517 — the example the identifier field shows, typed as it is, adds a medium (B-691).

« Pour l'ajout d'un suivi, par identifiant, il est noté « 1234 » comme exemple. Je
teste 1234 et cela ne fonctionne pas car ce n'est pas le format attendu pour un
identifiant TMDB, l'exemple « 1234 » est trompeur » (Laura, TM Bugs). The field
showed « 1234 » for TMDB and TVDB alike, an identifier no medium of the maquette
carries, and « Ajouter » was drawn disabled whatever was typed.

WHAT IS READ, for each source of the « + » screen's « Ou ajouter par identifiant »:
  1. empty, « Ajouter » waits and the screen says why;
  2. the placeholder is an example in the source's own format;
  3. that example typed as it is enables « Ajouter », and the tap creates the
     follow: the layer answers the create, and the follows the surfaces read
     hold the medium;
  4. an identifier no medium carries is answered « not found », under the field.
"""
import asyncio
import re

from common import PANEL_IN, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

# The medium each source's example names, as the provider search titles it.
EXPECTED = {
    "TMDB": "Star Wars : Les Aventures des Petits Jedi",
    "TVDB": "Star Wars : Les Aventures des Petits Jedi",
    "IMDB": "Star Wars : The Clone Wars",
}

# An identifier in a placeholder: « tt » and digits, or digits.
IDENTIFIER = re.compile(r"(tt\d+|\d+)")

# What the screen and the layer say of the identifier block.
READ = """() => ({
  placeholder: document.querySelector('#byidv')?.getAttribute('placeholder') ?? '',
  disabled: document.querySelector('[data-part="add/id-submit"]')?.disabled ?? null,
  waiting: !!document.querySelector('[data-part="add/id-waiting"]'),
  missing: document.querySelector('[data-part="add/id-missing"]')?.textContent ?? null,
  follows: (window.__queries.getQueryCache().getAll()
    .find((query) => query.queryKey[0] === '/api/acquisition/followed' && query.queryKey.length <= 2)
    ?.state.data ?? []).map((follow) => follow.title),
  creates: window.__mocks.answered().filter((call) => call.operationId === 'createFollow')
    .map((call) => call.status),
})"""

OPEN_BLOCK = "() => document.querySelector('[data-part=\"add/by-id\"] summary')?.click()"


async def open_block(browser, provider):
    """Opens the « + » screen's identifier block on one source, in a fresh context.

    A FRESH CONTEXT PER SOURCE: TMDB's and TVDB's examples name the same medium,
    and a follow the first created would answer the second « already followed ».

    Args:
        browser: The launched browser.
        provider: The source's switch label.

    Returns:
        The (context, page) pair.
    """
    context, page = await open_page(browser)
    await read_at(page, "acq-add-empty", "() => null", wait=PANEL_IN + SETTLED)
    await page.evaluate(OPEN_BLOCK)
    await page.click(f'[data-part="add/by-id"] [data-part="view/switch"] button:text-is("{provider}")')
    await page.wait_for_timeout(SETTLED)
    return context, page


async def main():
    journal = Journal("R517 — the identifier field's example adds a medium")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        for provider, title in EXPECTED.items():
            context, page = await open_block(browser, provider)
            page.on("pageerror", lambda error: errors.append(str(error)))
            rest = await page.evaluate(READ)
            journal.check(f"{provider}: empty, « Ajouter » waits and the screen says why",
                          rest["disabled"] is True and rest["waiting"], str(rest))
            found = IDENTIFIER.search(rest["placeholder"])
            example = found.group(1) if found else ""
            wanted = r"^tt\d+$" if provider == "IMDB" else r"^\d+$"
            journal.check(f"{provider}: the placeholder is an example in the source's format",
                          re.match(wanted, example) is not None, rest["placeholder"])
            await page.fill("#byidv", example)
            typed = await page.evaluate(READ)
            journal.check(f"{provider}: the example typed enables « Ajouter »", typed["disabled"] is False,
                          str(typed["disabled"]))
            await page.click('[data-part="add/id-submit"]')
            await page.wait_for_function("() => window.__mocks.inFlight() === 0")
            await page.wait_for_timeout(SETTLED)
            done = await page.evaluate(READ)
            journal.check(f"{provider}: the tap creates the follow of « {title} »",
                          title in done["follows"] and any(status < 300 for status in done["creates"]),
                          f"creates {done['creates']}, follows hold it: {title in done['follows']}")
            await context.close()

        context, page = await open_block(browser, "TMDB")
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.fill("#byidv", "1234")
        await page.click('[data-part="add/id-submit"]')
        await page.wait_for_function("() => window.__mocks.inFlight() === 0")
        await page.wait_for_timeout(SETTLED)
        unknown = await page.evaluate(READ)
        journal.check("an identifier no medium carries is answered « not found »",
                      unknown["missing"] is not None and unknown["creates"] == [], str(unknown))
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

"""R236 — a navigation badge reads an answer the frame keeps observed, from any page.

A badge is a function its row points at, reading the query cache synchronously
(`app/navigation.ts`). A synchronous read is not an observer: a query nobody
observes is not refetched when a live event invalidates it, and is dropped from
the cache five minutes after its last observer left. So a badge read from a page
that does not draw its own subject froze on whatever the boot had fetched, and a
live event that changed the subject changed nothing on the button.

Each row that carries a badge therefore DECLARES the reads its badge derives
from, and the frame observes them for the document's lifetime — one observer
per row the frame DRAWS, so a row not drawn asks for nothing.

On a cold load of the Médiathèque — a page that reads nothing of Acquisition:

1. the Acquisition button carries the seeded « À traiter » count;
2. the server empties « À traiter » and says so with a live event the backend
   emits: the badge is gone — absent, never « 0 » — without the operator
   having opened Acquisition.

THE BADGE COUNTS WITHOUT RIGHTS, and that is said rather than left to be found:
no right exists yet. The rights half — a row the account cannot open registers
no observer and sends no read — is written with the rights model, and mutated
there.
"""
import asyncio

from common import PHONE, PROTOTYPE, SETTLED, Journal
from playwright.async_api import async_playwright

LIBRARY = "media"
BADGE = """() => {
  const badge = document.querySelector('#nav button[data-page="acq"] [data-part="shell/tab-badge"]');
  return badge ? badge.textContent.trim() : null;
}"""
CURRENT = "() => document.querySelector('#nav button[aria-current=\"page\"]')?.dataset.page ?? null"


async def main():
    journal = Journal("R236 — a navigation badge reads an answer the frame keeps observed")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context = await browser.new_context(**PHONE)
        page = await context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(PROTOTYPE + LIBRARY, wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await page.evaluate("()=>window.__mocks.quiet()")
        await page.wait_for_timeout(SETTLED)

        current = await page.evaluate(CURRENT)
        journal.check("the cold load lands on the Médiathèque, not on Acquisition", current == "lib", str(current))
        seeded = await page.evaluate(BADGE)
        journal.check("on a cold load of another page, Acquisition's button carries the seeded count",
                      seeded is not None and seeded.isdigit() and int(seeded) > 0, str(seeded))

        await page.evaluate("""async () => {
          window.__mocks.clearBlocked();
          window.__mocks.stream.emit("WantedAbandoned", {});
          await window.__mocks.quiet();
        }""")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("()=>window.__mocks.quiet()")
        after = await page.evaluate(BADGE)
        journal.check("after a live event empties « À traiter », the badge is gone from the other page",
                      after is None, f"still reads {after}")

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

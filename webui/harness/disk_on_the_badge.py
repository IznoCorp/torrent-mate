"""R410 — a filling disk speaks on the menu's badge (L24, OPEN 2 = A).

The operator, 2026-09-29, « A »: a disk « bientôt plein » and a library-index
anomaly COUNT in the menu button's badge (Système), beside the maintenance
facts and the faults (round 5 Q8) — each read on the fact's own tone, never on
its words. The seed at rest is the operator's real machine: Disk2 nearly full,
anomalies to clean — so at rest the badge says so (orchestrator's ruling B,
2026-09-30: the seed is not moved to look calm).

WHAT IS READ, on the Médiathèque, a page that draws nothing of Système:

  1. `system-disk-filling` (the machine at rest): the menu button's number
     counts the served disks and index facts whose state asks for care, on top
     of the maintenance facts and the faults;
  2. the same machine POSED healthy — every disk with room, no anomaly: the
     number drops by exactly those facts;
  3. `menu-clear`: no badge at all.
"""
import asyncio

from common import SETTLED, Journal, open_page, read_at, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

BUTTON = """() => document.querySelector('[data-drawer] [data-part="shell/menu-badge"]')?.textContent.trim() ?? null"""
CARE = """async () => {
  const read = async (address) => (await fetch(address)).json();
  const facts = [...await read('/api/v1/maintenance/disks'), ...await read('/api/v1/maintenance/index-health')];
  return facts.filter((fact) => fact.state === 'nearly_full' || fact.state === 'to_clean').length;
}"""


async def main():
    journal = Journal("R410 — a filling disk speaks on the menu's badge")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        filling = await read_at(page, "system-disk-filling", BUTTON, wait=SETTLED * 2)
        care = await page.evaluate(CARE)
        journal.check("at rest, the served disks and index hold facts that ask for care", care >= 2, str(care))
        await page.evaluate("() => { window.__mocks.setMachineHealthy(true); window.__queries.invalidateQueries(); }")
        await page.wait_for_timeout(SETTLED * 2)
        healthy = await page.evaluate(BUTTON)
        journal.check("the badge counts them: posed healthy, it drops by exactly that many",
                      filling is not None and int(filling) - int(healthy or 0) == care,
                      f"at rest {filling}, healthy {healthy}, care {care}")

        clear = await read_at(page, "menu-clear", BUTTON, wait=SETTLED * 2)
        journal.check("menu-clear: no badge at all", clear is None, str(clear))

        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

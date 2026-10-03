"""R423 — « Réaffecter… »: offered by right, filtered to who sees the card, and the move is the server's (§ 17).

DESIGN maquette-l18 § 3.5, § 5 (R-L18-i, R-L18-j), round 8 Q13 = A, M9, F27.

1. R-L18-i — THE OFFER: the journey panel carries « Réaffecter… » for the owner (Admin holds
   `acquisition.reassign`) and not for a household member who sees everyone's cards.
2. R-L18-i — M9: the chooser lists the accounts that SEE the card — its other requesters and
   the roles holding `acquisition.see.others` — never the whole roster.
3. R-L18-j — THE MOVE: tapping an account calls `reassignRequester`; the card's requesters
   are then the server's answer — the one moved off gone, the chosen one on, the others kept —
   and its line says so. Forced by a household member, the call answers 403.
"""
import asyncio
import json
import pathlib

from common import SETTLED, PANEL_IN, ACTED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "design/src"
SEEDS = json.loads((SOURCE / "mocks/seeds/accounts.json").read_text(encoding="utf-8"))
CARD = "Star Trek: Strange New Worlds (2022)"
# The chooser's state turns the test roster on (its invented requests are the test accounts').
ROLES = SEEDS["roles"] + SEEDS["testRoles"]
ACCOUNTS = SEEDS["accounts"] + SEEDS["testAccounts"]
SEES = {role["id"] for role in ROLES if "acquisition.see.others" in role["rights"]}

CHOICES = """() => [...document.querySelectorAll('#sheet [data-reassign-to]')]
  .map((one) => ({ value: one.getAttribute('data-reassign-to'), text: one.textContent }))"""
OFFERED = "() => !!document.querySelector('#sheet [data-panel^=\"reassign:\"]')"
REQUESTERS = """async (title) => {
  const queue = await (await fetch('/api/v1/acquisition/to-handle')).json();
  const card = Object.values(queue).flat().find((one) => one.title === title);
  return card ? card.requesters.map((one) => one.id) : null;
}"""


async def main():
    journal = Journal("R423 — « Réaffecter… », by right, to who sees the card")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("()=>window.__go('acq-card-plural-requesters')")
        await page.wait_for_timeout(SETTLED)
        await page.evaluate("(title)=>window.__panel.produce('journey', title)", CARD)
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        journal.check("R-L18-i: the owner's journey panel offers « Réaffecter… »", await page.evaluate(OFFERED))
        await page.evaluate("()=>window.__go('acq-card-read-only')")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        journal.check("R-L18-i: a household member who sees everything is not offered it",
                      not await page.evaluate(OFFERED))

        await page.evaluate("()=>window.__go('acq-reassign-chooser')")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        choices = await page.evaluate(CHOICES)
        before = await page.evaluate(REQUESTERS, CARD)
        chosen = sorted(choice["value"].split("|")[3] for choice in choices)
        expected = sorted(one["id"] for one in ACCOUNTS
                          if (one["id"] in (before or []) or one["role"] in SEES) and one["id"] != (before or [""])[0])
        journal.check("R-L18-i (M9): the chooser lists exactly the accounts that see the card", chosen == expected,
                      f"offered {chosen}, expected {expected}, requesters {before}")

        target = next((choice for choice in choices if choice["value"].split("|")[3] not in (before or [])), None)
        journal.check("R-L18-j: an account not yet a requester is offered", target is not None, str(choices))
        if target:
            await page.click(f'#sheet [data-reassign-to="{target["value"]}"]')
            await page.wait_for_timeout(ACTED + SETTLED)
            called = await page.evaluate("""() => window.__mocks.answered()
              .filter((one) => one.operationId === 'reassignRequester').map((one) => one.status)""")
            after = await page.evaluate(REQUESTERS, CARD)
            moved_off, moved_on = before[0], target["value"].split("|")[3]
            journal.check("R-L18-j: the tap calls reassignRequester", called == [200], str(called))
            journal.check("R-L18-j: one requester off, the chosen one on, the others kept",
                          after is not None and moved_off not in after and moved_on in after
                          and all(one in after for one in before[1:]), f"{before} → {after}")

        await page.evaluate("()=>window.__go('acq-household')")
        await page.wait_for_timeout(SETTLED)
        forced = await page.evaluate("""async (title) => (await fetch('/api/v1/acquisition/requesters/reassign', {
          method: 'POST', body: JSON.stringify({ kind: 'card', title, from: 'household-member', to: 'guest' }) })).status""",
                                     CARD)
        journal.check("R-L18-j: forced by a household member, the move answers 403", forced == 403, str(forced))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

"""R424 — quality and pause are per acquisition, per requester, and role-gated (§ 17; round 10 Q6).

DESIGN maquette-l18 § 3.4 point 5, § 5 (R-L18-l, R-L18-l-bis).

1. R-L18-l — « THE HIGHEST WINS » COUNTS ONLY THE REQUESTERS WHOSE ROLE HOLDS THE RIGHT: on a
   follow four accounts asked for, a guest's seeded 2160p is ignored and the floor in force is
   the highest of the others'. Setting one's own floor moves it; a guest forcing it gets 403.
2. R-L18-l-bis — « PAUSED » HOLDS ONLY WHEN EVERY REQUESTER HOLDING `acquisition.pause.own` ASKED:
   one holder's pause leaves the follow running; the last holder's pauses it; a guest's seeded
   pause counts for nothing.
3. BOTH SIDES OF THE OFFER: the follow's panel offers « Profil de qualité » and the account's
   own pause to a household member, and neither to a guest.
"""
import asyncio

from common import SETTLED, PANEL_IN, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

KYMA = "Kyma, l'onde mystérieuse"

FOLLOW = """async (title) => (await (await fetch('/api/acquisition/followed')).json()).find((one) => one.title === title)"""
AS = """async ([who, method, what, body]) => { window.__mocks.setIdentity(who);
  const address = '/api/acquisition/followed/' + encodeURIComponent(%r) + '/' + what;
  return (await fetch(address, { method, body: JSON.stringify(body) })).status; }""" % KYMA
OFFER = """() => ({ quality: !!document.querySelector('#sheet [data-profile]'),
                    pause: !!document.querySelector('#sheet [data-pause-own]') })"""


async def main():
    journal = Journal("R424 — quality and pause, per requester, role-gated")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        context, page = await open_page(browser)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("()=>window.__go('quality-own-offered')")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        offered = await page.evaluate(OFFER)
        journal.check("a household member's follow panel offers its own quality and pause",
                      offered["quality"] and offered["pause"], str(offered))
        follow = await page.evaluate(FOLLOW, KYMA)
        journal.check("R-L18-l: the floor in force ignores a requester whose role lacks the right",
                      follow.get("quality") == "1080p", f"in force {follow.get('quality')} (a guest seeded 2160p)")
        journal.check("R-L18-l-bis: one holder's pause leaves the follow running", follow.get("paused") is False,
                      str({key: follow.get(key) for key in ("ownPaused", "paused")}))

        raised = await page.evaluate(AS, ["household-member", "PUT", "quality", {"profile": "2160p"}])
        follow = await page.evaluate(FOLLOW, KYMA)
        journal.check("R-L18-l: setting one's own floor moves the floor in force",
                      raised == 200 and follow.get("quality") == "2160p", f"{raised} → {follow.get('quality')}")
        forced = await page.evaluate(AS, ["guest", "PUT", "quality", {"profile": "720p"}])
        journal.check("R-L18-l: a guest forcing a floor answers 403", forced == 403, str(forced))

        for who in ("guest-with-quality", "izno"):
            await page.evaluate(AS, [who, "PUT", "pause", {"paused": True}])
        follow = await page.evaluate(FOLLOW, KYMA)
        journal.check("R-L18-l-bis: once every holder asked, the follow is paused", follow.get("paused") is True,
                      str(follow.get("paused")))
        await page.evaluate(AS, ["household-member", "PUT", "pause", {"paused": False}])
        follow = await page.evaluate(FOLLOW, KYMA)
        journal.check("R-L18-l-bis: one holder lifting its pause runs it again", follow.get("paused") is False,
                      str(follow.get("paused")))
        forced = await page.evaluate(AS, ["guest", "PUT", "pause", {"paused": False}])
        journal.check("R-L18-l-bis: a guest forcing a pause answers 403", forced == 403, str(forced))

        await page.evaluate("()=>window.__go('quality-own-absent')")
        await page.wait_for_timeout(PANEL_IN + SETTLED)
        absent = await page.evaluate(OFFER)
        journal.check("a guest's follow panel offers neither", not absent["quality"] and not absent["pause"],
                      str(absent))

        journal.check("no JS error", not errors, str(errors))
        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

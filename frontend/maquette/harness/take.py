"""R123 — « Récupérer maintenant » really takes the medium.

THE VERB IS `data-take`, and NO RULE READ IT. `grep -ln 'data-take'
frontend/maquette/harness/*.py` returned nothing on 2026-09-04. It is EMITTED
by React — `features/releases/releases-screen.tsx` — and READ by the dying
engine's document delegation: a contract with two ends in two worlds and no
reader at all.

WHAT THAT COST, and it is B-309. The document has TWO branches for the
attribute. The release-choice screen's is checked first and carries no guard, so
it swallows the one the medium's own panel emits — where the value is a TITLE
and not an index:

    const release = releases()[Number(closest.dataset.take)];   // Number("The Hawk") → NaN
    toast(`« ${release.res} …`);                                // throws

The tap raises a TypeError, the panel closes, **and nothing is taken**. The
panel's own branch, further down, is unreachable.

THIS RULE WAS WRITTEN BEFORE THE VERB MOVED and was RED against the engine as it
stood — no mutation needed, which is the strongest form of « seen red first »
this repository asks for. L19's phase 13 moves the reader and it goes green.

WHAT IT READS, and each fails differently:

  1. THE MEDIUM LEAVES THE TAKEABLE SET AND JOINS WHAT IS IN FLIGHT. Not a
     toast: a message is a message, and it can be right about nothing.
  2. NO ERROR IS RAISED. B-309's own signature, and the reason a hold reading
     only the counts could have passed a build that threw on the way.
  3. THE RELEASE SCREEN'S OWN TAKE STILL WORKS. The two branches share an
     attribute, so a repair that fixed one by breaking the other would leave
     this rule green if it read only the panel's side.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, open_page

from playwright.async_api import async_playwright

QUEUE = """()=>({
  takeable: (window.__queue?.().takeable || []).map((one) => one.t),
  inFlight: (window.__queue?.().inFlight || []).map((one) => one.t)})"""


async def main():
    journal = Journal("R123 — « Récupérer maintenant » really takes the medium")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        # ── THE PANEL'S OWN TAKE ───────────────────────────────────────────
        await page.evaluate("()=>window.__go('acq-now-loaded')")
        await page.wait_for_timeout(500)
        before = await page.evaluate(QUEUE)
        journal.check(
            "the queue really holds something to be taken, so this walk has a "
            "subject",
            len(before["takeable"]) > 0, str(before["takeable"]))
        title = before["takeable"][0] if before["takeable"] else ""
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
        await page.wait_for_timeout(400)
        offered = await page.evaluate(
            """()=>{const a = document.querySelector('#sheetin [data-take]');
                    return a ? {take: a.dataset.take, text: a.textContent.trim()} : null;}""")
        journal.check(
            f"« {title} »'s own panel offers to take it",
            offered is not None and offered["take"] == title, str(offered))
        errors.clear()
        await page.click("#sheetin [data-take]")
        await page.wait_for_timeout(800)
        after = await page.evaluate(QUEUE)
        journal.check(
            "tapping it raises no error (B-309)",
            not errors, str(errors))
        journal.check(
            "the medium LEAVES what is waiting to be taken",
            title not in after["takeable"],
            f"{before['takeable']} → {after['takeable']}")
        journal.check(
            "and JOINS what is in flight — the state moved, not the message",
            title in after["inFlight"],
            f"{before['inFlight']} → {after['inFlight']}")

        # ── AND THE RELEASE SCREEN'S TAKE, which shares the attribute ──────
        # A repair that fixed one branch by breaking the other would leave a
        # rule reading only the panel's side perfectly green.
        await page.evaluate("()=>window.__go('screen-releases')")
        await page.wait_for_timeout(600)
        rows = await page.evaluate(
            "()=>document.querySelectorAll('[data-take]').length")
        journal.check(
            "the release screen really offers releases to take",
            rows > 0, f"{rows} row(s)")
        errors.clear()
        await page.evaluate(
            "()=>document.querySelector('[data-take]').click()")
        await page.wait_for_timeout(800)
        journal.check(
            "choosing a release raises no error either",
            not errors, str(errors))
        journal.check(
            "and it leaves the release screen",
            not await page.evaluate(
                """()=>!!document.querySelector('.screen.open[data-key^="releases:"]')"""))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())

"""R123 — « Récupérer maintenant » really takes the medium.

THE VERB IS `data-take`, and NO RULE READ IT. `grep -ln 'data-take'
frontend/maquette/harness/*.py` returned nothing. It is EMITTED
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
this repository asks for. It goes green once the reader moves into the feature.

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
from common import ACTED, Journal, PANEL_IN, PANEL_OUT, SETTLED, open_page

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
        await page.wait_for_timeout(SETTLED)
        before = await page.evaluate(QUEUE)
        journal.check(
            "the queue really holds something to be taken, so this walk has a "
            "subject",
            len(before["takeable"]) > 0, str(before["takeable"]))
        title = before["takeable"][0] if before["takeable"] else ""
        await page.evaluate("(t)=>window.__panel.produce('follow', t)", title)
        await page.wait_for_timeout(PANEL_IN)
        # SELECTED BY `data-part`, and the take READ from its dataset. A
        # selection on `[data-take]`'s PRESENCE would make the attribute a
        # boolean state in `check-markup-contracts`'s derived list — it is a
        # VALUE, an index or a title, and the release screen writes one on every
        # row by design.
        offered = await page.evaluate(
            """()=>{const a = [...document.querySelectorAll(
                      '#sheetin [data-part="sheet/action"]')]
                      .find((one) => 'take' in one.dataset);
                    return a ? {take: a.dataset.take, text: a.textContent.trim()} : null;}""")
        journal.check(
            f"« {title} »'s own panel offers to take it",
            offered is not None and offered["take"] == title, str(offered))
        errors.clear()
        await page.evaluate(
            """()=>{[...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
                     .find((one) => 'take' in one.dataset).click();}""")
        # ── B-249's SHAPE ON THIS PATH, read before anything settles ───────
        # The branch used to close the panel and `setTimeout(…, 260)` before
        # doing anything. It does not any more: the act lands inside the tap's
        # own commit. 120 ms is under half that wait, so a queue that has
        # already moved here is a queue that did not wait.
        await page.wait_for_timeout(120)
        early = await page.evaluate(QUEUE)
        journal.check(
            "the queue moves inside the tap's own commit, with no producer "
            "wait before it (B-249)",
            title not in early["takeable"],
            f"after 120 ms: {early['takeable']} — a 260 ms wait would still "
            f"show {before['takeable']}")
        await page.wait_for_timeout(ACTED)
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
        await page.wait_for_timeout(SETTLED)
        rows = await page.evaluate(
            """()=>[...document.querySelectorAll('[data-part="card/foot"]')]
                    .filter((one) => 'take' in one.dataset).length""")
        journal.check(
            "the release screen really offers releases to take",
            rows > 0, f"{rows} row(s)")
        errors.clear()
        await page.evaluate(
            """()=>{[...document.querySelectorAll('[data-part="card/foot"]')]
                     .find((one) => 'take' in one.dataset).click();}""")
        await page.wait_for_timeout(ACTED)
        journal.check(
            "choosing a release raises no error either",
            not errors, str(errors))
        journal.check(
            "and it leaves the release screen",
            # ANCHORED ON `data-part`, never on a class token: a class in a
            # rule selection dies the day the class is removed, and nothing can
            # then say whether the anchor or the style was at fault.
            not await page.evaluate(
                """()=>[...document.querySelectorAll('[data-part="screen"][data-open]')]
                        .some((one) => (one.dataset.key || '').startsWith('releases:'))"""))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())

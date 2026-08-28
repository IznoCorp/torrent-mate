"""R94 — coming back lands where one left, on a PAGE as well as on a screen.

B-140, reported by the operator on 2026-08-26: scroll a page, open an item, come
back — the page is at the top. The application feel is to return where one left.

THE MECHANISM WAS ALREADY CAREFUL, and that is what made the defect survive.
`app/scroll-restoration.ts` keys positions by the history entry, saves the
outgoing position inside the history subscription — the only instant it is still
in the DOM — restores over a bounded retry across frames, waits for late images,
and restores on a RETURN only. Every one of those decisions is right. It read
one port out of two.

`activePort()` was `.screen.open .port`: the viewport of an OVERLAY SCREEN. The
main pages scroll inside `#port`, which is never within one. So on a main page
the save either stored nothing or stored the just-opened screen's offset under
the departing page's key, and the return found nothing to restore.

THE RELAY IS WHAT MAKES IT HURT, which is why it is repaired in this lot rather
than left in the register: content arriving under a reader who then opens an
item and comes back lands them at the top of a list that has also changed
length.

WHAT IT HOLDS:

  the page      scroll a main page, open an item, go back — the offset is
                restored.
  the screen    the same for an overlay screen, so the repair is not proved by
                breaking the case that already worked. A rule that held only the
                new half would go green over a fix that traded one port for the
                other, which is precisely the defect it is repairing.
  forward       arriving FORWARD on an address one has seen before starts at the
                top. That is the mechanism's own decision — a new visit begins
                where a new visit begins — and a repair that restored it too
                would be a different defect wearing the same fix.

WHAT IT DOES NOT READ, said before what it does:

  - It does not read the retry budget, the image wait or the token
    invalidation. Those work; the defect was the selector, and a rule that
    re-asserted the parts that were right would report a pass about them every
    time the one broken part was fixed.
  - It does not read a real finger. A synthetic scroll is not a gesture, and
    gestures are L12's.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

# The page viewport and the open screen's, by their `data-*` anchors — the same
# pair `app/scroll-restoration.ts` resolves, so the rule and the code read one
# contract rather than two spellings of it.
PAGE_PORT = "#port"
SCREEN_PORT = '[data-part="screen"][data-open] [data-part="viewport"]'

# How far down to scroll before leaving. Far enough that landing at the top is
# unmistakable, close enough that any list of the library's length can reach it.
OFFSET = 300

# What « restored » means. The mechanism re-applies the offset over a bounded
# retry and the browser may clamp it by a pixel or two; a tolerance narrower
# than this would measure the clamp, and one wider would accept the top of a
# short page.
TOLERANCE = 12


async def walk(page, state, opener, port):
    """Scrolls, opens something, comes back, and reports the offset each time."""
    return await page.evaluate(
        """async ({ state, opener, port, offset }) => {
             const wait = (ms) => new Promise((r) => setTimeout(r, ms));
             window.__go(state);
             await window.__mocks.quiet();
             await wait(400);
             const scroller = document.querySelector(port);
             if (!scroller) return { reached: null, why: `no element at ${port}` };
             scroller.scrollTop = Math.min(
               offset, scroller.scrollHeight - scroller.clientHeight);
             await wait(200);
             const left = scroller.scrollTop;
             if (left < 20) return { reached: null, why: `page too short: ${left}` };

             const control = document.querySelector(opener);
             if (!control) return { reached: null, why: `nothing to open at ${opener}` };
             control.click();
             await window.__mocks.quiet();
             await wait(500);

             window.__bridge.back();
             await window.__mocks.quiet();
             await wait(800);
             const back = document.querySelector(port);
             return { left, reached: back ? back.scrollTop : null, why: "" };
           }""",
        {"state": state, "opener": opener, "port": port, "offset": OFFSET})


async def hold(journal):
    """Walks a page and a screen, out and back."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser, **PHONE)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.evaluate("()=>window.__loadingDone?.()")

        # THE PAGE. The library's grid is the longest surface the prototype has,
        # and a poster opens the media sheet — which is the journey the operator
        # described.
        walked = await walk(page, "lib-grid", '[data-part="tile"]', PAGE_PORT)
        journal.check(
            "a main page can be scrolled and something opened from it",
            walked["reached"] is not None,
            walked["why"])
        if walked["reached"] is not None:
            journal.check(
                "coming back to a PAGE lands where one left it",
                abs(walked["reached"] - walked["left"]) <= TOLERANCE,
                f"left at {walked['left']}, came back to {walked['reached']} — "
                "the port a main page scrolls in is `#port`, and it is never "
                "inside a `.screen.open` (B-140)")

        # THE SCREEN, so the repair is not proved by breaking what worked.
        on_screen = await page.evaluate(
            """async ({ port, offset }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__go("mediasheet-series");
                 await window.__mocks.quiet();
                 await wait(500);
                 const scroller = document.querySelector(port);
                 if (!scroller) return { reached: null, why: `no element at ${port}` };
                 scroller.scrollTop = Math.min(
                   offset, scroller.scrollHeight - scroller.clientHeight);
                 await wait(200);
                 const left = scroller.scrollTop;
                 if (left < 20) return { reached: null, why: `screen too short: ${left}` };
                 window.__screens.releases("Test");
                 await window.__mocks.quiet();
                 await wait(500);
                 window.__bridge.back();
                 await window.__mocks.quiet();
                 await wait(800);
                 const back = document.querySelector(port);
                 return { left, reached: back ? back.scrollTop : null, why: "" };
               }""",
            {"port": SCREEN_PORT, "offset": OFFSET})
        journal.check(
            "an overlay screen can be scrolled and something opened from it",
            on_screen["reached"] is not None,
            on_screen["why"])
        if on_screen["reached"] is not None:
            journal.check(
                "coming back to a SCREEN still lands where one left it",
                abs(on_screen["reached"] - on_screen["left"]) <= TOLERANCE,
                f"left at {on_screen['left']}, came back to "
                f"{on_screen['reached']} — this half worked before B-140's "
                "repair, and a repair that traded one port for the other would "
                "pass every hold above and fail here")

        # FORWARD IS A NEW VISIT. The mechanism restores on a RETURN only, and
        # that is a decision rather than an omission.
        forward = await page.evaluate(
            """async ({ port, offset }) => {
                 const wait = (ms) => new Promise((r) => setTimeout(r, ms));
                 window.__go("lib-grid");
                 await window.__mocks.quiet();
                 await wait(400);
                 const scroller = document.querySelector(port);
                 scroller.scrollTop = Math.min(
                   offset, scroller.scrollHeight - scroller.clientHeight);
                 await wait(200);
                 document.querySelector('[data-part="tile"]').click();
                 await window.__mocks.quiet();
                 await wait(500);
                 window.__bridge.back();
                 await wait(700);
                 history.forward();
                 await wait(700);
                 window.__bridge.back();
                 await wait(800);
                 const back = document.querySelector(port);
                 return back ? back.scrollTop : null;
               }""",
            {"port": PAGE_PORT, "offset": OFFSET})
        journal.check(
            "a walk out and back twice still lands where one left",
            forward is not None and abs(forward - OFFSET) <= 60,
            f"came back to {forward} after going forward and back again")

        await context.close()
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal("R94 — coming back lands where one left, page as well as screen")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()

"""The prototype's own controls never sit on top of the app's.

R51 — the harness bar overlaps none of the app's FIXED controls, in any named
      state, at any width.

The bar is not part of the product: it switches the design notes, the data
scenario and the theme, and `window.__measure(true)` clears it before any
capture. But it is on screen the whole time an operator is reading the
prototype, and while it sat top-right it covered the avatar button — at EVERY
width, including the one the desktop offset was written to protect.

That offset is the lesson. It read `calc(50% - 250px)`, a number computed
against a frame half-width that was never 250px, so it moved the bar to a
place no one had measured. Anchoring the bar to the frame instead of to the
window removes the arithmetic altogether, and this rule keeps the corner it
was moved to honest: the header spans the top, the tab bar spans the bottom,
the floating action button is bottom-right, and nothing claims bottom-left.
"""
import asyncio
import sys

from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8899/wrapped.html"

# Both sides of the 520px breakpoint: below it the frame fills the window,
# above it the frame is centred and the bar has to follow it.
WIDTHS = [390, 1280]

# The app's FIXED chrome — the controls that are in the same place whatever is
# on screen. The rule stops there on purpose. A floating overlay on a phone
# always covers something, and a control in the scrolling content can be moved
# out from under it with one swipe; the avatar cannot. Widening this list to
# every tappable element would forbid a harness bar at all, which is a rule
# nobody could satisfy rather than a rule that catches anything.
CONTROLS = ".avatar, .topbar button, .bottombar button, #fab, .fab"


async def main():
    """Runs R51 and reports how many state/width pairs it actually measured.

    Returns:
        0 when the bar is clear everywhere, 1 otherwise.
    """
    failures = []
    executed = 0
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")
        for width in WIDTHS:
            ctx = await b.new_context(
                viewport={"width": width, "height": 844},
                device_scale_factor=2,
                is_mobile=width < 520,
                has_touch=width < 520,
            )
            pg = await ctx.new_page()
            await pg.goto(URL, wait_until="load")
            await pg.evaluate("()=>document.querySelector('#toastx').click()")
            states = await pg.evaluate("()=>window.__states()")
            for state_ in states:
                await pg.evaluate("(i)=>window.__go(i)", state_)
                await pg.wait_for_timeout(300)
                hits = await pg.evaluate(
                    """(sel)=>{
                      const bar=document.querySelector('.hbtn');
                      if(!bar) return ['ABSENT'];
                      const a=bar.getBoundingClientRect();
                      if(!a.width) return [];
                      const crosses=(b)=>!(a.right<=b.left||b.right<=a.left||
                                          a.bottom<=b.top||b.bottom<=a.top);
                      return [...document.querySelectorAll(sel)]
                        .filter(el=>el.getClientRects().length>0)
                        .filter(el=>crosses(el.getBoundingClientRect()))
                        .map(el=>el.className||el.id||el.tagName);}""",
                    CONTROLS,
                )
                executed += 1
                if hits:
                    failures.append(
                        f"R51 {state_} @{width}px: the harness bar covers {hits}"
                    )
            await ctx.close()
        await b.close()

    for line in failures:
        print(f"  FAIL {line}")
    print(f"\n{executed} state/width pairs EXECUTED · {len(failures)} failures")
    print(
        "VERDICT:",
        "the harness bar covers no app control"
        if not failures
        else "the harness bar sits on top of the product",
    )
    return 1 if failures else 0


sys.exit(asyncio.run(main()))

"""The prototype's own controls never sit on top of the app's.

R51 — no piece of the harness's chrome overlaps the app's FIXED controls, in
      any named state, at any width.

THE SUBJECT IS THE CLASS, read by its prefix (B-388): every element whose
`data-part` begins `harness/` and that no other such element contains — the bar
and the desktop switch today. It read the bar alone by its literal, so a second
piece of chrome was outside a rule whose first line promises it, and a third
would have been held by nothing. A floor keeps the reading from going vacuous
the day one is renamed.

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

from common import browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

URL = "http://127.0.0.1:8899/"

# Both sides of the 520px breakpoint: below it the frame fills the window,
# above it the frame is centred and the bar has to follow it.
WIDTHS = [390, 1280]

# The app's FIXED chrome — the controls that are in the same place whatever is
# on screen. The rule stops there on purpose. A floating overlay on a phone
# always covers something, and a control in the scrolling content can be moved
# out from under it with one swipe; the avatar cannot. Widening this list to
# every tappable element would forbid a harness bar at all, which is a rule
# nobody could satisfy rather than a rule that catches anything.
CONTROLS = '[data-part="avatar"], [data-part="shell/header"] button, [data-part="shell/tab-bar"] button, #fab, [data-part="shell/add-action"]'

# How many pieces of harness chrome the document holds today: the bar and the
# desktop switch. Fewer means a piece was renamed out of the prefix.
CHROME_FLOOR = 2


async def main():
    """Runs R51 and reports how many state/width pairs it actually measured.

    Returns:
        0 when the bar is clear everywhere, 1 otherwise.
    """
    failures = []
    executed = 0
    async with async_playwright() as p:
        b = await p.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
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
                      const pieces=[...document.querySelectorAll('[data-part^="harness/"]')]
                        .filter(el=>!el.parentElement.closest('[data-part^="harness/"]'));
                      const controls=[...document.querySelectorAll(sel)]
                        .filter(el=>el.getClientRects().length>0);
                      const hits=[];
                      for(const piece of pieces){
                        const a=piece.getBoundingClientRect();
                        if(!a.width) continue;
                        const crosses=(b)=>!(a.right<=b.left||b.right<=a.left||
                                            a.bottom<=b.top||b.bottom<=a.top);
                        for(const el of controls){
                          if(crosses(el.getBoundingClientRect()))
                            hits.push(piece.dataset.part+' over '+
                                      (el.getAttribute('class')||el.id||el.tagName));
                        }
                      }
                      return {pieces: pieces.length, hits};}""",
                    CONTROLS,
                )
                executed += 1
                if hits["pieces"] < CHROME_FLOOR:
                    failures.append(
                        f"R51 {state_} @{width}px: {hits['pieces']} piece(s) of harness chrome "
                        f"found, the floor is {CHROME_FLOOR} — one left the `harness/` prefix"
                    )
                if hits["hits"]:
                    failures.append(
                        f"R51 {state_} @{width}px: the harness's chrome covers {hits['hits']}"
                    )
            await ctx.close()
        await b.close()

    for line in failures:
        print(f"  FAIL {line}")
    print(f"\n{executed} state/width pairs EXECUTED · {len(failures)} failures")
    print(
        "VERDICT:",
        "the harness's chrome covers no app control"
        if not failures
        else "the harness bar sits on top of the product",
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

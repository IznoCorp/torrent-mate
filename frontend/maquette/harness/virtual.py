"""R117 — the long list is windowed, and it stays right while it scrolls (P24).

The library holds 1 861 titles. Un-windowed, scrolling to the end leaves 1 861
nodes in the document, and every one of them is a poster the browser must lay
out on any reflow.

TWO HOLDS, AND THE SECOND IS THE ONE THAT BITES. A rule that only counted nodes
on the cold load would be green over a virtualiser that renders correctly at
rest and tears the moment a thumb moves it — which is the failure mode of every
windowing bug worth having. So the list is scrolled with a REAL touch stream and
read again: different rows must be rendered, and they must be the rows that
belong at that offset.

WHY THE COUNT IS READ AGAINST A DECLARED TOTAL rather than against a number
written here. `ui/virtual-rows.tsx` publishes `data-virtualised` carrying how
many rows exist, so the hold compares what is RENDERED against what the surface
says it HAS. A floor typed into this file would be a second source of truth that
drifts the day the fixture changes — B-272's species, and this repository has
already paid for it once this wave.

WHAT IT DOES NOT READ: the rendering. That the windowed list looks exactly like
the un-windowed one is the ORACLE's answer, and it gave it — the spacer design
exists precisely so the end state does not move, and 2 958 measurements agree.
This rule holds the node count and the scroll correctness, which the oracle
cannot see because it measures one settled state at a time.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal

# The list mode: one lane, so the window is small enough that a difference in
# node count is unambiguous. The gallery's three lanes fit its whole fixture in
# one viewport, which would make the count hold vacuous — and a hold that cannot
# fail is worth nothing.
STATE = "lib-list"
ROW = '[data-part="card"]'

# How far the finger drags the list, in pixels. Several rows' worth, so the
# window has certainly moved.
SCROLL_DISTANCE = 900

# One row plus its gap. The two margins are compared against it rather than
# against a fixed pixel count: what makes a shift a DEFECT is that it costs a
# whole row of safety, and the row's height is the list's own number.
ONE_LINE = 134


async def rendered(page):
    """What is on screen, and what the surface says it has.

    Args:
        page: The Playwright page.

    Returns:
        A dict of the rendered node count, the declared total, and the first
        row's text — which is what says WHICH window is showing.
    """
    return await page.evaluate("""(row)=>{
      const items = [...document.querySelectorAll(row)];
      const container = document.querySelector('#libitems');
      return {
        rendered: items.length,
        declared: Number(container && container.dataset.virtualised) || 0,
        first: items.length ? (items[0].textContent || '').trim().slice(0, 40) : '',
      };
    }""", ROW)


async def hold(journal):
    """Counts the window, then scrolls it with a real finger and counts again."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        context = await browser.new_context(**PHONE)
        page = await context.new_page()
        await page.goto(PROTOTYPE, wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        await page.evaluate("()=>document.querySelector('#toastx')?.click()")
        await page.wait_for_timeout(250)
        await page.evaluate("(s)=>window.__go(s)", STATE)
        await page.wait_for_timeout(700)

        first = await rendered(page)

        # THE CONTROL. With too few rows the window would hold every one of them
        # and the hold below would pass over a list that is not windowed at all.
        journal.check(
            "the fixture is long enough for a window to mean anything",
            first["declared"] >= 12,
            f"{first['declared']} row(s) declared — with fewer, « rendered < "
            "declared » proves nothing")

        journal.check(
            "the list renders FEWER nodes than it has rows",
            first["rendered"] < first["declared"],
            f"{first['rendered']} node(s) for {first['declared']} row(s) — the "
            "list is not windowed, so 1 861 titles are 1 861 nodes")

        # ── and it stays right while it moves ──────────────────────────────
        session = await page.context.new_cdp_session(page)
        box = await page.evaluate(
            "()=>{const r=document.querySelector('#port').getBoundingClientRect();"
            "return {x:r.x+r.width/2, y:r.y+r.height*0.7};}")
        # A REAL touch stream, not `scrollTop = n`: a virtualiser subscribes
        # to scroll events, and a programmatic jump can land it in a state a
        # finger never produces.
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": box["x"], "y": box["y"], "id": 1}]})
        for step in range(1, 13):
            await session.send("Input.dispatchTouchEvent", {
                "type": "touchMove",
                "touchPoints": [{"x": box["x"],
                                 "y": box["y"] - SCROLL_DISTANCE * step / 12,
                                 "id": 1}]})
            await page.wait_for_timeout(16)
        await session.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})
        await page.wait_for_timeout(500)

        second = await rendered(page)
        journal.check(
            "the scroll actually moved the list",
            await page.evaluate("()=>document.querySelector('#port').scrollTop") > 0,
            "the scrollport did not move — the hold below would compare a "
            "window against itself")
        journal.check(
            "and the window MOVED with it — different rows are rendered",
            second["first"] != first["first"] and second["first"] != "",
            f"the first rendered row is still « {second['first']} » — the "
            "window renders correctly at rest and does not follow the finger")
        # THE WINDOW IS CENTRED ON THE VIEWPORT, and this is what catches a
        # virtualiser told the wrong origin.
        #
        # `#libitems` does not start at the top of `#port` — the filters and
        # the tabs are above it in the same scrollport, 179px of them. A
        # virtualiser that assumes the list begins at the scroller's origin
        # computes every offset short by that distance and renders a window
        # SHIFTED down the list: measured before the fix, 485px of margin
        # above the viewport and 742 below, where the overscan asks for the
        # same on each side.
        #
        # The visible rows were still covered, which is why nothing else
        # caught it — the oracle measures at rest at scrollTop 0, where the
        # shift is zero by construction. What was lost is two thirds of the
        # safety margin ABOVE, and it is the top a scroll-up eats first.
        margins = await page.evaluate(
            "(row)=>{"
            "const port = document.querySelector('#port');"
            "const rows = [...port.querySelectorAll(row)];"
            "if (rows.length < 2) return null;"
            "const box = port.getBoundingClientRect();"
            "return {above: box.top - rows[0].getBoundingClientRect().top,"
            "        below: rows[rows.length - 1].getBoundingClientRect().bottom - box.bottom};}",
            ROW)
        journal.check(
            "the window is CENTRED on the viewport, not shifted down the list",
            margins is not None
            and abs(margins["above"] - margins["below"]) < ONE_LINE,
            f"{margins} — a difference of more than one row means the "
            "virtualiser was told the wrong origin, and the smaller side is "
            "margin the reader loses on a fast scroll")

        journal.check(
            "and it is still a window, not the whole list",
            second["rendered"] < second["declared"],
            f"{second['rendered']} node(s) for {second['declared']} row(s) "
            "after scrolling — the window grew into the full list")

        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal("R117 — the long list is windowed, and stays right while it scrolls")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()

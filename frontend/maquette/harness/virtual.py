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

# MEASURED FROM THE RENDERED LIST, never re-typed. What makes a shift a DEFECT
# is that it costs a whole row of safety, so the comparison is against a row's
# real height — and a row's height is declared in
# `features/library/reference.ts`, which would make a number typed here a second
# source of truth that goes stale the day the card is redrawn (B-276).


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




# ── THE WINDOW FOLLOWS THE CONTAINER QUERY ──────────────────────────────────
# `.gallery` is `repeat(3)` below 460px of PORT and becomes 4, then 5 at 620 and
# 6 at 820. Nothing caps the port to a phone's width in production: the only
# 390px frame is `styles/harness.css`, which ships nowhere.
#
# The lane count was a PROP typed 3. At five columns the virtualiser believed in
# 621 lines where the grid draws 373, sized its spacers for three per line, and
# put the wrong rows under the finger.
#
# HELD AT A WIDTH WHERE IT DIFFERS FROM THREE, which is the only width that can
# fail: every earlier rule ran at 390 and the oracle measures there, so a
# container query was a designed state with no reader at any other width.
#
# The frame is widened for the reading because the harness pins `#device` to a
# phone — that pin is the instrument, not the product.
WIDE_PORT = 700
WIDEN = ("#device{width:%dpx !important;max-width:none !important;}"
         "#port{width:auto !important;}" % (WIDE_PORT - 10))


async def hold_the_lanes_are_measured(journal, browser):
    """Opens the gallery wide enough to change its column count, and reads both."""
    context = await browser.new_context(
        **{**PHONE, "viewport": {"width": WIDE_PORT, "height": 844}})
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)
    await page.add_style_tag(content=WIDEN)
    await page.evaluate("()=>window.__go('lib-grid')")
    await page.wait_for_timeout(900)

    reading = await page.evaluate("""()=>{
      const box = document.querySelector('#libitems');
      const style = getComputedStyle(box);
      const tracks = style.gridTemplateColumns;
      return {
        columns: tracks && tracks !== 'none' ? tracks.split(/\\s+/).length : 1,
        lanes: Number(box.dataset.lanes) || 0,
      };
    }""")

    # THE CONTROL: without a width that actually changes the grid, the hold
    # below compares three against three and proves nothing.
    journal.check(
        f"at {WIDE_PORT}px the gallery draws MORE than three columns",
        reading["columns"] > 3,
        f"{reading['columns']} column(s) — the container query did not fire, so "
        "the hold below is the 390px case wearing another width")
    journal.check(
        "and the window's lane count is the grid's, not a typed three",
        reading["lanes"] == reading["columns"],
        f"the grid draws {reading['columns']} columns and the window windows "
        f"{reading['lanes']} — it believes in the wrong number of lines, sizes "
        "its spacers for the wrong row, and puts the wrong rows under the finger")
    await context.close()


async def hold(journal):
    """Counts the window, then scrolls it with a real finger and counts again."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_lanes_are_measured(journal, browser)
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
        one_line = await page.evaluate(
            "(row)=>{const first=document.querySelector(row);"
            " if(!first) return 0;"
            " const box=first.getBoundingClientRect();"
            " const parent=getComputedStyle(first.parentElement);"
            " return box.height + (parseFloat(parent.rowGap || parent.gap) || 0);}",
            ROW)
        journal.check(
            "a row's height is measured, not typed into this rule",
            one_line > 20,
            f"read {one_line} — the comparison below would need a number typed "
            "here, which is the second source of truth B-276 names")
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
            and abs(margins["above"] - margins["below"]) < one_line,
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

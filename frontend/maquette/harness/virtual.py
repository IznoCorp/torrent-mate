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

    # AND THE GEOMETRY AGREES, which the two numbers above cannot say between
    # them: `data-lanes` is a number the window PUBLISHES and the comparison
    # above re-derives the same computed style, so a window that publishes the
    # measured columns and still sizes its lines from a typed three passes both.
    # What only the spacers can produce is the container's total height.
    geometry = await page.evaluate(r"""()=>{
      const box = document.querySelector('#libitems');
      const tile = box.querySelector('[data-part="tile"]');
      const style = getComputedStyle(box);
      return {
        height: box.getBoundingClientRect().height,
        rows: Number(box.dataset.virtualised) || 0,
        columns: (style.gridTemplateColumns || '').split(/\s+/).length,
        line: tile ? tile.getBoundingClientRect().height : 0,
        gap: parseFloat(style.rowGap || style.gap) || 0,
      };
    }""")
    lines = -(-geometry["rows"] // max(geometry["columns"], 1))
    expected = lines * (geometry["line"] + geometry["gap"]) - geometry["gap"]
    journal.check(
        "and the window is as TALL as those lanes make it",
        geometry["line"] > 0 and geometry["rows"] > 4
        and abs(geometry["height"] - expected) < max(2 * geometry["line"], 40),
        f"read {geometry} — {geometry['rows']} row(s) over "
        f"{geometry['columns']} lane(s) is {lines} line(s), which stand "
        f"{expected:.0f}px tall, and the window measures "
        f"{geometry['height']:.0f}px. The spacers are sized for a different "
        "number of lines than the grid draws, whatever the attribute says")
    await context.close()




# ── NODES THAT STAY IN THE WINDOW ARE THE SAME NODES ────────────────────────
# The window used to be one `dangerouslySetInnerHTML` string, re-applied
# whenever the range moved — every row crossing, so about every 134px of list.
# That destroyed and recreated every visible node, and three things went with
# them: a row opened by a swipe was replaced by a closed one mid-gesture and the
# dying engine kept the detached node as its `openCard`; `:active` and
# `data-pressing` vanished from a tile under the finger; and every `<img>` in
# the window was re-created and re-decoded, about forty per crossing, in the lot
# whose subject is the PERFORMANCE FLOOR.
#
# The rules that existed could not see it: R117 measured geometry at rest, and
# geometry is exactly what a faithful re-render preserves.
#
# WHAT THIS HOLDS is identity — a mark written onto a live row survives a scroll
# that keeps that row in the window. A mark is used rather than the node itself
# because a node reference cannot cross the page boundary; an attribute written
# by hand is the same node's, or it is gone.
IDENTITY_MARK = "data-identity-probe"


async def hold_rows_keep_their_identity(journal, browser):
    """Marks a live row, scrolls a little, and asks whether the mark survived."""
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)
    await page.evaluate("(s)=>window.__go(s)", STATE)
    await page.wait_for_timeout(700)

    marked = await page.evaluate("""(row)=>{
      const rows = [...document.querySelectorAll(row)];
      if (rows.length < 4) return null;
      // A row in the MIDDLE of the window, so a small scroll keeps it in range.
      const target = rows[Math.floor(rows.length / 2)];
      target.setAttribute('data-identity-probe', 'kept');
      return {index: Math.floor(rows.length / 2), total: rows.length,
              text: (target.textContent || '').trim().slice(0, 30)};
    }""", ROW)
    journal.check(
        "a live row can be marked, so identity has something to carry",
        marked is not None,
        f"read {marked} — with too few rows drawn the scroll below cannot keep "
        "one in the window")
    if not marked:
        await context.close()
        return
    before_edges = await page.evaluate(
        "(row)=>{const drawn=[...document.querySelectorAll(row)];"
        " return drawn.length ? [drawn[0].textContent.trim().slice(0, 40),"
        "   drawn[drawn.length - 1].textContent.trim().slice(0, 40)] : ['', ''];}",
        ROW)

    # A SMALL scroll: far enough to move the window's edges, near enough that
    # the marked row is still inside it. A scroll that evicted the row would
    # make the hold pass for the wrong reason, so the row's presence is checked
    # too.
    session = await page.context.new_cdp_session(page)
    box = await page.evaluate(
        "()=>{const r=document.querySelector('#port').getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height*0.7};}")
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": box["x"], "y": box["y"], "id": 1}]})
    for step in range(1, 9):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": box["x"], "y": box["y"] - 420 * step / 8, "id": 1}]})
        await page.wait_for_timeout(16)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(600)

    after = await page.evaluate("""(row)=>{
      const still = document.querySelector('[data-identity-probe="kept"]');
      const drawn = [...document.querySelectorAll(row)];
      return {survived: !!(still && still.isConnected),
              drawn: drawn.length,
              // WHICH ROWS ARE DRAWN, not how far the port scrolled. A window
              // that never re-ranged keeps every node too, so identity would
              // pass for the wrong reason — and whether 200px crosses a line
              // depends on the row height and the scroll margin.
              edges: drawn.length
                ? [drawn[0].textContent.trim().slice(0, 40),
                   drawn[drawn.length - 1].textContent.trim().slice(0, 40)]
                : ['', ''],
              scrolled: document.querySelector('#port').scrollTop};
    }""", ROW)

    journal.check(
        "the scroll actually moved the window's RANGE",
        after["scrolled"] > 0 and after["edges"] != before_edges,
        f"scrollTop {after['scrolled']} and the window still draws "
        f"{after['edges']!r} — its RANGE never moved, so nothing was asked of "
        "identity: a window that never re-ranges keeps every node too")
    journal.check(
        "and a row still in the window is the SAME node it was",
        after["survived"],
        f"read {after} — the marked row was rebuilt: the window rewrote itself "
        "rather than moving at its edges, which takes an open swipe, a pressed "
        "state and every decoded image with it")
    await context.close()


async def hold_the_gallery_keeps_its_ORDER(journal, browser):
    """Scrolls the gallery down and back UP, and reads the order it draws.

    THE DEFECT THIS EXISTS FOR, and no rule could see it. The window inserts
    each new row before the row that FOLLOWS it, which is right; it walked its
    range UPWARDS, which meant the follower of a new row was itself new and not
    yet in the tree, so those rows fell through to « append before the tail
    spacer » and landed at the END of the window. The grid's auto-placement
    follows DOM order, so scrolling UP by one line in a three-lane gallery drew
    two rows at the bottom of the window and the top line read « 8 9 10 ».

    Every rule drove the LIST, which is immune by arithmetic — one lane means
    the last new index always has a live follower — and every one of them
    scrolled DOWN, where the new rows are at the end anyway. Two blind spots
    that had to coincide, and they did.

    Args:
        journal: The rule's journal.
        browser: A launched Playwright browser.
    """
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)
    await page.evaluate("()=>window.__go('lib-grid')")
    await page.wait_for_timeout(900)

    read_order = """()=>[...document.querySelectorAll(
      '#libitems > [data-part=\"tile\"]')].map(
        (tile) => Number(tile.dataset.tile))"""

    session = await page.context.new_cdp_session(page)
    box = await page.evaluate(
        "()=>{const r=document.querySelector('#port').getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height*0.6};}")

    async def drag(distance):
        """Drags the scrollport by `distance`, positive meaning DOWNWARD."""
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": box["x"], "y": box["y"], "id": 1}]})
        for step in range(1, 13):
            await session.send("Input.dispatchTouchEvent", {
                "type": "touchMove",
                "touchPoints": [{"x": box["x"],
                                 "y": box["y"] - distance * step / 12, "id": 1}]})
            await page.wait_for_timeout(16)
        await session.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})
        await page.wait_for_timeout(500)

    def first_out_of_order(series):
        """The index of the first row that is smaller than the one before it.

        Args:
            series: The `data-tile` numbers in DOM order.

        Returns:
            The position of the first break, or -1.
        """
        for position in range(1, len(series)):
            if series[position] < series[position - 1]:
                return position
        return -1

    lanes = await page.evaluate(
        "()=>Number(document.querySelector('#libitems').dataset.lanes) || 0")
    journal.check(
        "the gallery draws in LANES, or this hold measures the list again",
        lanes >= 2,
        f"{lanes} lane(s) — the defect is a multi-lane one, and one lane is "
        "immune to it by arithmetic")

    # DEEP INTO THE LIST FIRST, so that scrolling back up has rows to re-insert
    # ABOVE the ones already live. The port is taken there by assignment rather
    # than by a finger, and that is deliberate: a real finger is what the hold
    # MEASURES, and it is spent on the upward gesture where the defect lives —
    # a thousand pixels of dragging to reach the same place proves nothing extra
    # and takes twenty seconds. Paging is given time to answer, because the
    # window can only re-range over rows that exist.
    await page.evaluate("()=>{document.querySelector('#port').scrollTop = 3000;}")
    await page.wait_for_timeout(900)
    await drag(400)
    down = await page.evaluate(read_order)
    journal.check(
        "scrolled DOWN, the window draws its rows in order",
        down == sorted(down) and len(down) > 4,
        f"the window drew {down} — the first break is at position "
        f"{first_out_of_order(down)}")

    # AND BACK UP, which is where the order was lost.
    await drag(-500)
    up = await page.evaluate(read_order)
    journal.check(
        "and scrolled back UP, it still draws them in order",
        up == sorted(up) and len(up) > 4,
        f"the window drew {up} — the first break is at position "
        f"{first_out_of_order(up)}. Rows re-inserted at the top of the range "
        "were appended at its END, so the grid lays them out last and the "
        "reader's first line is not the first line")
    journal.check(
        "and the two readings are not the same window",
        down[:1] != up[:1],
        f"the window began at {down[:1]} both times — it never re-ranged "
        "upwards, so the hold above measured the downward case twice")
    await context.close()


async def hold(journal):
    """Counts the window, then scrolls it with a real finger and counts again."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_lanes_are_measured(journal, browser)
        await hold_rows_keep_their_identity(journal, browser)
        await hold_the_gallery_keeps_its_ORDER(journal, browser)
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

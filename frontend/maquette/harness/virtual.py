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
import re
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
# One page of the listing, as the layer serves it, and one row's pitch — the
# card's height plus the gap the container puts between two. Both are read from
# the sources they are declared in rather than typed here twice: a number in
# this file that the fixture moves is a second source of truth.
def declared(pattern, *where):
    """Reads a number declared in a TypeScript source, or says which one moved.

    THE READ IS A REGEX BECAUSE PYTHON CANNOT IMPORT TYPESCRIPT, and the price of
    that is a match which can stop matching. Unwrapped it stopped as
    `AttributeError: 'NoneType' has no attribute 'group'` at import time — loud,
    but naming neither the file nor the declaration, so the reader's first guess
    is that the rule is broken rather than that a constant was reformatted.

    Args:
        pattern: The expression, with every number to read as a group.
        *where: The path of the source, from `frontend/maquette`.

    Returns:
        The sum of the groups, as integers.

    Raises:
        AssertionError: If the declaration is no longer where it was.
    """
    source = pathlib.Path(__file__).resolve().parent.parent.joinpath(*where)
    found = re.search(pattern, source.read_text(encoding="utf-8"), re.S)
    assert found, (
        f"the declaration matching {pattern!r} is no longer in "
        f"{source.name} — this rule reads it there rather than typing the "
        f"number twice, so it has to be pointed at wherever it moved")
    return sum(int(number) for number in found.groups())


PAGE_SIZE = declared(r"PAGE_SIZE = (\d+)",
                     "design", "src", "mocks", "handlers", "library.ts")
ROW_PITCH = declared(r"list: \{[^}]*rowHeight: (\d+)[^}]*gap: (\d+)",
                     "design", "src", "features", "library", "reference.ts")

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
      '#libitems > [data-part="tile"]')].map(
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


async def hold_a_deleted_row_leaves_the_screen(journal, browser):
    """A row deleted beyond the first page leaves the window in the same task.

    THE REGRESSION THIS EXISTS FOR. The window redrew only on a KEY, and the key
    named the first page's identity — but the cache's structural sharing returns
    an unchanged page as the SAME object, so deleting a row on any page but the
    first left the key still, the window untouched, and the row the reader had
    just deleted on screen until the network answered. On a mutation the layer
    HOLDS — no invalidation by design — it never left at all.

    It is driven through `__deleteLibraryItems`, the seam the engine's own
    delete calls, rather than through the swipe: what is measured here is the
    window's redraw, and the gesture that reaches it is `drag.py`'s subject.

    WHY BEYOND THE FIRST PAGE, and it is the whole finding: deleting a row on
    page 0 changes that page's identity and the old key moved with it. Only a
    row further down separates « the rows changed » from « the first page
    changed », and 321 of the fixture's 345 rows are further down. **So the
    index is HELD, not hoped for**: the first version of this hold asked for one
    more page through a door that does not exist, reached page 1 only by the
    fling three touch strokes happen to produce, and checked `scrollTop > 0` —
    which is not « beyond the first page » on any machine.

    AND IT IS READ ONE TASK AFTER THE DELETE, WITH THE NETWORK DOWN. The first
    version read 150 ms later against a layer answering instantly: the refetch
    the delete triggers had already rebuilt the window by then, so the hold was
    green on the very code it was written against. Offline, the mutation is HELD
    and no refetch exists to repair anything — which is also the case the
    docstring above names and did not drive.
    """
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)
    await page.evaluate("(s)=>window.__go(s)", STATE)
    await page.wait_for_timeout(700)
    # ONE PAGE MORE, so the window can hold a row the first page does not — and
    # the door is asserted to EXIST, because a name that has moved leaves
    # `undefined && …` behind, which is a no-op that reads exactly like a call.
    door = await page.evaluate(
        "()=>typeof window.__libraryNextPage === 'function'")
    journal.check(
        "the list publishes the door this hold asks a page through",
        door, f"typeof window.__libraryNextPage === 'function': {door}")
    await page.evaluate("()=>window.__libraryNextPage && window.__libraryNextPage()")
    await page.wait_for_timeout(700)
    declared = await page.evaluate(
        """()=>Number((document.querySelector('#libitems') || {dataset: {}})
             .dataset.virtualised || 0)""")
    journal.check(
        "and a second page landed, so a row beyond the first exists to delete",
        declared > PAGE_SIZE, f"{declared} row(s) declared, one page is {PAGE_SIZE}")
    session = await page.context.new_cdp_session(page)
    box = await page.evaluate(
        "()=>{const r=document.querySelector('#port').getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height*0.7};}")
    # SCROLLED UNTIL THE WINDOW IS PAST THE FIRST PAGE, with a real touch stream
    # and a bounded loop — not a fixed number of strokes whose reach depends on
    # how far this browser's fling carries. Three strokes put the window at index
    # 19 on this machine, under the 24 the hold is about; a count that happens to
    # work here is the precondition failing silently somewhere else.
    reached = 0
    for _ in range(12):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchStart",
            "touchPoints": [{"x": box["x"], "y": box["y"]}]})
        for step in range(1, 9):
            await session.send("Input.dispatchTouchEvent", {
                "type": "touchMove",
                "touchPoints": [{"x": box["x"], "y": box["y"] - step * 45}]})
        await session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        await page.wait_for_timeout(150)
        reached = await page.evaluate(
            "(pitch)=>Math.round(document.querySelector('#port').scrollTop / pitch)",
            ROW_PITCH)
        if reached >= PAGE_SIZE + 6:
            break
    await page.wait_for_timeout(400)

    # THE MEASURED ROW'S INDEX, derived from the window's own leading spacer
    # rather than from the scroll: the spacer stands in for every row above the
    # window, so its height over one row's pitch IS the first drawn index.
    drawn = await page.evaluate("""({ row, pitch }) => {
      const container = document.querySelector('#libitems');
      const spacer = container && container.querySelector('[data-part="window/spacer"]');
      const above = spacer ? Math.round(spacer.getBoundingClientRect().height / pitch) : 0;
      const items = [...document.querySelectorAll(row)];
      const at = Math.floor(items.length / 2);
      const title = items[at] && items[at].querySelector('[data-part="card/title"]');
      return { count: items.length,
               at: above + at,
               title: title ? title.textContent.trim() : null,
               scrolled: document.querySelector('#port').scrollTop };
    }""", {"row": ROW, "pitch": ROW_PITCH})
    journal.check(
        "the row measured is BEYOND the first page — the whole subject of this "
        "hold, and a scroll offset is not that check",
        drawn["at"] >= PAGE_SIZE and drawn["count"] > 0 and drawn["title"],
        f"{drawn['count']} row(s) drawn at {drawn['scrolled']}px; measuring on "
        f"index {drawn['at']} ({drawn['title']!r}), one page is {PAGE_SIZE}")
    if not drawn["title"]:
        await context.close()
        return
    # ONE TASK, and no network. `setOffline` makes the mutation HELD — the
    # layer keeps it and invalidates nothing — so nothing but the optimistic
    # write can take the row off the screen; and the read is a macrotask after
    # it, which is what « at once, not when the network answers » means. The
    # store bump the engine's own delete makes is deliberately NOT sent: what is
    # measured is the query notification alone.
    await page.evaluate("()=>window.__mocks.setOffline(true)")
    await page.evaluate(
        """(title)=>new Promise((done) => {
             window.__deleteLibraryItems([title]);
             setTimeout(done, 0);
           })""", drawn["title"])
    after = await page.evaluate("""(row) => {
      const inside = row + ' [data-part="card/title"]';
      const titles = [...document.querySelectorAll(inside)]
        .map((node) => node.textContent.trim());
      return { titles, count: titles.length };
    }""", ROW)
    journal.check(
        "and a row deleted there is off the screen at once, not when the "
        "network answers",
        drawn["title"] not in after["titles"],
        f"{drawn['title']!r} still drawn: {drawn['title'] in after['titles']}; "
        f"{after['count']} row(s) now, one task after the delete, offline")
    await page.evaluate("()=>window.__mocks.setOffline(false)")
    await context.close()


async def hold_the_selection_state_draws_its_ticks(journal, browser):
    """The named selection state draws its ticks, reached the way the oracle reaches it.

    THE DEFECT THIS EXISTS FOR, and it is a repair's own regression. A selection
    was dropped by an effect WATCHING the listing's question for movement. A
    driven state applies a lens and THEN seeds a selection — two writes in a
    sequence — and from a watcher that is indistinguishable from a reader
    changing the lens with rows ticked. Driven alone the state was fine; driven
    after another library state, as every state is when they are driven in one
    page in order, the lens moved and the ticks were wiped before anything drew
    them. A state called « mode sélection » with nothing selected in it.

    WHY THE ORDER IS THE WHOLE HOLD. The oracle drives all of them in ONE page,
    one after another, and every other rule that touches this state arrives from
    a page where the list is unmounted, so the seed survives. The predecessor
    here is the state that changes the lens, which is the case that failed.
    """
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)

    async def ticks():
        return await page.evaluate("""() => {
          const pressed = [...document.querySelectorAll('#libitems [aria-pressed="true"]')];
          const name = (node) => (node.querySelector(
            '[data-part="tile/title"], [data-part="card/title"]') || node).textContent.trim();
          return { pressed: pressed.map(name),
                   selected: [...(window.__store.read().state.selected || [])] };
        }""")

    await page.evaluate("()=>window.__go('lib-selection')")
    await page.wait_for_timeout(800)
    alone = await ticks()
    journal.check(
        "the selection state seeds ticks when it is the first state driven — "
        "the hold below has a subject",
        len(alone["selected"]) > 0,
        f"{len(alone['selected'])} title(s) in the set, "
        f"{len(alone['pressed'])} row(s) pressed")

    # THE PREDECESSOR IS THE ONE THAT MOVES THE LENS, which is what the oracle's
    # own order puts in front of it.
    await page.evaluate("()=>window.__go('lib-recent')")
    await page.wait_for_timeout(700)
    await page.evaluate("()=>window.__go('lib-selection')")
    await page.wait_for_timeout(800)
    after_another = await ticks()
    journal.check(
        "and it draws them when another library state was driven first, in the "
        "same page — which is the only way anything drives all of them",
        after_another["pressed"] == alone["pressed"]
        and len(after_another["pressed"]) > 0,
        f"{len(after_another['pressed'])} row(s) pressed after « lib-recent », "
        f"{len(alone['pressed'])} when driven alone; the set holds "
        f"{len(after_another['selected'])}")

    # AND THE READER CHANGING THE QUESTION DOES DROP THEM, which is the other
    # half of the same rule and the reason the watcher existed at all: a search
    # narrows what is on screen, and ticks taken before it are ticks nobody can
    # see to untick while « Supprimer » still offers them.
    await page.evaluate("""() => {
      const field = document.querySelector('#libq');
      field.value = 'zzz';
      field.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    await page.wait_for_timeout(800)
    after_search = await ticks()
    journal.check(
        "and a search — the reader changing the question — drops them: a tick "
        "nobody can see is a tick nobody can untick",
        after_search["selected"] == [],
        f"the set holds {len(after_search['selected'])} title(s) after a search "
        f"that narrows the listing")
    await context.close()


async def hold_a_bulk_delete_names_what_was_ticked(journal, browser):
    """A bulk delete acts on the rows the reader ticked, in any order.

    THE DEFECT THIS EXISTS FOR. The selection was a set of LISTING indexes — the
    rank of a row on screen — and the delete read each one as an index into the
    SOURCE. Under the source's own order the two coincide, which is the only
    order anybody had walked. Sorted A → Z, ticking the second and third rows
    named the second and third media of the SOURCE in the dialog and destroyed
    them, while the two the reader had ticked stayed. A search did the same. It
    is the worst class of defect this interface can have — a destructive action
    on something the operator did not choose — and every gate was green over it.

    WHAT IT DRIVES. The order is set through the store rather than through the
    sort panel: the panel is a control of its own with its own holds, and what
    is under test here is the tick and the delete. The rows are ticked by
    pressing them, the dialog is read for the titles it NAMES, and the listing
    is read afterwards for what actually left.
    """
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)
    await page.evaluate("(s)=>window.__go(s)", STATE)
    await page.wait_for_timeout(600)
    # AN ORDER THAT IS NOT THE SOURCE'S, which is the whole point: under the
    # source's own order a listing index and a source index are the same number
    # and the defect is invisible.
    await page.evaluate(
        "()=>window.__store.write({ sortKey: 'az', sortReversed: false })")
    await page.wait_for_timeout(800)
    await page.click('[data-selmode="1"]')
    await page.wait_for_timeout(600)

    picked = await page.evaluate("""() => {
      const rows = [...document.querySelectorAll('[data-part="selection/row"]')];
      const two = rows.slice(1, 3);
      const name = (node) => (node.querySelector('[data-part="card/title"]')
                              || node).textContent.trim();
      const names = two.map(name);
      two.forEach((node) => node.click());
      return names;
    }""")
    await page.wait_for_timeout(400)
    journal.check(
        "two rows are ticked under an order that is not the source's — the "
        "subject of the two holds below",
        len(picked) == 2 and all(picked),
        f"ticked {picked!r}")

    await page.click('[data-delsel="1"]')
    await page.wait_for_timeout(600)
    named = await page.evaluate("""() => {
      const dialog = document.querySelector('[data-part="dialog"]');
      return dialog ? dialog.textContent : '';
    }""")
    journal.check(
        "and the dialog names THOSE TWO — a set of positions read as a set of "
        "media names other media, and the reader confirms a list that says one "
        "thing while the act does another",
        all(title in named for title in picked),
        f"ticked {picked!r}; the dialog says "
        f"{' '.join(named.split())[:160]!r}")

    confirmed = await page.evaluate("""(titles) => {
      const buttons = [...document.querySelectorAll('[data-part="dialog/button"]')];
      const destructive = buttons.find((button) => button.dataset.tone === 'danger')
        || buttons[buttons.length - 1];
      if (!destructive) return { pressed: false };
      destructive.click();
      return new Promise((done) => setTimeout(() => {
        const rows = [...document.querySelectorAll('#libitems > :not([data-part="window/spacer"])')];
        const name = (node) => (node.querySelector(
          '[data-part="card/title"], [data-part="tile/title"]') || node).textContent.trim();
        const drawn = rows.map(name);
        done({ pressed: true,
               stillThere: titles.filter((title) => drawn.includes(title)) });
      }, 600));
    }""", picked)
    journal.check(
        "and confirming removes THOSE TWO from the listing, not two others",
        confirmed["pressed"] and confirmed["stillThere"] == [],
        f"ticked {picked!r}; still drawn after the delete: "
        f"{confirmed.get('stillThere')!r}")
    await context.close()


async def hold_the_list_comes_back_from_selection_mode(journal, browser):
    """Leaving selection mode at a deep scroll leaves the reader where they were.

    THE DEFECT THIS EXISTS FOR, found by walking the real controls. A selection
    row is about 60 px against a card's 126, so entering and leaving the mode
    changes the window's pitch — and the virtualiser memoises its measurements
    on the options it treats as geometry, which do not include the estimated
    size. The browse window was then placed with the SELECTION pitch: the
    leading spacer read 5 620 px, the first row sat 2 807 px below the port, and
    the library was BLANK. It stayed blank through a scroll in either direction,
    because scrolling moves no memoised option either.

    AND THE ROW THE READER WAS LOOKING AT IS THE OTHER HALF, which is why this
    hold reads a TITLE and not a pixel. The first repair brought rows back and
    moved the reader four rows up each time — the place restored was the top of
    the overscan, four lines above anything visible — and a hold that asked only
    « is the port past zero » was green over all of it. « Somewhere » is not a
    place.

    THE ORDER OF THE GESTURES IS THE READER'S, and it is not the obvious one.
    « Sélectionner » lives in the count line, which scrolls away: at a deep
    scroll it sits 2 846 px above the viewport, and a click driver scrolls it
    into view before pressing — so a hold that scrolled deep and THEN pressed
    was measuring a mode change taken at the top of the list, which no reader
    can produce. The mode is entered at the top, where the button is; the depth
    is reached inside the mode; and « Terminé » is pressed in the selection bar,
    which is fixed and always in view.
    """
    context = await browser.new_context(**PHONE)
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)
    await page.evaluate("(s)=>window.__go(s)", STATE)
    await page.wait_for_timeout(600)
    await page.evaluate("()=>window.__libraryNextPage && window.__libraryNextPage()")
    await page.wait_for_timeout(700)

    # EACH MODE DRAWS ITS OWN ROW. Browsing draws cards; selection draws
    # `selection/row`, a different element with a different height — which is
    # the whole reason the pitch moves. A hold reading only the card would
    # measure « nothing on screen » in selection mode and call it the defect.
    # The TITLE is read from whichever of them is drawn, because the title is
    # what the reader recognises across the change.
    async def visible(row, fallback=None):
        drawn = await page.evaluate("""(row) => {
          const port = document.querySelector('#port').getBoundingClientRect();
          const rows = [...document.querySelectorAll(row)];
          const spacer = document.querySelector('#libitems [data-part="window/spacer"]');
          const seen = rows.filter((node) => {
            const box = node.getBoundingClientRect();
            return box.bottom > port.top + 1 && box.top < port.bottom;
          });
          const name = (node) => (node.querySelector(
            '[data-part="card/title"], [data-part="tile/title"]'
          ) || node).textContent.trim();
          return {
            drawn: rows.length,
            inView: seen.length,
            top: seen.length ? name(seen[0]) : null,
            spacer: spacer ? Math.round(spacer.getBoundingClientRect().height) : -1,
            scrolled: Math.round(document.querySelector('#port').scrollTop),
          };
        }""", row)
        # EACH MODE DRAWS ITS OWN ROW, and a walk that crosses a mode change
        # cannot know which of the two is on screen at the moment it reads. The
        # fallback is asked only when the first selector found nothing at all.
        if fallback and not drawn["drawn"]:
            return await visible(fallback)
        return drawn

    SELECTION_ROW = '[data-part="selection/row"]'
    top = await visible(ROW)
    journal.check(
        "the list draws rows in the viewport — the subject of the holds below",
        top["inView"] > 0,
        f"{top['inView']} of {top['drawn']} row(s) in view at "
        f"{top['scrolled']}px, spacer {top['spacer']}px")

    # ENTERED AT THE TOP, where the control is.
    await page.click('[data-selmode="1"]')
    await page.wait_for_timeout(600)
    # AND THE DEPTH IS REACHED INSIDE THE MODE, which is the reader's own way of
    # arriving at a deep scroll with a pitch about to change under them.
    await page.evaluate("()=>{document.querySelector('#port').scrollTop = 3000;}")
    await page.wait_for_timeout(600)
    during = await visible(SELECTION_ROW)
    journal.check(
        "scrolling deep INSIDE selection mode keeps rows on the screen",
        during["inView"] > 0 and during["top"],
        f"{during['inView']} of {during['drawn']} in view at {during['scrolled']}px, "
        f"spacer {during['spacer']}px, top row {during['top']!r}")

    in_port = await page.evaluate("""() => {
      const button = document.querySelector('[data-selmode="0"]');
      if (!button) return null;
      const box = button.getBoundingClientRect();
      return box.top >= 0 && box.bottom <= window.innerHeight;
    }""")
    journal.check(
        "« Terminé » is in the viewport where the reader left it — a control a "
        "driver has to scroll to is a control this walk is not driving",
        in_port is True, f"in the viewport: {in_port}")

    await page.click('[data-selmode="0"]')
    await page.wait_for_timeout(700)
    after = await visible(ROW)
    journal.check(
        "« Terminé » brings the list back — the window is re-measured when the "
        "row pitch changes, not left placed with the other mode's",
        after["inView"] > 0,
        f"{after['inView']} of {after['drawn']} in view at {after['scrolled']}px, "
        f"spacer {after['spacer']}px against {during['spacer']}px at "
        f"{during['scrolled']}px")
    journal.check(
        "and the reader is in front of the SAME ROW — the place is a row, and "
        "a port merely past zero is not one",
        after["top"] is not None and after["top"] == during["top"],
        f"top row {during['top']!r} before, {after['top']!r} after")

    # AND A READER WHO HAS BARELY SCROLLED HAS A PLACE TOO. Three hundred pixels
    # down, the first row is a sliver at the top and it is the row they are
    # reading — but its index is 0, and « restore only a place past zero » moved
    # them two rows down on every round trip. What is refused is a port ABOVE the
    # container's own start, where the head is on screen and scrolling to row 0
    # would hide it.
    await page.evaluate("()=>{document.querySelector('#port').scrollTop = 300;}")
    await page.wait_for_timeout(500)
    barely = await visible(ROW)
    await page.click('[data-selmode="1"]')
    await page.wait_for_timeout(600)
    await page.click('[data-selmode="0"]')
    await page.wait_for_timeout(700)
    barely_after = await visible(ROW)
    # THE TITLE ALONE CANNOT DECIDE THIS ONE, and that is why it is read with a
    # pixel. Three hundred pixels down and at the container's own start the top
    # VISIBLE row is the same row — index 0 — so a hold comparing titles passes
    # on the code that refused to restore item 0 and left the reader two rows
    # further down. What separates them is where the PORT lands: at the
    # container's start, or a screenful past it.
    journal.check(
        "a reader three hundred pixels down keeps their row through the mode "
        "and back — the first row is a place like any other",
        barely["top"] is not None and barely_after["top"] == barely["top"]
        and abs(barely_after["scrolled"] - barely["scrolled"]) < ROW_PITCH,
        f"top row {barely['top']!r} at {barely['scrolled']}px, "
        f"{barely_after['top']!r} at {barely_after['scrolled']}px after — "
        f"the port moved {abs(barely_after['scrolled'] - barely['scrolled'])}px, "
        f"and a row is {ROW_PITCH}px")

    # AND THE OTHER PITCH CHANGE, which changes the LANES as well as the height:
    # list to gallery and back. A place remembered as a LINE is a row in the list
    # and three in the gallery, so restoring one across the switch sent the
    # reader somewhere else entirely — measured, row 21 came back as row 3.
    #
    # DRIVEN BY SCRIPT, AND SAID SO. The mode control sits in the library's head
    # and scrolls away with it: at this depth it is 2 824 px above the viewport,
    # so a click driver would scroll to the top first and the switch would happen
    # where there is no place to lose. The reachable deep pitch change is the
    # selection round trip above; this one drives the MECHANISM — a place across
    # a change of lanes — and a hold that pretended otherwise is the defect this
    # rule was rewritten for.
    await page.evaluate("()=>{document.querySelector('#port').scrollTop = 3000;}")
    await page.wait_for_timeout(600)
    before_grid = await visible(ROW)
    await page.evaluate("()=>document.querySelector('[data-lmode=\"grid\"]').click()")
    await page.wait_for_timeout(900)
    in_grid = await visible('[data-part="tile"]')
    await page.evaluate("()=>document.querySelector('[data-lmode=\"list\"]').click()")
    await page.wait_for_timeout(900)
    back_in_list = await visible(ROW)
    journal.check(
        "the gallery opens on the row the list was showing, and the list comes "
        "back to it — across a change of LANES, where a line index is not a place",
        in_grid["top"] == before_grid["top"]
        and back_in_list["top"] == before_grid["top"],
        f"list {before_grid['top']!r} → gallery {in_grid['top']!r} → "
        f"list {back_in_list['top']!r}")

    # AND A PLACE KEPT FOR A DRAWING THAT DID NOT MOVE THE PITCH IS NOT KEPT.
    # In the GALLERY, entering selection mode changes the draw key and not the
    # pitch — a tile is a tile — so a place taken at a deep scroll had nothing
    # to be restored by and sat waiting. The reader goes back to the top; the
    # next pitch change of ANY kind fires it. A phone produces those without
    # touching a mode: a rotation, a window widening, a font landing, a
    # scrollbar. Measured before the repair: the port jumped 2 940 px to row 39
    # on a rotation taken minutes later.
    await page.evaluate("()=>window.__go('lib-grid')")
    await page.wait_for_timeout(700)
    await page.evaluate("()=>{document.querySelector('#port').scrollTop = 3000;}")
    await page.wait_for_timeout(500)
    deep_in_gallery = await visible('[data-part="tile"]')
    await page.click('[data-selmode="1"]')
    await page.wait_for_timeout(600)
    await page.evaluate("()=>{document.querySelector('#port').scrollTop = 0;}")
    await page.wait_for_timeout(600)
    at_the_top = await visible('[data-part="selection/row"]', '[data-part="tile"]')
    # THE PITCH CHANGE, WITHOUT A MODE CHANGE. A narrower viewport re-measures
    # the tile — the gallery is a container query — which is the pitch moving
    # for a reason the reader never asked about.
    await page.set_viewport_size({"width": 360, "height": 844})
    await page.wait_for_timeout(700)
    after_resize = await visible('[data-part="selection/row"]', '[data-part="tile"]')
    journal.check(
        "the reader was deep in the gallery, entered selection mode — which "
        "changes the drawing and not the pitch — and went back to the top: the "
        "walk below has its subject",
        deep_in_gallery["inView"] > 0 and at_the_top["scrolled"] == 0,
        f"deep at {deep_in_gallery['scrolled']}px on {deep_in_gallery['top']!r}, "
        f"then at {at_the_top['scrolled']}px on {at_the_top['top']!r}")
    journal.check(
        "and a pitch change with no mode change leaves them where they are — a "
        "place kept for a drawing that did not move the pitch EXPIRES, instead "
        "of waiting for the next rotation to fire it",
        after_resize["scrolled"] == 0,
        f"the port is at {after_resize['scrolled']}px on {after_resize['top']!r} "
        f"after the viewport narrowed, where the reader left it at "
        f"{at_the_top['scrolled']}px")
    await page.set_viewport_size({"width": PHONE["viewport"]["width"],
                                  "height": PHONE["viewport"]["height"]})
    await context.close()


async def hold(journal):
    """Counts the window, then scrolls it with a real finger and counts again."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_lanes_are_measured(journal, browser)
        await hold_rows_keep_their_identity(journal, browser)
        await hold_the_gallery_keeps_its_ORDER(journal, browser)
        await hold_a_deleted_row_leaves_the_screen(journal, browser)
        await hold_the_list_comes_back_from_selection_mode(journal, browser)
        await hold_a_bulk_delete_names_what_was_ticked(journal, browser)
        await hold_the_selection_state_draws_its_ticks(journal, browser)
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

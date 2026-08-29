"""R98 — the two dismiss gestures, driven by a real touch stream and by a real mouse.

E-002 and E-003, requested by the operator on 2026-08-28 as marks on a
screenshot. The menu closes on a leftward swipe begun at its right edge; the
sheet closes on a downward swipe begun anywhere in a band four times its handle,
and ONLY while the content is at its top.

WHY THE PROOF IS THREE EXERCISES AND THIS FILE IS TWO OF THEM. The plan says it
of L12 and it governs both gestures:

    A synthetic event is not a finger. It is never cancelled, so it cannot tell
    whether a gesture survives the compositor. Two gestures were lost that way
    and no script noticed. A real mouse on a browser with no touch at all found
    two more.

So this rule drives:

  1. A REAL TOUCH STREAM over the Chrome DevTools Protocol
     (`Input.dispatchTouchEvent`), never `mouse.move`. A synthetic mouse
     produces no `pointercancel` and would validate a gesture the compositor
     would take away.
  2. A REAL MOUSE, on a context with no touch at all — the case that found two
     lost gestures. The drag must work or be cleanly inert, never half.

The third exercise is a pass BY HAND on the device, and no script can stand in
for it: `pointercancel` is delivered by a compositor deciding it wants the
gesture, and neither driver above is that compositor. It is recorded in the
register with its date and its device, and until it is, these gestures are
`to confirm` and not `closed`.

WHAT THIS RULE DOES NOT READ, said before what it does:

  - IT DOES NOT PROVE `pointercancel` HANDLING. It proves the handler EXISTS and
    that a cancel restores rather than closes, by dispatching one — which is a
    cancel this rule caused, not one the compositor chose. The difference is the
    whole reason exercise 3 exists.
  - IT DOES NOT READ THE THRESHOLD'S RIGHTNESS. 70px on each axis is reused from
    the sheet's own constant. Whether a thumb agrees is a finger's answer.
  - IT DOES NOT MEASURE A PAINTING. That the drawer follows the finger is held
    as a transform that MOVED, not as a rendering; the oracle owns renderings,
    and these two gestures are expected to cost it nothing — which is verified
    in the wave rather than assumed here.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, Journal, open_page

# The band widths the gestures declare, so a rule and a variant read one number
# rather than two spellings of it.
DRAWER_BAND = 72
SHEET_BAND = 88

# Far enough past the 70px threshold that a lift is unambiguous, short enough
# that it stays inside the frame.
TRAVEL = 140

# How far the painted drawer may sit behind what the handler wrote. A few pixels
# is the frame the compositor is mid-way through; forty is a transition.
FOLLOW_TOLERANCE = 12


async def touch_drag(page, start, delta, cancel=False):
    """Drives a REAL touch stream through the DevTools Protocol.

    Never `mouse.move`. A synthetic mouse is never cancelled by the compositor,
    so it cannot tell a gesture that survives from one that is taken away — the
    exact blindness that lost two gestures before this rule existed.

    Args:
        page: The Playwright page.
        start: The (x, y) the finger lands on.
        delta: The (dx, dy) it travels.
        cancel: End with `touchCancel` instead of `touchEnd`.
    """
    session = await page.context.new_cdp_session(page)
    x, y = start
    dx, dy = delta
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": x, "y": y}]})
    for step in range(1, 7):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x + dx * step / 6, "y": y + dy * step / 6}]})
        await page.wait_for_timeout(16)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchCancel" if cancel else "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(500)
    await session.detach()


async def open_drawer(page):
    """Opens the menu and returns its right edge."""
    await page.evaluate("()=>window.__go('drawer-navigation')")
    await page.wait_for_timeout(900)
    return await page.evaluate(
        """()=>{
             const drawer = document.querySelector("#drawer");
             const box = drawer.getBoundingClientRect();
             // `data-open` AND NEVER `.open`. Both are on the node and the
             // class is the one that paints, which is exactly why invariant 2
             // refuses it: a rule anchored on a style class dies the day the
             // class is converted, and this one was written with both until
             // `check-markup-contracts` refused it.
             return { open: drawer.hasAttribute("data-open"),
                      right: Math.round(box.right),
                      middle: Math.round((box.top + box.bottom) / 2) };
           }""")


async def drawer_is_open(page):
    """Says whether the menu is still up."""
    return await page.evaluate(
        """()=>{
             const drawer = document.querySelector("#drawer");
             if (!drawer) return false;
             return drawer.hasAttribute("data-open");
           }""")


async def drawer_follows(page, start, travel):
    """Drags the menu half-way and reports what is PAINTED, not what was written.

    THE HOLDS ABOVE READ `data-open` AND NOTHING ELSE, which is why four of them
    passed over a gesture that was entirely dead: « begun outside the band does
    not close it » and « a cancelled swipe puts the menu back » are both
    satisfied by a drag that never started. This one reads the drawer's PAINTED
    transform mid-gesture, so a handler writing a transform the CSS then
    animates away — a 300 ms transition nobody cancelled — is visible.

    Returns:
        A `(written, painted)` pair of pixel offsets, mid-drag.
    """
    session = await page.context.new_cdp_session(page)
    x, y = start
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for step in range(1, 5):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x - travel * step / 4, "y": y}]})
        await page.wait_for_timeout(16)
    reading = await page.evaluate(
        """()=>{
             const drawer = document.querySelector("#drawer");
             const written = drawer.style.transform;
             const painted = new DOMMatrix(getComputedStyle(drawer).transform).m41;
             return { written, painted: Math.round(painted) };
           }""")
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchCancel", "touchPoints": []})
    await page.wait_for_timeout(300)
    await session.detach()
    written = reading["written"]
    asked = int(float(written.split("(")[1].split("px")[0])) if "(" in written else 0
    return asked, reading["painted"]


# WHICH PANEL, and the two are chosen for what they hold rather than for what
# they look like. `sheet-journey`'s content fits, so it can never be scrolled
# and the at-top condition cannot be exercised on it — a first version of this
# rule set `scrollTop` there, read it back as 0, and failed for a reason that
# was the fixture's and not the interface's. `followsheet-complete` overflows by
# 746px, measured.
FITTING_SHEET = "sheet-journey"
SCROLLING_SHEET = "followsheet-complete"


async def open_sheet(page, state=FITTING_SHEET):
    """Opens a panel and returns the geometry the band is measured against."""
    await page.evaluate("(s)=>window.__go(s)", state)
    await page.wait_for_timeout(1100)
    return await page.evaluate(
        """()=>{
             const sheet = document.querySelector("#sheet");
             const box = sheet.getBoundingClientRect();
             return { open: sheet.hasAttribute("data-open"),
                      top: Math.round(box.top),
                      middle: Math.round((box.left + box.right) / 2) };
           }""")


async def sheet_is_open(page):
    """Says whether the panel is still up."""
    return await page.evaluate(
        """()=>document.querySelector("#sheet")?.hasAttribute("data-open") === true""")


async def hold_the_drawer(journal, browser):
    """E-002, by touch and by mouse."""
    context, page = await open_page(browser)

    where = await open_drawer(page)
    journal.check("the menu opens to be dismissed", where["open"],
                  f"its right edge is at {where['right']}")

    # INSIDE the band, which ends ON the right edge.
    await touch_drag(page, (where["right"] - 10, where["middle"]), (-TRAVEL, 0))
    journal.check(
        "a leftward swipe from the menu's right edge closes it",
        not await drawer_is_open(page),
        f"a real touch stream from {where['right'] - 10} travelling {TRAVEL}px "
        "left, dispatched over the DevTools Protocol — never a synthetic mouse, "
        "which is never cancelled and so proves nothing about the compositor")

    where = await open_drawer(page)
    # OUTSIDE the band: the same gesture begun a band's width further left.
    await touch_drag(page, (where["right"] - DRAWER_BAND - 40, where["middle"]),
                     (-TRAVEL, 0))
    journal.check(
        "the same swipe begun outside the band does not close it",
        await drawer_is_open(page),
        f"begun {DRAWER_BAND + 40}px from the edge, past the {DRAWER_BAND}px "
        "band — a band that closes from anywhere is not a band")

    where = await open_drawer(page)
    await touch_drag(page, (where["right"] - 10, where["middle"]), (-TRAVEL, 0),
                     cancel=True)
    journal.check(
        "a cancelled swipe puts the menu back rather than closing it",
        await drawer_is_open(page),
        "a cancel is not a lift — `sheet.tsx` paid for this one, and the "
        "gesture that is taken away is the gesture that must change nothing")

    # THE DRAWER FOLLOWS THE FINGER, read from what is PAINTED. The handler
    # wrote a transform all along; nothing cancelled the 300 ms transition, so
    # the drawer lagged 40-53 px behind and no hold here could see it.
    where = await open_drawer(page)
    asked, painted = await drawer_follows(
        page, (where["right"] - 10, where["middle"]), TRAVEL)
    journal.check(
        "the menu follows the finger rather than animating after it",
        abs(painted - asked) <= FOLLOW_TOLERANCE,
        f"mid-drag the handler wrote {asked}px and the browser painted "
        f"{painted}px — a gap wider than {FOLLOW_TOLERANCE}px is a transition "
        "nobody cancelled, and « a manipulation rather than a blind command » "
        "is then false")

    # THE LINKS ARE NOT DRAGGABLE, held on the CAUSE and not on the behaviour,
    # because the behaviour is not reachable from here.
    #
    # All six `<a>` of the menu cover the band. A mouse drag begun on one starts
    # the browser's own link-drag, and that swallows the pointer stream:
    # `pointerdown`, one `pointermove`, `dragstart`, `pointercancel` — the touch
    # failure's signature from another cause.
    #
    # ⚠ THIS HOLD READS THE DECLARATION, NOT THE DRAG, and the reason is
    # measured rather than assumed: a first version dragged from a link and
    # asserted the drawer closed. It passed WITH the fix and passed WITHOUT it —
    # Playwright's `page.mouse` emits `pointerdown pointerup` and no `dragstart`
    # at all, so it cannot reproduce a native link-drag and the hold discriminated
    # nothing. A hold that cannot fall is worse than no hold, so it was replaced
    # by this one, which falls the moment the declaration goes.
    where = await open_drawer(page)
    links = await page.evaluate(
        """({ band }) => {
             const drawer = document.querySelector("#drawer");
             const edge = drawer.getBoundingClientRect().right;
             const all = [...drawer.querySelectorAll("a")];
             const inBand = all.filter((a) => a.getBoundingClientRect().right >= edge - band);
             return {
               total: all.length,
               inBand: inBand.length,
               undraggable: inBand.filter((a) => {
                 const style = getComputedStyle(a);
                 return style.webkitUserDrag === "none" && style.userSelect === "none";
               }).length,
             };
           }""",
        {"band": DRAWER_BAND})
    journal.check(
        "every menu link under the band refuses the browser's own drag",
        links["inBand"] > 0 and links["undraggable"] == links["inBand"],
        f"{links['undraggable']} of {links['inBand']} links covering the band "
        f"carry `-webkit-user-drag: none` and `user-select: none` "
        f"({links['total']} in the menu) — the remedy `legacy.css:578-587` "
        "already writes for the same class: « it swallows the pointer stream "
        "outright … invisible to a touch test, fatal to a mouse one »")

    where = await open_drawer(page)
    await page.mouse.move(where["right"] - 10, where["middle"])
    await page.mouse.down()
    for step in range(1, 7):
        await page.mouse.move(where["right"] - 10 - TRAVEL * step / 6,
                              where["middle"])
    await page.mouse.up()
    await page.wait_for_timeout(400)
    journal.check(
        "and a real mouse closes it too",
        not await drawer_is_open(page),
        "the browser with no touch at all is the case that found two lost "
        "gestures; the drag must work or be cleanly inert, never half")

    await context.close()


async def hold_the_sheet(journal, browser):
    """E-003, including the one condition that is its whole arbitration."""
    context, page = await open_page(browser)

    where = await open_sheet(page)
    journal.check("the panel opens to be dismissed", where["open"],
                  f"its top edge is at {where['top']}")

    # Inside the band and well below the 22px handle, which is the point: the
    # grip is four times what it was.
    await touch_drag(page, (where["middle"], where["top"] + SHEET_BAND - 12),
                     (0, TRAVEL))
    journal.check(
        "a downward swipe from the widened band closes the panel",
        not await sheet_is_open(page),
        f"begun {SHEET_BAND - 12}px below the panel's edge — far past the 22px "
        "handle that used to be the only grip")

    where = await open_sheet(page)
    await touch_drag(page, (where["middle"], where["top"] + SHEET_BAND + 60),
                     (0, TRAVEL))
    journal.check(
        "the same swipe begun below the band does not close it",
        await sheet_is_open(page),
        f"begun {SHEET_BAND + 60}px down, past the {SHEET_BAND}px band")

    # THE CONDITION THAT IS THE WHOLE ARBITRATION.
    where = await open_sheet(page, SCROLLING_SHEET)
    scrolled = await page.evaluate(
        """()=>{
             const inner = document.querySelector("#sheetin");
             inner.scrollTop = 80;
             inner.dispatchEvent(new Event("scroll", { bubbles: true }));
             return inner.scrollTop;
           }""")
    journal.check(
        "the panel used for the scrolled case can actually be scrolled",
        scrolled > 0,
        f"`#sheetin.scrollTop` reads {scrolled} after being set to 80 — a panel "
        "whose content fits cannot exercise this condition, and a rule that "
        "asserts over one is asserting about nothing")
    await page.wait_for_timeout(300)
    await touch_drag(page, (where["middle"], where["top"] + SHEET_BAND - 12),
                     (0, TRAVEL))
    journal.check(
        "with the content scrolled, the same swipe scrolls and does not close",
        await sheet_is_open(page),
        f"`#sheetin.scrollTop` was {scrolled} — at the top a downward drag is a "
        "dismissal, anywhere else it is a scroll, and a panel that opens is "
        "always at the top so the first gesture is always a dismissal")

    where = await open_sheet(page)
    await touch_drag(page, (where["middle"], where["top"] + SHEET_BAND - 12),
                     (0, TRAVEL), cancel=True)
    journal.check(
        "a cancelled downward swipe puts the panel back",
        await sheet_is_open(page),
        "the same posture as the menu's, and the same reason")

    # AN UPWARD SWIPE FROM INSIDE THE BAND STILL SCROLLS, and nothing exercised
    # this until an adversarial review measured it. `touch-action: none` takes
    # BOTH axes, so while the band is armed — which is every sheet the moment it
    # opens — an upward swipe in the top 88px scrolled nothing, dismissed
    # nothing, and did nothing at all: 0 against 399 for the same gesture twelve
    # pixels lower. The arbitration is POSITIONAL, and what shipped was
    # bidirectional.
    where = await open_sheet(page, SCROLLING_SHEET)
    before = await page.evaluate(
        """()=>document.querySelector("#sheetin").scrollTop""")
    await touch_drag(page, (where["middle"], where["top"] + SHEET_BAND - 12),
                     (0, -TRAVEL))
    after = await page.evaluate(
        """()=>document.querySelector("#sheetin").scrollTop""")
    journal.check(
        "an upward swipe from inside the band scrolls the content",
        after > before and await sheet_is_open(page),
        f"`#sheetin.scrollTop` went {before} → {after} and the panel stayed "
        "open — the band claims the DOWNWARD half only, and hands the other "
        "back to the content")

    await context.close()


async def hold(journal):
    """Drives both gestures on a phone frame."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_drawer(journal, browser)
        await hold_the_sheet(journal, browser)
        await browser.close()
    journal.summary(errors)


def main():
    journal = Journal(
        "R98 — the two dismiss gestures, by a real touch stream and a real mouse")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()

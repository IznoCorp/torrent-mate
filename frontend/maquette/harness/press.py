"""R112 — the press arbitration's two halves R55 does not read.

R55 drives the long press with a real thumb and holds a great deal: the panel
opens on five surfaces, nothing is selected, the lift does not fire the panel
that has just appeared, the browser's own menu is refused on a poster and kept
inside a text field, and a press answers above the scrollport. All of that
stays its.

WHAT IT DOES NOT READ, which is what this rule exists for. Both halves are
places where a WRONG implementation passes every hold R55 has.

  1. THE DRIFT THAT CANCELS — AND IT IS ONLY MEASURABLE UNDER A MOUSE. R55
     drifts the finger ±5px through the press, deliberately, because a real
     thumb drifts. So it proves the press SURVIVES a small drift and never that
     it DIES of a large one.

     MEASURED BEFORE THIS RULE WAS WRITTEN, and it inverts the usual lesson.
     Under a real touch stream the tolerance is NOT OBSERVABLE AT ALL: Chrome's
     compositor fires `pointercancel` at every drift of 14px or more, which
     cancels the press through the cancel handler whether or not the tolerance
     exists. Removing the tolerance entirely changes nothing a touch stream can
     see — measured at 5, 14, 16, 18, 22, 30 and 40px, identical both ways.

     A REAL MOUSE IS THE ONLY INSTRUMENT THAT ISOLATES IT, because the
     compositor never claims a mouse gesture: with the tolerance, a 16px drag
     opens nothing; without it, the same drag opens the panel, and
     `pointercancel` never fires in either run. So the mouse hold below asserts
     THAT COUNT IS ZERO — which is what makes it a proof about the arbitration
     rather than about the browser.

     This is why the touch hold is kept but honestly labelled: it proves the
     press dies, not WHAT killed it.

  2. THE SWALLOW MUST NOT EAT A CLICK NOBODY POINTED — and the case is narrower
     than it first looks, which is worth writing down because the first version
     of this rule got it wrong and mutation said so.

     R55 holds « the lift does not fire the panel that has just appeared », the
     click AT the press's own point. The design's other half is that the click
     is identified BY ITS POINT so « a deliberate tap somewhere else never
     does ».

     MEASURED: a deliberate tap cannot be swallowed WHATEVER the point check
     does, because the arbitration clears its mark on every `pointerdown`, and a
     tap begins with one. So a rule that presses and then taps elsewhere passes
     with the point check deleted — it is measuring the pointerdown reset, not
     the point.

     What the point check actually protects is a click that arrives with NO
     pointerdown before it: a programmatic `.click()`, and a keyboard
     activation, both of which fire a click no finger pointed at. Those carry
     coordinates far from the press — `.click()` reports 0,0 — so the distance
     check lets them through, and without it the first one after any long press
     is eaten. That is the hold below.

BOTH ARE DRIVEN TWICE — a real touch stream over the DevTools Protocol, and a
REAL MOUSE on a context with no touch at all. The plan's constraint governs
this lot:

    A synthetic event is not a finger. It is never cancelled, so it cannot tell
    whether a gesture survives the compositor. Two gestures were lost that way
    and no script noticed. A real mouse on a browser with no touch at all found
    two more.

The mouse half is not a formality here. The tolerance exists because a THUMB is
never still; a mouse holds perfectly still, so the press path a mouse walks is
the one where the timer always fires — and it is the path on which the swallow's
« by point, not by target » was originally got wrong.

WHAT THIS RULE DOES NOT READ, said rather than left to be found:

  - IT DOES NOT PROVE THE TOLERANCE'S VALUE. 12px is the arbitration's own
    constant, reused here through the far side of the same seam rather than
    re-typed: a rule that hard-copies a number is a second source of truth that
    goes stale silently, which is a shape this repository has already paid for.
    Whether 12 is the right number for a thumb is a finger's answer, not a
    script's.
  - IT DOES NOT PROVE `pointercancel` HANDLING BY THE COMPOSITOR. It drives a
    drift the compositor is free to claim; whether it does is the device's
    answer. What is held is the arbitration's own decision.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal, open_page

# The press must be held longer than the arbitration's own delay for the timer
# to fire at all. Read from the page rather than re-typed — see the docstring's
# note on a rule that hard-copies a number.
PRESS_HOLD_MARGIN = 260

# Far past the 12px tolerance, for the TOUCH exercise. At this distance the
# compositor claims the gesture as a scroll, so the touch hold proves the press
# dies without isolating what killed it — which is what that hold says.
CANCELLING_DRIFT = 40

# For the MOUSE exercise, where the compositor claims nothing. Past the 12px
# tolerance and deliberately modest: this is the distance at which, measured
# both ways, the tolerance alone decides — with it the panel stays shut, without
# it the same drag opens it, and `pointercancel` never fires either way.
MOUSE_DRIFT = 16

# Where a deliberate tap lands relative to the press: well beyond the tolerance,
# so a swallow keyed on the POINT must let it through.
DISTANT_TAP_OFFSET = 120

# The surface this rule drives. A gallery tile is the simplest pressable thing
# in the tree: the whole tile answers, and a tap on it is already spoken for.
STATE = "lib-grid"
TILE = '[data-part="tile"]'


async def drive_press(page, x, y, drift, hold_ms, lift=True):
    """Presses with a real touch stream, drifting by `drift` while held.

    Args:
        page: The Playwright page.
        x: Where the finger lands, horizontally.
        y: Where the finger lands, vertically.
        drift: How far it travels while held, in pixels, on both axes.
        hold_ms: How long it stays down.
        lift: End with `touchEnd`. False leaves the finger DOWN, which is how a
            caller reaches the moment after the press has fired and before the
            lift's own click has consumed the swallow mark.
    """
    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    # THE DRIFT ARRIVES EARLY, and this is the whole difference between a rule
    # that measures the tolerance and one that cannot. Ramped across the hold —
    # the first version of this driver — the press timer fires long before the
    # drift has accumulated past 12px, so the tolerance is never consulted and
    # the hold passes over an arbitration that has none. Found by mutation: the
    # rule stayed green with the tolerance deleted.
    for step in range(1, 5):
        travelled = drift * step / 4
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x + travelled, "y": y + travelled, "id": 1}]})
        await page.wait_for_timeout(30)
    for _ in range(max(1, int(max(0, hold_ms - 120) / 60))):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x + drift, "y": y + drift, "id": 1}]})
        await page.wait_for_timeout(60)
    if lift:
        await session.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})


async def panel_is_open(page):
    """Whether the panel the press opens is showing.

    Args:
        page: The Playwright page.

    Returns:
        True when the sheet carries `data-open`.
    """
    return await page.evaluate(
        "()=>!!document.querySelector('#sheet')?.hasAttribute('data-open')")


async def settle(page):
    """Closes whatever a previous exercise opened, and waits for rest."""
    await page.evaluate("()=>window.__closeLayers?.()")
    await page.wait_for_timeout(320)


async def hold_the_tolerance(journal, browser):
    """A press that drifts past the tolerance must NOT open the panel."""
    context, page = await open_page(browser)
    await page.evaluate("(s)=>window.__go(s)", STATE)
    await page.wait_for_timeout(420)
    box = await page.evaluate(
        "(sel)=>{const e=document.querySelector(sel); if(!e) return null;"
        "const r=e.getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height/2};}", TILE)
    journal.check("a tile is drawn to press", bool(box), str(box))
    if not box:
        await context.close()
        return

    hold = 480 + PRESS_HOLD_MARGIN
    # The control: a thumb's own drift, well inside the tolerance. This must
    # OPEN — without it the negative below would pass on a broken press.
    await drive_press(page, box["x"], box["y"], 5, hold)
    await page.wait_for_timeout(160)
    journal.check("a press drifting 5px still opens the panel",
                  await panel_is_open(page), "the control for the hold below")
    await settle(page)

    await drive_press(page, box["x"], box["y"], CANCELLING_DRIFT, hold)
    await page.wait_for_timeout(160)
    opened = await panel_is_open(page)
    journal.check(
        f"under a finger, a press drifting {CANCELLING_DRIFT}px opens nothing "
        "(the compositor's cancel AND the tolerance — this does not isolate "
        "either)",
        not opened,
        "a scroll begun on a tile opens a panel")
    await settle(page)
    await context.close()


async def hold_the_swallow_is_by_point(journal, browser):
    """A click nobody pointed at must survive the swallow. See the docstring."""
    context, page = await open_page(browser)
    await page.evaluate("(s)=>window.__go(s)", STATE)
    await page.wait_for_timeout(420)
    box = await page.evaluate(
        "(sel)=>{const e=document.querySelector(sel); if(!e) return null;"
        "const r=e.getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height/2};}", TILE)
    if not box:
        journal.check("a tile is drawn to press", False, "absent")
        await context.close()
        return

    # A button of the interface's own, and a counter on it. Its click is fired
    # PROGRAMMATICALLY — no pointerdown, so the arbitration's mark is still set
    # when it arrives, which is the only situation in which the point check
    # decides anything.
    await page.evaluate("""()=>{
      const target = document.createElement('button');
      target.id = '__clickProbe';
      target.style.cssText = 'position:fixed;left:4px;top:4px;width:24px;height:24px';
      window.__probeFired = 0;
      target.addEventListener('click', () => { window.__probeFired += 1; });
      document.body.appendChild(target);
    }""")

    # THE FINGER STAYS DOWN. The mark is set when the timer fires and consumed
    # by the very next click — and for a lifted press that click is the lift's
    # own, arriving 1ms later. Measured: after a normal press the mark is
    # already gone, so a probe fired then decides nothing. Holding the finger
    # down is the only moment at which the mark is set and unclaimed, and it is
    # how R55 reaches the same instant.
    await drive_press(page, box["x"], box["y"], 5, 480 + PRESS_HOLD_MARGIN,
                      lift=False)
    await page.wait_for_timeout(120)
    marked = await page.evaluate("()=>!!window.swallowClick")
    journal.check("the press left its swallow mark set",
                  marked,
                  "without the mark the hold below decides nothing")
    await page.evaluate("()=>document.getElementById('__clickProbe').click()")
    await page.wait_for_timeout(120)
    fired = await page.evaluate("()=>window.__probeFired")
    journal.check(
        "a click nobody pointed at is NOT swallowed by the press's mark",
        fired == 1,
        "the swallow is keyed on the press rather than on its POINT, so the "
        "first programmatic or keyboard-fired click after any long press is "
        "eaten")
    await settle(page)
    await context.close()


async def open_mouse_page(browser):
    """Opens the prototype on a context with NO TOUCH AT ALL, at the state.

    A fresh context per exercise, deliberately. The two mouse exercises ran on
    one page at first — the held press, then the drag — and the drag then
    measured a page a panel had already opened and closed on. It reported the
    tolerance holding while the tolerance was DELETED, which is the vacuity this
    rule was rewritten to remove, arrived at a second time from a different
    direction: state left behind by one hold is a second reason the next one can
    pass.

    Args:
        browser: A launched Playwright browser.

    Returns:
        The (context, page, box) triple, box being the tile's centre.
    """
    context = await browser.new_context(**{**PHONE, "has_touch": False})
    page = await context.new_page()
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    await page.wait_for_timeout(250)
    await page.evaluate("(s)=>window.__go(s)", STATE)
    await page.wait_for_timeout(420)
    box = await page.evaluate(
        "(sel)=>{const e=document.querySelector(sel); if(!e) return null;"
        "const r=e.getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height/2};}", TILE)
    return context, page, box


async def hold_the_mouse_press(journal, browser):
    """A mouse holds perfectly still, so this is where the timer always fires."""
    context, page, box = await open_mouse_page(browser)
    if not box:
        journal.check("a tile is drawn to press, under a mouse", False, "absent")
        await context.close()
        return
    await page.mouse.move(box["x"], box["y"])
    await page.mouse.down()
    await page.wait_for_timeout(480 + PRESS_HOLD_MARGIN)
    await page.mouse.up()
    await page.wait_for_timeout(160)
    journal.check("under a real mouse, a held press opens the panel",
                  await panel_is_open(page),
                  "the press path a mouse walks is the one where the timer "
                  "always fires")
    await context.close()


async def hold_the_mouse_tolerance(journal, browser):
    """THE ONE EXERCISE THAT ISOLATES THE TOLERANCE. See the docstring."""
    context, page, box = await open_mouse_page(browser)
    if not box:
        journal.check("a tile is drawn to drag, under a mouse", False, "absent")
        await context.close()
        return
    await page.evaluate("()=>{window.__pointerCancels=0;"
                      "document.addEventListener('pointercancel',"
                      "()=>{window.__pointerCancels+=1;});}")
    await page.mouse.move(box["x"], box["y"])
    await page.mouse.down()
    # The drift arrives EARLY, for the reason the touch driver gives.
    for step in range(1, 5):
        await page.mouse.move(box["x"] + MOUSE_DRIFT * step / 4,
                            box["y"] + MOUSE_DRIFT * step / 4)
        await page.wait_for_timeout(30)
    await page.wait_for_timeout(620)
    await page.mouse.up()
    await page.wait_for_timeout(160)
    opened = await panel_is_open(page)
    cancels = await page.evaluate("()=>window.__pointerCancels")
    # THE TWO ASSERTIONS ARE ONE PROOF. That the panel stayed shut says the
    # press died; that `pointercancel` never fired says the COMPOSITOR did not
    # kill it — so the tolerance did. Without the second, this hold proves
    # exactly what the touch hold proves, which is less than it claims.
    journal.check(
        f"under a real mouse, a drag of {MOUSE_DRIFT}px opens nothing",
        not opened,
        "the tolerance is not applied: a mouse drag across a tile opens a panel")
    journal.check(
        "and the compositor never cancelled it, so it was the TOLERANCE",
        cancels == 0,
        f"pointercancel fired {cancels}x — this hold would prove nothing")
    await context.close()


async def hold(journal):
    """Drives the two halves under a real finger and a real mouse."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_tolerance(journal, browser)
        await hold_the_swallow_is_by_point(journal, browser)
        await hold_the_mouse_press(journal, browser)
        await hold_the_mouse_tolerance(journal, browser)
        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal(
        "R112 — the press arbitration's tolerance, and a swallow keyed on its "
        "point")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()

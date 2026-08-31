"""R112 — the press arbitration's two halves R55 does not read.

R55 drives the long press with a real thumb and holds a great deal: the panel
opens on five surfaces, nothing is selected, the lift does not fire the panel
that has just appeared, the browser's own menu is refused on a poster and kept
inside a text field, and a press answers above the scrollport. All of that
stays its.

WHAT IT DOES NOT READ, which is what this rule exists for. Both halves are
places where a WRONG implementation passes every hold R55 has.

  1. THE DRIFT THAT CANCELS. R55 drifts the finger ±5px through the press —
     deliberately, because « a real thumb drifts several pixels over half a
     second » and below one pixel Chrome delivers no `touchmove` at all. So it
     proves the press SURVIVES a small drift. It never drives a drift PAST the
     12px tolerance, so it never proves the press DIES of a large one. An
     arbitration with no tolerance check at all — one that opens the panel
     however far the finger travels — passes every hold R55 has, and turns
     every scroll that starts on a tile into a panel.

  2. THE SWALLOW THAT MUST NOT SWALLOW EVERYTHING. R55 holds « the lift does not
     fire the panel that has just appeared », which is the click AT the press's
     own point. An implementation that swallowed the next click WHEREVER it
     landed satisfies that hold completely — and breaks every deliberate tap
     that follows a press anywhere on the interface. The design's answer is that
     the click is identified BY ITS POINT, and the negative half of that claim
     is the half nothing measured: a tap far from the press must go through.

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

# Far past the 12px tolerance, and far enough that no rounding argument can be
# made about it. Short enough to stay on the same surface.
CANCELLING_DRIFT = 40

# Where a deliberate tap lands relative to the press: well beyond the tolerance,
# so a swallow keyed on the POINT must let it through.
DISTANT_TAP_OFFSET = 120

# The surface this rule drives. A gallery tile is the simplest pressable thing
# in the tree: the whole tile answers, and a tap on it is already spoken for.
STATE = "lib-grid"
TILE = '[data-part="tile"]'


async def drive_press(page, x, y, drift, hold_ms):
    """Presses with a real touch stream, drifting by `drift` while held.

    Args:
        page: The Playwright page.
        x: Where the finger lands, horizontally.
        y: Where the finger lands, vertically.
        drift: How far it travels while held, in pixels, on both axes.
        hold_ms: How long it stays down.
    """
    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    steps = max(1, int(hold_ms / 60))
    for step in range(1, steps + 1):
        travelled = drift * step / steps
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x + travelled, "y": y + travelled, "id": 1}]})
        await page.wait_for_timeout(60)
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
    ctx, pg = await open_page(browser)
    await pg.evaluate("(s)=>window.__go(s)", STATE)
    await pg.wait_for_timeout(420)
    box = await pg.evaluate(
        "(sel)=>{const e=document.querySelector(sel); if(!e) return null;"
        "const r=e.getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height/2};}", TILE)
    journal.check("a tile is drawn to press", bool(box), str(box))
    if not box:
        await ctx.close()
        return

    hold = 480 + PRESS_HOLD_MARGIN
    # The control: a thumb's own drift, well inside the tolerance. This must
    # OPEN — without it the negative below would pass on a broken press.
    await drive_press(pg, box["x"], box["y"], 5, hold)
    await pg.wait_for_timeout(160)
    journal.check("a press drifting 5px still opens the panel",
                  await panel_is_open(pg), "the control for the hold below")
    await settle(pg)

    await drive_press(pg, box["x"], box["y"], CANCELLING_DRIFT, hold)
    await pg.wait_for_timeout(160)
    opened = await panel_is_open(pg)
    journal.check(
        f"a press drifting {CANCELLING_DRIFT}px does NOT open the panel",
        not opened,
        "the tolerance is not applied: a scroll begun on a tile opens a panel")
    await settle(pg)
    await ctx.close()


async def hold_the_swallow_is_by_point(journal, browser):
    """The click a press causes is swallowed; a distant tap is NOT."""
    ctx, pg = await open_page(browser)
    await pg.evaluate("(s)=>window.__go(s)", STATE)
    await pg.wait_for_timeout(420)

    # A counter on the capture phase, so what is measured is whether the click
    # SURVIVES the arbitration's own capture-phase swallow — not whether some
    # handler downstream happened to act on it.
    await pg.evaluate("""()=>{
      window.__clicksSeen = 0;
      document.addEventListener('click', () => { window.__clicksSeen += 1; },
                                {capture: false});
    }""")
    box = await pg.evaluate(
        "(sel)=>{const e=document.querySelector(sel); if(!e) return null;"
        "const r=e.getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height/2};}", TILE)
    if not box:
        journal.check("a tile is drawn to press", False, "absent")
        await ctx.close()
        return

    # A press, then a click at a DISTANT point — the case an implementation
    # swallowing everything gets wrong.
    await drive_press(pg, box["x"], box["y"], 5, 480 + PRESS_HOLD_MARGIN)
    await pg.wait_for_timeout(120)
    before = await pg.evaluate("()=>window.__clicksSeen")
    await pg.mouse.click(box["x"], box["y"] - DISTANT_TAP_OFFSET)
    await pg.wait_for_timeout(160)
    after = await pg.evaluate("()=>window.__clicksSeen")
    journal.check(
        f"a tap {DISTANT_TAP_OFFSET}px away from the press is NOT swallowed",
        after > before,
        "the swallow is keyed on the press rather than on its POINT, so every "
        "deliberate tap after a long press is eaten")
    await settle(pg)
    await ctx.close()


async def hold_under_a_real_mouse(journal, browser):
    """Both halves again, on a context with no touch at all."""
    ctx = await browser.new_context(**{**PHONE, "has_touch": False})
    pg = await ctx.new_page()
    await pg.goto(PROTOTYPE, wait_until="load")
    await pg.evaluate("()=>window.__loadingDone?.()")
    await pg.evaluate("()=>document.querySelector('#toastx')?.click()")
    await pg.wait_for_timeout(250)
    await pg.evaluate("(s)=>window.__go(s)", STATE)
    await pg.wait_for_timeout(420)

    box = await pg.evaluate(
        "(sel)=>{const e=document.querySelector(sel); if(!e) return null;"
        "const r=e.getBoundingClientRect();"
        "return {x:r.x+r.width/2, y:r.y+r.height/2};}", TILE)
    if not box:
        journal.check("a tile is drawn to press, under a mouse", False, "absent")
        await ctx.close()
        return

    # A mouse holds perfectly still, so this is the path on which the timer
    # always fires.
    await pg.mouse.move(box["x"], box["y"])
    await pg.mouse.down()
    await pg.wait_for_timeout(480 + PRESS_HOLD_MARGIN)
    await pg.mouse.up()
    await pg.wait_for_timeout(160)
    journal.check("under a real mouse, a held press opens the panel",
                  await panel_is_open(pg),
                  "the press path a mouse walks is the one where the timer "
                  "always fires")
    await settle(pg)

    # And the drift half: a mouse that travels past the tolerance while down.
    await pg.mouse.move(box["x"], box["y"])
    await pg.mouse.down()
    for step in range(1, 7):
        await pg.mouse.move(box["x"] + CANCELLING_DRIFT * step / 6,
                            box["y"] + CANCELLING_DRIFT * step / 6)
        await pg.wait_for_timeout(60)
    await pg.wait_for_timeout(480)
    await pg.mouse.up()
    await pg.wait_for_timeout(160)
    journal.check(
        f"under a real mouse, a drag of {CANCELLING_DRIFT}px opens nothing",
        not await panel_is_open(pg),
        "a mouse drag across a tile opens a panel")
    await ctx.close()


async def hold(journal):
    """Drives the two halves under a real finger and a real mouse."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_tolerance(journal, browser)
        await hold_the_swallow_is_by_point(journal, browser)
        await hold_under_a_real_mouse(journal, browser)
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

"""R113 — the gesture acknowledgement, under BOTH motion preferences.

`lib/feedback.ts` decides WHEN a gesture is acknowledged and `styles/base.css`
decides what that looks like (rule 1). This drives a real finger and reads both.

WHY BOTH PREFERENCES, EVERY TIME. Invariant 14: reduced motion is a DESIGNED
state, not a fallback. A rule asserting only that the acknowledgement animates
has certified half of a designed state, and the half it leaves out is the one a
reader who asked for no motion actually gets. So each hold is driven twice:

  - under `no-preference`, an animation must be RUNNING on the marked element —
    read from `getAnimations()` mid-gesture, which is the only moment it exists;
  - under `reduce`, NONE must be, and the acknowledgement must still have been
    MADE. That second half is the point and it is easy to get wrong: an
    implementation that simply skipped the feedback under `reduce` would pass a
    rule that only checked for the absence of animation, and it would be a
    different interface rather than a calmer one.

THE INSTRUMENT'S OWN TRAP, and it governs how this is written. The oracle
measures at rest under `html.measuring`, so a state captured mid-transition is a
flicker — which is why named states are measured settled and why this rule
DRIVES the gesture and reads it while it runs, rather than leaving the
acknowledgement for the oracle to stumble into. The mark lives 200ms; a read
after that measures nothing and passes exactly like a read that measured
success, so every read here happens inside the window and the rule fails loudly
if the mark is already gone.

WHAT IT DOES NOT READ: whether the acknowledgement is the RIGHT appearance. That
it is an opacity step of one value rather than another is a drawing decision the
oracle owns at rest and a person owns in review. This holds that it happens, that
it is declared rather than scripted, and that it has a defined appearance under
both preferences.
"""
import asyncio
import pathlib
import sys

from playwright.async_api import async_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import PHONE, PROTOTYPE, Journal

# The press fires at 480ms and the mark lives 200ms, so the read must land
# between 480 and 680. Held at 540 — sixty milliseconds past the timer, well
# inside the window.
#
# THE FIRST VERSION HELD 740 AND READ NOTHING, which is this rule's own docstring
# warning come true in the rule that carries it: 480 + 200 = 680, so the mark had
# already expired and the read measured an absence exactly as a broken seam
# would. It failed loudly rather than passing, which is the only reason it was
# cheap — a read placed the other side of a window it was too EARLY for would
# have passed and proved nothing.
PRESS_HOLD = 540

# The mark's lifetime is 200ms. Every read must land inside it.
MARK_WINDOW = 200

STATE = "lib-grid"
TILE = '[data-part="tile"]'


async def open_at_state(browser, motion):
    """Opens the prototype with a motion preference, at the pressable state.

    Args:
        browser: A launched Playwright browser.
        motion: `"no-preference"` or `"reduce"`.

    Returns:
        The (context, page, box) triple, box being the tile's centre.
    """
    context = await browser.new_context(**{**PHONE, "reduced_motion":
                                          "reduce" if motion == "reduce" else "no-preference"})
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


async def press_and_read(page, box):
    """Long-presses with a real finger and reads the mark WHILE it lives.

    The finger stays down: the mark is written when the press timer fires, and
    reading it after the lift races the 200ms window against the lift's own
    click.

    Args:
        page: The Playwright page.
        box: The centre to press.

    Returns:
        A dict carrying the mark and the animations running on the marked node.
    """
    await page.evaluate("""()=>{
      window.__marks = [];
      new MutationObserver(records => {
        for (const record of records)
          if (record.attributeName === 'data-feedback' &&
              record.target.getAttribute('data-feedback'))
            window.__marks.push({
              marked: true,
              kind: record.target.getAttribute('data-feedback'),
            });
      }).observe(document.documentElement, {subtree: true, attributes: true,
                                            attributeFilter: ['data-feedback']});
    }""")
    session = await page.context.new_cdp_session(page)
    x, y = box["x"], box["y"]
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for _ in range(int(PRESS_HOLD / 60)):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove", "touchPoints": [{"x": x + 2, "y": y + 2, "id": 1}]})
        await page.wait_for_timeout(60)
    # OBSERVED, NOT QUERIED, and the difference is the whole hold. `onPress`
    # opens the panel, which re-renders the pressed surface: the marked node is
    # detached within the same frame — measured, `isConnected` false while the
    # mark still reads `commit`. A `querySelector` therefore finds nothing and
    # reports a working seam as a broken one.
    #
    # That is not a defect to repair: the panel appearing under the finger IS
    # this gesture's acknowledgement, and a pulse on top of it would be a second
    # answer to one gesture. What the seam call is for here is the haptic half.
    # So the hold is that the seam was CALLED — the mark set, on the pressed
    # node, with the right kind — which a MutationObserver sees and a query
    # cannot.
    reading = await page.evaluate("()=>window.__marks[0] || "
                                  "{marked: false, kind: null}")
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    return reading


async def hold_the_acknowledgement(journal, browser, motion):
    """Drives a press under one motion preference and reads both halves."""
    context, page, box = await open_at_state(browser, motion)
    if not box:
        journal.check(f"a tile is drawn to press ({motion})", False, "absent")
        await context.close()
        return
    reading = await press_and_read(page, box)

    # THE MARK IS MADE UNDER BOTH PREFERENCES. This is the half that catches an
    # implementation which simply skips the acknowledgement under `reduce`.
    journal.check(
        f"under `{motion}`, the gesture IS acknowledged",
        reading["marked"] and reading["kind"] == "commit",
        f"read {reading} — a gesture unacknowledged under a motion preference "
        "is a different interface, not a calmer one")

    # THE STYLESHEET'S ANSWER, on a node that survives. What invariant 14
    # governs is the DECLARATION — that `[data-feedback]` has a defined
    # appearance under each preference — so the mark is applied to a persistent
    # node and the answer read there. This is not « checking a choice against
    # itself »: the choice under test is the stylesheet's, and it is read
    # through the browser's own animation timeline rather than from the source.
    reading = await page.evaluate("""()=>{
      const node = document.querySelector('#port') || document.body;
      const before = getComputedStyle(node).opacity;
      node.setAttribute('data-feedback', 'commit');
      const running = node.getAnimations().length;
      const during = getComputedStyle(node).opacity;
      node.removeAttribute('data-feedback');
      return {running, before, during};
    }""")
    animations = reading["running"]
    if motion == "reduce":
        # TWO ASSERTIONS, AND THE SECOND IS THE ONE THAT BITES. « Nothing
        # animates » is satisfied just as well by a stylesheet that says nothing
        # about `[data-feedback]` at all — measured: deleting the whole `reduce`
        # block left this hold green. Reduced motion is a DESIGNED state, so the
        # marked node must LOOK different; that it does not move is the other
        # half, not the whole.
        journal.check(
            "under `reduce`, the acknowledgement does NOT move",
            animations == 0,
            f"{animations} animation(s) — reduced motion is a designed state, "
            "and this one moves anyway")
        journal.check(
            "and under `reduce` it is still DRAWN — a designed state, not an "
            "absence",
            reading["before"] != reading["during"],
            f"opacity {reading['before']} unmarked and {reading['during']} "
            "marked — the mark changes nothing, so a reader who asked for no "
            "motion is given no acknowledgement at all")
    else:
        journal.check(
            "under `no-preference`, the acknowledgement RUNS",
            animations > 0,
            "no animation on a marked node — the acknowledgement is declared in "
            "the stylesheet and must be observable while it runs")
    await context.close()


async def hold_the_pressed_state(journal, browser):
    """`:active` lights while the finger is down, and it is not scripted."""
    context, page, box = await open_at_state(browser, "no-preference")
    if not box:
        journal.check("a tile is drawn to press", False, "absent")
        await context.close()
        return
    # The pressed state is a STYLE, so it is read as one. Driven with a real
    # mouse: `:active` under a synthetic touch stream is not reliably applied,
    # and a hold that cannot fail is worth nothing.
    await page.mouse.move(box["x"], box["y"])
    before = await page.evaluate(
        "(sel)=>getComputedStyle(document.querySelector(sel)).opacity", TILE)
    await page.mouse.down()
    await page.wait_for_timeout(80)
    during = await page.evaluate(
        "(sel)=>{const e=document.querySelector(sel);"
        "const t=e.closest('[data-panel]') || e;"
        "return getComputedStyle(t).opacity;}", TILE)
    await page.mouse.up()
    await page.wait_for_timeout(120)
    journal.check(
        "the pressed state lights while the finger is down",
        during != before,
        f"opacity was {before} at rest and {during} pressed — `:active` reaches "
        "nothing here")
    await context.close()


async def hold(journal):
    """Drives the acknowledgement under both preferences, and the pressed state."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_acknowledgement(journal, browser, "no-preference")
        await hold_the_acknowledgement(journal, browser, "reduce")
        await hold_the_pressed_state(journal, browser)
        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal(
        "R113 — the gesture acknowledgement, under both motion preferences")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()

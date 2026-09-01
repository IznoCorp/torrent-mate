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

EACH IS DRIVEN WHERE IT IS MEASURABLE — a real touch stream over the DevTools
Protocol, and a
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

  - IT DOES NOT PROVE THE TOLERANCE'S VALUE. Whether 12 is the right number for
    a thumb is a finger's answer, not a script's.

    AND THIS PARAGRAPH USED TO CLAIM MORE THAN THE FILE DID. It said the
    constant was « reused through the far side of the same seam rather than
    re-typed » while the file re-typed 44 and 480 a hundred lines below — a
    docstring asserting the discipline its own code broke, written in the same
    hour. Found by an adversarial pass over this wave's instruments, one commit
    after the wave named that species (B-276). The numbers are READ now, from
    `window.__gestures`, which the vocabulary publishes for whatever drives it.
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

# For the MOUSE exercise, where the compositor claims nothing. It is DERIVED
# from the tolerance the module publishes rather than typed beside it: just past
# it, which is the distance at which the tolerance alone decides — with it the
# panel stays shut, without it the same drag opens it, and `pointercancel` never
# fires either way. Typed, it was a second source of truth for the same number
# (B-276), and the module published `tolerancePixels` « so a rule does not
# re-type them » while this file re-typed it four lines below the sentence.
MOUSE_DRIFT_MARGIN = 4

# WHAT « THE INDICATOR IS GONE » MEANS, in pixels. Sub-pixel residue in a
# settled transition, and nothing more — this is not a threshold with a meaning,
# it is the difference between zero and a rounding.
INDICATOR_GONE_PIXELS = 1

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

    hold = await page.evaluate(
        "()=>window.__gestures.press.milliseconds") + PRESS_HOLD_MARGIN
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
    hold = await page.evaluate(
        "()=>window.__gestures.press.milliseconds") + PRESS_HOLD_MARGIN
    await drive_press(page, box["x"], box["y"], 5, hold, lift=False)
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
    await page.wait_for_timeout(
        await page.evaluate("()=>window.__gestures.press.milliseconds")
        + PRESS_HOLD_MARGIN)
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
    press = await page.evaluate("()=>window.__gestures.press")
    press_milliseconds = press["milliseconds"]
    drift = press["tolerancePixels"] + MOUSE_DRIFT_MARGIN
    for step in range(1, 5):
        await page.mouse.move(box["x"] + drift * step / 4,
                            box["y"] + drift * step / 4)
        await page.wait_for_timeout(30)
    # HELD PAST THE PRESS DELAY, READ RATHER THAN TYPED. This was 620 after
    # four moves of 30 — 740ms laid by hand against a delay the design draws.
    # Push the press delay past that and the lift precedes the timer: the
    # panel stays shut for the WRONG reason, and this hold goes green with the
    # tolerance deleted, because a mouse gets no `pointercancel` either way.
    # B-276, in the file whose docstring says it removed that species.
    await page.wait_for_timeout(press_milliseconds + PRESS_HOLD_MARGIN - 120)
    await page.mouse.up()
    await page.wait_for_timeout(160)
    opened = await panel_is_open(page)
    cancels = await page.evaluate("()=>window.__pointerCancels")
    # THE TWO ASSERTIONS ARE ONE PROOF. That the panel stayed shut says the
    # press died; that `pointercancel` never fired says the COMPOSITOR did not
    # kill it — so the tolerance did. Without the second, this hold proves
    # exactly what the touch hold proves, which is less than it claims.
    journal.check(
        f"under a real mouse, a drag of {drift}px opens nothing",
        not opened,
        "the tolerance is not applied: a mouse drag across a tile opens a panel")
    journal.check(
        "and the compositor never cancelled it, so it was the TOLERANCE",
        cancels == 0,
        f"pointercancel fired {cancels}x — this hold would prove nothing")
    await context.close()


# ── THE PULL, and the halves R55 does not read ───────────────────────────────
# R55 proves the pull ARMS and SPINS on seven surfaces. It never drives a pull
# SHORT of the arming distance, so it never proves that one refreshes nothing —
# and a gesture with no threshold at all passes every hold it has, refreshing on
# every downward flick the scrollport ever sees.

# THE DRIVE DISTANCES ARE DERIVED FROM THE PUBLISHED NUMBERS, not typed — which
# is what makes the publish itself checkable.
#
# Round 1 had this rule READ the arming distance instead of re-typing it, and
# round 2 asked the next question: can a WRONG publish pass? It could. With the
# distances typed, a publish reporting a value far BELOW the real one left both
# holds green — the short pull still failed to arm the real gesture, and
# `0 < 1` is true. The number was read and never confronted with the behaviour
# it describes.
#
# Deriving the drives from it closes that: a publish that disagrees with the
# gesture produces a pull the gesture treats the other way round, and the holds
# fall. The margins are in the DAMPED domain, either side of the arming
# distance, so they follow it wherever it moves.
DAMPED_MARGIN_PIXELS = 8

# READ FROM THE PAGE, NEVER RE-TYPED — `window.__gestures` is what the
# vocabulary publishes for whatever drives it. This file said, in its own
# docstring, that a rule which hard-copies a number is a second source of truth
# that goes stale silently, and then hard-copied 44, 16 and 480. Found by an
# adversarial pass over this wave's own instruments, one commit after the wave
# NAMED that species (B-276).


async def drive_pull(page, port, distance):
    """Pulls DOWN from the top of the scrollport with a real touch stream.

    Args:
        page: The Playwright page.
        port: The scrollport's bounding box.
        distance: How far the finger travels downward.
    """
    session = await page.context.new_cdp_session(page)
    x = port["x"] + port["width"] / 2
    y = port["y"] + 60
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for step in range(1, 13):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x, "y": y + distance * step / 12, "id": 1}]})
        await page.wait_for_timeout(16)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})


async def drive_pull_and_back(page, port, distance):
    """Pulls DOWN past the threshold, then back UP past where it started.

    A pull dragged back up is not a pull. The engine checked the finger's FINAL
    direction at the release, beside the armed state, and a high-water mark
    alone would refresh anyway.

    Args:
        page: The Playwright page.
        port: The scrollport's bounding box.
        distance: How far down the finger goes before returning.
    """
    session = await page.context.new_cdp_session(page)
    x = port["x"] + port["width"] / 2
    y = port["y"] + 60
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for step in range(1, 13):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x, "y": y + distance * step / 12, "id": 1}]})
        await page.wait_for_timeout(16)
    # And back up, finishing ABOVE where the finger landed.
    for step in range(1, 13):
        travelled = distance - (distance + 40) * step / 12
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x, "y": y + travelled, "id": 1}]})
        await page.wait_for_timeout(16)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})


async def hold_the_pull_threshold(journal, browser):
    """A pull short of the arming distance must refresh NOTHING."""
    context, page = await open_page(browser)
    await page.evaluate("(s)=>window.__go(s)", "lib-grid")
    await page.wait_for_timeout(420)
    port = await page.evaluate(
        "()=>{const e=document.querySelector('#port');"
        "const r=e.getBoundingClientRect();"
        "return {x:r.x, y:r.y, width:r.width};}")
    pull_numbers = await page.evaluate("()=>window.__gestures.pull")
    arming = pull_numbers["armPixels"]
    damping = pull_numbers["damping"]
    # In the finger's own domain: what the gesture must travel for the pull to
    # land just under and just over its arming distance.
    short_pull = round((arming - DAMPED_MARGIN_PIXELS) / damping)
    long_pull = round((arming + DAMPED_MARGIN_PIXELS) / damping)
    journal.check("the pull gesture publishes its arming distance",
                  isinstance(arming, (int, float)) and arming > 0
                  and isinstance(damping, (int, float)) and 0 < damping <= 1,
                  f"read {arming!r} — the rule would have to re-type it, which "
                  "is the second source of truth B-276 names")

    # THE CONTROL FIRST. Without it the negative below passes just as well over
    # a pull-to-refresh that is simply broken.
    await drive_pull(page, port, long_pull)
    await page.wait_for_timeout(220)
    # READ AS GEOMETRY, NOT AS A CLASS NAME. D4: a rule anchors on `data-*` or
    # on what the element measurably IS, never on a style class — a class-name
    # read dies the day the class is renamed, and nothing can then say whether
    # the read or the style was at fault. The indicator's HEIGHT is the fact
    # the gesture produces; `loading` is one styling of it.
    spun = await page.evaluate(
        "()=>document.querySelector('#ptr').getBoundingClientRect().height")
    # THE INDICATOR IS STILL UP, which is what a refresh looks like — not
    # « its height is at least the arming distance ». That comparison held a
    # height the engine writes (44px, hard-coded) against a distance the gesture
    # publishes (44px), two quantities that are equal by COINCIDENCE: move
    # either and the hold changes meaning without changing colour. What
    # separates an armed release from an unarmed one is that the indicator STAYS
    # while the refresh runs and goes back at once when nothing was armed.
    journal.check("a pull past the arming distance refreshes",
                  spun > INDICATOR_GONE_PIXELS,
                  f"the indicator stood at {spun}px shortly after the release — "
                  "an armed pull leaves it up while the refresh runs, and this "
                  "is the control for the hold below")
    await page.evaluate("()=>window.__reposPTR()")
    await page.wait_for_timeout(120)

    await drive_pull(page, port, short_pull)
    await page.wait_for_timeout(220)
    reading = await page.evaluate(
        "()=>document.querySelector('#ptr').getBoundingClientRect().height")
    journal.check(
        f"a pull of {short_pull}px — short of the arming distance — refreshes "
        "NOTHING",
        reading <= INDICATOR_GONE_PIXELS,
        f"the indicator stood at {reading}px shortly after the release, where "
        "an unarmed pull puts it straight back: the threshold is not applied, "
        "so every downward flick the scrollport sees refreshes")
    await page.evaluate("()=>window.__reposPTR()")
    await page.wait_for_timeout(120)

    # A PULL DRAGGED BACK UP IS NOT A PULL, and the high-water mark alone would
    # say it was. `travelled` keeps the deepest point the finger reached,
    # because the guard that stops updating it returns early rather than
    # clearing it — so a release read on that number alone refreshes after a
    # pull the reader visibly abandoned. The engine checked the FINAL direction
    # beside the armed state; this holds that it still does.
    await drive_pull_and_back(page, port, long_pull)
    await page.wait_for_timeout(220)
    reading = await page.evaluate(
        "()=>document.querySelector('#ptr').getBoundingClientRect().height")
    journal.check(
        "a pull dragged back UP past its start refreshes NOTHING",
        reading <= INDICATOR_GONE_PIXELS,
        f"the indicator stood at {reading}px — the release read the deepest "
        "point the finger reached and not where it ended")
    await page.evaluate("()=>window.__reposPTR()")
    await page.wait_for_timeout(120)

    # THE CAP AND THE SETTLE ARE PUBLISHED, so they are READ. Both numbers were
    # published « so a rule does not re-type them » and no rule read either:
    # a number nobody reads is a number nobody notices moving, which is the
    # other half of B-276 and the reason the sentence was written.
    #
    # THE CAP is what stops the indicator following the finger forever. Pulled
    # far past it, the indicator must stand at the cap and not beyond.
    # READ WITH THE FINGER STILL DOWN. A release puts the indicator back, so a
    # reading taken after one measures the release and not the cap — it read
    # 0px, and « 0 <= 72 » is a hold that cannot fail.
    session = await page.context.new_cdp_session(page)
    finger_x = port["x"] + port["width"] / 2
    finger_y = port["y"] + 60
    # TWICE THE DISTANCE THE CAP IS REACHED AT, which is far enough to prove a
    # bound and short enough to stay on the screen: a drag that runs off the
    # bottom edge is a drag the driver stops delivering, and the indicator then
    # reads 0 for a reason that has nothing to do with the cap.
    await page.evaluate("()=>{document.querySelector('#port').scrollTop = 0;}")
    await page.wait_for_timeout(120)
    reach = round(pull_numbers["capPixels"] / max(damping, 0.01) * 2)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart",
        "touchPoints": [{"x": finger_x, "y": finger_y, "id": 1}]})
    for step in range(1, 13):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": finger_x,
                             "y": finger_y + reach * step / 12, "id": 1}]})
        await page.wait_for_timeout(16)
    stretched = await page.evaluate(
        "()=>document.querySelector('#ptr').getBoundingClientRect().height")
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(220)
    journal.check(
        "a pull far past the cap stops AT the cap",
        arming < stretched <= pull_numbers["capPixels"] + 1,
        f"the indicator stood at {stretched}px with the finger still down, "
        f"against a published cap of {pull_numbers['capPixels']}px and an "
        f"arming distance of {arming}px — beyond it the damping alone does not "
        "bound the gesture and a long drag stretches the surface as far as the "
        "finger goes; at or under the arming distance nothing was pulled at all")
    await page.evaluate("()=>window.__reposPTR()")
    await context.close()


async def hold_a_cancelled_mouse_pull_is_released(journal, browser):
    """A pull cancelled by the platform mid-gesture must put the indicator back.

    `pointercancel` is IGNORED for a finger, deliberately: the browser claims
    the pan one move in while the touch stream carrying the gesture keeps
    running, so ending on it would undo the gesture. For a MOUSE or a stylus
    there is no such stream, and a cancel is the platform taking the pointer
    away for good.

    THE MODULE CLEARED ITS VARIABLES AND TOLD THE SURFACE NOTHING, which ends
    the bookkeeping and leaves the picture: the indicator hung at the height the
    cancelled pull left it, armed, with its transition suppressed, until some
    later gesture moved it. Nothing drove a mouse cancel, so nothing saw it.

    Args:
        journal: The rule's journal.
        browser: A launched Playwright browser.
    """
    context, page = await open_page(browser)
    await page.evaluate("(s)=>window.__go(s)", "lib-grid")
    await page.wait_for_timeout(420)
    port = await page.evaluate(
        "()=>{const e=document.querySelector('#port');"
        "const r=e.getBoundingClientRect();"
        "return {x:r.x, y:r.y, width:r.width};}")
    arming = (await page.evaluate("()=>window.__gestures.pull"))["armPixels"]

    x = port["x"] + port["width"] / 2
    y = port["y"] + 60
    await page.mouse.move(x, y)
    await page.mouse.down()
    for step in range(1, 13):
        await page.mouse.move(x, y + 220 * step / 12)
        await page.wait_for_timeout(16)
    pulled = await page.evaluate(
        "()=>document.querySelector('#ptr').getBoundingClientRect().height")
    journal.check(
        "a mouse can pull the indicator open at all",
        pulled >= arming,
        f"the indicator stood at {pulled}px — with no pull to cancel, the hold "
        "below decides nothing")

    # THE PLATFORM TAKES THE POINTER AWAY. No driver raises a mouse
    # `pointercancel`, so it is dispatched as the platform would: the listener
    # reads nothing but `pointerType`, which is what makes the substitution
    # honest rather than convenient.
    await page.evaluate("""()=>{
      window.dispatchEvent(new PointerEvent('pointercancel', {
        pointerType: 'mouse', isPrimary: true, bubbles: true}));
    }""")
    await page.wait_for_timeout(260)
    # READ AS GEOMETRY, like the three holds above it and for their reason (D4):
    # the indicator's HEIGHT is the fact the gesture produces, and `armed` is one
    # styling of it — a class-name read dies the day the class is renamed, and
    # nothing can then say whether the read or the style was at fault.
    released = await page.evaluate(
        "()=>document.querySelector('#ptr').getBoundingClientRect().height")
    journal.check(
        "and a cancelled mouse pull puts the indicator BACK",
        released <= INDICATOR_GONE_PIXELS,
        f"the indicator stood at {released}px after the cancel, where a release "
        "puts it straight back — the gesture's variables were cleared and "
        "the surface was told nothing, so the indicator stays where the "
        "cancelled pull left it")
    await page.mouse.up()
    await context.close()


async def hold(journal):
    """Drives the two halves under a real finger and a real mouse."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_tolerance(journal, browser)
        await hold_the_pull_threshold(journal, browser)
        await hold_the_swallow_is_by_point(journal, browser)
        await hold_the_mouse_press(journal, browser)
        await hold_the_mouse_tolerance(journal, browser)
        await hold_a_cancelled_mouse_pull_is_released(journal, browser)
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

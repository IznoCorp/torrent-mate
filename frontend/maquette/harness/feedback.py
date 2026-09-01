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

# HOW LONG PAST THE PRESS TO READ. The press delay itself is READ from
# `window.__gestures`, never re-typed — the mark lives 200ms after the timer
# fires, so the read must land inside that window.
#
# THE FIRST VERSION HELD 740 AND READ NOTHING, which is this rule's own docstring
# warning come true in the rule that carries it: the mark had already expired and
# the read measured an absence exactly as a broken seam would. It failed loudly
# rather than passing, which is the only reason it was cheap.
PRESS_READ_MARGIN = 60


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
              // WHERE THE MARK LANDED, and not merely that one landed
              // somewhere. The observer watches the whole document, so
              // `feedback("commit", document.body)` satisfied every hold
              // below: the seam was called, on nothing the finger touched.
              // An acknowledgement is an answer TO A GESTURE, so the node it
              // is written on is half of what is being held.
              onTheTile: !!record.target.closest('[data-part="tile"]'),
              tag: record.target.tagName.toLowerCase(),
            });
      }).observe(document.documentElement, {subtree: true, attributes: true,
                                            attributeFilter: ['data-feedback']});
    }""")
    hold = await page.evaluate(
        "()=>window.__gestures.press.milliseconds") + PRESS_READ_MARGIN
    session = await page.context.new_cdp_session(page)
    x, y = box["x"], box["y"]
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for _ in range(int(hold / 60)):
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
    reading = await page.evaluate(
        "()=>window.__marks[0] || {marked: false, kind: null, onTheTile: false}")
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
    journal.check(
        f"and under `{motion}` the mark lands ON THE TILE THE FINGER HELD",
        bool(reading.get("onTheTile")),
        f"read {reading} — the acknowledgement was written somewhere else in "
        "the document. A seam called with the wrong element answers a gesture "
        "the reader did not make, and every other hold here would still pass")

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




# ── THE PRESS ACKNOWLEDGEMENT — a third moment, and the one nothing said ────
# A long press arms for 480ms before anything happens, and until L12 the
# interface was silent for that whole span. The tile now sinks and darkens while
# the press arms, and releases as the panel arrives.
#
# IT REPLACES THE POSTER'S FLIGHT, which the operator withdrew after watching it
# in slow motion. What the carry was FOR survives — binding the panel to the card
# that summoned it — played in place, moving nothing across the screen.
#
# THE THREE MOMENTS ARE HELD APART HERE BECAUSE THEY ARE EASY TO CONFLATE:
# `:active` is the finger being down at all, `[data-feedback]` is the
# acknowledgement AFTER a gesture commits, and `[data-pressing]` is the span
# between them. A rule that read only « something changed while the finger was
# down » would be satisfied by `:active` alone and would be green over an arming
# that says nothing.
ARMING_STATE = "lib-grid"
ARMING_TILE = '[data-part="tile"]'
# HOSTED IN A TRIPLE-QUOTED STRING so the selector needs no escaping.
# `check-markup-contracts` reads the harness as RAW TEXT, and a backslash where
# a quote is expected makes the selection invisible to it — the arm would count
# one fewer and say nothing about it.
READ_TILE = """()=>{
  const tile = document.querySelector('[data-part="tile"]');
  const style = getComputedStyle(tile);
  return {mark: tile.hasAttribute('data-pressing'),
          scale: style.scale, filter: style.filter,
          // THE MOMENT IS STAMPED IN THE PAGE, at the instant the mark is read
          // and on the same clock the mark is placed by. Stamped in Python
          // before the call, it was the moment the ROUND TRIP began: every
          // reading executed later than the moment recorded against it, by a
          // CDP hop. A sample recorded at 105ms of a 120ms settle then ran at
          // 118ms or past it under the suite's load, read a mark that was
          // legitimately there, and the rule fell announcing « the mark is
          // placed on pointerdown after all » — a false diagnosis of the very
          // defect it names, in the repair for a flake of the same species.
          at: window.__pressedAt
            ? performance.now() - window.__pressedAt : null};
}"""



async def hold_the_press_acknowledgement(journal, browser, motion):
    """Reads the tile before, during and after the arming of a long press."""
    context, page, box = await open_at_state(browser, motion)
    if not box:
        journal.check(f"a tile is drawn to press ({motion})", False, "absent")
        await context.close()
        return

    at_rest = await page.evaluate(READ_TILE)
    # THE PRESSED NODE IS CAPTURED BY REFERENCE, because the panel's arrival
    # REPLACES it. The library's draw is keyed on the store version, the panel
    # bumps it, and this very rule measured `isConnected === false` on the
    # pressed node one phase earlier. Re-querying `[data-part="tile"]` after
    # the lift therefore asked a BRAND NEW tile whether it was still pressed,
    # and a new tile never is: deleting the release left this hold green while
    # the detached node kept `data-pressing`, and on any surface React does not
    # redraw the tile would simply stay pressed.
    await page.evaluate(
        "(row)=>{window.__pressedNode = document.querySelector(row);}",
        ARMING_TILE)
    session = await page.context.new_cdp_session(page)
    x, y = box["x"], box["y"]
    # THE SETTLE IS READ, not assumed. The mark is placed AFTER the compositor's
    # settle so a flick beginning on a tile never lights it; the number is
    # published for that reason and no rule read it, which is the half of B-276
    # that is not a stale delay but an unread one. Held here: a tile is NOT
    # marked before the settle has passed.
    settle = await page.evaluate(
        "()=>window.__gestures.press.settleMilliseconds")
    # THE PAGE'S OWN CLOCK STARTS ON THE PAGE'S OWN `pointerdown`, which is the
    # same event the settle timer is armed by. Nothing in the harness can time
    # against that event from outside it.
    await page.evaluate("""()=>{
      window.__pressedAt = null;
      window.addEventListener('pointerdown', () => {
        if (window.__pressedAt === null) window.__pressedAt = performance.now();
      }, {capture: true});
    }""")
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    # SAMPLED ON EVERY STEP, and the two readings are CHOSEN from the series by
    # the moment each one lands rather than by a step number.
    #
    # It used to read one fixed step, and the settle read added 60ms of dead
    # time in front of it: under the suite's parallel load the fixed step then
    # drifted past the press delay and the mark had already gone — the rule fell
    # in the suite and passed alone, which is B-277's species arriving in the
    # rule this repair touched. A moment cannot drift out of a series that
    # records its own moments.
    # THE FIRST READINGS COME FAST, so that one of them lands well inside the
    # settle. At a flat 50ms cadence the first sample arrives around 50-70ms of
    # a 120ms settle, and the round trip alone can carry it past the 100ms
    # margin — measured: a recording run read NOTHING inside the window and the
    # hold fell saying the mark had been placed early. Failing loudly there is
    # the right direction and is still a false report; the cadence opens tight
    # and relaxes once the settle is behind it.
    samples = []
    for index in range(16):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove", "touchPoints": [{"x": x + 2, "y": y + 2, "id": 1}]})
        await page.wait_for_timeout(16 if index < 3 else 50)
        samples.append(await page.evaluate(READ_TILE))
    press_delay = await page.evaluate(
        "()=>window.__gestures.press.milliseconds")
    # A MARGIN ON BOTH BOUNDARIES, and the asymmetry that had one on the arming
    # window and none on the settle is what made this rule fall in the suite and
    # pass alone. A reading whose own moment sits within a frame of a boundary
    # decides nothing about which side of it the mark belongs to, so it is
    # discarded rather than classified.
    boundary = 20
    before_settle = [reading for reading in samples
                     if reading["at"] is not None
                     and reading["at"] < settle - boundary]
    arming_window = [reading for reading in samples
                     if reading["at"] is not None
                     and settle + 40 < reading["at"] < press_delay - 40]
    # THE PRECONDITION IS ITS OWN HOLD, so a run that sampled nothing inside the
    # settle says THAT rather than accusing the code of marking early — the two
    # readings are different findings and were one sentence.
    journal.check(
        f"under `{motion}`, the settle window WAS sampled",
        bool(before_settle),
        f"no reading landed inside the {settle}ms settle over "
        f"{[None if r['at'] is None else round(r['at']) for r in samples]} — "
        "the hold below would then read an absence")
    journal.check(
        f"under `{motion}`, the tile is NOT marked before the settle passes",
        not any(r["mark"] for r in before_settle),
        f"read {before_settle} strictly inside a {settle}ms settle — the mark "
        "is placed "
        "on `pointerdown` after all, which lights every flick that begins on a "
        "tile")
    journal.check(
        f"under `{motion}`, the arming window WAS sampled",
        bool(arming_window),
        f"no sample landed between {settle}ms and {press_delay}ms over "
        f"{[None if r['at'] is None else round(r['at']) for r in samples]} — "
        "the two holds below would then read an absence")
    arming = arming_window[-1] if arming_window else None
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(600)
    after = await page.evaluate("""()=>{
      const node = window.__pressedNode;
      if (!node) return {mark: null, filter: null, replaced: null};
      const style = getComputedStyle(node);
      return {mark: node.hasAttribute('data-pressing'),
              filter: style.filter,
              replaced: !node.isConnected};
    }""")

    journal.check(
        f"under `{motion}`, the tile is marked WHILE the press arms",
        bool(arming and arming["mark"]),
        f"read {arming} — the interface says nothing for the 480ms a press "
        "takes to arm")
    journal.check(
        f"and under `{motion}` it DARKENS — the acknowledgement is drawn",
        bool(arming) and arming["filter"] != at_rest["filter"],
        f"filter {at_rest['filter']} at rest and {arming['filter'] if arming else None} "
        "while arming — the mark lands and the stylesheet answers with nothing")
    journal.check(
        f"and under `{motion}` the PRESSED NODE ITSELF is released",
        after["mark"] is False,
        f"read {after} — the node that was pressed still carries the mark. It "
        "is read by reference rather than re-queried, because the panel's "
        "arrival replaces the tile and a fresh one is never pressed: "
        "re-querying asked the wrong node and answered « released » whatever "
        "the gesture did")

    if motion == "reduce":
        journal.check(
            "under `reduce`, the tile does NOT move — only the darkening",
            bool(arming) and arming["scale"] in ("none", "1"),
            f"scale {arming['scale'] if arming else None} — reduced motion is a "
            "designed state and this one moves anyway")
    else:
        journal.check(
            "under `no-preference`, the tile SINKS as well as darkening",
            bool(arming) and arming["scale"] not in ("none", "1"),
            f"scale {arming['scale'] if arming else None} — the acknowledgement "
            "is a darkening alone, which is the reduced state played to everyone")
    await context.close()




async def hold_a_scroll_is_never_acknowledged(journal, browser, motion):
    """A flick begun ON a tile must never light that tile's pressed state.

    D9's table refuses `onTouchStart` for pressed states for exactly this: it
    lights when the finger is starting a SCROLL, so a list flickers as it is
    scrolled past. The acknowledgement was written on the raw `pointerdown` and
    had the same defect — hidden under `no-preference` by a 450ms ramp, and plain
    under `reduce`, where the darkening lands instantly.

    Driven under BOTH preferences because the two hide it differently, and the
    `reduce` one is where a reader actually saw it.
    """
    context, page, box = await open_at_state(browser, motion)
    if not box:
        journal.check(f"a tile is drawn to flick ({motion})", False, "absent")
        await context.close()
        return

    session = await page.context.new_cdp_session(page)
    x, y = box["x"], box["y"]
    await page.evaluate(
        "()=>{window.__lit=0;window.__w=setInterval(()=>{"
        " if(document.querySelector('[data-pressing]')) window.__lit+=1;},8);}")
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    # A FLICK: away fast, which is what a scroll is. Three moves over ~50ms,
    # well past the 12px tolerance and inside the settle.
    for step in range(1, 4):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": x, "y": y - 30 * step, "id": 1}]})
        await page.wait_for_timeout(16)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(500)
    lit = await page.evaluate("()=>{clearInterval(window.__w);return window.__lit;}")

    journal.check(
        f"under `{motion}`, a flick begun on a tile never lights it",
        lit == 0,
        f"the pressed state was up for {lit} sample(s) during a scroll — a list "
        "flickers as it is scrolled past, which is the defect D9's table refuses "
        "`onTouchStart` for")
    await context.close()


async def hold(journal):
    """Drives the acknowledgement under both preferences, and the pressed state."""
    errors = []
    async with async_playwright() as play:
        browser = await play.chromium.launch(channel="chrome")
        await hold_the_acknowledgement(journal, browser, "no-preference")
        await hold_the_acknowledgement(journal, browser, "reduce")
        await hold_the_pressed_state(journal, browser)
        await hold_the_press_acknowledgement(journal, browser, "no-preference")
        await hold_the_press_acknowledgement(journal, browser, "reduce")
        await hold_a_scroll_is_never_acknowledged(journal, browser, "no-preference")
        await hold_a_scroll_is_never_acknowledged(journal, browser, "reduce")
        await browser.close()
    journal.summary(errors)


def main():
    """Runs the rule."""
    journal = Journal(
        "R113 — the gesture acknowledgement, under both motion preferences")
    asyncio.run(hold(journal))


if __name__ == "__main__":
    main()

"""R135 — a TAP opens the sheet, a LONG PRESS opens the panel (B-316).

THE OPERATOR'S RULING, reading (i): on Découvrir's poster tile and
on its deck card alike, a TAP opens the media sheet and a LONG PRESS opens the
suggestion panel — « Ajouter / Voir la fiche / Pas intéressé » — reusing the
gesture the library's rows already carry, never a second mechanism.

WHAT WAS WRONG. On the poster tile `data-panel="sug:N"` and `data-mediasheet`
sit on the SAME node; on the deck card the media verb is on the card's child.
The media SCREEN opened on all ten finger points measured, and the suggestion
panel was reachable by no finger at all.

**THIS RULE MEASURES RATHER THAN ASSUMES, and that distinction is the reason it
exists.** Reading the code says the panel SHOULD open: `panelUnderFinger`
resolves `[data-panel]` from the element itself and from a `.card`/`.sugwrap`
child, so it finds the tile's own node and the deck card's article; the press
arbitration then swallows the click the lift causes. Every step of that
reasoning is sound and the operator's finger disagrees with it. So nothing here
is held by what the source says — each hold drives a real touch and reads what
the interface did.

WHAT IT READS, on BOTH card kinds, and each fails differently:

  1. THE CARD IS THERE AND A FINGER REACHES IT — hit-tested at its centre, with
     the covering element named when it is not, because a press measured into
     a covered node measures nothing.
  2. A TAP OPENS THE MEDIA SHEET, and leaves no panel open. Both halves: a tap
     that opened the sheet AND raised the panel is the two gestures colliding,
     which is the defect wearing its other face.
  3. A LONG PRESS OPENS THE SUGGESTION PANEL — counted BY LABEL, because the
     ruling names the three actions and a count alone would pass over a panel
     offering the wrong ones.
  4. AND THE LONG PRESS DOES NOT ALSO OPEN THE SHEET. This is the hold that
     falls today: the click the lift causes must be swallowed, and the reading
     says which layer ended up on top when it is not.

A REAL TOUCH THROUGHOUT, over CDP. `page.touchscreen.tap` sends a touch with no
movement and no dwell, and a long press is a dwell by definition — a synthetic
tap cannot express the gesture under test, let alone the drift a real thumb has
while it holds still (the arbitration tolerates 12px and B-337 lives in that
tolerance).
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, PANEL_IN, SETTLED, open_page

from playwright.async_api import async_playwright

# THE TWO SURFACES THE RULING NAMES, and the element each draws a suggestion as.
# `data-part`, never a class: a class token in a rule dies the day the style is
# renamed and nothing can then say whether the anchor or the drawing was at
# fault (`check-markup-contracts` holds that at a hard zero).
SURFACES = [
    ("acq-discover-posters", '[data-part="tile"]', "the poster tile"),
    # THE CARD ON TOP, by its depth, and NOT the first in document order. The
    # pile draws three and reverses them, so `querySelector` answers the card
    # at the BOTTOM — covered by the two above it. Measured: hit-testing its
    # centre reported an `IMG` belonging to another card and the hold fell,
    # naming a defect in this rule rather than in the interface.
    ("acq-discover-deck", '[data-part="deck/card"][data-depth="0"]',
     "the deck card"),
]

# WHERE A FINGER MAY LAND ON IT, and whether anything covers that point.
AIM = """(selector)=>{
  const one = document.querySelector(selector);
  if (!one) return {found: false};
  const box = one.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, width: box.width, height: box.height,
          inside: box.top >= 0 && box.bottom <= window.innerHeight,
          covering: hit ? (hit.getAttribute('data-part') || hit.tagName) : null,
          reachable: !!hit && (hit === one || one.contains(hit)
                               || hit.closest(selector) === one)};}"""

# WHAT IS ON SCREEN AFTERWARDS. The panel by its own part and its open mark;
# the media screen by the part only IT draws. Read together in one evaluation,
# so the two answers describe the same instant.
AFTER = """()=>({
  panelOpen: document.querySelectorAll('[data-part="sheet"][data-open]').length > 0,
  actions: [...document.querySelectorAll('#sheetin [data-part="sheet/action"]')]
    .map((one) => (one.textContent || '').trim()),
  mediaScreen: !!document.querySelector('[data-part="media/add"], [data-part="media/trailer"]'),
})"""


async def settled_after_a_layer(page):
    """Waits until no closing scrim can still eat a touch.

    A CLOSED LAYER IS NOT INSTANTLY AN UNCOVERED PAGE. The scrim's visibility
    is transitioned with a DELAY: it reaches `opacity: 0` at once and keeps
    `visibility: visible` until the delay expires, so it is still a real
    element in the hit-test tree while the page looks, to the eye, entirely
    uncovered.

    IT NO LONGER SWALLOWS A TOUCH — the closed state carries
    `pointer-events-none`, and that repair is what makes the delay harmless
    rather than the reason a first tap does nothing. This wait is kept anyway,
    because a hold that hit-tests through a layer mid-departure is measuring a
    moment the reader never sees, and because the wait costs one predicate
    while trusting a transition costs a false reading.

    Args:
        page: The page.
    """
    await page.wait_for_function(
        """()=>[...document.querySelectorAll('[data-part="scrim"]')].every(
             (one) => getComputedStyle(one).visibility === 'hidden'
                      || getComputedStyle(one).opacity !== '0')""",
        timeout=3000)


async def finger(page, point, dwell, drift=0):
    """Puts one finger down, holds it, and lifts it.

    Args:
        page: The page.
        point: Where it goes down.
        dwell: How long it stays down, in milliseconds. A tap is short; a long
            press is longer than the arbitration's own threshold.
        drift: How far it wanders while held, in pixels. A real thumb is never
            still, and the arbitration tolerates 12px on purpose — a press
            driven perfectly still is a press only a mouse ever makes.
    """
    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": point[0], "y": point[1]}]})
    if drift:
        await page.wait_for_timeout(dwell // 2)
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove",
            "touchPoints": [{"x": point[0] + drift, "y": point[1] + drift}]})
        await page.wait_for_timeout(dwell - dwell // 2)
    else:
        await page.wait_for_timeout(dwell)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await session.detach()


# A TAP, and a HOLD longer than the arbitration's threshold. Named rather than
# spelled at the call sites, so the two gestures cannot drift apart between the
# four walks below.
TAP_MS = 60
HOLD_MS = 700
THUMB_DRIFT_PX = 4


async def main():
    journal = Journal("R135 — a tap opens the sheet, a long press opens the panel")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        for state, selector, what in SURFACES:
            # ── THE TAP ────────────────────────────────────────────────────
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            await settled_after_a_layer(page)
            aim = await page.evaluate(AIM, selector)
            journal.check(
                f"{what}: a finger reaches it — hit-tested at its centre, with "
                "the covering element named, because a press into a covered "
                "node measures nothing",
                aim.get("found") and aim.get("reachable"), str(aim))
            if not (aim.get("found") and aim.get("reachable")):
                continue

            await finger(page, (aim["x"], aim["y"]), TAP_MS)
            await page.wait_for_timeout(ACTED)
            after = await page.evaluate(AFTER)
            journal.check(
                f"{what}: a TAP opens the MEDIA SHEET and leaves no panel open "
                "— a tap that did both is the two gestures colliding",
                after["mediaScreen"] and not after["panelOpen"], str(after))

            # ── THE LONG PRESS ─────────────────────────────────────────────
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(SETTLED)
            await settled_after_a_layer(page)
            aim = await page.evaluate(AIM, selector)
            if not (aim.get("found") and aim.get("reachable")):
                journal.check(f"{what}: the card is still reachable for the "
                              "long press", False, str(aim))
                continue
            await finger(page, (aim["x"], aim["y"]), HOLD_MS, THUMB_DRIFT_PX)
            await page.wait_for_timeout(PANEL_IN)
            after = await page.evaluate(AFTER)

            journal.check(
                f"{what}: a LONG PRESS opens the SUGGESTION panel — its "
                "actions read BY LABEL, because a count alone passes over a "
                "panel offering the wrong ones",
                after["panelOpen"] and len(after["actions"]) >= 3,
                str(after["actions"]))
            journal.check(
                f"{what}: and the long press does NOT also open the media "
                "sheet — the click the lift causes must be swallowed",
                after["panelOpen"] and not after["mediaScreen"], str(after))

        journal.check("and no gesture raised an error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

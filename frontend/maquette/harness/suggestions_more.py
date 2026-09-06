"""R134 — asking for more suggestions ADDS some, and keeps what was thrown away.

« Charger 30 de plus », at the end of the pile. The engine answered it by
writing `{ sugGone: new Set(), sugOrder: null }` and re-rendering: it CLEARED
what the operator had dismissed and reshuffled the same reserve, then said
« Nouveau lot chargé — 30 suggestions de plus. » Nothing about that sentence was
true of what it did, and the one thing a feed owes its reader is that what they
threw away stays thrown away.

**THIS RULE IS RED AGAINST THE ENGINE WITH NO MUTATION NEEDED**, which is the
strongest form of « seen red first » and it is free here: the engine
un-dismisses, so the hold « what was dismissed stays dismissed » falls against
it exactly as it stands.

WHAT IT READS, and each fails differently:

  1. THE BUTTON IS DRAWN, AND A FINGER REACHES IT. Held by its own geometry —
     rectangle inside the viewport, uncovered at its centre, label read —
     because `[data-sugmore]` is reachable from NO named state and the oracle
     therefore cannot see it (B-352). A rule that cannot see the button it
     presses is measuring a click into empty space.
  2. THE RESERVE GROWS, by the number the message names.
  3. WHAT WAS DISMISSED STAYS DISMISSED. Every position thrown away before the
     press is still gone after it. This is the hold the engine fails.
  4. THE MESSAGE IS TRUE OF WHAT HAPPENED — the number it names is the number
     that arrived, not the number on the button. A page at the end of the
     reserve is smaller than a full one.
  5. AND PRESSING IT ON A SPENT RESERVE SAYS SO, rather than announcing a
     count of nothing.

THE SPENT PILE IS BUILT BY THIS RULE, not navigated to: no named state reaches
the end mark, and `engine/states.js` is grandfathered so one cannot be added
(B-352). The rule writes `sugGone` itself and lets the deck redraw.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ACTED, Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE DECK IS DRAWN as a pile of cards with an end mark behind it.
DISCOVER_STATE = "acq-discover"

# HOW MANY THE LAYER HOLDS FOR THE DECK, and what was thrown away. Read from
# the seam the deck itself indexes into, so the rule and the interface cannot
# disagree about how big the reserve is.
RESERVE = "()=>(window.__suggestions?.() || []).length"
GONE = "()=>[...(window.__store.read().state.sugGone || [])].sort((a,b)=>a-b)"

# SPENDING THE PILE, without navigating anywhere. Every position but the last
# few is thrown away, which is what a reader who has worked through the deck
# leaves behind — and it is the only way to reach the end mark, since no named
# state does (B-352).
SPEND = """()=>{
  const total = (window.__suggestions?.() || []).length;
  const gone = new Set();
  for (let at = 0; at < total; at += 1) gone.add(at);
  window.__store.write({sugMode: 'deck', sugGone: gone, sugOrder: null});
  return {total, gone: [...gone].length};}"""

# THE BUTTON, BY ITS OWN GEOMETRY. The oracle cannot see it — it is drawn only
# by `deckHTML` when the pile is spent, and no named state reaches that — so
# its DRAWING is held here: on screen, uncovered at its centre, and its label
# read back rather than assumed.
THE_BUTTON = """()=>{
  const one = document.querySelector('[data-sugmore]');
  if (!one) return {found: false};
  const box = one.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  return {found: true, x, y, width: box.width, height: box.height,
          label: (one.textContent || '').trim(),
          inside: box.top >= 0 && box.bottom <= window.innerHeight
                  && box.left >= 0 && box.right <= window.innerWidth,
          covering: hit ? (hit.className || hit.tagName) : null,
          reachable: !!hit && (hit === one || one.contains(hit))};}"""


async def finger_tap(page, point, dwell=60):
    """Puts one finger down and lifts it, with a dwell and no movement."""
    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": point[0], "y": point[1]}]})
    await page.wait_for_timeout(dwell)
    await session.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
    await session.detach()


async def press(page, journal, label):
    """Finds the button, holds its drawing, and taps it.

    Args:
        page: The page.
        journal: The journal to record the drawing holds in.
        label: What to call this press in the hold's own name.

    Returns:
        What the button looked like, or None when it was not drawn.
    """
    aim = await page.evaluate(THE_BUTTON)
    journal.check(
        f"{label}: the button is drawn, inside the viewport and uncovered at "
        "its centre — held by its own geometry, because no named state reaches "
        "it and the oracle cannot see it (B-352)",
        aim.get("found") and aim.get("inside") and aim.get("reachable"),
        str(aim))
    if not (aim.get("found") and aim.get("reachable")):
        return None
    await finger_tap(page, (aim["x"], aim["y"]))
    await page.wait_for_timeout(ACTED)
    return aim


async def main():
    journal = Journal("R134 — more suggestions arrive, and what was thrown away stays thrown away")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", DISCOVER_STATE)
        await page.wait_for_timeout(SETTLED)

        spent = await page.evaluate(SPEND)
        await page.wait_for_timeout(SETTLED)
        journal.check(
            "the reserve is loaded and the rule can spend it — the end mark is "
            "reachable from no named state, so this walk builds it",
            spent["total"] > 0, str(spent))
        if not spent["total"]:
            await context.close()
            await browser.close()
            journal.summary()
            return

        before_reserve = await page.evaluate(RESERVE)
        before_gone = await page.evaluate(GONE)

        # ── THE FIRST PRESS: it must ADD ───────────────────────────────────
        aim = await press(page, journal, "spent pile")
        if aim is None:
            await context.close()
            await browser.close()
            journal.summary()
            return

        after_reserve = await page.evaluate(RESERVE)
        after_gone = await page.evaluate(GONE)
        message = await page.evaluate("()=>window.__toast?.read()?.message?.message || ''")

        journal.check(
            "the reserve GREW — the press asks the layer for more and appends "
            "what it answers, rather than reshuffling what was already there",
            after_reserve > before_reserve,
            f"{before_reserve} → {after_reserve}")

        journal.check(
            "and WHAT WAS DISMISSED STAYS DISMISSED — every position thrown "
            "away before the press is still gone after it. The engine cleared "
            "them, which is why this rule is red against it with no mutation",
            set(before_gone).issubset(set(after_gone)),
            f"{len(before_gone)} dismissed before, {len(after_gone)} after; "
            f"lost {sorted(set(before_gone) - set(after_gone))[:8]}")

        arrived = after_reserve - before_reserve
        journal.check(
            "and the MESSAGE names the number that ARRIVED, not the number on "
            "the button — a page at the end of the reserve is smaller than a "
            "full one",
            str(arrived) in message,
            f"{arrived} arrived, message « {message} »")

        # ── THE SECOND PRESS: the reserve is spent, and it says so ─────────
        spent_again = await page.evaluate(SPEND)
        await page.wait_for_timeout(SETTLED)
        journal.check("the grown reserve can be spent in turn",
                      spent_again["total"] == after_reserve, str(spent_again))
        aim = await press(page, journal, "spent again")
        if aim is None:
            await context.close()
            await browser.close()
            journal.summary()
            return

        exhausted_reserve = await page.evaluate(RESERVE)
        exhausted_message = await page.evaluate(
            "()=>window.__toast?.read()?.message?.message || ''")
        journal.check(
            "pressing it on a SPENT reserve adds nothing and SAYS so, rather "
            "than announcing a count of nothing",
            exhausted_reserve == after_reserve
            and str(after_reserve) in exhausted_message,
            f"{after_reserve} → {exhausted_reserve}, "
            f"message « {exhausted_message} »")

        journal.check("and no press raised an error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())

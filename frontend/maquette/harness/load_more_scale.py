"""R136 — « charger plus » is drawn at the footer's scale, not at the screen's.

The operator reported the button too big (B-315 a). It wore `.btnprimary`, the
action-button system — one scale shared with every primary action in the
product — and at the foot of a spent pile that reads as the screen's main path
when it is an offer to carry on reading.

**THIS RULE IS RED AGAINST A BUILD THAT STILL DRAWS THE OLD BUTTON WITH NO
MUTATION NEEDED**, which is the cheapest proof a rule bites: two of its holds
compare the rendered size to a step of the type scale, and the action-button
system sits on a different step.

WHAT IT READS, and each fails differently:

  1. THE BUTTON IS DRAWN, AND A FINGER REACHES IT. Held by its own geometry —
     rectangle inside the viewport, uncovered at its centre — because
     `[data-sugmore]` is reachable from NO named state and the oracle therefore
     cannot see it (B-352). A rule measuring a control nobody can reach is
     measuring nothing.
  2. ITS TYPE IS THE FOOTER'S STEP, read as the step and not as a pixel count.
  3. AND IT IS NOT THE ACTION-BUTTON SYSTEM'S STEP, which is the defect named:
     the two steps are one apart on the scale, so a rule that only asserted
     « small » would pass the button it was written against.
  4. ITS BOX IS THE FOOTER'S BOX — the padding step the footer's actions carry.

NO PIXEL IS TYPED IN THIS FILE, and that is the whole method. A size written
here would be a second source of truth for the scale: change the token and the
rule would keep asserting the old number while the interface moved. Every
comparison resolves the token THROUGH THE PAGE — a probe element wearing
`font-size: var(--text-N)` is measured by the same engine that measures the
button — so the rule reads « the same step », never « 12 pixels ».

THE SPENT PILE IS BUILT BY THIS RULE, not navigated to: no named state reaches
the end mark, and `engine/states.js` is grandfathered so one cannot be added
(B-352). The rule writes `sugGone` itself and lets the deck redraw.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal, SETTLED, open_page

from playwright.async_api import async_playwright

# WHERE THE DECK IS DRAWN as a pile of cards with an end mark behind it.
DISCOVER_STATE = "acq-discover"

# LEAVING THE DECK, so that coming back REBUILDS the pile, and SPENDING it.
# Two evaluations and not one: the deck branch refuses to rewrite a pile that
# is already drawn, and two `write` calls inside a single task are batched into
# one commit, so the interface never renders the mode it was asked to leave.
LEAVE_DECK = """()=>window.__store.write({sugMode: 'poster'})"""

SPEND = """()=>{
  const total = (window.__suggestions?.() || []).length;
  const gone = new Set();
  for (let at = 0; at < total; at += 1) gone.add(at);
  window.__store.write({sugMode: 'deck', sugGone: gone, sugOrder: null});
  return {total, gone: [...gone].length};}"""

# THE SCALE, RESOLVED BY THE PAGE ITSELF. A probe wearing the token is laid
# out by the same engine that lays out the button, so the two figures are
# comparable without either being written down here. The probe is positioned
# out of the way and removed before anything else is measured — an element left
# in the document would be a control the next rule finds and cannot explain.
#
# `paddingTop` is read rather than the shorthand: the shorthand is not
# resolved to pixels by `getComputedStyle` on every engine, and a rule that
# compares two strings instead of two lengths agrees with any spelling.
STEP = """(token)=>{
  const probe = document.createElement('div');
  probe.style.cssText =
    'position:fixed;left:-9999px;top:0;font-size:var(' + token + ');' +
    'padding:var(' + token + ');';
  document.body.appendChild(probe);
  const seen = getComputedStyle(probe);
  const read = {fontSize: parseFloat(seen.fontSize),
                padding: parseFloat(seen.paddingTop)};
  probe.remove();
  return read;}"""

# THE BUTTON: where it is, whether a finger reaches it, and how it is set.
THE_BUTTON = """()=>{
  const one = document.querySelector('[data-sugmore]');
  if (!one) return {found: false};
  const box = one.getBoundingClientRect();
  const x = box.left + box.width / 2;
  const y = box.top + box.height / 2;
  const hit = document.elementFromPoint(x, y);
  const seen = getComputedStyle(one);
  return {found: true, width: box.width, height: box.height,
          fontSize: parseFloat(seen.fontSize),
          padding: parseFloat(seen.paddingTop),
          label: (one.textContent || '').trim(),
          inside: box.top >= 0 && box.bottom <= window.innerHeight
                  && box.left >= 0 && box.right <= window.innerWidth,
          reachable: !!hit && (hit === one || one.contains(hit))};}"""


async def main():
    journal = Journal("R136 — « charger plus » is drawn at the footer's scale")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        await page.evaluate("(id)=>window.__go(id)", DISCOVER_STATE)
        await page.wait_for_timeout(SETTLED)

        await page.evaluate(LEAVE_DECK)
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

        seen = await page.evaluate(THE_BUTTON)
        journal.check(
            "the button is drawn, inside the viewport and uncovered at its "
            "centre — held by its own geometry, because no named state reaches "
            "it and the oracle cannot see it (B-352)",
            seen.get("found") and seen.get("inside") and seen.get("reachable"),
            str(seen))
        if not seen.get("found"):
            await context.close()
            await browser.close()
            journal.summary()
            return

        footer_step = await page.evaluate(STEP, "--text-3")
        screen_step = await page.evaluate(STEP, "--text-4")
        footer_box = await page.evaluate(STEP, "--spacing-4")

        journal.check(
            "its type is the FOOTER's step of the scale, resolved by the page "
            "rather than written down here",
            seen["fontSize"] == footer_step["fontSize"],
            f"button {seen['fontSize']}, the step resolves to "
            f"{footer_step['fontSize']}")

        journal.check(
            "and it is NOT the action-button system's step — the defect the "
            "operator named. The two steps are one apart, so « it looks small » "
            "would have passed the button this rule was written against",
            seen["fontSize"] != screen_step["fontSize"],
            f"button {seen['fontSize']}, the screen's step resolves to "
            f"{screen_step['fontSize']}")

        journal.check(
            "its box is the footer's box: the padding step a footer's actions "
            "carry, not the taller one the screen's actions carry",
            seen["padding"] == footer_box["padding"],
            f"button {seen['padding']}, the step resolves to "
            f"{footer_box['padding']}")

        journal.check("and drawing it raised no error", not errors, str(errors))

        await context.close()
        await browser.close()
    journal.summary()


asyncio.run(main())

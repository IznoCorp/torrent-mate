"""R81 — what an assistive technology is told, and an audit cannot see.

Three things live here, and they share one property: `a11y.py` cannot see any
of them. Focus MOVING, a surface saying it is BUSY, and an error ANNOUNCING
itself are facts about a sequence, or about a state the audit is not driving.

WHY A RULE AND NOT THE ACCESSIBILITY AUDIT. `a11y.py` reads the markup of ONE
MOMENT. Focus management is a SEQUENCE: something was focused, a layer opened,
focus moved inside it, the rest of the frame stopped being reachable, the layer
closed, and focus went back where it came from. No static audit can observe any
of that, so the two instruments measure different things and neither replaces
the other.

WHAT FAILS WHEN THIS IS ABSENT, and each half fails on its own:

  · a layer that opens without taking focus leaves a keyboard on the page
    behind it — Tab walks a list the reader cannot see, and a screen reader
    keeps announcing a surface the interface has covered;
  · a layer that closes without GIVING focus back drops the caret at the top of
    the document, and the reader starts again.

THE BACKGROUND IS CHECKED BY `inert`, NOT BY `aria-hidden`. `aria-hidden` hides
a subtree from a screen reader and leaves every control in it tabbable, which is
worse than either half alone: the reader tabs into something no longer
announced.
"""
import asyncio
import sys

from common import BAR, Journal, open_page
from playwright.async_api import async_playwright

# One entry per layer this rule drives: the control that opens it, the layer's
# root, and a short name for the report.
LAYERS = (
    ("drawer", '[data-drawer="1"]', "#drawer"),
    ("sheet", '[data-sheet="utilisateur"]', "#sheet"),
)

# Where the tab order must stop while a layer is up. `#port` is the main region
# behind every layer; if it is still reachable, so is the whole page.
BACKGROUND = "#port"

FOCUS_STATE = """([layer, background])=>{
  const root = document.querySelector(layer);
  const behind = document.querySelector(background);
  const active = document.activeElement;
  return {
    open: Boolean(root && root.hasAttribute('data-open')),
    inside: Boolean(root && active && root.contains(active)),
    active: active ? (active.id || active.className || active.tagName) : null,
    backgroundInert: Boolean(behind && behind.hasAttribute('inert')),
  };}"""

# The error surfaces of one state, and how many of them announce. Hosted in a
# triple-quoted string on purpose: `check-markup-contracts.py` reads this file
# as TEXT to pair every `data-*` a rule selects with the markup that emits it,
# and an escaped quote hides the selection from it — the arm would count one
# fewer and say nothing.
SURFACES = """()=>{
  const all = [...document.querySelectorAll('[data-part="surface-error"]')];
  return [all.length,
    all.filter((node)=>node.getAttribute('role') === 'alert').length];}"""

TRIGGER_HAS_FOCUS = """(selector)=>{
  const trigger = document.querySelector(selector);
  return Boolean(trigger && document.activeElement === trigger);}"""


async def main():
    journal = Journal("R81 — focus enters a layer, and the interface says what it is doing")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        context, page = await open_page(browser)

        for name, opener, layer in LAYERS:
            await page.click(opener)
            await page.wait_for_timeout(400)
            opened = await page.evaluate(FOCUS_STATE, [layer, BACKGROUND])
            journal.check(
                f"opening the {name} moves focus into it",
                opened["open"] and opened["inside"], str(opened))
            journal.check(
                f"opening the {name} takes the background out of the tab order",
                opened["backgroundInert"],
                f"{BACKGROUND} inert: {opened['backgroundInert']}")

            await page.keyboard.press("Escape")
            await page.wait_for_timeout(400)
            closed = await page.evaluate(FOCUS_STATE, [layer, BACKGROUND])
            journal.check(
                f"Escape closes the {name}",
                not closed["open"], str(closed))
            journal.check(
                f"closing the {name} gives the background back",
                not closed["backgroundInert"],
                f"{BACKGROUND} inert: {closed['backgroundInert']}")
            journal.check(
                f"closing the {name} returns focus to the control that opened it",
                await page.evaluate(TRIGGER_HAS_FOCUS, opener),
                f"active: {closed['active']}")

        # THE SKIP LINK, on a FRESH PAGE, which is also how a reader meets it.
        #
        # Not on the page above, and the reason is a real property of browsers
        # rather than tidiness: the sequential focus navigation starting point
        # is set by the last CLICK, and `blur()` does not move it. After the
        # layer holds — which deliberately leave focus on the control that
        # opened them — Tab resumes after the avatar, so the first version of
        # this hold measured the fourth stop and reported the skip link
        # missing. A fresh page has no starting point but the document's.
        fresh_context, fresh = await open_page(browser)
        await fresh.keyboard.press("Tab")
        await fresh.wait_for_timeout(150)
        first = await fresh.evaluate(
            "()=>document.activeElement?.className || ''")
        journal.check(
            "the first stop of the tab order is the skip link",
            "skip-link" in first, f"active: {first!r}")
        await fresh.keyboard.press("Enter")
        await fresh.wait_for_timeout(250)
        landed = await fresh.evaluate(
            "()=>document.activeElement?.id || ''")
        journal.check(
            "following the skip link moves FOCUS to the main region, not only "
            "the scroll position",
            landed == "port", f"active: {landed!r}")
        await fresh_context.close()

        # WHAT THE INTERFACE SAYS WHILE IT WORKS, here for the same reason as
        # the rest: an audit reads a moment, and « busy » is a moment it is not
        # driving.
        #
        # The busy mark is set in ONE place — the page host, the only thing that
        # knows every page's phase. Marked page by page it would be eight call
        # sites, and the eighth would be forgotten.
        await page.evaluate("(id)=>window.__go(id)", "lib-loading")
        await page.wait_for_timeout(400)
        journal.check(
            "a page that is loading says so",
            await page.evaluate(
                "()=>document.querySelector('#port')?.getAttribute('aria-busy')"
            ) == "true",
            "aria-busy while loading")
        await page.evaluate("(id)=>window.__go(id)", "lib-grid")
        await page.wait_for_timeout(400)
        journal.check(
            "and stops saying so once it has loaded",
            await page.evaluate(
                "()=>document.querySelector('#port')?.hasAttribute('aria-busy')"
            ) is False,
            "aria-busy cleared")

        # EVERY error surface announces, over EVERY state that renders one.
        #
        # The shape is repeated at nine call sites across six files, which is
        # exactly where the ninth gets forgotten — so this drives every named
        # state whose id says error and sums what it finds. A first version of
        # this hold drove one state, found one surface and called that a count:
        # a hold that samples and reads like a census is worse than no hold,
        # because it is believed.
        seen, announced = 0, 0
        for state in [s for s in await page.evaluate("()=>window.__states()")
                      if "error" in s]:
            await page.evaluate("(id)=>window.__go(id)", state)
            await page.wait_for_timeout(300)
            found = await page.evaluate(SURFACES)
            seen += found[0]
            announced += found[1]
        journal.check(
            "every error surface reaches a listener, not only a reader",
            seen > 0 and seen == announced,
            f"{announced} of {seen} surface(s) announce, over the error states")

        await context.close()
        await browser.close()
    print(BAR)
    journal.summary()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)

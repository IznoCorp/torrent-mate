"""R190 — Back from a screen opened from a panel brings the panel back, and the return is DRAWN.

B-275's own reading, and § 16's mirror. A reader long-presses a tile, the panel
rises, « Voir la fiche » opens the media screen and the panel is captured
LEAVING — `::view-transition-old(leaving-panel)` plays `panel-down` (R115). The
ladder keeps the panel's entry under the screen's, so one Back lands on it and
the panel is put back. This rule holds what that Back SHOWS.

THE TWO HALVES, and why neither is enough alone:

  1. the panel is back — `#sheet[data-open]` present, and the address names a
     panel again. Without it the return has no subject: there is nothing to
     draw coming back.
  2. its return is drawn — `::view-transition-new(leaving-panel)` runs
     `panel-down` IN REVERSE, the departure's own curve read backwards. Read by
     the ANIMATION'S NAME and its DIRECTION on that pseudo-element, never by
     « a view-transition pseudo-element animated »: every one of them carries
     the browser's own cross-fade by default, so that sentence is true with the
     reverse deleted outright.

AND UNDER `prefers-reduced-motion: reduce` the panel still comes back and
NOTHING moves: no `leaving-panel` animation runs. The reduced state is a drawn
state, read like the other.

WHAT IT DOES NOT HOLD: the ladder's counts, which are R188's, and the departure,
which is R115's (`transition.py`), unchanged.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Journal  # noqa: E402
from transition import FROM_STATE, TILE, open_page_with  # noqa: E402

from playwright.async_api import async_playwright  # noqa: E402

journal = Journal("R190 — the panel's return is drawn (B-275)")

# Every running view-transition animation, by pseudo-element, name and
# direction, sampled every 8 ms from before the Back until it has settled.
WATCH = """()=>{
  window.__seen = new Set();
  window.__watch = setInterval(() => {
    for (const animation of document.getAnimations()) {
      const pseudo = animation.effect && animation.effect.pseudoElement;
      if (!pseudo || !pseudo.includes('view-transition')) continue;
      const timing = animation.effect.getComputedTiming();
      window.__seen.add(pseudo + ':' + (animation.animationName || '?')
        + ':' + (timing.direction || 'normal'));
    }
  }, 8);
}"""

READ = """()=>({open: !!document.querySelector('#sheet')?.hasAttribute('data-open'),
               screen: !!document.querySelector('[data-part="screen"][data-open]'),
               address: location.pathname + location.search})"""


async def walk_back_from_the_sheet(browser, motion):
    """Opens the panel, leaves it for the media screen, steps Back and reads.

    Args:
        browser: A launched Playwright browser.
        motion: `"no-preference"` or `"reduce"`.

    Returns:
        The reading after the Back, and the animations seen during it — or
        None when the walk could not reach the media screen, said as a check.
    """
    context, page = await open_page_with(browser, motion)
    await page.evaluate("(s)=>window.__go(s)", FROM_STATE)
    await page.wait_for_timeout(600)
    box = await page.evaluate(
        "(sel)=>{const r=document.querySelector(sel).getBoundingClientRect();"
        " return {x:r.x + r.width/2, y:r.y + r.height/2};}", TILE)
    session = await page.context.new_cdp_session(page)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": box["x"], "y": box["y"], "id": 1}]})
    await page.wait_for_timeout(700)
    await session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(600)
    leave = await page.query_selector('#sheet [data-mediasheet]')
    panel = await page.evaluate(READ)
    if not (panel["open"] and leave):
        journal.check(f"[{motion}] a long press opens a panel offering the media screen",
                      False, f"{panel} leave={leave is not None}")
        await context.close()
        return None
    await leave.click()
    await page.wait_for_timeout(1200)
    arrived = await page.evaluate(READ)
    journal.check(f"[{motion}] « Voir la fiche » reaches the media screen, the panel gone",
                  arrived["screen"] and not arrived["open"], f"{arrived}")

    await page.evaluate(WATCH)
    await page.go_back()
    await page.wait_for_timeout(1200)
    seen = await page.evaluate("()=>{clearInterval(window.__watch); return [...window.__seen];}")
    back = await page.evaluate(READ)
    await context.close()
    return back, sorted(seen)


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")

        walked = await walk_back_from_the_sheet(browser, "no-preference")
        if walked:
            back, seen = walked
            # B-275, read first and printed at once: with no panel back, the
            # drawing below has no subject and its fall would say nothing new.
            journal.check(
                "one Back from the media screen brings the panel back (B-275)",
                back["open"] and not back["screen"] and "panel=" in back["address"],
                f"{back}")
            journal.check(
                "and its return is DRAWN — `new(leaving-panel)` plays `panel-down` in reverse",
                any(name.startswith("::view-transition-new(leaving-panel):panel-down:reverse")
                    for name in seen),
                f"pseudo-elements seen: {seen}")

        walked = await walk_back_from_the_sheet(browser, "reduce")
        if walked:
            back, seen = walked
            journal.check(
                "[reduce] the panel still comes back",
                back["open"] and not back["screen"], f"{back}")
            journal.check(
                "[reduce] and nothing about `leaving-panel` moves",
                not any("leaving-panel" in name for name in seen),
                f"pseudo-elements seen: {seen}")

        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

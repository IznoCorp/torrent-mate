"""R531 — Découvrir on a phone: the pile ends above the bottom bar, every time.

THE DEFECT. The deck's top card ended at 762 px or, on the same state driven the
same way, at 820 px — under the bottom bar, whose top is at 787 px, so the end of
the card's reason was cut. The pile's height is measured (`mountDeck`) against
the scroller's reserve for the bar, `--tm-bottom-bar-h`, and a `ResizeObserver`
publishes that reserve AFTER the bar changes: a bar that goes and comes back (the
account read again) left the reserve at 0 px while the pile was measured, and
nothing measured it again once the reserve landed.

WHAT IS READ, on a 390 × 844 phone:

  1. each of the deck's states, driven DRIVES times in a fresh page under an
     emulated CPU throttle (CDP, never real load): the top card ends above the
     bar, and no further above it than ROOM — a pile shrunk to its floor would
     end above the bar too;
  2. THE RACE'S OTHER ORDER, forced: the bar grows under a standing pile, as a
     phone's safe area does, so the reserve is published after the measure. The
     pile follows it, and follows it back. This one does not depend on timing.

At 1280 × 800 there is no bottom bar: the pile ends inside the window.
"""
import asyncio

from common import PHONE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

# The deck's two states a finger reaches with no rejection, and how often each is driven.
STATES = ("discover-deck", "discover-deck-passed")
DRIVES = 8

# How much slower the emulated processor runs. SLIGHTLY, on purpose: on the code
# before this rule, 3 of 32 drives were cut at 1.2, none of 32 at 2 nor at 3, and
# none of 16 at 4 nor at 6 — a slow page redraws once more after the reserve has
# landed, and the race hides. The drives are a sample, and may all pass on the
# defective code; the forced order below is what fails on it.
THROTTLE = 1.2

# The most room, in pixels, between the top card's foot and the bar's top.
ROOM = 40

# What a phone's safe area adds under the bar.
SAFE_AREA = 34

# Long enough for the state's own gesture (300 ms) and the card's flight (440 ms).
GESTURE = 1500

READ = """() => {
  const card = document.querySelector('[data-part="deck/card"][data-depth="0"]');
  const bar = document.querySelector('[data-part="shell/tab-bar"]');
  if (!card || !bar) return null;
  const c = card.getBoundingClientRect(), b = bar.getBoundingClientRect();
  return {bottom: Math.round(c.bottom), bar: Math.round(b.top), height: Math.round(c.height)};
}"""

# THE BAR'S HEIGHT, NOT ITS PADDING: the publisher's observer watches the content box.
GROW = """(extra) => {
  const bar = document.querySelector('[data-part="shell/tab-bar"]');
  bar.style.height = '';
  if (extra) bar.style.height = (bar.getBoundingClientRect().height + extra) + 'px';
}"""

DESKTOP = {**PHONE, "viewport": {"width": 1280, "height": 800}, "is_mobile": False, "has_touch": False,
           "device_scale_factor": 1}
OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"

PILE = """() => {
  const pile = document.querySelector('[data-part="deck"]');
  if (!pile) return null;
  const p = pile.getBoundingClientRect();
  return {top: Math.round(p.top), bottom: Math.round(p.bottom), width: Math.round(p.width),
          window: window.innerHeight};
}"""


def clear_of_the_bar(seen):
    """Whether the top card ends above the bar, with no more than ROOM under it.

    Args:
        seen: A READ answer.

    Returns:
        The verdict.
    """
    return seen is not None and 0 <= seen["bar"] - seen["bottom"] <= ROOM


async def main():
    """Drives the deck's states on a phone, forces the late reserve, then reads the desktop."""
    journal = Journal("R531 — Découvrir on a phone: the pile ends above the bottom bar, every time")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())

        for state in STATES:
            cut = []
            for _ in range(DRIVES):
                context, page = await open_page(browser)
                page.on("pageerror", lambda error: errors.append(str(error)))
                session = await context.new_cdp_session(page)
                await session.send("Emulation.setCPUThrottlingRate", {"rate": THROTTLE})
                seen = await read_at(page, state, READ, wait=GESTURE)
                if not clear_of_the_bar(seen):
                    cut.append(seen)
                await context.close()
            journal.check(f"{state}: the top card ends above the bar on each of {DRIVES} throttled drives",
                          not cut, f"{len(cut)} of {DRIVES} not: {cut[:2]}")

        context, page = await open_page(browser)
        page.on("pageerror", lambda error: errors.append(str(error)))
        for state in STATES:
            before = await read_at(page, state, READ, wait=GESTURE)
            await page.evaluate(GROW, SAFE_AREA)
            await page.wait_for_timeout(SETTLED)
            grown = await page.evaluate(READ)
            await page.evaluate(GROW, 0)
            await page.wait_for_timeout(SETTLED)
            back = await page.evaluate(READ)
            journal.check(f"{state}: the bar grown under a standing pile, the pile ends above it",
                          clear_of_the_bar(grown) and grown["bar"] < before["bar"],
                          f"before {before} · grown {grown}")
            journal.check(f"{state}: the bar back to its height, the pile takes the room back",
                          clear_of_the_bar(back) and back == before, f"before {before} · back {back}")
        await context.close()

        context, page = await open_page(browser, **DESKTOP)
        await context.add_init_script(OUT_OF_FRAME)
        await page.reload(wait_until="load")
        await page.evaluate("()=>window.__loadingDone?.()")
        page.on("pageerror", lambda error: errors.append(str(error)))
        for state in STATES:
            seen = await read_at(page, state, PILE, wait=GESTURE)
            journal.check(f"1280 × 800, {state}: the pile ends inside the window",
                          seen is not None and 0 <= seen["window"] - seen["bottom"] <= ROOM, f"{seen}")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

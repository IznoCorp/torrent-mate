"""R235 — a pull to refresh begun ON a card refreshes, on every list that draws cards.

The operator pulls with his thumb on the list, and the list is cards. The pull
gesture refuses a drag that belongs to something else, and it used to count a
swipe row among those things — so on « Suivis » and on the Médiathèque's list,
whose rows are all swipe rows, a thumb on the list started no pull at all. The
swipe claims a drag only when it goes to the side, and the pull only when it
goes down from the top, so no drag is ever claimed by both.

On each state below, a real touch starts at the centre of the first card and
travels down past the arming distance:

1. while the finger is held, the pull indicator is open — the pull is armed;
2. released, the indicator's wheel turns — the re-read has started.

« En cours » and « À traiter » draw plain cards and are read beside the two
lists of swipe rows, so a repair that only moved the fault would be seen.

Red before the move: on « Suivis » and on the Médiathèque's list, the indicator
never opens.
"""
import asyncio

from common import SETTLED, Journal, open_page, browser_channel, chrome_launch_args
from playwright.async_api import async_playwright

STATES = ("acq-follows-list", "acq-now-loaded", "acq-todo-loaded", "lib-list", "lib-grid")

# How long the finger stays down once the pull has travelled.
HELD_MILLISECONDS = 300

# Where the first card (or gallery tile) is, the scrollport's own top, and the pull's numbers.
GEOMETRY = """() => {
  const port = document.querySelector('#port');
  const card = document.querySelector('#view [data-part="swipe"], #view [data-part="card"], #view [data-part="tile"]');
  if (!card) return null;
  const box = card.getBoundingClientRect();
  return {x: box.x + box.width / 2, y: box.y + Math.min(box.height / 2, 40),
          scrollTop: port.scrollTop, numbers: window.__gestures?.pull ?? null};
}"""

# Samples the indicator every frame: its tallest height while the finger is
# down, and whether its wheel turns once the finger is up.
WATCH = """() => {
  const indicator = document.querySelector('#ptr');
  const wheel = indicator.firstElementChild;
  const record = {held: 0, released: false, spun: false, done: false};
  window.__pullOnCard = record;
  window.__pullOnCardRelease = () => { record.released = true; };
  const start = performance.now();
  const tick = () => {
    if (!record.released) record.held = Math.max(record.held, indicator.getBoundingClientRect().height);
    else if (getComputedStyle(wheel).animationName !== 'none') record.spun = true;
    if (performance.now() - start < 4000 && !record.spun) requestAnimationFrame(tick);
    else record.done = true;
  };
  requestAnimationFrame(tick);
}"""


async def pull_from_the_card(page):
    """Pulls down from the first card with a real touch, holds, and releases.

    Args:
        page: The Playwright page, on the state to pull.

    Returns:
        The geometry read before the pull, and the indicator's record.
    """
    geometry = await page.evaluate(GEOMETRY)
    if geometry is None or geometry["numbers"] is None:
        return geometry, None
    numbers = geometry["numbers"]
    distance = round((numbers["armPixels"] + 20) / numbers["damping"])
    session = await page.context.new_cdp_session(page)
    x, y = geometry["x"], geometry["y"]
    await page.evaluate(WATCH)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for step in range(1, 13):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove", "touchPoints": [{"x": x, "y": y + distance * step / 12, "id": 1}]})
        await page.wait_for_timeout(16)
    await page.wait_for_timeout(HELD_MILLISECONDS)
    await page.evaluate("()=>window.__pullOnCardRelease()")
    await session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    for _ in range(50):
        if await page.evaluate("()=>window.__pullOnCard.done"):
            break
        await page.wait_for_timeout(100)
    return geometry, await page.evaluate("()=>window.__pullOnCard")


async def main():
    journal = Journal("R235 — a pull begun on a card refreshes")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        for state in STATES:
            context, page = await open_page(browser)
            errors = []
            page.on("pageerror", lambda error, sink=errors: sink.append(str(error)))
            answer = await page.evaluate(
                "(id)=>{try{window.__go(id);return null}catch(error){return String(error)}}", state)
            journal.check(f"the named state {state} exists", answer is None, answer or "")
            await page.wait_for_timeout(SETTLED)
            geometry, record = await pull_from_the_card(page)
            journal.check(f"{state}: a card is drawn at the scrollport's top",
                          geometry is not None and geometry["scrollTop"] <= 0, str(geometry))
            journal.check(f"{state}: pulled from ON a card, the indicator opens while the finger is held",
                          record is not None and record["held"] > 0, str(record))
            journal.check(f"{state}: released, the wheel turns — the re-read has started",
                          record is not None and record["spun"], str(record))
            journal.check(f"{state}: no JS error", not errors, str(errors))
            await context.close()
        await browser.close()
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

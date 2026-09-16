"""R199 — the pull indicator is centred, and closes when the refresh does (B-331).

WHAT THE OPERATOR SAW. On « Réglages », after a pull: the message « Actualisé. »
up while the indicator was still open 44 px tall, and a spinner drawn at the
left edge, cut. The indicator closed on a fixed 1 100 ms timer that knew
nothing of the refresh it stood for.

THE SAMPLING FIRST, which the entry left open: the spinner's box is read at
rest, armed (the finger still down), loading (just released) and closing, at the
phone width, and every reading is printed with the first hold, so the report
can say which moment is off-centre — on this machine, not the operator's phone.

WHAT IT HOLDS:

  p1. WHILE LOADING, THE SPINNER'S CENTRE IS WITHIN 1 PX OF THE SCROLLPORT'S,
      and its box lies inside the scrollport — not cut by an edge.
  p2. THE INDICATOR CLOSES WHEN THE REFRESH SETTLES, read with the mock layer
      answering after two different latencies: each closing lands after its own
      latency and within the height transition of it. A fixed delay can match
      at most one of them.
  p3. « Actualisé. » IS SAID ONCE THE INDICATOR HAS CLOSED, never while it is
      still open.
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import SETTLED, Journal, open_page

from playwright.async_api import async_playwright

SETTINGS_STATE = "settings"
# Two answer times far enough apart that no single fixed delay closes after both
# and within the transition of both.
LATENCIES = (400, 1600)
# The height transition, plus what a busy machine adds to a frame.
CLOSING_ALLOWANCE_MILLISECONDS = 700
MESSAGE = "Actualisé."  # french-ok: the app's rendered message, asserted

SPINNER = """()=>{
  const indicator = document.querySelector('#ptr');
  const spinner = indicator?.firstElementChild;
  const port = document.querySelector('#port');
  if (!indicator || !spinner || !port) return null;
  const box = spinner.getBoundingClientRect();
  const frame = port.getBoundingClientRect();
  return {
    height: Math.round(indicator.getBoundingClientRect().height * 10) / 10,
    x: Math.round(box.left * 10) / 10, y: Math.round(box.top * 10) / 10,
    width: Math.round(box.width * 10) / 10,
    offset: Math.round(((box.left + box.width / 2) - (frame.left + frame.width / 2)) * 10) / 10,
    inside: box.left >= frame.left - 0.5 && box.right <= frame.right + 0.5
            && box.top >= frame.top - 0.5,
  };
}"""

# Records, frame by frame from the release, when the indicator is back to 0 and
# when the message is up.
WATCH = """(message)=>{
  const times = {released: performance.now(), closed: null, said: null, saidWhileOpen: false};
  window.__pullTimes = times;
  const indicator = document.querySelector('#ptr');
  const tick = () => {
    const now = performance.now();
    const height = indicator.getBoundingClientRect().height;
    const toast = document.getElementById('toast');
    const said = !!toast && toast.offsetParent !== null && toast.textContent.includes(message);
    if (said && times.said === null) {
      times.said = now - times.released;
      times.saidWhileOpen = height > 0.5;
    }
    if (height <= 0.5 && now - times.released > 30 && times.closed === null) {
      times.closed = now - times.released;
    }
    if (now - times.released < 6000 && (times.closed === null || times.said === null)) {
      requestAnimationFrame(tick);
    }
  };
  requestAnimationFrame(tick);
}"""


async def pull(page, sample):
    """Drives a real touch pull past the arming distance, sampling the spinner on the way.

    Args:
        page: The Playwright page, on « Réglages ».
        sample: The dict the readings are written into, by moment.
    """
    port = await page.evaluate("()=>{const r=document.querySelector('#port').getBoundingClientRect();"
                               "return {x:r.x, y:r.y, width:r.width};}")
    numbers = await page.evaluate("()=>window.__gestures.pull")
    distance = round((numbers["armPixels"] + 20) / numbers["damping"])
    session = await page.context.new_cdp_session(page)
    x = port["x"] + port["width"] / 2
    y = port["y"] + 60
    sample["rest"] = await page.evaluate(SPINNER)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for step in range(1, 13):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove", "touchPoints": [{"x": x, "y": y + distance * step / 12, "id": 1}]})
        await page.wait_for_timeout(16)
    sample["armed"] = await page.evaluate(SPINNER)
    await page.evaluate(WATCH, MESSAGE)
    await session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    await page.wait_for_timeout(250)
    sample["loading"] = await page.evaluate(SPINNER)


async def main():
    """Pulls « Réglages » under two answer times and reads the indicator."""
    journal = Journal("R199 — the pull indicator is centred and closes with the refresh")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        closings = {}
        samples = {}
        for latency in LATENCIES:
            context, page = await open_page(browser)
            await page.evaluate("(id)=>window.__go(id)", SETTINGS_STATE)
            await page.wait_for_timeout(SETTLED)
            await page.evaluate("(ms)=>window.__mocks.setDefaultLatency(ms)", latency)
            sample = {}
            await pull(page, sample)
            for _ in range(40):
                times = await page.evaluate("()=>window.__pullTimes")
                if times["closed"] is not None and times["said"] is not None:
                    break
                if times["closed"] is None:
                    sample["closing"] = await page.evaluate(SPINNER)
                await page.wait_for_timeout(100)
            closings[latency] = await page.evaluate("()=>window.__pullTimes")
            samples[latency] = sample
            await page.evaluate("()=>window.__mocks.setDefaultLatency(0)")
            await context.close()
        await browser.close()

    first = samples[LATENCIES[-1]]
    loading = first.get("loading")
    journal.check("while loading, the spinner is centred on the scrollport and not cut",
                  loading is not None and loading["height"] > 0.5
                  and abs(loading["offset"]) <= 1 and loading["inside"],
                  f"samples {first}")
    for latency in LATENCIES:
        times = closings[latency]
        journal.check(f"with a {latency} ms answer the indicator closes when the refresh settles",
                      times["closed"] is not None
                      and latency <= times["closed"] <= latency + CLOSING_ALLOWANCE_MILLISECONDS,
                      f"closed {times['closed']} ms after the release")
        journal.check(f"with a {latency} ms answer « Actualisé. » comes once it has closed",
                      times["said"] is not None and not times["saidWhileOpen"]
                      and times["closed"] is not None and times["said"] >= times["closed"] - 1,
                      f"said {times['said']} ms (open {times['saidWhileOpen']}), closed {times['closed']} ms")
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

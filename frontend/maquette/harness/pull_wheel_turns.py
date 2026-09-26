"""R223 — the pull indicator's wheel is SEEN turning while the refresh is answered (B-553).

WHAT THE OPERATOR SAW. On his phone: « Le loader quand on glisse vers le bas pour
recharger ne tourne pas. » The rotation is declared — the spinner carries
`animation: spin` while the indicator is `loading` — and since B-331 the
indicator closes when the re-read settles. Against the mock layer that is a few
milliseconds, so a wheel that turns may still never be SEEN turning.

THE MEASUREMENT FIRST. Every page below is pulled by a real touch at the phone
width; from the release, every frame records the wheel's angle (read from its
computed transform) and whether the wheel is spinning, and an observer times
the spinning's two edges. The readings are printed in the holds' details, so
the report can say how long the wheel spins on each page and how far it turned.

WHAT IT HOLDS:

  w1. THE SERVED STYLESHEET DEFINES `spin` AS A ROTATION, and the wheel carries
      it while loading — a keyframe dropped by the build would leave a name
      that animates nothing.
  w2. WHEN THE REFRESH TAKES ITS TIME, THE WHEEL TURNS on every page — the
      animation runs, with motion allowed and with motion reduced alike (the
      phone's « remove animations » is `prefers-reduced-motion: reduce`).
  w3. AT THE MOCK LAYER'S OWN ANSWER TIME, THE WHEEL IS SEEN TURNING: it
      spins for at least one loop of the wheel, and the angle read over that
      time changes.
"""
import asyncio
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# The pages carrying the indicator: R55's seven scrolling surfaces, and « Réglages »,
# where B-331 was seen.
PAGES = ("acq-now-idle", "acq-follows-list", "acq-discover", "lib-grid", "lib-list",
         "arr-idle", "system", "settings")
# An answer time long enough for several loops of the wheel.
SLOW_LATENCY_MILLISECONDS = 1600
# Below this many degrees across the samples, a wheel is not turning.
TURNING_DEGREES = 30

KEYFRAMES = """()=>{
  const found = [];
  const walk = (rules) => {
    for (const rule of rules) {
      if (rule.type === CSSRule.KEYFRAMES_RULE && rule.name === 'spin') found.push(rule.cssText);
      if (rule.cssRules) walk(rule.cssRules);
    }
  };
  for (const sheet of document.styleSheets) {
    try { walk(sheet.cssRules); } catch (error) { found.push('unreadable ' + sheet.href); }
  }
  return found;
}"""

# Records, from the release, the wheel's angle every frame and when its animation
# starts and stops. The spinning state is read on the WHEEL — the animation the
# drawing applies to it — and its edges are timed by an observer on the
# indicator's attribute changes, so a state lasting less than a frame is still
# timed rather than read as absent.
WATCH = """()=>{
  const indicator = document.querySelector('#ptr');
  const wheel = indicator.firstElementChild;
  const record = {released: performance.now(), samples: [], animation: null, loop: null,
                  started: null, stopped: null};
  window.__wheel = record;
  const since = () => Math.round((performance.now() - record.released) * 10) / 10;
  const spinning = () => getComputedStyle(wheel).animationName !== 'none';
  const angle = () => {
    const matrix = getComputedStyle(wheel).transform;
    if (!matrix || matrix === 'none') return 0;
    const values = matrix.slice(matrix.indexOf('(') + 1, -1).split(',').map(Number);
    return Math.atan2(values[1], values[0]) * 180 / Math.PI;
  };
  const edge = () => {
    const now = spinning();
    if (now && record.started === null) {
      record.started = since();
      record.animation = getComputedStyle(wheel).animationName;
    }
    if (!now && record.started !== null && record.stopped === null) record.stopped = since();
  };
  const observer = new MutationObserver(edge);
  observer.observe(indicator, {attributes: true});
  record.loop = getComputedStyle(document.documentElement).getPropertyValue('--duration-loop-1').trim();
  const tick = () => {
    edge();
    const now = since();
    record.samples.push([Math.round(now), spinning(), Math.round(angle())]);
    if (now < 3000 && (record.stopped === null || now < 100)) requestAnimationFrame(tick);
    else { observer.disconnect(); record.done = true; }
  };
  requestAnimationFrame(tick);
}"""


def turned(samples):
    """Sums how far the wheel turned while it was spinning.

    Args:
        samples: The frames recorded, as `[milliseconds, spinning, degrees]`.

    Returns:
        The degrees travelled, each step unwrapped across the ±180° seam.
    """
    loading = [sample for sample in samples if sample[1]]
    travelled = 0.0
    for previous, current in zip(loading, loading[1:]):
        step = (current[2] - previous[2]) % 360
        travelled += step if step <= 180 else 360 - step
    return travelled


async def pull(page):
    """Drives a real touch pull past the arming distance and releases it, watching the wheel.

    Args:
        page: The Playwright page, on the page to pull.

    Returns:
        The record written from the release: the samples, the spinning's two
        edges, the animation name read while spinning, and the loop's declared
        duration.
    """
    port = await page.evaluate("()=>{const r=document.querySelector('#port').getBoundingClientRect();"
                               "return {x:r.x, y:r.y, width:r.width};}")
    numbers = await page.evaluate("()=>window.__gestures.pull")
    distance = round((numbers["armPixels"] + 20) / numbers["damping"])
    session = await page.context.new_cdp_session(page)
    x = port["x"] + port["width"] / 2
    y = port["y"] + 60
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for step in range(1, 13):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove", "touchPoints": [{"x": x, "y": y + distance * step / 12, "id": 1}]})
        await page.wait_for_timeout(16)
    await page.evaluate(WATCH)
    await session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    for _ in range(40):
        if await page.evaluate("()=>!!window.__wheel.done"):
            break
        await page.wait_for_timeout(100)
    return await page.evaluate("()=>window.__wheel")


async def measure(browser, page_id, latency, motion):
    """Pulls one page under one answer time and one motion preference.

    Args:
        browser: The launched browser.
        page_id: The named state to pull.
        latency: The mock layer's answer time, or None for its own.
        motion: The `reduced_motion` the context emulates.

    Returns:
        The record of the pull and the `spin` keyframes the served sheets hold.
    """
    context, page = await open_page(browser, reduced_motion=motion)
    await page.evaluate("(id)=>window.__go(id)", page_id)
    await page.wait_for_timeout(SETTLED)
    if latency is not None:
        await page.evaluate("(ms)=>window.__mocks.setDefaultLatency(ms)", latency)
    keyframes = await page.evaluate(KEYFRAMES)
    record = await pull(page)
    await page.evaluate("()=>window.__mocks.setDefaultLatency(0)")
    await context.close()
    return record, keyframes


async def main():
    """Pulls every page carrying the indicator and reads whether its wheel is seen turning."""
    journal = Journal("R223 — the pull indicator's wheel is seen turning")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        slow = {}
        reduced = {}
        own = {}
        keyframes = []
        for page_id in PAGES:
            slow[page_id], keyframes = await measure(browser, page_id, SLOW_LATENCY_MILLISECONDS, "no-preference")
            reduced[page_id], _ = await measure(browser, page_id, SLOW_LATENCY_MILLISECONDS, "reduce")
            own[page_id], _ = await measure(browser, page_id, None, "no-preference")
        await browser.close()

    def reading(record):
        """One pull's reading: how long the wheel spun, and how far it turned."""
        spun = None
        if record["started"] is not None and record["stopped"] is not None:
            spun = round(record["stopped"] - record["started"], 1)
        return spun, turned(record["samples"])

    def readings(records):
        """Every page's reading under one condition, printed in a hold's detail."""
        return " · ".join(f"{page_id} {reading(records[page_id])[0]} ms {reading(records[page_id])[1]:.0f}°"
                          for page_id in PAGES)

    journal.check("the served stylesheet defines `spin` as a rotation",
                  any("rotate(360deg)" in text for text in keyframes), f"keyframes {keyframes}")
    unnamed = [page_id for page_id in PAGES if slow[page_id]["animation"] != "spin"]
    journal.check("the wheel carries `spin` while loading, on every page", not unnamed, f"without it: {unnamed}")
    for label, records in (("with motion allowed", slow), ("with motion reduced", reduced)):
        still = [page_id for page_id in PAGES if reading(records[page_id])[1] < TURNING_DEGREES]
        journal.check(f"with a {SLOW_LATENCY_MILLISECONDS} ms answer the wheel turns {label}, on every page",
                      not still, f"still: {still}; spun: {readings(records)}")
    unseen = []
    for page_id in PAGES:
        spun, degrees = reading(own[page_id])
        loop = float(own[page_id]["loop"].rstrip("s") or "nan") * 1000
        if math.isnan(loop) or spun is None or spun < loop or degrees < TURNING_DEGREES:
            unseen.append(page_id)
    journal.check("at the mock layer's own answer time the wheel is seen turning for a loop, on every page",
                  not unseen, f"unseen: {unseen}; loop {own[PAGES[0]]['loop']}; spun: {readings(own)}")
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

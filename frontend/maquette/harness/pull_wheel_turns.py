"""R223 — the pull indicator's wheel is SEEN turning while the refresh is answered (B-553).

WHAT THE OPERATOR SAW. On his phone: « Le loader quand on glisse vers le bas pour
recharger ne tourne pas. » The rotation is declared — the spinner carries
`animation: spin` while the indicator is `loading` — and since B-331 the
indicator closes when the re-read settles. Against the mock layer that is a few
milliseconds, so a wheel that turns may still never be SEEN turning.

THE MEASUREMENT FIRST. Every page below is pulled by a real touch at the phone
width; from the release, every frame records the wheel's angle (read from its
computed transform) and whether the indicator is still `loading`. The readings
are printed with the holds, so the report can say how long `loading` lasts on
each page and how far the wheel turned.

WHAT IT HOLDS:

  w1. THE SERVED STYLESHEET DEFINES `spin` AS A ROTATION, and the wheel carries
      it while loading — a keyframe dropped by the build would leave a name
      that animates nothing.
  w2. WHEN THE REFRESH TAKES ITS TIME, THE WHEEL TURNS on every page — the
      animation runs, with motion allowed and with motion reduced alike (the
      phone's « remove animations » is `prefers-reduced-motion: reduce`).
  w3. AT THE MOCK LAYER'S OWN ANSWER TIME, THE WHEEL IS SEEN TURNING: the
      indicator stays `loading` for at least one loop of the wheel, and the
      angle read over that time changes.
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

# Records, frame by frame from the release, the wheel's angle and the indicator's state.
WATCH = """()=>{
  const indicator = document.querySelector('#ptr');
  const wheel = indicator.firstElementChild;
  const record = {released: performance.now(), samples: [], animation: null, loop: null};
  window.__wheel = record;
  const angle = () => {
    const matrix = getComputedStyle(wheel).transform;
    if (!matrix || matrix === 'none') return 0;
    const values = matrix.slice(matrix.indexOf('(') + 1, -1).split(',').map(Number);
    return Math.atan2(values[1], values[0]) * 180 / Math.PI;
  };
  record.loop = getComputedStyle(document.documentElement).getPropertyValue('--duration-loop-1').trim();
  const tick = () => {
    const now = performance.now() - record.released;
    const loading = indicator.classList.contains('loading');
    if (loading && record.animation === null) record.animation = getComputedStyle(wheel).animationName;
    record.samples.push([Math.round(now), loading, Math.round(angle())]);
    if (now < 3000 && (loading || now < 100)) requestAnimationFrame(tick);
    else record.done = true;
  };
  requestAnimationFrame(tick);
}"""


def turned(samples):
    """Sums how far the wheel turned while the indicator was loading.

    Args:
        samples: The frames recorded, as `[milliseconds, loading, degrees]`.

    Returns:
        The degrees travelled, each step unwrapped across the ±180° seam, and
        the milliseconds the indicator stayed loading.
    """
    loading = [sample for sample in samples if sample[1]]
    travelled = 0.0
    for previous, current in zip(loading, loading[1:]):
        step = (current[2] - previous[2]) % 360
        travelled += step if step <= 180 else 360 - step
    duration = loading[-1][0] - loading[0][0] if loading else 0
    return travelled, duration


async def pull(page):
    """Drives a real touch pull past the arming distance and releases it, watching the wheel.

    Args:
        page: The Playwright page, on the page to pull.

    Returns:
        The record written from the release: the samples, the animation name
        read while loading, and the loop's declared duration.
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

    for page_id in PAGES:
        for label, record in (("slow", slow[page_id]), ("reduced", reduced[page_id]), ("own", own[page_id])):
            degrees, duration = turned(record["samples"])
            print(f"  reading {page_id:18} {label:8} loading {duration:5} ms, turned {degrees:6.0f}°, "
                  f"animation {record['animation']}, loop {record['loop']}")

    journal.check("the served stylesheet defines `spin` as a rotation",
                  any("rotate(360deg)" in text for text in keyframes), f"keyframes {keyframes}")
    unnamed = [page_id for page_id in PAGES if slow[page_id]["animation"] != "spin"]
    journal.check("the wheel carries `spin` while loading, on every page", not unnamed, f"without it: {unnamed}")
    for label, records in (("with motion allowed", slow), ("with motion reduced", reduced)):
        still = [f"{page_id} ({turned(records[page_id]['samples'])[0]:.0f}°)" for page_id in PAGES
                 if turned(records[page_id]["samples"])[0] < TURNING_DEGREES]
        journal.check(f"with a {SLOW_LATENCY_MILLISECONDS} ms answer the wheel turns {label}, on every page",
                      not still, f"still: {still}")
    unseen = []
    for page_id in PAGES:
        degrees, duration = turned(own[page_id]["samples"])
        loop = float(own[page_id]["loop"].rstrip("s") or "nan") * 1000
        if math.isnan(loop) or duration < loop or degrees < TURNING_DEGREES:
            unseen.append(f"{page_id} (loading {duration} ms, {degrees:.0f}°, loop {loop:.0f} ms)")
    journal.check("at the mock layer's own answer time the wheel is seen turning for a loop, on every page",
                  not unseen, f"unseen: {unseen}")
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

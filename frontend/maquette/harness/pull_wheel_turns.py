"""R223 — the pull indicator's wheel is SEEN turning, from the arming to the reload's end (B-553).

WHAT THE OPERATOR SAW. On his phone: « Le loader quand on glisse vers le bas pour
recharger ne tourne pas. » The rotation was declared only while the indicator
was `loading`, and since B-331 the indicator closes when the re-read settles —
against the mock layer, 7 to 19 ms after the release, measured on every page
below: a wheel that turns and is never seen turning.

WHAT HE RULED: « La roue tourne dès que le geste est armé, un tour
minimal visible, disparaît quand le rechargement est fini. »

HOW IT IS READ. Every page below is pulled by a real touch at the phone width.
From the finger's first contact, every frame records the wheel's angle (read
from its computed transform), whether it is spinning (its computed animation),
and whether the finger is still down; an observer times the spinning's edges.
The readings are printed in the holds' details.

WHAT IT HOLDS:

  w1. THE SERVED STYLESHEET DEFINES `spin` AS A ROTATION, and the wheel carries
      it — a keyframe dropped by the build would leave a name that animates
      nothing.
  w2. THE WHEEL TURNS WHILE THE PULL IS ARMED, the finger still down.
  w3. AT THE MOCK LAYER'S OWN ANSWER TIME, THE WHEEL MAKES AT LEAST ONE TURN
      AFTER THE RELEASE: it spins for one loop of the wheel, and turns.
  w4. A SLOW RELOAD KEEPS IT TURNING UNTIL THE RELOAD IS DONE, and it stops
      then — not before the answer, not long after it — with motion allowed
      and with motion reduced alike (the phone's « remove animations » is
      `prefers-reduced-motion: reduce`).
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import SETTLED, Journal, open_page

from playwright.async_api import async_playwright

# The pages carrying the indicator: R55's seven scrolling surfaces, and « Réglages »,
# where B-331 was seen.
PAGES = ("acq-now-idle", "acq-follows-list", "discover-full", "lib-grid", "lib-list",
         "acq-todo-loaded", "system", "settings")  # « À traiter » in the dead page's place
# An answer time longer than one loop of the wheel, by far.
SLOW_LATENCY_MILLISECONDS = 1600
# How long the finger stays down once the pull is armed.
HELD_MILLISECONDS = 500
# Below this many degrees, a wheel is not turning.
TURNING_DEGREES = 30
# What a frame costs a timer on a busy machine, below one loop.
FRAME_TOLERANCE_MILLISECONDS = 20
# How long after a slow reload's answer the wheel may still spin: the re-read
# itself, and what a busy machine adds to it.
SETTLING_ALLOWANCE_MILLISECONDS = 700

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

# Records, from the finger's first contact, the wheel's angle every frame, and
# times the spinning's edges by an observer on the indicator's attribute changes,
# so a spinning shorter than a frame is timed rather than read as absent. The
# spinning state is read on the WHEEL — the animation the drawing applies to it.
WATCH = """()=>{
  const indicator = document.querySelector('#ptr');
  const wheel = indicator.firstElementChild;
  const record = {start: performance.now(), released: null, samples: [], animation: null,
                  loop: null, stopped: null, spunAfterRelease: false};
  window.__wheel = record;
  const since = () => Math.round((performance.now() - record.start) * 10) / 10;
  const spinning = () => getComputedStyle(wheel).animationName !== 'none';
  const angle = () => {
    const matrix = getComputedStyle(wheel).transform;
    if (!matrix || matrix === 'none') return 0;
    const values = matrix.slice(matrix.indexOf('(') + 1, -1).split(',').map(Number);
    return Math.atan2(values[1], values[0]) * 180 / Math.PI;
  };
  const edge = () => {
    const now = spinning();
    if (now && record.animation === null) record.animation = getComputedStyle(wheel).animationName;
    // The end is the first stop AFTER the wheel has spun past the release: a
    // wheel still at rest when the finger lifts has not stopped, it has not started.
    if (now && record.released !== null) record.spunAfterRelease = true;
    if (!now && record.spunAfterRelease && record.stopped === null) record.stopped = since();
  };
  window.__wheelRelease = () => { record.released = since(); };
  const observer = new MutationObserver(edge);
  observer.observe(indicator, {attributes: true});
  record.loop = getComputedStyle(document.documentElement).getPropertyValue('--duration-loop-1').trim();
  const tick = () => {
    edge();
    const now = since();
    record.samples.push([now, spinning(), Math.round(angle()), record.released === null]);
    const after = record.released === null ? 0 : now - record.released;
    if (now < 6000 && (record.stopped === null || after < 100)) requestAnimationFrame(tick);
    else { observer.disconnect(); record.done = true; }
  };
  requestAnimationFrame(tick);
}"""


def turned(samples):
    """Sums how far the wheel turned across frames where it was spinning.

    Args:
        samples: The frames, as `[milliseconds, spinning, degrees, held]`.

    Returns:
        The degrees travelled, each step unwrapped across the ±180° seam.
    """
    spinning = [sample for sample in samples if sample[1]]
    travelled = 0.0
    for previous, current in zip(spinning, spinning[1:]):
        step = (current[2] - previous[2]) % 360
        travelled += step if step <= 180 else 360 - step
    return travelled


async def pull(page):
    """Drives a real touch pull past the arming distance, holds it, and releases it.

    Args:
        page: The Playwright page, on the page to pull.

    Returns:
        The record written from the first contact: the samples, the release and
        the spinning's end in milliseconds, the animation name read while
        spinning, and the loop's declared duration.
    """
    port = await page.evaluate("()=>{const r=document.querySelector('#port').getBoundingClientRect();"
                               "return {x:r.x, y:r.y, width:r.width};}")
    numbers = await page.evaluate("()=>window.__gestures.pull")
    distance = round((numbers["armPixels"] + 20) / numbers["damping"])
    session = await page.context.new_cdp_session(page)
    x = port["x"] + port["width"] / 2
    y = port["y"] + 60
    await page.evaluate(WATCH)
    await session.send("Input.dispatchTouchEvent", {
        "type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
    for step in range(1, 13):
        await session.send("Input.dispatchTouchEvent", {
            "type": "touchMove", "touchPoints": [{"x": x, "y": y + distance * step / 12, "id": 1}]})
        await page.wait_for_timeout(16)
    await page.wait_for_timeout(HELD_MILLISECONDS)
    await page.evaluate("()=>window.__wheelRelease()")
    await session.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    for _ in range(80):
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


def armed_turn(record):
    """Degrees the wheel turned while the finger was still down."""
    return turned([sample for sample in record["samples"] if sample[3]])


def after_release(record):
    """How long the wheel spun after the release, and how far it turned then."""
    spun = None if record["stopped"] is None else round(record["stopped"] - record["released"], 1)
    return spun, turned([sample for sample in record["samples"] if not sample[3]])


def readings(records):
    """Every page's reading under one condition, for a hold's detail."""
    return " · ".join(
        f"{page_id} armed {armed_turn(records[page_id]):.0f}° / after {after_release(records[page_id])[0]} ms "
        f"{after_release(records[page_id])[1]:.0f}°" for page_id in PAGES)


async def main():
    """Pulls every page carrying the indicator and reads when its wheel turns."""
    journal = Journal("R223 — the pull indicator's wheel is seen turning")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome")
        slow = {}
        reduced = {}
        own = {}
        keyframes = []
        for page_id in PAGES:
            own[page_id], keyframes = await measure(browser, page_id, None, "no-preference")
            slow[page_id], _ = await measure(browser, page_id, SLOW_LATENCY_MILLISECONDS, "no-preference")
            reduced[page_id], _ = await measure(browser, page_id, SLOW_LATENCY_MILLISECONDS, "reduce")
        await browser.close()

    journal.check("the served stylesheet defines `spin` as a rotation",
                  any("rotate(360deg)" in text for text in keyframes), f"keyframes {keyframes}")
    unnamed = [page_id for page_id in PAGES if slow[page_id]["animation"] != "spin"]
    journal.check("the wheel carries `spin`, on every page", not unnamed, f"without it: {unnamed}")

    still = [page_id for page_id in PAGES if armed_turn(own[page_id]) < TURNING_DEGREES]
    journal.check("the wheel turns while the pull is armed, the finger still down, on every page",
                  not still, f"still: {still}; {readings(own)}")

    loop = float(own[PAGES[0]]["loop"].rstrip("s") or "0") * 1000
    short = []
    for page_id in PAGES:
        spun, degrees = after_release(own[page_id])
        if spun is None or spun < loop - FRAME_TOLERANCE_MILLISECONDS or degrees < TURNING_DEGREES:
            short.append(page_id)
    journal.check("at the mock layer's own answer time the wheel makes one turn after the release, on every page",
                  loop > 0 and not short, f"short: {short}; loop {loop:.0f} ms; {readings(own)}")

    for label, records in (("with motion allowed", slow), ("with motion reduced", reduced)):
        off = []
        for page_id in PAGES:
            spun, degrees = after_release(records[page_id])
            if (spun is None or not SLOW_LATENCY_MILLISECONDS <= spun
                    <= SLOW_LATENCY_MILLISECONDS + SETTLING_ALLOWANCE_MILLISECONDS or degrees < TURNING_DEGREES):
                off.append(page_id)
        journal.check(f"with a {SLOW_LATENCY_MILLISECONDS} ms reload the wheel turns until it is done and stops "
                      f"then, {label}, on every page", not off, f"off: {off}; {readings(records)}")
    journal.summary()


if __name__ == "__main__":
    asyncio.run(main())

"""R-conformity-a: every named state, at every width a phone or a desktop has.

THE DEFECT THIS ENDS. Every other rule measures at ONE width, `PHONE` in
`common.py` — 390 px — and the frame fixes it there. The operator's phone is
not 390 px wide, and a phone that is not the harness's reads a list « cut on
the right » that every rule passed (Système's runs, 2026-09-29). So this rule
opens every named state at seven widths and refuses, over the whole device:

  overflow  — the document, a VERTICAL scroll port, or preformatted text in a
              horizontal one, wider than its box: read sideways under a finger;
  outside   — an element whose box leaves the window with no ancestor that
              scrolls or clips it on x;
  cut       — an element carrying text or a painted border whose box passes the
              box of the ancestor that clips it on x, or whose own text is
              clipped in place (the ellipsis);
  bevel     — a border drawn `outset`, `inset`, `groove` or `ridge`: the design
              system draws none, so it is a browser default no class reset — the
              runs list's buttons, whose right edge shades into the background.

THE WIDTHS. 320, 360, 369, 390 and 412 are phones, measured as phones (touch,
mobile). 768 and 1280 are windows, measured OUT of the harness's phone frame —
`tm-desktop-switch` set before the document parses, as the harness's own script
reads it — because inside the frame the app is 390 px wide whatever the window,
and a reading there would be the 390 px reading again under another name.

THE OWED LIST. A fall this train does not repair is declared below by `arm ·
data-part` with its OWNER — never by a whole state, never by a width, never by
a class, so a second defect on the same state still falls. A run over every
state and every width also refuses an owed entry that no longer falls: the list
says what is owed today, not what was owed once.

WHAT IT DOES NOT READ, said so nobody reads more into it: vertical clipping (a
line clamp), an element hidden by `visibility`, `opacity: 0` or `display`, a
designed horizontal row (a scroll port that does not also scroll vertically),
and anything outside `#device`.

SUBSETS. `TM_RESPONSIVE_STATES` (comma-separated ids) and `TM_RESPONSIVE_WIDTHS`
narrow a run to the states a phase touches; a narrowed run never judges the owed
list's staleness, since it did not read what the list covers.
"""
import asyncio
import json
import os
import time

from common import PHONE, PROTOTYPE, SETTLED, Journal, chrome_launch_args, served_copy, STARTED_AGAINST
from playwright.async_api import async_playwright

PHONES = (320, 360, 369, 390, 412)
WINDOWS = (768, 1280)
HEIGHT = 844
# Three pages at a time, one per width, the harness's own ceiling
# (`TM_HARNESS_JOBS=3`, docs/reference/implementer-office.md § the mutex).
PARALLEL = int(os.environ.get("TM_HARNESS_JOBS", "3"))

# arm · data-part → its owner. Every entry is a fall read on this tree and
# repaired by someone else; the owner is who, and where it is written down.
OWED: dict[tuple[str, str], str] = {
    # Reds this train repairs in a later phase of its own plan
    # (docs/features/maquette-conformity/plan/INDEX.md): each entry leaves the
    # list in the commit that repairs it, and the rule then holds it.
    ("bevel", "runs/row"): "maquette-conformity phase 2",
    ("bevel", "shell/connection-notice"): "maquette-conformity phase 2 (R1's family)",
    ("cut", "card/requester"): "maquette-conformity phase 3",
    ("cut", "shell/tab-bar"): "maquette-conformity phase 4",
    ("overflow", "run/log"): "maquette-conformity phase 6 (the operator's OPEN 10)",
    ("cut", "card/title"): "maquette-conformity phase 5 (§ 12)",
    ("cut", "card/subtitle"): "maquette-conformity phase 5 (§ 12)",
    ("cut", "tile/title"): "maquette-conformity phase 5 (§ 12's family)",
    ("cut", "cast"): "maquette-conformity phase 5 (§ 12's family)",
    ("cut", "segment"): "maquette-conformity phase 7",
    ("cut", "segment/count"): "maquette-conformity phase 7",
}

MEASURE = """(width) => {
  const device = document.querySelector('#device');
  const falls = [];
  const partOf = (element) => element.closest('[data-part]')?.getAttribute('data-part') ?? element.tagName.toLowerCase();
  const push = (arm, element, rect) => falls.push({arm, part: partOf(element),
    rect: rect ? [Math.round(rect.left), Math.round(rect.right)] : null});
  const root = document.documentElement;
  if (root.scrollWidth > root.clientWidth + 1) falls.push({arm: 'overflow', part: 'document', rect: [0, root.scrollWidth]});
  const scrolls = (style) => style.overflowX === 'auto' || style.overflowX === 'scroll';
  const clips = (style) => style.overflowX === 'hidden' || style.overflowX === 'clip';
  const ownText = (element) => [...element.childNodes].some((node) => node.nodeType === 3 && node.textContent.trim());
  const BEVELS = new Set(['outset', 'inset', 'groove', 'ridge']);
  // The surface on top, picked as `states.py` picks it: a page a screen, a
  // sheet or a dialog covers is not what the state shows, and its falls are
  // the page's own state's to report.
  const view = document.querySelector('#view');
  const dialog = document.querySelector('#dlg[data-open]');
  const sheet = document.querySelector('#sheet[data-open]');
  const screen = document.querySelector('[data-part="screen"][data-open][data-key]');
  const layer = dialog || sheet || screen;
  for (const element of device.querySelectorAll('*')) {
    if (layer && view && view.contains(element) && !layer.contains(element)) continue;
    if (!element.checkVisibility({opacityProperty: true, visibilityProperty: true})) continue;
    const rect = element.getBoundingClientRect();
    if (rect.width <= 1 && rect.height <= 1) continue;
    const style = getComputedStyle(element);
    // Visually hidden on purpose — the screen-reader-only heading: clipped to
    // nothing by its own declaration, read by no eye.
    if (style.clip !== 'auto' || (style.clipPath !== 'none' && style.clipPath.startsWith('inset(50%'))) continue;
    if (scrolls(style) && (style.overflowY === 'auto' || style.overflowY === 'scroll')
        && element.scrollHeight > element.clientHeight + 1 && element.scrollWidth > element.clientWidth + 1)
      push('overflow', element, rect);
    // Preformatted text that scrolls sideways is a page read sideways, not a
    // designed row of chips: § 12 grants no exception (the operator's OPEN 10).
    else if (scrolls(style) && style.whiteSpace === 'pre' && element.scrollWidth > element.clientWidth + 1)
      push('overflow', element, rect);
    const painted = ['Top', 'Right', 'Bottom', 'Left'].some((side) =>
      parseFloat(style[`border${side}Width`]) > 0 && style[`border${side}Style`] !== 'none');
    if (['Top', 'Right', 'Bottom', 'Left'].some((side) =>
        parseFloat(style[`border${side}Width`]) > 0 && BEVELS.has(style[`border${side}Style`])))
      push('bevel', element, rect);
    const text = ownText(element);
    if (text && clips(style) && element.scrollWidth > element.clientWidth + 1) push('cut', element, rect);
    // The first ancestor that does something to x decides what a box past it is.
    let holder = null;
    for (let parent = element.parentElement; parent && parent !== device.parentElement; parent = parent.parentElement) {
      const parentStyle = getComputedStyle(parent);
      if (scrolls(parentStyle) || clips(parentStyle)) { holder = {parent, scrolls: scrolls(parentStyle)}; break; }
    }
    // PARTLY past the edge, never wholly: a layer parked outside its box (the
    // closed drawer, translated off the left) is not seen at all, and what is
    // not seen is not cut — a surface pushed wholly out by an overflow still
    // widens its scroll port, which the overflow arm reads.
    const partly = (left, right) => rect.right > left + 0.5 && rect.left < right - 0.5
      && (rect.left < left - 0.5 || rect.right > right + 0.5);
    if (holder === null) {
      if (partly(0, width)) push('outside', element, rect);
    } else if (!holder.scrolls && (text || painted)) {
      const box = holder.parent.getBoundingClientRect();
      if (partly(box.left, box.right)) push('cut', element, rect);
    }
  }
  return falls;
}"""


def context_for(width):
    """Builds the browser context a width is measured in.

    Args:
        width: The window's width in CSS pixels.

    Returns:
        The context options — a phone below the frame's breakpoint, a desktop
        window out of the frame above it.
    """
    if width in PHONES:
        return {**PHONE, "viewport": {"width": width, "height": HEIGHT}}
    return {"viewport": {"width": width, "height": HEIGHT}, "device_scale_factor": 1,
            "is_mobile": False, "has_touch": False, "color_scheme": "dark"}


async def read_width(browser, width, wanted):
    """Opens the prototype at one width and measures every wanted state.

    Args:
        browser: A launched Playwright browser.
        width: The width to measure at.
        wanted: The state ids asked for, or None for every declared one.

    Returns:
        A dict state id → the falls read there, and the JS errors seen.
    """
    served_copy.assert_unchanged(STARTED_AGAINST, f"opening the prototype at {width} px")
    context = await browser.new_context(**context_for(width))
    if width in WINDOWS:
        # Before the document parses, so the harness's own inline script reads
        # it exactly as it reads the operator's remembered choice.
        await context.add_init_script("try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}")
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(f"{width}px: {error}"))
    await page.goto(PROTOTYPE, wait_until="load")
    await page.evaluate("()=>window.__loadingDone?.()")
    await page.evaluate("()=>document.querySelector('#toastx')?.click()")
    ids = wanted or await page.evaluate("()=>window.__states()")
    readings = {}
    for state in ids:
        try:
            await page.evaluate("(id)=>window.__go(id)", state)
        except Exception as error:  # noqa: BLE001 — a state that cannot be reached is a fall, named
            readings[state] = [{"arm": "unreachable", "part": str(error)[:80], "rect": None}]
            continue
        await page.wait_for_timeout(SETTLED)
        readings[state] = await page.evaluate(MEASURE, width)
    await context.close()
    return readings, errors


async def main():
    """Measures every named state at every width and judges the falls."""
    wanted = [state for state in os.environ.get("TM_RESPONSIVE_STATES", "").split(",") if state] or None
    widths = tuple(int(width) for width in os.environ.get("TM_RESPONSIVE_WIDTHS", "").split(",") if width) \
        or PHONES + WINDOWS
    whole = wanted is None and widths == PHONES + WINDOWS
    journal = Journal("R-conformity-a — every named state at every width: no overflow, no cut, no bevel")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", args=chrome_launch_args())
        gate = asyncio.Semaphore(PARALLEL)

        async def one(width):
            async with gate:
                return width, await read_width(browser, width, wanted)

        started = time.monotonic()
        results = await asyncio.gather(*(one(width) for width in widths))
        await browser.close()
    # The cost is printed on every run: the plan decides from it where the
    # whole sweep may run (docs/features/maquette-conformity/plan/phase-01-the-responsive-rule.md).
    print(f"measured in {time.monotonic() - started:.0f} s")
    per_state: dict[str, list[str]] = {}
    owed_seen: dict[tuple[str, str], set[str]] = {}
    errors = []
    for width, (readings, width_errors) in sorted(results):
        errors += width_errors
        for state, falls in readings.items():
            for fall in falls:
                key = (fall["arm"], fall["part"])
                if key in OWED:
                    owed_seen.setdefault(key, set()).add(f"{state}@{width}")
                    continue
                per_state.setdefault(state, [])
                line = f"{width}px {fall['arm']} {fall['part']} {fall['rect']}"
                if line not in per_state[state]:
                    per_state[state].append(line)
    states = sorted({state for _, (readings, _) in results for state in readings})
    # The whole reading, to a file when asked: `run.sh` prints a failing rule's
    # first lines only, and the owed list is built from every fall.
    report = os.environ.get("TM_RESPONSIVE_REPORT")
    if report:
        with open(report, "w", encoding="utf-8") as handle:
            json.dump({"widths": list(widths), "states": len(states), "falls": per_state,
                       "owed": {f"{arm} · {part}": sorted(seen) for (arm, part), seen in owed_seen.items()}},
                      handle, ensure_ascii=False, indent=1)
    print(f"{len(states)} state(s) × {len(widths)} width(s) {list(widths)}\n")
    for state in states:
        falls = per_state.get(state, [])
        journal.check(f"{state} at every width", not falls, "; ".join(falls))
    for key, owner in OWED.items():
        seen = owed_seen.get(key, set())
        print(f"  OWED {key[0]} · {key[1]} → {owner} — {len(seen)} reading(s)"
              + (f", e.g. {sorted(seen)[0]}" if seen else ""))
        if whole:
            journal.check(f"owed {key[0]} · {key[1]} still falls", seen, "an owed entry that no longer falls leaves the list")
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

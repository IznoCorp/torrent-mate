"""R-conformity-a: every named state, at every width a phone or a desktop has.

THE DEFECT THIS ENDS. Every other rule measures at ONE width, `PHONE` in
`common.py` — 390 px — and the frame fixes it there. The operator's phone is
not 390 px wide, and a phone that is not the harness's reads a list « cut on
the right » that every rule passed (Système's runs). So this rule
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
              runs list's buttons, whose right edge shades into the background;
  undrawn   — an `<svg>` the page shows, drawn at no size: an icon sized by
              its viewBox alone, which a flex box resolves to 0 in WebKit and
              to the room left in Chromium (the menu's, B-579) — or to 0 in
              both (the header's brand mark);
  unseen    — in WebKit only, a frame control a finger must find (the menu
              button, the bottom bar's buttons, a tab) that is outside the
              window, covered at its centre, drawn at no size, or inked under
              3:1 against the colour beneath it — in light AND in dark. A
              control a surface covers ON PURPOSE is not unseen: under a pushed
              screen, the startup or the sign-in screen, or inside a page made
              `inert` by a layer above it.

THE iPHONE'S ENGINE. The harness is Chromium and an iPhone is WebKit, so the
same states are read once more in WebKit at 390 px, in both colour schemes: a
defect only one engine draws is a defect a Chromium harness never sees.

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

WHICH ARM READS WHAT, MEASURED. The page CLIPS on x (its scroll ports are
`overflow-x: hidden`), so a block wider than the page falls as `cut`, never as
`overflow`: a list widened past its page read `cut · flux`, a header widened
past a desktop window read `outside · shell/header`. `overflow` reads today only
through its preformatted-text branch (the raw log); its document and vertical-
port branches read nothing on this tree and stay as the net for a page that
stops clipping.

SUBSETS. `TM_RESPONSIVE_STATES` (comma-separated ids), `TM_RESPONSIVE_WIDTHS`
(Chromium's widths) and `TM_RESPONSIVE_ENGINES` (`chromium`, `webkit`) narrow a run to the states a change touches; a narrowed run never judges the owed
list's staleness, since it did not read what the list covers.
"""
import asyncio
import json
import os
import time

from common import PHONE, PROTOTYPE, SETTLED, Journal, browser_channel, chrome_launch_args, served_copy, STARTED_AGAINST
from playwright.async_api import async_playwright

PHONES = (320, 360, 369, 390, 412)
WINDOWS = (768, 1280)
HEIGHT = 844
# The iPhone's format, measured in the iPhone's engine.
IPHONE = 390
# Three pages at a time, one per width, the harness's own ceiling
# (`TM_HARNESS_JOBS=3`, docs/reference/implementer-office.md § the mutex).
PARALLEL = int(os.environ.get("TM_HARNESS_JOBS", "3"))

# arm · data-part → its owner. Every entry is a fall read on this tree and
# repaired by its owner, named beside it — never silenced.
OWED: dict[tuple[str, str], str] = {
    # Reds with a named owner and a repair to come: each entry leaves the
    # list in the commit that repairs it, and the rule then holds it.
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
    // An icon the page shows drawn at no size: an `<svg>` sized by its
    // viewBox alone has no intrinsic width, and a flex box resolves it to
    // the room left — the whole of it in one engine, nothing in another.
    if (element.tagName.toLowerCase() === 'svg' && (rect.width < 1 || rect.height < 1)) { push('undrawn', element, rect); continue; }
    if (rect.width <= 1 && rect.height <= 1) continue;
    const style = getComputedStyle(element);
    // Visually hidden on purpose — the screen-reader-only heading: clipped to
    // nothing by its own declaration, read by no eye.
    if (style.clip !== 'auto' || (style.clipPath !== 'none' && style.clipPath.startsWith('inset(50%'))) continue;
    if (scrolls(style) && (style.overflowY === 'auto' || style.overflowY === 'scroll')
        && element.scrollHeight > element.clientHeight + 1 && element.scrollWidth > element.clientWidth + 1)
      push('overflow', element, rect);
    // Preformatted text that scrolls sideways is a page read sideways, not a
    // designed row of chips: § 12 grants no exception.
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
    } else if (!holder.scrolls && (text || painted)
               // A ROW HELD MID-SWIPE: its card travels past the row that clips
               // it, which is the gesture's own drawing — the word of that side
               // uncovered under it — not a cut (re-aimed 2026-09-30,
               // `discover-list-travel-left/right`; the row still fits, and
               // anything past IT still falls). The design system's drawer
               // swipe is the same drawing: a card of a `swipe` row, held open
               // on its drawer (its inline travel), uncovers the drawer's
               // action (`torrent-swipe-remove`); at rest it is still read.
               && !(holder.parent.hasAttribute('data-travel') && element.closest('[data-part="card"]'))
               && !(holder.parent.dataset.part === 'swipe'
                    && element.closest('[data-part="card"]')?.style.transform)) {
      const box = holder.parent.getBoundingClientRect();
      if (partly(box.left, box.right)) push('cut', element, rect);
    }
  }
  return falls;
}"""


# The frame's controls a finger must find on every state, read only when no
# layer covers the page (a sheet or the drawer covers them on purpose): the
# menu button, the bottom bar's buttons, and every tab of a tab bar.
VISIBLE = """(width) => {
  if (document.querySelector('#dlg[data-open], #sheet[data-open], #drawer[data-open]')) return [];
  const falls = [];
  // ANY CSS colour to sRGB bytes through a canvas: an engine may answer a
  // computed colour as `oklch(…)` or `color(srgb …)`, and a regex over its
  // numbers reads a lightness as a red.
  const paint = document.createElement('canvas').getContext('2d', {willReadFrequently: true});
  const colour = (text) => {
    paint.clearRect(0, 0, 1, 1);
    paint.fillStyle = '#000'; paint.fillStyle = text; paint.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = paint.getImageData(0, 0, 1, 1).data;
    return [r, g, b, a / 255];
  };
  const luminance = ([r, g, b]) => [r, g, b].map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
    .reduce((sum, v, index) => sum + v * [0.2126, 0.7152, 0.0722][index], 0);
  const ratio = (a, b) => { const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  const under = (element) => {
    for (let node = element; node; node = node.parentElement) {
      const value = colour(getComputedStyle(node).backgroundColor);
      if (value[3] > 0.5) return value;
    }
    return [0, 0, 0, 1];
  };
  const COVERS = '[data-part="screen"][data-open], #splash, #login, #sheet[data-open], #dlg[data-open], #drawer[data-open]';
  const controls = [
    ['menu', document.querySelector('[data-part="shell/header"] [data-drawer]')],
    ...[...document.querySelectorAll('[data-part="shell/tab-bar"] button')].map((button) => ['bottom-bar', button]),
    ...[...document.querySelectorAll('#view [role="tab"], [data-part="screen"][data-open] [role="tab"]')].map((tab) => ['tab', tab]),
  ];
  for (const [name, control] of controls) {
    if (!control) { falls.push({arm: 'unseen', part: name, rect: null}); continue; }
    if (name !== 'menu' && !control.checkVisibility()) continue;
    // Made unreachable on purpose: a layer above marks the page `inert`, and
    // WebKit's hit test then passes through it to the document itself.
    if (control.closest('[inert]')) continue;
    const box = control.getBoundingClientRect();
    const inside = box.width >= 1 && box.height >= 1 && box.left >= -0.5 && box.right <= width + 0.5 && box.top >= -0.5
      && box.bottom <= innerHeight + 0.5;
    const hit = inside ? document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2) : null;
    // COVERED ON PURPOSE is not unseen: a screen pushed over the page, the
    // startup screen and the sign-in screen cover the frame by design, and
    // what sits under them is the page's state to hold, not this one's.
    if (hit && !control.contains(hit) && hit.closest(COVERS)) continue;
    const found = Boolean(hit) && control.contains(hit);
    // The DRAWING, not the button: an icon is its svg, a label its text.
    const drawing = control.querySelector('svg') || control;
    const drawn = drawing.getBoundingClientRect();
    const style = getComputedStyle(drawing);
    const ink = colour(drawing.tagName.toLowerCase() === 'svg' && style.stroke !== 'none' ? style.stroke : style.color);
    const contrast = ink[3] > 0 ? ratio(ink, under(control)) : 0;
    if (!found || drawn.width < 1 || drawn.height < 1 || contrast < 3)
      falls.push({arm: 'unseen', part: name, rect: [Math.round(drawn.width), Math.round(drawn.height), +contrast.toFixed(2),
        Math.round(box.top), hit ? (hit.closest('[data-part]')?.getAttribute('data-part') ?? hit.tagName) : 'outside']});
  }
  return falls;
}"""


def context_for(width, scheme="dark"):
    """Builds the browser context one pass is measured in.

    Args:
        width: The window's width in CSS pixels.
        scheme: The colour scheme the document is asked to follow.

    Returns:
        The context options — a phone below the frame's breakpoint, a desktop
        window out of the frame above it.
    """
    if width in PHONES:
        return {**PHONE, "viewport": {"width": width, "height": HEIGHT}, "color_scheme": scheme}
    return {"viewport": {"width": width, "height": HEIGHT}, "device_scale_factor": 1,
            "is_mobile": False, "has_touch": False, "color_scheme": scheme}


async def read_pass(browser, label, width, wanted, engine, scheme):
    """Opens the prototype for one pass and measures every wanted state.

    Args:
        browser: A launched Playwright browser of the pass's engine.
        label: How the pass is named in every fall it reads.
        width: The width to measure at.
        wanted: The state ids asked for, or None for every declared one.
        engine: The engine's name, which decides whether the controls' visibility is held.
        scheme: The colour scheme of the pass.

    Returns:
        A dict state id → the falls read there, and the JS errors seen.
    """
    served_copy.assert_unchanged(STARTED_AGAINST, f"opening the prototype for {label}")
    context = await browser.new_context(**context_for(width, scheme))
    if width in WINDOWS:
        # Before the document parses, so the harness's own inline script reads
        # it exactly as it reads the operator's remembered choice.
        await context.add_init_script("try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}")
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(f"{label}: {error}"))
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
        if engine == "webkit":
            readings[state] += await page.evaluate(VISIBLE, width)
    await context.close()
    return readings, errors


def passes_asked(environment=os.environ):
    """Lists the passes a run makes, narrowed by the environment.

    Args:
        environment: Where the narrowing is read — an empty one names every pass.

    Returns:
        The (label, engine, width, scheme) of each pass: Chromium at every width
        in the reference appearance, then WebKit at the iPhone's width in both.
    """
    widths = tuple(int(width) for width in environment.get("TM_RESPONSIVE_WIDTHS", "").split(",") if width) \
        or PHONES + WINDOWS
    engines = [engine for engine in environment.get("TM_RESPONSIVE_ENGINES", "chromium,webkit").split(",") if engine]
    passes = [(f"{width}px", "chromium", width, "dark") for width in widths] if "chromium" in engines else []
    if "webkit" in engines:
        passes += [(f"webkit-{scheme}@{IPHONE}px", "webkit", IPHONE, scheme) for scheme in ("light", "dark")]
    return passes


async def main():
    """Measures every named state in every pass and judges the falls."""
    wanted = [state for state in os.environ.get("TM_RESPONSIVE_STATES", "").split(",") if state] or None
    passes = passes_asked()
    whole = wanted is None and passes == passes_asked({})
    journal = Journal("R-conformity-a — every named state at every width and in the iPhone's engine: "
                      "no overflow, no cut, no bevel, every frame control seen")
    async with async_playwright() as playwright:
        browsers = {}
        if any(engine == "chromium" for _, engine, *_ in passes):
            browsers["chromium"] = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        if any(engine == "webkit" for _, engine, *_ in passes):
            browsers["webkit"] = await playwright.webkit.launch()
        gate = asyncio.Semaphore(PARALLEL)

        async def one(label, engine, width, scheme):
            async with gate:
                return label, await read_pass(browsers[engine], label, width, wanted, engine, scheme)

        started = time.monotonic()
        results = await asyncio.gather(*(one(*each) for each in passes))
        for browser in browsers.values():
            await browser.close()
    # The cost is printed on every run: where the whole sweep may run is
    # decided from it.
    print(f"measured in {time.monotonic() - started:.0f} s")
    per_state: dict[str, list[str]] = {}
    owed_seen: dict[tuple[str, str], set[str]] = {}
    errors = []
    for label, (readings, pass_errors) in results:
        errors += pass_errors
        for state, falls in readings.items():
            for fall in falls:
                key = (fall["arm"], fall["part"])
                if key in OWED:
                    owed_seen.setdefault(key, set()).add(f"{state}@{label}")
                    continue
                per_state.setdefault(state, [])
                line = f"{label} {fall['arm']} {fall['part']} {fall['rect']}"
                if line not in per_state[state]:
                    per_state[state].append(line)
    states = sorted({state for _, (readings, _) in results for state in readings})
    # The whole reading, to a file when asked: `run.sh` prints a failing rule's
    # first lines only, and the owed list is built from every fall.
    report = os.environ.get("TM_RESPONSIVE_REPORT")
    if report:
        with open(report, "w", encoding="utf-8") as handle:
            json.dump({"passes": [label for label, *_ in passes], "states": len(states), "falls": per_state,
                       "owed": {f"{arm} · {part}": sorted(seen) for (arm, part), seen in owed_seen.items()}},
                      handle, ensure_ascii=False, indent=1)
    print(f"{len(states)} state(s) × {len(passes)} pass(es) {[label for label, *_ in passes]}\n")
    for state in states:
        falls = per_state.get(state, [])
        journal.check(f"{state} in every pass", not falls, "; ".join(falls))
    for key, owner in OWED.items():
        seen = owed_seen.get(key, set())
        print(f"  OWED {key[0]} · {key[1]} → {owner} — {len(seen)} reading(s)"
              + (f", e.g. {sorted(seen)[0]}" if seen else ""))
        if whole:
            journal.check(f"owed {key[0]} · {key[1]} still falls", seen, "an owed entry that no longer falls leaves the list")
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

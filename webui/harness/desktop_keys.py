"""R488 — Keys and hover on a desktop: `/`, ↑/↓, Enter, Escape, and a ground under the pointer (phase 9).

The operator, 2026-10-01 — DECIDED 6 = B: « a small declared key set — `/` to the page's search, ↑/↓ in a
list, Enter opens, Escape closes — and a hover ground on rows, cards and tiles. No action exists only on
hover or only on a key. » `docs/features/maquette-desktop/DESIGN.md` § 1.4: only Escape and Tab existed;
no row, card or tile answered the pointer.

WHAT IS READ, out of the harness's phone frame, with a keyboard and a mouse, at 1024, 1280 and 1440:

  1. `/` puts the caret in the page's search (Médiathèque, Acquisition's follows, Réglages), and on a page
     with none (Trackers) moves nothing;
  2. ↓ from nowhere enters the list, ↓ and ↑ walk its rows (Acquisition, Trackers' torrents and roster),
     and in a gallery ↓ goes to the tile BELOW (Médiathèque); ↓ out of the search reaches the first tile;
  3. Enter opens the focused card, Escape closes what it opened and gives the focus back to the card;
  4. under an open panel no arrow reaches the page behind it;
  5. a card, a tile, a topic, a setting, a fact row and a tracker answer the pointer with a ground, and
     the pointer reveals no control the row did not already show;
  6. a right click on what has a panel — a card (its body too, which a tap opens), a tile, a torrent —
     opens that panel, the browser's menu refused there, and a text field keeps its own menu and opens
     nothing (DECIDED 8 = A, 2026-10-01: « sur ordinateur, un clic droit sur un élément qui a un panneau
     (carte, affiche, tuile) ouvre ce panneau, le même que l'appui long (qui reste) »).

And at 390, with a finger: no ground under a tap — hover is behind `@media (hover: hover)`.
"""
import asyncio

from common import PANEL_IN, PHONE, SETTLED, Journal, browser_channel, chrome_launch_args, open_page, read_at
from playwright.async_api import async_playwright

OUT_OF_FRAME = "try{localStorage.setItem('tm-desktop-switch','out-of-the-frame')}catch(e){}"


def desktop(width):
    """A desktop window of WIDTH, out of the frame, pointer only."""
    return {**PHONE, "viewport": {"width": width, "height": 800}, "is_mobile": False, "has_touch": False,
            "device_scale_factor": 1}


# What holds the focus, named the way the checks below read it.
FOCUSED = """() => {
  const a = document.activeElement;
  if (!a || a === document.body) return {part: null, id: null, type: null, x: null, y: null, inSheet: false, text: ''};
  const r = a.getBoundingClientRect();
  return {part: a.getAttribute('data-part'), id: a.id, type: a.getAttribute('type'), x: Math.round(r.left), y: Math.round(r.top),
          inSheet: !!a.closest('#sheet'), text: (a.textContent || '').trim().slice(0, 30)};
}"""

BLUR = "() => { document.activeElement?.blur?.(); }"

# The ground under the pointer: what a hovered element paints, beside what it paints untouched.
PAINT = """(selector) => {
  const e = [...document.querySelectorAll(selector)].find((x) => x.getBoundingClientRect().width > 0 && x.getBoundingClientRect().top > 60);
  if (!e) return null;
  e.scrollIntoView({block: 'center'});
  const s = getComputedStyle(e);
  const controls = [...e.querySelectorAll('button, a, [role="button"], input')].filter((c) => {
    const st = getComputedStyle(c), r = c.getBoundingClientRect();
    return r.width > 0 && st.visibility !== 'hidden' && parseFloat(st.opacity) > 0.05;
  }).length;
  const r = e.getBoundingClientRect();
  return {ground: s.backgroundColor + ' ' + s.boxShadow, controls, x: r.left + r.width / 2, y: r.top + Math.min(r.height / 2, 30)};
}"""

GROUNDS = (
    ("acq-now-loaded", '[data-part="card"]'),
    ("lib-grid", '[data-part="tile"]'),
    ("settings", '[data-part="topic"]'),
    ("settings-topic", '[data-part="setting/row"]'),
    ("system", 'button[data-part="flux/row-body"]'),
    ("trackers-roster", '[data-part="trackers/body"]'),
)

SEARCHES = (("lib-grid", "libq"), ("acq-follows-list", "follq"), ("settings", None))


async def key(page, name, settle=SETTLED):
    """Presses one key and lets the interface answer."""
    await page.keyboard.press(name)
    await page.wait_for_timeout(settle)
    return await page.evaluate(FOCUSED)


async def keys(journal, page, width):
    """The declared keys, walked at one width."""
    for state, field in SEARCHES:
        await read_at(page, state, BLUR)
        seen = await key(page, "/")
        journal.check(f"{width} {state}: `/` puts the caret in the page's search",
                      seen["type"] == "search" and (field is None or seen["id"] == field), f"{seen}")
    await read_at(page, "trackers-page", BLUR)
    seen = await key(page, "/")
    journal.check(f"{width} trackers-page: `/` with no search moves nothing", seen["part"] is None, f"{seen}")

    for state, part in (("acq-now-loaded", "card/body"), ("trackers-page", "card/body"), ("trackers-roster", "trackers/body")):
        await read_at(page, state, BLUR)
        first = await key(page, "ArrowDown")
        second = await key(page, "ArrowDown")
        back = await key(page, "ArrowUp")
        journal.check(f"{width} {state}: ↓ enters the list, ↓ walks down a row, ↑ walks back",
                      first["part"] == part and second["part"] == part and second["y"] > first["y"]
                      and back["y"] == first["y"], f"{first} → {second} → {back}")

    await read_at(page, "lib-grid", BLUR)
    first = await key(page, "ArrowDown")
    below = await key(page, "ArrowDown")
    journal.check(f"{width} lib-grid: in a gallery ↓ goes to the tile below, not the one beside",
                  first["part"] == "tile" and below["part"] == "tile" and below["x"] == first["x"] and below["y"] > first["y"],
                  f"{first} → {below}")
    await read_at(page, "lib-grid", BLUR)
    await key(page, "/")
    seen = await key(page, "ArrowDown")
    journal.check(f"{width} lib-grid: ↓ out of the search reaches the first tile", seen["part"] == "tile", f"{seen}")

    await read_at(page, "acq-now-loaded", BLUR)
    card = await key(page, "ArrowDown")
    await key(page, "Enter", PANEL_IN)
    opened = await page.evaluate("() => !!document.querySelector('#sheet[data-open]')")
    journal.check(f"{width} acq-now-loaded: Enter opens the focused card", opened, f"focused {card}")
    inside = await key(page, "ArrowDown")
    journal.check(f"{width}: under an open panel no arrow reaches the page behind", inside["part"] != "card/body" or inside["inSheet"],
                  f"{inside}")
    after = await key(page, "Escape", PANEL_IN)
    closed = await page.evaluate("() => !document.querySelector('#sheet[data-open]')")
    journal.check(f"{width}: Escape closes it and the focus is back on the card",
                  closed and after["part"] == "card/body" and after["y"] == card["y"], f"{after}")


async def grounds(journal, page, width):
    """The pointer's ground, and no control that only the pointer reveals."""
    for state, selector in GROUNDS:
        await read_at(page, state, "() => document.activeElement?.blur?.()")
        await page.mouse.move(2, 790)
        await page.wait_for_timeout(SETTLED)
        still = await page.evaluate(PAINT, selector)
        if still is None:
            journal.check(f"{width} {state}: {selector} drawn", False, "none found")
            continue
        await page.mouse.move(still["x"], still["y"])
        await page.wait_for_timeout(SETTLED)
        hovered = await page.evaluate(PAINT, selector)
        journal.check(f"{width} {state}: {selector} answers the pointer with a ground",
                      hovered["ground"] != still["ground"], f"{still['ground']} → {hovered['ground']}")
        journal.check(f"{width} {state}: the pointer reveals no control {selector} did not show",
                      hovered["controls"] == still["controls"], f"{still['controls']} → {hovered['controls']}")


# What a right click lands on, and the panel it must open. A card's BODY is the case the long press
# refuses to arm on (a tap opens it already); a right click has no tap after it, so it opens there too.
SECONDARY = (
    ("acq-now-loaded", '#view [data-part="card/body"]'),
    ("lib-grid", '#view [data-part="tile"]'),
    ("trackers-page", '#view [data-part="torrents/row"] [data-panel]'),
)

# Whether the last `contextmenu` was refused, read where it ends: the window, after the document's own
# listener has answered it.
MENU_WATCH = """() => { window.__menuRefused = null;
  window.addEventListener('contextmenu', (e) => { window.__menuRefused = e.defaultPrevented; }); }"""

POINT = """(selector) => {
  const e = [...document.querySelectorAll(selector)].find((x) => x.getBoundingClientRect().width > 0 && x.getBoundingClientRect().top > 60);
  if (!e) return null;
  e.scrollIntoView({block: 'center'});
  const r = e.getBoundingClientRect();
  return {x: r.left + r.width / 2, y: r.top + Math.min(r.height / 2, 30)};
}"""

SHEET_OPEN = "() => !!document.querySelector('#sheet[data-open]')"


async def secondary(journal, page, width):
    """A right click opens the panel of what it lands on; a text field keeps its menu."""
    await page.evaluate(MENU_WATCH)
    for state, selector in SECONDARY:
        await read_at(page, state, BLUR)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(PANEL_IN)
        point = await page.evaluate(POINT, selector)
        if point is None:
            journal.check(f"{width} {state}: {selector} drawn", False, "none found")
            continue
        await page.mouse.click(point["x"], point["y"], button="right")
        await page.wait_for_timeout(PANEL_IN)
        opened = await page.evaluate(SHEET_OPEN)
        refused = await page.evaluate("() => window.__menuRefused")
        journal.check(f"{width} {state}: a right click on {selector} opens its panel, the browser's menu refused",
                      opened and refused is True, f"panel {opened}, menu refused {refused}")
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(PANEL_IN)
    await read_at(page, "lib-grid", BLUR)
    point = await page.evaluate(POINT, "#libq")
    await page.mouse.click(point["x"], point["y"], button="right")
    await page.wait_for_timeout(PANEL_IN)
    opened = await page.evaluate(SHEET_OPEN)
    refused = await page.evaluate("() => window.__menuRefused")
    await page.keyboard.press("Escape")
    journal.check(f"{width} lib-grid: a right click in the search opens nothing and keeps the field's menu",
                  not opened and refused is False, f"panel {opened}, menu refused {refused}")


async def main():
    journal = Journal("R488 — Keys and hover on a desktop: `/`, ↑/↓, Enter, Escape, and a ground under the pointer")
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel=browser_channel(), args=chrome_launch_args())
        for width in (1024, 1280, 1440):
            context, page = await open_page(browser, **desktop(width))
            await context.add_init_script(OUT_OF_FRAME)
            await page.reload(wait_until="load")
            await page.evaluate("()=>window.__loadingDone?.()")
            page.on("pageerror", lambda error: errors.append(str(error)))
            await keys(journal, page, width)
            await grounds(journal, page, width)
            await secondary(journal, page, width)
            await context.close()

        context, page = await open_page(browser)
        hover = await page.evaluate("() => matchMedia('(hover: hover)').matches")
        await read_at(page, "lib-grid", "() => true")
        still = await page.evaluate(PAINT, '[data-part="tile"]')
        await page.mouse.move(still["x"], still["y"])
        await page.wait_for_timeout(SETTLED)
        touched = await page.evaluate(PAINT, '[data-part="tile"]')
        journal.check("390: a finger leaves no ground — hover is behind (hover: hover)",
                      not hover and touched["ground"] == still["ground"], f"hover {hover}: {still['ground']} → {touched['ground']}")
        await context.close()
        await browser.close()
    journal.summary(errors)


if __name__ == "__main__":
    asyncio.run(main())

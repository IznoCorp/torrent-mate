"""R65 — the drawer is a place one passes through, not a route.

Three defects lived here at once, and every existing rule stayed green through
all of them, because each drove a named state instead of walking the journey.

· Every entry led nowhere. The close unwound the layer's own history entry with
  `history.back()`, which is asynchronous, so its pop landed AFTER the arrival
  had rendered — and the popstate handler read that pop as a navigation and
  applied the entry underneath, which describes where one already was. The page
  changed for one frame and was put back.
· One entry pointed at an id no page carries, and answered a tap with a message.
· The entry marking where one IS was painted in its own colour: the background
  fell back onto `--primary` because `--sidebar-accent` is defined nowhere, and
  the label is `--primary` too. Contrast 1.00 — a label in invisible ink.

What the drawer owes, and what this script holds it to:

1. Every entry names a page that exists, and reaching it ARRIVES — measured
   after the frame settles, not on the frame the tap produced.
2. The drawer leaves nothing behind. A back from the destination lands where
   one was BEFORE opening it, because the destination took the drawer's own
   history entry rather than sitting after it.
3. Closing the drawer without going anywhere leaves the history where it was.
4. Closing a layer leaves the page underneath alone — neither rebuilt, nor
   scrolled back to its top. This one was never reported: a mutation found it
   while proving the rule bites, and it is the same root cause seen from the
   other side. A bottom panel opened halfway down a list sent the list home.
5. Every entry is legible, the current one included, measured as PAINTED:
   the label's colour against the colours composited behind it.
"""
import asyncio

from common import Journal, open_page
from playwright.async_api import async_playwright

# WCAG AA for body text. The current entry sat at 1.00 — the floor exists so a
# number that low can never again be reported as a colour choice.
CONTRAST_FLOOR = 4.5

WHERE = """() => ({
  page: state.page,
  drawer: document.querySelector('#drawer').hasAttribute('data-open'),
  scrim: document.querySelector('#scrim').hasAttribute('data-open'),
  layer: history.state && history.state.layer ? history.state.layer : null,
  nav: history.state && history.state.tm === 'nav' ? history.state.page : null,
})"""

# Colours are converted through a canvas, never parsed. `getComputedStyle`
# returns the colour space the author wrote — `oklch()` here — and three
# numbers pulled out of that string with a regex built for `rgb()` mean
# nothing. Drawing over white and again over black also recovers the alpha of
# a tint, which is what compositing a translucent surface needs.
CONTRAST = """() => {
  const cnv = document.createElement('canvas');
  cnv.width = cnv.height = 1;
  const ctx = cnv.getContext('2d', { willReadFrequently: true });
  const over = (color, background) => {
    ctx.fillStyle = background;
    ctx.fillRect(0, 0, 1, 1);
    ctx.fillStyle = color;
    ctx.fillRect(0, 0, 1, 1);
    return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3);
  };
  const rgba = (color) => {
    const white = over(color, '#fff');
    const black = over(color, '#000');
    const a = 1 - (white[0] - black[0]) / 255;
    return { rgb: black.map((v) => (a > 0 ? v / a : 0)), a };
  };
  const channel = (v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  const lum = (c) =>
    0.2126 * channel(c[0] / 255) + 0.7152 * channel(c[1] / 255) + 0.0722 * channel(c[2] / 255);
  const behind = (el) => {
    const stack = [];
    let node = el.parentElement;
    while (node) {
      const { rgb, a } = rgba(getComputedStyle(node).backgroundColor);
      if (a > 0.001) stack.push([rgb, a]);
      if (a > 0.999) break;
      node = node.parentElement;
    }
    let out = [255, 255, 255];
    for (let i = stack.length - 1; i >= 0; i--) {
      const [c, a] = stack[i];
      out = out.map((v, k) => c[k] * a + v * (1 - a));
    }
    return out;
  };
  return [...document.querySelectorAll('#drawer a[data-navgo]')].map((a) => {
    const s = getComputedStyle(a);
    const own = rgba(s.backgroundColor);
    let background = behind(a);
    if (own.a > 0.001) {
      background = background.map((v, k) => own.rgb[k] * own.a + v * (1 - own.a));
    }
    const text = rgba(s.color).rgb;
    const [l1, l2] = [lum(text), lum(background)].sort((x, y) => y - x);
    return {
      id: a.dataset.navgo,
      current: a.hasAttribute('aria-current'),
      contrast: Math.round(((l1 + 0.05) / (l2 + 0.05)) * 100) / 100,
    };
  });
}"""

# The ids the interface can actually render. An entry naming anything else is
# a dead end however carefully it is drawn.
PAGES = "() => window.__pages ? window.__pages() : null"


async def where(pg):
    """What the interface shows and what its history holds."""
    return await pg.evaluate(WHERE)


async def open_drawer(pg):
    """Opens the drawer through its handle, the only way in."""
    await pg.tap("[data-drawer]")
    await pg.wait_for_timeout(320)


async def close_via_scrim(pg, x=370, y=700):
    """Closes a layer by tapping outside it, which is where a thumb goes.

    The scrim is tapped by COORDINATE: it lies under the panel, so a selector
    tap resolves to the element and then waits forever for the panel to stop
    intercepting it. Which coordinate is free depends on the layer — the drawer
    is anchored left and full height, a bottom panel is anchored to the bottom
    edge — and a point that lands ON the layer taps its content instead. That
    mistake reads as the rule failing, which is the worst kind of green.
    """
    await pg.touchscreen.tap(x, y)
    await pg.wait_for_timeout(320)


async def main():
    journal = Journal("R65 — the drawer is a passage, not a route")

    async with async_playwright() as p:
        b = await p.chromium.launch(channel="chrome")

        # ── 1. Every entry names a page that exists, and reaching it arrives ──
        ctx, pg = await open_page(b)
        await open_drawer(pg)
        entries = await pg.eval_on_selector_all(
            "#drawer a[data-navgo]", "els => els.map((e) => e.dataset.navgo)")
        pages = await pg.evaluate(PAGES)
        journal.check("the drawer carries entries", len(entries) > 0,
                      f"{len(entries)} entries: {', '.join(entries)}")
        if pages is not None:
            unknown = [e for e in entries if e not in pages]
            journal.check("every entry names a page that exists", not unknown,
                          f"pages: {', '.join(pages)}"
                          + (f" — unknown: {', '.join(unknown)}" if unknown else ""))
        await ctx.close()

        for target in entries:
            ctx, pg = await open_page(b)
            start = (await where(pg))["page"]
            await open_drawer(pg)
            await pg.tap(f'#drawer a[data-navgo="{target}"]')
            # Long enough for an asynchronous pop to land: the defect showed a
            # correct frame first and was undone a tick later, so measuring
            # early would have certified it.
            await pg.wait_for_timeout(600)
            after = await where(pg)
            journal.check(
                f"« {target} » arrives and stays there",
                after["page"] == target and not after["drawer"],
                f"page={after['page']} drawer={after['drawer']} (start {start})")

            # ── 2. The drawer leaves nothing behind ──
            if target != start:
                await pg.go_back()
                await pg.wait_for_timeout(500)
                back = await where(pg)
                journal.check(
                    f"from « {target} », back returns to the start",
                    back["page"] == start and not back["drawer"],
                    f"page={back['page']} drawer={back['drawer']}")
            await ctx.close()

        # ── 3. Closing without going anywhere leaves history where it was ──
        ctx, pg = await open_page(b)
        before = await where(pg)
        await open_drawer(pg)
        opened = await where(pg)
        journal.check("opening the drawer stacks a layer, not a page",
                      opened["drawer"] and opened["layer"] == "drawer",
                      f"layer={opened['layer']}")
        # THE RUNG IS ON THE LADDER, and it is asked for by name. Since L15 the
        # drawer is a component and the back handler no longer tests
        # `#drawer.classList.contains("open")` — it asks a REGISTRATION
        # (`app/layer-registry.ts`). A rung that stopped registering is
        # invisible to every hold shaped like « Back closed what was open »:
        # the drawer would simply never be the thing Back reached, and the pop
        # would spend the entry underneath instead. The registration is read
        # here, and the two holds below are what say it works.
        rungs = await pg.evaluate("()=>window.__layers ? window.__layers.names() : null")
        journal.check("the drawer is a rung the ladder can name",
                      rungs is not None and "drawer" in rungs,
                      f"rungs={rungs}")
        journal.check("and the ladder's own reading agrees it is open",
                      await pg.evaluate("()=>window.__layers.isOpen('drawer')"),
                      "the registration says open")
        await close_via_scrim(pg)
        closed = await where(pg)
        journal.check("closing without going anywhere leaves the history intact",
                      not closed["drawer"] and closed["nav"] == before["nav"]
                      and closed["layer"] is None,
                      f"nav={closed['nav']} layer={closed['layer']}")

        # And back from there is the back of the page, not of the drawer: it
        # must not have to walk through an entry the drawer left behind.
        await pg.go_back()
        await pg.wait_for_timeout(500)
        after_back = await where(pg)
        journal.check("once closed, a back does not reopen the drawer",
                      not after_back["drawer"],
                      f"drawer={after_back['drawer']} page={after_back['page']}")
        await ctx.close()

        # ── 4. Closing a layer leaves the page underneath alone ──
        # The drawer is one of three layers that push an entry and pop it back.
        # When that pop is read as a navigation, the page underneath is rebuilt
        # from the entry describing where one already is — so a bottom panel
        # opened halfway down a list sent the list back to its top on closing.
        # Nobody reported it; a mutation found it. It is checked on the panel
        # rather than the drawer because a list is what one scrolls.
        for name, open_layer, outside in (
            # A bottom panel leaves the top of the frame free; the drawer leaves
            # its right.
            ("the panel", lambda pg: pg.tap('#view [data-part="card"] [data-panel]'), (195, 60)),
            ("the drawer", open_drawer, (370, 700)),
        ):
            ctx, pg = await open_page(b)
            await open_layer(pg)
            await pg.wait_for_timeout(450)
            await pg.evaluate("""() => {
              const mark = document.createElement('i');
              mark.id = 'r65-marker';
              document.querySelector('#view').appendChild(mark);
              document.querySelector('#port').scrollTop = 300;
            }""")
            await pg.wait_for_timeout(150)
            before_scroll = await pg.evaluate(
                "() => Math.round(document.querySelector('#port').scrollTop)")
            await close_via_scrim(pg, *outside)
            after = await pg.evaluate("""() => ({
              marker: !!document.querySelector('#r65-marker'),
              scroll: Math.round(document.querySelector('#port').scrollTop),
            })""")
            journal.check(
                f"closing {name} does not rebuild the page underneath",
                after["marker"], f"marker present={after['marker']}")
            journal.check(
                f"closing {name} does not lose where the page was scrolled",
                after["scroll"] == before_scroll,
                f"{before_scroll} → {after['scroll']}")
            await ctx.close()

        # ── 5. Every entry is legible, the current one included ──
        ctx, pg = await open_page(b)
        await open_drawer(pg)
        for row in await pg.evaluate(CONTRAST):
            journal.check(
                f"« {row['id']} »"
                + (" (the current entry)" if row["current"] else "")
                + " reads against its background",
                row["contrast"] >= CONTRAST_FLOOR,
                f"contrast {row['contrast']} (floor {CONTRAST_FLOOR})")
        await ctx.close()

        await b.close()

    journal.summary()


asyncio.run(main())

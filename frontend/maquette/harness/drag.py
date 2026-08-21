"""R64 — a row's quick actions, in both directions, on both engines.

A card body opens the bottom panel on a tap, and the same card answers a
horizontal drag. Two gestures on one object is exactly where a scope conflict
lives: a drag that also fires the tap opens a panel over the drawer it just
revealed, and a tap read as a drag moves a row nobody meant to move.

Three things this holds to, each of which was broken:

  · the drag runs BOTH ways — the right drawer holds what one does TO a medium,
    the left holds the one thing the row is FOR — and only ONE row is open at a
    time, because two open drawers ask which one an action belongs to and the
    answer is never on screen;
  · a drag never fires the tap, and an action inside the drawer always does —
    swallowing every click after a drag would kill the buttons the gesture
    exists to reach;
  · it renders identically on Chromium AND WebKit. The drawer used an automatic
    margin and WebKit sized it without honouring its children's flex-basis:
    148px for two 84px buttons, so they spilled twenty pixels past the rounded
    card. Measured on one engine, that defect is invisible.

Driven with `Input.dispatchTouchEvent` on Chromium — a synthetic event is never
cancelled and cannot tell whether a gesture survives the compositor. WebKit has
no such endpoint here, so the geometry is what is compared there, which is
exactly what was wrong on it.
"""
import asyncio

from common import Journal, open_page
from playwright.async_api import async_playwright


_journal = None


def check(name, condition, detail=""):
    """Records one executed check and its verdict, in the shared journal."""
    return _journal.check(name, condition, detail)


GEOMETRY = """() => {
  const sw = document.querySelector('#view .swipe');
  if (!sw) return null;
  const rs = sw.getBoundingClientRect();
  const side = (s) => {
    const e = sw.querySelector(s);
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return {l: Math.round(r.width * 10) / 10,
            actions: e.querySelectorAll('.act').length};
  };
  return {
    right: side('.side.right'), left: side('.side.left'),
    // What spills past the row is what a rounded card cannot hide.
    spills: [...sw.querySelectorAll('.act')].map(x => {
      const r = x.getBoundingClientRect();
      return Math.round(Math.max(rs.left - r.left, r.right - rs.right) * 10) / 10;}),
  };
}"""


async def on_the_list(p, launch):
    """Opens the prototype past the startup screen, on the follows list."""
    b = await launch()
    ctx, pg = await open_page(b)
    await pg.wait_for_timeout(450)
    await pg.evaluate("()=>window.__go('acq-follows-list')")
    await pg.wait_for_timeout(550)
    return b, ctx, pg


async def main():
    global _journal
    _journal = Journal("R64 — a row's drag")

    async with async_playwright() as p:
        # ── the geometry, on both engines ──────────────────────────────────
        measures = {}
        for name, launch in (("Chromium", lambda: p.chromium.launch(channel="chrome")),
                           ("WebKit", lambda: p.webkit.launch())):
            b, _, pg = await on_the_list(p, launch)
            measures[name] = await pg.evaluate(GEOMETRY)
            await b.close()

        for name, m in measures.items():
            check(f"{name}: the row has a drawer on each side",
                     m and m["right"] and m["left"], str(m))
            if m and m["right"]:
                check(f"{name}: the right drawer measures its buttons",
                         abs(m["right"]["l"] - m["right"]["actions"] * 84) < 1,
                         f"{m['right']['l']} for {m['right']['actions']} action(s)")
                check(f"{name}: no action spills past the row",
                         max(m["spills"]) <= 0.5, str(m["spills"]))

        chrome, webkit = measures.get("Chromium"), measures.get("WebKit")
        check("both engines draw the same drawer",
                 chrome and webkit
                 and abs(chrome["right"]["l"] - webkit["right"]["l"]) < 1,
                 f"{chrome and chrome['right']} vs {webkit and webkit['right']}")

        # ── the behaviour, under a real finger ─────────────────────────────
        b, ctx, pg = await on_the_list(p, lambda: p.chromium.launch(channel="chrome"))
        cdp = await ctx.new_cdp_session(pg)
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))

        async def drag(x, y, dx, step=14):
            """Drags one finger horizontally, in steps a thumb really makes."""
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
            n = max(1, abs(int(dx)) // step)
            for i in range(1, n + 1):
                await cdp.send("Input.dispatchTouchEvent",
                               {"type": "touchMove",
                                "touchPoints": [{"x": x + dx * i / n, "y": y, "id": 1}]})
                await asyncio.sleep(0.016)
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})
            await pg.wait_for_timeout(430)

        rows = await pg.evaluate(
            """()=>[...document.querySelectorAll('#view .swipe')].slice(0, 2).map(s => {
                 const r = s.getBoundingClientRect();
                 return {x: r.x + r.width * 0.6, y: r.y + r.height / 2};})""")
        check("at least two rows are drawn", len(rows) >= 2, str(len(rows)))

        async def positions():
            return await pg.evaluate(
                """()=>[...document.querySelectorAll('#view .swipe [data-part="card"]')].slice(0, 2)
                     .map(c => c.style.transform || '')""")

        await drag(rows[0]["x"], rows[0]["y"], -140)
        p0 = await positions()
        check("a drag to the left opens the right drawer",
                 p0[0].startswith("translateX(-"), str(p0))
        check("and it does NOT open the bottom panel",
                 not await pg.evaluate(
                     "()=>document.querySelector('#sheet').hasAttribute('data-open')"))

        await drag(rows[1]["x"], rows[1]["y"], -140)
        p1 = await positions()
        check("dragging another row puts the first one back",
                 p1[0] == "" and p1[1].startswith("translateX(-"), str(p1))

        await drag(rows[0]["x"], rows[0]["y"], 140)
        p2 = await positions()
        check("a drag to the right opens the left drawer",
                 p2[0].startswith("translateX(") and "-" not in p2[0], str(p2))

        # ── the reversal ───────────────────────────────────────────────────
        # An open row is dragged back, and the drag has to resume from where
        # the row IS. Assuming a side instead read a row open on the LEFT as
        # if it were open on the right, so its first move leapt the width of
        # both drawers.
        #
        # Sampled DURING the gesture, because a jump is a discontinuity: both
        # ends of a drag can be right while everything in between is wrong,
        # and a probe reading only the rest positions certifies it.
        async def where_is_it():
            """The first row's own offset, in pixels, 0 when it is at rest."""
            return await pg.evaluate(
                """()=>{const c = document.querySelector('#view .swipe [data-part="card"]');
                       const t = c && c.style.transform;
                       return t ? parseFloat(t.slice(t.indexOf('(') + 1)) : 0;}""")

        async def drag_watching(x, y, dx, step=14):
            """Drags a finger and reports where the row sat after each step."""
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]})
            n = max(1, abs(int(dx)) // step)
            samples = []
            for i in range(1, n + 1):
                await cdp.send("Input.dispatchTouchEvent",
                               {"type": "touchMove",
                                "touchPoints": [{"x": x + dx * i / n, "y": y, "id": 1}]})
                await asyncio.sleep(0.016)
                samples.append(await where_is_it())
            await cdp.send("Input.dispatchTouchEvent",
                           {"type": "touchEnd", "touchPoints": []})
            await pg.wait_for_timeout(430)
            return samples

        rest = await where_is_it()
        samples = await drag_watching(rows[0]["x"], rows[0]["y"], -60)
        # A step of the drag is 14 to 15 pixels. The ceiling is generous enough
        # that no honest step reaches it and far below the 252px the defect
        # produced, so it cannot be met by tightening a threshold.
        gap = abs(samples[0] - rest) if samples else None
        check("an open row follows the finger without leaping",
                 gap is not None and gap < 40,
                 f"rest {rest} → first sample {samples and samples[0]} (gap {gap})")

        p3 = await positions()
        check("the reverse drag settles it back at rest, without opening the other side",
                 p3[0] == "", str(p3))

        # And a LONG reverse drag settles at rest too. This is the operator's
        # own prescription — « elle devrait se replacer normalement et je
        # reswipe à gauche si je veux voir les actions à gauche » — and it is
        # what the clamp exists for: left to keep its sign, the travel of a row
        # dragged well past rest is read as a large one, so the row springs
        # back OPEN on the side it started from. A short reverse drag never
        # reaches that, which is why it has to be a long one here.
        await drag(rows[0]["x"], rows[0]["y"], 140)
        check("the left drawer is reopened for the next measurement",
                 (await positions())[0] == "translateX(84px)", str(await positions()))
        await drag(rows[0]["x"], rows[0]["y"], -200)
        p4 = await positions()
        check("a long reverse drag stops at rest, without setting off the other way",
                 p4[0] == "", str(p4))

        # A tap must still reach the panel: swallowing every click after a drag
        # would make the row unusable in the other direction. Tapped for REAL —
        # a programmatic click carries no pointerdown, so it never clears the
        # mark the previous drag left, and the probe would measure its own
        # shortcut rather than the interface.
        await pg.evaluate("""()=>{document.querySelectorAll('#view .swipe [data-part="card"]')"""
                          ".forEach(c => c.style.transform = '');}")
        await pg.wait_for_timeout(250)
        body = await pg.evaluate(
            """()=>{const b = document.querySelector('#view .swipe [data-part="card/body"]');
                   const r = b.getBoundingClientRect();
                   return {x: r.x + r.width / 2, y: r.y + 12};}""")
        await cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchStart",
                        "touchPoints": [{"x": body["x"], "y": body["y"], "id": 1}]})
        await pg.wait_for_timeout(70)
        await cdp.send("Input.dispatchTouchEvent",
                       {"type": "touchEnd", "touchPoints": []})
        await pg.wait_for_timeout(450)
        check("a plain tap still opens the panel",
                 await pg.evaluate(
                     "()=>document.querySelector('#sheet').hasAttribute('data-open')"))
        await pg.evaluate("()=>closeSheet()")
        await pg.wait_for_timeout(300)

        # And an action inside the drawer answers, which the click-swallowing
        # would otherwise have killed along with the tap. The row is measured
        # AGAIN: opening the panel re-renders the list, and a point read before
        # that lands on whatever replaced it.
        await pg.evaluate("()=>window.__go('acq-follows-list')")
        await pg.wait_for_timeout(550)
        rows = await pg.evaluate(
            """()=>[...document.querySelectorAll('#view .swipe')].slice(0, 1).map(s => {
                 const r = s.getBoundingClientRect();
                 return {x: r.x + r.width * 0.6, y: r.y + r.height / 2};})""")
        check("the list is on screen again", len(rows) == 1, str(len(rows)))
        await drag(rows[0]["x"], rows[0]["y"], -140)
        reachable = await pg.evaluate("""()=>{
          const a = document.querySelector('#view .swipe .side.right .act');
          if (!a) return null;
          const r = a.getBoundingClientRect();
          const onTop = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
          return !!(onTop && onTop.closest('.act'));}""")
        check("the revealed button really is under the finger",
                 reachable is True, str(reachable))

        # The scoping is proven with a MOUSE. After a touch drag the browser
        # suppresses the click itself, so a touch probe cannot tell a swallowed
        # click from a click that never happened — and a rule that cannot fail
        # proves nothing. A mouse drag really does fire one, in the same place,
        # which is exactly the case the swallowing exists for.
        await pg.evaluate("()=>window.__go('acq-follows-list')")
        await pg.wait_for_timeout(520)
        body = await pg.evaluate(
            """()=>{const b = document.querySelector('#view .swipe [data-part="card/body"]');
                   const r = b.getBoundingClientRect();
                   return {x: r.x + r.width / 2, y: r.y + 14};}""")
        await pg.mouse.move(body["x"], body["y"])
        await pg.mouse.down()
        for i in range(1, 11):
            await pg.mouse.move(body["x"] - 14 * i, body["y"])
            await asyncio.sleep(0.016)
        await pg.mouse.up()
        await pg.wait_for_timeout(450)
        check("with a mouse either, a drag does not open the panel",
                 not await pg.evaluate(
                     "()=>document.querySelector('#sheet').hasAttribute('data-open')"))
        check("and it did open the drawer",
                 (await positions())[0].startswith("translateX(-"), str(await positions()))

        check("no JS error", not errors, str(errors))
        await b.close()

    _journal.summary()

asyncio.run(main())
